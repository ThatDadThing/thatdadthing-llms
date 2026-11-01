# Public feed contract v1

Executable validation: `scripts/discovery.py:validate`. All JSON is UTF-8 and parseable.
Every build must have exactly the deployment file allowlist in `FILES`.

Products and collections are objects containing schemaVersion=1, source and the corresponding
products/collections arrays. IDs are strings. Products require name, canonical URL, description,
category, datePublished and dateModified. Collections require exact governed name, canonical URL,
description, productCount and dateModified. Empty source collection descriptions remain empty;
the generator does not invent editorial copy or alter classification.

The Garage blog retains its top-level array and BlogPosting fields; additive title, URL, blog
and identity fields aid reconciliation. Dad-a-Pedia and blogcatalog are objects with articles arrays.
Articles require title, canonical URL, description, blog, datePublished and dateModified.
The blogcatalog URL set must equal the disjoint union of the Garage and Dad-a-Pedia URL sets.
A newly introduced blog blocks publication until its mapping is deliberately added.

FAQ records require question, answer and canonical source. Brand text comes from the public
Organization description. Brand voice comes from the exact public FAQ tone question.
A missing, ambiguous or changed structural source fails the build.

All copied prose is one line of printable ASCII after defined mechanical conversion:
straight quotes, hyphenated dash characters, ellipsis, trademark removal, accent decomposition
and whitespace normalization. Unsupported characters block publication for review.
Collection names are the sole exception and retain exact governed Unicode.
URLs use percent-encoding on the canonical www host. No source copy is rewritten in Shopify.

Product catalog and product sitemap URL sets must match exactly; no partial, private, preview,
unlisted or future-date export is allowed. Every emitted product, collection and article has
a successful public page fetch and matching canonical URL. Future publication dates fail validation.
The generator never reads Notion/Drive unpublished content.

Health data records generatedAt separately from sourceSnapshotStartedAt/sourceSnapshotFinishedAt.
Counts, source URLs and SHA-256 hashes identify the observed input set. Generation time alone
does not prove source freshness. A rebuild from the same captured inputs and same timestamp
must be byte-identical.

Prices, inventory and variant offers are intentionally omitted: live storefront pages own current
buying information. This feed does not represent a Merchant Center submission or acceptance.

