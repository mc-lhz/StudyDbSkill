#!/usr/bin/env python3
"""Contract tests for Review/Mark.py. Stdlib only, offline.

The reverse cases matter most here because Mark.py is a WRITE tool:
  * without --yes the file must be byte-identical afterwards
  * an unverified record must be refused
  * the 会但粗心 guard must hold even if someone shortens the ladder

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
MARK_PATH = os.path.join(os.path.dirname(HERE), "Review", "Mark.py")

spec = importlib.util.spec_from_file_location("mark_under_test", MARK_PATH)
Mark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Mark)

TODAY = "2026-10-19"
FAILURES = []
CRLF = "\r\n"


def body_for(record_id, value="高"):
    return CRLF.join([
        "---",
        "id: %s" % record_id,
        "subject: 生物",
        "exam: BIO-20261013-01",
        "date: 2026-10-13",
        "chapter: 神经调节",
        "point: 神经冲动的产生和传导",
        "qtype: 选择题",
        "cause: concept" if False else "cause: 概念混淆",
        "value: %s" % value,
        "difficulty: 中",
        "status: {status}",
        "first_wrong: 2026-10-13",
        "last_review: 2026-10-13",
        "review_count: {count}",
        "next_review: {due}",
        "verified: {verified}",
        "---",
        "",
        "# Q1 合成错题",
        "",
        "## 我的错解", "第一行正文。", "第二行正文 —— 必须原样保留。",
        "## 正解思路", "x",
        "## 一句话教训", "y",
        "## 这题的价值", "%s。" % value,
        "",
    ])


def write_record(root, record_id, status="新错", count=0, due="2026-10-14",
                 verified="true", cause="概念混淆", value="高"):
    path = os.path.join(root, "data", "subjects", "生物", "errors",
                        "%s.md" % record_id)
    text = (body_for(record_id, value)
            .replace("{status}", status).replace("{count}", str(count))
            .replace("{due}", due).replace("{verified}", verified)
            .replace("cause: 概念混淆", "cause: %s" % cause))
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def read(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


@contextlib.contextmanager
def vault(records):
    root = tempfile.mkdtemp(prefix="biovault-mark-")
    for sub in ("errors", "points", "exams"):
        os.makedirs(os.path.join(root, "data", "subjects", "生物", sub))
    old = os.environ.get("BIOVAULT_HOME")
    os.environ["BIOVAULT_HOME"] = root
    try:
        paths = {rid: write_record(root, rid, **over) for rid, over in records.items()}
        yield paths
    finally:
        if old is None:
            os.environ.pop("BIOVAULT_HOME", None)
        else:
            os.environ["BIOVAULT_HOME"] = old
        shutil.rmtree(root, ignore_errors=True)


def run(argv):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        code = Mark.main(argv)
    return code, buf.getvalue()


def fields(path):
    text = read(path)
    meta, _ = Mark.parse_front_matter(text)
    return meta


def check(label, cond, detail=""):
    if cond:
        print("PASS  %s" % label)
    else:
        print("FAIL  %s  %s" % (label, detail))
        FAILURES.append(label)


def test_no_yes_does_not_write():
    """REVERSE CASE: --yes missing must preview AND leave the file untouched."""
    with vault({"BIO-20261013-001": {}}) as paths:
        before = read(paths["BIO-20261013-001"])
        code, text = run(["BIO-20261013-001", "--result", "right", "--date", TODAY])
        after = read(paths["BIO-20261013-001"])
        check("反向用例 缺 --yes → 退出码 5", code == 5, "code=%s" % code)
        check("反向用例 缺 --yes → 文件逐字节不变", before == after)
        check("缺 --yes 时给出预览", "预览" in text)


def test_first_right():
    with vault({"BIO-20261013-002": {}}) as paths:
        code, _ = run(["BIO-20261013-002", "--result", "right",
                       "--date", TODAY, "--yes"])
        got = fields(paths["BIO-20261013-002"])
        check("第一次做对 → 已订正", got["status"] == "已订正", got["status"])
        check("第一次做对 → count 1", got["review_count"] == "1")
        check("第一次做对 → 1 天后", got["next_review"] == "2026-10-20", got["next_review"])
        check("last_review 记为复习日", got["last_review"] == TODAY)
        check("退出码 0", code == 0)


def test_second_right_interval_and_status():
    with vault({"BIO-20261013-003": {"status": "已订正", "count": 1}}) as paths:
        run(["BIO-20261013-003", "--result", "right", "--date", TODAY, "--yes"])
        got = fields(paths["BIO-20261013-003"])
        check("第二次做对 → 已复现", got["status"] == "已复现", got["status"])
        check("第二次做对 → 3 天后", got["next_review"] == "2026-10-22", got["next_review"])


def test_third_right_graduates():
    with vault({"BIO-20261013-004": {"status": "已复现", "count": 2}}) as paths:
        run(["BIO-20261013-004", "--result", "right", "--date", TODAY, "--yes"])
        got = fields(paths["BIO-20261013-004"])
        check("第三次做对 → 已掌握（退队列）", got["status"] == "已掌握", got["status"])
        check("第三次做对 → 7 天后", got["next_review"] == "2026-10-26", got["next_review"])


def test_wrong_resets_to_new():
    with vault({"BIO-20261013-005": {"status": "已复现", "count": 2}}) as paths:
        run(["BIO-20261013-005", "--result", "wrong", "--date", TODAY, "--yes"])
        got = fields(paths["BIO-20261013-005"])
        check("做错 → 一律降到 新错", got["status"] == "新错", got["status"])
        check("做错 → 计数归零", got["review_count"] == "0", got["review_count"])
        check("做错 → 明天重来", got["next_review"] == "2026-10-20", got["next_review"])


def test_careless_guard_survives_ladder_shortening():
    """REVERSE CASE: the 会但粗心 guard is independent of the ladder.
    Shorten graduation to 1 review and the guard must still refuse it."""
    saved = Mark.GRADUATE_COUNT
    Mark.GRADUATE_COUNT = 1
    try:
        with vault({
            "BIO-20261013-006": {"cause": "会但粗心"},
            "BIO-20261013-007": {"cause": "概念混淆"},
        }) as paths:
            run(["BIO-20261013-006", "BIO-20261013-007",
                 "--result", "right", "--date", TODAY, "--yes"])
            careless = fields(paths["BIO-20261013-006"])
            normal = fields(paths["BIO-20261013-007"])
            check("反向用例 阶梯缩短后 会但粗心 仍不毕业",
                  careless["status"] != "已掌握", careless["status"])
            check("对照：普通错因 正常毕业",
                  normal["status"] == "已掌握", normal["status"])
    finally:
        Mark.GRADUATE_COUNT = saved


def test_unverified_refused():
    """REVERSE CASE: reviewing unverified content must be refused."""
    with vault({"BIO-20261013-008": {"verified": "false"}}) as paths:
        before = read(paths["BIO-20261013-008"])
        code, text = run(["BIO-20261013-008", "--result", "right",
                          "--date", TODAY, "--yes"])
        after = read(paths["BIO-20261013-008"])
        check("反向用例 verified:false 被拒绝，退出码 2", code == 2, "code=%s" % code)
        check("反向用例 verified:false 文件未动", before == after)
        check("拒绝理由可见", "verified" in text)


def test_unknown_id():
    with vault({"BIO-20261013-009": {}}):
        code, text = run(["BIO-20991231-999", "--result", "right",
                          "--date", TODAY, "--yes"])
        check("不存在的 id → 退出码 2", code == 2, "code=%s" % code)
        check("不存在的 id 有明确提示", "找不到" in text)


def test_newline_and_body_preserved():
    """CRLF must survive, and the body must not be reflowed."""
    with vault({"BIO-20261013-010": {}}) as paths:
        path = paths["BIO-20261013-010"]
        before = read(path)
        run(["BIO-20261013-010", "--result", "right", "--date", TODAY, "--yes"])
        after = read(path)
        check("写回后仍是 CRLF", "\r\n" in after and "\n" not in after.replace("\r\n", ""))
        check("正文两行原样保留", "第二行正文 —— 必须原样保留。" in after)
        before_body = before.split("## 我的错解", 1)[1]
        after_body = after.split("## 我的错解", 1)[1]
        check("正文逐字节不变", before_body == after_body)


def test_json_output():
    with vault({"BIO-20261013-011": {}}):
        code, text = run(["BIO-20261013-011", "--result", "right",
                          "--date", TODAY, "--yes", "--json"])
        data = json.loads(text)
        check("--json 输出可解析", data["written"][0]["status"] == "已订正")


def test_batch_mixed():
    """One batch, one bad id: good ones still apply, exit code reports failure."""
    with vault({"BIO-20261013-012": {}, "BIO-20261013-013": {}}) as paths:
        code, _ = run(["BIO-20261013-012", "BIO-20990101-001", "BIO-20261013-013",
                       "--result", "right", "--date", TODAY, "--yes"])
        check("批量：坏 id 不阻断其余记录",
              fields(paths["BIO-20261013-012"])["status"] == "已订正"
              and fields(paths["BIO-20261013-013"])["status"] == "已订正")
        check("批量：有失败则退出码非 0", code != 0, "code=%s" % code)


def main():
    for fn in (test_no_yes_does_not_write, test_first_right,
               test_second_right_interval_and_status, test_third_right_graduates,
               test_wrong_resets_to_new, test_careless_guard_survives_ladder_shortening,
               test_unverified_refused, test_unknown_id,
               test_newline_and_body_preserved, test_json_output, test_batch_mixed):
        fn()
    print("")
    if FAILURES:
        print("RESULT: %d FAILED -> %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
