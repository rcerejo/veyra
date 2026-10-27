"""Explicit temporal roles and UTC calendar windows; no database-specific vocabulary."""
from datetime import date,datetime,timedelta,timezone
import re

from app.schemas.query import QueryDateConstraint,QueryTimestampComparison
from app.query_engine.planner import MONTHS


def timestamp_role(catalog,table,hint=''):
    from app.query_engine.compositional import tokens,ref,CoverageError
    from app.query_engine.relationships import _roots
    candidates=[c for c in catalog.tables[table].columns if any(x in c.name.lower() for x in ('date','timestamp','time')) or c.name.lower().endswith(('_on','_at'))]
    meaningful=_roots(tokens(hint))-{'their','its','the','date','timestamp','time','on','at'}
    if meaningful:
        scored=[(len(_roots(tokens(c.name))&meaningful),c) for c in candidates]
        scored.sort(key=lambda v:-v[0])
        if scored and scored[0][0]>0 and (len(scored)==1 or scored[0][0]>scored[1][0]):
            return ref(table,scored[0][1].name)
        raise CoverageError(f'The timestamp role "{hint}" in {table} is missing or ambiguous; specify its column.')
    if len(candidates)!=1:
        raise CoverageError(f'{table} needs an explicit timestamp role; found {len(candidates)} candidates.')
    return ref(table,candidates[0].name)


def split_window(fragment):
    month='|'.join(MONTHS)
    value=rf'(?:{month})\b|20\d{{2}}-\d{{2}}-\d{{2}}\b|(?:last|this)\b'
    match=re.search(rf'\s+(?:on or after|on or before|at or after|at or before|before|after|during|in|on|from|since)\s+(?=(?:the\s+)?(?:{value}))',fragment)
    if match:
        return fragment[:match.start()],fragment[match.start():].strip()
    match=re.search(r'\s+(?:last|this)\s+(?:\d+\s+(?:utc\s+)?(?:calendar\s+)?days|week|month)\b',fragment)
    return (fragment[:match.start()],fragment[match.start():].strip()) if match else (fragment,None)


def calendar_window(text,field,today=None,year=None):
    from app.query_engine.compositional import CoverageError
    current=today or datetime.now(timezone.utc).date()
    value=text.strip()
    relative=re.fullmatch(r'(?:(?:in|during)\s+)?(?:the\s+)?(last|this)\s+(?:(\d+)\s+(?:utc\s+)?(?:calendar\s+)?(days)|week|month)',value)
    if relative:
        which,number,days=relative.groups()
        if days:
            if which!='last' or not 1<=int(number)<=366:
                raise CoverageError('Use last 1–366 UTC calendar days; rolling-hour windows require an explicit different definition.')
            start=current-timedelta(days=int(number))
            end=current
        elif value.endswith('week'):
            monday=current-timedelta(days=current.weekday())
            start=monday-timedelta(days=7) if which=='last' else monday
            end=monday if which=='last' else monday+timedelta(days=7)
        else:
            first=current.replace(day=1)
            start=(first-timedelta(days=1)).replace(day=1) if which=='last' else first
            end=first if which=='last' else date(first.year+int(first.month==12),1 if first.month==12 else first.month+1,1)
        return QueryDateConstraint(field=field,start=start.isoformat(),end=end.isoformat(),normalized=True,
            resolution='UTC calendar window; last N days excludes today; weeks start Monday')
    years=re.findall(r'\b(20\d{2})\b',value)
    chosen=int(years[0]) if years else year or current.year
    if len(set(years))>1:
        raise CoverageError('Cross-year windows require explicit ISO boundaries in this increment.')
    month_pattern=r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2})(?!\d)\b'
    matches=list(re.finditer(month_pattern,value))
    iso=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',value)
    dates=[date.fromisoformat(v) for v in iso] if iso else [date(chosen,MONTHS[m[1]],int(m[2])) for m in matches]
    if len(dates)>2:
        raise CoverageError('Specify at most two temporal boundaries.')
    if not dates:
        month=re.fullmatch(r'(?:in|during)\s+('+'|'.join(MONTHS)+r')(?:\s+(20\d{2}))?',value)
        if not month:
            raise CoverageError('Specify an explicit month, ISO window, or supported UTC relative window.')
        start=date(int(month[2] or chosen),MONTHS[month[1]],1)
        end=date(start.year+int(start.month==12),1 if start.month==12 else start.month+1,1)
        return QueryDateConstraint(field=field,start=start.isoformat(),end=end.isoformat(),normalized=True,resolution='UTC calendar month')
    # Reject unconsumed conditions, rather than silently treating them as a bound.
    cleaned=re.sub(r'\b20\d{2}-\d{2}-\d{2}\b','',value)
    cleaned=re.sub(month_pattern,'',cleaned)
    cleaned=re.sub(r'\b20\d{2}\b|[, ]',' ',cleaned)
    cleaned=re.sub(r'\b(on|at|or|after|before|in|during|from|since|through|to|and|inclusive|exclusive)\b',' ',cleaned)
    if cleaned.strip():
        raise CoverageError('The temporal window includes unrepresented terms or conditions.')
    first=dates[0].isoformat()
    if len(dates)==2:
        if not re.search(r'\b(from|after|since)\b',value):
            raise CoverageError('Specify the lower and upper boundary operators.')
        start_inclusive=not value.startswith('after ')
        end=dates[1]
        if 'through' in value or ('inclusive' in value and 'before' not in value):
            end+=timedelta(days=1)
        elif not re.search(r'\bbefore\b|\bexclusive\b',value):
            raise CoverageError('Specify whether the window end is inclusive or exclusive.')
        result=QueryDateConstraint(field=field,start=first,end=end.isoformat(),start_inclusive=start_inclusive,normalized=True)
    elif value.startswith(('before ','on or before ','at or before ')):
        # Inclusive dates cover the full named calendar day.
        end=dates[0]+timedelta(days=1) if value.startswith(('on or before ','at or before ')) else dates[0]
        result=QueryDateConstraint(field=field,end=end.isoformat(),normalized=True)
    elif value.startswith(('after ','on or after ','at or after ','since ','from ')):
        result=QueryDateConstraint(field=field,start=first,start_inclusive=not value.startswith('after '),normalized=True)
    elif value.startswith(('in ','during ','on ')):
        result=QueryDateConstraint(field=field,start=first,end=(dates[0]+timedelta(days=1)).isoformat(),normalized=True)
    else:
        raise CoverageError('Specify the temporal boundary operator.')
    if result.start and result.end and result.start>=result.end:
        raise CoverageError('The temporal window must end after it starts.')
    result.resolution='ISO timestamps normalized to UTC; date literals represent UTC midnight'
    return result


def split_anchor_comparison(related):
    match=re.search(r'\s+(on or after|on or before|at or after|at or before|after|before)\s+(?:their|its|the)\s+(.+)$',related)
    return (related[:match.start()],match[1],match[2]) if match else (related,None,None)


def temporal_fields(plan):
    fields=[d.field for d in plan.dates]
    fields.extend(g.field for g in plan.groupings if g.grain)
    for related in plan.existence:
        fields.extend(d.field for d in related.dates)
        for compare in related.timestamps:
            fields.extend([compare.left,compare.right])
    return list({(f.table,f.column):f for f in fields}.values())


def validate_timestamp_column(adapter,field):
    """Time-bounded whole-column check, not a claim based on a clean sample."""
    from app.query_engine.compositional import field_sql,_quote,CoverageError
    from app.database.sqlite import QueryTimeoutError
    col=field_sql(field)
    sql=f'''SELECT 1 AS invalid FROM {_quote(field.table)} WHERE {col} IS NOT NULL AND (
      TYPEOF({col}) <> 'text' OR SUBSTR({col},1,10) NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
      OR (LENGTH({col})>10 AND SUBSTR({col},11,1) NOT IN ('T',' '))
      OR JULIANDAY({col}) IS NULL
      OR DATE(SUBSTR({col},1,10),'+0 days') <> SUBSTR({col},1,10)) LIMIT 1'''
    try:
        _,rows,_=adapter.execute_readonly(sql,1,2)
    except QueryTimeoutError as exc:
        raise CoverageError('Timestamp validation exceeded its deadline; configure validated temporal roles before analysis.') from exc
    if rows:
        raise CoverageError(f'{field.table}.{field.column} contains invalid or mixed timestamps. Use ISO dates/timestamps and explicitly normalize epoch or local-date fields.')
