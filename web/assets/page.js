// Behaviour shared by the document pages: copy-link buttons and the section filter.
// Nothing here talks to a server or stores anything.

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

document.addEventListener("click", async e => {
  const b = e.target.closest("button.copy-link");
  if (!b) return;
  const url = new URL(location.href);
  url.hash = b.dataset.frag ? `#${b.dataset.frag}` : "";
  const ok = await copyText(url.href);
  let t = document.getElementById("toast");
  if (!t) {
    t = Object.assign(document.createElement("div"), { id: "toast", className: "toast" });
    t.setAttribute("role", "status");
    document.body.appendChild(t);
  }
  t.textContent = ok ? "Link copied" : "Could not copy the link";
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 1800);
});

// "Find a section": narrows the contents list on a document's front page as you type.
const box = document.getElementById("toc-filter");
if (box) {
  const items = [...document.querySelectorAll(".chapters li, .recs a")];
  const chapters = [...document.querySelectorAll(".chapter")];
  const empty = document.getElementById("toc-empty");
  const apply = () => {
    const words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const el of items) {
      const hay = (el.textContent + " " + (el.dataset.find || "")).toLowerCase();
      const hit = words.every(w => hay.includes(w));
      el.hidden = !hit;
      if (hit) shown++;
    }
    for (const c of chapters) {
      c.hidden = ![...c.querySelectorAll("li, .recs a")].some(el => !el.hidden);
    }
    if (empty) empty.hidden = shown > 0 || !words.length;
  };
  box.addEventListener("input", apply);
}

// Compare view: hide or show a law's column.
document.addEventListener("click", e => {
  const b = e.target.closest("button[data-col]");
  if (!b) return;
  const on = b.getAttribute("aria-pressed") !== "true";
  b.setAttribute("aria-pressed", String(on));
  const col = document.querySelector(`.cmp-col[data-col="${b.dataset.col}"]`);
  if (col) col.hidden = !on;
  const grid = document.querySelector(".cmp-grid");
  if (grid) grid.style.setProperty("--cols", String(document.querySelectorAll(".cmp-col:not([hidden])").length || 1));
});
