#!/usr/bin/env python3
"""Print the review queue for the biology error vault.

Read-only by design. The queue is **time-dependent**: the moment it is
written to disk it starts rotting, and a stale data/indexes/queue.md that
looks authoritative is worse than no file at all. Rebuilding it live costs
one directory scan.

Two queues come out of the same scan because they answer different questions:

  review queue (default)    verified records whose next_review is due
                            -> what to study today
  pending queue (--pending) records with verified: false
                            -> what to verify first

The pending queue is not a nicety. The first real exam produced 18 records
that were *all* verified:false, so the default queue was legitimately empty.
A tool that prints "nothing to do" there is lying by omission -- the work
that day was verification, not review.

Exit codes (shared contract, see AGENTS.md):
  0  ran fine -- an empty queue is a state, not an error
  2  bad arguments
  6  data root not resolvable (never fall back to examples/)
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

# 优先级权重：分数 = 逾期天数 × 权重。全逾期时由 value 拉开差距，
# 部分逾期时由天数拉开差距。不做 SM-2 —— AGENTS.md 明说「高中生版本够用」。
VALUE_WEIGHT = {"高": 3, "中": 2, "低": 1}
DEFAULT_WEIGHT = 1

# 状态机里「已掌握」＝退队列（AGENTS.md § 状态机）
GRADUATED = "已掌握"

GROUP_FIELDS = ("cause", "chapter", "point")


def out(msg=""):
    """stdout = what the user and the AI read. Console is GBK, so force utf-8."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(msg)


def warn(msg):
    """Diagnostics go to stderr so they never pollute the parsed output."""
    sys.stderr.write(msg + "\n")


def verbose(msg):
    if os.environ.get("BIOVAULT_VERBOSE") == "1":
        warn("[verbose] " + msg)


def resolve_data_root(skill_dir):
    """env BIOVAULT_HOME > config.json dataRoot > None.

    Returning None is deliberate: 「找不到数据仓」和「你还没录过题」是两回事，
    静默回落到 examples/ 会让你以为录了其实没有。
    """
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
    """Minimal YAML-subset parser -- no PyYAML, same as the other tools.

    Strips a leading UTF-8 BOM first. Without this a BOM'd file parses as
    "no front matter" and every field silently reads empty -- the record
    then looks like it has no dates rather than like it is broken.
    PowerShell 5.1 `Set-Content -Encoding utf8` writes exactly such a BOM.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block, body = text[3:end], text[end + 4:]
    meta = {}
    for line in block.splitlines():
        if not line.strip() or line[0] in " \t#>":
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            meta[m.group(1)] = val
    return meta, body


def first_heading(body):
    for line in body.splitlines():
        m = re.match(r"^#\s+(.*)$", line.strip())
        if m:
            return m.group(1).strip()
    return ""


def parse_date(value):
    """None on anything unparseable; callers report rather than crash."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        return None


EVIDENCE_CAUSE = re.compile(r"^\s*-\s*错因[:：]\s*([^｜|]+)", re.M)


def evidence_section(body):
    """Return the `## 错题证据` body, or "" when the card has none."""
    match = re.search(r"^## 错题证据\s*$(.*?)(?=^## |\Z)", body, re.S | re.M)
    return match.group(1) if match else ""


def evidence_count(body):
    return len(re.findall(r"^### ", evidence_section(body), re.M))


def detect_cause(body, meta):
    """错因现在写在证据块里，不在 front-matter。

    多块证据时取最严格的那个：只要有一条是「会但粗心」，整张卡就按
    「会但粗心」守卫，别让一条宽松的记录把它冲掉。
    """
    if meta.get("cause"):
        return meta["cause"]
    causes = [c.strip() for c in EVIDENCE_CAUSE.findall(evidence_section(body))]
    if "会但粗心" in causes:
        return "会但粗心"
    return causes[0] if causes else ""


def load_cards(points_dir):
    """Read every knowledge card under points/ (recursive).

    Schema 1.13：一张卡 = 知识点 + 挂在 `## 错题证据` 下的错题证据。
    卡本身就是复习单元，不再有独立的 errors/ —— 错题不单独成文件。
    满分但考试时犹豫的题也照样挂在这里，所以「有证据」≠「做错过」。
    """
    records = []
    if not os.path.isdir(points_dir):
        return records
    for dirpath, dirnames, filenames in os.walk(points_dir):
        dirnames.sort()
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, points_dir)
            try:
                with open(full, encoding="utf-8") as fh:
                    meta, body = parse_front_matter(fh.read())
            except Exception as exc:
                warn("unreadable card %s: %s" % (rel, exc))
                continue
            meta["_file"] = rel
            meta["_title"] = meta.get("title") or first_heading(body)
            meta["_due"] = parse_date(meta.get("next_review"))
            meta["_cause"] = detect_cause(body, meta)
            meta["_evidence"] = evidence_count(body)
            if meta["_due"] is None:
                warn("BAD DATE %s: next_review=`%s`" % (rel, meta.get("next_review", "")))
            records.append(meta)
    return records


def overdue_days(record, today):
    if record["_due"] is None:
        return 0
    return (today - record["_due"]).days


def score(record, today):
    weight = VALUE_WEIGHT.get(record.get("value", ""), DEFAULT_WEIGHT)
    return max(0, overdue_days(record, today)) * weight


def split_queues(records, today):
    """One pass, four buckets. Test order matters: 未复核 first, then 已掌握,
    then the date comparison."""
    review, upcoming, pending, bad = [], [], [], []
    for rec in records:
        if rec.get("verified") == "false":
            pending.append(rec)
            continue
        if rec.get("status") == GRADUATED:
            continue                      # 已掌握 = 退队列
        if rec["_due"] is None:
            bad.append(rec)
        elif rec["_due"] <= today:
            review.append(rec)
        else:
            upcoming.append(rec)
    return review, upcoming, pending, bad


def sort_key(record, today):
    # 分数降序 → 逾期久者先 → 文件名升序，保证同分时输出稳定、可 diff
    return (-score(record, today), record["_due"] or datetime.date.min, record["_file"])


def render_record(rec, today, rank, point_titles, mode="review"):
    lines = []
    head = "%2d. %s  [%s]" % (rank, rec.get("id", rec["_file"]), rec.get("value", "?"))
    if mode == "review":
        over = overdue_days(rec, today)
        head += "  %s  分 %d" % ("逾期 %d 天" % over if over > 0 else "今日到期",
                                 score(rec, today))
    lines.append(head)

    where = " · ".join(x for x in (rec.get("chapter", ""), rec.get("point", ""),
                                   rec.get("qtype", "")) if x)
    if where:
        lines.append("    " + where)
    if rec.get("_title"):
        lines.append("    题面 " + rec["_title"])

    if rec.get("_evidence"):
        bits = ["错因 " + (rec.get("_cause") or "?"),
                "证据 %d 条" % rec["_evidence"]]
    else:
        bits = ["纯知识卡（无错题证据）"]
    if rec.get("norm"):
        bits.append("norm " + rec["norm"])
    if rec.get("review_count", "") not in ("", None):
        bits.append("已复习 %s 次" % rec["review_count"])
    lines.append("    " + " | ".join(bits))

    ref = rec.get("point_ref")
    if ref and ref != rec.get("id"):
        title = point_titles.get(ref)
        lines.append("    知识点 %s%s" % (ref, "「%s」" % title if title else ""))

    # AGENTS.md：会但粗心 不允许一次过 已掌握，强制至少两次间隔。
    # 这里只提示；真正的拦截在 Mark.py 写入时做 —— 提示拦不住人，校验才会。
    if mode == "review" and rec.get("_cause") == "会但粗心":
        lines.append("    ⚠️ 会但粗心：强制至少两次间隔才能过 已掌握")

    lines.append("    → data/subjects/生物/points/%s" % rec["_file"])
    return "\n".join(lines)


def item_sort(rec, today, mode):
    """Pending is ordered by 值不值先复核 (value only), not by lateness --
    an unverified record has no meaningful overdue position yet."""
    if mode == "pending":
        return (-VALUE_WEIGHT.get(rec.get("value", ""), DEFAULT_WEIGHT), rec["_file"])
    return sort_key(rec, today)


def render_grouped(items, today, group_by, point_titles, mode="review"):
    """聚簇输出：同一错因/章/节的记录排在一起，减少来回跳章。"""
    buckets = {}
    for rec in items:
        buckets.setdefault(rec.get(group_by) or "（未填）", []).append(rec)
    order = sorted(buckets, key=lambda k: (-len(buckets[k]), k))
    blocks, rank = [], 0
    for key in order:
        blocks.append("── %s（%d 条）" % (key, len(buckets[key])))
        for rec in sorted(buckets[key], key=lambda r: item_sort(r, today, mode)):
            rank += 1
            blocks.append(render_record(rec, today, rank, point_titles, mode))
            blocks.append("")
    return "\n".join(blocks)


def cause_histogram(records):
    hist = {}
    for rec in records:
        key = rec.get("cause") or "?"
        hist[key] = hist.get(key, 0) + 1
    return sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))


def render_pending(pending, today, point_titles, group_by=None):
    lines = ["待复核清单 · %s  （%d 条）" % (today.isoformat(), len(pending)), ""]
    if group_by:
        lines.append(render_grouped(pending, today, group_by, point_titles, mode="pending"))
    else:
        items = sorted(pending, key=lambda r: item_sort(r, today, "pending"))
        for i, rec in enumerate(items, 1):
            lines.append(render_record(rec, today, i, point_titles, mode="pending"))
            lines.append("")
    lines.append("复核正文与 cause 后把 verified 改成 true，才会进入复习队列。")
    lines.append("批量刷 verified 会让闸门整体失效——SKILL.md 已写死，不要为了好看刷它。")
    return "\n".join(lines)


def render_text(review, upcoming, pending, bad, today, args, point_titles, total=0):
    if args.pending:
        return render_pending(pending, today, point_titles, args.group)

    lines = ["复习队列 · %s" % today.isoformat(), ""]

    if not review:
        lines.append("到期 0 条。")
        lines.append("")
        if not total:
            # 没读到卡 ≠ 没有要复习的。这两种空必须分开说，否则就是撒谎。
            lines.append("⚠️ 队列为空的原因是一张卡都没读到：检查 BIOVAULT_HOME，")
            lines.append("   以及 points/<章>/KP-*.md 是否存在。")
        elif pending:
            # 最重要的一条分支：空队列不等于没事做
            lines.append("⚠️ 队列为空：%d 条记录全部 verified: false，被硬闸门挡在队列外。"
                         % len(pending))
            lines.append("   今天该做的不是复习，是复核。跑：")
            lines.append("       python tools/Review/Queue.py --pending")
        elif bad:
            lines.append("⚠️ 队列为空：有 %d 条记录日期损坏，无法排期。" % len(bad))
        elif upcoming:
            lines.append("今天没有到期记录，且没有待复核记录。加 --all 看未到期。")
        else:
            lines.append("今天没有到期记录，且没有待复核记录——队列确实是空的。")
        lines.append("")

    if review:
        if args.group:
            lines.append(render_grouped(review, today, args.group, point_titles))
        else:
            blocks = [render_record(r, today, i, point_titles)
                      for i, r in enumerate(sorted(review, key=lambda x: sort_key(x, today)), 1)]
            lines.append("\n\n".join(blocks))
        lines.append("")

    if bad:
        lines.append("── ⚠️ 日期损坏，无法排期（%d 条）" % len(bad))
        for rec in sorted(bad, key=lambda r: r["_file"]):
            lines.append("   %s  next_review=`%s`"
                         % (rec.get("id", rec["_file"]), rec.get("next_review", "")))
        lines.append("")

    if args.all and upcoming:
        lines.append("── 即将到期（%d 条）" % len(upcoming))
        for rec in sorted(upcoming, key=lambda r: (r["_due"], r["_file"])):
            lines.append("   %s  [%s]  下次 %s"
                         % (rec.get("id", rec["_file"]), rec.get("value", "?"),
                            rec["_due"].isoformat()))
        lines.append("")

    bits = ["到期 %d 条" % len(review)]
    if upcoming:
        bits.append("未到期 %d 条" % len(upcoming))
    if pending:
        bits.append("待复核 %d 条" % len(pending))
    if bad:
        bits.append("日期损坏 %d 条" % len(bad))
    lines.append(" · ".join(bits))

    if review:
        hist = cause_histogram(review)
        lines.append("")
        lines.append("到期错因分布：" + " / ".join("%s %d" % kv for kv in hist))
        threshold = max(2, len(review) // 3)
        worst = [kv[0] for kv in hist if kv[1] >= threshold]
        if worst:
            # AGENTS.md 健康指标：单一错因 >50% 说明学习方式要调，不是难度问题
            lines.append("⚠️ 集中错因：%s —— 更像学习方式问题，不是难度问题。" % "、".join(worst))
    return "\n".join(lines)


def render_json(review, upcoming, pending, bad, today, point_titles):
    def pack(rec):
        ref = rec.get("point_ref")
        return {
            "id": rec.get("id", ""),
            "file": rec["_file"],
            "title": rec.get("_title", ""),
            "value": rec.get("value", ""),
            "cause": rec.get("_cause") or rec.get("cause", ""),
            "norm": rec.get("norm", ""),
            "status": rec.get("status", ""),
            "chapter": rec.get("chapter", ""),
            "point": rec.get("point", ""),
            "qtype": rec.get("qtype", ""),
            "next_review": rec["_due"].isoformat() if rec["_due"] else None,
            "overdue_days": overdue_days(rec, today),
            "score": score(rec, today),
            "review_count": rec.get("review_count", ""),
            "point_ref": ref or "",
            "point_title": (point_titles.get(ref, "") if ref else "") or rec.get("_title", ""),
            "evidence_count": rec.get("_evidence", 0),
        }
    return json.dumps({
        "today": today.isoformat(),
        "counts": {"review": len(review), "upcoming": len(upcoming),
                   "pending": len(pending), "bad_dates": len(bad)},
        "review": [pack(r) for r in sorted(review, key=lambda x: sort_key(x, today))],
        "upcoming": [pack(r) for r in sorted(upcoming, key=lambda x: (x["_due"], x["_file"]))],
        "pending": [pack(r) for r in sorted(pending, key=lambda r: (
            -VALUE_WEIGHT.get(r.get("value", ""), DEFAULT_WEIGHT), r["_file"]))],
    }, ensure_ascii=False, indent=2)


def build_parser():
    p = argparse.ArgumentParser(
        prog="Queue.py",
        description="打印错题仓的复习队列（只读，不写任何文件）。")
    p.add_argument("--pending", action="store_true",
                   help="改看待复核队列：verified 为 false 的记录")
    p.add_argument("--all", action="store_true",
                   help="同时列出尚未到期的记录")
    p.add_argument("--group", choices=GROUP_FIELDS, default=None,
                   help="聚簇输出，而非按优先级排序")
    p.add_argument("--limit", type=int, default=0,
                   help="最多列出多少条，0 表示不限")
    p.add_argument("--today", default=None,
                   help="覆盖今天的日期，格式 YYYY-MM-DD；测试与复现用")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--verbose", action="store_true", help="把诊断打到 stderr")
    return p


def sanity_check(records):
    """next_review 早于考试日期几乎一定是录入笔误，报出来但不拦。"""
    for rec in records:
        exam = parse_date(rec.get("first_wrong") or rec.get("date"))
        if exam and rec["_due"] and rec["_due"] < exam:
            warn("SUSPECT %s: next_review (%s) is before the exam date (%s)"
                 % (rec["_file"], rec["_due"], exam))


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.verbose:
        os.environ["BIOVAULT_VERBOSE"] = "1"

    skill_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_root = resolve_data_root(skill_dir)
    if not data_root or not os.path.isdir(data_root):
        out("FATAL: data root not resolvable (exit %d)." % EXIT_NO_DATA)
        out("       Set BIOVAULT_HOME or fix dataRoot in config.json.")
        out("       Refusing to fall back to examples/ -- that is a different dataset.")
        return EXIT_NO_DATA

    today = datetime.date.today()
    if args.today:
        today = parse_date(args.today)
        if today is None:
            warn("--today 格式必须是 YYYY-MM-DD，收到 `%s`" % args.today)
            return EXIT_ARGS

    subject = os.path.join(data_root, "data", "subjects", "生物")
    verbose("subject dir: %s" % subject)
    points_dir = os.path.join(subject, "points")
    records = load_cards(points_dir)
    if not records and os.path.isdir(os.path.join(subject, "errors")):
        warn("points/ 里一张卡都没有，但旧 errors/ 还在：本工具只认 1.13 的"
             "知识资产库，先把错题证据并进 points/<章>/KP-*.md")
    point_titles = {rec.get("id") or rec["_file"]: rec.get("_title", "")
                    for rec in records}
    sanity_check(records)

    review, upcoming, pending, bad = split_queues(records, today)
    if args.limit and args.limit > 0:
        review = sorted(review, key=lambda x: sort_key(x, today))[:args.limit]

    if args.json:
        out(render_json(review, upcoming, pending, bad, today, point_titles))
    else:
        out(render_text(review, upcoming, pending, bad, today, args, point_titles,
                        len(records)))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
