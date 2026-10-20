"""离线契约测试：不联网、不需要凭据。

检查编译、导入、CLI、文档配对、禁词、凭据与绝对路径泄漏。
"""
from __future__ import annotations

import base64
import compileall
import importlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".toml", ".yml", ".yaml", ".ini", ".cfg"}
FORBIDDEN = [
    base64.b64decode("5aW955qE5pWw").decode("utf-8"),
    base64.b64decode("aGFvZmVuc2h1").decode("utf-8"),
]

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))


def iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.endswith(".pyc"):
            continue
        yield path


def test_compile():
    ok = compileall.compile_dir(str(TOOLS), quiet=1, force=True)
    check("compileall tools", ok)


def test_imports():
    sys.path.insert(0, str(TOOLS))
    modules = [
        "ScoreClient",
        "Common.Config",
        "Access.HttpTransport",
        "Access.Auth",
        "StudentBase.Students",
        "ExamCenter.Exams",
        "ExamCenter.AnswerSheet",
    ]
    failed = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - 契约测试需要收集全部失败
            failed.append(f"{name}: {exc}")
    check("import modules", not failed, "; ".join(failed))


def test_cli():
    script = str(TOOLS / "ScoreClient.py")
    ok = True
    output = ""
    for args in (["--help"], ["students", "--help"], ["images", "--help"]):
        proc = subprocess.run(
            [sys.executable, script, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            ok = False
            output = proc.stderr.strip()
            break
    check("CLI help", ok, output)


def test_docs():
    missing = [
        str(path.relative_to(ROOT))
        for path in TOOLS.rglob("*.py")
        if path.name != "__init__.py" and not path.with_suffix(".md").exists()
    ]
    check("py/md pairing", not missing, ", ".join(missing))


def test_forbidden_terms():
    hits = []
    for path in iter_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for term in FORBIDDEN:
            if term.lower() in text:
                hits.append(f"{path.relative_to(ROOT)}: {term}")
    check("forbidden terms", not hits, "; ".join(hits))


def test_credentials():
    phone = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
    secret = re.compile(
        r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{3,}['\"]"
    )
    token = re.compile(r"(?i)hfs-token['\"]?\s*[:=]\s*['\"][A-Za-z0-9._-]{16,}['\"]")
    hits = []
    for path in iter_files():
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in (("phone", phone), ("secret", secret), ("token", token)):
            if pattern.search(text):
                hits.append(f"{path.relative_to(ROOT)}: {label}")
    check("no credentials", not hits, "; ".join(hits))


def test_absolute_paths():
    pattern = re.compile(r"(C:" + r"\\\\?Users" + r"|D:" + r"\\\\" + r"|/home/|/Users/)")
    hits = [
        str(path.relative_to(ROOT))
        for path in iter_files()
        if path != Path(__file__).resolve()
        and path.suffix.lower() in TEXT_SUFFIXES
        and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    check("no absolute user paths", not hits, ", ".join(hits))


def test_password_preserved():
    sys.path.insert(0, str(TOOLS))
    from Access.Auth import AuthMixin

    captured = {}

    class Dummy(AuthMixin):
        token = None

        def post_json(self, path, body, params=None, auth=True):
            captured["body"] = body
            return {"token": "fake-token"}

    raw = " QWwq.1221. "
    Dummy().login("user", raw)
    decoded = base64.b64decode(captured["body"]["password"]).decode("utf-8")
    check("password keeps dots/spaces", decoded == raw, repr(decoded))


def test_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    ok = bool(re.fullmatch(r"\d+\.\d+\.\d+", version))
    check("VERSION semver", ok, version)


def test_skill():
    path = ROOT / "SKILL.md"
    if not path.exists():
        check("SKILL.md", False, "missing")
        return
    text = path.read_text(encoding="utf-8")
    ok = (
        text.startswith("---\n")
        and "name: BestGrade" in text
        and "description:" in text
        and "# 学校分数系统使用指南" in text
    )
    check("SKILL frontmatter/title", ok)
    check("reference/api.md", (ROOT / "reference" / "api.md").exists())


def main():
    test_compile()
    test_imports()
    test_cli()
    test_docs()
    test_forbidden_terms()
    test_credentials()
    test_absolute_paths()
    test_password_preserved()
    test_version()
    test_skill()
    failed = [item for item in results if not item[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
