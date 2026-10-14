// Engine-independent search logic shared by the page and the test runner.
// Runs entirely in the browser; query text is never sent anywhere.
//
// Pipeline: citation lookup -> query cleanup -> jurisdiction detection ->
//           synonym expansion -> ranked search -> phrase / first-paragraph boosts.

// ---------- text helpers ----------

export const STOPWORDS = new Set((
  "a an the of to in on at by for from with without about as is are was were be been being do does did " +
  "i me my we our you your it its this that these those and or but if then than so such what which who whom " +
  "when where why how can could should would may might must shall will under any there their them they " +
  "need needs include includes included have has had get got into out up over per via also please tell " +
  "explain exactly really just very much many some every each other another own same too only both " +
  "am im ive dont doesnt cant wont isnt arent whats hows thats tell show give find"
).split(" "));

// Light plural / verb-ending stemmer so "bases", "processes", "required" match their roots.
export function stem(w) {
  if (w.length <= 3) return w;
  if (w.endsWith("ies") && w.length > 4) w = w.slice(0, -3) + "y";
  else if (w.endsWith("sses") || /(x|z|ch|sh)es$/.test(w)) w = w.slice(0, -2);
  else if (w.endsWith("ss") || w.endsWith("us") || w.endsWith("is")) return w;
  else if (w.endsWith("s")) w = w.slice(0, -1);
  if (w.length > 6 && w.endsWith("ing")) w = w.slice(0, -3);
  else if (w.length > 5 && w.endsWith("ed")) w = w.slice(0, -2);
  if (w.length > 4 && w.endsWith("e")) w = w.slice(0, -1);
  return w;
}

const ALNUM = /[^\p{L}\p{N}\s'-]/gu;
export function normalize(raw) {
  return " " + raw.toLowerCase().replace(/[‘’]/g, "'").replace(/'s(?![a-z])/g, "")
    .replace(ALNUM, " ").replace(/\s+/g, " ").trim() + " ";
}
const hasPhrase = (padded, phrase) => padded.includes(" " + normalize(phrase).trim() + " ");

// ---------- engine configuration (single source of truth) ----------

export const INDEX_OPTIONS = {
  idField: "id",
  fields: ["term", "heading", "ref", "text"],
  processTerm: t => { t = t.toLowerCase().replace(/'s$/, ""); return STOPWORDS.has(t) ? null : stem(t); },
};
export const SEARCH_OPTIONS = {
  boost: { term: 4, heading: 3, ref: 2, text: 1 }, prefix: false, fuzzy: 0.15, combineWith: "OR",
  bm25: { k: 1.2, b: 0.4, d: 0.5 }, // long provisions (many lettered points) are penalised less than default
};
const EXPANSION_WEIGHT = 0.7;      // synonym matches count a bit less than the visitor's own words
const FIRST_PARAGRAPH_BONUS = 1.08; // paragraph 1 is usually the operative rule; used as a tie-breaker
const MAX_PHRASE_WORDS = 5;

// ---------- citation lookup ----------

// "GDPR Article 30", "Art. 35(1)", "article 6(1)(f)", "recital 26"
const ART = /^\s*(?:gdpr\s*[,:-]?\s*)?(?:art(?:icle)?s?\.?\s*)(\d{1,3})\s*(?:\(\s*(\d{1,3})\s*\))?\s*(?:\(\s*([a-z]{1,3})\s*\))?\s*$/i;
const RCT = /^\s*(?:gdpr\s*[,:-]?\s*)?(?:recital|rec\.?)\s*\(?(\d{1,3})\)?\s*$/i;

export function lookupCitation(raw, data) {
  let m = raw.match(RCT);
  if (m) {
    const c = data.chunks.find(x => x.id === `gdpr:rct:${+m[1]}`);
    return c ? { chunk: c, exact: true, note: null } : null;
  }
  m = raw.match(ART);
  if (!m) return null;
  const art = +m[1], para = m[2] ? +m[2] : null, point = m[3] || null;
  if (para !== null) {
    const c = data.chunks.find(x => x.id === `gdpr:art:${art}:${para}`);
    if (c) return { chunk: c, exact: true, note: point ? `Point (${point}) is shown within ${c.ref}.` : null };
  }
  const a = data.articles.find(x => x.id === `gdpr:art:${art}`);
  if (!a) return null;
  const first = data.chunks.find(x => x.id === `gdpr:art:${art}:${para ?? 1}`) ||
                data.chunks.find(x => x.art === art);
  return first ? { chunk: first, article: a, exact: para === null,
    note: para !== null ? `${a.ref}(${para}) was not found; showing the article.` : null } : null;
}

// ---------- query analysis ----------

export function analyzeQuery(raw, syn, loadedDocs) {
  const padded = normalize(raw);
  const words = padded.trim().split(" ").filter(Boolean);

  // jurisdictions mentioned
  const mentioned = [];
  const jurWords = new Set();
  for (const j of syn.jurisdictions) {
    const hit = j.words.filter(w => hasPhrase(padded, w));
    if (hit.length) {
      mentioned.push(j);
      hit.forEach(w => normalize(w).trim().split(" ").forEach(x => jurWords.add(x)));
    }
  }
  const loadedMentioned = mentioned.filter(j => j.docs.some(d => loadedDocs.includes(d)));
  const unloaded = mentioned.filter(j => !j.docs.some(d => loadedDocs.includes(d)));
  const filterDocs = [...new Set(loadedMentioned.flatMap(j => j.docs.filter(d => loadedDocs.includes(d))))];

  // synonym expansion
  const expansions = [];
  const triggers = [];
  for (const g of syn.synonyms) {
    const hit = g.terms.find(t => hasPhrase(padded, t));
    if (hit) {
      triggers.push(hit);
      for (const x of g.expand) if (!expansions.includes(x) && !hasPhrase(padded, x)) expansions.push(x);
    }
  }

  const terms = words.filter(w => !STOPWORDS.has(w) && !jurWords.has(w));
  return { padded, words, terms, mentioned, loadedMentioned, unloaded, filterDocs, expansions, triggers };
}

// phrases (2+ words) from the visitor's wording, trimmed of leading/trailing stopwords
function visitorPhrases(words) {
  const out = new Set();
  for (let n = MAX_PHRASE_WORDS; n >= 2; n--) {
    for (let i = 0; i + n <= words.length; i++) {
      const g = words.slice(i, i + n);
      if (STOPWORDS.has(g[0]) || STOPWORDS.has(g[n - 1])) continue;
      out.add(g.join(" "));
    }
  }
  return [...out];
}

// ---------- search ----------

export function createEngine(MiniSearch, data) {
  const ms = new MiniSearch(INDEX_OPTIONS);
  ms.addAll(data.chunks);
  const byId = new Map(data.chunks.map(c => [c.id, c]));
  return { ms, byId };
}

export function search(engine, data, syn, raw, opts = {}) {
  const { ms, byId } = engine;
  const loadedDocs = Object.keys(data.docs);
  const q = analyzeQuery(raw, syn, loadedDocs);
  const out = { query: q, results: [], citation: null, messages: [], expansions: q.expansions };

  const cit = lookupCitation(raw, data);
  if (cit) out.citation = cit;
  const pureCitation = cit && cit.exact && /^\s*(gdpr\s*)?(art|recital)/i.test(raw);
  if (pureCitation) return out;

  // visitor asked only about a law that is not loaded
  if (q.unloaded.length && !q.loadedMentioned.length) {
    const names = q.unloaded.map(j => j.label).join(", ");
    const have = loadedDocs.map(d => d.toUpperCase()).join(", ");
    out.messages.push(`${names} ${q.unloaded.length > 1 ? "are" : "is"} not in the loaded sources yet. ` +
      `Currently loaded: ${have}.`);
    out.outOfScope = true;
    return out;
  }
  if (q.unloaded.length) {
    out.messages.push(`Not loaded yet: ${q.unloaded.map(j => j.label).join(", ")}. ` +
      `Showing results from the loaded sources only.`);
  }
  if (!q.terms.length && !q.expansions.length) return out;

  const scores = new Map();
  const matched = new Map();
  const add = (hits, weight) => {
    for (const h of hits) {
      scores.set(h.id, (scores.get(h.id) || 0) + h.score * weight);
      if (!matched.has(h.id)) matched.set(h.id, new Set());
      h.terms.forEach(t => matched.get(h.id).add(t));
    }
  };
  if (q.terms.length) add(ms.search(q.terms.join(" "), SEARCH_OPTIONS), 1);
  for (const phrase of q.expansions) add(ms.search(phrase, SEARCH_OPTIONS), EXPANSION_WEIGHT);

  // phrase boost: reward chunks containing multi-word phrases from the question or its expansions
  const phrases = visitorPhrases(q.words).concat(q.expansions.map(x => normalize(x).trim()));
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]).slice(0, 150);
  const final = [];
  for (const [id, score] of ranked) {
    const c = byId.get(id);
    if (q.filterDocs.length && !q.filterDocs.includes(c.doc)) continue;
    const hay = normalize(`${c.heading} ${c.term} ${c.text}`);
    let longest = 0;
    for (const ph of phrases) {
      const n = ph.split(" ").length;
      if (n > longest && hay.includes(" " + ph + " ")) longest = n;
    }
    let s = score * (1 + 0.2 * Math.max(0, longest - 1));
    if (c.kind === "paragraph" && c.n === 1) s *= FIRST_PARAGRAPH_BONUS;
    final.push({ id, score: s, terms: [...(matched.get(id) || [])] });
  }
  final.sort((a, b) => b.score - a.score);
  out.results = final;
  return out;
}
