from datetime import date, timedelta

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


def retention(adapter: SQLiteAdapter) -> dict:
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    for table, fields in {"users": {"user_id", "signup_date"}, "events": {"user_id", "event_timestamp"}}.items():
        missing = fields - schema.get(table, set())
        if missing:
            raise MetricSchemaError(f"Retention requires {table}: {', '.join(sorted(missing))}")

    def run(sql):
        _, rows, truncated = adapter.execute_readonly(sql, 100000, 8)
        if truncated:
            raise MetricSchemaError("Retention input exceeds the current 100,000-row analysis limit")
        return rows

    through = run("SELECT MAX(DATE(event_timestamp)) AS day FROM events")[0]["day"]
    if not through:
        raise MetricSchemaError("Retention requires timestamped events")
    cutoff = date.fromisoformat(through)
    rows = run("SELECT DATE(signup_date) AS cohort, COUNT(DISTINCT user_id) AS users FROM users WHERE DATE(signup_date) IS NOT NULL GROUP BY cohort ORDER BY cohort")
    counts = run("SELECT DATE(u.signup_date) AS cohort, CAST(julianday(DATE(e.event_timestamp)) - julianday(DATE(u.signup_date)) AS INTEGER) AS offset, COUNT(DISTINCT u.user_id) AS retained FROM users u JOIN events e ON e.user_id = u.user_id WHERE DATE(u.signup_date) IS NOT NULL GROUP BY cohort, offset")
    lookup = {(r['cohort'], r['offset']): r['retained'] for r in counts}
    cohorts = []
    for row in rows:
        cells = []
        for day in (1, 7, 30):
            mature = date.fromisoformat(row['cohort']) + timedelta(days=day) <= cutoff
            retained = lookup.get((row['cohort'], day), 0) if mature else None
            cells.append({"day": day, "eligible_users": row['users'] if mature else 0, "retained_users": retained, "rate": retained / row['users'] if mature else None})
        cohorts.append({"cohort": row['cohort'], "users": row['users'], "cells": cells})
    rolling=[]
    for day in (1,7,30):
        eligible=[row for row in rows if date.fromisoformat(row['cohort'])+timedelta(days=day)<=cutoff]
        denominator=sum(row['users'] for row in eligible)
        result=run(f"SELECT COUNT(DISTINCT u.user_id) AS retained FROM users u JOIN events e ON e.user_id=u.user_id WHERE DATE(u.signup_date,'+{day} days')<='{through}' AND DATE(e.event_timestamp)>=DATE(u.signup_date,'+{day} days') AND DATE(e.event_timestamp)<='{through}'")
        numerator=result[0]['retained']
        rolling.append({'day':day,'eligible_users':denominator,'retained_users':numerator,'rate':numerator/denominator if denominator else None})
    weekly=run("""SELECT DATE(u.signup_date,'-' || ((CAST(strftime('%w',u.signup_date) AS INTEGER)+6)%7) || ' days') AS cohort,
        CAST((julianday(DATE(e.event_timestamp))-julianday(DATE(u.signup_date)))/7 AS INTEGER) AS week,
        COUNT(DISTINCT u.user_id) AS users FROM users u JOIN events e ON e.user_id=u.user_id
        WHERE DATE(e.event_timestamp)>=DATE(u.signup_date) GROUP BY cohort, week ORDER BY cohort, week""")
    weekly_rates = []
    for week in range(9):
        first,last = week*7,week*7+6
        cells=run(f"""SELECT DATE(u.signup_date,'-' || ((CAST(strftime('%w',u.signup_date) AS INTEGER)+6)%7) || ' days') AS cohort,
            COUNT(DISTINCT u.user_id) AS eligible_users,
            COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp) BETWEEN DATE(u.signup_date,'+{first} days') AND DATE(u.signup_date,'+{last} days')) THEN u.user_id END) AS retained_users
            FROM users u WHERE DATE(u.signup_date,'+{last} days')<='{through}' GROUP BY cohort""")
        for cell in cells:
            cell.update(week=week,rate=cell['retained_users']/cell['eligible_users'])
        weekly_rates.extend(cells)
    activation=run(f"""SELECT COUNT(*) AS eligible_users,
        SUM(CASE WHEN EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.user_id AND e.event_type='purchase' AND julianday(e.event_timestamp)>=julianday(u.signup_date) AND julianday(e.event_timestamp)<julianday(u.signup_date)+7) THEN 1 ELSE 0 END) AS activated_users
        FROM users u WHERE DATE(u.signup_date,'+7 days')<='{through}'""")[0]
    activation['rate']=(activation['activated_users'] or 0)/activation['eligible_users'] if activation['eligible_users'] else None
    churn_cutoff=cutoff-timedelta(days=30)
    churn_start=churn_cutoff-timedelta(days=29)
    churn=run(f"""SELECT COUNT(DISTINCT e.user_id) AS eligible_users,
        COUNT(DISTINCT CASE WHEN NOT EXISTS(SELECT 1 FROM events later WHERE later.user_id=e.user_id AND DATE(later.event_timestamp)>'{churn_cutoff}' AND DATE(later.event_timestamp)<='{through}') THEN e.user_id END) AS churned_users
        FROM events e WHERE DATE(e.event_timestamp) BETWEEN '{churn_start}' AND '{churn_cutoff}'""")[0]
    churn.update(rate=churn['churned_users']/churn['eligible_users'] if churn['eligible_users'] else None,baseline_start=str(churn_start),baseline_end=str(churn_cutoff),followup_end=through)
    return {"data_through": through, "timezone": "UTC", "definition": "Exact-day retention: users with any event on UTC day N after signup divided by signup cohort users. Immature cohorts are excluded. Observation completeness is inferred from the latest event date.", "cohorts": cohorts, 'rolling_retention':rolling,'weekly_activity_counts':weekly,
            'weekly_retention':weekly_rates,'activation':activation,'churn':churn,
            'activation_definition':'Purchase within seven elapsed days of signup; signup timestamps stored as dates are interpreted as UTC midnight. Only users with seven days of follow-up are eligible.',
            'churn_definition':'Users active in the baseline thirty days with no event in the following thirty days, divided by baseline active users. This is inactivity churn, not subscription cancellation.',
            'rolling_definition':'Return on day N or any later observed day among users whose signup + N is observed. Follow-up lengths vary; rates are not comparable across different observation cutoffs.', 'weekly_definition':'Distinct users active in seven-day age bins, grouped by Monday signup cohort. Counts only; incomplete age bins are not interpreted as retention rates.'}
