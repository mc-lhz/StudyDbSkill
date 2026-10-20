"""登录与身份上下文。

**token 不落盘**：登录成功后由 CLI 打印到控制台，后续命令用 `--token` 传入。
这样既不用每次重新登录，也不会在磁盘上留下 bearer 凭据。

密码只存在于调用参数里：不写盘、不读环境变量、不缓存。
登录时按原样提交，**不 strip、不忽略点号**（含首尾点）。
"""
from __future__ import annotations

import base64

from Common.Config import DEVICE_TYPE, BestGradeError, UsageError

# 会话失效的判据。接口没有文档化的过期码，所以退一步看 HTTP 状态与文案；
# 宁可多一次重新登录，也不要拿着废 token 反复失败。
_AUTH_HINTS = ("登录", "会话", "失效", "过期", "未授权")


def isAuthError(exc):
    if getattr(exc, "status", None) in (401, 403):
        return True
    message = str(getattr(exc, "message", exc) or "")
    return any(hint in message for hint in _AUTH_HINTS)


class AuthMixin:
    token = None
    loginName = None
    tokenSource = None  # "provided" | "login"

    def login(self, username, password):
        username = "" if username is None else str(username).strip()
        password = "" if password is None else str(password)
        if not username or not password:
            raise UsageError("必须提供 --username 与 --password")
        body = {
            "loginName": username,
            "password": base64.b64encode(password.encode("utf-8")).decode("ascii"),
            "roleType": 2,
            "loginType": 1,
            "rememberMe": 2,
        }
        data = self.postJson("/v2/users/sessions", body, auth=False)
        if not isinstance(data, dict) or not data.get("token"):
            raise BestGradeError("登录响应缺少 token")
        self.token = data["token"]
        self.loginName = username
        self.loginInfo = data
        self.tokenSource = "login"
        return data

    def useToken(self, token):
        """直接使用外部传入的 token，不发起登录请求。"""
        text = "" if token is None else str(token).strip()
        if not text:
            raise UsageError("--token 不能为空")
        self.token = text
        self.tokenSource = "provided"
        return text

    def switchStudent(self, student):
        """把会话切到指定学生，student 为学生字典。

        每次命令都要切换：复用 token 只省掉登录，不省会话里的学生上下文。
        """
        studentId = student.get("studentId") if isinstance(student, dict) else str(student)
        if not studentId:
            raise UsageError("缺少 studentId")
        data = self.postJson(
            "/v2/user-center/sessions",
            {"studentId": studentId, "deviceType": DEVICE_TYPE},
        )
        self.studentId = studentId
        self.student = student if isinstance(student, dict) else {"studentId": studentId}
        return data

    def ensureToken(self):
        if not self.token:
            raise BestGradeError("尚未登录，请先调用 login() 或 useToken()")
        return self.token