"""Generate the static site (pages, assets, search data) from data/processed/."""
import hashlib
import html
import shutil

from common import PROCESSED, ROOT, read_json
import export_search

DIST = ROOT / "dist"
WEB = ROOT / "web"
e = html.escape

VERSION = "dev"  # set in build(): content hash used to bust browser caches

DISCLAIMER = ("Reference tool, not legal advice. Text is taken from the official source and shown "
              "unmodified; check the official source and version date before relying on it.")


LOGO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg>')


def page(title: str, body: str, rel: str, active: str = "") -> str:
    nav = [("Search", f"{rel}", "search"), ("GDPR", f"{rel}gdpr/", "gdpr")]
    links = " ".join(
        f'<a href="{href}"{" aria-current=page" if key == active else ""}>{label}</a>'
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


def side_panel(doc: dict, doc_id: str, nav_title: str = "", nav_items: list = None) -> str:
    out = ['<aside class="side">',
           '<div class="side-card"><h3>Source</h3>',
           f'<p><a href="{e(doc["source_url"])}">Official text</a></p>',
           f'<p class="muted">{e(doc["version_label"])}<br>Retrieved {e(doc["retrieved_at"][:10])}</p></div>']
    if nav_items:
        out.append(f'<div class="side-card"><h3>{e(nav_title)}</h3><ul class="side-nav">'
                   + "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in nav_items) + "</ul></div>")
    out.append(f'<p class="side-link"><a href="../../">All {e(doc_id.upper())} provisions</a></p></aside>')
    return "".join(out)


def build_doc_pages(doc_id: str) -> None:
    pdir = PROCESSED / doc_id
    doc = read_json(pdir / "document.json")
    chunks = read_json(pdir / "chunks.json")
    refs = read_json(pdir / "crossrefs.json")
    by_id = {c["chunk_id"]: c for c in chunks}
    out_refs: dict[str, list[str]] = {}
    in_refs: dict[str, set[str]] = {}
    for r in refs:
        if r["to_chunk_id"]:
            out_refs.setdefault(r["from_chunk_id"], [])
            if r["to_chunk_id"] not in out_refs[r["from_chunk_id"]]:
                out_refs[r["from_chunk_id"]].append(r["to_chunk_id"])
            tgt = by_id[r["to_chunk_id"]]
            art_id = tgt["chunk_id"] if tgt["kind"] == "article" else tgt["parent_chunk_id"]
            src = by_id[r["from_chunk_id"]]
            src_art = src["chunk_id"] if src["kind"] == "article" else src["parent_chunk_id"]
            in_refs.setdefault(art_id, set()).add(src_art or src["chunk_id"])

    def link(rel: str, cid: str) -> str:
        c = by_id[cid]
        return f'<a href="{rel}{c["permalink"]}">{e(c["section_ref"])}</a>'

    arts = sorted((c for c in chunks if c["kind"] == "article"), key=lambda c: c["number"])
    rcts = sorted((c for c in chunks if c["kind"] == "recital"), key=lambda c: c["number"])

    for i, a in enumerate(arts):
        rel = "../../../"
        parts = [f'<p class="crumbs"><span class="badge">{e(doc_id.upper())}</span> '
                 f'{e(" › ".join(a["hierarchy"][:-1]))}</p>',
                 f'<h1>{e(a["section_ref"])}<span class="sub">{e(a["heading"])}</span></h1>']
        nav_items = []
        for cid in a["child_chunk_ids"]:
            c = by_id[cid]
            n = c["number"]
            label = (f"Definition ({n})" if c["kind"] == "definition"
                     else (f"Paragraph {n}" if not c.get("unnumbered") else ""))
            cites = out_refs.get(cid, [])
            cite_html = ""
            if cites:
                cite_html = ('<p class="refs">References: '
                             + ", ".join(link(rel, t) for t in cites) + "</p>")
            if label:
                nav_items.append((f"p{n}", label))
            parts.append(
                f'<section class="prov" id="p{n}">'
                + (f'<a class="anchor" href="#p{n}" title="Permalink">{e(label)}</a>' if label else "")
                + f'<div class="text">{render_text(c["text"])}</div>{cite_html}</section>')
        notes = a["footnotes"]
        if notes:
            parts.append('<section class="notes"><h2>Notes</h2><ol>'
                         + "".join(f'<li>{e(f["text"])}</li>' for f in notes) + "</ol></section>")
        cited_by = sorted(in_refs.get(a["chunk_id"], set()) - {a["chunk_id"]})
        if cited_by:
            parts.append('<p class="refs">Referred to in: '
                         + ", ".join(link(rel, t) for t in cited_by if t in by_id) + "</p>")
        prev_a = arts[i - 1] if i else None
        next_a = arts[i + 1] if i + 1 < len(arts) else None
        pn = "<nav class=pager>"
        pn += f'<a href="../{prev_a["number"]}/">← {e(prev_a["section_ref"])}</a>' if prev_a else "<span></span>"
        pn += f'<a href="../{next_a["number"]}/">{e(next_a["section_ref"])} →</a>' if next_a else "<span></span>"
        parts.append(pn + "</nav>")
        d = DIST / doc_id / "art" / str(a["number"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(f'{a["section_ref"]} - {a["heading"]}',
                 doc_layout(parts, side_panel(doc, doc_id, "In this article", nav_items)),
                 rel, doc_id), encoding="utf-8")

    for i, r in enumerate(rcts):
        rel = "../../../"
        cites = out_refs.get(r["chunk_id"], [])
        body = [f'<p class="crumbs"><span class="badge">{e(doc_id.upper())}</span> Recitals</p>',
                f'<h1>{e(r["section_ref"])}</h1>',
                f'<section class="prov"><div class="text">{render_text(r["text"])}</div>'
                + ('<p class="refs">References: ' + ", ".join(link(rel, t) for t in cites) + "</p>" if cites else "")
                + "</section>"]
        if r["footnotes"]:
            body.append('<section class="notes"><h2>Notes</h2><ol>'
                        + "".join(f'<li>{e(f["text"])}</li>' for f in r["footnotes"]) + "</ol></section>")
        pv = rcts[i - 1] if i else None
        nx = rcts[i + 1] if i + 1 < len(rcts) else None
        body.append("<nav class=pager>"
                    + (f'<a href="../{pv["number"]}/">← Recital {pv["number"]}</a>' if pv else "<span></span>")
                    + (f'<a href="../{nx["number"]}/">Recital {nx["number"]} →</a>' if nx else "<span></span>")
                    + "</nav>")
        d = DIST / doc_id / "rct" / str(r["number"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(r["section_ref"], doc_layout(body, side_panel(doc, doc_id)), rel, doc_id), encoding="utf-8")

    # document browser
    groups: dict[str, dict[str, list]] = {}
    for a in arts:
        h = a["hierarchy"]
        chap = h[0]
        sec = h[1] if len(h) > 2 else ""
        groups.setdefault(chap, {}).setdefault(sec, []).append(a)
    toc = [f'<h1>{e(doc["title"])}</h1>', source_block(doc),
           f'<p class="lede">{len(arts)} articles and {len(rcts)} recitals. <a href="#recitals">Jump to recitals</a>.</p>',
           '<div class="chapters">']
    for chap, secs in groups.items():
        card = [f'<section class="chapter"><h2>{e(chap)}</h2>']
        for sec, items in secs.items():
            if sec:
                card.append(f"<h3>{e(sec)}</h3>")
            card.append("<ul class=toc>" + "".join(
                f'<li><a href="art/{a["number"]}/">Art. {a["number"]}</a> {e(a["heading"])}</li>'
                for a in items) + "</ul>")
        toc.append("".join(card) + "</section>")
    toc.append("</div>")
    toc.append('<section class="chapter" id="recitals"><h2>Recitals</h2><p class="recs">'
               + " ".join(f'<a href="rct/{r["number"]}/">{r["number"]}</a>' for r in rcts) + "</p></section>")
    (DIST / doc_id).mkdir(parents=True, exist_ok=True)
    (DIST / doc_id / "index.html").write_text(
        page(f'{doc["title"]}', "\n".join(toc), "../", doc_id), encoding="utf-8")


def build_home() -> None:
    examples = ["GDPR Article 30", "When is a data protection impact assessment required?",
                "What must a record of processing activities contain?",
                "lawful bases for processing", "right to erasure", "Recital 26"]
    ex = " ".join(f'<button type="button" class="chip" data-q="{e(x)}">{e(x)}</button>' for x in examples)
    body = f"""<section class="hero">
<h1>Find the exact text of privacy law</h1>
<p class="lede">Search by citation or by question. Every result is the unmodified source text,
with its citation, version, and a link to the official source. Currently loaded: the GDPR.</p>
<form id="search-form" role="search" autocomplete="off">
  <label for="q" class="vh">Search</label>
  <input id="q" type="search" autocomplete="off" name="q-not-saved" placeholder="Try &quot;GDPR Article 30&quot; or &quot;right to erasure&quot;" autofocus>
  <button type="submit">Search</button>
</form>
<div class="examples"><span>Try:</span> {ex}</div>
</section>
<div id="status" role="status" aria-live="polite"></div>
<ol id="results" class="results"></ol>
<noscript><p>Search needs JavaScript. You can still <a href="gdpr/">browse the GDPR</a>.</p></noscript>
<script type="module" src="assets/search.js?v={VERSION}"></script>"""
    (DIST / "index.html").write_text(page("Quick Privacy Searches", body, "", "search"), encoding="utf-8")


def export_synonyms() -> None:
    import json
    import yaml
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
        if f.suffix == ".js":  # version module imports and the data fetch so caches never go stale
            t = f.read_text(encoding="utf-8")
            for name in ("minisearch.js", "lookup.js"):
                t = t.replace(f'"./{name}"', f'"./{name}?v={VERSION}"')
            t = t.replace('"assets/search-data.json"', f'"assets/search-data.json?v={VERSION}"')
            t = t.replace('"assets/synonyms.json"', f'"assets/synonyms.json?v={VERSION}"')
            (DIST / "assets" / f.name).write_text(t, encoding="utf-8")
        else:
            shutil.copy(f, DIST / "assets" / f.name)
    shutil.copy(WEB / "vendor" / "minisearch.js", DIST / "assets" / "minisearch.js")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    for d in sorted(PROCESSED.iterdir()):
        if (d / "chunks.json").exists():
            build_doc_pages(d.name)
    export_search.export()
    export_synonyms()
    build_home()
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"site: {n} html pages -> {DIST}")


if __name__ == "__main__":
    build()
