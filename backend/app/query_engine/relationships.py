"""Restricted relation-existence grammar, preserving outer-row grain with correlated EXISTS.

No database access, schema-specific aliases, metric inference, or evaluator imports.
"""
from collections import deque
import re

from app.schemas.query import CompositionalQuery,QueryExistence,QueryFilter,QueryJoin,QueryMeasure,QueryTimestampComparison


def _roots(words):
    result=set(words)
    for word in words:
        for suffix in ('ment','ed','ing','ion'):
            if word.endswith(suffix) and len(word)>len(suffix)+2:
                result.add(word[:-len(suffix)])
    return result


def _match_table(phrase,catalog,morphology=False):
    from app.query_engine.compositional import tokens,CoverageError
    words=_roots(tokens(phrase)) if morphology else tokens(phrase)
    matches=[]
    for name in catalog.tables:
        wanted=_roots(tokens(name)) if morphology else tokens(name)
        # Morphology is only a grounding hint, not permission to drop qualifiers.
        if (wanted & words if morphology else wanted<=words):
            score=len(tokens(name)&tokens(phrase))*10+len(tokens(name))
            matches.append((score,name))
    if not matches:
        return None
    matches.sort(reverse=True)
    if len(matches)>1 and matches[0][0]==matches[1][0]:
        raise CoverageError('Multiple related entities match. Specify the outer entity and the related table.')
    return matches[0][1]


def _paths(catalog,outer,target):
    """Bounded deterministic shortest paths; never choose an arbitrary equal-length path."""
    from app.query_engine.compositional import CoverageError
    graph={t:set() for t in catalog.tables}
    for table in catalog.tables.values():
        for key in table.foreign_keys:
            if key.target_table in graph and key.target_table!=table.name:
                graph[table.name].add(key.target_table)
                graph[key.target_table].add(table.name)
    queue=deque([(outer,)])
    results=[]
    shortest=None
    visits=0
    while queue:
        path=queue.popleft()
        visits+=1
        if visits>1000:
            raise CoverageError('Relationship discovery exceeds the bounded planner budget.')
        if shortest is not None and len(path)>shortest:
            break
        if path[-1]==target:
            results.append(path)
            shortest=len(path)
            if len(results)>20:
                raise CoverageError('Too many candidate relationships; specify a path.')
        elif len(path)<4:
            for neighbor in sorted(graph[path[-1]]-set(path)):
                queue.append((*path,neighbor))
    return results


def _bridge_path(catalog,path):
    if len(path)!=3:
        return False
    bridge=catalog.tables[path[1]]
    primary={c.name for c in bridge.columns if c.primary_key}
    foreign={k.column for k in bridge.foreign_keys}
    targets={k.target_table for k in bridge.foreign_keys}
    return len(primary)>=2 and primary<=foreign and {path[0],path[-1]}<=targets


def _edge(catalog,left,right,phrase):
    from app.query_engine.compositional import tokens,ref,CoverageError
    candidates=[]
    for child,parent in ((left,right),(right,left)):
        grouped={}
        for key in catalog.tables[child].foreign_keys:
            if key.target_table==parent:
                grouped.setdefault(key.constraint_id,[]).append(key)
        for identity,keys in grouped.items():
            source={c.name for c in catalog.tables[child].columns}
            target={c.name for c in catalog.tables[parent].columns}
            if any(k.column not in source or k.target_column not in target for k in keys):
                raise CoverageError('The referenced relationship key is missing or unresolved; repair/approve that relationship first.')
            keys.sort(key=lambda k:k.sequence)
            score=len(tokens(' '.join(k.column for k in keys)) & tokens(phrase))
            candidates.append((score,identity,[(ref(child,k.column),ref(parent,k.target_column)) for k in keys]))
    candidates.sort(key=lambda item:-item[0])
    if not candidates or len(candidates)>1 and candidates[0][0]==candidates[1][0]:
        raise CoverageError('Relationship roles are missing or ambiguous; specify the foreign-key role.')
    _,identity,equalities=candidates[0]
    return identity,equalities


def plan_relationship(text,catalog,today=None):
    from app.query_engine.compositional import tokens,ref,CoverageError
    from app.query_engine.temporal import split_window,split_anchor_comparison,timestamp_role,calendar_window
    match=re.fullmatch(r'(.+?)\s+(without|with no|have no|has no|have|has|belongs? to|with)\s+(.+?)[?.!]*',text)
    if not match:
        prefix,compare,anchor=split_anchor_comparison(text)
        if compare:
            outer_candidate=_match_table(prefix,catalog)
            candidates=[]
            for table,columns in catalog.samples.items():
                matched={str(v) for values in columns.values() for v in values if re.search(r'(?<!\w)'+re.escape(str(v).lower())+r'(?!\w)',prefix)}
                if matched:
                    candidates.append((table,matched))
            if outer_candidate and len(candidates)==1 and candidates[0][0]!=outer_candidate:
                table,values=candidates[0]
                outer_prefix=prefix
                for value in values:
                    outer_prefix=re.sub(r'(?<!\w)'+re.escape(value.lower())+r'(?!\w)','',outer_prefix)
                rewritten=outer_prefix.strip()+' with '+' '.join(sorted(values))+' '+table.replace('_',' ')+' '+compare+' their '+anchor
                match=re.fullmatch(r'(.+?)\s+(with)\s+(.+?)[?.!]*',rewritten)
    if not match and re.search(r'\bbut\b',text):
        pieces=re.split(r'\s+but\s+',text,maxsplit=1)
        if len(pieces)==2 and split_window(pieces[0])[1] and split_window(pieces[1])[1]:
            match=re.fullmatch(r'(.+?)\s+(with)\s+(.+?)[?.!]*',pieces[0]+' with '+pieces[1])
    if not match:
        return None
    outer_text,operator,related_text=match.groups()
    outer_text,outer_window=split_window(outer_text)
    related_text,inner_window=split_window(related_text)
    related_text,comparison_operator,anchor_hint=split_anchor_comparison(related_text)
    target=_match_table(related_text,catalog)
    if target is None:
        target=_match_table(related_text,catalog,morphology=True)
    if target is None:
        return None  # Non-relational filters remain with the existing planner.
    if not re.match(r'^(list|show|count|how many|number of)\b',outer_text):
        raise CoverageError('Specify whether to list outer entities or count those with/without related records.')
    unconsumed=outer_text+' '+related_text
    if re.search(r'\b(and|or|then|both|before|after|during|daily|weekly|monthly|by|per|at least|more than|best|retention|conversion|activation|churn|funnel)\b|\d|[<>=!]',unconsumed):
        raise CoverageError('This relationship request includes a compound, temporal, grouped, or metric operation not supported by this existence increment; it will not be omitted.')
    outer=_match_table(outer_text,catalog)
    if outer is None:
        raise CoverageError('Specify the outer entity table for the participation/absence question.')
    if outer==target:
        raise CoverageError('Self-relationships require explicit aliases and role mappings.')
    grammar=tokens('list show count how many number of different distinct unique the all a an are there records rows')
    outer_dates=[]
    inner_dates=[]
    comparisons=[]
    years=re.findall(r'\b(20\d{2})\b',text)
    inherited_year=int(years[0]) if years else None
    role_words=tokens(outer_text)-tokens(outer)-grammar
    if outer_window:
        outer_role=timestamp_role(catalog,outer,' '.join(sorted(role_words)))
        outer_dates=[calendar_window(outer_window,outer_role,today=today,year=inherited_year)]
        role_words-=tokens(outer_role.column)
    if role_words:
        raise CoverageError('An outer-entity qualifier is unresolved. Specify its field/condition separately.')
    if inner_window or comparison_operator:
        # Entity/category words are not implicit date roles. Prefer an explicitly
        # mentioned date-field stem; otherwise require exactly one date column.
        date_columns=[c for c in catalog.tables[target].columns if any(s in c.name.lower() for s in ('date','timestamp','time')) or c.name.lower().endswith(('_on','_at'))]
        role_hint=' '.join(w for w in tokens(related_text) if any(_roots({w})&_roots(tokens(c.name)) for c in date_columns))
        inner_role=timestamp_role(catalog,target,role_hint)
        if inner_window:
            inner_dates=[calendar_window(inner_window,inner_role,today=today,year=inherited_year)]
        if comparison_operator:
            anchor=timestamp_role(catalog,outer,anchor_hint)
            comparisons=[QueryTimestampComparison(left=inner_role,right=anchor,operator={
                'after':'gt','before':'lt','on or after':'gte','at or after':'gte','on or before':'lte','at or before':'lte'}[comparison_operator])]
    paths=_paths(catalog,outer,target)
    if operator.startswith('belong'):
        # A unique activity path is not evidence of membership. Require a direct
        # declared relation or an unambiguous structural association bridge.
        paths=[path for path in paths if len(path)==2 or _bridge_path(catalog,path)]
    if len(paths)!=1:
        raise CoverageError('No unique bounded foreign-key path was found; specify the relationship/bridge table.')
    path=paths[0]
    identity,correlations=_edge(catalog,path[0],path[1],text)
    joins=[]
    for left,right in zip(path[1:],path[2:]):
        identity,equalities=_edge(catalog,left,right,text)
        joins.append(QueryJoin(left_table=left,right_table=right,equalities=equalities,constraint_id=identity))
    filters=[]
    used_values=set()
    for column,values in catalog.samples.get(target,{}).items():
        matched=[v for v in values if re.search(r'(?<!\w)'+re.escape(str(v).casefold())+r'(?!\w)',related_text)]
        if len(matched)>1:
            raise CoverageError('Multiple category values need an explicit supported Boolean condition.')
        if matched:
            value=matched[0]
            if str(value) in used_values:
                raise CoverageError('A category value matches multiple fields; specify its column.')
            filters.append(QueryFilter(field=ref(target,column),operator='eq',value=value))
            used_values.add(str(value))
    known=_roots(tokens(target))|tokens('a an any the record records ledger')
    known|=_roots(tokens(' '.join(used_values)))
    # Only consume role words from the selected constraint, never from all edges.
    known|=_roots(tokens(' '.join(a.column+' '+b.column for a,b in correlations)))
    for d in inner_dates:
        known|=_roots(tokens(d.field.column))
    residual=_roots(tokens(related_text))-known
    # Retain original inflected words only when their derived root is grounded.
    residual={w for w in residual if not _roots({w})&known}
    if residual:
        raise CoverageError('Related-record conditions are unresolved: '+', '.join(sorted(residual))+'. Specify the related field/value; no condition will be dropped.')
    counting=bool(re.match(r'^(count|how many|number of)\b',outer_text))
    distinct=bool(tokens(outer_text)&{'different','distinct','unique'})
    measure=None
    if counting:
        measure=QueryMeasure(function='count')
        if distinct:
            keys=[c for c in catalog.tables[outer].columns if c.primary_key]
            if len(keys)!=1:
                raise CoverageError('A distinct participation count requires one explicit outer entity key.')
            measure=QueryMeasure(function='count',field=ref(outer,keys[0].name),distinct=True)
    elif distinct:
        raise CoverageError('Specify the distinct key and whether to list or count participating entities.')
    exists=QueryExistence(entity=path[1],correlations=correlations,joins=joins,filters=filters,
                          negated=operator in ('without','with no','have no','has no'),dates=inner_dates,timestamps=comparisons)
    return CompositionalQuery(entity=outer,measure=measure,existence=[exists],dates=outer_dates,
        requested_operations=['relationships','not_exists' if exists.negated else 'exists']+(['measure'] if measure else [])+(['distinct'] if distinct else [])+(['related_filters'] if filters else [])+(['temporal_relationship'] if outer_dates or inner_dates or comparisons else []))
