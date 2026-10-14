"""Export searchable chunks (and article stubs for citation lookup) to JSON for the browser.

Output: dist/assets/search-data.json
  {"chunks": [...searchable chunks with full text...], "articles": [...stubs...]}
"""
import json

from common import PROCESSED, ROOT, read_json, write_json

DIST = ROOT / "dist"


def load_all_chunks() -> list[dict]:
    chunks = []
    for d in sorted(PROCESSED.iterdir()):
        if (d / "chunks.json").exists():
            chunks.extend(read_json(d / "chunks.json"))
    return chunks


def export() -> dict:
    docs = {}
    for d in sorted(PROCESSED.iterdir()):
        if (d / "document.json").exists():
            doc = read_json(d / "document.json")
            docs[doc["doc_id"]] = doc
    chunks, articles = [], []
    for c in load_all_chunks():
        if c["kind"] == "article":
            articles.append({"id": c["chunk_id"], "doc": c["doc_id"], "ref": c["section_ref"],
                             "heading": c["heading"], "url": c["permalink"], "n": c["number"]})
            continue
        chunks.append({
            "id": c["chunk_id"], "doc": c["doc_id"], "kind": c["kind"], "n": c["number"],
            "ref": c["section_ref"], "heading": c["heading"],
            "term": c.get("defined_term", ""), "text": c["text"],
            "url": c["permalink"], "hier": c["hierarchy"], "parent": c["parent_chunk_id"],
            "art": int(c["chunk_id"].split(":")[2]) if c["kind"] != "recital" else None,
        })
    out = {"chunks": chunks, "articles": articles,
           "docs": {k: {"title": v["title"], "source_url": v["source_url"],
                        "version_label": v["version_label"], "retrieved_at": v["retrieved_at"],
                        "doc_type": v["doc_type"], "jurisdiction": v["jurisdiction"]}
                    for k, v in docs.items()}}
    write_json(DIST / "assets" / "search-data.json", out)
    return out


if __name__ == "__main__":
    o = export()
    size = (DIST / "assets" / "search-data.json").stat().st_size
    print(f"exported {len(o['chunks'])} chunks, {len(o['articles'])} articles ({size:,} bytes)")
