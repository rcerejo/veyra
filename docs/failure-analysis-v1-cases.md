# V1 development audit: all 108 cases

Manual evidence annotations, not automated causal attribution. Primary categories partition the 71 failures; secondary categories overlap. Historical scores and references are unchanged.

Baseline SHA-256: `ab30518aeb69f65210ed11bf334f2f1eff0af094eafaeb35b805ece9f13762d7`.

Manifest SHA-256: `9bcbeaa7cbbc125d0f9e59f72a8f00d0070755a3a20e705246deee99b06cfaab`.

## education-01: PASS

How many learners are there?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "learners"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM learners
```

## education-02: PASS

How many courses are there?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "courses"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM courses
```

## education-03: PASS

How many enrollments are there?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "enrollments"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM enrollments
```

## education-04: PASS

How many lesson views are there?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "lesson_views"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM lesson_views
```

## education-05: PASS

How many different learners have enrolled?

Expected: query. Observed: query.

Evaluation Warning: Accidental pass: total learners equals distinct enrolled learners.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "learners"
```

Reference SQL:

```sql
SELECT COUNT(DISTINCT learner_id) FROM enrollments
```

## education-06: PASS

Count enrollments by state

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT "enrollments"."state" AS dimension, COUNT(*) AS record_count FROM "enrollments" GROUP BY "enrollments"."state" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT state,COUNT(*) FROM enrollments GROUP BY state
```

## education-07: FAIL

How many learners are in each region?

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Requested each-region grouping is absent; generated SQL returns one count.

Secondary categories: none.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "learners"
```

Reference SQL:

```sql
SELECT region,COUNT(*) FROM learners GROUP BY region
```

## education-08: PASS

Total minutes of lesson viewing

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT ROUND(SUM("lesson_views"."minutes"), 2) AS "sum_minutes" FROM "lesson_views"
```

Reference SQL:

```sql
SELECT SUM(minutes) FROM lesson_views
```

## education-09: FAIL

Average nonmissing completion score

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated AVG is rounded to two decimals although the reference/oracle retains precision.

Secondary categories: 8.

Generated SQL:

```sql
SELECT ROUND(AVG("completions"."score"), 2) AS "average_score" FROM "completions"
```

Reference SQL:

```sql
SELECT AVG(score) FROM completions
```

## education-10: FAIL

How many completion scores are missing?

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated count omits the requested IS NULL predicate.

Secondary categories: none.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "completions"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM completions WHERE score IS NULL
```

## education-11: FAIL

List enrollments whose state is active

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit state predicate. State is absent from categorical profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "enrollments".* FROM "enrollments" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM enrollments WHERE state='active'
```

## education-12: FAIL

List enrollments whose state is cancelled

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit state predicate. State is absent from categorical profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "enrollments".* FROM "enrollments" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM enrollments WHERE state='cancelled'
```

## education-13: FAIL

List enrollments whose state is complete

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit state predicate. State is absent from categorical profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "enrollments".* FROM "enrollments" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM enrollments WHERE state='complete'
```

## education-14: FAIL

Show enrollments joined in February 2026

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification says there is no date column although joined_on/viewed_on exists. Date recognizer excludes *_on.

Secondary categories: 1.

Message: I found the requested month, but enrollments has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT * FROM enrollments WHERE joined_on>='2026-02-01' AND joined_on<'2026-03-01'
```

## education-15: FAIL

Show enrollments joined in March 2026

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification says there is no date column although joined_on/viewed_on exists. Date recognizer excludes *_on.

Secondary categories: 1.

Message: I found the requested month, but enrollments has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT * FROM enrollments WHERE joined_on>='2026-03-01' AND joined_on<'2026-04-01'
```

## education-16: FAIL

Count lesson views on or after March 10 and before March 20, 2026

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification says there is no date column although joined_on/viewed_on exists. Date recognizer excludes *_on.

Secondary categories: 1.

Message: I found the requested month, but lesson_views has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT COUNT(*) FROM lesson_views WHERE viewed_on>='2026-03-10' AND viewed_on<'2026-03-20'
```

## education-17: FAIL

Number of distinct viewing learners each day

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Counts all learners without joining viewing/enrollment records, distinct users or daily grouping.

Secondary categories: 1, 3, 4.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "learners"
```

Reference SQL:

```sql
SELECT v.viewed_on,COUNT(DISTINCT e.learner_id) FROM lesson_views v JOIN enrollments e ON e.enrollment_id=v.enrollment_id GROUP BY v.viewed_on
```

## education-18: FAIL

Enrollment counts by course subject

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT c.subject,COUNT(*) FROM enrollments e JOIN courses c ON c.course_id=e.course_id GROUP BY c.subject
```

## education-19: FAIL

Total viewing minutes by learner region

Expected: query. Observed: clarification.

Primary category 1: Incorrect schema or column identification. Selects learners as measure table and asks which field to sum; minutes belongs to lesson_views.

Secondary categories: 2.

Message: Which numeric field from learners should I sum?

Reference SQL:

```sql
SELECT l.region,SUM(v.minutes) FROM lesson_views v JOIN enrollments e ON e.enrollment_id=v.enrollment_id JOIN learners l ON l.learner_id=e.learner_id GROUP BY l.region
```

## education-20: FAIL

List learners without an enrollment

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Generated lookup omits the requested NOT EXISTS enrollment relationship.

Secondary categories: none.

Generated SQL:

```sql
SELECT "learners".* FROM "learners" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT l.* FROM learners l WHERE NOT EXISTS(SELECT 1 FROM enrollments e WHERE e.learner_id=l.learner_id)
```

## education-21: FAIL

List courses without completions

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Clarifies a lexical table tie instead of planning the explicitly requested anti-join.

Secondary categories: none.

Message: I found multiple equally likely tables: completions, courses. Which one should I use?

Reference SQL:

```sql
SELECT c.* FROM courses c WHERE NOT EXISTS(SELECT 1 FROM enrollments e JOIN completions x ON x.enrollment_id=e.enrollment_id WHERE e.course_id=c.course_id)
```

## education-22: FAIL

Enrollment counts by registration region and course subject

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT l.region,c.subject,COUNT(*) FROM enrollments e JOIN learners l ON l.learner_id=e.learner_id JOIN courses c ON c.course_id=e.course_id GROUP BY l.region,c.subject
```

## education-23: FAIL

Daily total viewing minutes

Expected: query. Observed: query.

Primary category 4: Incorrect date and time logic. Sums minutes across the entire table instead of grouping by day.

Secondary categories: 3.

Generated SQL:

```sql
SELECT ROUND(SUM("lesson_views"."minutes"), 2) AS "sum_minutes" FROM "lesson_views"
```

Reference SQL:

```sql
SELECT viewed_on,SUM(minutes) FROM lesson_views GROUP BY viewed_on
```

## education-24: FAIL

Which three enrollments have the most viewing minutes? Break ties by enrollment ID ascending.

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Returns enrollment rows without requested SUM, ranking, top-three limit or tie rule.

Secondary categories: 1, 2.

Generated SQL:

```sql
SELECT "enrollments".* FROM "enrollments" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT enrollment_id,SUM(minutes) AS total FROM lesson_views GROUP BY enrollment_id ORDER BY total DESC,enrollment_id ASC LIMIT 3
```

## education-25: FAIL

Learners enrolled in at least two distinct courses

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical table tie prevents relationship query with distinct-course HAVING.

Secondary categories: 3.

Message: I found multiple equally likely tables: courses, learners. Which one should I use?

Reference SQL:

```sql
SELECT learner_id FROM enrollments GROUP BY learner_id HAVING COUNT(DISTINCT course_id)>=2
```

## education-26: FAIL

Count enrollments with a lesson view on or after their join date

Expected: query. Observed: query.

Primary category 4: Incorrect date and time logic. Counts every enrollment without checking view date >= enrollment date.

Secondary categories: 2.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "enrollments"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on)
```

## education-27: FAIL

Count enrollments that joined, then viewed a lesson, then completed, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered funnel/denominator is not represented; output is a count or raw enrollment rows.

Secondary categories: 2, 3, 4.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "enrollments"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v JOIN completions c ON c.enrollment_id=v.enrollment_id WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on AND c.completed_on>=v.viewed_on)
```

## education-28: FAIL

What fraction of all enrollments joined then viewed then completed, allowing same-day steps?

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered funnel/denominator is not represented; output is a count or raw enrollment rows.

Secondary categories: 2, 3, 4.

Generated SQL:

```sql
SELECT "enrollments".* FROM "enrollments" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT COUNT(*)*1.0/(SELECT COUNT(*) FROM enrollments) FROM enrollments e WHERE EXISTS(SELECT 1 FROM lesson_views v JOIN completions c ON c.enrollment_id=v.enrollment_id WHERE v.enrollment_id=e.enrollment_id AND v.viewed_on>=e.joined_on AND c.completed_on>=v.viewed_on)
```

## education-29: FAIL

List completions with scores at least 50

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the score >= 50 predicate.

Secondary categories: none.

Generated SQL:

```sql
SELECT "completions".* FROM "completions" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM completions WHERE score>=50
```

## education-30: FAIL

How many enrollments joined before March 1, 2026 but completed during March?

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification says there is no date column although joined_on/viewed_on exists. Date recognizer excludes *_on.

Secondary categories: 1.

Message: I found the requested month, but enrollments has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT COUNT(*) FROM enrollments e WHERE e.joined_on<'2026-03-01' AND EXISTS(SELECT 1 FROM completions c WHERE c.enrollment_id=e.enrollment_id AND c.completed_on>='2026-03-01' AND c.completed_on<'2026-04-01')
```

## education-31: PASS

Show retention

Expected: clarification. Observed: clarification.

Message: This analytical metric needs a confirmed definition and mappings for entities, activity and dates in this dataset. Please configure those meanings before calculating it.

## education-32: PASS

Show course revenue

Expected: clarification. Observed: clarification.

Clarification Warning: Category is correct, but message asks which table rather than the missing business definition/field.

Message: I could not identify which table the question refers to. Which dataset should I use?

## education-33: FAIL

Who are our best learners?

Expected: clarification. Observed: query.

Primary category 6: Ambiguous questions that should trigger clarification. Undefined best learner criterion is answered with raw learners rather than clarification.

Secondary categories: 5.

Generated SQL:

```sql
SELECT "learners".* FROM "learners" ORDER BY 1 LIMIT 5000
```

## education-34: PASS

Show conversion rate

Expected: clarification. Observed: clarification.

Clarification Warning: Category is correct, but message asks which table rather than the missing business definition/field.

Message: I could not identify which table the question refers to. Which dataset should I use?

## education-35: PASS

Delete all learners

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.

## education-36: PASS

Drop the courses table

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.

## logistics-01: PASS

Count all depots

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "depots"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM depots
```

## logistics-02: PASS

Count all parcels

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM parcels
```

## logistics-03: PASS

Count all checkpoints

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "checkpoints"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM checkpoints
```

## logistics-04: PASS

Count all charges

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "charges"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM charges
```

## logistics-05: FAIL

How many distinct parcels have checkpoints?

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical table tie blocks distinct parcels participating in the checkpoint relationship.

Secondary categories: 3.

Message: I found multiple equally likely tables: checkpoints, parcels. Which one should I use?

Reference SQL:

```sql
SELECT COUNT(DISTINCT parcel_id) FROM checkpoints
```

## logistics-06: PASS

Count checkpoints by stage

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT "checkpoints"."stage" AS dimension, COUNT(*) AS record_count FROM "checkpoints" GROUP BY "checkpoints"."stage" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT stage,COUNT(*) FROM checkpoints GROUP BY stage
```

## logistics-07: PASS

Total parcel weight in grams

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT ROUND(SUM("parcels"."weight_grams"), 2) AS "sum_weight_grams" FROM "parcels"
```

Reference SQL:

```sql
SELECT SUM(weight_grams) FROM parcels
```

## logistics-08: PASS

Average parcel weight in grams

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT ROUND(AVG("parcels"."weight_grams"), 2) AS "average_weight_grams" FROM "parcels"
```

Reference SQL:

```sql
SELECT AVG(weight_grams) FROM parcels
```

## logistics-09: FAIL

Net charged cents grouped by currency, including refunds

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Net charged cents is compiled as COUNT(*) instead of SUM(amount_cents).

Secondary categories: none.

Generated SQL:

```sql
SELECT "charges"."currency" AS dimension, COUNT(*) AS record_count FROM "charges" GROUP BY "charges"."currency" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT currency,SUM(amount_cents) FROM charges GROUP BY currency
```

## logistics-10: FAIL

How many negative ledger charges exist?

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated count omits amount_cents < 0.

Secondary categories: none.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "charges"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM charges WHERE amount_cents<0
```

## logistics-11: FAIL

List checkpoints at stage accepted

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit stage predicate. Stage is absent from profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "checkpoints".* FROM "checkpoints" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM checkpoints WHERE stage='accepted'
```

## logistics-12: FAIL

List checkpoints at stage in_transit

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit stage predicate. Stage is absent from profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "checkpoints".* FROM "checkpoints" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM checkpoints WHERE stage='in_transit'
```

## logistics-13: FAIL

List checkpoints at stage delivered

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the explicit stage predicate. Stage is absent from profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "checkpoints".* FROM "checkpoints" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM checkpoints WHERE stage='delivered'
```

## logistics-14: FAIL

List parcels shipped from March 10 through March 19, 2026 inclusive

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification rejects shipped_on as unrecognizable despite an explicit date request.

Secondary categories: 1.

Message: I found the requested month, but parcels has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT * FROM parcels WHERE shipped_on>='2026-03-10' AND shipped_on<'2026-03-20'
```

## logistics-15: FAIL

Daily count of parcels shipped

Expected: query. Observed: query.

Primary category 4: Incorrect date and time logic. Daily grouping is omitted; generated SQL returns one parcel count.

Secondary categories: 3.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT shipped_on,COUNT(*) FROM parcels GROUP BY shipped_on
```

## logistics-16: FAIL

Count distinct delivered parcels per day

Expected: query. Observed: query.

Primary category 4: Incorrect date and time logic. Per-day grouping, delivered filter, distinctness and checkpoint table are absent.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT occurred_on,COUNT(DISTINCT parcel_id) FROM checkpoints WHERE stage='delivered' GROUP BY occurred_on
```

## logistics-17: FAIL

Parcel counts by origin zone

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT d.zone,COUNT(*) FROM parcels p JOIN depots d ON d.depot_id=p.origin_depot GROUP BY d.zone
```

## logistics-18: FAIL

Parcel counts by destination zone

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT d.zone,COUNT(*) FROM parcels p JOIN depots d ON d.depot_id=p.destination_depot GROUP BY d.zone
```

## logistics-19: FAIL

Parcel counts by origin zone and destination zone

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT o.zone AS origin_zone,d.zone AS destination_zone,COUNT(*) FROM parcels p JOIN depots o ON o.depot_id=p.origin_depot JOIN depots d ON d.depot_id=p.destination_depot GROUP BY o.zone,d.zone
```

## logistics-20: FAIL

Net cents by origin zone and currency, counting each ledger charge once

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT d.zone,c.currency,SUM(c.amount_cents) FROM charges c JOIN parcels p ON p.parcel_id=c.parcel_id JOIN depots d ON d.depot_id=p.origin_depot GROUP BY d.zone,c.currency
```

## logistics-21: FAIL

List parcels without a delivered checkpoint

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Generated lookup omits the NOT EXISTS delivered-checkpoint condition.

Secondary categories: 3.

Generated SQL:

```sql
SELECT "parcels".* FROM "parcels" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT p.* FROM parcels p WHERE NOT EXISTS(SELECT 1 FROM checkpoints s WHERE s.parcel_id=p.parcel_id AND s.stage='delivered')
```

## logistics-22: FAIL

List parcels with no ledger charges

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical table tie prevents the requested no-charges anti-join.

Secondary categories: none.

Message: I found multiple equally likely tables: charges, parcels. Which one should I use?

Reference SQL:

```sql
SELECT p.* FROM parcels p WHERE NOT EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id)
```

## logistics-23: FAIL

How many parcels have more than one ledger charge?

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Counts all parcels instead of grouping related charges and applying HAVING COUNT(*) > 1.

Secondary categories: 3.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM (SELECT parcel_id FROM charges GROUP BY parcel_id HAVING COUNT(*)>1)
```

## logistics-24: FAIL

Three heaviest parcels, weight descending then parcel ID ascending

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Returns parcel rows without the requested weight projection, descending rank or top-three limit.

Secondary categories: none.

Generated SQL:

```sql
SELECT "parcels".* FROM "parcels" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT parcel_id,weight_grams FROM parcels ORDER BY weight_grams DESC,parcel_id ASC LIMIT 3
```

## logistics-25: FAIL

How many parcels have both a shipping charge and a refund?

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Counts all parcels without the two required related-ledger EXISTS predicates.

Secondary categories: 3.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id AND c.kind='shipping') AND EXISTS(SELECT 1 FROM charges c WHERE c.parcel_id=p.parcel_id AND c.kind='refund')
```

## logistics-26: FAIL

Count parcels delivered on or after their shipping date

Expected: query. Observed: query.

Primary category 4: Incorrect date and time logic. Counts every parcel without checking delivery date >= shipping date.

Secondary categories: 2.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints s WHERE s.parcel_id=p.parcel_id AND s.stage='delivered' AND s.occurred_on>=p.shipped_on)
```

## logistics-27: FAIL

Count parcels shipped then accepted then delivered, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered shipping/acceptance/delivery funnel is replaced by a count or raw rows.

Secondary categories: 2, 3, 4.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "parcels"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints a JOIN checkpoints b ON a.parcel_id=b.parcel_id WHERE a.parcel_id=p.parcel_id AND a.stage='accepted' AND b.stage='delivered' AND a.occurred_on>=p.shipped_on AND b.occurred_on>=a.occurred_on)
```

## logistics-28: FAIL

Fraction of all parcels shipped then accepted then delivered, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered shipping/acceptance/delivery funnel is replaced by a count or raw rows.

Secondary categories: 2, 3, 4.

Generated SQL:

```sql
SELECT "parcels".* FROM "parcels" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT COUNT(*)*1.0/(SELECT COUNT(*) FROM parcels) FROM parcels p WHERE EXISTS(SELECT 1 FROM checkpoints a JOIN checkpoints b ON a.parcel_id=b.parcel_id WHERE a.parcel_id=p.parcel_id AND a.stage='accepted' AND b.stage='delivered' AND a.occurred_on>=p.shipped_on AND b.occurred_on>=a.occurred_on)
```

## logistics-29: FAIL

Net USD cents for parcels shipped before March 15, 2026

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Clarification rejects shipped_on as unrecognizable despite an explicit date request.

Secondary categories: 1.

Message: I found the requested month, but parcels has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT SUM(c.amount_cents) FROM charges c JOIN parcels p ON p.parcel_id=c.parcel_id WHERE c.currency='USD' AND p.shipped_on<'2026-03-15'
```

## logistics-30: FAIL

List parcels heavier than 400 grams

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits weight_grams > 400.

Secondary categories: none.

Generated SQL:

```sql
SELECT "parcels".* FROM "parcels" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM parcels WHERE weight_grams>400
```

## logistics-31: FAIL

Show parcel counts by zone

Expected: clarification. Observed: error.

Primary category 7: SQL generation or execution errors. Ambiguous origin/destination zone request reaches the same implicit-FK None exception instead of clarification.

Secondary categories: 2, 6.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

## logistics-32: PASS

What is total revenue in dollars?

Expected: clarification. Observed: clarification.

Clarification Warning: Category is correct, but message asks which table rather than the missing business definition/field.

Message: I could not identify which table the question refers to. Which dataset should I use?

## logistics-33: PASS

Show customer churn

Expected: clarification. Observed: clarification.

Message: This analytical metric needs a confirmed definition and mappings for entities, activity and dates in this dataset. Please configure those meanings before calculating it.

## logistics-34: FAIL

Which depot is best?

Expected: clarification. Observed: query.

Primary category 6: Ambiguous questions that should trigger clarification. Undefined best depot criterion is answered with raw depots rather than clarification.

Secondary categories: 5.

Generated SQL:

```sql
SELECT "depots".* FROM "depots" ORDER BY 1 LIMIT 5000
```

## logistics-35: PASS

Update every parcel weight to zero

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.

## logistics-36: PASS

Delete all charges

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.

## collaboration-01: PASS

How many organizations records exist?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "organizations"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM organizations
```

## collaboration-02: PASS

How many people records exist?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "people"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM people
```

## collaboration-03: PASS

How many memberships records exist?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "memberships"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM memberships
```

## collaboration-04: PASS

How many audit log records exist?

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "audit_log"
```

Reference SQL:

```sql
SELECT COUNT(*) FROM audit_log
```

## collaboration-05: PASS

How many distinct people belong to an organization?

Expected: query. Observed: query.

Evaluation Warning: Accidental pass: total people equals distinct organization members.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "people"
```

Reference SQL:

```sql
SELECT COUNT(DISTINCT person_id) FROM memberships
```

## collaboration-06: PASS

Count organizations by plan

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT "organizations"."plan" AS dimension, COUNT(*) AS record_count FROM "organizations" GROUP BY "organizations"."plan" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT plan,COUNT(*) FROM organizations GROUP BY plan
```

## collaboration-07: PASS

Count memberships by role

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT "memberships"."role" AS dimension, COUNT(*) AS record_count FROM "memberships" GROUP BY "memberships"."role" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT role,COUNT(*) FROM memberships GROUP BY role
```

## collaboration-08: PASS

Sum invoice amounts in USD cents including all states

Expected: query. Observed: query.

Generated SQL:

```sql
SELECT ROUND(SUM("invoices"."usd_cents"), 2) AS "sum_usd_cents" FROM "invoices"
```

Reference SQL:

```sql
SELECT SUM(usd_cents) FROM invoices
```

## collaboration-09: FAIL

Average paid invoice amount in USD cents

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. AVG includes void invoices because the paid-state predicate is absent.

Secondary categories: 1.

Generated SQL:

```sql
SELECT ROUND(AVG("invoices"."usd_cents"), 2) AS "average_usd_cents" FROM "invoices"
```

Reference SQL:

```sql
SELECT AVG(usd_cents) FROM invoices WHERE state='paid'
```

## collaboration-10: FAIL

List void invoices

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Generated lookup omits the void-state predicate; state is absent from profiles.

Secondary categories: 1.

Generated SQL:

```sql
SELECT "invoices".* FROM "invoices" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT * FROM invoices WHERE state='void'
```

## collaboration-11: FAIL

List audit log records for sign_in

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Normalized action labels require a catalog join, but generated SQL returns the entire audit log.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT "audit_log".* FROM "audit_log" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT l.* FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id WHERE a.label='sign_in'
```

## collaboration-12: FAIL

List audit log records for document_create

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Normalized action labels require a catalog join, but generated SQL returns the entire audit log.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT "audit_log".* FROM "audit_log" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT l.* FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id WHERE a.label='document_create'
```

## collaboration-13: FAIL

List audit log records for share_link

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Normalized action labels require a catalog join, but generated SQL returns the entire audit log.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT "audit_log".* FROM "audit_log" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT l.* FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id WHERE a.label='share_link'
```

## collaboration-14: FAIL

List invoices issued March 1 through March 9, 2026 inclusive

Expected: query. Observed: clarification.

Primary category 4: Incorrect date and time logic. Issued_on is not recognized as a date field.

Secondary categories: 1.

Message: I found the requested month, but invoices has no recognizable date or timestamp column.

Reference SQL:

```sql
SELECT * FROM invoices WHERE issued_on>='2026-03-01' AND issued_on<'2026-03-10'
```

## collaboration-15: FAIL

Daily distinct active people from the audit log

Expected: query. Observed: clarification.

Primary category 1: Incorrect schema or column identification. Lexical audit_log/people tie blocks an explicit audit-log activity request.

Secondary categories: 3, 4.

Message: I found multiple equally likely tables: audit_log, people. Which one should I use?

Reference SQL:

```sql
SELECT occurred_on,COUNT(DISTINCT actor_id) FROM audit_log GROUP BY occurred_on
```

## collaboration-16: FAIL

Distinct active people per workspace, not membership counts

Expected: query. Observed: query.

Primary category 1: Incorrect schema or column identification. Selects people rather than audit_log; distinct actors and workspace grouping are absent.

Secondary categories: 3.

Generated SQL:

```sql
SELECT "people".* FROM "people" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT workspace_id,COUNT(DISTINCT actor_id) FROM audit_log GROUP BY workspace_id
```

## collaboration-17: FAIL

Count audit actions by their catalog label

Expected: query. Observed: query.

Primary category 1: Incorrect schema or column identification. Counts catalog entries instead of fact-table occurrences joined to catalog labels.

Secondary categories: 2, 3.

Generated SQL:

```sql
SELECT "action_catalog"."label" AS dimension, COUNT(*) AS record_count FROM "action_catalog" GROUP BY "action_catalog"."label" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT a.label,COUNT(*) FROM audit_log l JOIN action_catalog a ON a.action_id=l.action_id GROUP BY a.label
```

## collaboration-18: FAIL

Count membership relationships by organization plan

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT o.plan,COUNT(*) FROM memberships m JOIN organizations o ON o.org_id=m.org_id GROUP BY o.plan
```

## collaboration-19: FAIL

Distinct members by organization plan, deduplicating people across organizations of the same plan

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Counts organizations by plan instead of distinct people across membership relationships.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT "organizations"."plan" AS dimension, COUNT(*) AS record_count FROM "organizations" GROUP BY "organizations"."plan" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT o.plan,COUNT(DISTINCT m.person_id) FROM memberships m JOIN organizations o ON o.org_id=m.org_id GROUP BY o.plan
```

## collaboration-20: FAIL

Paid invoice USD cents by organization plan without membership fanout

Expected: query. Observed: error.

Primary category 7: SQL generation or execution errors. Implicit REFERENCES target produces target_column=None; join SQL calls identifier.replace on None.

Secondary categories: 2.

Error: AttributeError: 'NoneType' object has no attribute 'replace'

Reference SQL:

```sql
SELECT o.plan,SUM(i.usd_cents) FROM invoices i JOIN organizations o ON o.org_id=i.org_id WHERE i.state='paid' GROUP BY o.plan
```

## collaboration-21: FAIL

List people with no memberships

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical table tie prevents the requested anti-join; no additional business definition is needed.

Secondary categories: none.

Message: I found multiple equally likely tables: memberships, people. Which one should I use?

Reference SQL:

```sql
SELECT p.* FROM people p WHERE NOT EXISTS(SELECT 1 FROM memberships m WHERE m.person_id=p.person_id)
```

## collaboration-22: FAIL

List organizations with no paid invoices

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical table tie prevents the requested anti-join; no additional business definition is needed.

Secondary categories: none.

Message: I found multiple equally likely tables: invoices, organizations. Which one should I use?

Reference SQL:

```sql
SELECT o.* FROM organizations o WHERE NOT EXISTS(SELECT 1 FROM invoices i WHERE i.org_id=o.org_id AND i.state='paid')
```

## collaboration-23: FAIL

People who belong to more than one organization

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Returns all people rather than applying a grouped membership HAVING condition.

Secondary categories: 3.

Generated SQL:

```sql
SELECT "people".* FROM "people" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT person_id FROM memberships GROUP BY person_id HAVING COUNT(*)>1
```

## collaboration-24: FAIL

Top three actors by audit record count, breaking ties by actor ID ascending

Expected: query. Observed: query.

Primary category 3: Incorrect filtering or aggregation. Returns one audit count without actor grouping, ranking or top-three limit.

Secondary categories: 1.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "audit_log"
```

Reference SQL:

```sql
SELECT actor_id,COUNT(*) AS n FROM audit_log GROUP BY actor_id ORDER BY n DESC,actor_id ASC LIMIT 3
```

## collaboration-25: FAIL

Count audit log records from people who are not members of that workspace

Expected: query. Observed: clarification.

Primary category 2: Incorrect joins or table relationships. Lexical tie prevents the explicit person/workspace composite anti-join.

Secondary categories: 1.

Message: I found multiple equally likely tables: audit_log, people. Which one should I use?

Reference SQL:

```sql
SELECT COUNT(*) FROM audit_log l WHERE NOT EXISTS(SELECT 1 FROM memberships m WHERE m.person_id=l.actor_id AND m.org_id=l.workspace_id)
```

## collaboration-26: FAIL

Count distinct people who signed in then created a document across any workspaces, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered person-level funnel across workspaces is replaced by people count/raw rows.

Secondary categories: 1, 2, 3, 4.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "people"
```

Reference SQL:

```sql
SELECT COUNT(DISTINCT a.actor_id) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN action_catalog x ON x.action_id=a.action_id JOIN action_catalog y ON y.action_id=b.action_id WHERE x.label='sign_in' AND y.label='document_create' AND b.occurred_on>=a.occurred_on
```

## collaboration-27: FAIL

Count distinct people who signed in, then created a document, then shared a link across any workspaces, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered person-level funnel across workspaces is replaced by people count/raw rows.

Secondary categories: 1, 2, 3, 4.

Generated SQL:

```sql
SELECT COUNT(*) AS record_count FROM "people"
```

Reference SQL:

```sql
SELECT COUNT(DISTINCT a.actor_id) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN audit_log c ON c.actor_id=a.actor_id WHERE a.action_id=(SELECT action_id FROM action_catalog WHERE label='sign_in') AND b.action_id=(SELECT action_id FROM action_catalog WHERE label='document_create') AND c.action_id=(SELECT action_id FROM action_catalog WHERE label='share_link') AND b.occurred_on>=a.occurred_on AND c.occurred_on>=b.occurred_on
```

## collaboration-28: FAIL

Fraction of all registered people who signed in then created then shared across any workspaces, allowing same-day steps

Expected: query. Observed: query.

Primary category 5: Incorrect interpretation of business metrics. Explicit ordered person-level funnel across workspaces is replaced by people count/raw rows.

Secondary categories: 1, 2, 3, 4.

Generated SQL:

```sql
SELECT "people".* FROM "people" ORDER BY 1 LIMIT 5000
```

Reference SQL:

```sql
SELECT COUNT(DISTINCT a.actor_id)*1.0/(SELECT COUNT(*) FROM people) FROM audit_log a JOIN audit_log b ON b.actor_id=a.actor_id JOIN audit_log c ON c.actor_id=a.actor_id WHERE a.action_id=1 AND b.action_id=2 AND c.action_id=3 AND b.occurred_on>=a.occurred_on AND c.occurred_on>=b.occurred_on
```

## collaboration-29: FAIL

Count distinct actors active March 10 through March 19, 2026 inclusive

Expected: query. Observed: clarification.

Primary category 1: Incorrect schema or column identification. Cannot identify audit_log from actors; lexical matching does not resolve actor to actor_id.

Secondary categories: 3, 4.

Message: I could not identify which table the question refers to. Which dataset should I use?

Reference SQL:

```sql
SELECT COUNT(DISTINCT actor_id) FROM audit_log WHERE occurred_on>='2026-03-10' AND occurred_on<'2026-03-20'
```

## collaboration-30: FAIL

Count audit actions by organization plan and action label

Expected: query. Observed: query.

Primary category 2: Incorrect joins or table relationships. Counts organizations by one dimension instead of audit events joined to both plan and action label.

Secondary categories: 1, 3.

Generated SQL:

```sql
SELECT "organizations"."plan" AS dimension, COUNT(*) AS record_count FROM "organizations" GROUP BY "organizations"."plan" ORDER BY 2 DESC LIMIT 5000
```

Reference SQL:

```sql
SELECT o.plan,a.label,COUNT(*) FROM audit_log l JOIN organizations o ON o.org_id=l.workspace_id JOIN action_catalog a ON a.action_id=l.action_id GROUP BY o.plan,a.label
```

## collaboration-31: PASS

Show user activation

Expected: clarification. Observed: clarification.

Message: This analytical metric needs a confirmed definition and mappings for entities, activity and dates in this dataset. Please configure those meanings before calculating it.

## collaboration-32: PASS

Calculate session duration

Expected: clarification. Observed: clarification.

Clarification Warning: Category is correct, but message asks which table rather than the missing business definition/field.

Message: I could not identify which table the question refers to. Which dataset should I use?

## collaboration-33: PASS

Show retention by plan

Expected: clarification. Observed: clarification.

Message: This analytical metric needs a confirmed definition and mappings for entities, activity and dates in this dataset. Please configure those meanings before calculating it.

## collaboration-34: PASS

Show revenue per user

Expected: clarification. Observed: clarification.

Clarification Warning: Category is correct, but message asks which table rather than the missing business definition/field.

Message: I could not identify which table the question refers to. Which dataset should I use?

## collaboration-35: PASS

Delete all people

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.

## collaboration-36: PASS

Drop the memberships table

Expected: refusal. Observed: refusal.

Message: VEYRA supports read-only analysis. Data modification requests cannot be executed.
