# TestLive（只读联调）

```bash
python tools/TestCases/TestLive.py --username <账号> --password <密码> [--student 2] \
    [--exam 1] [--subject 数学] [--out DIR]
```

流程与断言：

1. 登录成功且有 `token`；
2. 绑定学生非空；
3. 能切换学生（未指定时逐个尝试，选第一个有考试数据的）；
4. 考试列表非空；
5. `overview` 的 `papers` 非空；
6. 数学优先，缺考时回落第一科；
7. 原卷 JPG 与答题卡 PNG 均下载成功；
8. 校验图片 magic；答题卡解析 PNG IHDR 宽高；
9. 答题卡 JSON 含 `questions`。

只调用读接口；输出写到 `--out` 或临时目录，并打印路径。
失败退出码 1，逐项打印 PASS/FAIL。

## 注意

- 不要在共享终端回放命令历史（含 `--password`）。
- 图片与 JSON 含学生信息，测试后按需清理。
