# TestQueue.py

## 职责

`tools/Review/Queue.py` 的离线测试。同样不联网、不碰真实数据仓，用例自带临时仓。

## 对应数据

无。`make_record` / `vault` 在临时目录造卡片（`points/<章>/KP-*.md`），`TODAY` 固定 `2026-10-19`。

## 覆盖的 12 条

| 用例 | 钉住的行为 |
|---|---|
| `test_verified_gate` | `verified: false` 不进复习队列 |
| `test_verified_included` | `verified: true` 且到期才进队列 |
| `test_graduated_leaves_queue` | `已掌握` 不再出现在复习队列 |
| `test_future_not_due` | `next_review` 未到期不进默认队列 |
| `test_score_formula` | `逾期天数 × value 权重`，高 3 / 中 2 / 低 1 |
| `test_value_ordering` | 同逾期天数时高价值排前面 |
| `test_bom_tolerated` | 带 BOM 的记录照样解析出日期 |
| `test_bad_date_flagged_not_crashed` | 坏日期**报出来**而不是静默丢弃或崩 |
| `test_empty_queue_is_success` | 空队列退出 `0`，且文本说清「没读到卡」 |
| `test_no_data_root` | 数据根不可解析时退出 `6` |
| `test_cards_in_chapter_subdirs` | 卡在 `points/<章>/` 子目录里也不会被扫漏 |
| `test_cause_from_evidence` | 错因从 `## 错题证据` 读出来（`会但粗心` 可识别） |

## 最小用法

```
python tools/TestCases/TestQueue.py
```

成功以 `RESULT: OK` 结尾、退出 `0`；失败打印 `RESULT: n FAILED -> 用例名`、退出 `1`。

## 注意事项

- **`test_empty_queue_is_success` 是在防「用沉默撒谎」**：队列为空可能意味着该复核而非该休息，所以判空交给输出里的原因说明，不靠退出码
- **`test_bom_tolerated` 对应一次真实事故**：PowerShell 写的 BOM 曾让所有日期读成空，记录看起来「没有日期」而不是「文件坏了」
- **`test_bad_date_flagged_not_crashed`** 是「失败绝不当成功」的具体化：坏数据必须出现在输出里，不能被 catch 掉
- 改 `Queue.py` 后必须重跑；`--group` / `--all` / `--limit` 的渲染没有单测覆盖，改输出格式要手工看一眼
