# Change log

## 2026-11-01 - JSON Jargon discovery completion candidate

- Replace the one-product starter catalog with public-source generation and exact sitemap reconciliation.
- Add all current public collections, articles, FAQs, brand context, source lineage and health data.
- Add blogcatalog/ai-manifest compatibility paths; keep the Garage BlogPosting array.
- Validate public eligibility, canonical identity, explicit blog partitioning, ASCII copy and output allowlist.
- Add regression tests, gated two-hour Pages refresh, stale-feed checks and rollback artifacts.
- Stage a separate narrow Shopify discovery patch; no live theme, release or account configuration changes.
- Preserve public no-training preference; omit private content, prices and inventory claims.

## 2026-11-02 - Hold empty collections

Require actual paginated public product membership; exclude empty and draft-only collections. Verify productIds/counts and prevent invalid collection records from passing output validation. Source health reports the eligibility counts. No Shopify publication settings changed.

Repeated CI exposed HTTP429 throttling. Added shared request pacing and Retry-After backoff, and removed duplicate push validation triggers. No validation/eligibility gate was weakened.

## 2026-11-03 - Paired launch JSON handoff

Add the approved Don't Let It Hit Ya meta description, existing Lovably Unhinged tone, Adult audience and five exact-image alt descriptions to the editorial snapshot. Recommendation text remains empty because no separate recommendation copy was approved. The public-source rebuild discovers the live product and Lovably Unhinged article in the existing product/Dad-a-Pedia/blogcatalog contracts. No generator, schema or commerce changes.
