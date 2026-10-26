import time
import tracemalloc
from collections import Counter

from app.core.config import Settings
from app.database.schema import SchemaCatalog
from app.query_engine.service import QueryService
from app.query_engine.validator import UnsafeQueryError, validate_sql
from app.schemas.query import QueryRequest, QueryResponse, QueryPlan


def benchmark_cases() -> list[dict]:
    cases = []
    for table, singular in [('users','user'),('orders','order')]:
        for question in [f'How many {table} are there?',f'Count {table}']:
            cases.append({'question':question,'sql':f'SELECT COUNT(*) FROM {table}'})
    cases += [{'question':'What is the total revenue?','sql':'SELECT ROUND(SUM(revenue),2) FROM orders'},
              {'question':'Show users by country','sql':'SELECT country, COUNT(*) FROM users GROUP BY country ORDER BY COUNT(*) DESC'},
              {'question':'Show users by acquisition channel','sql':'SELECT acquisition_channel, COUNT(*) FROM users GROUP BY acquisition_channel ORDER BY COUNT(*) DESC'},
              {'question':'Show events by type','sql':'SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC'},
              {'question':'Show daily active users','sql':'SELECT DATE(event_timestamp), COUNT(DISTINCT user_id) FROM events GROUP BY DATE(event_timestamp) ORDER BY DATE(event_timestamp)'}]
    for month, start, end in [('January','2026-01-01','2026-02-01'),('February','2026-02-01','2026-03-01'),('March','2026-03-01','2026-04-01'),('April','2026-04-01','2026-05-01')]:
        for table,column in [('users','signup_date'),('orders','order_timestamp'),('sessions','session_start')]:
            cases.append({'question':f'Show {table} in {month} 2026','sql':f"SELECT * FROM {table} WHERE {column}>='{start}' AND {column}<'{end}' ORDER BY {column} LIMIT 5000"})
        for event, phrase in [('app_open','opened the app'),('view_product','viewed a product'),('add_to_cart','added to cart'),('checkout_started','started checkout'),('purchase','purchased')]:
            cases.append({'question':f'Show all instances where users {phrase} in {month} 2026','sql':f"SELECT * FROM events WHERE event_type='{event}' AND event_timestamp>='{start}' AND event_timestamp<'{end}' ORDER BY event_timestamp LIMIT 5000"})
    for table in ('events','sessions','experiments','experiment_assignments'):
        cases.append({'question':f'How many {table} are there?','sql':f'SELECT COUNT(*) FROM {table}'})
    cases += [{'question': 'Show recent orders', 'sql':'SELECT order_id,user_id,order_timestamp,revenue FROM orders ORDER BY order_timestamp DESC LIMIT 50'},
              {'question': 'Delete all users', 'reject':True}, {'question':'Drop the events table','reject':True}, {'question':'Update every order revenue to zero','reject':True}, {'question':'Show me the best thing','clarify':True}]
    cases += [
        {'question':'Show total revenue by country','sql':'SELECT u.country, SUM(o.revenue) FROM orders o JOIN users u ON u.user_id=o.user_id GROUP BY u.country'},
        {'question':'Show total revenue by device type','sql':'SELECT u.device_type, SUM(o.revenue) FROM orders o JOIN users u ON u.user_id=o.user_id GROUP BY u.device_type'},
        {'question':'Show average order revenue by acquisition channel','sql':'SELECT u.acquisition_channel, AVG(o.revenue) FROM orders o JOIN users u ON u.user_id=o.user_id GROUP BY u.acquisition_channel'},
        {'question':'Show Day 7 signup retention','sql':"SELECT COUNT(DISTINCT CASE WHEN EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp)=DATE(u.signup_date,'+7 days')) THEN u.user_id END)*1.0/NULLIF(COUNT(*),0) FROM users u WHERE DATE(u.signup_date,'+7 days')<=(SELECT MAX(DATE(event_timestamp)) FROM events)"},
        {'question':'Show active user purchase conversion','sql':"SELECT COUNT(DISTINCT CASE WHEN event_type='purchase' THEN user_id END)*1.0/NULLIF(COUNT(DISTINCT user_id),0) FROM events"},
        {'question':'Show signup cohorts by month','sql':"SELECT strftime('%Y-%m',signup_date),COUNT(*) FROM users GROUP BY strftime('%Y-%m',signup_date)"},
        {'question':'Show experiment assignments by variant','sql':'SELECT experiment_id,variant,COUNT(*) FROM experiment_assignments GROUP BY experiment_id,variant'},
        {'question':'Show total revenue by signup cohort','sql':"SELECT strftime('%Y-%m',u.signup_date), SUM(o.revenue) FROM users u JOIN orders o ON o.user_id=u.user_id GROUP BY strftime('%Y-%m',u.signup_date)"},
    ]
    return cases


def canonical(rows):
    return Counter(tuple(row.values()) for row in rows)


async def evaluate(settings: Settings, include_models: bool = False) -> dict:
    service=QueryService(settings)
    catalog=SchemaCatalog(service.adapter.discover_schema(),service.adapter.profile_values())
    cases=benchmark_cases()
    systems=['veyra'] + (['direct_llm','schema_llm'] if include_models and await service.ollama.available() else [])
    measured=[]
    owns_trace=not tracemalloc.is_tracing()
    if owns_trace:
        tracemalloc.start()
    for system in systems:
        outcomes=[]
        for case in cases:
            started=time.perf_counter()
            inference_ms=None
            result={'question':case['question'],'correct':False,'executed':False,'safe_rejection':False,'syntax_valid':None}
            try:
                if system=='veyra':
                    answer=await service.ask(QueryRequest(question=case['question']))
                    rows=answer.rows if isinstance(answer,QueryResponse) else None
                    result['syntax_valid']=True if isinstance(answer,QueryResponse) else None
                    result['correction_attempts']=answer.metadata.correction_attempts if isinstance(answer,QueryResponse) else 0
                else:
                    inference_started=time.perf_counter()
                    sql=await service.ollama.generate_sql(case['question'],QueryPlan(intent='unknown'),catalog.prompt_context() if system=='schema_llm' else 'No schema supplied.')
                    inference_ms=(time.perf_counter()-inference_started)*1000
                    rows=service.adapter.execute_readonly(validate_sql(sql,catalog),5000,8)[1]
                    result['syntax_valid']=True
                result['executed']=rows is not None
                if case.get('reject') or case.get('clarify'):
                    result['correct']=rows is None
                else:
                    reference=service.adapter.execute_readonly(case['sql'],5000,8)[1]
                    result['correct']=rows is not None and canonical(rows)==canonical(reference)
            except Exception as exc:
                result['error']=str(exc)[:300]
                result['safe_rejection']=bool(case.get('reject')) and isinstance(exc,UnsafeQueryError)
                result['correct']=result['safe_rejection']
            result.update(latency_ms=round((time.perf_counter()-started)*1000,2),inference_ms=inference_ms)
            outcomes.append(result)
        measured.append({'system':system,'cases':outcomes,'correct':sum(r['correct'] for r in outcomes),'total':len(outcomes),'execution_success':sum(r['executed'] for r in outcomes),'corrected_queries':sum(r.get('correction_attempts',0)>0 for r in outcomes),'successful_corrections':sum(r.get('correction_attempts',0)>0 and r['correct'] for r in outcomes)})
    peak=tracemalloc.get_traced_memory()[1]
    if owns_trace:
        tracemalloc.stop()
    return {'database':service.adapter.path.name,'python_peak_bytes':peak,'systems':measured,'model_baselines':'measured' if len(systems)>1 else 'not run (enable models and make Ollama available)', 'notes':['Correctness compares result multisets with independent reference SQL; column aliases and order are ignored.','Advanced metric correctness is also covered separately by unit tests.','Model baselines run through read-only safety checks. No benchmark score is inferred for skipped systems.','Latency is wall-clock; inference latency is available for model baselines. Syntax-valid is true for validated executed SQL; rejected requests are unclassified. Python peak allocation is not total process RSS and may include concurrent requests.']}
