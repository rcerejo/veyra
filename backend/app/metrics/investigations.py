from datetime import date

from pydantic import BaseModel, model_validator

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


class InvestigationRequest(BaseModel):
    baseline_start: date
    baseline_end: date
    current_start: date
    current_end: date
    conversion_event: str = 'purchase'

    @model_validator(mode='after')
    def validate_periods(self):
        if not self.baseline_start <= self.baseline_end < self.current_start <= self.current_end:
            raise ValueError('Use ordered, non-overlapping baseline and current periods')
        if (self.baseline_end-self.baseline_start) != (self.current_end-self.current_start):
            raise ValueError('Comparison periods must contain the same number of days')
        if not self.conversion_event.strip() or len(self.conversion_event) > 100:
            raise ValueError('Choose a conversion event of 1–100 characters')
        return self


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
