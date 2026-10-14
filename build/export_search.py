"""Export searchable chunks (and parent stubs for citation lookup) to JSON for the browser.

Output: dist/assets/search-data.json
  {"chunks": [...searchable chunks with full text...], "articles": [...parent stubs...], "docs": {...}}
"""
import yaml

from common import PROCESSED, ROOT, read_json, write_json

DIST = ROOT / "dist"
PARENT_KINDS = ("article", "section")


def export() -> dict:
    order = [d["doc_id"] for d in yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["documents"]]
    docs, chunks, parents = {}, [], []
    for doc_id in order:
        d = PROCESSED / doc_id
        if not (d / "chunks.json").exists():
            continue
        doc = read_json(d / "document.json")
        docs[doc_id] = {
            "title": doc["title"], "short": doc.get("short_name", doc_id.upper()),
            "source_url": doc["source_url"], "version_label": doc["version_label"],
            "retrieved_at": doc["retrieved_at"], "doc_type": doc["doc_type"],
            "jurisdiction": doc["jurisdiction"],
        }
        for i, c in enumerate(read_json(d / "chunks.json")):
            if c["kind"] in PARENT_KINDS:
                parents.append({"id": c["chunk_id"], "doc": doc_id, "ref": c["section_ref"],
                                "heading": c["heading"], "url": c["permalink"], "n": c["number"]})
                continue
            chunks.append({
                "id": c["chunk_id"], "doc": doc_id, "kind": c["kind"], "n": c["number"], "ord": i,
                "ref": c["section_ref"], "heading": c["heading"],
                "term": c.get("defined_term", ""), "text": c["text"], "lead": c.get("lead_in", ""),
                "url": c["permalink"], "hier": c["hierarchy"], "parent": c["parent_chunk_id"],
            })
    out = {"chunks": chunks, "articles": parents, "docs": docs}
    write_json(DIST / "assets" / "search-data.json", out)
    return out


if __name__ == "__main__":
    o = export()
    print(f"exported {len(o['chunks'])} chunks, {len(o['articles'])} parents")
