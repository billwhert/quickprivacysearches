// Search page: runs entirely in the browser. No network calls except loading the
// static data and library files from this same site; query text is never sent anywhere.
import MiniSearch from "./minisearch.js";
import { createEngine, search, stem, STOPWORDS, normalize } from "./lookup.js";

const $ = id => document.getElementById(id);
const input = $("q"), form = $("search-form"), status = $("status"), list = $("results");
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const MAX_RESULTS = 20;

let data, syn, engine;

const ready = (async () => {
  status.textContent = "Loading index...";
  [data, syn] = await Promise.all([
    fetch("assets/search-data.json").then(r => r.json()),
    fetch("assets/synonyms.json").then(r => r.json()),
  ]);
  engine = createEngine(MiniSearch, data);
  status.textContent = "";
})();

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
  const art = c.art ? data.articles.find(a => a.id === `${c.doc}:art:${c.art}`) : null;
  const heading = c.heading ? `<span class="sub"> - ${esc(c.heading)}</span>` : "";
  const parentLink = art ? `<button class="link expand" data-art="${c.art}" data-doc="${c.doc}">Show full article</button>
    <a href="${art.url}">Open article page</a>` : "";
  const kind = { paragraph: "Article", definition: "Definition", recital: "Recital" }[c.kind] || c.kind;
  return `<li class="result${opts.exact ? " exact" : ""}" data-id="${esc(c.id)}">
    <div class="result-head"><span class="badge">${esc(c.doc.toUpperCase())}</span>
      <span class="badge kind">${esc(kind)}</span>${opts.exact ? '<span class="badge">Exact match</span>' : ""}</div>
    <p class="crumbs">${esc(c.hier.slice(0, -1).join(" › "))}</p>
    <h2><a href="${c.url}">${esc(c.ref)}</a>${heading}</h2>
    ${opts.note ? `<p class="note">${esc(opts.note)}</p>` : ""}
    <div class="text">${renderLines(c.text, terms)}</div>
    <p class="meta">${esc(doc.title)} · ${esc(doc.version_label)} · retrieved ${esc(doc.retrieved_at.slice(0, 10))}</p>
    <div class="actions"><a href="${c.url}">Permalink</a>
      <a href="${esc(doc.source_url)}">Official source</a>${parentLink}</div>
    <div class="expanded" hidden></div>
  </li>`;
}

function highlightTerms(q) {
  const words = q.terms.concat(q.expansions.flatMap(x => normalize(x).trim().split(" ")))
    .filter(w => !STOPWORDS.has(w));
  return [...new Set(words.map(stem))].filter(w => w.length > 2);
}

async function run(raw) {
  raw = raw.trim();
  await ready;
  if (!raw) { list.innerHTML = ""; status.textContent = ""; return; }
  const res = search(engine, data, syn, raw);
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
  if (!out.length) {
    const tail = res.outOfScope
      ? `You can <a href="gdpr/">browse the GDPR</a> instead.`
      : `No provisions found for "${esc(raw)}" in the loaded sources. ` +
        `Try broader terms or different wording, or <a href="gdpr/">browse the GDPR</a>.`;
    status.innerHTML = (notes.length ? notes.join("<br>") + "<br>" : "") + tail;
  } else {
    const count = `${out.length} result${out.length === 1 ? "" : "s"}` +
      (res.results.length > shown ? ` (top ${shown} of ${res.results.length} matches)` : "");
    status.innerHTML = esc(count) + (notes.length ? "<br>" + notes.join("<br>") : "");
  }
}

list.addEventListener("click", e => {
  const b = e.target.closest("button.expand");
  if (!b) return;
  const box = b.closest(".result").querySelector(".expanded");
  if (!box.hidden) { box.hidden = true; b.textContent = "Show full article"; return; }
  const art = +b.dataset.art;
  const parts = data.chunks.filter(c => c.doc === b.dataset.doc && c.art === art)
    .sort((x, y) => x.n - y.n);
  box.innerHTML = parts.map(c => `<section class="prov"><a class="anchor" href="${c.url}">${esc(c.ref)}</a>
    <div class="text">${renderLines(c.text, [])}</div></section>`).join("");
  box.hidden = false;
  b.textContent = "Hide full article";
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
// Links that arrive with #q=... (for example from another site) run once, then the hash is removed.
const m = location.hash.match(/^#q=(.*)$/);
if (m) {
  input.value = decodeURIComponent(m[1].replace(/\+/g, " "));
  history.replaceState(null, "", location.pathname + location.search);
  run(input.value);
}
// Back/forward cache restores must not bring an old search back either.
window.addEventListener("pageshow", e => {
  if (e.persisted) { input.value = ""; list.innerHTML = ""; status.textContent = ""; }
});
