"""原卷与答题卡：取 JSON 元数据并把页面图片落到本地。"""
from __future__ import annotations

import json
import os
import urllib.parse

from Common.Config import BestGradeError, UsageError, output_root, safe_name

KINDS = ("both", "paper", "answer")


def _ext_from_url(url, default="png"):
    suffix = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower().lstrip(".")
    return suffix if suffix in ("png", "jpg", "jpeg") else default


def _write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


class AnswerSheetMixin:
    def paper_pictures(self, exam_id, paper):
        """原卷页面地址列表。"""
        data = self.get_json(
            f"/v3/exam/{exam_id}/papers/{paper['paperId']}/paper-picture",
            params={"pid": paper.get("pid") or ""},
        )
        if not isinstance(data, list) or not data:
            raise BestGradeError(f"{paper.get('subject', '')} 没有可用的原卷图片")
        return data

    def answer_sheet(self, exam_id, paper):
        """答题卡元数据（含 url、urlResize、questions 等）。"""
        data = self.get_json(
            f"/v3/exam/{exam_id}/papers/{paper['paperId']}/answer-picture",
            params={"pid": paper.get("pid") or ""},
        )
        if not isinstance(data, dict) or not (data.get("url") or []):
            raise BestGradeError(f"{paper.get('subject', '')} 没有可用的答题卡图片")
        return data

    def fetch_images(
        self,
        exam_id,
        subject=None,
        paper_id=None,
        pid=None,
        kind="both",
        out_dir=None,
    ):
        if kind not in KINDS:
            raise UsageError(f"--kind 只能是 {'/'.join(KINDS)}")
        paper, _ = self.resolve_paper(exam_id, subject=subject, paper_id=paper_id, pid=pid)
        subject_name = safe_name(paper.get("subject") or subject or "subject", "subject")
        destination = out_dir or os.path.join(output_root(), str(exam_id), subject_name)
        destination = os.path.abspath(destination)
        os.makedirs(destination, exist_ok=True)

        manifest = {
            "examId": exam_id,
            "subject": paper.get("subject"),
            "paperId": paper.get("paperId"),
            "pid": paper.get("pid"),
            "outDir": destination,
        }

        if kind in ("both", "paper"):
            urls = self.paper_pictures(exam_id, paper)
            json_path = os.path.join(destination, "paper-picture.json")
            _write_json(json_path, {"url": urls})
            files = self._download_pages(urls, os.path.join(destination, "paper"), "jpg")
            manifest["paper"] = {"json": json_path, "files": files}

        if kind in ("both", "answer"):
            data = self.answer_sheet(exam_id, paper)
            urls = data.get("url") or []
            json_path = os.path.join(destination, "answer-picture.json")
            _write_json(json_path, data)
            files = self._download_pages(urls, os.path.join(destination, "answer"), "png")
            manifest["answer"] = {"json": json_path, "files": files}

        return manifest

    def _download_pages(self, urls, folder, default_ext):
        files = []
        for index, url in enumerate(urls, start=1):
            ext = _ext_from_url(url, default_ext)
            path = os.path.join(folder, f"page-{index:02d}.{ext}")
            saved, size, actual = self.download(url, path)
            if actual != ext and actual in ("png", "jpg"):
                final = os.path.join(folder, f"page-{index:02d}.{actual}")
                os.replace(saved, final)
                saved = final
            files.append({"path": saved, "bytes": size, "kind": actual})
        return files
