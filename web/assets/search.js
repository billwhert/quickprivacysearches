// Search page: runs entirely in the browser. No network calls except loading the
// static data and library files from this same site; query text is never sent anywhere.
import MiniSearch from "./minisearch.js";
import { createEngine, search, stem, STOPWORDS, normalize, docsForFilters, matchTopics } from "./lookup.js";

const $ = id => document.getElementById(id);
const input = $("q"), form = $("search-form"), statusEl = $("status"), list = $("results");
const area = $("results-area"), home = $("home-sections"), topicBox = $("topic-cards");
const filterWrap = $("filter-wrap"), pillsEl = $("pills"), moreEl = $("more"), toastEl = $("toast");
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const PAGE = 20;

const svg = p => `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const I = {
  filter: svg('<path d="M4 6h16M7 12h10M10 18h4"/>'),
  x: svg('<path d="M18 6 6 18M6 6l12 12"/>'),
  more: svg('<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'),
  ext: svg('<path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>'),
  link: svg('<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/>'),
  expand: svg('<path d="M4 7h16M4 12h16M4 17h10"/>'),
  flag: svg('<path d="M5 21V4h11l-1.5 4L16 12H5"/>'),
  arrow: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  guide: svg('<path d="M4 5h11a3 3 0 0 1 3 3v12H7a3 3 0 0 1-3-3z"/><path d="M8 9h6M8 13h5"/>'),
};

let data, syn, engine, guides = [];
let lastQuery = "", limit = PAGE, panelOpen = false;
let counts = null, topicCounts = null;       // matches for the current question, before filters
const filters = { laws: new Set(), types: new Set(), jurisdictions: new Set(), topics: new Set() };
const TYPE_LABELS = { law: "Statutes", regulation: "Regulations", guidance: "Guidance" };
const JUR_LABELS = { EU: "European Union", "US-CA": "California", "US-Federal": "US federal", CA: "Canada" };

const ready = (async () => {
  let tj;
  [data, syn, tj] = await Promise.all([
    fetch("assets/search-data.json").then(r => r.json()),
    fetch("assets/synonyms.json").then(r => r.json()),
    fetch("assets/topics.json").then(r => r.json()).catch(() => ({ topics: [] })),
  ]);
  guides = tj.topics || [];
  engine = createEngine(MiniSearch, data);
})();

// ---------- helpers ----------

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => toastEl.classList.remove("show"), 1800);
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { /* ignore */ }
    ta.remove();
    return ok;
  }
}

const topicLabel = id => (data.taxonomy.find(t => t.id === id) || { label: id }).label;
const filterState = () => ({ laws: [...filters.laws], types: [...filters.types], jurisdictions: [...filters.jurisdictions] });
const nFilters = () => filters.laws.size + filters.types.size + filters.jurisdictions.size + filters.topics.size;

// Highlight the visitor's own words at word starts (stems match their inflections) and synonym phrases whole.
function highlighter(q) {
  const stems = [...new Set(q.terms.filter(w => !STOPWORDS.has(w)).map(stem))].filter(w => w.length > 2);
  const phrases = q.expansions.map(x => normalize(x).trim()).filter(x => x.includes(" "));
  const escRe = t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const alts = phrases.map(p => escRe(p).replace(/ /g, "\\s+")).concat(stems.map(s => escRe(s) + "[\\p{L}\\p{N}'-]*"));
  if (!alts.length) return t => esc(t);
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(${alts.join("|")})`, "giu");
  return t => t.split(re).map((p, i) => (i % 2 ? `<mark>${esc(p)}</mark>` : esc(p))).join("");
}

function renderLines(text, hl = esc) {
  return text.split("\n").map(line => {
    const indent = Math.min(4, Math.floor((line.length - line.trimStart().length) / 2));
    return `<p class="l${indent}">${hl(line.trim())}</p>`;
  }).join("");
}

function reportUrl(c) {
  const q = new URLSearchParams({ template: "report-an-error.yml", title: `[Error] ${c.ref}`, provision: c.ref,
    page: data.site.site_url.replace(/\/$/, "") + "/" + c.url });
  return `${data.site.repo}/issues/new?${q}`;
}

function tagsHtml(c) {
  const have = c.topics || [];
  const parents = new Set(have.map(t => (data.taxonomy.find(x => x.id === t) || {}).parent).filter(Boolean));
  const tags = have.filter(t => !parents.has(t) && t !== "definitions");
  if (!tags.length) return "";
  return `<div class="tags">${tags.slice(0, 3).map(t => `<span class="tag">${esc(topicLabel(t))}</span>`).join("")}</div>`;
}

// ---------- result cards ----------

function card(c, hl, opts = {}) {
  const doc = data.docs[c.doc];
  const parent = c.parent ? data.articles.find(a => a.id === c.parent) : null;
  const noun = c.parent && c.parent.includes(":art:") ? "article" : "section";
  const kind = { paragraph: noun === "article" ? "Article" : "Section", definition: "Definition", recital: "Recital" }[c.kind] || c.kind;
  const long = c.text.length > 520 || c.text.split("\n").length > 6;
  const menu = `<div class="menu" role="menu" hidden>
      <button type="button" role="menuitem" data-act="copy" data-url="${esc(c.url)}">${I.link}Copy link</button>
      ${parent ? `<button type="button" role="menuitem" data-act="expand" data-parent="${esc(parent.id)}">${I.expand}Show the full ${noun}</button>` : ""}
      <a role="menuitem" href="${esc(reportUrl(c))}" target="_blank" rel="noopener noreferrer">${I.flag}Report an error</a>
    </div>`;
  return `<li class="result${opts.exact ? " exact" : ""}">
    <div class="r-top"><span class="law">${esc(doc.short)}</span><span class="dot">·</span><span>${esc(kind)}</span>
      ${opts.exact ? '<span class="dot">·</span><span>Exact match</span>' : ""}</div>
    <h2><a href="${c.url}">${esc(c.ref)}</a>${c.heading ? ` <span class="sub">${esc(c.heading)}</span>` : ""}</h2>
    <p class="crumbs">${esc(c.hier.slice(0, -1).join(" › "))}</p>
    ${tagsHtml(c)}
    ${opts.note ? `<p class="note">${esc(opts.note)}</p>` : ""}
    ${c.lead ? `<p class="lead-in"><span>Context:</span>${esc(c.lead)}</p>` : ""}
    <div class="clamp${long ? "" : " short open"}"><div class="text">${renderLines(c.text, hl)}</div></div>
    <div class="r-foot">
      ${long ? '<button type="button" class="link" data-act="clamp">Show more</button>' : ""}
      <a class="primary" href="${c.url}">Read in context</a>
      <a href="${esc(c.src || doc.source_url)}" target="_blank" rel="noopener noreferrer">Official source ${I.ext}</a>
      <span class="push more-menu"><button type="button" class="icon-btn" data-act="menu" aria-haspopup="true"
        aria-expanded="false" aria-label="More actions for ${esc(c.ref)}">${I.more}</button>${menu}</span>
      <p class="meta">${esc(doc.version_label)} · retrieved ${esc(doc.retrieved_at.slice(0, 10))}</p>
    </div>
    <div class="expanded" hidden></div>
  </li>`;
}

// ---------- filters ----------

function count(group, value) {
  if (group === "topics") return topicCounts ? (topicCounts[value] || 0) : null;
  if (!counts) return null;
  let n = 0;
  for (const [doc, k] of Object.entries(counts)) {
    const d = data.docs[doc];
    const v = group === "laws" ? doc : group === "types" ? d.doc_type : d.jurisdiction;
    if (v === value) n += k;
  }
  return n;
}

function option(group, value, label, sub = false) {
  const n = count(group, value);
  const key = `${group}:${value}`;
  return `<label class="fp-option${sub ? " sub" : ""}"><input type="checkbox" data-key="${esc(key)}"
    ${filters[group].has(value) ? "checked" : ""}> ${esc(label)}${n === null ? "" : `<span class="n">${n > 99 ? "99+" : n}</span>`}</label>`;
}

function renderFilters() {
  const docs = Object.entries(data.docs);
  const types = [...new Set(docs.map(([, d]) => d.doc_type))];
  const jur = [...new Set(docs.map(([, d]) => d.jurisdiction))];
  const n = nFilters();
  const topics = data.taxonomy.filter(t => !t.parent).map(t =>
    option("topics", t.id, t.label) + data.taxonomy.filter(x => x.parent === t.id).map(x => option("topics", x.id, x.label, true)).join("")).join("");
  const focusKey = document.activeElement?.dataset?.key;
  const scroll = filterWrap.querySelector(".fp-body")?.scrollTop || 0;
  filterWrap.innerHTML = `
    <button type="button" class="filter-btn" id="filter-btn" aria-expanded="${panelOpen}" aria-controls="filter-panel">
      ${I.filter} Filters${n ? ` <span class="count">${n}</span>` : ""}</button>
    <div class="filter-panel" id="filter-panel" role="dialog" aria-label="Filters" ${panelOpen ? "" : "hidden"}>
      <div class="fp-body">
        <div class="fp-group"><h3>Law</h3><div class="fp-list">${docs.map(([id, d]) => option("laws", id, d.short)).join("")}</div></div>
        <div class="fp-group"><h3>Type</h3><div class="fp-list">${types.map(t => option("types", t, TYPE_LABELS[t] || t)).join("")}</div>
          <h3 style="margin-top:1rem">Jurisdiction</h3><div class="fp-list">${jur.map(j => option("jurisdictions", j, JUR_LABELS[j] || j)).join("")}</div></div>
        <div class="fp-group wide"><h3>Topic</h3><div class="fp-list">${topics}</div></div>
      </div>
      <div class="fp-foot"><button type="button" class="link" data-act="clear">Clear all</button>
        <button type="button" data-act="done">Done</button></div>
    </div>`;
  const body = filterWrap.querySelector(".fp-body");
  if (body) body.scrollTop = scroll;
  if (focusKey) filterWrap.querySelector(`[data-key="${CSS.escape(focusKey)}"]`)?.focus();
  const pills = [];
  for (const [group, set] of Object.entries(filters)) {
    for (const v of set) {
      const label = group === "laws" ? data.docs[v].short : group === "types" ? (TYPE_LABELS[v] || v)
        : group === "jurisdictions" ? (JUR_LABELS[v] || v) : topicLabel(v);
      pills.push(`<button type="button" class="pill" data-key="${esc(group + ":" + v)}" aria-label="Remove filter ${esc(label)}">${esc(label)} ${I.x}</button>`);
    }
  }
  pillsEl.innerHTML = pills.length ? pills.join("") + '<button type="button" class="link" data-act="clear">Clear all</button>' : "";
}

function toggleFilter(key) {
  const i = key.indexOf(":");
  const set = filters[key.slice(0, i)], v = key.slice(i + 1);
  set.has(v) ? set.delete(v) : set.add(v);
  limit = PAGE;
  run(lastQuery, { keepPanel: true });
}

function setPanel(open) {
  panelOpen = open;
  const p = $("filter-panel"), b = $("filter-btn");
  if (p) p.hidden = !open;
  if (b) b.setAttribute("aria-expanded", String(open));
}

filterWrap.addEventListener("change", e => { if (e.target.dataset.key) toggleFilter(e.target.dataset.key); });
filterWrap.addEventListener("click", e => {
  if (e.target.closest("#filter-btn")) setPanel(!panelOpen);
  const act = e.target.closest("[data-act]")?.dataset.act;
  if (act === "done") setPanel(false);
  if (act === "clear") { Object.values(filters).forEach(s => s.clear()); run(lastQuery, { keepPanel: true }); }
});
pillsEl.addEventListener("click", e => {
  const pill = e.target.closest(".pill");
  if (pill) toggleFilter(pill.dataset.key);
  if (e.target.closest('[data-act="clear"]')) { Object.values(filters).forEach(s => s.clear()); run(lastQuery); }
});
document.addEventListener("click", e => {
  if (panelOpen && !e.target.closest("#filter-wrap")) setPanel(false);
  if (!e.target.closest(".more-menu")) closeMenus();
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") { if (panelOpen) { setPanel(false); $("filter-btn")?.focus(); } closeMenus(); }
});

// ---------- search ----------

function tally(res) {
  const t = {}, tt = {};
  const add = c => { t[c.doc] = (t[c.doc] || 0) + 1; for (const x of c.topics || []) tt[x] = (tt[x] || 0) + 1; };
  if (res.citation) add(res.citation.chunk);
  for (const h of res.results) add(engine.byId.get(h.id));
  return { docs: t, topics: tt };
}

async function run(raw, opts = {}) {
  raw = (raw || "").trim();
  await ready;
  lastQuery = raw;
  if (!opts.keepPanel) setPanel(false);
  if (!raw) { area.hidden = true; home.hidden = false; return; }
  area.hidden = false;
  home.hidden = true;

  const all = search(engine, data, syn, raw);
  ({ docs: counts, topics: topicCounts } = tally(all));
  const res = nFilters()
    ? search(engine, data, syn, raw, { docs: docsForFilters(data, filterState()), topics: [...filters.topics] })
    : all;
  renderFilters();

  const hl = highlighter(res.query);
  const items = [];
  const seen = new Set();
  if (res.citation) {
    items.push(card(res.citation.chunk, x => esc(x), { exact: true, note: res.citation.note }));
    seen.add(res.citation.chunk.id);
  }
  const rest = res.results.filter(h => !seen.has(h.id));
  for (const h of rest.slice(0, limit)) items.push(card(engine.byId.get(h.id), hl));
  const total = rest.length + (res.citation ? 1 : 0);

  topicBox.innerHTML = matchTopics(raw, guides, res.query.filterDocs).map(({ topic: t }) => `
    <article class="topic-card"><span class="fi">${I.guide}</span><div>
      <p class="eyebrow" style="margin:0">Guided topic${t.state === "published" ? "" : " · needs review"}</p>
      <h2><a href="${t.url}">${esc(t.title)}</a></h2><p>${esc(t.scope)}</p>
      <a class="go" href="${t.url}">Open the research path</a></div></article>`).join("");

  if (!items.length) {
    const why = res.messages.length ? res.messages.map(esc).join(" ") :
      `Nothing in the ${nFilters() ? "selected" : "loaded"} sources matches “${esc(raw)}”.`;
    list.innerHTML = `<li class="empty"><p>${why}</p><p class="muted">${nFilters() ? "Try removing a filter, or " : "Try "}
      broader or different wording, or <a href="documents/">browse the laws</a>.</p></li>`;
    statusEl.textContent = "No results";
    moreEl.innerHTML = "";
    return;
  }
  list.innerHTML = items.join("");
  const shown = items.length;
  const notes = res.messages.map(m => `<span class="note-line">${esc(m)}</span>`);
  if (res.expansions.length) {
    notes.push(`<span class="note-line">Also searched: ${res.expansions.slice(0, 3).map(x => `<em>${esc(x)}</em>`).join(", ")}${res.expansions.length > 3 ? "…" : ""}</span>`);
  }
  statusEl.innerHTML = `<strong>${total}</strong> result${total === 1 ? "" : "s"}${total > shown ? ` · showing ${shown}` : ""}${notes.join("")}`;
  moreEl.innerHTML = total > shown ? `<button type="button" class="btn-ghost" data-act="more">Show more results</button>` : "";
}

// ---------- result actions ----------

function closeMenus(except) {
  list.querySelectorAll(".menu:not([hidden])").forEach(m => {
    if (m === except) return;
    m.hidden = true;
    m.previousElementSibling?.setAttribute("aria-expanded", "false");
  });
}

list.addEventListener("click", async e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const li = el.closest(".result");
  switch (el.dataset.act) {
    case "clamp": {
      const box = li.querySelector(".clamp");
      const open = box.classList.toggle("open");
      el.textContent = open ? "Show less" : "Show more";
      break;
    }
    case "menu": {
      const m = el.nextElementSibling;
      closeMenus(m);
      m.hidden = !m.hidden;
      el.setAttribute("aria-expanded", String(!m.hidden));
      break;
    }
    case "copy": {
      const ok = await copyText(new URL(el.dataset.url, location.href).href);
      toast(ok ? "Link copied" : "Could not copy the link");
      closeMenus();
      break;
    }
    case "expand": {
      const box = li.querySelector(".expanded");
      closeMenus();
      if (!box.hidden) { box.hidden = true; break; }
      const parts = data.chunks.filter(c => c.parent === el.dataset.parent).sort((x, y) => x.ord - y.ord);
      box.innerHTML = parts.map(c => `<section class="prov"><a class="anchor" href="${c.url}">${esc(c.ref)}</a>
        <div class="text">${renderLines(c.text)}</div></section>`).join("");
      box.hidden = false;
      break;
    }
  }
});
moreEl.addEventListener("click", e => {
  if (e.target.closest('[data-act="more"]')) { limit += PAGE; run(lastQuery, { keepPanel: false }); }
});

// Nothing about a search is kept in the URL or in storage, so a refresh always starts blank.
// (The Back button may still restore the page as it was, which is the browser's own page cache.)
form.addEventListener("submit", e => { e.preventDefault(); limit = PAGE; run(input.value); });
document.querySelector(".examples").addEventListener("click", e => {
  const b = e.target.closest("button[data-q]");
  if (!b) return;
  input.value = b.dataset.q;
  limit = PAGE;
  run(b.dataset.q);
});
if (location.hash.startsWith("#q=")) history.replaceState(null, "", location.pathname + location.search);
