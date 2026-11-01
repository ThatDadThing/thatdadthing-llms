"""Build supplementary discovery feeds exclusively from the public Shopify storefront."""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import os
import subprocess
import time
import unicodedata
from urllib.parse import urlsplit, urlunsplit, quote, unquote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

SITE = "https://www.thatdadthing.com"
FEEDS = "https://thatdadthing.github.io/thatdadthing-llms/"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
UA = "Mozilla/5.0 (compatible; TDTDiscovery/1.0; +https://www.thatdadthing.com/pages/ai-policy)"
FILES = ["products.json", "collections.json", "blog.json", "dadapedia.json",
         "blogcatalog.json", "faq.json", "brand.json", "brandvoice.json",
         "manifest.json", "ai-manifest.json", "health.json", "llms.txt",
         "ai.txt", "ai-sitemap.xml", "index.html"]
TRANSLATE = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2122": "", "\u00ae": "", "\u00a0": " "})

class Failure(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise Failure(message)

class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.canonical = None
        self.description = ""
        self.scripts = []
        self.script = None
        self.details = []
        self.detail = None
        self.detail_stack = []
        self.in_main = False
        self.summary = False
        self.ignored = 0
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "canonical" in a.get("rel", "").split():
            self.canonical = a.get("href")
        if tag == "meta" and a.get("name") == "description":
            self.description = a.get("content", "")
        if tag == "script" and a.get("type") == "application/ld+json":
            self.script = []
        if tag in ("script", "style"):
            self.ignored += 1
        if tag == "main":
            self.in_main = True
        if tag == "details" and self.in_main:
            self.detail_stack.append(self.detail)
            self.detail = {"question": [], "answer": []}
        if tag == "summary" and self.detail is not None:
            self.summary = True
        if tag in ("p", "br", "li", "div", "h1", "h2", "h3"):
            self.text.append(" ")
            if self.detail is not None and not self.summary:
                self.detail["answer"].append(" ")

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append("".join(self.script))
            self.script = None
        if tag in ("script", "style"):
            self.ignored = max(0, self.ignored - 1)
        if tag == "summary":
            self.summary = False
        if tag == "details" and self.detail is not None:
            self.details.append({k: "".join(v) for k, v in self.detail.items()})
            self.detail = self.detail_stack.pop() if self.detail_stack else None
        if tag == "main":
            self.in_main = False
        if tag in ("p", "li", "div", "h1", "h2", "h3"):
            self.text.append(" ")

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if not self.ignored:
            self.text.append(data)
            if self.detail is not None:
                self.detail["question" if self.summary else "answer"].append(data)

def copy_text(value):
    text = " ".join(Document(html.unescape(value or "")).text)
    text = unicodedata.normalize("NFKD", text.translate(TRANSLATE))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    require(all(32 <= ord(c) <= 126 for c in text),
            "Unsupported non-ASCII source copy requires review: " + repr(text[:140]))
    return text

def canonical(url):
    p = urlsplit(url)
    require(p.scheme == "https" and p.hostname in ("www.thatdadthing.com", "thatdadthing.com"),
            "Unexpected source host: " + url)
    require(not p.query and not p.fragment, "Unexpected source query/fragment: " + url)
    return SITE + quote(unquote(p.path), safe="/-._~")

def timestamp(value):
    require(bool(value), "Missing source timestamp")
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)

def walk_entities(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_entities(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_entities(child)

class Source:
    def __init__(self, cache, offline=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.lineage = {}
        self.captured = {}

    def get(self, url):
        p = urlsplit(url)
        require(p.scheme == "https" and p.hostname == "www.thatdadthing.com",
                "Refusing non-storefront fetch: " + url)
        path = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".txt")
        if self.offline:
            require(path.exists(), "Offline fixture missing: " + url)
            text = path.read_text(encoding="utf-8")
        else:
            for attempt in range(3):
                try:
                    if os.name == "nt":
                        # Use Windows certificate trust through .NET; never disable TLS validation.
                        env = dict(os.environ, TDT_SOURCE_URL=url, TDT_SOURCE_UA=UA)
                        command = ("$ErrorActionPreference='Stop'; "
                            "$r=Invoke-WebRequest -Uri $env:TDT_SOURCE_URL -UserAgent $env:TDT_SOURCE_UA -TimeoutSec 30; "
                            "@{url=$r.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;content=$r.Content}|ConvertTo-Json -Compress")
                        proc = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=45, check=True)
                        result = json.loads(proc.stdout)
                        require(urlsplit(result["url"]).hostname == p.hostname, "Cross-host redirect")
                        text = result["content"]
                    else:
                        with urlopen(Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                            require(r.status == 200, "Source did not return 200: " + url)
                            require(urlsplit(r.url).hostname == p.hostname, "Cross-host redirect")
                            text = r.read().decode("utf-8")
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            path.write_text(text, encoding="utf-8")
        self.lineage[url] = hashlib.sha256(text.encode()).hexdigest()
        self.captured[url] = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()
        return text

def inventory(source):
    pending = [SITE + "/sitemap.xml"]
    seen = set()
    urls = {}
    while pending:
        url = pending.pop()
        require(url not in seen, "Duplicate/cyclic sitemap: " + url)
        seen.add(url)
        root = ET.fromstring(source.get(url))
        if root.tag.endswith("sitemapindex"):
            pending.extend(n.text for n in root.findall("s:sitemap/s:loc", NS))
        else:
            require(root.tag.endswith("urlset"), "Unexpected sitemap document")
            for node in root.findall("s:url", NS):
                loc = node.findtext("s:loc", namespaces=NS)
                url = canonical(loc)
                require(url not in urls, "Duplicate sitemap URL: " + url)
                urls[url] = node.findtext("s:lastmod", namespaces=NS)
    for section in ("/products/", "/collections/", "/blogs/"):
        require(any(section in u for u in urls), "Empty source section: " + section)
    return urls

def public_products(source, sitemap):
    records = {}
    for page in range(1, 101):
        payload = json.loads(source.get(SITE + "/products.json?limit=250&page=" + str(page)))
        require(isinstance(payload.get("products"), list), "Invalid public product response")
        batch = payload["products"]
        for p in batch:
            url = canonical(SITE + "/products/" + p["handle"])
            require(url not in records, "Duplicate public product: " + url)
            records[url] = p
        if len(batch) < 250:
            break
    else:
        raise Failure("Product pagination exceeded safety limit")
    expected = {u for u in sitemap if urlsplit(u).path.startswith("/products/")}
    require(expected == set(records), "Product sitemap/catalog mismatch; refuse partial or unlisted export")
    return records

def article_record(url, doc, lastmod, now):
    articles = []
    for script in doc.scripts:
        try:
            value = json.loads(script)
        except json.JSONDecodeError as exc:
            raise Failure("Invalid source JSON-LD: " + url) from exc
        for e in walk_entities(value):
            kind = e.get("@type", [])
            kind = [kind] if isinstance(kind, str) else kind
            if any(k in ("Article", "BlogPosting") for k in kind):
                articles.append(e)
    require(len(articles) == 1, "Expected one source Article: " + url)
    e = articles[0]
    published = e.get("datePublished")
    require(timestamp(published) <= now, "Future article in public source: " + url)
    entity_url = e.get("mainEntityOfPage", {})
    entity_url = entity_url.get("@id") if isinstance(entity_url, dict) else entity_url
    require(canonical(entity_url) == url, "Article identity mismatch: " + url)
    description = copy_text(doc.description or e.get("description") or "")
    require(bool(description), "Missing article description: " + url)
    return {"id": url, "title": copy_text(e["headline"]), "url": url,
            "description": description, "blog": urlsplit(url).path.split("/")[2],
            "datePublished": published, "dateModified": e.get("dateModified") or lastmod or published}

def build(source, as_of):
    now = timestamp(as_of)
    sitemap = inventory(source)
    product_data = public_products(source, sitemap)
    article_urls = sorted(u for u in sitemap if re.match(r"^/blogs/[^/]+/[^/]+$", urlsplit(u).path))
    collection_urls = sorted(u for u in sitemap if urlsplit(u).path.startswith("/collections/"))
    page_urls = sorted(set(product_data) | set(article_urls) |
                       {SITE, SITE + "/pages/faq", SITE + "/pages/ai-txt"} | set(collection_urls))
    def fetch_page(url):
        d = Document(source.get(url))
        require(d.canonical and canonical(d.canonical).rstrip("/") == url.rstrip("/"),
                "Canonical mismatch: " + url)
        return url, d
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        docs = dict(pool.map(fetch_page, page_urls))
    products = []
    for url, p in sorted(product_data.items()):
        require(timestamp(p.get("published_at")) <= now, "Future product: " + url)
        products.append({"id": str(p["id"]), "name": copy_text(p["title"]), "url": url,
            "description": copy_text(p.get("body_html")),
            "category": copy_text(p.get("product_type")),
            "datePublished": p["published_at"], "dateModified": p["updated_at"]})
    collections = []
    for url in collection_urls:
        p = json.loads(source.get(url + ".json"))["collection"]
        require(canonical(SITE + "/collections/" + p["handle"]) == url, "Collection identity mismatch")
        require(timestamp(p.get("published_at")) <= now, "Future collection")
        collections.append({"id": str(p["id"]), "name": " ".join(p["title"].split()), "url": url,
            "description": copy_text(p.get("description")), "productCount": p["products_count"],
            "dateModified": p["updated_at"]})
    articles = [article_record(u, docs[u], sitemap[u], now) for u in article_urls]
    faq = [{"question": copy_text(x["question"]), "answer": copy_text(x["answer"]),
            "source": SITE + "/pages/faq"} for x in docs[SITE + "/pages/faq"].details]
    require(len(faq) >= 1 and all(x["question"] and x["answer"] for x in faq), "No complete FAQ source")
    orgs = []
    for raw in docs[SITE].scripts:
        for e in walk_entities(json.loads(raw)):
            if e.get("@type") == "Organization" and e.get("description"):
                orgs.append(e)
    require(len(orgs) == 1, "Ambiguous source brand")
    org = orgs[0]
    brand = {"name": copy_text(org["name"]), "url": SITE,
             "description": copy_text(org["description"]), "slogan": copy_text(org.get("slogan")),
             "source": SITE}
    tone = [f for f in faq if f["question"] == "What is That Dad Thing's tone?"]
    require(len(tone) == 1, "Brand voice source question changed; review required")
    # Retain the existing public no-training preference; do not infer permission from crawling.
    require("Train: disallow" in source.get(SITE + "/pages/ai-txt"), "AI training preference changed; review required")
    def envelope(key, rows):
        return {"schemaVersion": 1, "source": SITE, key: rows}
    bundle = {
        "products.json": envelope("products", products),
        "collections.json": envelope("collections", collections),
        "blog.json": [dict(a, **{"@context": "https://schema.org", "@type": "BlogPosting",
            "headline": a["title"], "mainEntityOfPage": {"@type": "WebPage", "@id": a["url"]}})
            for a in articles if a["blog"] == "the-garage"],
        "dadapedia.json": envelope("articles", [a for a in articles if a["blog"] == "dad-a-pedia"]),
        "blogcatalog.json": envelope("articles", articles),
        "faq.json": envelope("faqs", faq),
        "brand.json": {"schemaVersion": 1, "brand": brand},
        "brandvoice.json": {"schemaVersion": 1, "source": SITE + "/pages/faq", "description": tone[0]["answer"]},
    }
    feed_names = list(bundle)
    manifest = {"schemaVersion": 1, "name": "That Dad Thing AI Feed Directory",
        "url": SITE, "repository": "https://github.com/ThatDadThing/thatdadthing-llms",
        "description": "Supplementary public catalog and brand context. Prefer current storefront pages for purchases.",
        "feeds": [{"name": f.removesuffix(".json"), "url": FEEDS + f, "type": "application/json"} for f in feed_names] +
                 [{"name": f, "url": FEEDS + f, "type": t} for f, t in
                  [("llms.txt", "text/plain"), ("ai.txt", "text/plain"), ("ai-sitemap.xml", "application/xml"),
                   ("health.json", "application/json")]]}
    bundle["manifest.json"] = manifest
    bundle["ai-manifest.json"] = manifest
    source_digest = hashlib.sha256(json.dumps(source.lineage, sort_keys=True).encode()).hexdigest()
    counts = {"products": len(products), "collections": len(collections), "articles": len(articles),
              "garageArticles": len(bundle["blog.json"]),
              "dadapediaArticles": len(bundle["dadapedia.json"]["articles"]), "faqs": len(faq)}
    bundle["health.json"] = {"schemaVersion": 1, "generatedAt": as_of, "sourceFingerprint": source_digest,
        "sourceSnapshotStartedAt": min(getattr(source, "captured", {}).values(), default=as_of),
        "sourceSnapshotFinishedAt": max(getattr(source, "captured", {}).values(), default=as_of),
        "counts": counts, "coverage": "Exact product and article sitemap reconciliation",
        "sourceURLs": dict(sorted(source.lineage.items()))}
    bundle["llms.txt"] = (
        "# That Dad Thing\n\n> " + brand["description"] + "\n\n"
        "Official storefront: " + SITE + "\nFAQ: " + SITE + "/pages/faq\n"
        "Dad-a-Pedia: " + SITE + "/blogs/dad-a-pedia\n"
        "Manifest: " + FEEDS + "manifest.json\nFeed health: " + FEEDS + "health.json\n\n"
        "These feeds supplement public storefront pages. Verify current price, availability, policies and details "
        "on the relevant live page. No feed guarantees indexing, AI retrieval or citation.\n"
    )
    bundle["ai.txt"] = (
        "# That Dad Thing AI access and citation policy\n\n"
        "Public content may be read for search indexing, answer generation, citation and product discovery.\n"
        "Existing model-training preference: disallow. Source: " + SITE + "/pages/ai-txt\n"
        "These preferences are not a universal technical or legal enforcement mechanism.\n"
        "Prefer canonical storefront pages when citing products, collections, FAQs and articles.\n"
        "Do not reproduce artwork, designs, slogans or original copy as reusable creative assets.\n"
        "Do not imply an endorsement or partnership. Check live policies, prices and availability.\n"
    )
    urls = [FEEDS + f for f in FILES if f != "index.html"]
    bundle["ai-sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join("  <url><loc>" + html.escape(u) + "</loc></url>\n" for u in urls) + "</urlset>\n")
    bundle["index.html"] = ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<title>That Dad Thing public discovery feeds</title><h1>That Dad Thing public discovery feeds</h1>'
        '<p>Supplementary catalog. Use the storefront for current buying information.</p><ul>' +
        "".join('<li><a href="' + f + '">' + f + "</a></li>" for f in FILES if f != "index.html") +
        '</ul><a href="' + SITE + '">Visit That Dad Thing</a></html>\n')
    bundle["health.json"]["fileHashes"] = {k: hashlib.sha256(encode(v).encode("utf-8")).hexdigest()
        for k, v in bundle.items() if k != "health.json"}
    validate(bundle)
    return bundle

def validate(bundle):
    require(set(bundle) == set(FILES), "Unexpected deployment file set")
    for filename, key in [("products.json", "products"), ("collections.json", "collections"),
                          ("blog.json", "articles"), ("dadapedia.json", "articles"),
                          ("blogcatalog.json", "articles"), ("faq.json", "faqs")]:
        rows = bundle[filename] if filename == "blog.json" else bundle[filename][key]
        require(isinstance(rows, list), "Expected list: " + filename)
        ids = [r.get("url", r.get("question")) for r in rows]
        require(len(ids) == len(set(ids)), "Duplicate feed identities: " + filename)
        for row in rows:
            required = ["question", "answer", "source"] if key == "faqs" else ["url", "description"]
            required += ["name"] if key in ("products", "collections") else (["title"] if key == "articles" else [])
            require(all(k in row and isinstance(row[k], str) for k in required), "Record contract failure")
            if key != "faqs":
                require(canonical(row["url"]) == row["url"], "Noncanonical output URL")
            for k, value in row.items():
                if isinstance(value, str) and not (filename == "collections.json" and k == "name"):
                    require(all(32 <= ord(c) <= 126 for c in value), "Non-ASCII or multiline field: " + filename + "/" + k)
    require(bundle["ai-manifest.json"] == bundle["manifest.json"], "Manifest aliases disagree")
    article_urls = lambda f: {r["url"] for r in (bundle[f] if f == "blog.json" else bundle[f]["articles"])}
    require(article_urls("blog.json").isdisjoint(article_urls("dadapedia.json")), "Article partition overlap")
    require(article_urls("blogcatalog.json") == article_urls("blog.json") | article_urls("dadapedia.json"),
            "Unmapped blog source; add explicit blog partition")
    for feed in bundle["manifest.json"]["feeds"]:
        require(feed["url"].startswith(FEEDS) and feed["url"][len(FEEDS):] in bundle, "Broken manifest reference")
    actual = {"products": len(bundle["products.json"]["products"]),
              "collections": len(bundle["collections.json"]["collections"]),
              "articles": len(bundle["blogcatalog.json"]["articles"]),
              "garageArticles": len(bundle["blog.json"]),
              "dadapediaArticles": len(bundle["dadapedia.json"]["articles"]),
              "faqs": len(bundle["faq.json"]["faqs"])}
    require(bundle["health.json"]["counts"] == actual, "Coverage counts disagree")
    for name in ("products", "collections", "articles", "faqs"):
        require(actual[name] > 0, "Empty core feed")
    ET.fromstring(bundle["ai-sitemap.xml"])

def encode(value):
    return value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n"

def write_bundle(bundle, output):
    validate(bundle)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (output / name).write_text(encode(bundle[name]), encoding="utf-8", newline="\n")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--as-of", default=dt.datetime.now(dt.timezone.utc).isoformat())
    args = parser.parse_args()
    bundle = build(Source(args.cache, args.offline), args.as_of)
    write_bundle(bundle, args.output)
    print(json.dumps(bundle["health.json"]["counts"], sort_keys=True))

if __name__ == "__main__":
    main()

