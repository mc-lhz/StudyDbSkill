"""学校分数系统只读客户端（门面 + CLI）。

能力边界：登录、学生切换、考试列表、考试元数据、原卷/答题卡图片。
不包含写操作，也不访问受限的题目详情接口。

凭据策略：**什么都不落盘**。
- `login` 子命令用账号密码换 token，并把 token 打到标准输出；
- 其余命令用 `--token` 接收，不再登录；
- 账号密码只在 `login` 那一次的命令行里存在，进程结束即消失。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from Access.Auth import AuthMixin, isAuthError
from Access.HttpTransport import Http
from Common.Config import BestGradeError, DEFAULT_LIMIT, UsageError, maskAccount
from ExamCenter.AnswerSheet import AnswerSheetMixin
from ExamCenter.Exams import ExamsMixin, formatExam, formatPaper
from StudentBase.Students import StudentsMixin, formatStudent


class ScoreClient(AuthMixin, StudentsMixin, ExamsMixin, AnswerSheetMixin, Http):
    pass


def _printJson(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _prepare(client, args, needStudent=True):
    """拿到可用凭据：优先复用传入的 token，没有才登录。

    切学生是每次都要做的：复用 token 只省掉登录，不省会话里的学生上下文。
    """
    token = getattr(args, "token", None)
    if token:
        client.useToken(token)
    else:
        client.login(getattr(args, "username", None), getattr(args, "password", None))
    if not needStudent:
        return None
    student = client.selectStudent(args.student)
    client.switchStudent(student)
    return student


def cmdLogin(client, args):
    data = client.login(args.username, args.password)
    if args.json:
        _printJson({
            "token": client.token,
            "loginName": client.loginName,
            "userId": data.get("userId"),
            "studentId": data.get("studentId"),
        })
        return 0
    print(f"登录成功：{maskAccount(client.loginName)}")
    print("")
    print(client.token)
    print("")
    print("以上是 token，后续命令用 --token 传入。它不写盘，只存在于本次输出里。")
    return 0


def cmdStudents(client, args):
    _prepare(client, args, needStudent=False)
    students = client.listStudents()
    if args.json:
        _printJson({"students": students})
        return 0
    print(f"共 {len(students)} 个绑定学生：")
    for index, student in enumerate(students, start=1):
        print(formatStudent(student, index))
    return 0


def cmdExams(client, args):
    _prepare(client, args)
    data = client.listExams(limit=args.limit)
    exams = data.get("list") or []
    if args.json:
        _printJson(data)
        return 0
    print(f"共 {data.get('totalCount', len(exams))} 场考试，显示 {len(exams)} 场：")
    for index, exam in enumerate(exams, start=1):
        print(formatExam(exam, index))
    return 0


def cmdOverview(client, args):
    _prepare(client, args)
    exam = client.resolveExam(args.exam, limit=args.limit)
    overview = client.examOverview(exam["examId"])
    if args.out:
        path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(overview, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    if args.json:
        _printJson(overview)
        return 0
    print(f"{overview.get('name', '')}  examId={overview.get('examId')}")
    print(f"总分 {overview.get('score')}/{overview.get('manfen')}  科目 {len(overview.get('papers') or [])} 门")
    for index, paper in enumerate(overview.get("papers") or [], start=1):
        print(formatPaper(paper, index))
    if args.out:
        print(f"已保存：{os.path.abspath(args.out)}")
    return 0


def cmdImages(client, args):
    _prepare(client, args)
    exam = client.resolveExam(args.exam, limit=args.limit)
    manifest = client.fetchImages(
        exam["examId"],
        subject=args.subject,
        paperId=args.paper,
        pid=args.pid,
        kind=args.kind,
        outDir=args.out,
    )
    if args.json:
        _printJson(manifest)
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


def buildParser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--token", help="已登录的 token（优先使用，不发起登录）")
    common.add_argument("--username", help="登录账号（仅 login 或首次使用时需要）")
    common.add_argument("--password", help="登录密码（仅本次进程使用，不落盘）")
    common.add_argument("--student", help="学生 id、序号或姓名（多学生时必填）")
    common.add_argument("--json", action="store_true", help="输出原始 JSON")

    parser = argparse.ArgumentParser(
        prog="ScoreClient.py",
        description="学校分数系统只读客户端：登录换 token，之后用 token 查询。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", parents=[common],
                       help="用账号密码换取 token（打印到标准输出）")
    p.set_defaults(func=cmdLogin, student=None)

    p = sub.add_parser("students", parents=[common], help="列出绑定学生")
    p.set_defaults(func=cmdStudents)

    p = sub.add_parser("exams", parents=[common], help="列出考试")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="最多返回场次")
    p.set_defaults(func=cmdExams)

    p = sub.add_parser("overview", parents=[common], help="打印/保存考试元数据")
    p.add_argument("--exam", required=True, help="examId 或列表序号")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--out", help="元数据 JSON 保存路径")
    p.set_defaults(func=cmdOverview)

    p = sub.add_parser("images", parents=[common], help="下载原卷与答题卡图片")
    p.add_argument("--exam", required=True, help="examId 或列表序号")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--subject", help="科目名，如 数学")
    p.add_argument("--paper", help="paperId")
    p.add_argument("--pid", help="pid")
    p.add_argument("--kind", choices=("both", "paper", "answer"), default="both")
    p.add_argument("--out", help="输出目录（默认 %%TEMP%%\\BestGrade\\<examId>\\<subject>）")
    p.set_defaults(func=cmdImages)
    return parser


def _report(exc):
    if isinstance(exc, UsageError):
        print(f"参数错误：{exc}", file=sys.stderr)
    else:
        print(f"请求失败：{exc}", file=sys.stderr)
    return exc.exitCode


def _retryable(client, args, exc):
    """token 失效且同时给了账号密码时，允许自动重登一次。"""
    return (
        client.tokenSource == "provided"
        and bool(getattr(args, "username", None))
        and bool(getattr(args, "password", None))
        and isAuthError(exc)
    )


def main(argv=None):
    args = buildParser().parse_args(argv)
    if args.command == "login" and (not args.username or not args.password):
        print("参数错误：login 需要 --username 与 --password", file=sys.stderr)
        return 2
    client = ScoreClient()
    try:
        return args.func(client, args)
    except BestGradeError as exc:
        if _retryable(client, args, exc):
            print("token 已失效，用提供的账号密码重新登录…", file=sys.stderr)
            client.token = None
            args.token = None
            try:
                return args.func(client, args)
            except BestGradeError as again:
                return _report(again)
        return _report(exc)


if __name__ == "__main__":
    sys.exit(main())