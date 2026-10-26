from datetime import date, timedelta

from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.database.sqlite import SQLiteAdapter
from app.metrics.activity import MetricSchemaError


def predict(adapter: SQLiteAdapter) -> dict:
    schema = {t.name:{c.name for c in t.columns} for t in adapter.discover_schema()}
    for table, fields in {'users':{'user_id','signup_date'},'events':{'user_id','event_timestamp'},'sessions':{'user_id','session_start'}}.items():
        if not fields <= schema.get(table,set()):
            raise MetricSchemaError(f'Prediction requires compatible {table} fields')
    def run(sql):
        _,rows,truncated = adapter.execute_readonly(sql,100000,8)
        if truncated:
            raise MetricSchemaError('Prediction input exceeds 100,000 users')
        return rows
    last = run('SELECT MAX(DATE(event_timestamp)) AS day FROM events')[0]['day']
    if not last:
        raise MetricSchemaError('Prediction needs event history')
    cutoff = date.fromisoformat(last)-timedelta(days=30)
    start = cutoff-timedelta(days=29)
    rows = run(f"""SELECT u.user_id,
        (SELECT COUNT(*) FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp) BETWEEN '{start}' AND '{cutoff}') AS events,
        (SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.user_id AND DATE(s.session_start) BETWEEN '{start}' AND '{cutoff}') AS sessions,
        COALESCE((SELECT julianday('{cutoff}')-MAX(julianday(DATE(e.event_timestamp))) FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp)<='{cutoff}'),365) AS recency,
        CASE WHEN EXISTS(SELECT 1 FROM events e WHERE e.user_id=u.user_id AND DATE(e.event_timestamp)>'{cutoff}' AND DATE(e.event_timestamp)<='{last}') THEN 0 ELSE 1 END AS churn
        FROM users u WHERE DATE(u.signup_date)<='{start}' ORDER BY u.user_id""")
    rows = [r for r in rows if r['events'] > 0]
    if len(rows)<60 or min(sum(r['churn']==v for r in rows) for v in (0,1))<10:
        raise MetricSchemaError('Prediction needs at least 60 active users and 10 users in each outcome class')
    features = [[r['events'],r['sessions'],r['recency']] for r in rows]
    labels = [r['churn'] for r in rows]
    train_x,test_x,train_y,test_y = train_test_split(features,labels,test_size=.3,stratify=labels,random_state=42)
    output=[]
    for name,model in [('logistic_regression',make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=42))),('random_forest',RandomForestClassifier(n_estimators=100,max_depth=5,min_samples_leaf=5,random_state=42,n_jobs=1))]:
        cv=cross_val_score(model,train_x,train_y,cv=StratifiedKFold(n_splits=3,shuffle=True,random_state=42),scoring='roc_auc',n_jobs=1)
        model.fit(train_x,train_y)
        probabilities=model.predict_proba(test_x)[:,1]
        predicted=probabilities>=.5
        importance = model[-1].coef_[0].tolist() if name=='logistic_regression' else model.feature_importances_.tolist()
        output.append({'model':name,'training_cv_roc_auc':float(cv.mean()),'roc_auc':roc_auc_score(test_y,probabilities),'pr_auc':average_precision_score(test_y,probabilities),'precision':precision_score(test_y,predicted,zero_division=0),'recall':recall_score(test_y,predicted,zero_division=0),'confusion_matrix':confusion_matrix(test_y,predicted).tolist(),'importance':dict(zip(('events','sessions','recency'),importance))})
    clustering=make_pipeline(StandardScaler(),KMeans(n_clusters=3,random_state=42,n_init=10))
    clusters=clustering.fit_predict(features)
    return {'feature_start':str(start),'feature_end':str(cutoff),'outcome_end':last,'users':len(rows),'train_users':len(train_y),'test_users':len(test_y),'models':output,'segments':[{'cluster':i,'users':int(sum(clusters==i))} for i in range(3)],'definition':'Churn means no events during the 30 days after the feature cutoff. Features use only the preceding 30 days. Only users registered before the feature period and active within it are eligible. Fixed stratified user holdout; this evaluates users at one historical cutoff, not future-time generalization. Cluster IDs have no intrinsic business meaning.'}
