"""Generate the static site (pages, assets, search data) from data/processed/."""
import hashlib
import html
import json
import shutil

import yaml

import export_search
from common import PROCESSED, ROOT, read_json

DIST = ROOT / "dist"
WEB = ROOT / "web"
e = html.escape

VERSION = "dev"  # set in build(): content hash used to bust browser caches
PARENT_KINDS = ("article", "section")

DISCLAIMER = ("Reference tool, not legal advice. Text is taken from the official source and shown "
              "unmodified; check the official source and version date before relying on it.")

LOGO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>')


# ---------- shared page frame ----------

def page(title: str, body: str, rel: str, nav_docs: list, active: str = "") -> str:
    nav = [("Search", rel, "search")] + [(d["short_name"], f"{rel}{d['doc_id']}/", d["doc_id"]) for d in nav_docs]
    links = " ".join(
        f'<a href="{href}"{" aria-current=page" if key == active else ""}>{e(label)}</a>'
        for label, href, key in nav)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<link rel="stylesheet" href="{rel}assets/style.css?v={VERSION}">
</head><body>
<header class="site"><div class="wrap">
<a class="brand" href="{rel}">{LOGO}Quick Privacy Searches</a><nav aria-label="Main">{links}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="site"><div class="wrap">
<p>{e(DISCLAIMER)}</p>
<p>No accounts, no tracking. Searches run in your browser and are never sent anywhere.</p>
</div></footer>
</body></html>
"""


def render_text(text: str) -> str:
    out = []
    for line in text.split("\n"):
        indent = (len(line) - len(line.lstrip(" "))) // 2
        out.append(f'<p class="l{min(indent, 4)}">{e(line.strip())}</p>')
    return "\n".join(out)


def source_block(doc: dict) -> str:
    return (f'<p class="meta">Source: <a href="{e(doc["source_url"])}">official text</a> · '
            f'{e(doc["version_label"])} · retrieved {e(doc["retrieved_at"][:10])}</p>')


def doc_layout(parts: list, side: str) -> str:
    return f'<div class="doc-layout"><article>{"".join(parts)}</article>{side}</div>'


def side_panel(doc: dict, nav_title: str = "", nav_items: list = None, src: str = "") -> str:
    out = ['<aside class="side">',
           '<div class="side-card"><h3>Source</h3>',
           f'<p><a href="{e(src or doc["source_url"])}">Official text</a></p>',
           f'<p class="muted">{e(doc["version_label"])}<br>Retrieved {e(doc["retrieved_at"][:10])}</p></div>']
    if nav_items:
        out.append(f'<div class="side-card"><h3>{e(nav_title)}</h3><ul class="side-nav">'
                   + "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in nav_items) + "</ul></div>")
    out.append(f'<p class="side-link"><a href="../../">All {e(doc["short_name"])} provisions</a></p></aside>')
    return "".join(out)


def depth_rel(permalink: str) -> str:
    return "../" * len([p for p in permalink.split("#")[0].split("/") if p])


def fragment(permalink: str) -> str:
    return permalink.split("#", 1)[1] if "#" in permalink else ""


def child_label(c: dict) -> str:
    """Human label for a child card on a section/article page."""
    if c["kind"] == "definition":
        if c.get("defined_term"):
            return f"Definition: {c['defined_term']}"
        return f"Definition ({c['number']})"
    if c.get("unnumbered") or str(c["number"]) == "0":
        return ""
    if c["doc_id"] == "gdpr":
        return f"Paragraph {c['number']}"
    return "".join(f"({p})" for p in str(c["number"]).split("."))


# ---------- per-document pages ----------

def build_doc_pages(doc_id: str, docs: list, by_id_all: dict, in_refs: dict) -> None:
    pdir = PROCESSED / doc_id
    doc = next(d for d in docs if d["doc_id"] == doc_id)
    chunks = read_json(pdir / "chunks.json")
    refs = read_json(pdir / "crossrefs.json")
    out_refs: dict[str, list[str]] = {}
    for r in refs:
        if r["to_chunk_id"]:
            lst = out_refs.setdefault(r["from_chunk_id"], [])
            if r["to_chunk_id"] not in lst:
                lst.append(r["to_chunk_id"])

    def link(rel: str, cid: str) -> str:
        c = by_id_all[cid]
        return f'<a href="{rel}{c["permalink"]}">{e(c["section_ref"])}</a>'

    parents = [c for c in chunks if c["kind"] in PARENT_KINDS]
    recitals = sorted((c for c in chunks if c["kind"] == "recital"), key=lambda c: c["number"])

    for i, a in enumerate(parents):
        rel = depth_rel(a["permalink"])
        crumbs = " › ".join(a["hierarchy"][:-1])
        h1_sub = f'<span class="sub">{e(a["heading"])}</span>' if a["heading"] else ""
        parts = [f'<p class="crumbs"><span class="badge">{e(doc["short_name"])}</span> {e(crumbs)}</p>',
                 f'<h1>{e(a["section_ref"])}{h1_sub}</h1>']
        nav_items = []
        for cid in a["child_chunk_ids"]:
            c = by_id_all[cid]
            label = child_label(c)
            frag = fragment(c["permalink"])
            if label and frag:
                nav_items.append((frag, label))
            cites = out_refs.get(cid, [])
            cite_html = ('<p class="refs">References: ' + ", ".join(link(rel, t) for t in cites) + "</p>"
                         if cites else "")
            lead = (f'<p class="lead-in"><span>Context:</span> {e(c["lead_in"])}</p>'
                    if c.get("lead_in") else "")
            anchor = (f'<a class="anchor" href="#{frag}" title="Permalink">{e(label)}</a>'
                      if label and frag else "")
            id_attr = f' id="{frag}"' if frag else ""
            parts.append(f'<section class="prov"{id_attr}>'
                         f'{anchor}{lead}<div class="text">{render_text(c["text"])}</div>{cite_html}</section>')
        notes = a.get("footnotes") or []
        if notes:
            parts.append('<section class="notes"><h2>Notes</h2><ol>'
                         + "".join(f'<li>{e(f["text"])}</li>' for f in notes) + "</ol></section>")
        if a.get("note"):
            parts.append(f'<section class="notes"><h2>Source note</h2><p>{e(a["note"])}</p></section>')
        cited_by = sorted(t for t in in_refs.get(a["chunk_id"], set()) if t != a["chunk_id"] and t in by_id_all)
        if cited_by:
            parts.append('<p class="refs">Referred to in: '
                         + ", ".join(link(rel, t) for t in cited_by) + "</p>")
        prev_a = parents[i - 1] if i else None
        next_a = parents[i + 1] if i + 1 < len(parents) else None
        pn = "<nav class=pager>"
        pn += (f'<a href="{rel}{prev_a["permalink"]}">← {e(prev_a["section_ref"])}</a>' if prev_a else "<span></span>")
        pn += (f'<a href="{rel}{next_a["permalink"]}">{e(next_a["section_ref"])} →</a>' if next_a else "<span></span>")
        parts.append(pn + "</nav>")
        d = DIST / a["permalink"]
        d.mkdir(parents=True, exist_ok=True)
        title = f'{a["section_ref"]} - {a["heading"]}' if a["heading"] else a["section_ref"]
        nav_title = "In this article" if a["kind"] == "article" else "In this section"
        (d / "index.html").write_text(
            page(title, doc_layout(parts, side_panel(doc, nav_title, nav_items, a["source_url"])), rel, docs, doc_id),
            encoding="utf-8")

    for i, r in enumerate(recitals):
        rel = depth_rel(r["permalink"])
        cites = out_refs.get(r["chunk_id"], [])
        body = [f'<p class="crumbs"><span class="badge">{e(doc["short_name"])}</span> Recitals</p>',
                f'<h1>{e(r["section_ref"])}</h1>',
                f'<section class="prov"><div class="text">{render_text(r["text"])}</div>'
                + ('<p class="refs">References: ' + ", ".join(link(rel, t) for t in cites) + "</p>" if cites else "")
                + "</section>"]
        if r["footnotes"]:
            body.append('<section class="notes"><h2>Notes</h2><ol>'
                        + "".join(f'<li>{e(f["text"])}</li>' for f in r["footnotes"]) + "</ol></section>")
        pv = recitals[i - 1] if i else None
        nx = recitals[i + 1] if i + 1 < len(recitals) else None
        body.append("<nav class=pager>"
                    + (f'<a href="../{pv["number"]}/">← Recital {pv["number"]}</a>' if pv else "<span></span>")
                    + (f'<a href="../{nx["number"]}/">Recital {nx["number"]} →</a>' if nx else "<span></span>")
                    + "</nav>")
        d = DIST / r["permalink"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(r["section_ref"], doc_layout(body, side_panel(doc)), rel, docs, doc_id), encoding="utf-8")

    # document browser
    groups: dict[str, dict[str, list]] = {}
    for a in parents:
        h = a["hierarchy"]
        chap = h[0] if len(h) > 1 else "Sections"
        sec = h[1] if len(h) > 2 else ""
        groups.setdefault(chap, {}).setdefault(sec, []).append(a)
    noun = "articles" if parents and parents[0]["kind"] == "article" else "sections"
    count = f"{len(parents)} {noun}" + (f" and {len(recitals)} recitals" if recitals else "")
    toc = [f'<h1>{e(doc["title"])}</h1>', source_block(doc),
           f'<p class="lede">{count}.' + (' <a href="#recitals">Jump to recitals</a>.' if recitals else "") + "</p>",
           '<div class="chapters">']
    prefix = doc["short_name"] + " "
    for chap, secs in groups.items():
        card = [f'<section class="chapter"><h2>{e(chap)}</h2>']
        for sec, items in secs.items():
            if sec:
                card.append(f"<h3>{e(sec)}</h3>")
            card.append("<ul class=toc>" + "".join(
                f'<li><a href="{a["permalink"]}">{e(a["section_ref"].removeprefix(prefix))}</a>'
                f'{e(a["heading"])}</li>' for a in items) + "</ul>")
        toc.append("".join(card) + "</section>")
    toc.append("</div>")
    if recitals:
        toc.append('<section class="chapter" id="recitals"><h2>Recitals</h2><p class="recs">'
                   + " ".join(f'<a href="{r["permalink"]}">{r["number"]}</a>' for r in recitals) + "</p></section>")
    (DIST / doc_id).mkdir(parents=True, exist_ok=True)
    (DIST / doc_id / "index.html").write_text(
        page(doc["title"], "\n".join(toc), "../", docs, doc_id), encoding="utf-8")


# ---------- home and build ----------

def build_home(docs: list) -> None:
    loaded = ", ".join(d["short_name"] for d in docs)
    examples = ["GDPR Article 30", "When is a data protection impact assessment required?",
                "What must a record of processing activities contain?", "lawful bases for processing",
                "1798.105", "What are the exceptions to the CCPA right to delete?",
                "What must a CCPA privacy notice include?", "Do I need a Do Not Sell link"]
    ex = " ".join(f'<button type="button" class="chip" data-q="{e(x)}">{e(x)}</button>' for x in examples)
    body = f"""<section class="hero">
<h1>Find the exact text of privacy law</h1>
<p class="lede">Search by citation or by question. Every result is the unmodified source text,
with its citation, version, and a link to the official source. Currently loaded: {e(loaded)}.</p>
<form id="search-form" role="search" autocomplete="off">
  <label for="q" class="vh">Search</label>
  <input id="q" type="search" autocomplete="off" name="q-not-saved" placeholder="Try &quot;GDPR Article 30&quot;, &quot;1798.105&quot; or &quot;right to erasure&quot;" autofocus>
  <button type="submit">Search</button>
</form>
<div class="examples"><span>Try:</span> {ex}</div>
</section>
<div id="status" role="status" aria-live="polite"></div>
<ol id="results" class="results"></ol>
<noscript><p>Search needs JavaScript. You can still browse the documents using the menu above.</p></noscript>
<script type="module" src="assets/search.js?v={VERSION}"></script>"""
    (DIST / "index.html").write_text(page("Quick Privacy Searches", body, "", docs, "search"), encoding="utf-8")


def export_synonyms() -> None:
    data = yaml.safe_load((ROOT / "synonyms.yaml").read_text(encoding="utf-8"))
    for g in data["synonyms"]:
        assert g["terms"] and g["expand"], f"empty synonym group: {g}"
    (DIST / "assets" / "synonyms.json").write_text(
        json.dumps({"synonyms": data["synonyms"], "jurisdictions": data["jurisdictions"]},
                   ensure_ascii=False), encoding="utf-8")


def build() -> None:
    global VERSION
    h = hashlib.sha256()
    for f in sorted(list((WEB / "assets").iterdir()) + [WEB / "vendor" / "minisearch.js"]):
        h.update(f.read_bytes())
    for f in sorted(PROCESSED.rglob("chunks.json")) + [ROOT / "synonyms.yaml"]:
        h.update(f.read_bytes())
    VERSION = h.hexdigest()[:10]
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    for f in (WEB / "assets").iterdir():
        if f.suffix == ".js":  # version module imports and data fetches so caches never go stale
            t = f.read_text(encoding="utf-8")
            for name in ("minisearch.js", "lookup.js"):
                t = t.replace(f'"./{name}"', f'"./{name}?v={VERSION}"')
            for name in ("search-data.json", "synonyms.json"):
                t = t.replace(f'"assets/{name}"', f'"assets/{name}?v={VERSION}"')
            (DIST / "assets" / f.name).write_text(t, encoding="utf-8")
        else:
            shutil.copy(f, DIST / "assets" / f.name)
    shutil.copy(WEB / "vendor" / "minisearch.js", DIST / "assets" / "minisearch.js")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    order = [d["doc_id"] for d in yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["documents"]]
    loaded = [d for d in order if (PROCESSED / d / "chunks.json").exists()]
    docs, by_id_all = [], {}
    for d in loaded:
        info = read_json(PROCESSED / d / "document.json")
        info.setdefault("short_name", d.upper())
        docs.append(info)
        for c in read_json(PROCESSED / d / "chunks.json"):
            by_id_all[c["chunk_id"]] = c
    in_refs: dict[str, set[str]] = {}   # which parents refer to each parent (across documents)
    for d in loaded:
        for r in read_json(PROCESSED / d / "crossrefs.json"):
            tid = r.get("to_chunk_id")
            if not tid or tid not in by_id_all:
                continue
            tgt, src = by_id_all[tid], by_id_all[r["from_chunk_id"]]
            tp = tgt["chunk_id"] if tgt["kind"] in PARENT_KINDS else tgt["parent_chunk_id"]
            sp = src["chunk_id"] if src["kind"] in PARENT_KINDS else (src["parent_chunk_id"] or src["chunk_id"])
            in_refs.setdefault(tp, set()).add(sp)
    for d in loaded:
        build_doc_pages(d, docs, by_id_all, in_refs)
    export_search.export()
    export_synonyms()
    build_home(docs)
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"site: {n} html pages -> {DIST}")


if __name__ == "__main__":
    build()
