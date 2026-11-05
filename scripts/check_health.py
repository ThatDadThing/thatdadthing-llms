"""Check deployed supplementary feeds and detect stale or mismatched publication."""
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import discovery as d

def fetch(url):
    d.require(url.startswith(d.FEEDS), "Unexpected feed host")
    if os.name == "nt":
        env = dict(os.environ, TDT_SOURCE_URL=url, TDT_SOURCE_UA=d.UA)
        command = ("$ErrorActionPreference='Stop'; "
            "$r=Invoke-WebRequest -Uri $env:TDT_SOURCE_URL -UserAgent $env:TDT_SOURCE_UA -TimeoutSec 30 -SkipHttpErrorCheck; "
            "@{url=$r.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;status=[int]$r.StatusCode;content=$r.Content}|ConvertTo-Json -Compress")
        proc = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=45, check=True)
        result = json.loads(proc.stdout)
        if result["status"] != 200:
            raise HTTPError(url, result["status"], "Feed request failed", {}, None)
        d.require(result["url"].startswith(d.FEEDS), "Unexpected feed redirect")
        return result["content"].encode("utf-8")
    with urlopen(Request(url, headers={"User-Agent": d.UA}), timeout=30) as r:
        d.require(r.status == 200 and r.url.startswith(d.FEEDS), "Unexpected feed response")
        return r.read()

def check(max_age_hours=36, expected=None):
    health = json.loads(fetch(d.FEEDS + "health.json"))
    age = (dt.datetime.now(dt.timezone.utc) - d.timestamp(health["generatedAt"])).total_seconds() / 3600
    d.require(-0.1 <= age <= max_age_hours, "Feed build is stale or dated in the future")
    source_age = (dt.datetime.now(dt.timezone.utc) - d.timestamp(health["sourceSnapshotStartedAt"])).total_seconds() / 3600
    d.require(-0.1 <= source_age <= max_age_hours, "Source snapshot is stale")
    d.require(set(health["fileHashes"]) == set(d.FILES) - {"health.json"}, "Unexpected health file set")
    manifest = json.loads(fetch(d.FEEDS + "manifest.json"))
    urls = {f["url"] for f in manifest["feeds"]} | {d.FEEDS + f for f in health["fileHashes"]}
    bundle = {"health.json": health}
    for url in sorted(urls):
        name = url.removeprefix(d.FEEDS)
        d.require(name in d.FILES and url == d.FEEDS + name, "Unexpected advertised URL")
        raw = fetch(url)
        if name != "health.json":
            d.require(hashlib.sha256(raw).hexdigest() == health["fileHashes"][name], "Published hash mismatch: " + name)
        bundle[name] = json.loads(raw) if name.endswith(".json") else raw.decode("utf-8")
        if expected:
            d.require(raw == (Path(expected) / name).read_bytes(), "Deployment mismatch: " + name)
    d.validate(bundle)
    print(json.dumps({"status": "healthy", "ageHours": round(age, 2), "counts": health["counts"]}))
    return health

def baseline(candidate, bootstrap=False):
    current = json.loads((Path(candidate) / "health.json").read_text(encoding="utf-8"))
    try:
        previous = json.loads(fetch(d.FEEDS + "health.json"))
    except HTTPError as exc:
        d.require(exc.code == 404 and bootstrap, "Missing deployment baseline; explicit bootstrap required")
        return
    for key in ("products", "collections", "articles", "faqs"):
        old, new = previous["counts"][key], current["counts"][key]
        d.require(new >= old * 0.75, "Large source-count drop requires review: " + key)
    print("Baseline count-drop guard passed")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected")
    p.add_argument("--max-age-hours", type=float, default=36)
    p.add_argument("--baseline")
    p.add_argument("--bootstrap", action="store_true")
    args = p.parse_args()
    if args.baseline:
        baseline(args.baseline, args.bootstrap)
    else:
        check(args.max_age_hours, args.expected)
