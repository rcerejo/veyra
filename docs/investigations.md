# Automated conversion investigations

POST `/api/investigations` accepts two equal-length, ordered, nonoverlapping UTC date ranges and a conversion event. The metric is distinct active users with that event divided by distinct active users in each period. This is a period conversion metric, not an ordered or assignment-based funnel. Repeat events do not increase a user's contribution.

Available user attributes supply device, country, acquisition channel, signup-month cohort, and subscription-tier breakdowns. Missing user attributes appear as unknown. User IDs must be unique. Missing dimensions are omitted rather than inferred. Product-category investigation needs an explicit event/product relationship and is not available in this version.

For segment weights w and rates r, the symmetric decomposition is:

- Within-segment contribution: `(w_before + w_after) / 2 * (r_after - r_before)`
- Composition contribution: `(r_before + r_after) / 2 * (w_after - w_before)`

Their sum equals `w_after*r_after - w_before*r_before`. Contributions across segments reconcile to the overall rate change for each dimension. For entering/exiting segments, the sole observed rate is used on both sides, assigning the contribution to composition. Dimensions overlap and must not be added together.

The report ranks absolute segment contributions and aligned daily rate changes. Rankings describe unusual magnitudes; they are not significance or causality claims. Segments with fewer than 30 users in either period are flagged. Missing days are not treated as verified zero-activity days. Periods outside the observed date range and empty periods are rejected. Event completeness within that range is assumed. Current user attributes cannot reconstruct historical segment changes.

Investigations also support revenue and active-user totals. Each segment's total difference is decomposed into changes in value per observed user and observed user count using the symmetric formula with counts in place of weights. Contributions reconcile in currency units or users. Revenue assumes a single currency and includes negative order amounts.

POST `/api/investigations/ask` accepts bounded plain-language questions mentioning conversion, revenue/sales, or active users. Four ISO dates resolve explicit baseline/current periods. With no dates it compares the latest seven observed dates to the preceding seven and reports that resolution. Unsupported metrics and ambiguous calendar-relative language produce explicit errors; formulas are never inferred by a language model. Historical attributes, causal inference and product-category mapping remain outside the current schema.
