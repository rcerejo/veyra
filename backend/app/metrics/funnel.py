from pydantic import BaseModel, Field

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


class FunnelRequest(BaseModel):
    steps: list[str] = Field(min_length=2, max_length=8)
    window_days: int = Field(default=7, ge=1, le=90)


def funnel(adapter: SQLiteAdapter, request: FunnelRequest) -> dict:
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    if not {'user_id', 'event_type', 'event_timestamp'} <= schema.get('events', set()):
        raise MetricSchemaError('Funnels require events.user_id, event_type, and event_timestamp')
    if any(not step.strip() for step in request.steps):
        raise ValueError('Funnel steps cannot be blank')
    _, rows, truncated = adapter.execute_readonly(
        "SELECT user_id, event_type, julianday(event_timestamp) AS timestamp FROM events WHERE user_id IS NOT NULL AND julianday(event_timestamp) IS NOT NULL ORDER BY timestamp", 100000, 8)
    if truncated:
        raise MetricSchemaError('Funnel input exceeds the current 100,000-event analysis limit')
    through = max((r['timestamp'] for r in rows), default=None)
    # Anchor each user on their first entry; only fully observed windows enter the denominator.
    anchors = {}
    for row in rows:
        if row['event_type'] == request.steps[0]:
            anchors.setdefault(row['user_id'], row['timestamp'])
    eligible = {user: anchor for user, anchor in anchors.items() if anchor + request.window_days <= through}
    progress = {user: (1, anchor) for user, anchor in eligible.items()}
    counts = [len(eligible)] + [0] * (len(request.steps) - 1)
    for row in rows:
        user = row['user_id']
        if user not in progress:
            continue
        index, previous = progress[user]
        if index < len(request.steps) and row['event_type'] == request.steps[index] and previous < row['timestamp'] <= eligible[user] + request.window_days:
            counts[index] += 1
            progress[user] = (index + 1, row['timestamp'])
    return {
        'window_days': request.window_days,
        'excluded_immature_users': len(anchors) - len(eligible),
        'definition': 'Unique users entering at their first occurrence of step 1. Subsequent steps must occur strictly later, within the window from entry. Only fully observed windows are eligible; completeness is inferred from the latest event.',
        'steps': [{'event': step, 'users': counts[i], 'conversion_rate': counts[i] / counts[0] if counts[0] else None, 'step_conversion_rate': counts[i] / counts[i-1] if i and counts[i-1] else (1.0 if not i and counts[0] else None), 'drop_off_users': counts[i-1] - counts[i] if i else 0} for i, step in enumerate(request.steps)],
    }
