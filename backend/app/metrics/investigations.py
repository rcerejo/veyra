from datetime import date, timedelta
import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


class InvestigationRequest(BaseModel):
    baseline_start: date
    baseline_end: date
    current_start: date
    current_end: date
    conversion_event: str = 'purchase'
    metric: Literal['conversion','revenue','active_users'] = 'conversion'

    @model_validator(mode='after')
    def validate_periods(self):
        if not self.baseline_start <= self.baseline_end < self.current_start <= self.current_end:
            raise ValueError('Use ordered, non-overlapping baseline and current periods')
        if (self.baseline_end-self.baseline_start) != (self.current_end-self.current_start):
            raise ValueError('Comparison periods must contain the same number of days')
        if not self.conversion_event.strip() or len(self.conversion_event) > 100:
            raise ValueError('Choose a conversion event of 1–100 characters')
        return self


class InvestigationQuestion(BaseModel):
    question: str = Field(min_length=3,max_length=1000)


def investigate_question(adapter: SQLiteAdapter, question: str) -> dict:
    text=question.casefold()
    metric='revenue' if any(word in text for word in ('revenue','sales')) else 'active_users' if 'active user' in text else 'conversion' if any(word in text for word in ('conversion','convert','purchase')) else None
    if metric is None:
        raise MetricSchemaError('Specify conversion, revenue, or active users. You can include four ISO dates: baseline start/end, then current start/end.')
    dates=re.findall(r'\b\d{4}-\d{2}-\d{2}\b',text)
    if dates and len(dates)!=4:
        raise MetricSchemaError('Provide four ISO dates: baseline start/end followed by current start/end, or omit dates for the latest complete seven observed dates')
    if dates:
        try:
            resolved=[date.fromisoformat(value) for value in dates]
        except ValueError as exc:
            raise MetricSchemaError('Investigation dates must be valid ISO calendar dates') from exc
        note='Periods resolved from the four dates in your question.'
    else:
        if any(word in text for word in ('month','year','today','yesterday','this week','last week')):
            raise MetricSchemaError('For calendar-relative questions, enter the four exact dates using the period controls. Without dates, this tool uses the latest seven observed dates versus the preceding seven.')
        table,column=('orders','order_timestamp') if metric=='revenue' else ('events','event_timestamp')
        schema={t.name:{c.name for c in t.columns} for t in adapter.discover_schema()}
        if column not in schema.get(table,set()):
            raise MetricSchemaError('Selected metric is unavailable in the active schema')
        last=adapter.execute_readonly(f'SELECT MAX(DATE({column})) AS day FROM {table}',1,8)[1][0]['day']
        if not last:
            raise MetricSchemaError('No timestamped data is available')
        end=date.fromisoformat(last)
        resolved=[end-timedelta(days=13),end-timedelta(days=7),end-timedelta(days=6),end]
        note='Periods resolved from the latest observed date, not the current calendar date; completeness is assumed.'
    try:
        request=InvestigationRequest(baseline_start=resolved[0],baseline_end=resolved[1],current_start=resolved[2],current_end=resolved[3],metric=metric)
    except ValueError as exc:
        raise MetricSchemaError('Periods must be valid, equal-length and non-overlapping') from exc
    result=investigate(adapter,request)
    result['resolution_note']=note
    result['explanation']=note+' '+result['explanation']
    return result


def decompose(before: dict, after: dict) -> list[dict]:
    n0, n1 = sum(v[0] for v in before.values()), sum(v[0] for v in after.values())
    result = []
    for segment in before.keys() | after.keys():
        a, x = before.get(segment, (0, 0))
        b, y = after.get(segment, (0, 0))
        w0, w1 = a/n0, b/n1
        # For entering/exiting segments, assign the observed rate to both periods.
        # This attributes their change to composition without inventing a rate shift.
        r0 = x/a if a else y/b
        r1 = y/b if b else x/a
        within = (w0+w1)/2*(r1-r0)
        composition = (r0+r1)/2*(w1-w0)
        result.append({'segment': segment, 'baseline_users': a, 'current_users': b,
                       'baseline_rate': x/a if a else None, 'current_rate': y/b if b else None,
                       'within_contribution': within, 'composition_contribution': composition,
                       'total_contribution': within+composition, 'small_sample': min(a,b) < 30})
    return sorted(result, key=lambda row: (-abs(row['total_contribution']), str(row['segment'])))


def investigate(adapter: SQLiteAdapter, request: InvestigationRequest) -> dict:
    if request.metric != 'conversion':
        return investigate_totals(adapter,request)
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    for table, fields in {'users': {'user_id'}, 'events': {'user_id','event_timestamp','event_type'}}.items():
        if not fields <= schema.get(table, set()):
            raise MetricSchemaError(f'Investigations require compatible {table} fields')
    def run(sql):
        _, rows, truncated = adapter.execute_readonly(sql, 100000, 8)
        if truncated:
            raise MetricSchemaError('Investigation exceeds the current analysis row limit')
        return rows
    event = "'" + request.conversion_event.replace("'", "''") + "'"
    if not run(f'SELECT 1 FROM events WHERE event_type={event} LIMIT 1'):
        raise MetricSchemaError('Selected conversion event is absent from this database')
    bounds = run('SELECT MIN(DATE(event_timestamp)) AS first, MAX(DATE(event_timestamp)) AS last FROM events')[0]
    if request.baseline_start.isoformat() < bounds['first'] or request.current_end.isoformat() > bounds['last']:
        raise MetricSchemaError('Comparison periods extend beyond available event dates')
    duplicates = run('SELECT user_id FROM users GROUP BY user_id HAVING COUNT(*)>1 LIMIT 1')
    if duplicates:
        raise MetricSchemaError('User identifiers must be unique for segment attribution')
    dimensions = [d for d in ('device_type','country','acquisition_channel','signup_date','subscription_tier') if d in schema['users']]
    aggregates = []
    daily = []
    for start, end in ((request.baseline_start,request.baseline_end),(request.current_start,request.current_end)):
        fields = ', '.join('u."'+d+'"' for d in dimensions)
        rows = run(f"""SELECT e.user_id, MAX(CASE WHEN e.event_type={event} THEN 1 ELSE 0 END) AS converted
            {','+fields if fields else ''} FROM events e LEFT JOIN users u ON u.user_id=e.user_id
            WHERE DATE(e.event_timestamp) BETWEEN '{start.isoformat()}' AND '{end.isoformat()}' AND e.user_id IS NOT NULL
            GROUP BY e.user_id""")
        if not rows:
            raise MetricSchemaError('Both periods need active users; no conversion rate can be calculated for an empty period')
        aggregates.append(rows)
        daily.append(run(f"SELECT DATE(event_timestamp) AS day, COUNT(DISTINCT user_id) AS users, COUNT(DISTINCT CASE WHEN event_type={event} THEN user_id END) AS converted FROM events WHERE DATE(event_timestamp) BETWEEN '{start.isoformat()}' AND '{end.isoformat()}' GROUP BY day ORDER BY day"))
    rates = [sum(r['converted'] for r in rows)/len(rows) for rows in aggregates]
    breakdowns = []
    for dimension in dimensions:
        buckets = []
        for rows in aggregates:
            grouped = {}
            for row in rows:
                value = row[dimension]
                segment = str(value) if value is not None else '(unknown)'
                if dimension == 'signup_date' and value:
                    segment = str(value)[:7]
                n,x = grouped.get(segment,(0,0))
                grouped[segment] = (n+1,x+row['converted'])
            buckets.append(grouped)
        breakdowns.append({'dimension': dimension, 'segments': decompose(*buckets)})
    delta = rates[1]-rates[0]
    explanation = f"Conversion changed from {rates[0]:.2%} to {rates[1]:.2%} ({delta*100:+.2f} percentage points)."
    if breakdowns:
        strongest = max(((d['dimension'],s) for d in breakdowns for s in d['segments']), key=lambda pair: abs(pair[1]['total_contribution']))
        explanation += f" The largest absolute segment contribution was {strongest[0]}={strongest[1]['segment']} ({strongest[1]['total_contribution']*100:+.2f} pp)."
    patterns = []
    previous_days = {r['day']: r for r in daily[0]}
    offset = request.current_start-request.baseline_start
    for row in daily[1]:
        previous = previous_days.get((date.fromisoformat(row['day'])-offset).isoformat())
        if previous and row['users'] and previous['users']:
            change = row['converted']/row['users']-previous['converted']/previous['users']
            patterns.append({'day': row['day'], 'baseline_day': previous['day'], 'rate_change': change, 'small_sample': min(row['users'],previous['users']) < 30})
    patterns.sort(key=lambda row: -abs(row['rate_change']))
    if patterns:
        largest = patterns[0]
        explanation += f" The largest aligned daily change was {largest['day']} versus {largest['baseline_day']} ({largest['rate_change']*100:+.2f} pp); this is an exploratory magnitude ranking."
    return {'metric': 'active_user_conversion', 'conversion_event': request.conversion_event, 'largest_daily_changes': patterns[:5],
            'periods': request.model_dump(mode='json'), 'baseline_users': len(aggregates[0]), 'current_users': len(aggregates[1]),
            'baseline_rate': rates[0], 'current_rate': rates[1], 'absolute_change': delta,
            'relative_change': delta/rates[0] if rates[0] else None, 'breakdowns': breakdowns, 'daily': daily,
            'explanation': explanation, 'warnings': ['Descriptive contributors are not causal explanations.', 'Each dimension independently decomposes the same overall change. Never add contributions across dimensions.', 'Small segments are flagged below 30 users in either period; rankings are exploratory, not significance tests.', 'Conversion means any selected event among active users within each period, not an ordered funnel.', 'Event completeness and stable user attributes are assumed. Historical attributes are not reconstructed.', 'Product-category decomposition is unavailable because this schema does not link events to a product category.']}


def investigate_totals(adapter: SQLiteAdapter, request: InvestigationRequest) -> dict:
    schema={t.name:{c.name for c in t.columns} for t in adapter.discover_schema()}
    table,column,value=('orders','order_timestamp','SUM(f.revenue)') if request.metric=='revenue' else ('events','event_timestamp','1.0')
    required={'user_id',column} | ({'revenue'} if table=='orders' else set())
    if not required<=schema.get(table,set()) or 'user_id' not in schema.get('users',set()):
        raise MetricSchemaError('Selected investigation requires compatible user and activity/revenue tables')
    def run(sql):
        _,rows,truncated=adapter.execute_readonly(sql,100000,8)
        if truncated:
            raise MetricSchemaError('Investigation exceeds analysis limit')
        return rows
    if run('SELECT user_id FROM users GROUP BY user_id HAVING COUNT(*)>1 LIMIT 1'):
        raise MetricSchemaError('User identifiers must be unique')
    bounds=run(f'SELECT MIN(DATE({column})) AS first,MAX(DATE({column})) AS last FROM {table}')[0]
    if not bounds['first'] or str(request.baseline_start)<bounds['first'] or str(request.current_end)>bounds['last']:
        raise MetricSchemaError('Comparison extends beyond observed metric dates')
    dimensions=[d for d in ('country','device_type','acquisition_channel','signup_date','subscription_tier') if d in schema['users']]
    periods=[]
    for start,end in ((request.baseline_start,request.baseline_end),(request.current_start,request.current_end)):
        fields=','.join('u.'+d for d in dimensions)
        periods.append(run(f"SELECT f.user_id,{value} AS value {','+fields if fields else ''} FROM {table} f LEFT JOIN users u ON u.user_id=f.user_id WHERE DATE(f.{column}) BETWEEN '{start}' AND '{end}' AND f.user_id IS NOT NULL GROUP BY f.user_id"))
    totals=[sum(row['value'] for row in rows) for rows in periods]
    breakdowns=[]
    for dimension in dimensions:
        groups=[]
        for rows in periods:
            grouped={}
            for row in rows:
                segment=str(row[dimension]) if row[dimension] is not None else '(unknown)'
                if dimension=='signup_date' and row[dimension]:
                    segment=segment[:7]
                n,total=grouped.get(segment,(0,0))
                grouped[segment]=(n+1,total+row['value'])
            groups.append(grouped)
        segments=[]
        for segment in groups[0].keys() | groups[1].keys():
            n0,x=groups[0].get(segment,(0,0));n1,y=groups[1].get(segment,(0,0))
            r0=x/n0 if n0 else y/n1;r1=y/n1 if n1 else x/n0
            within=(n0+n1)/2*(r1-r0);composition=(r0+r1)/2*(n1-n0)
            segments.append({'segment':segment,'baseline_users':n0,'current_users':n1,'within_contribution':within,'composition_contribution':composition,'total_contribution':y-x,'small_sample':min(n0,n1)<30})
        breakdowns.append({'dimension':dimension,'segments':sorted(segments,key=lambda row:(-abs(row['total_contribution']),row['segment']))})
    delta=totals[1]-totals[0]
    return {'metric':request.metric,'periods':request.model_dump(mode='json'),'baseline_rate':totals[0],'current_rate':totals[1],'absolute_change':delta,'relative_change':delta/totals[0] if totals[0] else None,'baseline_users':len(periods[0]),'current_users':len(periods[1]),'breakdowns':breakdowns,'daily':[],
            'explanation':f"{request.metric.replace('_',' ').capitalize()} changed from {totals[0]:,.2f} to {totals[1]:,.2f} ({delta:+,.2f}). Contributions split changes in value per observed user from changes in observed user counts.",
            'warnings':['Descriptive contributions do not establish causes.','Each dimension independently reconciles to the total; do not add dimensions together.','Revenue assumes one consistent currency; refunds and negative amounts are included.','Small segments have fewer than 30 observed users in either period.','Current user attributes are used; historical attributes and ingestion completeness are not verified.']}
