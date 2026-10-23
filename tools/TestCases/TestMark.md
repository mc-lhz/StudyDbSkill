# TestMark.py

## 职责

`tools/Review/Mark.py` 的离线测试。**不联网、不碰真实数据仓**：每个用例在临时目录里
现造一个小仓，跑完即删。

## 对应数据

无。用例自带夹具：`write_record` 造知识卡（`points/<章>/KP-*.md`，含 `## 错题证据`），
`vault` 把若干张装进临时数据根，
`TODAY` 固定为 `2026-10-19`，所以结果不随真实时钟漂移。

## 覆盖的 11 条

| 用例 | 钉住的行为 |
|---|---|
| `test_no_yes_does_not_write` | 缺 `--yes` 只预览、退出 `5`、文件逐字节不变 |
| `test_first_right` | 第 1 次对 → `已订正` / `review_count=1` / `+1 天` |
| `test_second_right_interval_and_status` | 第 2 次对 → `已复现` / `+3 天` |
| `test_third_right_graduates` | 第 3 次对 → `已掌握` / `+7 天` |
| `test_wrong_resets_to_new` | 做错一律降回 `新错`、计数归零 |
| `test_careless_guard_survives_ladder_shortening` | 把 `GRADUATE_COUNT` 改成 1，`会但粗心` 照样拦得住 |
| `test_unverified_refused` | `verified: false` 默认拒绝写 |
| `test_unknown_id` | 不存在的 id 报错，不新建文件 |
| `test_newline_and_body_preserved` | CRLF 与正文一字不差 |
| `test_json_output` | `--json` 输出可解析 |
| `test_batch_mixed` | 批量里一条失败不阻断其余，退出码如实反映 |

## 最小用法

```
python tools/TestCases/TestMark.py
```

成功以 `RESULT: OK` 结尾、退出 `0`；失败打印 `RESULT: n FAILED -> 用例名`、退出 `1`。

## 注意事项

- **这 11 条里有多条是反向用例**（不该写、不该放过），它们才是真正值钱的：正向用例只能证明「能跑」，反向用例才证明「拦得住」
- `会但粗心` 那条是**变异测试**：把阶梯调短后仍须通过。改了 `MIN_INTERVALS` 或 `GRADUATE_COUNT` 而它变绿，说明守卫被悄悄绕过
- 改 `Mark.py` 后**必须重跑**；测试绿了再提交
- 测试不写真实数据仓，所以它绿**不代表**你的真实记录没被写歪——真实写入仍靠 `Mark.py` 的回读校验
