// Shared, engine-independent search helpers: citation lookup and query preparation.
// Runs entirely in the browser; query text is never sent anywhere.

const STOPWORDS = new Set((
  "a an the of to in on at by for from with without about as is are was were be been being do does did " +
  "i me my we our you your it its this that these those and or but if then than so such what which who whom " +
  "when where why how can could should would may might must shall will under any there their them they " +
  "need needs include includes included have has had get got into out up over per via also"
).split(" "));

// Words that identify a law rather than the topic; used for filters (step 7) and stripped from the query.
const LAW_WORDS = { gdpr: "gdpr" };

export function prepareQuery(raw) {
  const words = raw.toLowerCase().replace(/[^\p{L}\p{N}\s'-]/gu, " ").split(/\s+/).filter(Boolean);
  const law = [];
  const terms = [];
  for (const w of words) {
    if (LAW_WORDS[w]) { law.push(LAW_WORDS[w]); continue; }
    if (STOPWORDS.has(w)) continue;
    terms.push(w);
  }
  return { terms, law, text: terms.join(" ") };
}

// "GDPR Article 30", "Art. 35(1)", "article 6(1)(f)", "art 4", "recital 26"
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
  return first ? { chunk: first, article: a, exact: para === null, note: para !== null ? `${a.ref}(${para}) was not found; showing the article.` : null } : null;
}

// Single source of truth for engine configuration (used by the page and the test runner).
export const INDEX_OPTIONS = { idField: "id", fields: ["term", "heading", "ref", "text"] };
export const SEARCH_OPTIONS = {
  boost: { term: 4, heading: 3, ref: 2, text: 1 }, prefix: true, fuzzy: 0.15, combineWith: "OR",
};
