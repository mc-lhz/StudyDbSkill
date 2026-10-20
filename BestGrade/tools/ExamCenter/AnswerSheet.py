"""原卷与答题卡：取 JSON 元数据并把页面图片落到本地。"""
from __future__ import annotations

import json
import os
import urllib.parse

from Common.Config import BestGradeError, UsageError, outputRoot, safeName

KINDS = ("both", "paper", "answer")


def _extFromUrl(url, default="png"):
    suffix = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower().lstrip(".")
    return suffix if suffix in ("png", "jpg", "jpeg") else default


def _writeJson(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


class AnswerSheetMixin:
    def paperPictures(self, examId, paper):
        """原卷页面地址列表。"""
        data = self.getJson(
            f"/v3/exam/{examId}/papers/{paper['paperId']}/paper-picture",
            params={"pid": paper.get("pid") or ""},
        )
        if not isinstance(data, list) or not data:
            raise BestGradeError(f"{paper.get('subject', '')} 没有可用的原卷图片")
        return data

    def answerSheet(self, examId, paper):
        """答题卡元数据（含 url、urlResize、questions 等）。"""
        data = self.getJson(
            f"/v3/exam/{examId}/papers/{paper['paperId']}/answer-picture",
            params={"pid": paper.get("pid") or ""},
        )
        if not isinstance(data, dict) or not (data.get("url") or []):
            raise BestGradeError(f"{paper.get('subject', '')} 没有可用的答题卡图片")
        return data

    def fetchImages(
        self,
        examId,
        subject=None,
        paperId=None,
        pid=None,
        kind="both",
        outDir=None,
    ):
        if kind not in KINDS:
            raise UsageError(f"--kind 只能是 {'/'.join(KINDS)}")
        paper, _ = self.resolvePaper(examId, subject=subject, paperId=paperId, pid=pid)
        subjectName = safeName(paper.get("subject") or subject or "subject", "subject")
        destination = outDir or os.path.join(outputRoot(), str(examId), subjectName)
        destination = os.path.abspath(destination)
        os.makedirs(destination, exist_ok=True)

        manifest = {
            "examId": examId,
            "subject": paper.get("subject"),
            "paperId": paper.get("paperId"),
            "pid": paper.get("pid"),
            "outDir": destination,
        }

        if kind in ("both", "paper"):
            urls = self.paperPictures(examId, paper)
            jsonPath = os.path.join(destination, "paper-picture.json")
            _writeJson(jsonPath, {"url": urls})
            files = self._downloadPages(urls, os.path.join(destination, "paper"), "jpg")
            manifest["paper"] = {"json": jsonPath, "files": files}

        if kind in ("both", "answer"):
            data = self.answerSheet(examId, paper)
            urls = data.get("url") or []
            jsonPath = os.path.join(destination, "answer-picture.json")
            _writeJson(jsonPath, data)
            files = self._downloadPages(urls, os.path.join(destination, "answer"), "png")
            manifest["answer"] = {"json": jsonPath, "files": files}

        return manifest

    def _downloadPages(self, urls, folder, defaultExt):
        files = []
        for index, url in enumerate(urls, start=1):
            ext = _extFromUrl(url, defaultExt)
            path = os.path.join(folder, f"page-{index:02d}.{ext}")
            saved, size, actual = self.download(url, path)
            if actual != ext and actual in ("png", "jpg"):
                final = os.path.join(folder, f"page-{index:02d}.{actual}")
                os.replace(saved, final)
                saved = final
            files.append({"path": saved, "bytes": size, "kind": actual})
        return files
