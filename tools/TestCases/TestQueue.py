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


CARD_CAUSE = "概念混淆"


def make_record(root, name, **over):
    """Write a minimal but schema-shaped knowledge card (schema 1.13).

    卡住在 points/<章>/, 错题证据挂在 `## 错题证据` 下——没有独立的 errors/。
    """
    chapter = over.pop("chapter", "神经调节")
    fields = {
        "id": os.path.splitext(name)[0],
        "title": "合成知识点 %s" % os.path.splitext(name)[0],
        "kind": "概念",
        "chapter": chapter,
        "point": "神经冲动的产生和传导",
        "value": "高",
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
        "# %s" % fields["title"],
        "",
        "## 一句话",
        "合成知识点。",
        "",
        "## 错题证据",
        "",
        "### 一.1 · 2026-10-13 月考",
        "- 错因：%s ｜ 规范：要点答全 ｜ 重要度：%s" % (CARD_CAUSE, fields["value"]),
        "- 我的错解：x",
        "- 教训：y",
        "",
    ])
    folder = os.path.join(root, "data", "subjects", "生物", "points", chapter)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    return path


def fresh_vault():
    root = tempfile.mkdtemp(prefix="biovault-test-")
    for sub in ("points", "exams"):
        os.makedirs(os.path.join(root, "data", "subjects", "生物", sub))
    return root


@contextlib.contextmanager
def vault(records=None, bom=False):
    root = fresh_vault()
    old = os.environ.get("BIOVAULT_HOME")
    os.environ["BIOVAULT_HOME"] = root
    try:
        for name, over in (records or {}).items():
            path = make_record(root, name, **over)
            if bom:
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
        check("空队列文本说清「没读到卡」而不是谎称没事做",
              "没读到" in text or "一张卡" in text, text[:80])


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


def test_cards_in_chapter_subdirs():
    """REGRESSION: 卡在 points/<章>/ 子目录里，不能被扫漏。

    真实数据仓就是 points/神经调节/KP-*.md。曾经的 bug：只扫一层，
    19 张卡读成 0 张，队列安静地空着，还宣称「队列确实是空的」。
    """
    with vault({
        "KP-A.md": {"chapter": "神经调节", "verified": "false"},
        "KP-B.md": {"chapter": "体液调节", "verified": "false"},
    }):
        _, data = run_json([])
        check("章子目录里的卡全部被扫到", data["counts"]["pending"] == 2,
              str(data["counts"]))
        check("卡标题回落到 front-matter 的 title",
              all(item["point_title"].startswith("合成知识点") for item in data["pending"]),
              str([i["point_title"] for i in data["pending"]]))


def test_cause_from_evidence():
    """错因现在写在 `## 错题证据` 里；会但粗心 必须能被识别出来。

    这条是 Mark.py 守卫的前置条件：读不出错因，守卫就形同虚设。
    """
    with vault({"KP-C.md": {"verified": "true"}}) as root:
        path = os.path.join(root, "data", "subjects", "生物", "points",
                            "神经调节", "KP-C.md")
        with io.open(path, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("错因：概念混淆", "错因：会但粗心")
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        _, data = run_json([])
        check("证据块里的错因被读出（会但粗心）",
              data["review"] and data["review"][0]["cause"] == "会但粗心",
              str([r["cause"] for r in data["review"]]))


def main():
    for fn in (test_verified_gate, test_verified_included, test_graduated_leaves_queue,
               test_future_not_due, test_score_formula, test_value_ordering,
               test_bom_tolerated, test_bad_date_flagged_not_crashed,
               test_empty_queue_is_success, test_no_data_root,
               test_cards_in_chapter_subdirs, test_cause_from_evidence):
        fn()
    print("")
    if FAILURES:
        print("RESULT: %d FAILED -> %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
