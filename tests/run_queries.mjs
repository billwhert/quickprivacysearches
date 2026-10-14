// Acceptance-test runner: node tests/run_queries.mjs  (needs dist/ built first)
// Uses the same lookup/search code as the site (web/assets/lookup.js).
import fs from "node:fs";
import MiniSearch from "minisearch";
import { createEngine, search } from "../web/assets/lookup.js";

const data = JSON.parse(fs.readFileSync("dist/assets/search-data.json", "utf8"));
const syn = JSON.parse(fs.readFileSync("dist/assets/synonyms.json", "utf8"));
const engine = createEngine(MiniSearch, data);

function topIds(raw) {
  const r = search(engine, data, syn, raw);
  const ids = [];
  if (r.citation) ids.push(r.citation.chunk.id);
  for (const h of r.results) if (!ids.includes(h.id)) ids.push(h.id);
  return { ids, r };
}

// [label, query, accepted chunk-id prefixes (any of top 3)]. Empty list = expect no results.
const SPEC = [
  ["Spec 1  reference lookup", "GDPR Article 30", ["gdpr:art:30:"]],
  ["Spec 4  DPIA required", "When is a DPIA required under GDPR?", ["gdpr:art:35:1", "gdpr:art:35:3"]],
  ["Spec 5  record of processing", "What must a record of processing activities contain?", ["gdpr:art:30:1", "gdpr:art:30:2"]],
  ["Spec 8  DSAR deadline", "What is the deadline to respond to a data subject access request under GDPR?", ["gdpr:art:12:3", "gdpr:art:15:"]],
  ["Spec 10 breach timelines (GDPR part)", "What are the breach notification timelines under GDPR vs. HIPAA?", ["gdpr:art:33:1"]],
  ["Spec 12 lawful bases", "What are the lawful bases for processing under GDPR?", ["gdpr:art:6:1"]],
  ["Spec 17 outside loaded sources", "What is Canada's breach reporting threshold?", []],
  ["Spec 18 synonym wording", "erase my data", ["gdpr:art:17:"]],
];
const EXTRA = [
  ["breach 72 hours", "breach notification to supervisory authority within 72 hours", ["gdpr:art:33:1"]],
  ["definition personal data", "definition of personal data", ["gdpr:art:4:1"]],
  ["right to erasure", "right to erasure", ["gdpr:art:17:1"]],
  ["DPO designation", "when must a data protection officer be designated", ["gdpr:art:37:1"]],
  ["conditions for consent", "conditions for consent", ["gdpr:art:7:"]],
  ["fines", "administrative fines for infringement", ["gdpr:art:83:"]],
  ["third-country transfers", "transfer of personal data to a third country", ["gdpr:art:44:", "gdpr:art:45:", "gdpr:art:46:"]],
  ["children consent", "children's consent information society services", ["gdpr:art:8:1"]],
  ["what is a DPIA", "what is a data protection impact assessment", ["gdpr:art:35:"]],
  ["joint controllers", "joint controllers", ["gdpr:art:26:1"]],
  ["data portability", "right to data portability", ["gdpr:art:20:1"]],
  ["processor contract", "contract between controller and processor must contain", ["gdpr:art:28:3"]],
  ["by design", "data protection by design and by default", ["gdpr:art:25:1"]],
  ["DSAR (abbrev.)", "how do I handle a DSAR", ["gdpr:art:12:", "gdpr:art:15:"]],
  ["ROPA (abbrev.)", "do we need a ROPA", ["gdpr:art:30:1"]],
  ["SCCs", "do we need SCCs for transfers", ["gdpr:art:46:"]],
  ["right to be forgotten", "right to be forgotten", ["gdpr:art:17:1"]],
  ["cookies consent", "do I need consent for cookies", ["gdpr:art:6:1", "gdpr:art:7:", "gdpr:art:4:11", "gdpr:rct:30", "gdpr:rct:32"]],
  ["out of scope: Virginia", "Virginia consumer data protection act opt out", []],
];

function run(title, tests) {
  console.log(`\n== ${title} ==`);
  let pass = 0;
  for (const [label, q, exp] of tests) {
    const { ids, r } = topIds(q);
    const top = ids.slice(0, 3);
    const ok = exp.length === 0 ? ids.length === 0 && r.messages.length > 0
                                : top.some(t => exp.some(e => t.startsWith(e)));
    if (ok) pass++;
    console.log(`${ok ? "PASS" : "FAIL"}  ${label}: "${q}"`);
    if (!ok || process.env.VERBOSE) console.log(`        -> ${top.join(", ") || "(none)"}${r.messages[0] ? "  | " + r.messages[0] : ""}`);
  }
  console.log(`${pass}/${tests.length}`);
  return [pass, tests.length];
}

const [p1, n1] = run("Spec acceptance tests (GDPR-only subset)", SPEC);
const [p2, n2] = run("Extra GDPR queries", EXTRA);
console.log(`\nTotal ${p1 + p2}/${n1 + n2}`);
process.exitCode = p1 === n1 ? 0 : 1;
