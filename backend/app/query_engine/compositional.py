"""Bounded compositional planning. Unsupported operations never become raw-table fallbacks."""
from datetime import date, timedelta
import math
import re

import sqlglot
from sqlglot import exp

from app.database.schema import SchemaCatalog
from app.query_engine.planner import MONTHS
from app.query_engine.semantic import SemanticResult, _time_window, _quote, _qualified
from app.schemas.query import (ColumnRef, CompositionalQuery, QueryDateConstraint, QueryFilter,
    QueryGrouping, QueryJoin, QueryMeasure, QueryPlan, QueryRanking)


class CoverageError(ValueError):
    pass


def tokens(text):
    words=re.findall(r'[a-z0-9]+',text.casefold())
    irregular={'people':'person','children':'child'}
    return {irregular.get(w,w[:-3]+'y' if w.endswith('ies') else w[:-1] if w.endswith('s') and not w.endswith(('ss','us','status')) else w) for w in words}


def ref(table,column):
    return ColumnRef(table=table,column=column)


def numeric(column):
    return any(s in column.data_type.casefold() for s in ('int','real','float','double','numeric','decimal'))


def equality_value(column, raw):
    """Ground a scalar using declared type; never turn a numeric word into text SQL."""
    quoted=len(raw)>=2 and raw[0] in ('\"', "'") and raw[-1]==raw[0]
    value=raw[1:-1] if quoted else raw
    if not numeric(column):
        return value
    value=value.casefold()
    words=dict(zip(('zero','one','two','three','four','five','six','seven','eight','nine','ten'),range(11)))
    if not quoted and value in words:
        return words[value]
    if not re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?',value):
        raise CoverageError(f'{column.name} is numeric. Specify a numeric value; quoted text and undefined numeric descriptions will not be substituted.')
    if re.fullmatch(r'[-+]?\d+',value):
        number=int(value)
        if not -(2**63)<=number<2**63:
            raise CoverageError('The numeric equality value exceeds SQLite integer range.')
        return number
    number=float(value)
    if not math.isfinite(number):
        raise CoverageError('The numeric equality value must be finite.')
    return number


def distinct_field(text,catalog,base):
    """Bind the requested distinct attribute/role, not an unconditional source PK."""
    target=re.search(r'\b(?:distinct|different|unique)\s+(.+?)(?=\s+(?:from|where|whose|with|by|during|in|on|for|have|has|belong)\b|[?!]|$)',text)
    if not target:
        raise CoverageError('Specify the field or entity identity to count distinctly.')
    raw=target[1].strip().rstrip('.')
    qualified=re.fullmatch(r'([a-z_]\w*)\.([a-z_]\w*)',raw)
    if qualified:
        if qualified[1]!=base or qualified[2] not in {c.name for c in catalog.tables[base].columns}:
            raise CoverageError('The distinct field must resolve to the selected source table; specify the required relationship instead of substituting an ID.')
        return ref(base,qualified[2]),tokens(qualified[2])
    wanted=tokens(raw)-tokens('the a an number of are there records rows')
    table=catalog.tables[base]
    candidates=[]
    for column in table.columns:
        full=tokens(column.name)
        role=full-{'id','key'}
        if wanted==full or (role and wanted==role):
            candidates.append(column.name)
    # An entity name may identify a source FK, but only through a real declared edge.
    for key in table.foreign_keys:
        if key.target_table in catalog.tables and wanted==tokens(key.target_table):
            if key.target_column is None:
                raise CoverageError('The distinct entity relationship has an unresolved key.')
            same=[k for k in table.foreign_keys if k.constraint_id==key.constraint_id]
            if len(same)!=1:
                raise CoverageError('Composite distinct identities require an explicit supported definition.')
            candidates.append(key.column)
    candidates=list(dict.fromkeys(candidates))
    if len(candidates)==1:
        return ref(base,candidates[0]),wanted
    if len(candidates)>1:
        raise CoverageError('Multiple distinct identity fields or relationship roles match. Specify the source column, such as table.column.')
    primary=[c.name for c in table.columns if c.primary_key]
    if wanted==tokens(base) and len(primary)==1:
        return ref(base,primary[0]),wanted
    raise CoverageError('The requested distinct field or identity is unresolved. Specify its source column; I will not substitute the source row ID.')


def numeric_fields(catalog,table):
    fk={k.column for k in catalog.tables[table].foreign_keys}
    return [c for c in catalog.tables[table].columns if numeric(c) and not c.primary_key and c.name not in fk and not c.name.endswith(('_id','_key'))]


def date_field(catalog,table):
    fields=[c.name for c in catalog.tables[table].columns if any(s in c.name.casefold() for s in ('date','timestamp')) or c.name.casefold().endswith(('_at','_on'))]
    if len(fields)!=1:
        raise CoverageError(f'Choose the date field for {table}; found {len(fields)} possible timestamp roles.')
    return ref(table,fields[0])


def literal(value):
    if isinstance(value,(int,float)):
        return str(value)
    return "'"+str(value).replace("'","''")+"'"


def field_sql(field):
    return _qualified(field.table,field.column)


def filter_sql(predicate):
    col=field_sql(predicate.field)
    if predicate.operator in ('is_null','not_null'):
        return col+(' IS NULL' if predicate.operator=='is_null' else ' IS NOT NULL')
    operators={'eq':'=','ne':'<>','gt':'>','gte':'>=','lt':'<','lte':'<='}
    return f'{col} {operators[predicate.operator]} {literal(predicate.value)}'


def join_sql(join):
    if not join.equalities:
        raise CoverageError('Join predicate is missing.')
    return ' JOIN '+_quote(join.right_table)+' ON '+' AND '.join(field_sql(a)+' = '+field_sql(b) for a,b in join.equalities)


def date_predicates(constraint):
    field=field_sql(constraint.field)
    if constraint.normalized:
        field=f'JULIANDAY({field})'
    result=[]
    for value,operator in ((constraint.start,'>=' if constraint.start_inclusive else '>'),
                           (constraint.end,'<=' if constraint.end_inclusive else '<')):
        if value:
            bound=literal(value)
            if constraint.normalized:
                bound=f'JULIANDAY({bound})'
            result.append(f'{field} {operator} {bound}')
    return result


def compile_query(plan):
    if plan.unresolved_operations:
        raise CoverageError('Resolve these requested operations: '+', '.join(plan.unresolved_operations))
    selected=[]
    for i,g in enumerate(plan.groupings):
        expression=field_sql(g.field)
        if g.grain=='day':
            expression=f'DATE({expression})'
        elif g.grain=='week':
            expression=f"DATE({expression}, 'weekday 0', '-6 days')"
        selected.append(f'{expression} AS '+_quote('dimension' if i==0 else f'dimension_{i+1}'))
    if plan.measure:
        m=plan.measure
        arg=field_sql(m.field) if m.field else '*'
        if m.distinct:
            if m.field is None:
                raise CoverageError('Distinct counts require an explicit entity key.')
            arg='DISTINCT '+arg
        function={'count':'COUNT','sum':'SUM','average':'AVG'}[m.function]
        alias='record_count' if m.function=='count' else f'{m.function}_{m.field.column}'
        selected.append(f'{function}({arg}) AS {_quote(alias)}')
    elif not plan.groupings:
        selected=[_quote(plan.entity)+'.*']
    else:
        raise CoverageError('A grouping needs an explicit measure.')
    sql='SELECT '+('DISTINCT ' if plan.distinct else '')+', '.join(selected)+' FROM '+_quote(plan.entity)
    for join in plan.joins:
        sql+=join_sql(join)
    predicates=[filter_sql(f) for f in plan.filters]
    for related in plan.existence:
        if not related.correlations:
            raise CoverageError('Existence must remain correlated to the outer entity.')
        tables=[related.entity,*[j.right_table for j in related.joins]]
        if plan.entity in tables or len(tables)!=len(set(tables)):
            raise CoverageError('Self/repeated-table existence needs explicit aliases and is not supported.')
        if any(not ((a.table==plan.entity and b.table in tables) or (b.table==plan.entity and a.table in tables)) for a,b in related.correlations):
            raise CoverageError('Existence correlation must connect the outer entity to an inner table.')
        inner='SELECT 1 FROM '+_quote(related.entity)+''.join(join_sql(j) for j in related.joins)
        conditions=[field_sql(a)+' = '+field_sql(b) for a,b in related.correlations]
        conditions.extend(filter_sql(f) for f in related.filters)
        for constraint in related.dates:
            conditions.extend(date_predicates(constraint))
        for comparison in related.timestamps:
            if comparison.left.table not in tables or comparison.right.table!=plan.entity:
                raise CoverageError('Timestamp comparisons must bind an inner date role to the outer anchor.')
            op={'gt':'>','gte':'>=','lt':'<','lte':'<=','eq':'='}[comparison.operator]
            conditions.append(f'JULIANDAY({field_sql(comparison.left)}) {op} JULIANDAY({field_sql(comparison.right)})')
            predicates.append(f'JULIANDAY({field_sql(comparison.right)}) IS NOT NULL')
        predicates.append(('NOT ' if related.negated else '')+'EXISTS ('+inner+' WHERE '+' AND '.join(conditions)+')')
    for d in plan.dates:
        predicates.extend(date_predicates(d))
    if predicates:
        sql+=' WHERE '+' AND '.join(predicates)
    if plan.groupings:
        sql+=' GROUP BY '+', '.join(str(i+1) for i in range(len(plan.groupings)))
    if plan.ranking:
        sql+=' ORDER BY '+', '.join((field_sql(r.field) if r.field else str(len(selected)))+(' DESC' if r.descending else ' ASC') for r in plan.ranking)
    elif plan.groupings:
        sql+=' ORDER BY '+str(len(selected))+' DESC'
    elif not plan.measure:
        sql+=' ORDER BY 1'
    if plan.groupings or not plan.measure or plan.ranking:
        sql+=f' LIMIT {plan.limit}'
    return sql


def validate_coverage(plan,sql):
    """Conservative AST contract, including predicate Boolean structure and literal values.

    Not a SQL semantic-equivalence prover. Model rewrites with a different structure
    are withheld rather than assuming equivalent coverage.
    """
    expected=sqlglot.parse_one(compile_query(plan),read='sqlite')
    actual=sqlglot.parse_one(sql,read='sqlite')
    for node in (expected,actual):
        for identifier in node.find_all(exp.Identifier):
            identifier.set('quoted',False)
    for key,label in [('where','filters/date constraints'),('group','groupings'),('joins','relationships'),
                      ('expressions','measure/projection/distinctness'),('distinct','distinctness'),
                      ('from_','entity'),('order','ranking'),('limit','limit')]:
        if expected.args.get(key)!=actual.args.get(key):
            raise CoverageError(f'Generated SQL does not preserve the structured {label}.')
    if expected!=actual:
        raise CoverageError('Generated SQL adds an unplanned clause or changes the structured query.')


def joins_to(catalog,base,targets,question):
    joined={base}
    output=[]
    for target in targets:
        if target in joined:
            continue
        path=catalog.join_path(base,target)
        if not path:
            raise CoverageError(f'No explicit relationship connects {base} to {target}.')
        for left,right in zip(path,path[1:]):
            if right in joined:
                continue
            edges=[]
            for child,parent in ((left,right),(right,left)):
                groups={}
                for k in catalog.tables[child].foreign_keys:
                    if k.target_table==parent:
                        groups.setdefault(k.constraint_id,[]).append(k)
                for identity,keys in groups.items():
                    if any(k.target_column is None for k in keys):
                        raise CoverageError(f'The relationship from {child} to {parent} has an unresolved referenced key.')
                    if child==right:
                        raise CoverageError('This relationship expands the fact grain. Explicit preaggregation or a distinct entity definition is required before joining.')
                    score=len(tokens(' '.join(k.column for k in keys)) & tokens(question))
                    edges.append((score,identity,[(ref(child,k.column),ref(parent,k.target_column)) for k in sorted(keys,key=lambda k:k.sequence)]))
            if not edges:
                raise CoverageError(f'No validated relationship connects {left} to {right}.')
            edges.sort(key=lambda e:-e[0])
            if len(edges)>1 and edges[0][0]==edges[1][0]:
                raise CoverageError(f'{left} has multiple relationships to {right}. Specify the relationship role, such as origin or destination.')
            _,identity,equalities=edges[0]
            output.append(QueryJoin(left_table=left,right_table=right,equalities=equalities,constraint_id=identity))
            joined.add(right)
    return output


def parse_dates(text,catalog,base):
    # Multiple linked timestamp roles must not be reduced to one month predicate.
    if re.search(r'\bbut\b|\bthen\b',text):
        raise CoverageError('This query needs multiple related date roles; specify or configure their relationship before analysis.')
    field=date_field(catalog,base)
    years=re.findall(r'\b(20\d{2})\b',text)
    year=int(years[-1]) if years else date.today().year
    pattern=r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2})(?!\d)\b'
    named=list(re.finditer(pattern,text))
    if named:
        days=[date(year,MONTHS[m[1]],int(m[2])) for m in named]
        if len(days)>2:
            raise CoverageError('More than two date boundaries need an explicit window definition.')
        before=text[:named[0].start()]
        start=None if re.search(r'\bbefore\s*$',before) else days[0].isoformat()
        end=days[-1].isoformat() if len(days)==2 or start is None else None
        if len(days)==2 and re.search(r'\b(through|inclusive)\b',text):
            end=(days[-1]+timedelta(days=1)).isoformat()
        if len(days)==1 and re.search(r'\bon\s*$',before) and not re.search(r'after',before):
            end=(days[0]+timedelta(days=1)).isoformat()
        return QueryDateConstraint(field=field,start=start,end=end)
    iso=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',text)
    if iso:
        days=[date.fromisoformat(v) for v in iso]
        if len(days)!=2:
            raise CoverageError('Specify both ISO date boundaries and whether the end is exclusive.')
        return QueryDateConstraint(field=field,start=days[0].isoformat(),end=days[1].isoformat())
    window=_time_window(text)
    if window:
        return QueryDateConstraint(field=field,start=window[0],end=window[1])
    raise CoverageError('The requested date condition is not supported; specify a clear calendar window.')


def plan_compositional(question,catalog,today=None):
    text=question.casefold().strip()
    plan=None
    try:
        from app.query_engine.activity_planner import plan_activity
        activity=plan_activity(text,catalog,today=today)
        if activity is not None:
            sql=compile_query(activity)
            validate_coverage(activity,sql)
            return SemanticResult(plan=QueryPlan(intent='aggregation',metric='distinct_observed_entities',
                dimensions=[g.field.column for g in activity.groupings],relevant_tables=[activity.entity,*[j.right_table for j in activity.joins]],composition=activity),sql=sql)
        from app.query_engine.relationships import plan_relationship
        plan=plan_relationship(text,catalog,today=today)
        if plan is not None:
            sql=compile_query(plan)
            validate_coverage(plan,sql)
            relevant=[plan.entity]
            for related in plan.existence:
                relevant.extend([related.entity,*[j.right_table for j in related.joins]])
            return SemanticResult(plan=QueryPlan(intent='aggregation' if plan.measure else 'lookup',
                metric=plan.measure.function if plan.measure else None,relevant_tables=list(dict.fromkeys(relevant)),composition=plan),sql=sql)
        if re.search(r'\b(retention|churn|activation|conversion|funnel|best)\b|\b(?:daily|weekly|monthly) active users\b',text):
            raise CoverageError('Confirm the metric definition, entity, qualifying activity and observation window before calculating this analytical metric.')
        if re.search(r'\b(then|fraction|ratio|without|having)\b|\bwith no\b|\bwho are not\b|\bmore than (?:one|two)\b|\bat least (?:two|three)\b',text):
            raise CoverageError('This request needs an ordered, ratio, or related-record condition that this planner version cannot compile safely. Specify the relationship/steps and denominator; it will not be replaced by a simple count.')
        grouping_match=re.search(r'\b(?:by|per|in each)\s+(.+?)(?:\s+(?:in|from|during|where|for)\b|$)',text)
        grouping_text=(re.split(r',?\s+(?:including|counting|deduplicating|not|breaking|allowing)\b',grouping_match[1],maxsplit=1)[0] if grouping_match else '')
        subject=text[:grouping_match.start()] if grouping_match else text
        qt=tokens(subject)
        scores={t:len(tokens(t)&qt)*10+(25 if t.replace('_',' ') in subject else 0) for t in catalog.tables}
        average=bool(re.search(r'\b(average|avg|mean)\b',text))
        summing=bool(re.search(r'\b(total|sum|net)\b',text))
        counting=bool(re.search(r'\b(how many|counts?|number of)\b',text))
        metric_candidates=[]
        for table in catalog.tables:
            for c in numeric_fields(catalog,table):
                overlap=len((tokens(c.name)-{'id','key'})&tokens(subject))
                if overlap:
                    metric_candidates.append((overlap+scores[table]/100,table,c.name))
        if (average or summing) and metric_candidates:
            metric_candidates.sort(reverse=True)
            if len(metric_candidates)>1 and metric_candidates[0][0]==metric_candidates[1][0]:
                raise CoverageError('Multiple numeric measures match. Specify the table and measure column.')
            _,base,measure_column=metric_candidates[0]
        else:
            ranked=sorted(scores,key=lambda t:(-scores[t],t))
            if not ranked or scores[ranked[0]]==0:
                raise CoverageError('I could not identify the fact/entity table. Specify its name or configure an entity mapping.')
            if len(ranked)>1 and scores[ranked[0]]==scores[ranked[1]]:
                raise CoverageError('I found multiple equally likely tables: '+', '.join(t for t in ranked if scores[t]==scores[ranked[0]])+'. Specify the entity or relationship.')
            base=ranked[0]
            measure_column=None
        plan=CompositionalQuery(entity=base)
        if counting:
            plan.measure=QueryMeasure(function='count')
        elif average or summing:
            if not measure_column:
                raise CoverageError(f'Which numeric field from {base} should I aggregate?')
            plan.measure=QueryMeasure(function='average' if average else 'sum',field=ref(base,measure_column))
        if plan.measure:
            plan.requested_operations.append('measure')
        # Group dimensions are individually grounded, not collapsed to one lexical match.
        if grouping_match:
            for phrase in re.split(r'\s+and\s+|,',grouping_text):
                if phrase.strip()=='day':
                    continue
                candidates=[]
                pt=tokens(phrase)
                for table in catalog.tables.values():
                    for c in table.columns:
                        ct=tokens(c.name)-{'id','key'}
                        if ct and ct<=pt:
                            identifier=c.primary_key or c.name.endswith(('_id','_key'))
                            score=len(ct)*10+len(tokens(table.name)&pt)*3+(1 if table.name==base else 0)+(0 if identifier else 5)
                            candidates.append((score,table.name,c.name))
                candidates.sort(reverse=True)
                if not candidates or (len(candidates)>1 and candidates[0][0]==candidates[1][0]):
                    raise CoverageError(f'The grouping "{phrase}" is missing or ambiguous; specify table.column and its relationship role.')
                _,table,col=candidates[0]
                plan.groupings.append(QueryGrouping(field=ref(table,col)))
            plan.requested_operations.append('grouping')
            if plan.measure is None:
                # A grouping-only phrase must not silently invent a measure.
                if re.search(r'\b(break down|breakdown)\b',text):
                    plan.measure=QueryMeasure(function='count')
                else:
                    raise CoverageError('Specify whether to count rows or aggregate a numeric field for this grouping.')
        if re.search(r'\b(daily|each day|per day)\b',text):
            plan.groupings.append(QueryGrouping(field=date_field(catalog,base),grain='day'))
            plan.requested_operations.append('daily_grouping')
        if re.search(r'\b(weekly|monthly|each week|each month)\b',text):
            raise CoverageError('Weekly/monthly grouping needs an explicit calendar definition; this increment supports daily grouping only.')
        # Distinct entities require a key, not COUNT(*).
        distinct_words=set()
        if re.search(r'\b(distinct|different|unique)\b',text):
            if not counting:
                raise CoverageError('Specify the distinct key and whether to count or list unique entities.')
            identity,distinct_words=distinct_field(text,catalog,base)
            plan.measure=QueryMeasure(function='count',field=identity,distinct=True)
            plan.requested_operations.append('distinct')
            # Related participation cannot be silently replaced by all entities.
            if re.search(r'\b(have|has|belong|with)\b',subject):
                raise CoverageError('A distinct participating-entity count needs the related fact table and participation condition; configure that relationship explicitly.')
        # Equality filters are based on bounded safe category samples.
        explicit_equalities=[]
        sample_subject=subject
        # Terminal prose punctuation is not part of an unquoted value. Quoted
        # literals (including their punctuation) remain untouched.
        equality_question=question.rstrip().rstrip('.?!')
        for column in catalog.tables[base].columns:
            phrase=r'[ _]+'.join(re.escape(p) for p in column.name.split('_'))
            value_pattern=r'(\"[^\"]*\"|\'[^\']*\'|[^\s,;?!]+)'
            matches=list(re.finditer(r'\b'+phrase+r'\s+(?:is|equals|=)\s+'+value_pattern,equality_question,re.I))
            # A bounded numeric adjective form: "with zero fee". Do not
            # infer an operator for arbitrary field/value proximity.
            if numeric(column):
                number_pattern=r'(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)'
                # "minutes of lesson viewing" is a measure description, not
                # an equality. Only a bounded numeric literal licenses "of".
                matches+=list(re.finditer(r'\b'+phrase+r'\s+of\s+('+number_pattern+r')(?=$|[\s,;?!])',equality_question,re.I))
                matches+=list(re.finditer(r'\bwith\s+(zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+'+phrase+r'\b',equality_question,re.I))
            if len(matches)>1:
                raise CoverageError('Multiple explicit equalities for one field need a supported Boolean definition; no condition will be dropped.')
            match=matches[0] if matches else None
            if match and match[1].casefold() not in ('missing','null','not'):
                explicit_equalities.append((column,match[1]))
                # A value bound to one explicit field is not a category predicate
                # on every other column which happens to contain the same value.
                if match.start()<len(subject):
                    sample_subject=sample_subject[:match.start()]+' '*(min(match.end(),len(subject))-match.start())+sample_subject[min(match.end(),len(subject)):]
        for table,columns in catalog.samples.items():
            if table!=base:
                continue
            for column,values in columns.items():
                matched=[v for v in values if re.search(r'(?<!\w)'+re.escape(str(v).casefold())+r'(?!\w)',sample_subject)]
                if len(matched)>1:
                    raise CoverageError('Multiple category values require an explicit AND/OR choice.')
                if matched:
                    plan.filters.append(QueryFilter(field=ref(table,column),operator='eq',value=matched[0]))
        # Explicit column equality supports values not present in samples.
        equality_words=set()
        has_numeric_equality=False
        for column,raw in explicit_equalities:
            value=equality_value(column,raw)
            plan.filters=[f for f in plan.filters if f.field.column!=column.name]
            plan.filters.append(QueryFilter(field=ref(base,column.name),operator='eq',value=value))
            equality_words|=tokens(raw)
            has_numeric_equality|=numeric(column)
        numeric_columns=numeric_fields(catalog,base)
        mentioned=[c for c in numeric_columns if (tokens(c.name)-{'id','key'})&tokens(subject)]
        candidate=mentioned[0] if len(mentioned)==1 else numeric_columns[0] if len(numeric_columns)==1 else None
        comparators=list(re.finditer(r'\b(at least|at most|greater than|less than|more than|heavier than|over|under)\s+(-?\d+(?:\.\d+)?)',text))
        for comparator in comparators:
            if not candidate:
                raise CoverageError('Specify which numeric field the requested threshold applies to.')
            operator={'at least':'gte','at most':'lte','greater than':'gt','more than':'gt','heavier than':'gt','over':'gt','under':'lt','less than':'lt'}[comparator[1]]
            plan.filters.append(QueryFilter(field=ref(base,candidate.name),operator=operator,value=float(comparator[2])))
        if re.search(r'\bnegative\b',text):
            if not candidate:
                raise CoverageError('Specify the numeric field whose values must be negative.')
            plan.filters.append(QueryFilter(field=ref(base,candidate.name),operator='lt',value=0))
        if re.search(r'\b(missing|null|nonmissing)\b',text):
            fields=[c for c in catalog.tables[base].columns if not c.primary_key and not c.name.endswith(('_id','_key')) and (tokens(c.name)-{'id','key'})&tokens(subject)]
            if len(fields)!=1:
                raise CoverageError('Specify which field is missing or nonmissing.')
            plan.filters.append(QueryFilter(field=ref(base,fields[0].name),operator='not_null' if 'nonmissing' in text else 'is_null'))
        if plan.filters:
            plan.requested_operations.append('filters')
        # Detect date requests independently of whether a date column happened to match.
        if re.search(r'\b('+'|'.join(MONTHS)+r')\b|\b20\d{2}-\d{2}-\d{2}\b|\b(?:last|this) (?:week|month|\d+ days)\b',text):
            plan.dates=[parse_dates(text,catalog,base)]
            if any(d.start and d.end and d.start>=d.end for d in plan.dates):
                raise CoverageError('The date window must end after it starts.')
            plan.requested_operations.append('date_window')
        if re.search(r'\b(on or after|before|after|join date|shipping date)\b',text) and not plan.dates:
            raise CoverageError('The requested timestamp comparison is not represented; specify both date roles.')
        # Unsupported predicates must not become unfiltered lookups.
        if re.search(r'\b(with|whose|where|at stage)\b',subject) and not plan.filters and not plan.dates or (' for ' in subject and not plan.measure and not plan.filters and not plan.dates):
            raise CoverageError('The requested condition could not be grounded. Specify its table, field, operator and value.')
        if re.search(r'\b(not|except|or|between)\b|[<>!=]',text.replace('on or after','on after')):
            raise CoverageError('This predicate form needs an explicit supported condition; it will not be omitted.')
        plan.joins=joins_to(catalog,base,[g.field.table for g in plan.groupings],text)
        if plan.joins:
            plan.requested_operations.append('relationships')
        if re.search(r'\b(top|most|heaviest|descending|ascending|break ties|breaking ties)\b',text.replace('at most','at maximum')):
            plan.requested_operations.append('ranking')
            raise CoverageError('Ranking and tie-breaking are represented but not resolved in this increment. Specify the ranking measure and tie keys.')
        limit_match=re.search(r'\b(?:limit|first|only|list|show)\s+(\d+)\b',text)
        if limit_match:
            limit=int(limit_match[1])
            if not 1<=limit<=5000 or plan.measure:
                raise CoverageError('Specify a row-list limit from 1 to 5000; aggregate/ranked limits need an explicit ranking definition.')
            plan.limit=limit
            plan.requested_operations.append('limit')
        if re.search(r'\d',text) and not (comparators or plan.dates or limit_match or has_numeric_equality):
            raise CoverageError('A numeric/date qualifier is not represented; specify its field/operator or date boundaries.')
        # Multiple explicitly mentioned fact tables without a represented join are unsupported.
        referenced={t for t in catalog.tables if tokens(t)<=tokens(subject)}
        referenced={t for t in referenced if not any(tokens(t)<tokens(other) for other in referenced)}
        if plan.measure and plan.measure.distinct:
            # A bound FK identity is not an unrepresented join to its parent table.
            referenced-={k.target_table for k in catalog.tables[base].foreign_keys
                         if k.column==plan.measure.field.column and (tokens(k.target_table)==distinct_words or tokens(k.column)==distinct_words)}
        connected={base,*[j.right_table for j in plan.joins]}
        if referenced-connected:
            raise CoverageError('The requested related table condition is not represented; specify its join and inclusion/exclusion rule.')
        # Account for leftover content words rather than accepting an unknown adjective
        # as permission to return every row. This is bounded grammar coverage, not a
        # claim of complete natural-language understanding.
        grammar=tokens('show list give me all records rows data instances how many are there exist count number of total sum net average mean avg nonmissing missing null negative distinct unique different in on from during for between to through inclusive before after or and at least most greater less than over under heavier whose where is equals of the a an each day daily grouped including states with please break down amounts relationships ledger limit first only')
        known=set(grammar)|set(MONTHS)|equality_words|distinct_words|tokens(' '.join(str(f.value) for f in plan.filters if f.value is not None))
        for table in connected:
            known|=tokens(table)
            for column in catalog.tables[table].columns:
                known|=tokens(column.name)
        residual={w for w in tokens(subject)-known if not w.isdigit()}
        # Simple viewing/view morphology is shared by schema and ordinary prose.
        residual={w for w in residual if not (w.endswith('ing') and w[:-3] in known)}
        if residual:
            raise CoverageError('These requested terms are not grounded in the plan: '+', '.join(sorted(residual))+'. Specify the field/condition or approve a semantic mapping.')
        sql=compile_query(plan)
        validate_coverage(plan,sql)
        filters={f'{f.field.table}.{f.field.column}':f.value for f in plan.filters if f.operator=='eq' and f.value is not None}
        query_plan=QueryPlan(intent='aggregation' if plan.measure else 'lookup',metric=plan.measure.function if plan.measure else None,
            dimensions=[g.field.column for g in plan.groupings],filters=filters,time_range='explicit_window' if plan.dates else None,
            relevant_tables=[base,*[j.right_table for j in plan.joins]],composition=plan)
        return SemanticResult(plan=query_plan,sql=sql)
    except (CoverageError,ValueError) as exc:
        if plan is not None:
            plan.unresolved_operations.append(str(exc))
        return SemanticResult(plan=QueryPlan(intent='unknown',composition=plan),clarification=str(exc))
