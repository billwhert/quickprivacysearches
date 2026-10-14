"""Fetch for eCFR documents made of several parts (e.g. HIPAA: 45 CFR Parts 160 and 164).

For each part we save two untouched files:
  data/raw/<doc_id>_<part>.html            official rendered text (eCFR renderer API)
  data/raw/<doc_id>_<part>_structure.json  official table of contents (eCFR versioner API)
The date is resolved once from the eCFR titles endpoint so every file is from the same version.
"""
import datetime
import hashlib
import json
import urllib.request

from common import RAW, ROOT, read_json, sha256, write_json

MANIFEST = RAW / "manifest.json"
UA = {"User-Agent": "privacy-law-reference-tool/0.1 (research; static site)"}


def _get(url: str, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=240) as r:
        return r.read()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_ecfr(doc_id: str, doc: dict, force: bool = False) -> dict:
    manifest = read_json(MANIFEST) if MANIFEST.exists() else {}
    old = manifest.get(doc_id)
    files_ok = all((RAW / f"{doc_id}_{p['part']}.html").exists() and
                   (RAW / f"{doc_id}_{p['part']}_structure.json").exists() for p in doc["parts"])
    if old and files_ok and not force:
        print(f"[fetch] {doc_id}: raw files present, skipping (use --force to re-download)")
        return old

    titles = json.loads(_get("https://www.ecfr.gov/api/versioner/v1/titles.json", "application/json"))
    def date_for(title):
        return next(t for t in titles["titles"] if t["number"] == title)["up_to_date_as_of"]

    date = date_for(doc["ecfr_title"])
    files, combined = {}, hashlib.sha256()
    for p in doc["parts"]:
        part = str(p["part"])
        title = p.get("title", doc["ecfr_title"])
        pdate = date_for(title)
        html = _get(p["fetch_url"].replace("{ECFR_DATE}", pdate), "text/html")
        struct = _get(p["structure_url"].replace("{ECFR_DATE}", pdate), "application/json")
        hp, sp = RAW / f"{doc_id}_{part}.html", RAW / f"{doc_id}_{part}_structure.json"
        hp.write_bytes(html)
        sp.write_bytes(struct)
        files[part] = {
            "html": str(hp.relative_to(ROOT)).replace("\\", "/"), "html_sha256": sha256(hp),
            "structure": str(sp.relative_to(ROOT)).replace("\\", "/"), "structure_sha256": sha256(sp),
            "bytes": len(html) + len(struct), "title": title, "date": pdate,
        }
        combined.update(files[part]["html_sha256"].encode())
        combined.update(files[part]["structure_sha256"].encode())
        print(f"[fetch] {doc_id} part {part}: {len(html):,} + {len(struct):,} bytes (eCFR as of {date})")
    digest = combined.hexdigest()
    now = _now()
    if old and old.get("checksum_sha256") == digest:
        old["last_checked_at"] = now
        entry = old
        print(f"[fetch] {doc_id}: unchanged")
    else:
        first = doc["parts"][0]
        entry = {
            "doc_id": doc_id, "source_url": doc["source_url"],
            "fetch_url": first["fetch_url"].replace("{ECFR_DATE}", date),
            "raw_path": files[str(first["part"])]["html"], "files": files, "ecfr_date": date,
            "bytes": sum(f["bytes"] for f in files.values()),
            "checksum_sha256": digest, "retrieved_at": now, "last_checked_at": now,
        }
    manifest[doc_id] = entry
    write_json(MANIFEST, manifest)
    return entry
