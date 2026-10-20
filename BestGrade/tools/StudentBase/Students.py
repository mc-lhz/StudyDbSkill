"""学生档案：绑定学生列表与选择解析。"""
from __future__ import annotations

from Common.Config import UsageError


def formatStudent(student, index=None):
    prefix = f"[{index}] " if index is not None else ""
    grade = student.get("grade") or ""
    className = student.get("class") or ""
    school = student.get("schoolName") or ""
    xuehao = student.get("xuehao") or ""
    return (
        f"{prefix}{student.get('studentName', '')}  {grade}{className}班  "
        f"{school}  学号 {xuehao}  id={student.get('studentId', '')}"
    )


class StudentsMixin:
    def listStudents(self):
        data = self.getJson("/v2/user-center/related-students")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("list", "students", "relatedStudents"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    def selectStudent(self, selector=None):
        students = self.listStudents()
        if not students:
            raise UsageError("当前账号没有绑定学生")
        if selector is None or str(selector).strip() == "":
            if len(students) == 1:
                return students[0]
            raise UsageError(
                "账号绑定了多个学生，请用 --student 指定（id、序号或姓名）：\n"
                + "\n".join(formatStudent(s, i + 1) for i, s in enumerate(students))
            )

        text = str(selector).strip()
        for student in students:
            if student.get("studentId") == text:
                return student

        if text.isdigit():
            index = int(text) - 1
            if 0 <= index < len(students):
                return students[index]

        name, _, grade = text.partition("@")
        matches = [
            student
            for student in students
            if student.get("studentName") == name.strip()
            and (not grade.strip() or grade.strip() in str(student.get("grade") or ""))
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise UsageError(
                f"学生「{text}」有多条匹配，请改用 id 或序号：\n"
                + "\n".join(formatStudent(s, i + 1) for i, s in enumerate(students))
            )
        raise UsageError(
            f"找不到学生「{text}」，候选如下：\n"
            + "\n".join(formatStudent(s, i + 1) for i, s in enumerate(students))
        )
