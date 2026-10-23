# Queue.py

## 职责

打印错题仓的**复习队列**。**只读，不写任何文件。**

一次扫描产出两条队列，因为它们回答的问题不同：

| 队列 | 内容 | 回答 |
|---|---|---|
| 复习队列（默认） | `verified: true` 且 `next_review` 到期的记录 | 今天该复习什么 |
| 复核队列（`--pending`） | `verified: false` 的记录 | 先复核哪条 |

## 为什么待复核队列必须存在

首份真实卷子的 19 张卡**全部** `verified: false`，所以默认队列合法地为空。
此时只打印「今天没有要复习的」是**用沉默撒谎**——那天该做的事是复核，不是复习。

工具必须说清楚「为什么空」以及「那该做什么」。这条分支在 `render_text` 里被特意照顾。

## 为什么队列不落盘

`AGENTS.md` 的派生层列了 `data/indexes/queue` 这份索引，但本工具**不生成它**。

队列是**时间相关**的：`--today` 一变、时钟一走，文件立刻过期，成了一份看起来权威、
实际每天在腐烂的文档，还会被 git 记成噪声 diff。现扫现算只花一次目录遍历。
若将来要静态快照，那是 `Rebuild/RebuildIndexes.py` 的事。

## 对应数据

`<数据根>/data/subjects/生物/points/**/*.md` —— **卡就是复习单元**。
schema 1.13 起错题不再单独成文件：错题证据挂在卡的 `## 错题证据` 下，
所以「有证据」≠「做错过」——满分但当时犹豫的题也照样挂上来。

不再读 `errors/`：该目录已取消。若它还在，队列会提示旧 schema 残留。

## 方法清单

| 方法 | 作用 |
|---|---|
| `resolve_data_root` | `BIOVAULT_HOME` > `config.json dataRoot` > `None`（绝不回落 `examples/`） |
| `parse_front_matter` | 手写 YAML 子集解析；**先剥 UTF-8 BOM** |
| `load_cards` | 递归读 `points/<章>/*.md`；坏日期的卡**保留并标记**，不静默丢弃 |
| `evidence_count` / `detect_cause` | 数 `## 错题证据` 里的块；错因从证据块取，多块时取最严格的（会但粗心 优先） |
| `split_queues` | 一趟分四桶：review / upcoming / pending / bad |
| `score` | `逾期天数 × 权重`（高 3 / 中 2 / 低 1） |
| `render_text` / `render_json` | 两种输出 |

## 最小用法

```
python tools/Review/Queue.py                      # 复习队列
python tools/Review/Queue.py --pending            # 待复核队列
python tools/Review/Queue.py --pending --group cause
python tools/Review/Queue.py --all                # 附未到期
python tools/Review/Queue.py --limit 5 --json
python tools/Review/Queue.py --today 2026-10-19   # 覆盖「今天」，测试与复现用
```

## 排序

`score = 逾期天数 × value 权重`，降序；同分按 `next_review` 升序、再按文件名升序
——**保证输出稳定可 diff**。`--group cause|chapter|point` 改为聚簇，供批量复核用。

不做 SM-2：`AGENTS.md` 明说「高中生版本够用」，且 `MEMORY.md § A3` 还在等实测。

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 跑完。**队列为空也是 0**——空是状态，不是错误；判空交给 stdout 与 `--json` 的 `counts` |
| `2` | `--today` 格式非法 |
| `6` | 数据根不可解析 |

不新增「队列为空」的错误码：会污染 `AGENTS.md` 已定的统一契约，收益只是一个 `if`。

## 注意事项

- **`--today` 不是可选装饰**：不给它，测试就依赖真实时钟——今天绿、下个月红
- **「没读到卡」和「没有要复习的」必须分开说**：0 张卡时输出会直接指出配置问题，而不是安抚你「队列确实是空的」
- **坏日期要报不要跳**：静默丢一条，用户会以为它在队列里（`失败绝不当成功`）
- **`会但粗心` 只提示不拦截**：真正的拦截在 `Mark.py` 写入时做，提示拦不住人，校验才会
- **不要为了让输出好看而放开 verified 闸门**：闸门一松，整个仓教的东西都不可信
- 测试见 `tools/TestCases/TestQueue.py`，含反向用例；改本文件后必须重跑
