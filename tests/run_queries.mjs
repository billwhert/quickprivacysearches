// Acceptance-test runner: node tests/run_queries.mjs  (needs dist/ built first)
// Uses the same lookup/search code as the site (web/assets/lookup.js).
// VERBOSE=1 prints the top results for every query.
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

// [label, query, accepted chunk-id prefixes (any of the top N)]. Empty list = expect a no-results message.
// Optional 4th element: {all: true} requires every prefix to appear; {top: n} changes N (default 3).
const SPEC = [
  ["Spec 1  GDPR reference lookup", "GDPR Article 30", ["gdpr:art:30:"]],
  ["Spec 2  CCPA reference lookup", "1798.105", ["ccpa:sec:1798.105:a"]],
  ["Spec 3  HIPAA reference lookup", "164.502(b)", ["hipaa:sec:164.502:b"]],
  ["Spec 4  DPIA required", "When is a DPIA required under GDPR?", ["gdpr:art:35:1", "gdpr:art:35:3"]],
  ["Spec 5  record of processing", "What must a record of processing activities contain?", ["gdpr:art:30:1", "gdpr:art:30:2"]],
  ["Spec 6  exceptions to right to delete", "What are the exceptions to the CCPA right to delete?", ["ccpa:sec:1798.105:d"]],
  ["Spec 7  HIPAA minimum necessary", "What is the HIPAA minimum necessary standard?", ["hipaa:sec:164.502:b", "hipaa:sec:164.514:d"]],
  ["Spec 8  DSAR deadline", "What is the deadline to respond to a data subject access request under GDPR?", ["gdpr:art:12:3", "gdpr:art:15:"]],
  ["Spec 9  define sell and share", "How does CCPA define “sell” and “share”?",
    ["ccpa:sec:1798.140:ad", "ccpa:sec:1798.140:ah"], { all: true, top: 5 }],
  ["Spec 10 breach timelines, both laws", "What are the breach notification timelines under GDPR vs. HIPAA?",
    ["gdpr:art:33:1", "hipaa:sec:164.404", "hipaa:sec:164.408", "hipaa:sec:164.410"], { groups: [[0], [1, 2, 3]], top: 6 }],
  ["Spec 11 business associate", "What counts as a “business associate” under HIPAA?", ["hipaa:sec:160.103:business-associate"]],
  ["Spec 12 lawful bases", "What are the lawful bases for processing under GDPR?", ["gdpr:art:6:1"]],
  ["Spec 13 CCPA privacy notice contents", "What must a CCPA privacy notice include?",
    ["ccpa:sec:1798.130:a", "ccpa:sec:1798.100:a", "ccpa_regs:sec:7011", "ccpa_regs:sec:7012"]],
  ["Spec 16 (approx.) does CCPA apply", "Does CCPA apply to my small business", ["ccpa:sec:1798.140:d"]],
  ["Spec 15 (approx.) Do Not Sell link", "Do I need a Do Not Sell link", ["ccpa:sec:1798.135", "ccpa_regs:sec:7013", "ccpa:sec:1798.120"]],
  ["Spec 17 outside loaded sources", "What is Canada's breach reporting threshold?", []],
  ["Spec 18 synonym wording", "erase my data", ["gdpr:art:17:"]],
  ["Spec 18b synonym wording (CA)", "delete my personal information", ["ccpa:sec:1798.105"]],
];
const EXTRA = [
  ["GDPR breach 72 hours", "breach notification to supervisory authority within 72 hours", ["gdpr:art:33:1"]],
  ["GDPR definition personal data", "definition of personal data", ["gdpr:art:4:1"]],
  ["GDPR right to erasure", "right to erasure", ["gdpr:art:17:1"]],
  ["GDPR DPO designation", "when must a data protection officer be designated", ["gdpr:art:37:1"]],
  ["GDPR conditions for consent", "conditions for consent", ["gdpr:art:7:"]],
  ["GDPR fines", "administrative fines for infringement", ["gdpr:art:83:"]],
  ["GDPR third-country transfers", "transfer of personal data to a third country", ["gdpr:art:44:", "gdpr:art:45:", "gdpr:art:46:"]],
  ["GDPR children consent", "children's consent information society services", ["gdpr:art:8:1"]],
  ["GDPR what is a DPIA", "what is a data protection impact assessment", ["gdpr:art:35:"]],
  ["GDPR joint controllers", "joint controllers", ["gdpr:art:26:1"]],
  ["GDPR data portability", "right to data portability", ["gdpr:art:20:1"]],
  ["GDPR processor contract", "contract between controller and processor must contain", ["gdpr:art:28:3"]],
  ["GDPR by design", "data protection by design and by default", ["gdpr:art:25:1"]],
  ["GDPR DSAR (abbrev.)", "how do I handle a DSAR", ["gdpr:art:12:", "gdpr:art:15:"]],
  ["GDPR ROPA (abbrev.)", "do we need a ROPA", ["gdpr:art:30:1"]],
  ["GDPR SCCs", "do we need SCCs for transfers", ["gdpr:art:46:"]],
  ["GDPR right to be forgotten", "right to be forgotten", ["gdpr:art:17:1"]],
  ["GDPR cookies consent", "do I need consent for cookies under GDPR", ["gdpr:art:6:1", "gdpr:art:7:", "gdpr:art:4:11", "gdpr:rct:30", "gdpr:rct:32"]],
  ["out of scope: Virginia", "Virginia consumer data protection act opt out", []],
  ["CCPA citation with subdivision", "Section 1798.140(ad)", ["ccpa:sec:1798.140:ad"]],
  ["CCPA citation, Civil Code form", "Cal. Civ. Code 1798.100(a)", ["ccpa:sec:1798.100:a"]],
  ["Regs citation §", "§ 7011", ["ccpa_regs:sec:7011"]],
  ["Regs citation with subsection", "11 CCR 7025(b)", ["ccpa_regs:sec:7025:b"]],
  ["CalOPPA citation", "22575(b)", ["caloppa:sec:22575:b"]],
  ["CalOPPA do not track", "do not track disclosure in a privacy policy", ["caloppa:sec:22575:b"], { top: 5 }],
  ["Regs opt-out preference signal", "global privacy control opt-out preference signal", ["ccpa_regs:sec:7025"]],
  ["Regs dark patterns", "what is a dark pattern", ["ccpa_regs:sec:7004"]],
  ["Regs notice at collection", "notice at collection requirements", ["ccpa_regs:sec:7012", "ccpa:sec:1798.100:a"]],
  ["Regs service provider contract", "service provider contract requirements", ["ccpa_regs:sec:7051", "ccpa:sec:1798.100:d", "ccpa:sec:1798.140:ag"]],
  ["CCPA right to correct", "right to correct inaccurate personal information", ["ccpa:sec:1798.106"]],
  ["CCPA sensitive PI definition", "definition of sensitive personal information", ["ccpa:sec:1798.140:ae"]],
  ["CCPA minors opt-in", "selling personal information of consumers under 16", ["ccpa:sec:1798.120:c", "ccpa_regs:sec:7070", "ccpa_regs:sec:7071"]],
  ["CCPA financial incentive notice", "notice of financial incentive", ["ccpa_regs:sec:7016", "ccpa:sec:1798.125"]],
  ["CCPA private right of action", "private right of action for data breach statutory damages", ["ccpa:sec:1798.150"]],
  ["CCPA enforcement fines", "administrative fine for violating the CCPA", ["ccpa:sec:1798.155", "ccpa:sec:1798.199.90"]],
  ["CCPA risk assessment", "when must a business conduct a risk assessment", ["ccpa_regs:sec:7150"]],
  ["CCPA verification of requests", "how to verify a consumer request", ["ccpa_regs:sec:7060"]],
  ["HIPAA citation, section only", "164.524", ["hipaa:sec:164.524:a"]],
  ["HIPAA citation with form", "45 CFR 164.404(b)", ["hipaa:sec:164.404:b"]],
  ["HIPAA citation § 160.103", "§ 160.103", ["hipaa:sec:160.103:0"]],
  ["HIPAA patient access", "how can a patient get a copy of their medical records", ["hipaa:sec:164.524"]],
  ["HIPAA de-identification", "how do you de-identify health data", ["hipaa:sec:164.514"]],
  ["HIPAA BAA", "what must a business associate agreement contain", ["hipaa:sec:164.504:e", "hipaa:sec:164.502:e", "hipaa:sec:164.314"]],
  ["HIPAA notice of privacy practices", "what must a notice of privacy practices include", ["hipaa:sec:164.520"]],
  ["HIPAA security risk analysis", "security risk analysis requirement", ["hipaa:sec:164.308:a"]],
  ["HIPAA breach media notice", "when must a breach be reported to the media", ["hipaa:sec:164.406"]],
  ["HIPAA breach to HHS", "breach notification to the Secretary of HHS", ["hipaa:sec:164.408"]],
  ["HIPAA civil money penalties", "hipaa civil money penalty amounts", ["hipaa:sec:160.404", "hipaa:sec:160.408"]],
  ["HIPAA psychotherapy notes", "psychotherapy notes authorization", ["hipaa:sec:164.508:a", "hipaa:sec:164.501"]],
  ["HIPAA family members", "can a provider share patient information with a family member", ["hipaa:sec:164.510"]],
  ["HIPAA encryption safeguard", "encryption of ePHI technical safeguards", ["hipaa:sec:164.312"]],
  ["HIPAA training", "workforce training on privacy policies", ["hipaa:sec:164.530:b", "hipaa:sec:164.308:a.5"]],
  ["HIPAA who is covered", "who is a covered entity", ["hipaa:sec:160.103:covered-entity", "hipaa:sec:160.102"]],
  ["CCPA response deadline", "how long to respond to a request to delete", ["ccpa_regs:sec:7021", "ccpa:sec:1798.130:a"]],
];

function filterTest() {
  const q = "HIPAA breach notification requirements";
  const { ids } = topIds(q);
  const ok = ids.length > 0 && ids.every(i => i.startsWith("hipaa:"));
  console.log(`${ok ? "PASS" : "FAIL"}  Spec 19 HIPAA filter returns only HIPAA: "${q}" (${ids.length} results)`);
  return ok ? 1 : 0;
}

function run(title, tests) {
  console.log(`\n== ${title} ==`);
  let pass = 0;
  for (const [label, q, exp, opt = {}] of tests) {
    const { ids, r } = topIds(q);
    const top = ids.slice(0, opt.top || 3);
    let ok;
    if (exp.length === 0) ok = ids.length === 0 && r.messages.length > 0;
    else if (opt.groups) ok = opt.groups.every(g => g.some(i => top.some(t => t.startsWith(exp[i]))));
    else if (opt.all) ok = exp.every(e => top.some(t => t.startsWith(e)));
    else ok = top.some(t => exp.some(e => t.startsWith(e)));
    if (ok) pass++;
    console.log(`${ok ? "PASS" : "FAIL"}  ${label}: "${q}"`);
    if (!ok || process.env.VERBOSE) console.log(`        -> ${top.join(", ") || "(none)"}${r.messages[0] ? "  | " + r.messages[0] : ""}`);
  }
  console.log(`${pass}/${tests.length}`);
  return [pass, tests.length];
}

const [p1a, n1a] = run("Spec acceptance tests (applicable to loaded laws)", SPEC);
const f19 = filterTest();
const p1 = p1a + f19, n1 = n1a + 1;
const [p2, n2] = run("Extra queries", EXTRA);
console.log(`\nTotal ${p1 + p2}/${n1 + n2}`);
process.exitCode = p1 === n1 ? 0 : 1;
