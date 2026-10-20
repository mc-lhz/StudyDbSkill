"""HTTP 传输层：JSON 信封校验、鉴权头、图片下载。

所有业务模块通过本类发请求，不直接使用 urllib。
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from Common.Config import (
    BASE_URL,
    DEVICE_TYPE,
    TIMEOUT,
    TOKEN_HEADER,
    USER_AGENT,
    BestGradeError,
)


class Http:
    def __init__(self, base_url=BASE_URL, timeout=TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = None

    def _url(self, path, params=None):
        url = path if path.startswith(("http://", "https://")) else self.base_url + path
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        return url

    def _headers(self, body, auth=True):
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "deviceType": DEVICE_TYPE,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if auth and self.token:
            headers[TOKEN_HEADER] = self.token
        return headers

    def request(self, method, path, body=None, params=None, auth=True):
        """发请求并解包信封，返回 data 字段。"""
        url = self._url(path, params)
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url, data=raw, headers=self._headers(body, auth), method=method.upper()
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            raise BestGradeError(
                self._error_message(payload) or f"HTTP {exc.code}", status=exc.code
            ) from None
        except urllib.error.URLError as exc:
            raise BestGradeError(f"网络不可达：{exc.reason}") from None
        return self._unwrap(payload)

    def _error_message(self, payload):
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return ""
        if isinstance(data, dict):
            return str(data.get("msg") or data.get("message") or "")
        return ""

    def _unwrap(self, payload):
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise BestGradeError("响应不是合法 JSON") from None
        if not isinstance(data, dict):
            raise BestGradeError("响应结构异常：顶层不是对象")
        meta = data.get("meta") if "code" not in data and isinstance(data.get("meta"), dict) else data
        code = meta.get("code", 0)
        try:
            code_num = int(code)
        except (TypeError, ValueError):
            code_num = code
        if code_num != 0:
            message = meta.get("msg") or meta.get("message") or f"接口返回 code={code}"
            raise BestGradeError(str(message), code=code_num)
        return data.get("data")

    def get_json(self, path, params=None, auth=True):
        return self.request("GET", path, params=params, auth=auth)

    def post_json(self, path, body, params=None, auth=True):
        return self.request("POST", path, body=body, params=params, auth=auth)

    def download(self, url, dest):
        """下载单个文件，校验图片 magic，返回 (路径, 字节数, 类型)。"""
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=max(self.timeout, 60)) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as exc:
            raise BestGradeError(f"图片下载失败：HTTP {exc.code}", status=exc.code) from None
        except urllib.error.URLError as exc:
            raise BestGradeError(f"图片下载失败：{exc.reason}") from None
        kind = sniff_image(payload)
        if kind is None:
            raise BestGradeError("下载内容不是 PNG/JPEG，可能链接已过期")
        parent = os.path.dirname(os.path.abspath(dest))
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".part-", dir=parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp, dest)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return dest, len(payload), kind


def sniff_image(payload):
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None
