# Students（绑定学生）

## `list_students()`

`GET /v2/user-center/related-students`，返回数组。兼容 `{list:[...]}` 形式。

## `select_student(selector=None)`

| selector | 匹配规则 |
|---|---|
| 空 | 仅当只有一个学生时返回；多个则抛 `UsageError` 并列出候选 |
| 18 位 id | 精确匹配 `studentId` |
| 纯数字 | 先按 id 匹配，未命中再当 1 起的序号 |
| `姓名` | 精确匹配姓名，唯一才返回 |
| `姓名@年级` | 姓名 + 年级包含匹配，用于同名不同年级 |

匹配多条或零条都会列出全部候选，退出码 2；**不会自动猜**同名学生的年级。

## `format_student(student, index=None)`

生成一行摘要：`[序号] 姓名  年级班级  学校  学号  id=...`。
