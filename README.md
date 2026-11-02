# That Dad Thing public discovery feeds

Owner: JSON Jargon. The Shopify storefront owns published product, collection, article,
FAQ and brand facts. GitHub owns this generator, its data contracts and validation.

The feeds supplement normal storefront pages and structured data. They are not a
guarantee of indexing, AI retrieval, recommendation eligibility or citation.

## Rebuild

Python 3.13+ and the standard library are sufficient on Linux. On Windows, PowerShell 7
provides HTTPS through Windows certificate trust; certificate verification stays enabled.

```text
python -m unittest discover -s tests -v
python scripts/discovery.py --output build/site --cache build/public-cache
python scripts/discovery.py --output build/replay --cache build/public-cache --offline --as-of TIMESTAMP_FROM_HEALTH_JSON
```

Only `build/site` is a deployment artifact. No credentials, Notion drafts, Drive artwork,
private inventory or repository internals enter it. Root feed files are reviewed snapshots;
the publishing workflow rebuilds them from live public sources before every deployment.
An offline rebuild uses captured inputs; source capture times remain distinct from build time.

## Sources and outputs

- Shopify product sitemap reconciled exactly with the paginated public product catalog.
- Collection sitemap, canonical checks and paginated public product membership; empty/draft-only collections are held.
- Article sitemap plus page Article/BlogPosting JSON-LD, canonical URLs and public descriptions.
- Public FAQ details/summary blocks; public homepage brand description; FAQ tone answer.
- Existing public training preference is preserved. No robots, privacy or channel settings change.

`manifest.json` and `ai-manifest.json` are identical directories.
`products.json`, `collections.json`, `faq.json`, `brand.json` and `brandvoice.json` describe
public source facts. `blog.json` retains its existing top-level BlogPosting array for The Garage.
`dadapedia.json` contains Dad-a-Pedia posts, including the public start/submission utilities.
`blogcatalog.json` contains every published article in the two current blogs.
`health.json` records capture/build timestamps, source hashes and coverage counts.
`llms.txt`, `ai.txt` and `ai-sitemap.xml` provide supporting discovery navigation.

Press/review feeds have no verified source and are not fabricated. The separate theme patch
removes their advertisements. Existing unadvertised empty social files are retained in Git
as historical files and are not part of the new deployment artifact.

See [data contract](docs/DATA_CONTRACT.md), [operations](docs/OPERATIONS.md) and
[change log](CHANGELOG.md). Implementation is staged; deployment needs approval.
