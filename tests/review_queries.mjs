// Print the top results for a file of questions so they can be judged by eye.
//   node tests/review_queries.mjs tests/review/batch1.txt [N]
// One question per line; lines starting with # are section labels.
import fs from "node:fs";
import MiniSearch from "minisearch";
import { createEngine, search } from "../web/assets/lookup.js";

const data = JSON.parse(fs.readFileSync("dist/assets/search-data.json", "utf8"));
const syn = JSON.parse(fs.readFileSync("dist/assets/synonyms.json", "utf8"));
const engine = createEngine(MiniSearch, data);
const byId = new Map(data.chunks.map(c => [c.id, c]));
const topN = +(process.argv[3] || 3);

for (const line of fs.readFileSync(process.argv[2], "utf8").split("\n")) {
  const q = line.trim();
  if (!q) continue;
  if (q.startsWith("#")) { console.log(`\n${q}`); continue; }
  const r = search(engine, data, syn, q);
  const ids = [];
  if (r.citation) ids.push(r.citation.chunk.id);
  for (const h of r.results) if (!ids.includes(h.id)) ids.push(h.id);
  console.log(`\n? ${q}${r.outOfScope ? "   [out of scope]" : ""}`);
  if (!ids.length) console.log(`   (no results) ${r.messages[0] || ""}`);
  ids.slice(0, topN).forEach((id, i) => {
    const c = byId.get(id);
    const what = (c.term ? `Definition: ${c.term}` : (c.sub || c.heading || "")).slice(0, 70);
    console.log(`   ${i + 1}. ${c.ref}  |  ${what}`);
  });
}
