#!/usr/bin/env python3
"""Validate records in the data vault against the four reference sources.

Checks, in order of severity:

  1. enum hits      chapter/point vs taxonomy, cause vs causes.md,
                    kind vs kinds.md, 规范 vs norms.md
  2. required body  kind-specific sections on the card, plus 错因 / 我的错解 /
                    教训 on every `## 错题证据` block (schema 1.13)
  3. field shape    required fields present, types parse, value in 高/中/低,
                    next_review looks like YYYY-MM-DD
  4. reverse gate   NO sensitive strings in the data repo  (see below)

The reverse gate is the important one. Every other check can be satisfied by
editing a file; this one exists because a leaked school name cannot be
un-leaked -- git history keeps it. It therefore fails the whole run.

Exit codes:
  0  all clean
  2  field-shape / body-section problems
  4  enum problems
  6  data root not resolvable   (NEVER silently fall back to examples/)
"""

import os
import re
import sys

EXIT_ENUM = 4
EXIT_SHAPE = 2
EXIT_NO_DATA = 6
EXIT_SENSITIVE = 5

# schema 1.13：错题不再单独成文件，证据挂在知识点卡的 `## 错题证据` 下。
# 复习状态因此也落在卡上，缺了就无法排期。
POINT_REQUIRED = ["id", "title", "kind", "created", "updated",
                  "status", "review_count", "next_review", "verified"]
EVIDENCE_REQUIRED = ("错因", "我的错解", "教训")
VALUES = ["高", "中", "低"]
QTYPES = ["选择题", "多选题", "填空", "图表分析", "实验设计", "简答", "计算", "其他"]
STATUSES = ["新错", "已订正", "已复现", "已掌握"]
DIFFICULTIES = ["易", "中", "难"]

# 脱敏红线：这些字符串一旦进入 git 历史就不可逆
SENSITIVE = ["厦门一中", "厦一中", "厦门第一中学", "4213671",
             "林妍", "谢巧", "陈茜"]

# 正文区段按 kind 分组，与 kinds.md 的「正文必填区段」列一致
POINT_SECTIONS = {
    "概念": ["## 一句话", "## 易混对象"],
    "机制": ["## 一句话", "## 为什么"],
    "对照": ["## 一句话", "## 易混对象", "## 典型考法"],
    "步骤": ["## 一句话", "## 为什么", "## 典型考法"],
    "措辞": ["## 一句话", "## 易混对象"],
    "公式": ["## 一句话", "## 为什么"],
    "易错": ["## 一句话", "## 典型考法"],
    "数据": ["## 一句话"],
}


def out(msg):
    """stdout = what the user/AI reads. Windows console is GBK, so force utf-8."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(msg)


def resolve_data_root(skill_dir):
    env = os.environ.get("BIOVAULT_HOME")
    if env:
        return env
    cfg = os.path.join(skill_dir, "config.json")
    if os.path.isfile(cfg):
        try:
            import json
            with open(cfg, encoding="utf-8") as fh:
                val = json.load(fh).get("dataRoot", "")
            if val:
                return os.path.expanduser(val)
        except Exception as exc:
            print("config.json unreadable: %s" % exc, file=sys.stderr)
    return None


def parse_front_matter(text):
    """Minimal YAML-subset parser. No PyYAML dependency on purpose --
    a validator that needs its own deps is a validator nobody runs.

    Strips a leading UTF-8 BOM first: with the BOM left in place every file
    looks like it has no front matter, so the validator silently passes
    records it should flag. PowerShell 5.1 `Set-Content -Encoding utf8`
    writes exactly such a BOM.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end]
    body = text[end + 4:]
    meta = {}
    for line in block.splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#", ">")):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[m.group(1)] = val
    return meta, body


def enum_from_table(path, column=0):
    """First column of every markdown table row, backticks stripped.

    Decorators are stripped because kinds.md once shipped | **`对照`** |
    which silently yielded '*`对照`*' and broke every 对照 card.
    """
    if not os.path.isfile(path):
        return None
    values = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) <= column:
                continue
            cell = cells[column]
            if not cell or set(cell) <= set("-: "):
                continue
            cell = cell.replace("`", "").replace("*", "").strip()
            if cell and not cell.endswith("：") and len(cell) <= 12:
                values.add(cell)
    return values


def load_enums(skill_dir):
    ref = os.path.join(skill_dir, "reference")
    tax = enum_from_table(os.path.join(ref, "taxonomy.md"))
    chapters, sections = set(), set()
    if tax:
        # taxonomy.md 的机器可读表是 | chapter | section | 两列
        with open(os.path.join(ref, "taxonomy.md"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("|"):
                    continue
                cells = [c.strip().replace("`", "") for c in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0] and set(cells[0]) - set("-: "):
                    chapters.add(cells[0])
                    sections.add(cells[1])
    return {
        "chapters": chapters,
        "sections": sections,
        "causes": enum_from_table(os.path.join(ref, "causes.md")),
        "kinds": enum_from_table(os.path.join(ref, "kinds.md")),
        "norms": enum_from_table(os.path.join(ref, "norms.md")),
    }


def check_enum(kind, value, allowed, path, problems, warnings):
    if not allowed:
        return
    head = value.split("·")[0].strip() if kind == "sections" else value
    if head not in allowed:
        problems.append("%s: %s `%s` not in enum" % (path, kind, head))


def evidence_section(body):
    match = re.search(r"^## 错题证据\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    return match.group(1) if match else ""


def validate_point(path, text, enums, problems, warnings):
    meta, body = parse_front_matter(text)
    for field in POINT_REQUIRED:
        if field not in meta:
            problems.append("%s: missing field `%s`" % (path, field))
    kind = meta.get("kind", "")
    check_enum("kinds", kind, enums["kinds"], path, problems, warnings)
    if meta.get("chapter"):
        check_enum("chapters", meta["chapter"], enums["chapters"], path, problems, warnings)
    if meta.get("point"):
        check_enum("sections", meta["point"], enums["sections"], path, problems, warnings)
    tags = meta.get("tags", "")
    if not meta.get("chapter") and not [t for t in tags.split(",") if t.strip()]:
        problems.append("%s: no chapter AND no tags (兜底规则)" % path)
    for section in POINT_SECTIONS.get(kind, ["## 一句话"]):
        if section not in body:
            problems.append("%s: kind=%s missing section `%s`" % (path, kind, section))

    if meta.get("status") and meta["status"] not in STATUSES:
        problems.append("%s: status `%s` not in enum" % (path, meta["status"]))
    if meta.get("value") and meta["value"] not in VALUES:
        problems.append("%s: value `%s` not in 高/中/低" % (path, meta["value"]))
    if meta.get("verified") not in ("true", "false"):
        problems.append("%s: verified must be true/false, got `%s`"
                        % (path, meta.get("verified")))
    due = meta.get("next_review")
    if due and not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        problems.append("%s: next_review `%s` is not YYYY-MM-DD" % (path, due))

    # 证据块：每块都必须能读出错因、错解、教训 —— 否则复习时无据可依
    section = evidence_section(body)
    blocks = [b.strip() for b in re.split(r"^### ", section, flags=re.M) if b.strip()]
    if section and not blocks:
        warnings.append("%s: `## 错题证据` 是空的" % path)
    for block in blocks:
        head = block.splitlines()[0].strip()
        for need in EVIDENCE_REQUIRED:
            if need not in block:
                problems.append("%s: 证据块「%s」缺 `%s`" % (path, head, need))
        cause = re.search(r"错因[:：]\s*([^｜|]+)", block)
        if not cause:
            problems.append("%s: 证据块「%s」没有可解析的错因" % (path, head))
        else:
            check_enum("causes", cause.group(1).strip(), enums["causes"],
                       path, problems, warnings)
        norm = re.search(r"规范[:：]\s*([^｜|]+)", block)
        if norm:
            value = norm.group(1).strip()
            if value not in ("", "—", "-"):
                check_enum("norms", value, enums["norms"], path, problems, warnings)


def scan_sensitive(data_root, problems):
    """反向闸门。宁可误报也不漏报。"""
    for dirpath, dirnames, filenames in os.walk(data_root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "inbox")]
        for name in filenames:
            if not name.endswith((".md", ".json", ".csv")):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except Exception:
                continue
            for needle in SENSITIVE:
                if needle in text:
                    problems.append("SENSITIVE: `%s` found in %s"
                                    % (needle, os.path.relpath(full, data_root)))


def main():
    skill_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_root = resolve_data_root(skill_dir)
    if not data_root or not os.path.isdir(data_root):
        out("FATAL: data root not resolvable (exit %d)." % EXIT_NO_DATA)
        out("       Set BIOVAULT_HOME or fix dataRoot in config.json.")
        out("       Refusing to fall back to examples/ -- that is a different dataset.")
        return EXIT_NO_DATA

    enums = load_enums(skill_dir)
    problems, warnings = [], []
    subject = os.path.join(data_root, "data", "subjects", "生物")

    counts = {"points": 0, "exams": 0}
    # 递归扫描：卡按章放在 points/<章>/ 下，只扫一层会读成 0 张还报 OK。
    folder_path = os.path.join(subject, "points")
    if not os.path.isdir(folder_path):
        warnings.append("missing points/ -- 没有知识资产库可校验")
    else:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            dirnames.sort()
            for name in sorted(filenames):
                if not name.endswith(".md"):
                    continue
                full = os.path.join(dirpath, name)
                with open(full, encoding="utf-8") as fh:
                    validate_point(os.path.relpath(full, subject), fh.read(),
                                   enums, problems, warnings)
                counts["points"] += 1
        if counts["points"] == 0:
            warnings.append("points/ 存在但一张卡都没读到，先确认目录结构")

    legacy = os.path.join(subject, "errors")
    if os.path.isdir(legacy):
        stale = [n for n in os.listdir(legacy) if n.endswith(".md")]
        if stale:
            warnings.append("旧 schema：errors/ 还有 %d 个文件；1.13 已改为"
                            "并入 points/<章>/KP-*.md，这些文件不会被校验"
                            % len(stale))

    exams_path = os.path.join(subject, "exams")
    if os.path.isdir(exams_path):
        counts["exams"] = len([n for n in os.listdir(exams_path) if n.endswith(".md")])

    scan_sensitive(data_root, problems)

    out("checked: %d cards, %d exams" % (counts["points"], counts["exams"]))
    for w in warnings:
        out("WARN  %s" % w)
    for p in problems:
        out("FAIL  %s" % p)

    if problems:
        enum_hits = [p for p in problems if "not in enum" in p or "兜底规则" in p]
        if any(p.startswith("SENSITIVE") for p in problems):
            out("RESULT: FAIL -- 脱敏红线被打破，**不要 push**。")
            return EXIT_SENSITIVE
        return EXIT_ENUM if enum_hits else EXIT_SHAPE
    out("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())