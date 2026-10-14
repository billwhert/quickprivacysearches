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
  fields: ["term", "heading", "sub", "ref", "text"],
  processTerm: t => { t = t.toLowerCase().replace(/'s$/, ""); return STOPWORDS.has(t) ? null : stem(t); },
};
export const SEARCH_OPTIONS = {
  boost: { term: 4, heading: 3, sub: 3, ref: 2, text: 1 }, prefix: false, fuzzy: 0.15, combineWith: "OR",
  bm25: { k: 1.2, b: 0.4, d: 0.5 }, // long provisions (many lettered points) are penalised less than default
};
const EXPANSION_WEIGHT = 0.7;      // synonym matches count a bit less than the visitor's own words
const FIRST_PARAGRAPH_BONUS = 1.08; // paragraph 1 is usually the operative rule; used as a tie-breaker
const MAX_PHRASE_WORDS = 5;
const DIVERSITY_MIN_RATIO = 0.5;  // best-of-each-law is promoted if it scores at least this share of the top hit
const MIN_TERM_WEIGHT = 0.3;  // floor for ubiquitous words
const RARE_IDF = 3.2;         // ln(N/df) at or above which a word has full weight
const EXACT_TERM_BOOST = 3;         // the whole question is a defined term: "who is a covered entity"
const QUOTED_TERM_BOOST = 2.5;      // "define 'sell'" -> the definition of Sell
const DEFINITION_DEFAULT_PENALTY = 0.7; // operative rules before definitions unless a definition is asked for
const DEFINITION_INTENT_BOOST = 1.3; // "definition of ..." -> definition chunks

// ---------- citation lookup ----------

// GDPR: "GDPR Article 30", "Art. 35(1)", "article 6(1)(f)", "recital 26"
const ART = /^\s*(?:gdpr\s*[,:-]?\s*)?(?:art(?:icle)?s?\.?\s*)(\d{1,3})\s*(?:\(\s*(\d{1,3})\s*\))?\s*(?:\(\s*([a-z]{1,3})\s*\))?\s*$/i;
const RCT = /^\s*(?:gdpr\s*[,:-]?\s*)?(?:recital|rec\.?)\s*\(?(\d{1,3})\)?\s*$/i;
// Code sections: "1798.105", "Civ. Code 1798.140(ad)(1)", "section 1798.100(a)", "§ 7011(a)", "11 CCR 7025", "22575(b)"
const CODE = new RegExp(
  "^\\s*(?:(?:ccpa|cpra|cppa|hipaa|ccr|regs?|regulations?)\\s*[,:-]?\\s*)?" +
  "(?:(?:45\\s*)?c\\.?f\\.?r\\.?\\s*,?\\s*)?" +
  "(?:(?:cal(?:ifornia)?\\.?\\s*)?(?:civ(?:il)?\\.?|bus(?:iness)?\\.?\\s*(?:&|and)?\\s*prof(?:essions)?\\.?)\\s*code\\s*,?\\s*)?" +
  "(?:(?:11\\s*)?c\\.?c\\.?r\\.?\\s*,?\\s*)?" +
  "(?:(?:sections?|secs?\\.?|§+)\\s*)?" +
  "(\\d{4,5}(?:\\.\\d+){0,2}|\\d{3}\\.\\d{3})\\s*((?:\\(\\s*[a-zA-Z0-9]{1,3}\\s*\\)\\s*)*)\\s*$", "i");

function docForNumber(num) {
  if (/^1798\./.test(num)) return "ccpa";
  if (/^7\d{3}$/.test(num)) return "ccpa_regs";
  if (/^16[04]\.\d{3}$/.test(num)) return "hipaa";
  return null;
}

function idx(data) {
  if (!data._idx) data._idx = new Map(data.chunks.map(c => [c.id, c]));
  return data._idx;
}

export function lookupCitation(raw, data) {
  const byId = idx(data);
  let m = raw.match(RCT);
  if (m) {
    const c = byId.get(`gdpr:rct:${+m[1]}`);
    return c ? { chunk: c, exact: true, note: null } : null;
  }
  m = raw.match(ART);
  if (m && byId.size) {
    const art = +m[1], para = m[2] ? +m[2] : null, point = m[3] || null;
    if (para !== null) {
      const c = byId.get(`gdpr:art:${art}:${para}`);
      if (c) return { chunk: c, exact: true, note: point ? `Point (${point}) is shown within ${c.ref}.` : null };
    }
    const a = data.articles.find(x => x.id === `gdpr:art:${art}`);
    if (!a) return null;
    const first = byId.get(`gdpr:art:${art}:${para ?? 1}`) || data.chunks.find(x => x.parent === a.id);
    return first ? { chunk: first, article: a, exact: para === null,
      note: para !== null ? `${a.ref}(${para}) was not found; showing the article.` : null } : null;
  }
  m = raw.match(CODE);
  if (m) {
    const num = m[1];
    const doc = docForNumber(num);
    if (!doc) return null;
    const secId = `${doc}:sec:${num}`;
    const sec = data.articles.find(x => x.id === secId);
    if (!sec) return null;
    const labels = (m[2].match(/\(\s*([a-zA-Z0-9]{1,3})\s*\)/g) || []).map(x => x.replace(/[()\s]/g, ""));
    for (let n = labels.length; n > 0; n--) {
      const c = byId.get(`${secId}:${labels.slice(0, n).join(".")}`);
      if (c) {
        const shown = labels.slice(0, n).map(l => `(${l})`).join("");
        const wanted = labels.map(l => `(${l})`).join("");
        return { chunk: c, article: sec, exact: true,
          note: n < labels.length ? `${sec.ref}${wanted} is shown within ${sec.ref}${shown}.` : null };
      }
    }
    const first = data.chunks.find(x => x.parent === secId);
    return first ? { chunk: first, article: sec, exact: !labels.length,
      note: labels.length ? `${sec.ref}${labels.map(l => `(${l})`).join("")} was not found; showing the section.` : null } : null;
  }
  return null;
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
    // topical phrases ("covered entity") also point to a law but remain part of the question
    const topical = (j.topical || []).filter(w => hasPhrase(padded, w));
    if (hit.length || topical.length) {
      mentioned.push(j);
      hit.forEach(w => normalize(w).trim().split(" ").forEach(x => jurWords.add(x)));
    }
  }
  const loadedMentioned = mentioned.filter(j => j.docs.some(d => loadedDocs.includes(d)));
  const unloaded = mentioned.filter(j => !j.docs.some(d => loadedDocs.includes(d)));
  const filterDocs = [...new Set(loadedMentioned.flatMap(j => j.docs.filter(d => loadedDocs.includes(d))))];

  // synonym expansion
  const expansions = [];
  const weighted = [];
  const triggers = [];
  for (const g of syn.synonyms) {
    const hit = g.terms.find(t => hasPhrase(padded, t));
    if (hit) {
      triggers.push(hit);
      for (const x of g.expand) {
        if (!expansions.includes(x) && !hasPhrase(padded, x)) {
          expansions.push(x);
          weighted.push({ phrase: x, weight: g.weight ?? 1 });
        }
      }
    }
  }

  const terms = words.filter(w => !STOPWORDS.has(w) && !jurWords.has(w));
  // "define 'sell' and 'share'": quoted words are defined terms the visitor wants to see defined
  const quoted = [...raw.matchAll(/[\u201c"]([^\u201d"]{2,40})[\u201d"]/g)].map(m => normalize(m[1]).trim());
  const wantsDefinition = /\b(defin(e|es|ed|ition|itions)|meaning of|what does .{1,40} mean|means?)\b/i.test(raw);
  return { padded, words, terms, mentioned, loadedMentioned, unloaded, filterDocs, expansions, weighted,
           triggers, quoted, wantsDefinition };
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

// ---------- guided topics ----------

/** Guided topics whose trigger words appear in the question. One word scores 1, a phrase 2; shown at 2+. */
export function matchTopics(raw, topics, filterDocs = []) {
  const padded = normalize(raw);
  const out = [];
  for (const t of topics || []) {
    if (filterDocs.length && !filterDocs.some(d => (t.docs || []).includes(d))) continue;
    let score = 0;
    const hits = [];
    for (const trig of t.triggers) {
      if (hasPhrase(padded, trig)) {
        score += trig.trim().split(/\s+/).length > 1 ? 2 : 1;
        hits.push(trig);
      }
    }
    if (score >= 2) out.push({ topic: t, score, hits });
  }
  return out.sort((a, b) => b.score - a.score);
}

// ---------- filters ----------

/** Documents allowed by the visitor's filters: OR within a group, AND across groups. */
export function docsForFilters(data, f = {}) {
  return Object.keys(data.docs).filter(id => {
    const d = data.docs[id];
    return (!f.laws?.length || f.laws.includes(id)) &&
           (!f.types?.length || f.types.includes(d.doc_type)) &&
           (!f.jurisdictions?.length || f.jurisdictions.includes(d.jurisdiction));
  });
}

// ---------- search ----------

export function createEngine(MiniSearch, data) {
  const ms = new MiniSearch(INDEX_OPTIONS);
  ms.addAll(data.chunks);
  const byId = new Map(data.chunks.map(c => [c.id, c]));
  // Rarity weighting: words that appear in a large share of provisions ("personal", "information",
  // "consumer") say little about what the visitor wants, so they count for less than specific words.
  const df = new Map();
  for (const c of data.chunks) {
    const seen = new Set();
    for (const f of INDEX_OPTIONS.fields) {
      for (const raw of (c[f] || "").toLowerCase().split(/[\s\p{P}]+/u)) {
        const t = raw && INDEX_OPTIONS.processTerm(raw);
        if (t) seen.add(t);
      }
    }
    seen.forEach(t => df.set(t, (df.get(t) || 0) + 1));
  }
  return { ms, byId, df, n: data.chunks.length };
}

function rarityWeight(engine, term) {
  const n = engine.n, d = engine.df.get(term) || 1;
  const idf = Math.log(n / d);
  return Math.min(1, Math.max(MIN_TERM_WEIGHT, idf / RARE_IDF));
}

export function search(engine, data, syn, raw, opts = {}) {
  const { ms, byId } = engine;
  const loadedDocs = Object.keys(data.docs);
  const q = analyzeQuery(raw, syn, loadedDocs);
  const out = { query: q, results: [], citation: null, messages: [], expansions: q.expansions };

  // Explicit filters chosen by the visitor (opts.docs) win over laws named in the question.
  const explicit = Array.isArray(opts.docs) && opts.docs.length < loadedDocs.length;
  if (explicit) {
    if (!opts.docs.length) {
      out.messages.push("No loaded document matches the selected filters.");
      return out;
    }
    q.filterDocs = opts.docs;
  }

  let cit = lookupCitation(raw, data);
  if (cit && explicit && !opts.docs.includes(cit.chunk.doc)) {
    out.messages.push(`${cit.chunk.ref} is in ${data.docs[cit.chunk.doc].short}, which your filters exclude.`);
    cit = null;
  }
  if (cit && opts.topics && opts.topics.length &&
      !(cit.chunk.topics || []).some(t => opts.topics.includes(t))) {
    out.messages.push(`${cit.chunk.ref} is outside the topics you selected.`);
    cit = null;
  }
  if (cit) out.citation = cit;
  const pureCitation = !!cit && cit.exact;
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
  const docOK = q.filterDocs.length ? (r => q.filterDocs.includes(byId.get(r.id).doc)) : undefined;
  const topicSet = opts.topics && opts.topics.length ? new Set(opts.topics) : null;
  const topicOK = c => !topicSet || (c.topics || []).some(t => topicSet.has(t));
  const searchOpts = { ...SEARCH_OPTIONS, boostTerm: t => rarityWeight(engine, t) };
  if (docOK || topicSet) {
    searchOpts.filter = r => {
      const c = byId.get(r.id);
      return (!docOK || docOK(r)) && topicOK(c);
    };
  }
  if (q.terms.length) add(ms.search(q.terms.join(" "), searchOpts), 1);
  for (const x of q.weighted) add(ms.search(x.phrase, searchOpts), EXPANSION_WEIGHT * x.weight);

  // phrase boost: reward chunks containing multi-word phrases from the question or its expansions
  const phrases = visitorPhrases(q.words).concat(q.expansions.map(x => normalize(x).trim()));
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]).slice(0, 150);
  const final = [];
  for (const [id, score] of ranked) {
    const c = byId.get(id);
    if (q.filterDocs.length && !q.filterDocs.includes(c.doc)) continue;
    if (!topicOK(c)) continue;
    const hay = normalize(`${c.heading} ${c.sub || ""} ${c.term} ${c.text}`);
    let longest = 0;
    for (const ph of phrases) {
      const n = ph.split(" ").length;
      if (n > longest && hay.includes(" " + ph + " ")) longest = n;
    }
    let s = score * (1 + 0.2 * Math.max(0, longest - 1));
    if (c.kind === "paragraph" && c.n === 1) s *= FIRST_PARAGRAPH_BONUS;
    if (c.term && q.terms.length) {
      const asked = q.terms.join(" ");
      if (c.term.split(";").some(t => normalize(t).trim() === asked)) s *= EXACT_TERM_BOOST;
    }
    if (c.term) {
      const termHay = normalize(c.term);
      if (q.quoted.some(t => termHay.includes(" " + t + " ") || t.split(" ").every(w => termHay.includes(" " + w)))) s *= QUOTED_TERM_BOOST;
      else if (q.wantsDefinition) s *= DEFINITION_INTENT_BOOST;
      else s *= DEFINITION_DEFAULT_PENALTY;
    }
    final.push({ id, score: s, terms: [...(matched.get(id) || [])] });
  }
  final.sort((a, b) => b.score - a.score);
  // A question that names no law: after the best match, show the best match from each other law
  // (if it is nearly as good) so no single law fills the first screen.
  if ((!q.filterDocs.length || q.filterDocs.length > 1) && final.length) {
    const top = final[0].score;
    const picked = new Set([final[0].id]);
    const head = [final[0]];
    const seenDocs = new Set([byId.get(final[0].id).doc]);
    // the visitor named several laws ("GDPR vs. HIPAA"): show each one, however it scores
    const named = new Set(q.filterDocs);
    for (const r of final) {
      const d = byId.get(r.id).doc;
      if (!seenDocs.has(d) && (named.has(d) || r.score >= top * DIVERSITY_MIN_RATIO)) {
        head.push(r); picked.add(r.id); seenDocs.add(d);
      }
    }
    out.results = head.concat(final.filter(r => !picked.has(r.id)));
    return out;
  }
  out.results = final;
  return out;
}
