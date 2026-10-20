# AnswerSheet（原卷与答题卡）

## `paperPictures(examId, paper)`

`GET /v3/exam/{examId}/papers/{paperId}/paper-picture?pid={pid}`

返回 JPG 地址数组。空数组视为学校未上传，抛 `BestGradeError`。

## `answerSheet(examId, paper)`

`GET /v3/exam/{examId}/papers/{paperId}/answer-picture?pid={pid}`

返回答题卡元数据：`url`、`urlResize`、`questions`、`score` 等。
`url` 为空时抛 `BestGradeError`。

## `fetchImages(examId, subject=None, paperId=None, pid=None, kind="both", outDir=None)`

1. `resolvePaper` 定位科目；
2. 输出目录：`--out` 或 `%TEMP%\BestGrade\<examId>\<科目>\`；
3. 保存 `paper-picture.json` / `answer-picture.json`；
4. 按页下载到 `paper/page-01.jpg`、`answer/page-01.png`；
5. 返回 manifest（含 `json` 路径、每页 `path/bytes/kind`）。

`kind` 取 `both|paper|answer`；扩展名优先取 URL，实际 magic 不一致时自动改名。

## 注意

- 页面 URL 是签名链接，过期需重新调用。
- 文件名固定两位页序，重跑会覆盖同页文件。
