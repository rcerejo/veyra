"""Distinct observed-entity counts with explicit fact evidence, not registered totals."""
import re

from app.schemas.query import CompositionalQuery,QueryActivity,QueryFilter,QueryGrouping,QueryJoin,QueryMeasure


def plan_activity(text,catalog,today=None):
    from app.query_engine.compositional import tokens,ref,CoverageError
    from app.query_engine.relationships import _roots
    from app.query_engine.temporal import split_window,calendar_window,timestamp_role
    if not re.search(r'\b(distinct|unique|different)\b',text) or not re.search(r'\b(active|daily|weekly|each day|per day|each week|per week)\b',text):
        return None
    if re.search(r'\b(list|then|fraction|ratio|not|without|having|or|best|retention|churn|conversion)\b',text):
        raise CoverageError('This observed-entity request has an unsupported list, Boolean, ordered or business-metric operation; specify a fact source and identity.')
    body,window=split_window(text)
    if window is None:
        from app.query_engine.planner import MONTHS
        bare=re.search(r'\s+(('+'|'.join(MONTHS)+r')\s+\d{1,2}\b.+\bthrough\b.+\b20\d{2}\b(?:\s+inclusive)?)$',body)
        if bare:
            body,window=body[:bare.start()],'from '+bare[1]
    qt=_roots(tokens(body))
    explicit_from=re.search(r'\bfrom (?:the )?(.+)$',body)
    explicit_fact=None
    if explicit_from:
        names=[t for t in catalog.tables if tokens(t)<=tokens(explicit_from[1])]
        if len(names)!=1:
            raise CoverageError('Specify one explicit fact source for the activity count.')
        explicit_fact=names[0]
    candidates=[]
    for source in catalog.tables:
        if explicit_fact and source!=explicit_fact:
            continue
        value_filters=[]
        for column,values in catalog.samples.get(source,{}).items():
            matches=[v for v in values if re.search(r'(?<!\w)'+re.escape(str(v).lower())+r'(?!\w)',body)
                     and (str(v).lower()!='active' or tokens(column)<=tokens(body))]
            if len(matches)>1:
                raise CoverageError('Specify a supported single event/category value for the distinct activity count.')
            if matches:
                value_filters.append(QueryFilter(field=ref(source,column),operator='eq',value=matches[0]))
        # Outgoing foreign-key walks preserve the activity fact grain. No reverse joins.
        paths=[(source,[],{source})]
        while paths:
            table,joins,seen=paths.pop()
            if len(joins)>1:
                continue
            grouped={}
            for key in catalog.tables[table].foreign_keys:
                grouped.setdefault((key.constraint_id,key.target_table),[]).append(key)
            for (identity,target),keys in grouped.items():
                if target not in catalog.tables or target in seen or any(k.target_column is None for k in keys):
                    continue
                target_columns={c.name for c in catalog.tables[target].columns}
                if any(k.target_column not in target_columns for k in keys):
                    continue
                equalities=[(ref(table,k.column),ref(target,k.target_column)) for k in sorted(keys,key=lambda k:k.sequence)]
                if len(keys)==1:
                    key=keys[0]
                    key_words=_roots(tokens(key.column)-{'id','key'})
                    entity_match=tokens(target)<=tokens(body)
                    role_match=bool(key_words & qt) and not bool(key_words & _roots(tokens(target)))
                    if entity_match or role_match:
                        lexical=_roots(tokens(source))&qt
                        evidence=(20 if explicit_fact else len(lexical)*10)+len(value_filters)*12+(5 if role_match else 0)
                        if evidence:
                            candidates.append((evidence,source,ref(table,key.column),target,joins,value_filters))
                if len(joins)<1:
                    paths.append((target,joins+[QueryJoin(left_table=table,right_table=target,equalities=equalities,constraint_id=identity)],seen|{target}))
    if not candidates:
        raise CoverageError('Activity requires an explicit fact source/category and an unambiguous entity FK, not a registered-population count.')
    candidates.sort(key=lambda c:-c[0])
    if len(candidates)>1 and candidates[0][0]==candidates[1][0]:
        raise CoverageError('Multiple activity facts or identity roles match; specify the fact table and entity key.')
    _,source,identity,target,joins,filters=candidates[0]
    measure=QueryMeasure(function='count',field=identity,distinct=True)
    plan=CompositionalQuery(entity=source,measure=measure,joins=joins,filters=filters,
        activity=QueryActivity(source=source,identity=identity,entity_table=target),requested_operations=['distinct','activity_identity'])
    day=bool(re.search(r'\b(daily|each day|per day)\b',body))
    week=bool(re.search(r'\b(weekly|each week|per week)\b',body))
    if day and week:
        raise CoverageError('Choose one calendar grain for the activity count.')
    if day or week:
        stamp=timestamp_role(catalog,source)
        plan.groupings=[QueryGrouping(field=stamp,grain='week' if week else 'day')]
        plan.filters.append(QueryFilter(field=stamp,operator='not_null'))
        plan.requested_operations.append('calendar_grouping')
    if window:
        plan.dates=[calendar_window(window,timestamp_role(catalog,source),today=today)]
        plan.requested_operations.append('date_window')
    if filters:
        plan.requested_operations.append('event_filter')
    # No categorical qualifier may be consumed unless its predicate was compiled.
    known=_roots(tokens('count number of how many show distinct unique different active daily weekly each day per week in from the a an rows records'))
    for table in {source,target,*[j.right_table for j in joins]}:
        known|=_roots(tokens(table))
    known|=_roots(tokens(identity.column))
    known|=_roots(tokens(' '.join(str(f.value) for f in filters)))
    residual=_roots(tokens(body))-known
    residual={w for w in residual if not _roots({w})&known}
    if residual:
        raise CoverageError('Unresolved activity qualifiers: '+', '.join(sorted(residual))+'. Specify the activity fields rather than dropping these conditions.')
    return plan
