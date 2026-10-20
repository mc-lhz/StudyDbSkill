# ScoreClient（门面 + CLI）

组合 `AuthMixin / StudentsMixin / ExamsMixin / AnswerSheetMixin / Http`，对外统一入口。

## 两步走：先换 token，再用 token

```bash
# 1) 登录一次，拿到 token（打印到标准输出，不落盘）
python tools/ScoreClient.py login --username <账号> --password <密码>

# 2) 之后所有命令都用 token，不再登录
python tools/ScoreClient.py exams    --token <token> --student 2
python tools/ScoreClient.py overview --token <token> --student 2 --exam 2592656
python tools/ScoreClient.py images   --token <token> --student 2 --exam 2592656 --subject 生物
```

`--username/--password` 与 `--token` 二选一：给了 token 就不登录；
两个都没给会报参数错误并提示先 `login`。

## 子命令

| 命令 | 必填 | 主要输出 |
|---|---|---|
| `login` | `--username --password` | **token**（标准输出） |
| `students` | `--token` | 绑定学生列表 |
| `exams` | `--token`，多学生时加 `--student` | 考试列表 |
| `overview` | 再加 `--exam` | 元数据 + 各科 paperId/pid |
| `images` | 再加 `--exam` 与 `--subject`/`--paper` | 原卷/答题卡 JSON 与图片 |

公共参数：`--token` `--username` `--password` `--student` `--json`；
`exams/overview/images` 支持 `--limit`。

## 类用法

```python
from ScoreClient import ScoreClient

c = ScoreClient()
c.use_token("<token>")          # 或 c.login("账号", "密码")
student = c.select_student("2")
c.switch_student(student)
exams = c.list_exams(limit=5)["list"]
```

类本身不做隐式登录；CLI 每个子命令都会先取凭据再按需切换学生。

## 退出码

`0` 成功；`2` 参数或选择歧义；`3` 网络/鉴权/接口错误。

## 注意

- **凭据不落盘**：密码只在 `login` 进程内，token 只在输出与 `--token` 参数里。
- `login` 会打印 token，不要在共享机器 / 录屏环境执行。
- token 失效且同时给了账号密码时，会自动重登一次（`_retryable`）。
- `--json` 输出原始结构，便于二次处理；人类可读输出只是摘要。
