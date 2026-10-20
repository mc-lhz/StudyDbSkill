"""考试中心：考试列表、元数据、科目定位。"""
from __future__ import annotations

import datetime

from Common.Config import DEFAULT_LIMIT, UsageError


def format_exam(exam, index=None):
    prefix = f"[{index}] " if index is not None else ""
    stamp = exam.get("time")
    when = ""
    if isinstance(stamp, (int, float)) and stamp > 0:
        when = datetime.datetime.fromtimestamp(stamp / 1000).strftime("%Y-%m-%d")
    score = exam.get("score")
    manfen = exam.get("manfen")
    tail = f"  {score}/{manfen}" if score is not None and manfen is not None else ""
    return f"{prefix}{exam.get('name', '')}  {when}  examId={exam.get('examId', '')}{tail}"


def format_paper(paper, index=None):
    prefix = f"[{index}] " if index is not None else ""
    return (
        f"{prefix}{paper.get('subject', '')}（{paper.get('name', '')}）  "
        f"{paper.get('score', '')}/{paper.get('manfen', '')}  "
        f"paperId={paper.get('paperId', '')} pid={paper.get('pid', '')}"
    )


class ExamsMixin:
    def list_exams(self, limit=DEFAULT_LIMIT, start=0):
        if limit <= 0:
            raise UsageError("--limit 必须大于 0")
        data = self.get_json("/v3/exam/list", params={"start": start, "limit": limit})
        return data if isinstance(data, dict) else {}

    def resolve_exam(self, selector, limit=DEFAULT_LIMIT):
        limit = max(int(limit), DEFAULT_LIMIT)
        exams = self.list_exams(limit=limit).get("list") or []
        if not exams:
            raise UsageError("没有可查询的考试")
        text = str(selector).strip()
        for exam in exams:
            if str(exam.get("examId")) == text:
                return exam
        if text.isdigit():
            index = int(text) - 1
            if 0 <= index < len(exams):
                return exams[index]
        matches = [exam for exam in exams if text and text in str(exam.get("name") or "")]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise UsageError(
                f"考试「{text}」有多条匹配，请改用 examId 或序号：\n"
                + "\n".join(format_exam(e, i + 1) for i, e in enumerate(exams))
            )
        raise UsageError(
            f"找不到考试「{text}」，候选如下：\n"
            + "\n".join(format_exam(e, i + 1) for i, e in enumerate(exams))
        )

    def exam_overview(self, exam_id):
        data = self.get_json(f"/v3/exam/{exam_id}/overview")
        if not isinstance(data, dict):
            raise UsageError(f"考试 {exam_id} 没有元数据")
        return data

    def resolve_paper(self, exam_id, subject=None, paper_id=None, pid=None):
        overview = self.exam_overview(exam_id)
        papers = overview.get("papers") or []
        if not papers:
            raise UsageError(f"考试 {exam_id} 没有科目数据")
        for paper in papers:
            if pid and str(paper.get("pid")) == str(pid):
                return paper, overview
            if paper_id and str(paper.get("paperId")) == str(paper_id):
                return paper, overview
        if subject:
            text = str(subject).strip()
            exact = [
                paper
                for paper in papers
                if text in (str(paper.get("subject") or ""), str(paper.get("name") or ""))
            ]
            if len(exact) == 1:
                return exact[0], overview
            partial = [
                paper
                for paper in papers
                if text in str(paper.get("subject") or "")
                or text in str(paper.get("name") or "")
            ]
            if len(partial) == 1:
                return partial[0], overview
            if len(partial) > 1:
                raise UsageError(
                    f"科目「{text}」有多条匹配，请改用 --paper：\n"
                    + "\n".join(format_paper(p, i + 1) for i, p in enumerate(papers))
                )
            raise UsageError(
                f"找不到科目「{text}」，可选：\n"
                + "\n".join(format_paper(p, i + 1) for i, p in enumerate(papers))
            )
        raise UsageError("必须提供 --subject 或 --paper（或 --pid）")
