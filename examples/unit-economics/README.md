# Utility example

## Guarantees

- Published exact/semantic matches can avoid a generator call.
- Reusable cache keys include tenant, locale, policy version, and query.
- Context-dependent queries bypass reusable cache.
- Generated answers are not stored as validated policy.

## Does not guarantee

- that token-set similarity is production quality;
- that the illustrative threshold transfers to another dataset;
- any currency savings or production hit rate;
- correctness of the fake generated response.
