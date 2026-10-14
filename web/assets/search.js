// Search page: runs entirely in the browser. No network calls except loading the
// static data and library files from this same site; query text is never sent anywhere.
import MiniSearch from "./minisearch.js";
import { prepareQuery, lookupCitation, INDEX_OPTIONS, SEARCH_OPTIONS } from "./lookup.js";

const $ = id => document.getElementById(id);
const input = $("q"), form = $("search-form"), status = $("status"), list = $("results");
const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const MAX_RESULTS = 20;

let data, ms;
const byId = new Map();

const ready = (async () => {
  status.textContent = "Loading index...";
  data = await (await fetch("assets/search-data.json")).json();
  ms = new MiniSearch(INDEX_OPTIONS);
  ms.addAll(data.chunks);
  data.chunks.forEach(c => byId.set(c.id, c));
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
  return `<li class="result${opts.exact ? " exact" : ""}" data-id="${esc(c.id)}">
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

async function run(raw) {
  raw = raw.trim();
  await ready;
  if (!raw) { list.innerHTML = ""; status.textContent = ""; return; }
  const out = [];
  const seen = new Set();
  const cit = lookupCitation(raw, data);
  if (cit) {
    out.push(card(cit.chunk, [], { exact: true, note: cit.note }));
    seen.add(cit.chunk.id);
  }
  const p = prepareQuery(raw);
  let hits = [];
  if (p.terms.length && !(cit && cit.exact && /^\s*(gdpr\s*)?(art|recital)/i.test(raw))) {
    hits = ms.search(p.terms.join(" "), SEARCH_OPTIONS);
  }
  const terms = p.terms;
  let shown = 0;
  for (const h of hits) {
    if (seen.has(h.id)) continue;
    out.push(card(byId.get(h.id), terms.concat(h.terms || [])));
    if (++shown >= MAX_RESULTS) break;
  }
  list.innerHTML = out.join("");
  if (!out.length) {
    status.innerHTML = `No provisions found for "${esc(raw)}" in the loaded sources (currently the GDPR only). ` +
      `Try broader terms, or <a href="gdpr/">browse the GDPR</a>.`;
  } else {
    status.textContent = `${out.length} result${out.length === 1 ? "" : "s"}` +
      (hits.length > shown ? ` (showing top ${shown} matches of ${hits.length})` : "");
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

function fromHash() {
  const m = location.hash.match(/^#q=(.*)$/);
  return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
}
function submit(q) {
  history.replaceState(null, "", q ? `#q=${encodeURIComponent(q)}` : location.pathname);
  run(q);
}
form.addEventListener("submit", e => { e.preventDefault(); submit(input.value); });
window.addEventListener("hashchange", () => { input.value = fromHash(); run(input.value); });
if (fromHash()) { input.value = fromHash(); run(input.value); }
