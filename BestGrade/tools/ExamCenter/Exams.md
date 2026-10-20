# Exams（考试与科目）

## `listExams(limit=10, start=0)`

`GET /v3/exam/list?start=&limit=`，返回 `{list,totalCount,isStrongBaseSchool,...}`。
`limit <= 0` 抛 `UsageError`。

## `resolveExam(selector, limit=10)`

- examId 精确匹配；
- 纯数字未命中 examId 时按 1 起序号；
- 否则按考试名**包含**匹配，唯一才返回；
- 多条/零条抛 `UsageError`，并列出候选。

内部会把 `limit` 至少放大到 10，避免序号与展示不一致。

## `examOverview(examId)`

`GET /v3/exam/{examId}/overview`，返回完整元数据（含 `papers`）。

## `resolvePaper(examId, subject=None, paperId=None, pid=None)`

优先级：`pid` > `paperId` > `subject`。
`subject` 先精确匹配 `subject`/`name`，再包含匹配；多条或零条列出全部科目。
返回 `(paper, overview)`。

## 格式化

- `formatExam`：`[序号] 名称  日期  examId=...  总分/满分`
- `formatPaper`：`[序号] 科目（全名）  得分/满分  paperId=... pid=...`
