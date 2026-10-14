"""Every internal link and anchor on every built page must resolve.  python tests/check_links.py

Checks href/src on all pages in dist/: the target file must exist, and a #fragment must match an
id on the target page. External links are listed by host but not fetched.
"""
import collections
import pathlib
import re
import sys
import urllib.parse

DIST = pathlib.Path(__file__).resolve().parent.parent / "dist"
ATTR = re.compile(r'\b(?:href|src)="([^"]+)"')
IDS = re.compile(r'\bid="([^"]+)"')

pages = sorted(DIST.rglob("*.html"))
ids_cache: dict[pathlib.Path, set] = {}


def ids_of(p: pathlib.Path) -> set:
    if p not in ids_cache:
        ids_cache[p] = set(IDS.findall(p.read_text(encoding="utf-8")))
    return ids_cache[p]


broken = collections.defaultdict(list)
external = collections.Counter()
checked = 0
for page in pages:
    if page.name == "404.html":
        continue        # uses site-absolute links on purpose (it is served for any missing path)
    html = page.read_text(encoding="utf-8")
    for raw in ATTR.findall(html):
        url = raw.replace("&amp;", "&")
        if url.startswith(("mailto:", "javascript:", "data:")):
            continue
        parts = urllib.parse.urlsplit(url)
        if parts.scheme in ("http", "https"):
            external[parts.netloc] += 1
            continue
        checked += 1
        path = urllib.parse.unquote(parts.path)
        if not path:                                    # "#frag" on the same page
            target = page
        else:
            target = (page.parent / path).resolve()
            if target.is_dir() or path.endswith("/"):
                target = target / "index.html"
        try:
            target.relative_to(DIST.resolve())
        except ValueError:
            broken[str(page.relative_to(DIST))].append(f"{raw}  (outside the site)")
            continue
        if not target.exists():
            broken[str(page.relative_to(DIST))].append(f"{raw}  (no such page)")
            continue
        if parts.fragment and target.suffix == ".html" and parts.fragment not in ids_of(target):
            broken[str(page.relative_to(DIST))].append(f"{raw}  (no #{parts.fragment} on that page)")

total = sum(len(v) for v in broken.values())
print(f"{len(pages)} pages, {checked} internal links checked, {total} broken")
for p, items in list(broken.items())[:25]:
    print(f"  {p}: {len(items)} broken, e.g. {items[0]}")
print("external hosts linked:", ", ".join(f"{h} ({n})" for h, n in external.most_common()))
sys.exit(1 if total else 0)
