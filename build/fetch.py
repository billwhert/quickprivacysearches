"""Fetch: download each document's official file unchanged and record checksum + date."""
import argparse
import datetime
import urllib.request

from common import RAW, ROOT, load_sources, read_json, sha256, write_json

MANIFEST = RAW / "manifest.json"


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(doc_id: str, force: bool = False) -> dict:
    doc = load_sources()[doc_id]
    manifest = read_json(MANIFEST) if MANIFEST.exists() else {}
    path = RAW / f"{doc_id}.{doc.get('raw_ext', 'html')}"
    if path.exists() and not force and doc_id in manifest:
        print(f"[fetch] {doc_id}: raw file present, skipping (use --force to re-download)")
        return manifest[doc_id]
    req = urllib.request.Request(
        doc["fetch_url"],
        headers={"Accept": doc.get("fetch_accept", "*/*"), "Accept-Language": "eng",
                 "User-Agent": "privacy-law-reference-tool/0.1 (research; static site)"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    old = manifest.get(doc_id)
    tmp = path.with_suffix(path.suffix + ".new")
    tmp.write_bytes(data)
    new_sum = sha256(tmp)
    if old and old["checksum_sha256"] == new_sum:
        tmp.unlink()
        old["last_checked_at"] = now()
        entry = old
        print(f"[fetch] {doc_id}: unchanged")
    else:
        tmp.replace(path)
        entry = {
            "doc_id": doc_id,
            "source_url": doc["source_url"],
            "fetch_url": doc["fetch_url"],
            "raw_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(data),
            "checksum_sha256": new_sum,
            "retrieved_at": now(),
            "last_checked_at": now(),
        }
        print(f"[fetch] {doc_id}: saved {len(data):,} bytes, sha256 {new_sum[:12]}...")
    manifest[doc_id] = entry
    write_json(MANIFEST, manifest)
    return entry


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("doc_id")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    fetch(a.doc_id, a.force)
