import copy
import datetime as dt
import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import discovery as d

ASOF = "2026-11-01T12:00:00+00:00"
P = d.SITE + "/products/test-shirt"
C = d.SITE + "/collections/test"
A = d.SITE + "/blogs/dad-a-pedia/test"
B = d.SITE + "/blogs/the-garage/test"

def document(url, body=""):
    return '<html><head><link rel="canonical" href="' + url + '"><meta name="description" content="Public summary"></head><body><main>' + body + '</main></body></html>'

def article(url):
    entity = {"@context": "https://schema.org", "@type": "Article", "headline": "Test article",
              "mainEntityOfPage": {"@id": url}, "datePublished": "2026-10-01T00:00:00Z"}
    return document(url, '<script type="application/ld+json">' + json.dumps(entity) + '</script>')

class Fixture:
    def __init__(self):
        self.lineage = {}
        urls = [P, C, A, B, d.SITE + "/pages/faq"]
        self.values = {d.SITE + "/sitemap.xml":
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            "".join("<url><loc>" + u + "</loc></url>" for u in urls) + "</urlset>",
            d.SITE + "/products.json?limit=250&page=1": json.dumps({"products": [
                {"id": 1, "title": "Test shirt", "handle": "test-shirt", "body_html": "<p>Published copy</p>",
                 "published_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z"}]}),
            P: document(P), C: document(C), A: article(A), B: article(B),
            C + "/products.json?limit=250&page=1": json.dumps({"products": [{"id": 1}]}),
            C + ".json": json.dumps({"collection": {"id": 2, "title": "Test collection", "handle": "test",
                 "description": "", "products_count": 1, "published_at": "2026-10-01T00:00:00Z",
                 "updated_at": "2026-10-02T00:00:00Z"}}),
            d.SITE: document(d.SITE, '<script type="application/ld+json">' +
                json.dumps({"@type": "Organization", "name": "That Dad Thing", "description": "Public brand"}) + "</script>"),
            d.SITE + "/pages/faq": document(d.SITE + "/pages/faq",
                "<details><summary>What is That Dad Thing's tone?</summary><p>Warm and funny.</p></details>"),
            d.SITE + "/pages/ai-txt": document(d.SITE + "/pages/ai-txt", "<pre>Train: disallow</pre>")}
    def get(self, url):
        value = self.values[url]
        self.lineage[url] = hashlib.sha256(value.encode()).hexdigest()
        return value

class Tests(unittest.TestCase):
    def test_public_coverage_and_determinism(self):
        first = d.build(Fixture(), ASOF)
        self.assertEqual(first, d.build(Fixture(), ASOF))
        self.assertEqual(first["health.json"]["counts"],
            dict(products=1, collections=1, articles=2, garageArticles=1, dadapediaArticles=1, faqs=1))
        self.assertEqual(first["ai-manifest.json"], first["manifest.json"])

    def test_empty_collection_is_held(self):
        f = Fixture()
        f.values[C + "/products.json?limit=250&page=1"] = '{"products":[]}'
        bundle = d.build(f, ASOF)
        self.assertEqual(bundle["collections.json"]["collections"], [])
        self.assertEqual(bundle["health.json"]["collectionEligibility"],
                         {"examined": 1, "included": 0, "excludedEmpty": 1})

    def test_admin_total_without_public_members_cannot_qualify(self):
        f = Fixture()
        data = json.loads(f.values[C + ".json"])
        data["collection"]["products_count"] = 100
        f.values[C + ".json"] = json.dumps(data)
        f.values[C + "/products.json?limit=250&page=1"] = '{"products":[]}'
        self.assertEqual(d.build(f, ASOF)["collections.json"]["collections"], [])

    def test_collection_count_uses_public_membership(self):
        f = Fixture()
        data = json.loads(f.values[C + ".json"])
        data["collection"]["products_count"] = 100
        f.values[C + ".json"] = json.dumps(data)
        row = d.build(f, ASOF)["collections.json"]["collections"][0]
        self.assertEqual(row["productCount"], 1)
        self.assertEqual(row["productIds"], ["1"])

    def test_unpublished_collection_member_fails_closed(self):
        f = Fixture()
        f.values[C + "/products.json?limit=250&page=1"] = '{"products":[{"id":999}]}'
        with self.assertRaisesRegex(d.Failure, "missing from public catalog"):
            d.build(f, ASOF)

    def test_empty_collection_cannot_be_injected_after_generation(self):
        bundle = d.build(Fixture(), ASOF)
        row = bundle["collections.json"]["collections"][0]
        row["productIds"], row["productCount"] = [], 0
        with self.assertRaisesRegex(d.Failure, "Empty collection"):
            d.validate(bundle)

    def test_collection_count_must_match_member_ids(self):
        bundle = d.build(Fixture(), ASOF)
        bundle["collections.json"]["collections"][0]["productCount"] = 999
        with self.assertRaisesRegex(d.Failure, "count disagrees"):
            d.validate(bundle)

    def test_rate_limit_backoff_respects_retry_after(self):
        from urllib.error import HTTPError
        self.assertEqual(d.retry_delay(HTTPError(d.SITE,429,"limited",{"Retry-After":"45"},None)),45)

    def test_rate_limit_backoff_defaults_conservatively(self):
        from urllib.error import HTTPError
        self.assertEqual(d.retry_delay(HTTPError(d.SITE,429,"limited",{},None)),30)

    def test_long_rate_limit_interval_stops_build(self):
        from urllib.error import HTTPError
        with self.assertRaisesRegex(d.Failure, "retry this build later"):
            d.retry_delay(HTTPError(d.SITE,429,"limited",{"Retry-After":"300"},None))

    def test_unlisted_product_cannot_enter_feed(self):
        f = Fixture()
        key = d.SITE + "/products.json?limit=250&page=1"
        p = json.loads(f.values[key])
        p["products"].append(dict(p["products"][0], id=9, handle="unlisted"))
        f.values[key] = json.dumps(p)
        with self.assertRaisesRegex(d.Failure, "mismatch"):
            d.build(f, ASOF)

    def test_future_product_rejected(self):
        f = Fixture()
        key = d.SITE + "/products.json?limit=250&page=1"
        p = json.loads(f.values[key])
        p["products"][0]["published_at"] = "2027-01-01T00:00:00Z"
        f.values[key] = json.dumps(p)
        with self.assertRaisesRegex(d.Failure, "Future product"):
            d.build(f, ASOF)

    def test_future_article_rejected(self):
        f = Fixture()
        f.values[A] = f.values[A].replace("2026-10-01", "2027-01-01")
        with self.assertRaisesRegex(d.Failure, "Future article"):
            d.build(f, ASOF)

    def test_wrong_canonical_rejected(self):
        f = Fixture()
        f.values[P] = document(d.SITE + "/products/wrong")
        with self.assertRaisesRegex(d.Failure, "Canonical mismatch"):
            d.build(f, ASOF)

    def test_missing_source_record_rejected(self):
        f = Fixture()
        f.values[d.SITE + "/products.json?limit=250&page=1"] = '{"products":[]}'
        with self.assertRaisesRegex(d.Failure, "mismatch"):
            d.build(f, ASOF)

    def test_source_failure_does_not_write_bundle(self):
        f = Fixture()
        del f.values[A]
        with self.assertRaises(KeyError):
            d.build(f, ASOF)

    def test_malformed_article_jsonld_rejected(self):
        f = Fixture()
        f.values[A] = document(A, '<script type="application/ld+json">{bad</script>')
        with self.assertRaisesRegex(d.Failure, "Invalid source JSON-LD"):
            d.build(f, ASOF)

    def test_training_preference_change_blocks_build(self):
        f = Fixture()
        f.values[d.SITE + "/pages/ai-txt"] = document(d.SITE + "/pages/ai-txt", "Train: allow")
        with self.assertRaisesRegex(d.Failure, "training preference"):
            d.build(f, ASOF)

    def test_faq_excludes_header_and_scripts(self):
        text = '<header><details><summary>Navigation</summary>Private</details></header>'
        text += '<main><details><summary>Question?</summary><p>Answer.</p><script>bad</script></details></main>'
        self.assertEqual(d.Document(text).details, [{"question": "Question?", "answer": " Answer."}])

    def test_ascii_normalization(self):
        self.assertEqual(d.copy_text("Dad\u2019s &amp; Dad\u2122\n\u2014 good"), "Dad's & Dad - good")
        with self.assertRaises(d.Failure):
            d.copy_text("Unapproved \U0001f680 copy")

    def test_unexpected_blog_requires_mapping(self):
        f = Fixture()
        new = d.SITE + "/blogs/new-blog/test"
        f.values[d.SITE + "/sitemap.xml"] = f.values[d.SITE + "/sitemap.xml"].replace(A, new)
        f.values[new] = article(new)
        with self.assertRaisesRegex(d.Failure, "Unmapped blog"):
            d.build(f, ASOF)

    def test_duplicate_identity_rejected(self):
        bundle = d.build(Fixture(), ASOF)
        bundle["products.json"]["products"] *= 2
        with self.assertRaisesRegex(d.Failure, "Duplicate"):
            d.validate(bundle)

    def test_cross_host_source_rejected(self):
        self.assertRaises(d.Failure, d.canonical, "https://example.com/products/test")

    def test_preview_query_rejected(self):
        self.assertRaises(d.Failure, d.canonical, P + "?preview_theme_id=123")

    def test_deployment_allowlist(self):
        bundle = d.build(Fixture(), ASOF)
        bundle["private.json"] = {}
        self.assertRaises(d.Failure, d.validate, bundle)



    def test_public_update_and_removal_propagate(self):
        f = Fixture()
        before = d.build(f, ASOF)
        key = d.SITE + "/products.json?limit=250&page=1"
        payload = json.loads(f.values[key])
        payload["products"][0]["body_html"] = "<p>Approved public update</p>"
        f.values[key] = json.dumps(payload)
        f.values[P] = document(P).replace("Public summary", "Approved public update")
        updated = d.build(f, ASOF)
        self.assertEqual(updated["products.json"]["products"][0]["description"], "Approved public update")
        self.assertNotEqual(before["health.json"]["sourceFingerprint"], updated["health.json"]["sourceFingerprint"])
        # Public removal must remove the record from both publication surfaces.
        f.values[d.SITE + "/sitemap.xml"] = f.values[d.SITE + "/sitemap.xml"].replace("<url><loc>" + B + "</loc></url>", "")
        removed = d.build(f, ASOF)
        self.assertEqual(removed["blog.json"], [])
        self.assertEqual(removed["health.json"]["counts"]["articles"], 1)

    def test_coverage_count_tampering_rejected(self):
        bundle = d.build(Fixture(), ASOF)
        bundle["health.json"]["counts"]["products"] = 999
        with self.assertRaisesRegex(d.Failure, "Coverage counts"):
            d.validate(bundle)


class HealthTests(unittest.TestCase):
    def setUp(self):
        import check_health
        self.h = check_health
        self.bundle = d.build(Fixture(), dt.datetime.now(dt.timezone.utc).isoformat())
        self.payload = {d.FEEDS + k: d.encode(v).encode("utf-8") for k, v in self.bundle.items()}
    def test_valid_publication(self):
        from unittest.mock import patch
        with patch.object(self.h, "fetch", side_effect=lambda u: self.payload[u]):
            self.assertEqual(self.h.check()["counts"]["products"], 1)
    def test_stale_source_not_hidden_by_new_build_time(self):
        from unittest.mock import patch
        self.bundle["health.json"]["sourceSnapshotStartedAt"] = "2020-01-01T00:00:00Z"
        self.payload[d.FEEDS + "health.json"] = d.encode(self.bundle["health.json"]).encode()
        with patch.object(self.h, "fetch", side_effect=lambda u: self.payload[u]):
            with self.assertRaisesRegex(d.Failure, "Source snapshot is stale"):
                self.h.check()
    def test_corrupt_published_file(self):
        from unittest.mock import patch
        self.payload[d.FEEDS + "products.json"] = b'{"products":[]}'
        with patch.object(self.h, "fetch", side_effect=lambda u: self.payload[u]):
            with self.assertRaisesRegex(d.Failure, "hash mismatch"):
                self.h.check()
    def test_first_deployment_needs_explicit_bootstrap(self):
        import tempfile
        from unittest.mock import patch
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as tmp:
            d.write_bundle(self.bundle, tmp)
            with patch.object(self.h, "fetch", side_effect=HTTPError(d.FEEDS,404,"missing",{},None)):
                self.assertRaises(d.Failure,self.h.baseline,tmp)
                self.h.baseline(tmp,True)
    def test_large_count_drop_blocks_deployment(self):
        import tempfile
        from unittest.mock import patch
        previous = copy.deepcopy(self.bundle["health.json"])
        previous["counts"]["products"] = 100
        with tempfile.TemporaryDirectory() as tmp:
            d.write_bundle(self.bundle, tmp)
            with patch.object(self.h, "fetch", return_value=json.dumps(previous).encode()):
                with self.assertRaisesRegex(d.Failure, "Large source-count drop"):
                    self.h.baseline(tmp)

if __name__ == "__main__":
    unittest.main()


class EnrichmentTests(unittest.TestCase):
    def approved(self):
        return {"1": {"id": "1", "url": P, "images": [], "description": "Approved meta description",
                       "tones": ["Dry Snark"], "audiences": ["Adult"],
                       "recommendationContext": {"recommendedFor": "Dads who like science", "interests": ["science"]}}}

    def test_editorial_survives_refresh_and_live_options_win(self):
        f = Fixture()
        key = d.SITE + "/products.json?limit=250&page=1"
        data = json.loads(f.values[key])
        data["products"][0].update(tags=["science"], options=[{"name": "Color", "values": ["Moss"]}],
                                  images=[{"src": "https://cdn.shopify.com/test_image.webp", "alt": "Science shirt"}])
        f.values[key] = json.dumps(data)
        row = d.build(f, ASOF, self.approved())["products.json"]["products"][0]
        self.assertEqual(row["description"], "Approved meta description")
        self.assertEqual(row["options"][0]["values"], ["Moss"])
        self.assertEqual(row["images"][0]["url"], "https://cdn.shopify.com/test_image.webp")
        self.assertEqual(row["recommendationContext"]["interests"], ["science"])
        self.assertEqual(row["collections"][0]["url"], C)

    def test_editorial_cannot_add_private_product(self):
        editorial = self.approved()
        editorial["private"] = dict(editorial["1"], id="private", url=d.SITE + "/products/private")
        bundle = d.build(Fixture(), ASOF, editorial)
        self.assertEqual([p["id"] for p in bundle["products.json"]["products"]], ["1"])
        self.assertEqual(bundle["health.json"]["productEditorial"]["approvedMatched"], 1)

    def test_editorial_identity_drift_blocks_release(self):
        editorial = self.approved()
        editorial["1"]["url"] = d.SITE + "/products/wrong"
        with self.assertRaisesRegex(d.Failure, "editorial URL mismatch"):
            d.build(Fixture(), ASOF, editorial)

    def test_unreviewed_product_uses_public_meta_without_invented_editorial(self):
        row = d.build(Fixture(), ASOF)["products.json"]["products"][0]
        self.assertEqual(row["description"], "Public summary")
        self.assertNotIn("recommendationContext", row)

    def test_approved_data_rejects_duplicate_ids(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "approved.json"
            row = self.approved()["1"]
            path.write_text(json.dumps({"schemaVersion": 1, "products": [row, row]}))
            with self.assertRaisesRegex(d.Failure, "Duplicate editorial"):
                d.load_editorial(path)


    def test_approved_alt_only_follows_a_matching_live_image(self):
        f = Fixture()
        key = d.SITE + "/products.json?limit=250&page=1"
        data = json.loads(f.values[key])
        data["products"][0]["images"] = [{"src": "https://cdn.shopify.com/live.webp"}]
        f.values[key] = json.dumps(data)
        editorial = self.approved()
        editorial["1"]["images"] = [{"url": "https://cdn.shopify.com/live.webp", "alt": "Approved science design"},
                                     {"url": "https://cdn.shopify.com/removed.webp", "alt": "Removed image"}]
        row = d.build(f, ASOF, editorial)["products.json"]["products"][0]
        self.assertEqual(row["images"], [{"url": "https://cdn.shopify.com/live.webp", "alt": "Approved science design"}])


class ArticlePublicationDateTests(unittest.TestCase):
    def rendered(self, dates, extra=""):
        header = "<article><header>" + "".join(
            '<time datetime="' + value + '">Publication date</time>' for value in dates
        ) + "</header>" + extra + "</article>"
        return d.Document(article(A).replace("</main>", header + "</main>"))

    def test_visible_publication_date_wins_over_creation_date(self):
        doc = self.rendered(["2026-10-29T12:00:05Z"])
        row = d.article_record(A, doc, None, d.timestamp(ASOF))
        self.assertEqual(row["datePublished"], "2026-10-29T12:00:05Z")

    def test_unrelated_time_outside_article_header_is_ignored(self):
        doc = self.rendered([], '<time datetime="2026-10-29T12:00:05Z">Related item</time>')
        row = d.article_record(A, doc, None, d.timestamp(ASOF))
        self.assertEqual(row["datePublished"], "2026-10-01T00:00:00Z")

    def test_ambiguous_header_dates_fail_closed(self):
        doc = self.rendered(["2026-10-29T12:00:05Z", "2026-10-30T12:00:05Z"])
        with self.assertRaisesRegex(d.Failure, "Ambiguous rendered"):
            d.article_record(A, doc, None, d.timestamp(ASOF))

    def test_future_visible_publication_fails_closed(self):
        doc = self.rendered(["2026-11-03T12:00:05Z"])
        with self.assertRaisesRegex(d.Failure, "Future article"):
            d.article_record(A, doc, None, d.timestamp(ASOF))
