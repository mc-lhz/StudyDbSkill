#!/usr/bin/env python3
"""Contract tests for Review/Queue.py. Stdlib only, offline, no credentials.

Every red line gets a reverse case (AGENTS.md): a check that cannot go red
is decoration. The one that matters most is the `verified` gate -- if it
silently lets unverified records into the queue, the vault teaches wrong
content, which is worse than teaching nothing.

Synthetic records are written to a temp tree, never into the repo. The
reverse cases flip one field at a time and assert the queue notices.

Exit code 0 = all pass, 1 = at least one red.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(os.path.dirname(HERE), "Review", "Queue.py")

spec = importlib.util.spec_from_file_location("queue_under_test", QUEUE_PATH)
Queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Queue)

TODAY = "2026-10-19"
FAILURES = []


def make_record(root, name, **over):
    """Write a minimal but schema-shaped error record."""
    fields = {
        "id": os.path.splitext(name)[0],
        "subject": "生物",
        "exam": "BIO-20261013-01",
        "date": "2026-10-13",
        "chapter": "神经调节",
        "point": "神经冲动的产生和传导",
        "qtype": "选择题",
        "cause": "概念混淆",
        "value": "高",
        "difficulty": "中",
        "status": "新错",
        "first_wrong": "2026-10-13",
        "last_review": "2026-10-13",
        "review_count": "0",
        "next_review": "2026-10-14",
        "verified": "true",
    }
    fields.update(over)
    body = "\n".join([
        "---",
        "\n".join("%s: %s" % (k, v) for k, v in fields.items()),
        "---",
        "",
        "# 合成错题 %s" % fields["id"],
        "",
        "## 我的错解", "x", "## 正解思路", "y",
        "## 一句话教训", "z", "## 这题的价值", "%s。" % fields["value"],
    ])
    with io.open(os.path.join(root, "data", "subjects", "生物", "errors", name),
                 "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)


def fresh_vault():
    root = tempfile.mkdtemp(prefix="biovault-test-")
    for sub in ("errors", "points", "exams"):
        os.makedirs(os.path.join(root, "data", "subjects", "生物", sub))
    return root


@contextlib.contextmanager
def vault(records=None, bom=False):
    root = fresh_vault()
    old = os.environ.get("BIOVAULT_HOME")
    os.environ["BIOVAULT_HOME"] = root
    try:
        for name, over in (records or {}).items():
            make_record(root, name, **over)
            if bom:
                path = os.path.join(root, "data", "subjects", "生物", "errors", name)
                with io.open(path, encoding="utf-8") as fh:
                    text = fh.read()
                with io.open(path, "w", encoding="utf-8-sig", newline="\n") as fh:
                    fh.write(text)
        yield root
    finally:
        if old is None:
            os.environ.pop("BIOVAULT_HOME", None)
        else:
            os.environ["BIOVAULT_HOME"] = old
        shutil.rmtree(root, ignore_errors=True)


def run(argv):
    """Return (exit_code, stdout_text). stderr is swallowed into a buffer."""
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        code = Queue.main(argv)
    return code, buf.getvalue()


def run_json(argv):
    code, text = run(argv + ["--json", "--today", TODAY])
    return code, json.loads(text)


def check(label, cond, detail=""):
    if cond:
        print("PASS  %s" % label)
    else:
        print("FAIL  %s  %s" % (label, detail))
        FAILURES.append(label)


def test_verified_gate():
    """REVERSE CASE: an unverified record must NOT reach the review queue."""
    with vault({"BIO-20261013-001.md": {"verified": "false"}}):
        _, data = run_json([])
        check("反向用例 verified:false 不进复习队列",
              data["counts"]["review"] == 0 and data["counts"]["pending"] == 1,
              "counts=%s" % data["counts"])
        check("反向用例 verified:false 出现在待复核队列",
              [r["id"] for r in data["pending"]] == ["BIO-20261013-001"])


def test_verified_included():
    with vault({"BIO-20261013-002.md": {"verified": "true"}}):
        _, data = run_json([])
        check("verified:true 且已到期 → 进复习队列",
              [r["id"] for r in data["review"]] == ["BIO-20261013-002"])


def test_graduated_leaves_queue():
    """REVERSE CASE: 已掌握 is defined as 退队列."""
    with vault({"BIO-20261013-003.md": {"verified": "true", "status": "已掌握"}}):
        _, data = run_json([])
        check("反向用例 已掌握 退队列",
              data["counts"]["review"] == 0 and data["counts"]["pending"] == 0,
              "counts=%s" % data["counts"])


def test_future_not_due():
    with vault({"BIO-20261013-004.md": {"verified": "true", "next_review": "2026-11-01"}}):
        _, data = run_json([])
        check("未到期不进复习队列",
              data["counts"]["review"] == 0 and data["counts"]["upcoming"] == 1)
        _, data_all = run_json(["--all"])
        check("--all 时出现在 upcoming",
              [r["id"] for r in data_all["upcoming"]] == ["BIO-20261013-004"])


def test_score_formula():
    """score = overdue_days x value_weight; 高=3."""
    with vault({"BIO-20261013-005.md": {"verified": "true", "value": "高",
                                        "next_review": "2026-10-14"}}):
        _, data = run_json([])
        rec = data["review"][0]
        check("score = 逾期天数 x 权重（5 天 x 高=3 → 15）",
              rec["score"] == 15, "score=%s overdue=%s" % (rec["score"], rec["overdue_days"]))


def test_value_ordering():
    """高 must outrank 低 at equal lateness."""
    with vault({
        "BIO-20261013-006.md": {"verified": "true", "value": "低",
                                "next_review": "2026-10-14"},
        "BIO-20261013-007.md": {"verified": "true", "value": "高",
                                "next_review": "2026-10-14"},
    }):
        _, data = run_json([])
        check("同逾期时 高 排在 低 前面",
              [r["value"] for r in data["review"]] == ["高", "低"])


def test_bom_tolerated():
    """REGRESSION: PowerShell Set-Content writes a BOM; without tolerance
    every field reads empty and the record looks merely dateless."""
    with vault({"BIO-20261013-008.md": {"verified": "true"}}, bom=True):
        _, data = run_json([])
        check("带 BOM 的记录仍能解析出字段",
              [r["id"] for r in data["review"]] == ["BIO-20261013-008"],
              "counts=%s" % data["counts"])


def test_bad_date_flagged_not_crashed():
    """A broken date must be reported, never silently dropped."""
    with vault({"BIO-20261013-009.md": {"verified": "true", "next_review": "not-a-date"}}):
        code, data = run_json([])
        check("坏日期：不崩、退出码 0", code == 0, "code=%s" % code)
        check("坏日期：计入 bad_dates 而非消失",
              data["counts"]["bad_dates"] == 1, "counts=%s" % data["counts"])
        code_txt, text = run(["--today", TODAY])
        check("坏日期：文本视图明确列出该条", "BIO-20261013-009" in text)


def test_empty_queue_is_success():
    with vault({}):
        code, text = run(["--today", TODAY])
        check("空队列退出码为 0（空是状态不是错误）", code == 0, "code=%s" % code)
        check("空队列文本不谎称「没事做」", "复核" in text or "确实是空的" in text)


def test_no_data_root():
    """REVERSE CASE: unresolvable root must be exit 6, never a fallback."""
    old = os.environ.pop("BIOVAULT_HOME", None)
    saved = Queue.resolve_data_root
    Queue.resolve_data_root = lambda _: None
    try:
        code, _ = run(["--today", TODAY])
    finally:
        Queue.resolve_data_root = saved
        if old is not None:
            os.environ["BIOVAULT_HOME"] = old
    check("反向用例 数据根不可解析 → 退出码 6", code == 6, "code=%s" % code)


def main():
    for fn in (test_verified_gate, test_verified_included, test_graduated_leaves_queue,
               test_future_not_due, test_score_formula, test_value_ordering,
               test_bom_tolerated, test_bad_date_flagged_not_crashed,
               test_empty_queue_is_success, test_no_data_root):
        fn()
    print("")
    if FAILURES:
        print("RESULT: %d FAILED -> %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
