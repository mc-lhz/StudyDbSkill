#!/usr/bin/env python3
"""Record a review outcome: advance (or reset) a record's schedule.

Queue.py answers "what is due". Mark.py is what makes the queue shrink --
without it `next_review` never moves and the queue is a treadmill.

Transition rules (user-decided 2026-10-19, see MEMORY.md 1.12):

    review right   新错 -> 已订正 -> 已复现 -> 已掌握   间隔 1 / 3 / 7 天
    review wrong   一律降回 新错，计数归零，明天再来

     新错 ──对──> 已订正 ──对──> 已复现 ──对──> 已掌握（退队列）
       ↑        ↑         ↑          │
       └────────┴─────────┴──────────┘  做错：一律降到 新错

Safety rails, in the spirit of AGENTS.md:

  * writing requires --yes; without it this is a preview and exit 5
  * the four fields are patched line-by-line, never re-serialized, so the
    rest of the file (including CRLF endings) survives byte-for-byte
  * every write is read back and re-parsed; "no exception" is not success
  * a verified:false record is refused unless --force -- reviewing content
    that was never checked is how you memorise something wrong

Exit codes (AGENTS.md):
  0  ok
  2  bad arguments / id not found / record not verified
  5  --yes missing (the change was previewed, not applied)
  6  data root not resolvable
"""

import argparse
import datetime
import json
import os
import re
import sys

EXIT_OK = 0
EXIT_ARGS = 2
EXIT_NO_DATA = 6
EXIT_NO_YES = 5

# 用户裁定（2026-10-19）：复习做对 3 次毕业，间隔 1 / 3 / 7 天。
# AGENTS.md 的 1→3→7→15→30 仍成立，只是 15/30 留给毕业后再次复习的场景。
GRADUATE_COUNT = 3
LADDER = [1, 3, 7]

# 做错时状态一律落到这里（用户裁定）
RESET_STATUS = "新错"

# 会但粗心 是「靠多刷能改、但不做专门训练就复发」且最易误判成「我会了」的错因，
# AGENTS.md 要求它至少两次间隔才能毕业。这里做成**独立于阶梯的守卫**：
# 只要 GRADUATE_COUNT 被改小，它仍然拦得住。
MIN_INTERVALS = {"会但粗心": 2}

WRITTEN_FIELDS = ("status", "review_count", "last_review", "next_review")


def out(msg=""):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(msg)


def warn(msg):
    sys.stderr.write(msg + "\n")


def resolve_data_root(skill_dir):
    env = os.environ.get("BIOVAULT_HOME")
    if env:
        return env
    cfg = os.path.join(skill_dir, "config.json")
    if os.path.isfile(cfg):
        try:
            with open(cfg, encoding="utf-8") as fh:
                val = json.load(fh).get("dataRoot", "")
            if val:
                return os.path.expanduser(val)
        except Exception as exc:
            warn("config.json unreadable: %s" % exc)
    return None


def parse_front_matter(text):
    """Same minimal parser as the other tools; BOM-stripping included."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line[0] in " \t#>":
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[m.group(1)] = val
    return meta, text[end + 4:]


def read_text(path):
    """Read raw, remembering the newline style so we can write it back."""
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), newline


def write_text(path, text, newline):
    """newline='' disables translation, so we control the line endings exactly."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", newline))


def patch_front_matter(text, updates):
    """Replace only the named `key: value` lines. Never re-serializes the rest,
    so ordering, comments and the body survive untouched."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        raise ValueError("no front matter")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("front matter not terminated")
    head, tail = text[:end], text[end:]
    lines = head.split("\n")
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if m and m.group(1) in updates:
            key = m.group(1)
            lines[i] = "%s: %s" % (key, updates[key])
            seen.add(key)
    for key, value in updates.items():
        if key not in seen:
            lines.append("%s: %s" % (key, value))
    return "\n".join(lines) + tail


def next_status(count):
    if count >= GRADUATE_COUNT:
        return "已掌握"
    if count == GRADUATE_COUNT - 1:
        return "已复现"
    return "已订正"


def plan(meta, result, today):
    """Return (updates, explanation). Pure -- no file access, so tests can
    drive it directly."""
    cause = meta.get("cause", "")
    try:
        count = int(meta.get("review_count") or 0)
    except ValueError:
        count = 0

    if result == "wrong":
        # 用户裁定：一律降到 新错，计数归零
        return {
            "status": RESET_STATUS,
            "review_count": "0",
            "last_review": today.isoformat(),
            "next_review": (today + datetime.timedelta(days=1)).isoformat(),
        }, "做错 → 降回 %s，计数归零，明天重来" % RESET_STATUS

    new_count = count + 1
    status = next_status(new_count)
    note = ""
    floor = MIN_INTERVALS.get(cause, 0)
    if status == "已掌握" and new_count < floor:
        status = next_status(GRADUATE_COUNT - 1) or "已复现"
        note = "（%s 强制至少 %d 次间隔，暂缓毕业）" % (cause, floor)

    days = LADDER[min(new_count, len(LADDER)) - 1]
    return {
        "status": status,
        "review_count": str(new_count),
        "last_review": today.isoformat(),
        "next_review": (today + datetime.timedelta(days=days)).isoformat(),
    }, "做对第 %d 次 → %s，%d 天后（%s）%s" % (
        new_count, status, days,
        (today + datetime.timedelta(days=days)).isoformat(), note)


EVIDENCE_CAUSE = re.compile(r"^\s*-\s*错因[:：]\s*([^｜|]+)", re.M)


def detect_cause(body, meta):
    """错因写在证据块里，不在 front-matter（schema 1.13）。

    多块证据取最严格的一条：只要有「会但粗心」，整张卡就受守卫约束。
    """
    if meta.get("cause"):
        return meta["cause"]
    match = re.search(r"^## 错题证据\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    causes = [c.strip() for c in EVIDENCE_CAUSE.findall(match.group(1) if match else "")]
    if "会但粗心" in causes:
        return "会但粗心"
    return causes[0] if causes else ""


def index_records(points_dir):
    """id -> (path, meta). id comes from front-matter, falling back to filename.

    Schema 1.13：复习单元是 points/<章>/KP-*.md（知识点卡），
    不再是已经取消的 errors/。递归扫描，子目录是章的归属。
    """
    found = {}
    if not os.path.isdir(points_dir):
        return found
    for dirpath, dirnames, filenames in os.walk(points_dir):
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, points_dir)
            try:
                text, _ = read_text(path)
            except Exception as exc:
                warn("unreadable %s: %s" % (rel, exc))
                continue
            meta, body = parse_front_matter(text)
            meta["cause"] = detect_cause(body, meta)
            key = meta.get("id") or os.path.splitext(name)[0]
            found[key] = (path, meta)
            found.setdefault(os.path.splitext(name)[0], (path, meta))
    return found


def apply_one(path, meta, updates, today):
    """Patch, write, then read back and assert. Raises on any mismatch."""
    text, newline = read_text(path)
    new_text = patch_front_matter(text, updates)
    write_text(path, new_text, newline)

    recheck, _ = read_text(path)
    got, _ = parse_front_matter(recheck)
    for key in WRITTEN_FIELDS:
        if key in updates and got.get(key) != str(updates[key]):
            raise AssertionError("read-back mismatch on %s: wrote `%s`, read `%s`"
                                 % (key, updates[key], got.get(key)))
    return got


def build_parser():
    p = argparse.ArgumentParser(
        prog="Mark.py",
        description="记录一次复习结果，推进或重置该错题的复习计划。")
    p.add_argument("ids", nargs="+", help="一个或多个错题 id")
    p.add_argument("--result", required=True, choices=("right", "wrong"),
                   help="复习结果：right 做对 / wrong 做错")
    p.add_argument("--date", default=None,
                   help="覆盖复习日期 YYYY-MM-DD；测试与补录用")
    p.add_argument("--detail", action="store_true",
                   help="打印每条的旧值与新值")
    p.add_argument("--force", action="store_true",
                   help="允许对 verified: false 的记录记账（默认拒绝）")
    p.add_argument("--yes", action="store_true", help="确认写入")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    skill_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_root = resolve_data_root(skill_dir)
    if not data_root or not os.path.isdir(data_root):
        out("FATAL: data root not resolvable (exit %d)." % EXIT_NO_DATA)
        out("       Set BIOVAULT_HOME or fix dataRoot in config.json.")
        return EXIT_NO_DATA

    today = datetime.date.today()
    if args.date:
        try:
            today = datetime.date.fromisoformat(args.date)
        except ValueError:
            warn("--date 格式必须是 YYYY-MM-DD，收到 `%s`" % args.date)
            return EXIT_ARGS

    points_dir = os.path.join(data_root, "data", "subjects", "生物", "points")
    records = index_records(points_dir)
    if not records:
        out("points/ 下一页卡都没读到：检查 BIOVAULT_HOME 与 points/<章>/KP-*.md")
        return EXIT_NO_DATA

    plans, errors = [], []
    for rid in args.ids:
        entry = records.get(rid)
        if not entry:
            errors.append("%s: 找不到该 id" % rid)
            continue
        path, meta = entry
        if meta.get("verified") == "false" and not args.force:
            # 复习一条从未复核的记录 = 在背未经确认的内容，正是硬闸门要拦的
            errors.append("%s: verified: false，先复核再加复习记录（要强来用 --force）" % rid)
            continue
        updates, why = plan(meta, args.result, today)
        plans.append({"id": rid, "path": path, "meta": meta,
                      "updates": updates, "why": why})

    if errors:
        for e in errors:
            out("FAIL  %s" % e)
    if not plans:
        out("没有可记账的记录（exit %d）。" % EXIT_ARGS)
        return EXIT_ARGS

    if not args.yes:
        out("预览（未写入；加 --yes 才生效）：")
        for item in plans:
            out("  %s  %s → %s | count %s → %s | 下次 %s"
                % (item["id"], item["meta"].get("status", "?"),
                   item["updates"]["status"],
                   item["meta"].get("review_count", "?"),
                   item["updates"]["review_count"],
                   item["updates"]["next_review"]))
        if errors:
            out("（另有 %d 条失败，见上）" % len(errors))
        out("EXIT %d" % EXIT_NO_YES)
        return EXIT_NO_YES

    results = []
    try:
        for item in plans:
            got = apply_one(item["path"], item["meta"], item["updates"], today)
            results.append({
                "id": item["id"],
                "status": got.get("status"),
                "review_count": got.get("review_count"),
                "next_review": got.get("next_review"),
                "why": item["why"],
            })
    except Exception as exc:
        # 回读校验失败：不假装成功（AGENTS.md）
        out("FAIL  写入或回读校验失败：%s" % exc)
        return EXIT_ARGS

    if args.json:
        out(json.dumps({"today": today.isoformat(), "written": results,
                        "failed": errors}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            out("OK  %s → %s  count=%s  下次 %s"
                % (r["id"], r["status"], r["review_count"], r["next_review"]))
            if args.detail:
                out("      %s" % r["why"])
        if errors:
            out("（%d 条未处理，见上）" % len(errors))
    return EXIT_OK if not errors else EXIT_ARGS


if __name__ == "__main__":
    sys.exit(main())
