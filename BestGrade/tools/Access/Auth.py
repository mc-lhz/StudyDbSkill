"""登录与身份上下文。

凭据只在本次进程内使用，不写盘、不缓存。
密码按调用方传入的原样提交：不 strip、不忽略点号（含首尾点）。
"""
from __future__ import annotations

import base64

from Common.Config import DEVICE_TYPE, BestGradeError, UsageError


class AuthMixin:
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
        data = self.post_json("/v2/users/sessions", body, auth=False)
        if not isinstance(data, dict) or not data.get("token"):
            raise BestGradeError("登录响应缺少 token")
        self.token = data["token"]
        self.login_name = username
        self.login_info = data
        return data

    def switch_student(self, student):
        """把会话切到指定学生，student 为学生字典。"""
        student_id = student.get("studentId") if isinstance(student, dict) else str(student)
        if not student_id:
            raise UsageError("缺少 studentId")
        data = self.post_json(
            "/v2/user-center/sessions",
            {"studentId": student_id, "deviceType": DEVICE_TYPE},
        )
        self.student_id = student_id
        self.student = student if isinstance(student, dict) else {"studentId": student_id}
        return data

    def ensure_token(self):
        if not self.token:
            raise BestGradeError("尚未登录，请先调用 login()")
        return self.token
