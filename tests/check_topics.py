"""Check topic tagging against provisions whose topics are known: python tests/check_topics.py"""
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
gold = yaml.safe_load((ROOT / "tests" / "topic_gold.yaml").read_text(encoding="utf-8"))["gold"]

chunks = {}
for d in (ROOT / "data" / "processed").iterdir():
    f = d / "chunks.json"
    if f.exists():
        for c in json.loads(f.read_text(encoding="utf-8")):
            chunks[c["chunk_id"]] = c

bad = 0
for g in gold:
    c = chunks.get(g["id"])
    if c is None:
        print(f"MISSING  {g['id']} (not in the loaded data)")
        bad += 1
        continue
    topics = set(c.get("topics", []))
    miss = [t for t in g.get("has", []) if t not in topics]
    extra = [t for t in g.get("not", []) if t in topics]
    if miss or extra:
        bad += 1
        print(f"FAIL  {g['id']}: " + (f"missing {miss} " if miss else "") + (f"unexpected {extra} " if extra else "")
              + f"| has {sorted(topics)}")
print(f"\n{len(gold) - bad}/{len(gold)} gold provisions correct")
sys.exit(1 if bad else 0)
