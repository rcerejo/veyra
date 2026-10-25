from math import erfc, sqrt

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError
from app.metrics.statistics import welch


def compare(control_n: int, control_x: int, treatment_n: int, treatment_x: int) -> dict:
    if not control_n or not treatment_n:
        return {'status': 'insufficient_data', 'effect': None, 'interval': None, 'p_value': None}
    c, t = control_x / control_n, treatment_x / treatment_n
    effect = t - c
    adequate = min(control_x, control_n-control_x, treatment_x, treatment_n-treatment_x) >= 10
    if not adequate:
        return {'status': 'insufficient_data', 'effect': effect, 'interval': None, 'p_value': None}
    se = sqrt(c*(1-c)/control_n + t*(1-t)/treatment_n)
    pooled = (control_x+treatment_x)/(control_n+treatment_n)
    null_se = sqrt(pooled*(1-pooled)*(1/control_n+1/treatment_n))
    p = erfc(abs(effect/null_se)/sqrt(2))
    return {'status': 'difference_detected' if p < .05 else 'inconclusive', 'effect': effect,
            'interval': [max(-1, effect-1.95996398454*se), min(1, effect+1.95996398454*se)], 'p_value': p}


def assignment_balance(control: int, treatment: int, expected_treatment: float | None) -> dict:
    if expected_treatment is None:
        return {'status': 'not_configured', 'p_value': None, 'expected_treatment_share': None}
    total = control + treatment
    expected = [total * (1 - expected_treatment), total * expected_treatment]
    if min(expected) < 5:
        return {'status': 'insufficient_data', 'p_value': None, 'expected_treatment_share': expected_treatment}
    statistic = sum((observed - target)**2 / target for observed, target in zip((control, treatment), expected))
    p = erfc(sqrt(statistic / 2))
    return {'status': 'mismatch' if p < .001 else 'passed', 'p_value': p, 'expected_treatment_share': expected_treatment}


def experiments(adapter: SQLiteAdapter, expected_treatment_share: float | None = None, conversion_event: str = 'purchase', window_days: int = 7) -> list[dict]:
    if not conversion_event.strip() or not 1 <= window_days <= 90:
        raise MetricSchemaError('Choose a conversion event and a window of 1–90 days')
    event_literal = "'" + conversion_event.replace("'", "''") + "'"
    schema = {t.name: {c.name for c in t.columns} for t in adapter.discover_schema()}
    required = {'experiments': {'experiment_id', 'experiment_name'}, 'experiment_assignments': {'experiment_id', 'user_id', 'variant', 'assigned_at'}, 'events': {'user_id', 'event_type', 'event_timestamp'}}
    for table, fields in required.items():
        if not fields <= schema.get(table, set()):
            raise MetricSchemaError(f'Experiment analysis requires compatible {table} fields')
    def run(sql):
        _, rows, truncated = adapter.execute_readonly(sql, 100000, 8)
        if truncated:
            raise MetricSchemaError('Experiment analysis exceeds the current row limit')
        return rows
    if not run(f'SELECT 1 FROM events WHERE event_type={event_literal} LIMIT 1'):
        raise MetricSchemaError('The selected conversion event does not exist in this database')
    listed = run('SELECT experiment_id, experiment_name FROM experiments')
    # Aggregate in SQLite so every assigned user contributes at most one outcome.
    rows = run(f"""SELECT a.experiment_id, a.variant, a.user_id,
        COUNT(*) AS assignment_count,
        MAX(CASE WHEN a.user_id IS NULL OR julianday(a.assigned_at) IS NULL THEN 1 ELSE 0 END) AS invalid_assignment,
        MAX(CASE WHEN julianday(a.assigned_at)+{window_days} <= (SELECT MAX(julianday(event_timestamp)) FROM events) THEN 1 ELSE 0 END) AS mature,
        MAX(CASE WHEN EXISTS (SELECT 1 FROM events e WHERE e.user_id=a.user_id AND e.event_type={event_literal}
        AND julianday(e.event_timestamp)>=julianday(a.assigned_at) AND julianday(e.event_timestamp)<julianday(a.assigned_at)+{window_days}) THEN 1 ELSE 0 END) AS converted
        FROM experiment_assignments a GROUP BY a.experiment_id, a.variant, a.user_id""")
    output = []
    for experiment in listed:
        assigned = [r for r in rows if r['experiment_id'] == experiment['experiment_id']]
        users = [r['user_id'] for r in assigned]
        if any(r['invalid_assignment'] for r in assigned):
            raise MetricSchemaError('Experiment assignments require a user and valid assignment timestamp')
        if len(users) != len(set(users)) or any(r['assignment_count'] != 1 for r in assigned):
            raise MetricSchemaError('Conflicting or duplicate experiment assignments must be resolved before analysis')
        if set(r['variant'] for r in assigned) - {'control', 'treatment'}:
            raise MetricSchemaError('This analysis requires variants named control and treatment')
        groups = {}
        for variant in ('control', 'treatment'):
            eligible = [r for r in assigned if r['variant'] == variant and r['mature']]
            groups[variant] = {'users': len(eligible), 'conversions': sum(r['converted'] for r in eligible)}
        c, t = groups['control'], groups['treatment']
        guardrails = []
        if {'session_id', 'user_id', 'session_start'} <= schema.get('sessions', set()):
            session_rows = run(f"""SELECT a.variant, a.user_id, COUNT(s.session_id) AS value
                FROM experiment_assignments a LEFT JOIN sessions s ON s.user_id=a.user_id
                AND julianday(s.session_start)>=julianday(a.assigned_at)
                AND julianday(s.session_start)<julianday(a.assigned_at)+{window_days}
                WHERE a.experiment_id={int(experiment['experiment_id'])}
                AND julianday(a.assigned_at)+{window_days}<=(SELECT MAX(julianday(event_timestamp)) FROM events)
                GROUP BY a.variant, a.user_id""")
            values = {v: [float(r['value']) for r in session_rows if r['variant'] == v] for v in ('control', 'treatment')}
            guardrails.append({'metric': 'sessions_per_assigned_user', 'direction': 'higher_is_better', 'control_mean': sum(values['control'])/len(values['control']) if values['control'] else None, 'treatment_mean': sum(values['treatment'])/len(values['treatment']) if values['treatment'] else None, **welch(values['control'], values['treatment'])})
        balance = assignment_balance(sum(r['variant'] == 'control' for r in assigned), sum(r['variant'] == 'treatment' for r in assigned), expected_treatment_share)
        comparison = compare(c['users'], c['conversions'], t['users'], t['conversions'])
        if balance['status'] == 'mismatch':
            comparison.update(status='assignment_mismatch', interval=None, p_value=None)
            for guardrail in guardrails:
                guardrail.update(status='assignment_mismatch', interval=None, p_value=None)
        relative = ((t['conversions']/t['users'])/(c['conversions']/c['users'])-1) if c['users'] and t['users'] and c['conversions'] else None
        output.append({**experiment, 'conversion_event': conversion_event, 'window_days': window_days, 'groups': groups, 'excluded_immature_users': sum(not r['mature'] for r in assigned),
                       'relative_lift': relative, 'guardrails': guardrails,
                       'warnings': ['Randomization is not verified. Confirm assignment design before causal interpretation.', 'Use a prespecified metric and fixed analysis point; repeated testing and multiple comparisons inflate false positives.', 'Statistical significance does not establish practical importance.', 'Guardrail comparisons are exploratory and unadjusted for multiplicity.'] + ([] if guardrails else ['Session guardrail unavailable: compatible session fields are missing.']) + (['Missing assignments for one or both variants.'] if not all(any(r['variant'] == v for r in assigned) for v in ('control', 'treatment')) else []),
                       'assignment_balance': balance, **comparison})
    return output
