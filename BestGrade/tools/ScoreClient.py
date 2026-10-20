"""学校分数系统只读客户端（门面 + CLI）。

能力边界：登录、学生切换、考试列表、考试元数据、原卷/答题卡图片。
不包含写操作，也不访问受限的题目详情接口。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from Access.Auth import AuthMixin
from Access.HttpTransport import Http
from Common.Config import BestGradeError, DEFAULT_LIMIT, UsageError
from ExamCenter.AnswerSheet import AnswerSheetMixin
from ExamCenter.Exams import ExamsMixin, format_exam, format_paper
from StudentBase.Students import StudentsMixin, format_student


class ScoreClient(AuthMixin, StudentsMixin, ExamsMixin, AnswerSheetMixin, Http):
    pass


def _print_json(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _login(client, args, need_student=True):
    client.login(args.username, args.password)
    if not need_student:
        return None
    student = client.select_student(args.student)
    client.switch_student(student)
    return student


def cmd_students(client, args):
    _login(client, args, need_student=False)
    students = client.list_students()
    if args.json:
        _print_json({"students": students})
        return 0
    print(f"共 {len(students)} 个绑定学生：")
    for index, student in enumerate(students, start=1):
        print(format_student(student, index))
    return 0


def cmd_exams(client, args):
    _login(client, args)
    data = client.list_exams(limit=args.limit)
    exams = data.get("list") or []
    if args.json:
        _print_json(data)
        return 0
    print(f"共 {data.get('totalCount', len(exams))} 场考试，显示 {len(exams)} 场：")
    for index, exam in enumerate(exams, start=1):
        print(format_exam(exam, index))
    return 0


def cmd_overview(client, args):
    _login(client, args)
    exam = client.resolve_exam(args.exam, limit=args.limit)
    overview = client.exam_overview(exam["examId"])
    if args.out:
        path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(overview, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    if args.json:
        _print_json(overview)
        return 0
    print(f"{overview.get('name', '')}  examId={overview.get('examId')}")
    print(f"总分 {overview.get('score')}/{overview.get('manfen')}  科目 {len(overview.get('papers') or [])} 门")
    for index, paper in enumerate(overview.get("papers") or [], start=1):
        print(format_paper(paper, index))
    if args.out:
        print(f"已保存：{os.path.abspath(args.out)}")
    return 0


def cmd_images(client, args):
    _login(client, args)
    exam = client.resolve_exam(args.exam, limit=args.limit)
    manifest = client.fetch_images(
        exam["examId"],
        subject=args.subject,
        paper_id=args.paper,
        pid=args.pid,
        kind=args.kind,
        out_dir=args.out,
    )
    if args.json:
        _print_json(manifest)
        return 0
    print(f"考试：{exam.get('name', '')}（{exam['examId']}）")
    print(f"科目：{manifest.get('subject')}  paperId={manifest.get('paperId')}")
    print(f"输出目录：{manifest['outDir']}")
    for section in ("paper", "answer"):
        block = manifest.get(section)
        if not block:
            continue
        label = "原卷" if section == "paper" else "答题卡"
        print(f"{label} JSON：{block['json']}")
        for item in block["files"]:
            print(f"  {item['path']}  {item['bytes']} B  {item['kind']}")
    return 0


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--username", required=True, help="登录账号")
    common.add_argument("--password", required=True, help="登录密码（仅本次进程使用）")
    common.add_argument("--student", help="学生 id、序号或姓名（多学生时必填）")
    common.add_argument("--json", action="store_true", help="输出原始 JSON")

    parser = argparse.ArgumentParser(
        prog="ScoreClient.py",
        description="学校分数系统只读客户端：登录、切换学生、考试、原卷/答题卡。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("students", parents=[common], help="列出绑定学生")
    p.set_defaults(func=cmd_students)

    p = sub.add_parser("exams", parents=[common], help="列出考试")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="最多返回场次")
    p.set_defaults(func=cmd_exams)

    p = sub.add_parser("overview", parents=[common], help="打印/保存考试元数据")
    p.add_argument("--exam", required=True, help="examId 或列表序号")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--out", help="元数据 JSON 保存路径")
    p.set_defaults(func=cmd_overview)

    p = sub.add_parser("images", parents=[common], help="下载原卷与答题卡图片")
    p.add_argument("--exam", required=True, help="examId 或列表序号")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--subject", help="科目名，如 数学")
    p.add_argument("--paper", help="paperId")
    p.add_argument("--pid", help="pid")
    p.add_argument("--kind", choices=("both", "paper", "answer"), default="both")
    p.add_argument("--out", help="输出目录（默认 %%TEMP%%\\BestGrade\\<examId>\\<subject>）")
    p.set_defaults(func=cmd_images)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    client = ScoreClient()
    try:
        return args.func(client, args)
    except UsageError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return exc.exit_code
    except BestGradeError as exc:
        print(f"请求失败：{exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
