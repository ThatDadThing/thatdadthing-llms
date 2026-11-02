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

## Collection publication gate - November 2, 2026

Include a collection only when its paginated public membership has at least one product in the verified public catalog. Draft-only or empty collections are held. productCount equals the number of unique productIds, all of which must exist in products.json. Administrative totals are not publication evidence. health.json records examined/included/excludedEmpty counts without advertising held collection identities. A fully empty eligible collection set is valid and publishes no collection records. Existing Shopify collection publication settings are not changed.


## Approved product enrichment - November 2, 2026

products.json uses schemaVersion 2. Product description is the complete Commander-approved
Notion SEO Description, mechanically normalized with copy_text; it is never cut to 123 characters.
data/approved-products.json is the allowlisted approved editorial snapshot. It contains only
id, public URL, meta description, tones, audiences, approved image alt metadata and recommendationContext (recommendedFor,
interests). Notion remains the editing/review surface; an approved batch is imported to Git.
There is no credential-backed automatic Notion sync. Unapproved edits do not publish themselves.
The snapshot is not included in the Pages artifact. Its SHA-256 is recorded in health.json.

Every refresh starts with live public Shopify products. Editorial records cannot introduce
unpublished products; a matching ID with a changed URL blocks deployment for review. New
public products without approved enrichment use their live meta description and have no
invented audience or recommendation attributes. Removed products drop out on the next build.

Tags, images/alt text and Color/Size options come from the fresh public product catalog.
Options describe listed choices, not stock or guaranteed combinations. Product collections are
computed from the same eligible, nonempty public collections in collections.json, with their
current names and public URLs. Empty and unpublished collections remain excluded.
Nested labels use the same mechanical copy normalization; collection names retain Unicode.
Published/modified dates remain Shopify's dates, not dates invented for editorial approval.
health.json productEditorial records approvedMatched and approved snapshot sha256 separately.

The public product catalog omits alt text on some images. For a current public image URL,
use its public alt when available, otherwise the approved Notion alt for that exact URL.
An approved image absent from the fresh public product is never added to the output.
