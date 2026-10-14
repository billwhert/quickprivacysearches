"""Generate the static site (pages, assets, search data) from data/processed/."""
import hashlib
import html
import json
import shutil

import yaml

import compare
import export_search
import guided
import trust
from common import PROCESSED, ROOT, read_json

DIST = ROOT / "dist"
WEB = ROOT / "web"
e = html.escape

VERSION = "dev"  # set in build(): content hash used to bust browser caches
TOPICS: dict = {}   # topic id -> {label, parent}; set in build()
GUIDES: list = []   # guided topics shown on this build; set in build()
COMPARES: list = []  # comparison sets; set in build()
SITE: dict = {}      # site.yaml; set in build()
PARENT_KINDS = ("article", "section")

DISCLAIMER = ("Reference tool, not legal advice. Text is taken from the official source and shown "
              "unmodified; check the official source and version date before relying on it.")

def icon(paths: str) -> str:
    return ('<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>')


ICONS = {
    "search": icon('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
    "link": icon('<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/>'
                 '<path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>'),
    "guide": icon('<path d="M4 5h11a3 3 0 0 1 3 3v12H7a3 3 0 0 1-3-3z"/><path d="M8 9h6M8 13h5"/>'),
    "compare": icon('<rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="4" width="7" height="16" rx="1.5"/>'),
    "browse": icon('<path d="M4 4h6v16H4zM14 4h6v16h-6z"/><path d="M6.5 8h1M16.5 8h1"/>'),
    "arrow": icon('<path d="M5 12h14M13 6l6 6-6 6"/>'),
}
LOGO = ICONS["search"]


# ---------- shared page frame ----------

def page(title: str, body: str, rel: str, nav_docs: list, active: str = "", desc: str = "") -> str:
    description = " ".join((desc or SITE.get("description", "")).split())
    nav = [("Search", rel, "search")]
    if GUIDES:
        nav.append(("Guides", f"{rel}topics/", "guides"))
    if COMPARES:
        nav.append(("Compare", f"{rel}compare/", "compare"))
    nav.append(("Browse", f"{rel}documents/", "browse"))
    if active in ("about", "disclaimer", "sources"):
        active = ""
    elif active not in ("search", "guides", "compare", ""):
        active = "browse"
    links = " ".join(
        f'<a href="{href}"{" aria-current=page" if key == active else ""}>{e(label)}</a>'
        for label, href, key in nav)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE.get("name", ""))}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="{rel}assets/style.css?v={VERSION}">
</head><body>
<header class="site"><div class="wrap">
<a class="brand" href="{rel}"><span class="brand-mark">{LOGO}</span>Quick Privacy Searches</a><nav aria-label="Main">{links}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<script type="module" src="{rel}assets/page.js?v={VERSION}"></script>
<footer class="site"><div class="wrap">
<div class="foot-about"><p class="foot-brand">Quick Privacy Searches</p>
<p>{e(DISCLAIMER)}</p>
<p>No accounts, no tracking. Searches run in your browser and are never sent anywhere.</p></div>
<div><h2>Explore</h2><ul><li><a href="{rel}">Search</a></li>{'<li><a href="' + rel + 'topics/">Guided topics</a></li>' if GUIDES else ''}
{'<li><a href="' + rel + 'compare/">Compare</a></li>' if COMPARES else ''}<li><a href="{rel}documents/">Browse the laws</a></li></ul></div>
<div><h2>About</h2><ul><li><a href="{rel}about/">About</a></li><li><a href="{rel}sources/">Sources</a></li>
<li><a href="{rel}disclaimer/">Disclaimer and privacy notice</a></li>
<li><a href="{e(trust.report_url(SITE))}">Report an error</a></li><li><a href="{e(SITE.get('repo', '#'))}">Repository</a></li></ul></div>
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


def side_panel(doc: dict, nav_title: str = "", nav_items: list = None, src: str = "", ref: str = "",
               permalink: str = "") -> str:
    out = ['<aside class="side">',
           '<div class="side-card"><h3>Source</h3>',
           f'<p><a href="{e(src or doc["source_url"])}">Official text</a></p>',
           f'<p class="muted">{e(doc["version_label"])}<br>Retrieved {e(doc["retrieved_at"][:10])}</p></div>']
    if nav_items:
        out.append(f'<div class="side-card"><h3>{e(nav_title)}</h3><ul class="side-nav">'
                   + "".join(f'<li><a href="#{a}">{e(t)}</a></li>' for a, t in nav_items) + "</ul></div>")
    report = (f'<p class="side-link"><a href="{e(trust.report_url(SITE, ref, permalink))}">Report an error '
              f'in this provision</a></p>') if ref else ""
    out.append(f'<p class="side-link"><a href="../../">All {e(doc["short_name"])} provisions</a></p>{report}</aside>')
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
        parts = [f'<header class="doc-head"><p class="crumbs"><span class="badge">{e(doc["short_name"])}</span> {e(crumbs)}</p>',
                 f'<h1>{e(a["section_ref"])}{h1_sub}</h1></header>']
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
            have = [t for t in c.get("topics", []) if t in TOPICS]
            shadowed = {TOPICS[t]["parent"] for t in have if TOPICS[t]["parent"]}
            tags = [t for t in have if t not in shadowed]   # a sub-topic replaces its parent
            tag_html = ('<p class="tags">' + "".join(f'<span class="tag">{e(TOPICS[t]["label"])}</span>'
                                                    for t in tags[:4]) + "</p>") if tags else ""
            anchor = (f'<div class="prov-head"><a class="anchor" href="#{frag}" title="Permalink">{e(label)}</a>'
                      f'<button type="button" class="copy-link icon-btn" data-frag="{frag}" title="Copy link" '
                      f'aria-label="Copy link to {e(label)}">{ICONS["link"]}</button></div>'
                      if label and frag else "")
            id_attr = f' id="{frag}"' if frag else ""
            parts.append(f'<section class="prov"{id_attr}>'
                         f'{anchor}{tag_html}{lead}<div class="text">{render_text(c["text"])}</div>{cite_html}</section>')
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
            page(title, doc_layout(parts, side_panel(doc, nav_title, nav_items, a["source_url"], a["section_ref"], a["permalink"])), rel, docs, doc_id,
                 desc=f'{a["section_ref"]}{": " + a["heading"] if a["heading"] else ""}. Exact text with its citation, '
                      f'version date and a link to the official source.'),
            encoding="utf-8")

    for i, r in enumerate(recitals):
        rel = depth_rel(r["permalink"])
        cites = out_refs.get(r["chunk_id"], [])
        body = [f'<header class="doc-head"><p class="crumbs"><span class="badge">{e(doc["short_name"])}</span> Recitals</p>',
                f'<h1>{e(r["section_ref"])}</h1></header>',
                f'<section class="prov"><div class="prov-head"><span class="anchor">Recital {r["number"]}</span>'
                f'<button type="button" class="copy-link icon-btn" data-frag="" title="Copy link" '
                f'aria-label="Copy link to this recital">{ICONS["link"]}</button></div>'
                f'<div class="text">{render_text(r["text"])}</div>'
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
            page(r["section_ref"], doc_layout(body, side_panel(doc, ref=r["section_ref"], permalink=r["permalink"])),
                 rel, docs, doc_id), encoding="utf-8")

    # document browser
    groups: dict[str, dict[str, list]] = {}
    for a in parents:
        h = a["hierarchy"]
        chap = h[0] if len(h) > 1 else "Sections"
        sec = h[1] if len(h) > 2 else ""
        groups.setdefault(chap, {}).setdefault(sec, []).append(a)
    noun = "articles" if parents and parents[0]["kind"] == "article" else "sections"
    count = f"{len(parents)} {noun}" + (f" and {len(recitals)} recitals" if recitals else "")
    toc = [f'<header class="doc-head"><p class="eyebrow">{e(doc["short_name"])}</p><h1>{e(doc["title"])}</h1>',
           f'<p class="lede">{count}.' + (' <a href="#recitals">Jump to recitals</a>.' if recitals else "") + "</p>",
           source_block(doc) + "</header>",
           f'<p><a class="btn-link" href="../{parents[0]["permalink"]}">Start reading at {e(parents[0]["section_ref"])} '
           f'{ICONS["arrow"]}</a></p>',
           f'<div class="tocbar">{ICONS["search"]}<label for="toc-filter" class="vh">Find a section</label>'
           '<input id="toc-filter" type="search" autocomplete="off" '
           'placeholder="Find a section by number or word"></div>',
           '<p id="toc-empty" class="muted" hidden>No section matches that.</p>',
           '<div class="chapters">']
    prefix = doc["short_name"] + " "
    for chap, secs in groups.items():
        card = [f'<section class="chapter"><h2>{e(chap)}</h2>']
        for sec, items in secs.items():
            if sec:
                card.append(f"<h3>{e(sec)}</h3>")
            def find_text(a):
                """Paragraph headings and defined terms inside a section, so the finder can reach them."""
                seen, out = set(), []
                for cid in a["child_chunk_ids"]:
                    c = by_id_all[cid]
                    for t in (c.get("subheading"), c.get("defined_term")):
                        if t and t not in seen:
                            seen.add(t)
                            out.append(t)
                return " ".join(out)
            card.append("<ul class=toc>" + "".join(
                f'<li data-find="{e(find_text(a))}"><a href="../{a["permalink"]}">'
                f'{e(a["section_ref"].removeprefix(prefix))}</a>{e(a["heading"])}</li>' for a in items) + "</ul>")
        toc.append("".join(card) + "</section>")
    toc.append("</div>")
    if recitals:
        toc.append('<section class="chapter" id="recitals"><h2>Recitals</h2><p class="recs">'
                   + " ".join(f'<a href="../{r["permalink"]}">{r["number"]}</a>' for r in recitals) + "</p></section>")
    (DIST / doc_id).mkdir(parents=True, exist_ok=True)
    (DIST / doc_id / "index.html").write_text(
        page(doc["title"], "\n".join(toc), "../", docs, doc_id), encoding="utf-8")


# ---------- guided topics ----------

def guide_card(t: dict, rel: str) -> str:
    state, _ = guided.review_state(t, BY_ID)
    badge = {"draft": '<span class="badge warn">Draft - awaiting review</span>',
             "needs-review": '<span class="badge warn">Needs review</span>'}.get(state, "")
    return (f'<article class="doc-card"><div class="result-head"><span class="badge">Guided topic</span>{badge}</div>'
            f'<h2><a href="{rel}topics/{e(t["id"])}/">{e(t["title"])}</a></h2>'
            f'<p class="muted">{e(t["scope"])}</p>'
            f'<p class="actions"><a href="{rel}topics/{e(t["id"])}/">Open the research path</a></p></article>')


BY_ID: dict = {}


def provision_card(cid: str, rel: str, docs_by_id: dict) -> str:
    c = BY_ID[cid]
    d = docs_by_id[c["doc_id"]]
    link = f'{rel}{c["permalink"]}'
    lead = f'<p class="lead-in"><span>Context:</span> {e(c["lead_in"])}</p>' if c.get("lead_in") else ""
    crumbs = " › ".join(c["hierarchy"][:-1])
    frag = fragment(c["permalink"])
    return (f'<section class="prov pc"><p class="pc-ref"><a href="{link}">{e(c["section_ref"])}</a></p>'
            f'<p class="crumbs">{e(crumbs)}</p>{lead}'
            f'<div class="clampable"><div class="text">{render_text(c["text"])}</div></div>'
            f'<p class="pc-foot"><a href="{link}">Read in context</a>'
            f'<a href="{e(c["source_url"])}" target="_blank" rel="noopener noreferrer">Official source</a></p>'
            f'<p class="meta">{e(d["version_label"])} · retrieved {e(d["retrieved_at"][:10])}</p>'
            f'</section>')


def build_guides(docs: list, by_id_all: dict) -> None:
    BY_ID.update(by_id_all)
    docs_by_id = {d["doc_id"]: d for d in docs}
    if not GUIDES:
        (DIST / "assets" / "topics.json").write_text(json.dumps({"topics": []}), encoding="utf-8")
        return
    index = {t["id"]: t for t in GUIDES}
    summary = []
    for t in GUIDES:
        rel = "../../"
        state, changed = guided.review_state(t, by_id_all)
        banner = ""
        if state == "draft":
            banner = ('<div class="banner draft"><strong>Draft.</strong> This provision list has not yet been reviewed. '
                      'It is shown for review only.</div>')
        elif state == "needs-review":
            banner = (f'<div class="banner draft"><strong>Needs review.</strong> {len(changed)} cited provision(s) '
                      f'changed since this topic was last reviewed.</div>')
        cited = guided.cited_ids(t)
        law_names = sorted({docs_by_id[BY_ID[c]["doc_id"]]["short_name"] for c in cited})
        parts = [f'<header class="doc-head"><p class="eyebrow">Guided topic</p>',
                 f'<h1>{e(t["title"])}</h1>', f'<p class="lede">{e(t["scope"])}</p>',
                 f'<p class="stat-line"><span>{len(t["items"])} steps</span><span>{len(cited)} provisions</span>'
                 f'<span>{e(", ".join(law_names))}</span></p></header>', banner]
        if t.get("reviewed_at"):
            parts.append(f'<p class="muted">Provision list reviewed {e(str(t["reviewed_at"]))}'
                         f'{" by " + e(t["reviewed_by"]) if t.get("reviewed_by") else ""}.</p>')
        nav_items = []
        if t.get("applicability"):
            parts.append('<h2 id="applies">Does the law apply at all?</h2>')
            nav_items.append(("applies", "Does the law apply?"))
            for i, q in enumerate(t["applicability"], 1):
                parts.append(f'<div class="q"><h3>{e(q["question"])}</h3>')
                if q.get("note"):
                    parts.append(f'<p class="summary"><span class="badge kind">Summary</span> {e(q["note"])}</p>')
                parts += [provision_card(cid, rel, docs_by_id) for cid in q["chunk_ids"]]
                parts.append("</div>")
        parts.append('<h2 id="provisions">What the provisions say</h2>')
        nav_items.append(("provisions", "What the provisions say"))
        parts.append('<ol class="checklist">')
        for i, it in enumerate(t["items"], 1):
            parts.append(f'<li id="item-{i}"><h3>{e(it["label"])}</h3>')
            if it.get("summary"):
                parts.append(f'<p class="summary"><span class="badge kind">Summary</span> {e(it["summary"])}</p>')
            parts += [provision_card(cid, rel, docs_by_id) for cid in it["chunk_ids"]]
            parts.append("</li>")
            nav_items.append((f"item-{i}", f"{i}. {it['label']}"))
        parts.append("</ol>")
        if t.get("related"):
            parts.append('<h2 id="related">Related</h2><ul class="related">')
            nav_items.append(("related", "Related"))
            for r in t["related"]:
                href = ""
                if r.get("topic") and r["topic"] in index:
                    href = f'{rel}topics/{r["topic"]}/'
                line = f'<a href="{href}">{e(r["label"])}</a>' if href else e(r["label"])
                if r.get("chunk_ids"):
                    line += " " + ", ".join(
                        f'<a href="{rel}{BY_ID[c]["permalink"]}">{e(BY_ID[c]["section_ref"])}</a>' for c in r["chunk_ids"])
                parts.append(f"<li>{line}</li>")
            parts.append("</ul>")
        parts.append(f'<p class="disclaimer">{e(guided.DISCLAIMER)}</p>')
        side = ('<aside class="side"><div class="side-card"><h3>On this page</h3><ul class="side-nav">'
                + "".join(f'<li><a href="#{a}">{e(l)}</a></li>' for a, l in nav_items) + "</ul></div>"
                '<p class="side-link"><a href="../">All guided topics</a></p></aside>')
        d = DIST / "topics" / t["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            page(t["title"], doc_layout(parts, side), rel, docs, "guides", desc=t["scope"]), encoding="utf-8")
        summary.append({
            "id": t["id"], "title": t["title"], "scope": t["scope"], "url": f'topics/{t["id"]}/',
            "triggers": t["triggers"], "docs": t.get("docs", []), "state": state,
            "applicability": [q["question"] for q in t.get("applicability", [])],
        })
    (DIST / "topics").mkdir(parents=True, exist_ok=True)
    body = ('<h1>Guided topics</h1><p class="lede">Hand-built research paths. Each gathers the provisions that bear on a '
            'common question, with exact text, citations and version dates. They describe what the law says; they '
            'are not advice.</p><div class="doc-grid">' + "".join(guide_card(t, "../") for t in GUIDES) + "</div>")
    (DIST / "topics" / "index.html").write_text(page("Guided topics", body, "../", docs, "guides"), encoding="utf-8")
    (DIST / "assets" / "topics.json").write_text(json.dumps({"topics": summary}, ensure_ascii=False), encoding="utf-8")


# ---------- compare ----------

def build_compare(docs: list, by_id_all: dict) -> None:
    if not COMPARES:
        return
    BY_ID.update(by_id_all)
    docs_by_id = {d["doc_id"]: d for d in docs}
    for s in COMPARES:
        rel = "../../"
        cols = s["columns"]
        toggles = "".join(
            f'<button type="button" class="fchip" aria-pressed="true" data-col="{e(c["doc"])}">'
            f'{e(docs_by_id[c["doc"]]["short_name"])}</button>' for c in cols)
        grid = []
        for c in cols:
            d = docs_by_id[c["doc"]]
            note = (f'<p class="summary"><span class="badge kind">Note</span> {e(" ".join(c["note"].split()))}</p>'
                    if c.get("note") else "")
            grid.append(
                f'<div class="cmp-col" data-col="{e(c["doc"])}"><div class="cmp-head">'
                f'<span class="badge">{e(d["short_name"])}</span><h2>{e(c["heading"])}</h2></div>{note}'
                + "".join(provision_card(cid, rel, docs_by_id) for cid in c["chunk_ids"]) + "</div>")
        parts = ['<p class="crumbs"><span class="badge">Compare</span></p>',
                 f'<h1>{e(s["title"])}</h1>', f'<p class="lede">{e(s["question"])}</p>',
                 '<div class="cmp-toggles"><span class="label">Show</span>' + toggles + "</div>",
                 f'<div class="cmp-grid" style="--cols:{len(cols)}">{"".join(grid)}</div>',
                 '<p class="disclaimer">The provisions are placed side by side as an editorial selection. That is not '
                 'a statement that they are equivalent or that they cover the same situations. The text is shown '
                 'exactly as published; check each provision\'s version date and official source.</p>']
        d = DIST / "compare" / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page(s["title"], "\n".join(parts), rel, docs, "compare", desc=s["question"]), encoding="utf-8")
    cards = "".join(
        f'<article class="doc-card"><div class="result-head">'
        + "".join(f'<span class="badge kind">{e(docs_by_id[c["doc"]]["short_name"])}</span>' for c in s["columns"])
        + f'</div><h2><a href="{e(s["id"])}/">{e(s["title"])}</a></h2><p class="muted">{e(s["question"])}</p>'
        f'<p class="actions"><a href="{e(s["id"])}/">Compare side by side</a></p></article>' for s in COMPARES)
    body = ('<h1>Compare the laws</h1><p class="lede">The same question, answered by each law, side by side. '
            'Pick a comparison; you can hide the laws you do not need.</p>'
            f'<div class="doc-grid">{cards}</div>')
    (DIST / "compare" / "index.html").write_text(page("Compare the laws", body, "../", docs, "compare"), encoding="utf-8")


# ---------- trust pages ----------

def build_trust(docs: list, by_id_all: dict) -> None:
    counts = {}
    for d in docs:
        own = [c for c in by_id_all.values() if c["doc_id"] == d["doc_id"]]
        parents = [c for c in own if c["kind"] in PARENT_KINDS]
        noun = "articles" if parents and parents[0]["kind"] == "article" else "sections"
        n_rec = sum(1 for c in own if c["kind"] == "recital")
        counts[d["doc_id"]] = f"{len(parents)} {noun}" + (f", {n_rec} recitals" if n_rec else "")
    for slug, title, body in [
        ("about", "About", trust.about_body(SITE, docs, counts)),
        ("disclaimer", "Disclaimer and privacy notice", trust.disclaimer_body(SITE)),
        ("sources", "Sources", trust.sources_body(SITE, docs, counts)),
    ]:
        d = DIST / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page(title, f'<div class="prose">{body}</div>', "../", docs, slug),
                                      encoding="utf-8")


# ---------- 404 and sitemap ----------

def build_extras(docs: list) -> None:
    base = "/" + SITE["site_url"].split("//", 1)[1].split("/", 1)[1] if "/" in SITE["site_url"].split("//", 1)[1] else "/"
    body = ('<div class="prose"><h1>Page not found</h1><p class="lede">That address does not exist on this site. '
            'It may have been mistyped, or a link may be out of date.</p>'
            f'<p><a class="btn-link" href="{base}">Search the laws</a> '
            f'<a class="btn-link" href="{base}documents/">Browse</a></p></div>')
    (DIST / "404.html").write_text(page("Page not found", body, base, docs, ""), encoding="utf-8")
    urls = [p.parent.relative_to(DIST).as_posix() for p in DIST.rglob("index.html")]
    root = SITE["site_url"].rstrip("/") + "/"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in sorted(urls):
        lines.append(f"<url><loc>{e(root + ('' if u == '.' else u + '/'))}</loc></url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------- home and build ----------

def build_home(docs: list) -> None:
    loaded = ", ".join(d["short_name"] for d in docs)
    examples = ["GDPR Article 30", "When is a DPIA required?", "1798.105", "Do I need a Do Not Sell link",
                "HIPAA minimum necessary", "breach notification timelines"]
    sep = '<span class="sep" aria-hidden="true">·</span>'
    ex = sep.join(f'<button type="button" data-q="{e(x)}">{e(x)}</button>' for x in examples)
    features = []
    if GUIDES:
        features.append(("topics/", "guide", "Guided topics",
                         "Research paths for common questions, with every relevant provision in order."))
    if COMPARES:
        features.append(("compare/", "compare", "Compare the laws",
                         "The same question answered by each law, side by side."))
    features.append(("documents/", "browse", "Browse the laws",
                     "Read any law in order, or jump to a section by number or keyword."))
    feature_html = "".join(
        f'<a class="feature" href="{href}"><span class="fi">{ICONS[ic]}</span><h3>{e(t)}</h3><p>{e(d)}</p>'
        f'<span class="more">Open {ICONS["arrow"]}</span></a>' for href, ic, t, d in features)
    laws = "".join(
        f'<a class="feature" href="{e(d["doc_id"])}/"><span class="badge">{e(d["short_name"])}</span>'
        f'<h3 style="margin-top:.8rem">{e(d["title"])}</h3><p>{e(d["version_label"])}</p></a>' for d in docs)
    body = f"""<section class="hero">
<p class="eyebrow">Free privacy law reference</p>
<h1>Find the exact text of privacy law</h1>
<p class="lede">Search by citation or plain question. Every result is the official wording, with its citation,
version date and a link to the source. Covering {e(loaded)}.</p>
<form id="search-form" role="search" autocomplete="off" class="search-box">
  <label for="q" class="vh">Search privacy law</label>
  {ICONS["search"]}
  <input id="q" type="search" autocomplete="off" name="q-not-saved" placeholder="Try &quot;right to erasure&quot; or &quot;164.502(b)&quot;" autofocus>
  <button type="submit">Search</button>
</form>
<div class="suggest examples">Try {ex}</div>
</section>
<section id="results-area" class="results-area" hidden>
  <div id="topic-cards" class="topic-cards"></div>
  <div class="toolbar">
    <div id="status" role="status" aria-live="polite"></div>
    <div class="filter-wrap" id="filter-wrap"></div>
  </div>
  <div id="pills" class="pills"></div>
  <ol id="results" class="results"></ol>
  <div id="more" class="more-results"></div>
</section>
<div id="home-sections" class="home-sections">
  <section><div class="section-head"><h2>Explore</h2></div><div class="feature-grid">{feature_html}</div></section>
  <section><div class="section-head"><h2>Laws included</h2><a href="sources/">Where the texts come from</a></div>
  <div class="feature-grid">{laws}</div></section>
</div>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<noscript><p>Search needs JavaScript. You can still browse the laws from the menu above.</p></noscript>
<script type="module" src="assets/search.js?v={VERSION}"></script>"""
    (DIST / "index.html").write_text(page("Quick Privacy Searches", body, "", docs, "search"), encoding="utf-8")


def build_documents(docs: list, by_id_all: dict) -> None:
    cards = []
    type_label = {"law": "Statute", "regulation": "Regulation", "guidance": "Guidance"}
    for d in docs:
        own = [c for c in by_id_all.values() if c["doc_id"] == d["doc_id"]]
        parents = [c for c in own if c["kind"] in PARENT_KINDS]
        recitals = [c for c in own if c["kind"] == "recital"]
        noun = "articles" if parents and parents[0]["kind"] == "article" else "sections"
        size = f"{len(parents)} {noun}" + (f", {len(recitals)} recitals" if recitals else "")
        cards.append(
            f'<li class="doc-card"><div class="result-head">'
            f'<span class="badge">{e(d["short_name"])}</span>'
            f'<span class="badge kind">{e(type_label.get(d["doc_type"], d["doc_type"]))}</span>'
            f'<span class="badge kind">{e(d["jurisdiction"])}</span></div>'
            f'<h2><a href="../{d["doc_id"]}/">{e(d["title"])}</a></h2>'
            f'<p class="muted">{e(d["version_label"])}<br>Retrieved {e(d["retrieved_at"][:10])} · {e(size)}</p>'
            f'<p class="actions"><a href="../{d["doc_id"]}/">Read it</a>'
            f'<a href="{e(d["source_url"])}">Official source</a></p></li>')
    body = ('<h1>Browse the laws</h1><p class="lede">Read any loaded law in order, find a section by number or '
            'word, and copy a link to any provision. Every provision page shows its version and retrieval date.</p>'
            f'<ul class="doc-grid">{"".join(cards)}</ul>')
    d = DIST / "documents"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(page("Browse the laws", body, "../", docs, "browse"), encoding="utf-8")


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
            for name in ("search-data.json", "synonyms.json", "topics.json"):
                t = t.replace(f'"assets/{name}"', f'"assets/{name}?v={VERSION}"')
            (DIST / "assets" / f.name).write_text(t, encoding="utf-8")
        else:
            shutil.copy(f, DIST / "assets" / f.name)
    shutil.copy(WEB / "vendor" / "minisearch.js", DIST / "assets" / "minisearch.js")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")

    SITE.clear()
    SITE.update(yaml.safe_load((ROOT / "site.yaml").read_text(encoding="utf-8")))
    TOPICS.clear()
    for t in yaml.safe_load((ROOT / "taxonomy" / "topics.yaml").read_text(encoding="utf-8"))["topics"]:
        TOPICS[t["id"]] = {"label": t["label"], "parent": t.get("parent")}
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
    guided_errors = guided.validate(guided.load_topics(), by_id_all)
    if guided_errors:
        raise SystemExit("Guided topics are inconsistent:\n  " + "\n  ".join(guided_errors))
    sets_all = compare.load_sets()
    compare_errors = compare.validate(sets_all, by_id_all, {d["doc_id"] for d in docs})
    if compare_errors:
        raise SystemExit("Comparison sets are inconsistent:\n  " + "\n  ".join(compare_errors))
    COMPARES.clear()
    COMPARES.extend(sets_all)
    topics_all = guided.load_topics()
    BY_ID.update(by_id_all)
    GUIDES.clear()
    GUIDES.extend(t for t in topics_all if guided.visible(t))
    names = ", ".join(d["short_name"] for d in docs)
    SITE["description"] = (f"Search the exact text of privacy law ({names}) with citations, version dates and links "
                           "to the official sources. Free, no accounts, no tracking.")
    for d in loaded:
        build_doc_pages(d, docs, by_id_all, in_refs)
    export_search.export()
    export_synonyms()
    build_home(docs)
    build_documents(docs, by_id_all)
    build_guides(docs, by_id_all)
    build_compare(docs, by_id_all)
    build_trust(docs, by_id_all)
    build_extras(docs)
    guided.write_review_sheet(topics_all, by_id_all, {d["doc_id"]: d for d in docs})
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"site: {n} html pages -> {DIST}")


if __name__ == "__main__":
    build()
