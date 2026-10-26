from __future__ import annotations

import re
from datetime import date

from app.schemas.query import QueryPlan


MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

EVENT_TYPE_PHRASES = {
    "app_open": ("app_open", "open the app", "opened the app", "opening the app", "launch the app", "launched the app", "app open", "app launch"),
    "view_product": ("view_product", "view a product", "viewed a product", "product view"),
    "add_to_cart": ("add_to_cart", "add to cart", "added to cart"),
    "checkout_started": ("checkout_started", "start checkout", "started checkout", "begin checkout"),
    "purchase": ("purchase", "purchased", "completed an order", "bought"),
}


def _event_type(text: str) -> str | None:
    for event_type, phrases in EVENT_TYPE_PHRASES.items():
        if any(phrase in text for phrase in phrases):
            return event_type
    return None


def _month_window(text: str) -> tuple[str, str, str] | None:
    match = re.search(
        rf"\b({'|'.join(MONTHS)})\b(?:\s+(20\d{{2}}))?",
        text,
    )
    if not match:
        return None
    month_name = match.group(1)
    year = int(match.group(2) or 2026)
    month = MONTHS[month_name]
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start.isoformat(), end.isoformat(), f"{month_name}_{year}"


def plan_question(question: str) -> QueryPlan:
    text = question.casefold()
    table_terms = {
        "users": ("user", "signup", "acquisition", "country", "device"),
        "events": ("event", "activity", "active"),
        "sessions": ("session", "duration"),
        "orders": ("order", "revenue", "sales"),
        "experiments": ("experiment", "variant", "treatment"),
    }
    relevant = [table for table, terms in table_terms.items() if any(term in text for term in terms)]
    if _event_type(text) and "events" not in relevant:
        relevant.append("events")
    intent = "trend" if any(word in text for word in ("daily", "weekly", "monthly", "over time", "trend")) else "aggregation"
    if any(word in text for word in ("show", "list", "which", "all instances", "give me")) and not any(word in text for word in ("count", "how many", "average", "total", "revenue")):
        intent = "lookup"
    metric = None
    for candidate in ("revenue", "users", "sessions", "events", "orders"):
        if candidate in text or candidate.rstrip("s") in text:
            metric = candidate
            break
    dimensions = [dimension for dimension in ("acquisition_channel", "country", "device_type", "event_type") if dimension.replace("_", " ") in text]
    month_window = _month_window(text)
    time_range = month_window[2] if month_window else ("last_30_days" if re.search(r"last (30|thirty) days", text) else None)
    event_type = _event_type(text)
    filters = {"event_type": event_type} if event_type else {}
    return QueryPlan(intent=intent, metric=metric, dimensions=dimensions, filters=filters, time_range=time_range, relevant_tables=relevant)


def deterministic_sql(question: str) -> str | None:
    text = question.casefold().strip(" ?.!")
    retention_day = re.search(r'\bday\s*(1|7|30)\s+(?:signup\s+)?retention\b',text)
    if retention_day:
        day=int(retention_day.group(1))
        return f"""SELECT SUM(CASE WHEN EXISTS (SELECT 1 FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp)=DATE(u.signup_date,'+{day} days')) THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) AS retention_rate FROM users u WHERE DATE(u.signup_date,'+{day} days') <= (SELECT MAX(DATE(event_timestamp)) FROM events)"""
    if 'active user' in text and 'purchase conversion' in text:
        return "SELECT COUNT(DISTINCT CASE WHEN event_type='purchase' THEN user_id END)*1.0/NULLIF(COUNT(DISTINCT user_id),0) AS conversion_rate FROM events"
    if 'signup cohort' in text and 'revenue' not in text and 'month' in text:
        return "SELECT strftime('%Y-%m',signup_date) AS cohort, COUNT(*) AS users FROM users GROUP BY cohort ORDER BY cohort"
    if 'experiment assignment' in text and 'variant' in text:
        return "SELECT experiment_id,variant,COUNT(*) AS users FROM experiment_assignments GROUP BY experiment_id,variant"
    if 'revenue' in text and ' by ' in text:
        dimension = next((column for phrase,column in [('country','country'),('device','device_type'),('channel','acquisition_channel'),('signup cohort',"strftime('%Y-%m',u.signup_date)")] if phrase in text),None)
        if dimension:
            expression=dimension if '(' in dimension else 'u.'+dimension
            aggregate='AVG' if 'average' in text else 'SUM'
            return f'SELECT {expression} AS segment, {aggregate}(o.revenue) AS revenue FROM orders o JOIN users u ON u.user_id=o.user_id GROUP BY segment'
    month_window = _month_window(text)
    if month_window:
        start, end, _ = month_window
        event_type = _event_type(text)
        if event_type:
            return (
                "SELECT event_id, user_id, event_type, event_timestamp, session_id FROM events "
                f"WHERE event_type = '{event_type}' "
                f"AND event_timestamp >= '{start}' AND event_timestamp < '{end}' "
                "ORDER BY event_timestamp LIMIT 5000"
            )
        table_dates = {
            "events": ("event_timestamp", "event"),
            "sessions": ("session_start", "session"),
            "orders": ("order_timestamp", "order"),
            "users": ("signup_date", "user"),
            "experiment_assignments": ("assigned_at", "assignment"),
        }
        for table, (column, term) in table_dates.items():
            if term in text:
                return (
                    f"SELECT * FROM {table} "
                    f"WHERE {column} >= '{start}' AND {column} < '{end}' "
                    f"ORDER BY {column} LIMIT 5000"
                )
        if "data" in text or "activity" in text or "everything" in text:
            return f"""
                WITH days AS (
                    SELECT DATE(signup_date) AS day FROM users WHERE signup_date >= '{start}' AND signup_date < '{end}'
                    UNION SELECT DATE(session_start) FROM sessions WHERE session_start >= '{start}' AND session_start < '{end}'
                    UNION SELECT DATE(event_timestamp) FROM events WHERE event_timestamp >= '{start}' AND event_timestamp < '{end}'
                    UNION SELECT DATE(order_timestamp) FROM orders WHERE order_timestamp >= '{start}' AND order_timestamp < '{end}'
                ),
                signups AS (SELECT DATE(signup_date) day, COUNT(*) signups FROM users WHERE signup_date >= '{start}' AND signup_date < '{end}' GROUP BY day),
                session_counts AS (SELECT DATE(session_start) day, COUNT(*) sessions FROM sessions WHERE session_start >= '{start}' AND session_start < '{end}' GROUP BY day),
                event_counts AS (SELECT DATE(event_timestamp) day, COUNT(*) events FROM events WHERE event_timestamp >= '{start}' AND event_timestamp < '{end}' GROUP BY day),
                order_counts AS (SELECT DATE(order_timestamp) day, COUNT(*) orders, ROUND(SUM(revenue), 2) revenue FROM orders WHERE order_timestamp >= '{start}' AND order_timestamp < '{end}' GROUP BY day)
                SELECT days.day,
                       COALESCE(signups.signups, 0) AS signups,
                       COALESCE(session_counts.sessions, 0) AS sessions,
                       COALESCE(event_counts.events, 0) AS events,
                       COALESCE(order_counts.orders, 0) AS orders,
                       COALESCE(order_counts.revenue, 0) AS revenue
                FROM days
                LEFT JOIN signups USING (day)
                LEFT JOIN session_counts USING (day)
                LEFT JOIN event_counts USING (day)
                LEFT JOIN order_counts USING (day)
                ORDER BY days.day
            """
    if ("how many" in text or re.search(r'\bcount\b',text)) and "user" in text:
        return "SELECT COUNT(*) AS user_count FROM users"
    if ("how many" in text or re.search(r'\bcount\b',text)) and "order" in text:
        return "SELECT COUNT(*) AS order_count FROM orders"
    if "revenue" in text and any(word in text for word in ("total", "how much", "overall")):
        return "SELECT ROUND(SUM(revenue), 2) AS total_revenue FROM orders"
    if "users" in text and ("channel" in text or "acquisition" in text):
        return "SELECT acquisition_channel, COUNT(*) AS users FROM users GROUP BY acquisition_channel ORDER BY users DESC"
    if "users" in text and "country" in text:
        return "SELECT country, COUNT(*) AS users FROM users GROUP BY country ORDER BY users DESC"
    if "events" in text and ("type" in text or "breakdown" in text):
        return "SELECT event_type, COUNT(*) AS events FROM events GROUP BY event_type ORDER BY events DESC"
    if "daily" in text and ("active user" in text or "dau" in text):
        return "SELECT DATE(event_timestamp) AS day, COUNT(DISTINCT user_id) AS active_users FROM events GROUP BY day ORDER BY day"
    if "recent" in text and "order" in text:
        return "SELECT order_id, user_id, order_timestamp, revenue FROM orders ORDER BY order_timestamp DESC LIMIT 50"
    return None

