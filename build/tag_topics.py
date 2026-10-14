"""Topic tagging: first-pass keyword rules + manual overrides that persist across rebuilds.

    python build/tag_topics.py            # tag every ingested document, write the review files

Inputs
  taxonomy/topics.yaml     controlled vocabulary and keyword rules
  taxonomy/overrides.yaml  manual corrections (re-applied on every run)
Outputs
  data/processed/<doc>/chunks.json   `topics` filled in (ids)
  data/reports/topic_review.csv      one row per provision: final topics, rule hits, excerpt
  data/reports/topic_tagging.md      coverage, topic counts, stale overrides
"""
import csv
import re
import sys

import yaml

from common import PROCESSED, REPORTS, ROOT, read_json, write_json

PARENT_KINDS = ("article", "section")
TAXONOMY = ROOT / "taxonomy" / "topics.yaml"
OVERRIDES = ROOT / "taxonomy" / "overrides.yaml"


# ---------- rules ----------

def norm_text(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s)


def compile_phrase(p: str) -> re.Pattern:
    words = norm_text(p).strip().split(" ")
    parts = []
    for w in words:
        wild = w.endswith("*")
        w = w.rstrip("*")
        parts.append(re.escape(w) + (r"\w*" if wild else ""))
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)")


def load_taxonomy() -> dict:
    raw = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    d = raw["defaults"]
    topics = []
    for t in raw["topics"]:
        topics.append({
            "id": t["id"], "label": t["label"], "parent": t.get("parent"),
            "description": t.get("description", ""),
            "phrases": [(p, compile_phrase(p)) for p in t.get("phrases", [])],
            "weak": [(p, compile_phrase(p)) for p in t.get("weak", [])],
            "headers": [(p, compile_phrase(p)) for p in t.get("headers", [])],
            "head": t.get("head", d["head"]), "text": t.get("text", d["text"]),
            "min_score": t.get("min_score", d["min_score"]),
        })
    ids = [t["id"] for t in topics]
    assert len(ids) == len(set(ids)), "duplicate topic id in topics.yaml"
    for t in topics:
        assert t["parent"] is None or t["parent"] in ids, f"unknown parent for {t['id']}"
    return {"topics": topics, "by_id": {t["id"]: t for t in topics}, "order": ids}


def load_overrides(tax: dict) -> list[dict]:
    if not OVERRIDES.exists():
        return []
    raw = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8")) or {}
    out = []
    for o in raw.get("overrides") or []:
        for k in ("add", "remove"):
            for t in o.get(k) or []:
                if t not in tax["by_id"]:
                    raise SystemExit(f"overrides.yaml: unknown topic '{t}' for {o.get('id')}")
        out.append(o)
    return out


def head_text(c: dict, parent: dict | None) -> str:
    bits = [c.get("heading", ""), c.get("subheading", ""), c.get("defined_term", "")]
    if parent is not None:
        bits.append(parent.get("heading", ""))
    return norm_text(" ".join(b for b in bits if b))


def score_topic(t: dict, head: str, body: str):
    score, hits = 0.0, []
    for phrase, rx in t["phrases"]:
        if rx.search(head):
            score += t["head"]
            hits.append(f"{phrase} [heading]")
        elif rx.search(body):
            score += t["text"]
            hits.append(phrase)
    for phrase, rx in t["weak"]:
        if rx.search(head):
            score += t["head"] / 2
            hits.append(f"~{phrase} [heading]")
        elif rx.search(body):
            score += t["text"] / 2
            hits.append(f"~{phrase}")
    for phrase, rx in t["headers"]:
        if rx.search(head):
            score += t["head"]
            hits.append(f"{phrase} [heading only]")
    return score, hits


def auto_tag(c: dict, parent: dict | None, tax: dict):
    head, body = head_text(c, parent), norm_text(c["text"])
    chosen, hits = set(), {}
    for t in tax["topics"]:
        s, h = score_topic(t, head, body)
        if s >= t["min_score"] and h:
            chosen.add(t["id"])
            hits[t["id"]] = h
    if c["kind"] == "definition":
        chosen.add("definitions")
        hits.setdefault("definitions", ["defined term"])
    for tid in list(chosen):          # a sub-topic brings its parent
        p = tax["by_id"][tid]["parent"]
        if p:
            chosen.add(p)
            hits.setdefault(p, [f"(from {tid})"])
    return chosen, hits


# ---------- run ----------

def run() -> dict:
    tax = load_taxonomy()
    overrides = load_overrides(tax)
    order = {tid: i for i, tid in enumerate(tax["order"])}
    docs = sorted(d.name for d in PROCESSED.iterdir() if (d / "chunks.json").exists())
    data = {d: read_json(PROCESSED / d / "chunks.json") for d in docs}
    by_id = {c["chunk_id"]: c for cs in data.values() for c in cs}

    # which chunks does each override apply to? (a section/article id covers all its provisions)
    stale, applied = [], {}
    for o in overrides:
        cid = o["id"]
        if cid not in by_id:
            stale.append(cid)
            continue
        c = by_id[cid]
        targets = [cid]
        if c["kind"] in PARENT_KINDS:
            targets += c.get("child_chunk_ids", [])
        for t in targets:
            applied.setdefault(t, []).append(o)

    rows, per_doc = [], {}
    rule_hits: dict[str, dict[str, int]] = {}
    for doc, chunks in data.items():
        searchable = [c for c in chunks if c["kind"] not in PARENT_KINDS]
        parents = {c["chunk_id"]: c for c in chunks if c["kind"] in PARENT_KINDS}
        tagged = 0
        for c in searchable:
            parent = parents.get(c.get("parent_chunk_id"))
            chosen, hits = auto_tag(c, parent, tax)
            auto = sorted(chosen, key=order.get)
            for t, hs in hits.items():
                for h in hs:
                    key = h.replace(" [heading]", "").replace(" [heading only]", "").lstrip("~")
                    if not key.startswith("("):
                        rule_hits.setdefault(t, {})
                        rule_hits[t][key] = rule_hits[t].get(key, 0) + 1
            manual = []
            for o in applied.get(c["chunk_id"], []):
                for t in o.get("add") or []:
                    chosen.add(t)
                    p = tax["by_id"][t]["parent"]
                    if p:
                        chosen.add(p)
                    manual.append(f"+{t}")
                for t in o.get("remove") or []:
                    chosen.discard(t)
                    manual.append(f"-{t}")
            final = sorted(chosen, key=order.get)
            c["topics"] = final
            c["topics_manual"] = bool(manual)
            if final:
                tagged += 1
            rows.append({
                "doc": doc, "chunk_id": c["chunk_id"], "ref": c["section_ref"],
                "heading": (c.get("subheading") or c.get("heading") or "")[:80],
                "topics": " ".join(final), "auto": " ".join(auto), "manual": " ".join(manual),
                "why": "; ".join(f"{t}: {', '.join(hits[t][:3])}" for t in auto if t in hits)[:240],
                "excerpt": re.sub(r"\s+", " ", c["text"])[:160],
            })
        for p in parents.values():     # a section carries the union of its provisions' topics
            kids = [c for c in searchable if c.get("parent_chunk_id") == p["chunk_id"]]
            p["topics"] = sorted({t for k in kids for t in k["topics"]}, key=order.get)
        per_doc[doc] = {"total": len(searchable), "tagged": tagged}
        write_json(PROCESSED / doc / "chunks.json", chunks)

    write_reports(tax, rows, per_doc, stale, len(overrides), rule_hits)
    return {"per_doc": per_doc, "stale": stale, "rows": rows, "rule_hits": rule_hits}


def write_reports(tax, rows, per_doc, stale, n_overrides, rule_hits):
    REPORTS.mkdir(parents=True, exist_ok=True)
    with open(REPORTS / "topic_review.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["doc", "chunk_id", "ref", "heading", "topics", "auto", "manual", "why", "excerpt"])
        w.writeheader()
        w.writerows(rows)
    counts = {t["id"]: 0 for t in tax["topics"]}
    by_doc = {d: {t["id"]: 0 for t in tax["topics"]} for d in per_doc}
    for r in rows:
        for t in r["topics"].split():
            counts[t] += 1
            by_doc[r["doc"]][t] += 1
    L = ["# Topic tagging report", "",
         "Generated by `build/tag_topics.py`. Correct tags in `taxonomy/overrides.yaml`; "
         "review every provision in `topic_review.csv`.", "", "## Coverage", "",
         "| Document | Provisions | With at least one topic | Share |", "|---|---|---|---|"]
    for d, v in per_doc.items():
        L.append(f"| {d} | {v['total']} | {v['tagged']} | {v['tagged'] * 100 // max(1, v['total'])}% |")
    L += ["", "## Provisions per topic", "",
          "| Topic | " + " | ".join(per_doc) + " | Total |", "|---|" + "---|" * (len(per_doc) + 1)]
    for t in tax["topics"]:
        L.append(f"| {t['label']} (`{t['id']}`) | " + " | ".join(str(by_doc[d][t['id']]) for d in per_doc)
                 + f" | {counts[t['id']]} |")
    L += ["", "## Phrases doing the work", "",
          "The most frequent rule hits per topic. A phrase that fires on a very large share of provisions is "
          "probably too broad; tighten it in `taxonomy/topics.yaml`.", ""]
    for t in tax["topics"]:
        top = sorted(rule_hits.get(t["id"], {}).items(), key=lambda kv: -kv[1])[:6]
        if top:
            L.append(f"- **{t['label']}**: " + ", ".join(f"`{k}` ({v})" for k, v in top))
    L += ["", f"## Manual overrides: {n_overrides} entries", ""]
    L += [f"- STALE (chunk id no longer exists): `{s}`" for s in stale] or ["- none stale"]
    untagged = [r for r in rows if not r["topics"]]
    L += ["", f"## Provisions with no topic: {len(untagged)}", "",
          "These are fine when a provision is purely procedural. Add a topic in `overrides.yaml` if one fits.", ""]
    for r in untagged[:40]:
        L.append(f"- `{r['chunk_id']}` {r['ref']} - {r['heading']}")
    if len(untagged) > 40:
        L.append(f"- ... and {len(untagged) - 40} more (see topic_review.csv)")
    (REPORTS / "topic_tagging.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    res = run()
    for d, v in res["per_doc"].items():
        print(f"{d}: {v['tagged']}/{v['total']} provisions tagged")
    if res["stale"]:
        print("STALE overrides:", res["stale"])
        sys.exit(1)
