#!/usr/bin/env python3
"""Regenerate hero-thumbs-review.html — a clickable contact sheet of the
current hero-thumbs pool for curation. Open it in a browser, click each bad
crop, and paste the --prune command it builds. The page is a local review
tool; it is not committed or deployed.

Run from the repo root (no dependencies): python3 scripts/hero_thumbs_review.py
"""
import html
import json
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(repo_root, "hero-thumbs", "manifest.json"), encoding="utf-8") as f:
    manifest = json.load(f)

cards = []
for t in manifest["thumbs"]:
    label = html.escape(f'{t["name"]} — {t["city"]} {t["state"]} {t["volume_year"]} · {t["category"]}')
    cards.append(
        f'<figure data-id="{t["id"]}"><img src="hero-thumbs/{t["file"]}" loading="lazy">'
        f'<figcaption><code>{t["id"]}</code> {label}</figcaption></figure>')

page = '''<!doctype html><html><head><meta charset="utf-8"><title>hero-thumbs review</title><style>
body{font:14px/1.4 -apple-system,sans-serif;margin:16px;background:#f4efe3}
#bar{position:sticky;top:0;background:#f4efe3;padding:8px 0;border-bottom:1px solid #ccc;margin-bottom:12px}
#cmd{width:100%;font:12px monospace;padding:6px;box-sizing:border-box}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:10px}
figure{margin:0;background:#fff;border:3px solid transparent;border-radius:4px;padding:6px;cursor:pointer}
figure.marked{border-color:#c0392b}
img{width:100%;display:block}
figcaption{font-size:12px;margin-top:4px}code{background:#eee;padding:0 3px}
</style></head><body>
<div id="bar"><strong>Click any bad crop to mark it</strong> — the prune command updates below.<br>
<input id="cmd" readonly value="(nothing marked yet)" onclick="this.select()"></div>
<div class="grid">''' + "\n".join(cards) + '''</div>
<script>
const marked = new Set();
document.querySelectorAll('figure').forEach(f => f.addEventListener('click', () => {
  const id = f.dataset.id;
  marked.has(id) ? marked.delete(id) : marked.add(id);
  f.classList.toggle('marked');
  document.getElementById('cmd').value = marked.size
    ? 'python3 scripts/build_hero_thumbs.py --prune ' + [...marked].join(' ')
    : '(nothing marked yet)';
}));
</script></body></html>'''

out = os.path.join(repo_root, "hero-thumbs-review.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(page)
print(f"wrote {out} with {len(cards)} cards")
