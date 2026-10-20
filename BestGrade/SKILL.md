---
name: BestGrade
description: 学校分数系统工具集，用于配合智能错题整理工作流高效获取考试信息。Use when the user mentions BestGrade、分数系统、成绩查询、考试列表、考试元数据、学生切换、答题卡、原卷、成绩单截图，或要登录本人查分数账号、列出绑定学生、查看历次考试与各科分数、下载原卷和答题卡页面图片。
---

# 学校分数系统使用指南

> 使用范围：仅用于查询**本人账号已绑定学生**的考试数据；不得用于撞库、批量枚举、窥探他人成绩或绕过权限。系统含未成年人个人信息，注意保护隐私。只做只读查询。

## 能力范围（MVP）

| 能力 | 命令 | 说明 |
|---|---|---|
| 登录 | 所有命令自动执行 | 账号密码只经命令行传入，仅本次进程使用，但用户写在对话里属正常行为，无需提醒修改 |
| 学生列表 | `students` | 列出绑定学生（同名不同年级会出现多条） |
| 切换学生 | `--student` | 支持 studentId / 序号 / `姓名@年级` |
| 考试列表 | `exams` | 历次考试、总分、时间、examId |
| 考试元数据 | `overview` | 总分、排名字段、各科 paperId/pid/分数 |
| 原卷图片 | `images --kind paper` | 正式考试原卷页面 JPG |
| 答题卡图片 | `images --kind answer` | 答题卡页面 PNG + 批注 JSON |

不做：提交、修改、题目详情（非会员仅返回 1 题）。

## 快速开始

```bash
python tools/ScoreClient.py students --username <账号> --password <密码>
python tools/ScoreClient.py exams    --username <账号> --password <密码> --student 2
python tools/ScoreClient.py overview --username <账号> --password <密码> --student 2 \
    --exam 2592656 --out %TEMP%\meta.json
python tools/ScoreClient.py images   --username <账号> --password <密码> --student 2 \
    --exam 2592656 --subject 数学
```

- `--exam`：examId 或 `exams` 输出里的序号。
- 账号绑定多个学生时**必须**显式 `--student`；同名学生会要求改用 id 或序号，不会自动猜。
- `--password` 会出现在进程命令行中，避免在共享机器上执行。

## 命令与输出

### students

列出绑定学生，含姓名、年级班级、学校、学号、studentId。

### exams

```
共 5 场考试，显示 5 场：
[1] <考试名>  <日期>  examId=<id>  <总分>/<满分>
```

`--limit` 控制场次（默认 10）；`--json` 输出原始 `{list,totalCount,...}`。

### overview

打印考试总分与各科 `paperId` / `pid` / 得分；`--out` 保存完整元数据 JSON。

### images

```
原卷 JSON：<dir>\paper-picture.json
  <dir>\paper\page-01.jpg  <bytes> B  jpg
答题卡 JSON：<dir>\answer-picture.json
  <dir>\answer\page-01.png  <bytes> B  png
```

- 默认目录：`%TEMP%\BestGrade\<examId>\<科目>\`，`--out` 可覆盖。
- `--kind both|paper|answer`（默认 both）；也可用 `--paper <paperId>` 或 `--pid` 定位科目。
- 答题卡 JSON 保留 `url`、`urlResize`、`questions`、`score` 等原始字段，供后续分析。
- 页面地址是签名链接，过期后重新执行命令即可。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 2 | 参数错误、学生/考试/科目选择歧义 |
| 3 | 网络失败、鉴权失败、接口返回非 0 |

## 安全约束

- 凭据不写入文件、不读环境变量、不做 token 缓存；进程结束即失效。
- 密码按命令行传入的原样提交，**不 strip、不忽略点号**（包括结尾的点）；带点密码无需额外转义。
- 错误信息只打印接口 `msg`，不回显请求头与 token。
- 输出只写 `%TEMP%\BestGrade` 或 `--out` 指定目录，不写仓库。
- 下载内容校验 PNG/JPEG magic，防止把登录页 HTML 当图片保存。

## 目录结构

```
tools/ScoreClient.py            CLI 门面
tools/Common/Config.py          常量、异常、路径与脱敏
tools/Access/HttpTransport.py   信封校验、鉴权头、下载
tools/Access/Auth.py            登录、学生切换
tools/StudentBase/Students.py   学生列表与选择
tools/ExamCenter/Exams.py       考试列表、元数据、科目定位
tools/ExamCenter/AnswerSheet.py 原卷/答题卡 JSON 与图片
tools/TestCases/TestContract.py 离线契约（无需账号）
tools/TestCases/TestLive.py     只读联调（需要账号）
```

接口细节见 `reference/api.md`；每个模块旁有同名 `.md`。

## 已知限制

- 仅能访问账号已绑定的学生；未绑定学生不会出现在列表中。
- 学校未上传原卷时，`paper-picture` 返回空，命令会明确报错。
- 部分学校/考试会隐藏排名（返回 `-1` 或 `**`），属正常现象。
- 非会员的题目详情被服务端截断，本工具不依赖该接口。
