"""全局配置与异常定义。

只放常量、异常和少量无依赖工具函数，供其余模块导入。
"""
from __future__ import annotations

import os
import re
import tempfile

BASE_URL = "https://hfs-be.yunxiao.com"
DEVICE_TYPE = "3"
TIMEOUT = 20
TOKEN_HEADER = "hfs-token"
DEFAULT_LIMIT = 10
OUTPUT_ROOT = os.path.join(tempfile.gettempdir(), "BestGrade")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class BestGradeError(Exception):
    """业务或网络错误，默认退出码 3。"""

    exit_code = 3

    def __init__(self, message, code=None, status=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class UsageError(BestGradeError):
    """参数、选择歧义等使用者错误，退出码 2。"""

    exit_code = 2


def output_root():
    """输出根目录，固定落在系统临时目录，避免污染仓库。"""
    return OUTPUT_ROOT


_SAFE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def safe_name(value, fallback="item"):
    """把考试名/科目名收敛成安全的单层目录名。"""
    text = _SAFE.sub("_", str(value or "")).strip(" ._")
    return text[:60] or fallback


def mask_account(name):
    """账号脱敏：保留首尾字符。"""
    text = str(name or "")
    if len(text) <= 2:
        return "*" * len(text)
    if len(text) <= 6:
        return text[0] + "*" * (len(text) - 2) + text[-1]
    return text[:2] + "*" * (len(text) - 4) + text[-2:]
