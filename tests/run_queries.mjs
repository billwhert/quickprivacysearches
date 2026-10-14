// Acceptance-test runner: node tests/run_queries.mjs  (needs dist/ built first)
// Uses the same lookup/search code and options as the site.
import fs from "node:fs";
import MiniSearch from "minisearch";
import { prepareQuery, lookupCitation, INDEX_OPTIONS, SEARCH_OPTIONS } from "../web/assets/lookup.js";

const data = JSON.parse(fs.readFileSync("dist/assets/search-data.json", "utf8"));
const ms = new MiniSearch(INDEX_OPTIONS);
ms.addAll(data.chunks);

function search(raw) {
  const cit = lookupCitation(raw, data);
  const ids = cit ? [cit.chunk.id] : [];
  const p = prepareQuery(raw);
  if (p.terms.length && !(cit && cit.exact && /^\s*(gdpr\s*)?(art|recital)/i.test(raw))) {
    for (const h of ms.search(p.terms.join(" "), SEARCH_OPTIONS)) if (!ids.includes(h.id)) ids.push(h.id);
  }
  return ids;
}

// [spec test id, query, accepted chunk-id prefixes (any of top 3)]
const TESTS = [
  ["1", "GDPR Article 30", ["gdpr:art:30:"]],
  ["4", "When is a DPIA required under GDPR?", ["gdpr:art:35:1", "gdpr:art:35:3"]],
  ["5", "What must a record of processing activities contain?", ["gdpr:art:30:1", "gdpr:art:30:2"]],
  ["12", "What are the lawful bases for processing under GDPR?", ["gdpr:art:6:1"]],
  ["8", "What is the deadline to respond to a data subject access request under GDPR?", ["gdpr:art:12:3", "gdpr:art:15:"]],
  ["10", "What are the breach notification timelines under GDPR?", ["gdpr:art:33:"]],
  ["18", "erase my data", ["gdpr:art:17:"]],
  ["17", "Canada breach reporting threshold", []], // expect no results
];

let pass = 0;
for (const [id, q, exp] of TESTS) {
  const top = search(q).slice(0, 3);
  const ok = exp.length === 0 ? search(q).length === 0 : top.some(t => exp.some(e => t.startsWith(e)));
  if (ok) pass++;
  console.log(`${ok ? "PASS" : "FAIL"}  test ${id.padEnd(3)} ${q}\n        -> ${top.join(", ") || "(no results)"}`);
}
console.log(`\n${pass}/${TESTS.length} passed`);
