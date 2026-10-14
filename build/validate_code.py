"""Validation for legal-code documents (sections / subdivisions) parsed by parse_code."""
import random

import parse_code as pc
from common import norm
from validate import CEILING_TOKENS, topic_citations


def validate_code(doc: dict, chunks: list[dict], toc: list[str], plain: str, crossrefs: list[dict],
                  all_ids: set) -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    secs = [c for c in chunks if c["kind"] == "section"]
    kids = [c for c in chunks if c["kind"] != "section"]
    nums = [s["number"] for s in secs]
    check(f"Section count matches the document's own table of contents ({len(toc)})",
          nums == toc, f"parsed {len(nums)}; missing {[t for t in toc if t not in nums][:8]}; "
                       f"extra {[n for n in nums if n not in toc][:8]}")
    no_kids = [s["chunk_id"] for s in secs if not s["child_chunk_ids"]]
    check("Every section has at least one chunk", not no_kids, str(no_kids))

    # label continuity among top-level subdivisions of each section
    bad = {}
    import re
    range_re = re.compile(r"^\((\w+)\)\s*[–—-]\s*\((\w+)\)")  # "(b)-(d) [Reserved]"
    for s in secs:
        labels = []                      # (label, last label it covers)
        for c in kids:
            if c["parent_chunk_id"] != s["chunk_id"] or c["kind"] == "definition":
                continue
            lab = c["number"].split(".")[0]
            if lab != "0" and (not labels or labels[-1][0] != lab):
                m = range_re.match(c["text"])    # "(b)-(d) [Reserved]" covers b through d
                labels.append((lab, m.group(2) if m and m.group(1) == lab else lab))
        for (_, prev_end), (cur, _) in zip(labels, labels[1:]):
            if not (prev_end.isalnum() and cur.isalnum()):
                continue
            style = "digit" if prev_end.isdigit() else ("upper" if prev_end.isupper() else "lower")
            if cur not in pc.successors(style, prev_end):
                bad.setdefault(s["number"], []).append(f"{prev_end}->{cur}")
    check("Top-level subdivision labels run in sequence (no gaps)", not bad, str(bad))

    empty = [c["chunk_id"] for c in kids if len(c["text"].strip()) < 3]
    check("No empty chunks", not empty, str(empty))
    big = [(c["chunk_id"], c["token_count"]) for c in kids if c["token_count"] > CEILING_TOKENS]
    check(f"No searchable chunk above {CEILING_TOKENS} tokens", not big, str(big))
    ids = [c["chunk_id"] for c in chunks]
    check("Chunk ids unique", len(ids) == len(set(ids)),
          str([i for i in set(ids) if ids.count(i) > 1][:5]))
    idset = set(ids)
    check("Every parent_chunk_id resolves",
          all(c["parent_chunk_id"] in idset for c in kids if c["parent_chunk_id"]))

    # table rows are rendered with " | " between cells; the source has no such separator
    miss = [c["chunk_id"] for c in kids if norm(c["text"]) not in plain
            and norm(c["text"].replace(" | ", " ")) not in plain]
    check("Every chunk's text appears verbatim in the saved source file", not miss,
          f"{len(miss)} missing: {miss[:8]}")
    if doc.get("profile", {}).get("definition_sections"):
        no_term = [c["chunk_id"] for c in kids if c["kind"] == "definition" and not c.get("defined_term")]
        check("Every definition has a defined term", not no_term, str(no_term))

    dangling = [r for r in crossrefs if r.get("own_space") and not r["to_chunk_id"]]
    check("Cross-references into this document resolve", not dangling,
          f"{len(dangling)} unresolved: {sorted({r['raw'] for r in dangling})[:10]}")

    cited = topic_citations()
    unresolved = sorted(c for c in cited if c.startswith(doc["doc_id"] + ":") and c not in all_ids)
    check("Guided-topic citations exist in loaded text", not unresolved,
          f"{len(cited)} cited across topics; unresolved: {unresolved}")

    rng = random.Random(f"spot-{doc['doc_id']}")
    return {"checks": checks, "sample": rng.sample(kids, min(10, len(kids))),
            "ok": all(c["ok"] for c in checks),
            "largest": sorted(kids, key=lambda c: -c["token_count"])[:5]}
