#!/usr/bin/env python3
"""Export every knowledge-point card in the vault as one self-contained HTML page.

Why a generated page instead of a hand-written one: the cards live in markdown
真源 and will keep growing. Anything hand-maintained alongside them is a second
copy that rots -- the same reason indexes/ is script-rebuilt and never edited.

Usage:
    python ExportPointsHtml.py [OUT_PATH]

Supports only the markdown subset the cards actually use (headings, tables,
lists, bold, inline code, blockquote, hr, task lists). No dependencies, so it
runs anywhere Python does.
"""

import io
import os
import re
import sys
from html import escape

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = r"D:\bio-error-vault-知识点卡.html"


def resolve_points_dir():
    root = os.environ.get("BIOVAULT_HOME")
    if not root:
        cfg = os.path.join(SKILL_DIR, "config.json")
        if os.path.isfile(cfg):
            import json
            with open(cfg, encoding="utf-8") as fh:
                root = json.load(fh).get("dataRoot", "")
            root = os.path.expanduser(root) if root else None
    if not root:
        sys.exit("data root not resolvable (exit 6)")
    pts = os.path.join(root, "data", "subjects", "生物", "points")
    if not os.path.isdir(pts):
        sys.exit("points dir not found: %s" % pts)
    return pts


def parse_front_matter(text):
    """Minimal YAML-subset parser, BOM-stripping included.

    A BOM'd file would otherwise parse as "no front matter" and every card
    would render with empty fields instead of failing loudly.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta, body = {}, text[end + 4:]
    for line in text[3:end].splitlines():
        if not line.strip() or line[0] in " \t#>":
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[m.group(1)] = val
    return meta, body


def inline(text):
    """Escape first, then re-introduce the two inline marks the cards use."""
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_html(body):
    out, i = [], 0
    lines = body.splitlines()
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            out.append(render_table(block))
            continue

        if stripped == "---":
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (level, inline(m.group(2)), level))
            i += 1
            continue

        if stripped.startswith(">"):
            block = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>"
                       % inline(" ".join(x for x in block if x)))
            continue

        m = re.match(r"^-\s+\[( |x|X)\]\s+(.*)$", stripped)
        if m:
            checked = " checked" if m.group(1).lower() == "x" else ""
            out.append("<li class='task'><input type='checkbox'%s disabled> %s</li>"
                       % (checked, inline(m.group(2))))
            i += 1
            continue

        if re.match(r"^[-*]\s+", stripped):
            out.append("<ul><li>%s</li></ul>" % inline(re.sub(r"^[-*]\s+", "", stripped)))
            i += 1
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            out.append("<ol><li>%s</li></ol>" % inline(re.sub(r"^\d+[.)]\s+", "", stripped)))
            i += 1
            continue

        # 段落：先把连续的非特殊行累积起来再渲染。
        # 必须这样——卡片里存在跨行的 **加粗**，逐行处理会让开合标记配不上对。
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("|", ">", "#"))
                    or nxt == "---"
                    or re.match(r"^[-*]\s+", nxt)
                    or re.match(r"^\d+[.)]\s+", nxt)
                    or re.match(r"^-\s+\[( |x|X)\]", nxt)):
                break
            para.append(nxt)
            i += 1
        out.append("<p>%s</p>" % inline(join_lines(para)))
    return "\n".join(out)


def join_lines(chunks):
    """Join wrapped lines. No space between CJK, one space between ASCII words."""
    text = ""
    for chunk in chunks:
        if text and text[-1].isascii() and text[-1].isalnum() \
                and chunk[0].isascii() and chunk[0].isalnum():
            text += " "
        text += chunk
    return text


def render_table(block):
    rows = []
    for raw in block:
        cells = [c.strip() for c in raw.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return ""
    head, rest = rows[0], rows[1:]
    out = ["<table><thead><tr>"]
    out += ["<th>%s</th>" % inline(c) for c in head]
    out.append("</tr></thead><tbody>")
    for row in rest:
        out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


CSS = """
:root{--bg:#fbfaf8;--card:#fff;--ink:#1f2328;--dim:#6b7280;--line:#e5e3df;
--accent:#2f6f4e;--warn:#b45309;--chip:#eef3ef}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{position:sticky;top:0;z-index:9;background:rgba(251,250,248,.96);
backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:18px 24px 12px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:var(--dim);font-size:13px}
.bar{margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button,input{font:inherit;font-size:13px;padding:5px 11px;border:1px solid var(--line);
border-radius:999px;background:#fff;color:var(--ink);cursor:pointer}
button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
input{width:220px;cursor:text}
main{max-width:860px;margin:0 auto;padding:24px}
article{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 24px;margin-bottom:18px}
.meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px}
.tag{background:var(--chip);color:var(--accent);border-radius:999px;padding:2px 10px;
font-size:12px}
.tag.id{color:var(--dim);background:#f1f0ee}
article h2{margin:0 0 2px;font-size:18px}
article h3{margin:22px 0 8px;font-size:16px;color:var(--accent);
border-left:3px solid var(--accent);padding-left:9px}
article p,article li{margin:6px 0}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#f5f4f2;font-weight:600}
blockquote{margin:12px 0;padding:10px 14px;border-left:3px solid var(--warn);
background:#fdf8f1;color:#7a4a09;border-radius:0 6px 6px 0}
code{background:#f1f0ee;padding:1px 5px;border-radius:4px;font-size:.9em}
hr{border:0;border-top:1px dashed var(--line);margin:18px 0}
li.task{list-style:none;margin-left:-18px}
.hidden{display:none}
#none{padding:40px;text-align:center;color:var(--dim)}
footer{max-width:860px;margin:0 auto;padding:8px 24px 40px;color:var(--dim);font-size:13px}
@media print{header{position:static}button{display:none}.hidden{display:block}}
"""

JS = """
const cards=[...document.querySelectorAll('article')];
const chips=[...document.querySelectorAll('.bar button')];
const box=document.getElementById('q');
let f=new Set(),kw='';
function apply(){
  let n=0;
  cards.forEach(c=>{
    const ch=c.dataset.chapter, k=c.dataset.kind;
    const ok=(!f.size||f.has('c:'+ch)||f.has('k:'+k))
            &&(!kw||c.textContent.toLowerCase().includes(kw));
    c.classList.toggle('hidden',!ok); if(ok)n++;
  });
  document.getElementById('none').style.display=n?'none':'block';
  document.getElementById('cnt').textContent='显示 '+n+' / '+cards.length+' 张卡';
}
chips.forEach(b=>b.onclick=()=>{
  const v=b.dataset.v;
  if(b.classList.contains('on')){f.delete(v);b.classList.remove('on')}
  else{f.add(v);b.classList.toggle('on',true)}
  apply();
});
box.addEventListener('input',()=>{kw=box.value.trim().toLowerCase();apply()});
document.getElementById('reset').onclick=()=>{
  f.clear();kw='';box.value='';
  chips.forEach(b=>b.classList.remove('on'));apply();
};
apply();
"""


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    pts = resolve_points_dir()
    cards = []
    # 递归：points/ 按章分了子目录。只扫一层会渲染出 0 张卡的空页面，
    # 看起来像「还没有知识点」，其实是扫描漏了。
    for dirpath, dirnames, filenames in os.walk(pts):
        dirnames.sort()
        for name in sorted(filenames):
            if not (name.endswith(".md") and name.startswith("KP-")):
                continue
            with io.open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                meta, body = parse_front_matter(fh.read())
            cards.append((meta, body))

    if not cards:
        sys.stderr.write("WARNING: no KP-*.md under %s (searched recursively)\n" % pts)

    chapters, kinds = [], []
    for meta, _ in cards:
        for val, bucket in ((meta.get("chapter", ""), chapters),
                            (meta.get("kind", ""), kinds)):
            if val and val not in bucket:
                bucket.append(val)

    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>生物错题仓 · 知识点卡</title><style>%s</style></head><body>" % CSS,
        "<header><h1>生物错题仓 · 知识点卡</h1>",
        "<div class='sub'>%d 张卡 · 来源 <code>data/subjects/生物/points/</code> "
        "· 本页由脚本生成，<strong>不要手改</strong>，改源文件后重新生成</div>" % len(cards),
        "<div class='bar'>",
        "<button data-v='__all' id='reset'>重置</button>",
    ]
    for c in chapters:
        parts.append("<button data-v='c:%s'>%s</button>" % (escape(c), escape(c)))
    for k in kinds:
        parts.append("<button data-v='k:%s'>%s</button>" % (escape(k), escape(k)))
    parts.append("<input id='q' placeholder='搜索关键词…'>")
    parts.append("<span class='sub' id='cnt'></span></div></header><main>")

    for meta, body in cards:
        title = meta.get("title", meta.get("id", ""))
        chips = "".join(
            "<span class='tag %s'>%s</span>" % (cls, escape(val))
            for cls, val in (("", meta.get("kind", "")),
                             ("", meta.get("chapter", "")),
                             ("", meta.get("point", "")),
                             ("id", meta.get("id", "")))
            if val)
        parts.append(
            "<article data-chapter='%s' data-kind='%s'>"
            "<h2>%s</h2><div class='meta'>%s</div>%s</article>"
            % (escape(meta.get("chapter", "")), escape(meta.get("kind", "")),
               escape(title), chips, md_to_html(body)))

    parts.append("<div id='none'>没有匹配的卡片</div></main>")
    parts.append("<footer>错题是证据，知识点是资产 —— 决策 1.0。"
                 "卡片与 `points/` 目录同源，删了重来即可。</footer>")
    parts.append("<script>%s</script></body></html>" % JS)

    with io.open(out_path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print("wrote %s (%d cards, %d bytes)"
          % (out_path, len(cards), os.path.getsize(out_path)))


if __name__ == "__main__":
    main()