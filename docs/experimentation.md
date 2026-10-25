# Experiment analysis

The Experimentation Lab compares conversion between variants named `control` and `treatment`. The analyst selects an existing event and a window of 1–90 days; the default is seven-day purchase conversion. Each assigned user contributes one binary outcome. Events before assignment and at or after the window boundary are excluded. Users without the full follow-up window are excluded, using the latest event timestamp as the observation cutoff. This cutoff assumes event ingestion is complete; it cannot establish completeness. Select the metric and analysis window before examining results; trying multiple definitions requires a separate multiplicity strategy.

The two-sided pooled proportion z-test and approximate unpooled 95% confidence interval require at least ten successes and ten failures in each arm. The reported effect is treatment minus control in percentage points. Inconclusive results do not establish equivalence. Independent randomized assignments and a fixed analysis point are assumed; repeated testing, multiplicity, and randomization are not verified.

The optional planned treatment share is supplied by the analyst, not inferred from outcomes. A Pearson chi-squared goodness-of-fit test checks all assignments against this allocation. Expected counts below five produce insufficient data; p < 0.001 flags a mismatch and suppresses outcome inference. A passing balance check alone does not prove randomization. Duplicate assignments, conflicting variants, missing users, and invalid assignment dates are rejected.

References: [NIST proportion comparison](https://itl.nist.gov/div898/software/dataplot/refman1/auxillar/binotest.htm) and [Microsoft assignment ratio diagnostics](https://www.microsoft.com/en-us/research/articles/alerting-in-microsofts-experimentation-platform-exp/).

## Planning and guardrails

The planning calculator uses a prospective baseline conversion, positive absolute improvement, and planned users per arm. It returns approximate required sample size for 80% power at two-sided alpha 0.05, power at the planned sample, and minimum detectable positive improvement. Allocation is equal in this planner, regardless of the balance-check setting. It is not observed power or a sequential stopping procedure.

The engagement guardrail is sessions starting within the same follow-up window per eligible assigned user, including zero-session users. Welch's unequal-variance t-test compares the per-user means, with a Student-t confidence interval. Degenerate and undersized inputs withhold inference. Guardrails are exploratory, unadjusted comparisons; the analyst must prespecify practical thresholds and a multiple-testing policy. Relative conversion lift is undefined if the control conversion rate is zero.

The current module supports binary conversion and a session-count guardrail on canonical product tables. Arbitrary schema mapping, other continuous metrics, multi-arm comparisons, sequential testing, and automatic causal verification are outside this implementation.
