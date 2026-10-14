"""Ingest one document: fetch -> parse -> crossrefs -> validate -> write processed JSON.

Usage: python build/ingest.py gdpr [--force-fetch]
"""
import argparse
import sys

import crossrefs
import parse_eurlex
import validate
from common import PROCESSED, ROOT, load_sources, read_json, write_json
from fetch import fetch


def all_loaded_ids(skip: str) -> set:
    ids = set()
    for d in PROCESSED.iterdir():
        f = d / "chunks.json"
        if d.name != skip and f.exists():
            ids.update(c["chunk_id"] for c in read_json(f))
    return ids


def ingest(doc_id: str, force_fetch: bool = False) -> bool:
    doc = load_sources()[doc_id]
    manifest = fetch(doc_id, force_fetch)
    raw_path = ROOT / manifest["raw_path"]

    if doc["parser"] == "code":
        import crossrefs_code
        import parse_code
        import validate_code
        chunks, toc = parse_code.parse(raw_path, doc, manifest["retrieved_at"])
        ids = {c["chunk_id"] for c in chunks} | all_loaded_ids(doc_id)
        refs = crossrefs_code.extract(chunks, ids, doc_id)
        plain = validate.norm(" ".join(parse_code.raw_lines(raw_path)))
        result = validate_code.validate_code(doc, chunks, toc, plain, refs, ids)
    elif doc["parser"] == "eurlex":
        raw_text = raw_path.read_text(encoding="utf-8")
        chunks = parse_eurlex.parse(raw_text, doc, manifest["retrieved_at"])
        refs = crossrefs.extract(chunks)
        result = validate.validate(doc, chunks, raw_text, refs)
    else:
        raise SystemExit(f"unknown parser: {doc['parser']}")
    report = validate.write_report(doc, manifest, result, chunks)

    out = PROCESSED / doc_id
    write_json(out / "document.json", {
        "doc_id": doc_id, "title": doc["title"], "short_name": doc.get("short_name", doc_id.upper()),
        "jurisdiction": doc["jurisdiction"], "doc_type": doc["doc_type"],
        "source_url": doc["source_url"], "version_label": doc.get("version_label"),
        "effective_date": doc.get("effective_date"), "retrieved_at": manifest["retrieved_at"],
        "language": doc["language"], "is_translation": doc["is_translation"],
        "raw_path": manifest["raw_path"], "checksum": manifest["checksum_sha256"],
        "license_note": doc.get("license_note"),
    })
    write_json(out / "chunks.json", chunks)
    write_json(out / "crossrefs.json", refs)

    for c in result["checks"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["name"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    print(f"{len(chunks)} chunks, {len(refs)} cross-references -> {out}")
    print(f"report: {report}")
    return result["ok"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("doc_id")
    ap.add_argument("--force-fetch", action="store_true")
    a = ap.parse_args()
    sys.exit(0 if ingest(a.doc_id, a.force_fetch) else 1)
