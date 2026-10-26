# Predictive analytics

POST `/api/prediction` evaluates logistic regression and random forest classifiers locally. The final thirty observed days define the label window. Features use event count, session count and recency from the preceding thirty-day window. Users must have signed up before that feature window and been active during it. Churn is no events in the label window.

A fixed, stratified 70/30 user split separates training and holdout data. Three-fold stratified cross-validation runs only on training users. Logistic-regression scaling is fit within each training fold. ROC-AUC, average precision (the reported PR-AUC summary), precision, recall and confusion matrix are computed from holdout outcomes. The decision threshold is 0.5. Logistic coefficients use standardized features; random-forest importances are impurity based and are not causal effects.

K-means standardizes the full eligible feature population for descriptive clustering. This is unsupervised exploration, not predictive holdout evaluation. Cluster identifiers are arbitrary. No individual risk scores are stored or served.

The current experiment uses one historical cutoff. It does not estimate future-time generalization or constitute a deployed churn model. Event completeness is assumed. Small or single-class datasets are rejected; a minimum of sixty users and ten per class is required. Synthetic dataset performance must not be represented as real-product performance.
