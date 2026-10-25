from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.database.schema import SchemaCatalog
from app.query_engine.planner import _month_window
from app.schemas.query import QueryPlan


@dataclass(frozen=True)
class SemanticResult:
    plan: QueryPlan
    sql: str | None = None
    clarification: str | None = None
    suggestions: tuple[str, ...] = ()


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold().replace("_", " "))
    return {_singular(word) for word in words if len(word) > 1}


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ses") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _quote(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _qualified(table: str, column: str) -> str:
    return f"{_quote(table)}.{_quote(column)}"


def _column_is_numeric(data_type: str) -> bool:
    lowered = data_type.casefold()
    return any(token in lowered for token in ("int", "real", "numeric", "decimal", "double", "float"))


def _date_column(catalog: SchemaCatalog, table_name: str) -> str | None:
    table = catalog.tables[table_name]
    candidates = []
    for column in table.columns:
        lowered = column.name.casefold()
        score = 0
        if "timestamp" in lowered:
            score += 5
        if lowered.endswith("_at"):
            score += 4
        if "date" in lowered:
            score += 3
        if "time" in lowered:
            score += 2
        if score:
            candidates.append((score, column.name))
    return max(candidates, default=(0, None))[1]


def _time_window(text: str, today: date | None = None) -> tuple[str, str, str] | None:
    explicit = _month_window(text)
    if explicit:
        return explicit
    current = today or date.today()
    if "last month" in text:
        this_month = current.replace(day=1)
        start = (this_month - timedelta(days=1)).replace(day=1)
        return start.isoformat(), this_month.isoformat(), "last_month"
    if "this month" in text:
        start = current.replace(day=1)
        end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
        return start.isoformat(), end.isoformat(), "this_month"
    if "this week" in text:
        start = current - timedelta(days=current.weekday())
        return start.isoformat(), (start + timedelta(days=7)).isoformat(), "this_week"
    if "last week" in text:
        end = current - timedelta(days=current.weekday())
        return (end - timedelta(days=7)).isoformat(), end.isoformat(), "last_week"
    match = re.search(r"\blast\s+(\d{1,3})\s+days?\b", text)
    if match:
        days = min(int(match.group(1)), 366)
        return (current - timedelta(days=days)).isoformat(), (current + timedelta(days=1)).isoformat(), f"last_{days}_days"
    return None


def _table_scores(question: str, catalog: SchemaCatalog) -> tuple[dict[str, int], list[tuple[str, str, object]]]:
    question_tokens = _tokens(question)
    subject_tokens = _tokens(re.split(r"\bby\b", question, maxsplit=1)[0])
    normalized_question = " ".join(re.findall(r"[a-z0-9]+", question.casefold()))
    scores = {name: 0 for name in catalog.tables}
    filters: list[tuple[str, str, object]] = []
    for table in catalog.tables.values():
        table_tokens = _tokens(table.name)
        table_phrase = " ".join(re.findall(r"[a-z0-9]+", table.name.casefold().replace("_", " ")))
        if table_phrase and table_phrase in normalized_question:
            scores[table.name] += 30
        elif table_tokens and table_tokens <= subject_tokens:
            scores[table.name] += 20
        elif table_tokens and table_tokens <= question_tokens:
            scores[table.name] += 10
        else:
            scores[table.name] += 2 * len(table_tokens & question_tokens)
        for column in table.columns:
            column_tokens = _tokens(column.name)
            if column.primary_key or column.name.casefold() in {"id", f"{table.name.casefold()}_id"}:
                continue
            if column_tokens and column_tokens <= question_tokens:
                scores[table.name] += 2
        for column, values in catalog.samples.get(table.name, {}).items():
            for value in values:
                value_tokens = _tokens(str(value))
                value_phrase = " ".join(re.findall(r"[a-z0-9]+", str(value).casefold().replace("_", " ")))
                if value_tokens and (value_tokens <= question_tokens or value_phrase in normalized_question):
                    scores[table.name] += 12
                    filters.append((table.name, column, value))
                    break
    return scores, filters


def _find_dimension(question: str, catalog: SchemaCatalog) -> tuple[str, str] | None:
    match = re.search(r"\bby\s+(.+?)(?:\s+(?:in|from|during|where|for)\b|$)", question.casefold())
    if not match:
        return None
    dimension_tokens = _tokens(match.group(1))
    candidates: list[tuple[int, str, str]] = []
    for table in catalog.tables.values():
        for column in table.columns:
            if column.primary_key or column.name.casefold().endswith("_id"):
                continue
            column_tokens = _tokens(column.name)
            overlap = len(column_tokens & dimension_tokens)
            if column_tokens and column_tokens <= dimension_tokens:
                overlap += 5
            if overlap:
                candidates.append((overlap, table.name, column.name))
    if not candidates:
        return None
    _, table_name, column_name = max(candidates)
    return table_name, column_name


def _find_metric_column(question: str, catalog: SchemaCatalog, table_name: str) -> str | None:
    question_tokens = _tokens(question)
    candidates: list[tuple[int, str]] = []
    for column in catalog.tables[table_name].columns:
        if not _column_is_numeric(column.data_type) or column.primary_key or column.name.casefold().endswith("_id"):
            continue
        overlap = len(_tokens(column.name) & question_tokens)
        if overlap:
            candidates.append((overlap, column.name))
    return max(candidates, default=(0, None))[1]


def _join_sql(catalog: SchemaCatalog, path: list[str]) -> str:
    joins: list[str] = []
    for left, right in zip(path, path[1:]):
        left_table = catalog.tables[left]
        right_table = catalog.tables[right]
        forward = next((key for key in left_table.foreign_keys if key.target_table == right), None)
        reverse = next((key for key in right_table.foreign_keys if key.target_table == left), None)
        if forward:
            joins.append(f"JOIN {_quote(right)} ON {_qualified(left, forward.column)} = {_qualified(right, forward.target_column)}")
        elif reverse:
            joins.append(f"JOIN {_quote(right)} ON {_qualified(right, reverse.column)} = {_qualified(left, reverse.target_column)}")
        else:
            raise ValueError(f"No explicit relationship between {left} and {right}")
    return " ".join(joins)


def plan_semantic_query(question: str, catalog: SchemaCatalog) -> SemanticResult:
    text = question.casefold().strip()
    scores, detected_filters = _table_scores(text, catalog)
    dimension = _find_dimension(text, catalog)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    positive = [item for item in ranked if item[1] > 0]

    if detected_filters:
        primary_table = detected_filters[0][0]
    elif positive:
        primary_table = positive[0][0]
    elif dimension:
        primary_table = dimension[0]
    else:
        plan = QueryPlan(intent="unknown", relevant_tables=[])
        table_names = list(catalog.tables)[:3]
        return SemanticResult(
            plan=plan,
            clarification="I could not identify which table the question refers to. Which dataset should I use?",
            suggestions=tuple(f"Show records from {name}" for name in table_names),
        )

    if not detected_filters and len(positive) > 1 and positive[0][1] == positive[1][1]:
        choices = [name for name, score in positive if score == positive[0][1]][:3]
        plan = QueryPlan(intent="unknown", relevant_tables=choices)
        return SemanticResult(
            plan=plan,
            clarification=f"I found multiple equally likely tables: {', '.join(choices)}. Which one should I use?",
            suggestions=tuple(f"{question.rstrip(' ?.')} using the {name} table" for name in choices),
        )

    aggregate: Literal["count", "sum", "average"] | None = None
    if re.search(r"\b(how many|count|number of)\b", text):
        aggregate = "count"
    elif re.search(r"\b(average|avg|mean)\b", text):
        aggregate = "average"
    elif re.search(r"\b(total|sum)\b", text):
        aggregate = "sum"

    relevant_tables = [primary_table]
    joins = ""
    dimension_expression = None
    if dimension:
        dimension_table, dimension_column = dimension
        dimension_expression = _qualified(dimension_table, dimension_column)
        if dimension_table != primary_table:
            path = catalog.join_path(primary_table, dimension_table)
            if not path:
                plan = QueryPlan(intent="unknown", dimensions=[dimension_column], relevant_tables=[primary_table, dimension_table])
                return SemanticResult(
                    plan=plan,
                    clarification=f"I found {dimension_column} in {dimension_table}, but there is no explicit relationship to {primary_table}.",
                    suggestions=(f"Analyze {primary_table} without {dimension_column}", f"Use {dimension_table}"),
                )
            joins = _join_sql(catalog, path)
            relevant_tables = path

    conditions: list[str] = []
    filters: dict[str, str | int | float | bool] = {}
    for table_name, column_name, value in detected_filters:
        if table_name not in relevant_tables and table_name != primary_table:
            continue
        literal = str(value).replace("'", "''")
        conditions.append(f"{_qualified(table_name, column_name)} = '{literal}'")
        filters[f"{table_name}.{column_name}"] = value

    month = _time_window(text)
    time_range = None
    if month:
        start, end, time_range = month
        date_column = _date_column(catalog, primary_table)
        if not date_column:
            plan = QueryPlan(intent="unknown", filters=filters, time_range=time_range, relevant_tables=relevant_tables)
            return SemanticResult(
                plan=plan,
                clarification=f"I found the requested month, but {primary_table} has no recognizable date or timestamp column.",
                suggestions=(f"Show all {primary_table}",),
            )
        conditions.extend([
            f"{_qualified(primary_table, date_column)} >= '{start}'",
            f"{_qualified(primary_table, date_column)} < '{end}'",
        ])

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    from_sql = f"FROM {_quote(primary_table)}"
    if joins:
        from_sql += f" {joins}"

    dimensions = [dimension[1]] if dimension else []
    if dimension_expression:
        metric_column = _find_metric_column(text, catalog, primary_table)
        if aggregate in {"sum", "average"} and not metric_column:
            plan = QueryPlan(intent="unknown", dimensions=dimensions, filters=filters, time_range=time_range, relevant_tables=relevant_tables)
            return SemanticResult(
                plan=plan,
                clarification=f"Which numeric field from {primary_table} should I {aggregate}?",
                suggestions=tuple(
                    f"{aggregate.title()} {column.name} by {dimension[1]}"
                    for column in catalog.tables[primary_table].columns if _column_is_numeric(column.data_type) and not column.primary_key
                )[:3],
            )
        if aggregate == "sum":
            measure = f"ROUND(SUM({_qualified(primary_table, metric_column)}), 2) AS {_quote(f'total_{metric_column}')}"
        elif aggregate == "average":
            measure = f"ROUND(AVG({_qualified(primary_table, metric_column)}), 2) AS {_quote(f'average_{metric_column}')}"
        else:
            measure = "COUNT(*) AS record_count"
        sql = f"SELECT {dimension_expression} AS dimension, {measure} {from_sql}{where} GROUP BY {dimension_expression} ORDER BY 2 DESC LIMIT 5000"
        intent = "aggregation"
        metric = metric_column if aggregate in {"sum", "average"} else "record_count"
    elif aggregate:
        metric_column = _find_metric_column(text, catalog, primary_table)
        if aggregate == "count":
            expression = "COUNT(*) AS record_count"
            metric = "record_count"
        elif metric_column:
            function = "SUM" if aggregate == "sum" else "AVG"
            expression = f"ROUND({function}({_qualified(primary_table, metric_column)}), 2) AS {_quote(f'{aggregate}_{metric_column}')}"
            metric = metric_column
        else:
            plan = QueryPlan(intent="unknown", filters=filters, time_range=time_range, relevant_tables=relevant_tables)
            return SemanticResult(plan=plan, clarification=f"Which numeric field from {primary_table} should I {aggregate}?", suggestions=())
        sql = f"SELECT {expression} {from_sql}{where}"
        intent = "aggregation"
    else:
        sql = f"SELECT {_quote(primary_table)}.* {from_sql}{where} ORDER BY 1 LIMIT 5000"
        intent = "lookup"
        metric = None

    plan = QueryPlan(
        intent=intent,
        metric=metric,
        dimensions=dimensions,
        filters=filters,
        time_range=time_range,
        relevant_tables=relevant_tables,
    )
    return SemanticResult(plan=plan, sql=sql)

