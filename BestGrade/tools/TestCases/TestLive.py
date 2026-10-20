"""只读联调测试：需要真实账号，仅调用读接口。

流程：登录 -> 学生列表 -> 切换 -> 考试列表 -> 元数据 -> 原卷/答题卡图片。
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from Access.HttpTransport import sniff_image  # noqa: E402
from ScoreClient import ScoreClient  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))


def png_size(path):
    with open(path, "rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return struct.unpack(">II", head[16:24])


def pick_student(client, selector):
    if selector:
        return client.select_student(selector), None
    errors = []
    for student in client.list_students():
        try:
            client.switch_student(student)
            exams = client.list_exams(limit=5).get("list") or []
        except Exception as exc:  # noqa: BLE001 - 逐个尝试，记录失败原因
            errors.append(str(exc))
            continue
        if exams:
            return student, None
    return None, "; ".join(errors) or "所有学生都没有考试数据"


def main():
    parser = argparse.ArgumentParser(description="只读联调测试")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--student", help="学生 id/序号/姓名")
    parser.add_argument("--exam", help="examId 或序号，默认第 1 场")
    parser.add_argument("--subject", help="科目，默认数学（不存在则用第一科）")
    parser.add_argument("--out", help="图片输出目录")
    args = parser.parse_args()

    client = ScoreClient()
    try:
        info = client.login(args.username, args.password)
        check("login token", bool(info.get("token")))

        students = client.list_students()
        check("students non-empty", bool(students), f"count={len(students)}")

        student, error = pick_student(client, args.student)
        check("switch student", bool(student), error or "")
        if not student:
            return 1

        exams = client.list_exams(limit=10).get("list") or []
        check("exams non-empty", bool(exams), f"count={len(exams)}")
        if not exams:
            return 1

        exam = client.resolve_exam(args.exam or "1", limit=10)
        overview = client.exam_overview(exam["examId"])
        papers = overview.get("papers") or []
        check("overview papers", bool(papers), f"examId={exam['examId']}")
        if not papers:
            return 1

        paper = None
        if args.subject:
            paper, _ = client.resolve_paper(exam["examId"], subject=args.subject)
        else:
            try:
                paper, _ = client.resolve_paper(exam["examId"], subject="数学")
            except Exception:  # noqa: BLE001 - 数学缺考时回落到第一科
                paper = papers[0]
        check("resolve paper", bool(paper and paper.get("paperId")), json.dumps(paper, ensure_ascii=False)[:120])

        destination = args.out or tempfile.mkdtemp(prefix="bestgrade-live-")
        manifest = client.fetch_images(
            exam["examId"],
            paper_id=paper["paperId"],
            kind="both",
            out_dir=destination,
        )
        paper_files = (manifest.get("paper") or {}).get("files") or []
        answer_files = (manifest.get("answer") or {}).get("files") or []
        check("paper images", bool(paper_files), f"count={len(paper_files)}")
        check("answer images", bool(answer_files), f"count={len(answer_files)}")

        for item in paper_files:
            with open(item["path"], "rb") as handle:
                kind = sniff_image(handle.read(8))
            check(f"paper magic {os.path.basename(item['path'])}", kind in ("png", "jpg"), str(kind))

        sizes = []
        for item in answer_files:
            size = png_size(item["path"])
            sizes.append(size)
            check(f"answer PNG {os.path.basename(item['path'])}", bool(size), str(size))
        check("answer dimensions", all(size and size[0] > 0 and size[1] > 0 for size in sizes), str(sizes))

        answer_json = (manifest.get("answer") or {}).get("json")
        with open(answer_json, encoding="utf-8") as handle:
            payload = json.load(handle)
        check("answer questions", bool(payload.get("questions")), f"count={len(payload.get('questions') or [])}")

        print("\n输出目录：", destination)
        print("考试：", exam.get("name"), exam.get("examId"))
        print("科目：", paper.get("subject"), "得分", paper.get("score"), "/", paper.get("manfen"))
        print("图片：原卷 %d 页，答题卡 %d 页" % (len(paper_files), len(answer_files)))
    except Exception as exc:  # noqa: BLE001 - 联调脚本需要打印完整失败
        check("live flow", False, f"{type(exc).__name__}: {exc}")
        return 1

    failed = [item for item in results if not item[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
