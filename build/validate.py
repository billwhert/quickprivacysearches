"""Validate: automatic checks after ingesting a document, plus a spot-check report."""
import random
import re

import yaml

from common import REPORTS, ROOT, norm
from parse_eurlex import load_tree

CEILING_TOKENS = 1500  # applies to searchable chunks (paragraph, definition, recital)


def source_plain_text(raw_text: str) -> str:
    root = load_tree(raw_text)
    for a in root.xpath('//a[starts-with(@href,"#ntr")]'):
        a.tail = "\ue000" + (a.tail or "")  # marker position; whitespace before it is dropped
        a.drop_tree()
    return re.sub(r"\s*\ue000", "", norm(root.text_content()))


def gaps(nums: list[int], start=1) -> list[int]:
    s = set(nums)
    return [n for n in range(start, max(nums) + 1) if n not in s] if nums else []


def topic_citations() -> set[str]:
    cited = set()
    for p in (ROOT / "topics").glob("*.yaml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for block in (data.get("applicability") or []) + (data.get("items") or []) + (data.get("related") or []):
            cited.update(block.get("chunk_ids") or [])
    return cited


def validate(doc: dict, chunks: list[dict], raw_text: str, crossrefs: list[dict]) -> dict:
    expected = doc.get("validation", {})
    by_kind = {}
    for c in chunks:
        by_kind.setdefault(c["kind"], []).append(c)
    arts = by_kind.get("article", [])
    rcts = by_kind.get("recital", [])
    defs = by_kind.get("definition", [])
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if "articles" in expected:
        check(f"Article count = {expected['articles']}", len(arts) == expected["articles"],
              f"found {len(arts)}")
    if "recitals" in expected:
        check(f"Recital count = {expected['recitals']}", len(rcts) == expected["recitals"],
              f"found {len(rcts)}")
    if "definitions" in expected:
        check(f"Art. 4 definition count = {expected['definitions']}",
              len(defs) == expected["definitions"], f"found {len(defs)}")

    check("Article numbers continuous", not gaps([a["number"] for a in arts]),
          f"gaps: {gaps([a['number'] for a in arts])}")
    check("Recital numbers continuous", not gaps([r["number"] for r in rcts]),
          f"gaps: {gaps([r['number'] for r in rcts])}")
    check("Definition numbers continuous", not gaps([d["number"] for d in defs]),
          f"gaps: {gaps([d['number'] for d in defs])}")
    bad_par = {}
    for a in arts:
        nums = [c["number"] for c in chunks if c["parent_chunk_id"] == a["chunk_id"]]
        if not nums or gaps(nums) or len(nums) != len(set(nums)):
            bad_par[a["chunk_id"]] = nums
    check("Paragraph numbering continuous within each article", not bad_par, str(bad_par) if bad_par else "")

    empty = [c["chunk_id"] for c in chunks if len(c["text"].strip()) < 3]
    check("No empty chunks", not empty, str(empty))
    searchable = [c for c in chunks if c["kind"] != "article"]
    big = [(c["chunk_id"], c["token_count"]) for c in searchable if c["token_count"] > CEILING_TOKENS]
    check(f"No searchable chunk above {CEILING_TOKENS} tokens", not big, str(big))
    ids = [c["chunk_id"] for c in chunks]
    check("Chunk ids unique", len(ids) == len(set(ids)))
    orphan = [c["chunk_id"] for c in chunks if c["parent_chunk_id"] and c["parent_chunk_id"] not in set(ids)]
    check("Every parent_chunk_id resolves", not orphan, str(orphan))

    plain = source_plain_text(raw_text)
    miss = [c["chunk_id"] for c in searchable if norm(c["text"]) not in plain]
    check("Every chunk's text appears verbatim in the saved source file", not miss,
          f"{len(miss)} missing: {miss[:10]}")
    art_miss = [a["chunk_id"] for a in arts if norm(a["text"]) not in plain]
    check("Every article text appears verbatim in the saved source file", not art_miss, str(art_miss[:10]))

    dangling = [r for r in crossrefs if not r["external"] and not r["to_chunk_id"]]
    check("Internal cross-references resolve", not dangling,
          f"{len(dangling)} unresolved: {[r['raw'] for r in dangling[:10]]}")

    cited = topic_citations()
    known = set(ids)
    unresolved = sorted(c for c in cited if c.startswith(doc["doc_id"] + ":") and c not in known)
    check("Guided-topic citations exist in loaded text", not unresolved,
          f"{len(cited)} cited across topics; unresolved: {unresolved}")

    rng = random.Random(f"spot-{doc['doc_id']}")
    sample = rng.sample(searchable, min(10, len(searchable)))
    return {"checks": checks, "sample": sample, "plain_len": len(plain),
            "ok": all(c["ok"] for c in checks),
            "largest": sorted(searchable, key=lambda c: -c["token_count"])[:5]}


def write_report(doc: dict, manifest: dict, result: dict, chunks: list[dict]) -> str:
    L = [f"# Validation report: {doc['doc_id']}", "",
         f"- Title: {doc['title']}",
         f"- Official source: {doc['source_url']}",
         f"- Fetched from: {manifest['fetch_url']}",
         f"- Retrieved: {manifest['retrieved_at']}  (sha256 `{manifest['checksum_sha256'][:16]}...`)",
         f"- Chunks: {len(chunks)} "
         + ", ".join(f"{k}={sum(1 for c in chunks if c['kind'] == k)}"
                     for k in ("article", "section", "paragraph", "definition", "recital")
                     if any(c["kind"] == k for c in chunks)),
         f"- Overall: **{'PASS' if result['ok'] else 'FAIL'}**", "", "## Checks", ""]
    for c in result["checks"]:
        L.append(f"- [{'x' if c['ok'] else ' '}] {c['name']}" + (f" ({c['detail']})" if c["detail"] else ""))
    L += ["", "## Largest searchable chunks", ""]
    L += [f"- `{c['chunk_id']}` {c['section_ref']}: ~{c['token_count']} tokens" for c in result["largest"]]
    L += ["", "## Spot-check: 10 random chunks (compare against the official source)", ""]
    for c in result["sample"]:
        L += [f"### {c['section_ref']}  `{c['chunk_id']}`", "",
              f"Hierarchy: {' > '.join(c['hierarchy'])}", "",
              "```text", c["text"][:900] + ("..." if len(c["text"]) > 900 else ""), "```", ""]
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"{doc['doc_id']}_validation.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return str(out)
