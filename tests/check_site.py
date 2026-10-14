"""Checks that the built site backs up what its trust pages say.  python tests/check_site.py
Needs dist/ built first (python build/build.py)."""
import html
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
fails = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        fails.append(name)


htmls = list(DIST.rglob("*.html"))
check("site has pages", len(htmls) > 100, f"{len(htmls)} pages")

# --- trust pages exist and say the required things ---
need = {
    "about/index.html": ["not legal advice", "official source", "Currently loaded", "Report an error".lower()],
    "disclaimer/index.html": ["Not legal advice", "No accounts", "not sent anywhere", "cookies", "GitHub"],
    "sources/index.html": ["Official source", "Reuse terms", "Attribution", "Retrieved", "Fingerprint"],
}
for rel, phrases in need.items():
    f = DIST / rel
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    low = text.lower()
    missing = [p for p in phrases if p.lower() not in low]
    check(f"{rel} present and complete", f.exists() and not missing, f"missing {missing}")

# --- Sources lists every loaded document, with attribution and official link ---
docs = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "data" / "processed").glob("*/document.json")]
src = (DIST / "sources" / "index.html").read_text(encoding="utf-8")
lacking = [d["doc_id"] for d in docs
           if d["title"].split("(")[0].strip()[:30] not in src or not d.get("attribution") or not d.get("reuse_url")
           or html.escape(d["source_url"]) not in src]
check("every document on Sources has title, official link, attribution and reuse link", not lacking, str(lacking))
check("no placeholder reuse wording left", all("Confirm" not in (d.get("license_note") or "") for d in docs))

# --- footer links on every page ---
no_footer = [str(p.relative_to(DIST)) for p in htmls
             if not all(k in p.read_text(encoding="utf-8") for k in ("about/", "sources/", "disclaimer/", "Report an error"))]
check("every page has the trust links in its footer", not no_footer, str(no_footer[:5]))

# --- report links are prefilled with the provision, never with a search ---
sample = (DIST / "gdpr" / "art" / "30" / "index.html").read_text(encoding="utf-8")
m = re.search(r'href="([^"]*issues/new[^"]*provision=[^"]*)"', sample)
check("provision page has a prefilled report link", bool(m))
if m:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1).replace("&amp;", "&")).query)
    check("report link carries only the provision and page", set(q) <= {"template", "title", "provision", "page"}, str(set(q)))

# --- privacy claims: no third-party resources, no storage, no tracking ---
external = []
for p in htmls:
    t = p.read_text(encoding="utf-8")
    for tag, attr in (("script", "src"), ("link", "href"), ("img", "src"), ("iframe", "src")):
        for m in re.finditer(rf"<{tag}\b[^>]*\b{attr}=\"(https?://[^\"]+)\"", t):
            if tag == "link" and 'rel="stylesheet"' not in m.group(0) and "preload" not in m.group(0):
                continue
            external.append((str(p.relative_to(DIST)), m.group(1)))
check("no third-party scripts, styles, images or frames in any page", not external, str(external[:3]))

js = "\n".join(p.read_text(encoding="utf-8") for p in (DIST / "assets").glob("*.js") if p.name != "minisearch.js")
for pat, label in [("localStorage", "localStorage"), ("sessionStorage", "sessionStorage"), ("document.cookie", "cookies"),
                   ("indexedDB", "IndexedDB"), ("navigator.sendBeacon", "sendBeacon"), ("XMLHttpRequest", "XMLHttpRequest")]:
    check(f"site code does not use {label}", pat not in js)
fetches = re.findall(r"fetch\(\s*([^)]+)\)", js)
bad = [f for f in fetches if "http" in f and "assets/" not in f]
check("site code only fetches its own static files", not bad, str(bad))

print(f"\n{'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}")
sys.exit(1 if fails else 0)
