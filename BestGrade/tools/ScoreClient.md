# ScoreClient（门面 + CLI）

组合 `AuthMixin / StudentsMixin / ExamsMixin / AnswerSheetMixin / Http`，对外统一入口。

## 类

```python
from ScoreClient import ScoreClient

c = ScoreClient()
c.login("账号", "密码")
student = c.select_student("2")
c.switch_student(student)
exams = c.list_exams(limit=5)["list"]
```

类本身不做隐式登录；CLI 的每个子命令都会先登录再按需切换学生。

## 子命令

| 命令 | 必填 | 主要输出 |
|---|---|---|
| `students` | `--username --password` | 绑定学生列表 |
| `exams` | 同上，多学生时加 `--student` | 考试列表 |
| `overview` | 再加 `--exam` | 元数据 + 各科 paperId/pid |
| `images` | 再加 `--exam` 与 `--subject`/`--paper` | 原卷/答题卡 JSON 与图片 |

公共参数：`--student`、`--json`；`exams/overview/images` 支持 `--limit`。

## 退出码

`0` 成功；`2` 参数或选择歧义；`3` 网络/鉴权/接口错误。

## 注意

- `--password` 仅本次进程使用，不落盘。
- `--json` 输出原始结构，便于二次处理；人类可读输出只是摘要。
