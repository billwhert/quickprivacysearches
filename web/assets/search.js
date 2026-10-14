// Search page: runs entirely in the browser. No network calls except loading the
// static data and library files from this same site; query text is never sent anywhere.
import MiniSearch from "./minisearch.js";
import { createEngine, search, stem, STOPWORDS, normalize, docsForFilters } from "./lookup.js";

const $ = id => document.getElementById(id);
const input = $("q"), form = $("search-form"), status = $("status"), list = $("results");
const filterBox = $("filters");
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const MAX_RESULTS = 20;

let data, syn, engine;
let lastQuery = "";
let counts = null;                       // matches per document for the current query, ignoring filters
const filters = { laws: new Set(), types: new Set(), jurisdictions: new Set() };

const TYPE_LABELS = { law: "Statutes", regulation: "Regulations", guidance: "Guidance" };
const JURISDICTION_LABELS = { EU: "European Union", "US-CA": "California", "US-Federal": "US federal" };

const ready = (async () => {
  status.textContent = "Loading index...";
  [data, syn] = await Promise.all([
    fetch("assets/search-data.json").then(r => r.json()),
    fetch("assets/synonyms.json").then(r => r.json()),
  ]);
  engine = createEngine(MiniSearch, data);
  status.textContent = "";
  renderFilters();
})();

// ---------- filters ----------

function filterState() {
  return { laws: [...filters.laws], types: [...filters.types], jurisdictions: [...filters.jurisdictions] };
}
function anyFilter() { return filters.laws.size + filters.types.size + filters.jurisdictions.size > 0; }

function countFor(group, value) {
  if (!counts) return "";
  let n = 0;
  for (const [doc, c] of Object.entries(counts)) {
    const d = data.docs[doc];
    const v = group === "laws" ? doc : group === "types" ? d.doc_type : d.jurisdiction;
    if (v === value) n += c;
  }
  return n > 99 ? "99+" : String(n);
}

function chip(group, value, label) {
  const on = filters[group].has(value);
  const n = countFor(group, value);
  return `<button type="button" class="fchip" aria-pressed="${on}" data-group="${group}" data-value="${esc(value)}">` +
         `${esc(label)}${n !== "" ? `<span class="fcount">${n}</span>` : ""}</button>`;
}

function renderFilters() {
  const docs = Object.entries(data.docs);
  const types = [...new Set(docs.map(([, d]) => d.doc_type))];
  const juris = [...new Set(docs.map(([, d]) => d.jurisdiction))];
  const group = (title, chips) => `<div class="fgroup"><span class="flabel">${title}</span>${chips}</div>`;
  filterBox.innerHTML =
    group("Law", docs.map(([id, d]) => chip("laws", id, d.short)).join("")) +
    group("Type", types.map(t => chip("types", t, TYPE_LABELS[t] || t)).join("")) +
    group("Jurisdiction", juris.map(j => chip("jurisdictions", j, JURISDICTION_LABELS[j] || j)).join("")) +
    (anyFilter() ? `<button type="button" class="link" id="clear-filters">Clear filters</button>` : "");
  filterBox.hidden = false;
}

filterBox.addEventListener("click", e => {
  if (e.target.closest("#clear-filters")) {
    Object.values(filters).forEach(s => s.clear());
  } else {
    const b = e.target.closest("button.fchip");
    if (!b) return;
    const set = filters[b.dataset.group];
    set.has(b.dataset.value) ? set.delete(b.dataset.value) : set.add(b.dataset.value);
  }
  if (lastQuery) run(lastQuery); else renderFilters();
});

// ---------- rendering ----------

function highlight(text, terms) {
  const safe = [...new Set(terms)].filter(t => t.length > 1)
    .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!safe.length) return esc(text);
  const re = new RegExp(`(${safe.join("|")})`, "gi");
  return text.split(re).map((p, i) => (i % 2 ? `<mark>${esc(p)}</mark>` : esc(p))).join("");
}

function renderLines(text, terms) {
  return text.split("\n").map(line => {
    const indent = Math.min(4, Math.floor((line.length - line.trimStart().length) / 2));
    return `<p class="l${indent}">${highlight(line.trim(), terms)}</p>`;
  }).join("");
}

function card(c, terms, opts = {}) {
  const doc = data.docs[c.doc];
  const parent = c.parent ? data.articles.find(a => a.id === c.parent) : null;
  const heading = c.heading ? `<span class="sub"> - ${esc(c.heading)}</span>` : "";
  const noun = c.parent && c.parent.includes(":art:") ? "article" : "section";
  const parentLink = parent ? `<button class="link expand" data-parent="${esc(parent.id)}" data-noun="${noun}">Show full ${noun}</button>
    <a href="${parent.url}">Open ${noun} page</a>` : "";
  const kind = { paragraph: noun === "article" ? "Article" : "Section", definition: "Definition", recital: "Recital" }[c.kind] || c.kind;
  const lead = c.lead ? `<p class="lead-in"><span>Context:</span> ${esc(c.lead)}</p>` : "";
  return `<li class="result${opts.exact ? " exact" : ""}" data-id="${esc(c.id)}">
    <div class="result-head"><span class="badge">${esc(doc.short)}</span>
      <span class="badge kind">${esc(kind)}</span>${opts.exact ? '<span class="badge">Exact match</span>' : ""}</div>
    <p class="crumbs">${esc(c.hier.slice(0, -1).join(" › "))}</p>
    <h2><a href="${c.url}">${esc(c.ref)}</a>${heading}</h2>
    ${opts.note ? `<p class="note">${esc(opts.note)}</p>` : ""}
    ${lead}
    <div class="text">${renderLines(c.text, terms)}</div>
    <p class="meta">${esc(doc.title)} · ${esc(doc.version_label)} · retrieved ${esc(doc.retrieved_at.slice(0, 10))}</p>
    <div class="actions"><a href="${c.url}">Permalink</a>
      <button class="link copy" data-url="${esc(c.url)}">Copy link</button>
      <a href="${esc(c.src || doc.source_url)}">Official source</a>${parentLink}</div>
    <div class="expanded" hidden></div>
  </li>`;
}

function highlightTerms(q) {
  const words = q.terms.concat(q.expansions.flatMap(x => normalize(x).trim().split(" ")))
    .filter(w => !STOPWORDS.has(w));
  return [...new Set(words.map(stem))].filter(w => w.length > 2);
}

function tally(res) {
  const t = {};
  if (res.citation) t[res.citation.chunk.doc] = (t[res.citation.chunk.doc] || 0) + 1;
  for (const h of res.results) {
    const d = engine.byId.get(h.id).doc;
    t[d] = (t[d] || 0) + 1;
  }
  return t;
}

async function run(raw) {
  raw = raw.trim();
  await ready;
  lastQuery = raw;
  if (!raw) { list.innerHTML = ""; status.textContent = ""; counts = null; renderFilters(); return; }

  // unfiltered pass gives the per-law counts shown on the filter chips
  const all = search(engine, data, syn, raw);
  counts = tally(all);
  const res = anyFilter()
    ? search(engine, data, syn, raw, { docs: docsForFilters(data, filterState()) })
    : all;
  renderFilters();

  const hl = highlightTerms(res.query);
  const out = [];
  const seen = new Set();
  if (res.citation) {
    out.push(card(res.citation.chunk, [], { exact: true, note: res.citation.note }));
    seen.add(res.citation.chunk.id);
  }
  let shown = 0;
  for (const h of res.results) {
    if (seen.has(h.id)) continue;
    out.push(card(engine.byId.get(h.id), hl));
    if (++shown >= MAX_RESULTS) break;
  }
  list.innerHTML = out.join("");

  const notes = res.messages.map(m => `<span class="note-line">${esc(m)}</span>`);
  if (res.expansions.length && out.length) {
    notes.push(`<span class="note-line">Also searched related wording: ` +
      `${res.expansions.map(x => `<em>${esc(x)}</em>`).join(", ")}</span>`);
  }
  if (anyFilter() && out.length) {
    const names = docsForFilters(data, filterState()).map(d => data.docs[d].short).join(", ");
    notes.push(`<span class="note-line">Filtered to: ${esc(names)}</span>`);
  }
  if (!out.length) {
    const hint = anyFilter() ? "Try clearing a filter, or " : "";
    const tail = res.outOfScope
      ? `You can browse the loaded laws from the Browse page instead.`
      : `No provisions found for "${esc(raw)}" in the selected sources. ` +
        `${hint}try broader terms or different wording, or use Browse to read a law in order.`;
    status.innerHTML = (notes.length ? notes.join("<br>") + "<br>" : "") + tail;
  } else {
    const count = `${out.length} result${out.length === 1 ? "" : "s"}` +
      (res.results.length > shown ? ` (top ${shown} of ${res.results.length} matches)` : "");
    status.innerHTML = esc(count) + (notes.length ? "<br>" + notes.join("<br>") : "");
  }
}

// ---------- result actions ----------

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { /* ignore */ }
    ta.remove();
    return ok;
  }
}

list.addEventListener("click", async e => {
  const copy = e.target.closest("button.copy");
  if (copy) {
    const url = new URL(copy.dataset.url, location.href).href;
    const ok = await copyText(url);
    const old = copy.textContent;
    copy.textContent = ok ? "Link copied" : "Copy failed";
    setTimeout(() => { copy.textContent = old; }, 1600);
    return;
  }
  const b = e.target.closest("button.expand");
  if (!b) return;
  const box = b.closest(".result").querySelector(".expanded");
  const noun = b.dataset.noun;
  if (!box.hidden) { box.hidden = true; b.textContent = `Show full ${noun}`; return; }
  const parts = data.chunks.filter(c => c.parent === b.dataset.parent).sort((x, y) => x.ord - y.ord);
  box.innerHTML = parts.map(c => `<section class="prov"><a class="anchor" href="${c.url}">${esc(c.ref)}</a>
    <div class="text">${renderLines(c.text, [])}</div></section>`).join("");
  box.hidden = false;
  b.textContent = `Hide full ${noun}`;
});

// Nothing about a search is kept in the URL, history, or storage: a refresh always starts blank.
function submit(q) { run(q); }
form.addEventListener("submit", e => { e.preventDefault(); submit(input.value); });
document.querySelector(".examples").addEventListener("click", e => {
  const b = e.target.closest("button[data-q]");
  if (!b) return;
  input.value = b.dataset.q;
  submit(b.dataset.q);
  input.focus();
});
// Old links carrying #q=... are never run; the hash is simply dropped so nothing lingers.
if (location.hash.startsWith("#q=")) history.replaceState(null, "", location.pathname + location.search);
// Back/forward cache restores must not bring an old search or filters back either.
window.addEventListener("pageshow", e => {
  if (e.persisted) {
    input.value = ""; list.innerHTML = ""; status.textContent = ""; lastQuery = ""; counts = null;
    Object.values(filters).forEach(s => s.clear());
    if (data) renderFilters();
  }
});
