# Automated conversion investigations

POST `/api/investigations` accepts two equal-length, ordered, nonoverlapping UTC date ranges and a conversion event. The metric is distinct active users with that event divided by distinct active users in each period. This is a period conversion metric, not an ordered or assignment-based funnel. Repeat events do not increase a user's contribution.

Available user attributes supply device, country, acquisition channel, signup-month cohort, and subscription-tier breakdowns. Missing user attributes appear as unknown. User IDs must be unique. Missing dimensions are omitted rather than inferred. Product-category investigation needs an explicit event/product relationship and is not available in this version.

For segment weights w and rates r, the symmetric decomposition is:

- Within-segment contribution: `(w_before + w_after) / 2 * (r_after - r_before)`
- Composition contribution: `(r_before + r_after) / 2 * (w_after - w_before)`

Their sum equals `w_after*r_after - w_before*r_before`. Contributions across segments reconcile to the overall rate change for each dimension. For entering/exiting segments, the sole observed rate is used on both sides, assigning the contribution to composition. Dimensions overlap and must not be added together.

The report ranks absolute segment contributions and aligned daily rate changes. Rankings describe unusual magnitudes; they are not significance or causality claims. Segments with fewer than 30 users in either period are flagged. Missing days are not treated as verified zero-activity days. Periods outside the observed date range and empty periods are rejected. Event completeness within that range is assumed. Current user attributes cannot reconstruct historical segment changes.

The current workflow is a structured conversion investigation. Other KPI definitions, free-text investigation routing, historical attributes, automatic causal inference, and product-category mapping require additional work.
