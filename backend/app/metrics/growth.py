from datetime import date

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


def growth(adapter: SQLiteAdapter, start: date, end: date) -> dict:
    if start > end:
        raise MetricSchemaError('Start must precede end')
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    for table, fields in {'users': {'user_id','signup_date','acquisition_channel'}, 'orders': {'user_id','order_timestamp','revenue'}, 'events': {'user_id','event_timestamp'}}.items():
        if not fields <= schema.get(table,set()):
            raise MetricSchemaError(f'Growth analytics requires compatible {table} fields')
    def run(sql):
        _, rows, truncated = adapter.execute_readonly(sql, 5000, 8)
        if truncated:
            raise MetricSchemaError('Growth result exceeds analysis limit')
        return rows
    where = f"BETWEEN '{start}' AND '{end}'"
    summary = run(f"""SELECT
        (SELECT COUNT(*) FROM users WHERE DATE(signup_date) {where}) AS new_users,
        (SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN users u ON u.user_id=e.user_id WHERE DATE(e.event_timestamp) {where} AND DATE(u.signup_date)<'{start}') AS returning_users,
        (SELECT COALESCE(SUM(revenue),0) FROM orders WHERE DATE(order_timestamp) {where}) AS revenue,
        (SELECT COUNT(*) FROM users WHERE DATE(signup_date)<='{end}') AS registered_users""")[0]
    summary['revenue_per_registered_user'] = summary['revenue']/summary['registered_users'] if summary['registered_users'] else None
    channels = run(f"""SELECT u.acquisition_channel AS channel, COUNT(DISTINCT u.user_id) AS users,
        COALESCE(SUM(o.revenue),0) AS revenue FROM users u LEFT JOIN orders o ON o.user_id=u.user_id AND DATE(o.order_timestamp) {where}
        WHERE DATE(u.signup_date)<='{end}' GROUP BY u.acquisition_channel ORDER BY revenue DESC""")
    monthly = run(f"SELECT strftime('%Y-%m',order_timestamp) AS month, SUM(revenue) AS revenue FROM orders WHERE DATE(order_timestamp) {where} GROUP BY month ORDER BY month")
    for i, row in enumerate(monthly):
        previous = monthly[i-1]['revenue'] if i else None
        row['growth_rate'] = row['revenue']/previous-1 if previous else None
    return {'start':str(start),'end':str(end),'summary':summary,'channels':channels,'monthly_revenue':monthly,
            'definition':'Revenue from orders in the selected UTC dates; ARPU denominator is all registered users by period end. Returning users signed up before the period and had an event in the period. Monthly changes compare returned months; boundary months may be partial.'}
