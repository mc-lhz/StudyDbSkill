# ValidateRecords.py

## 职责

数据仓的**入库闸门**。在 push 之前回答一个问题：这批记录能不能进 git 历史。

校验四层，任一不过就不该 merge：

| 层 | 查什么 | 退出码 |
|---|---|---|
| 结构 | front-matter 必填字段齐不齐、正文必填区段在不在 | `2` |
| 枚举 | `chapter`/`point`/`cause`/`kind`/`qtype`/`value`/`status` 是否在真源内 | `4` |
| 脱敏 | 校名、教师姓名、考号是否泄漏 | `5` |
| 数据根 | 能不能定位到数据仓 | `6` |

**没有 PyYAML 依赖**：一个需要先装依赖才能跑的校验器，最后没人会跑。

## 对应数据

| 路径 | 用途 |
|---|---|
| `<数据根>/data/subjects/生物/errors/**/*.md` | 错题记录（**递归**，允许按章分子目录） |
| `<数据根>/data/subjects/生物/points/**/*.md` | 知识点卡（**递归**，实际按 神经调节 / 体液调节 / 内环境与稳态 分子目录） |
| `<数据根>/data/subjects/生物/exams/*.md` | 考试档案（只计数） |
| `reference/taxonomy.md` | 章节树真源（5 章 18 节） |
| `reference/causes.md` | 11 个错因 |
| `reference/kinds.md` | 8 种知识点类型 + 正文必填区段 |
| `reference/norms.md` | 8 条答题规范 |

数据根解析顺序：`BIOVAULT_HOME` > `config.json` 的 `dataRoot` > **失败**。
**绝不回落到 `examples/`**——那是另一份数据集，回落等于用假数据验真数据。

## 方法清单

| 方法 | 作用 |
|---|---|
| `resolve_data_root` | 上面三级解析，失败返回 `None` |
| `parse_front_matter` | 手写 YAML 子集解析；**先剥 UTF-8 BOM** |
| `enum_from_table` | 从 `reference/*.md` 的表格里取某一列，枚举只有这一个真源 |
| `load_enums` | 一次性加载四份真源 |
| `check_enum` | 枚举外 → problem，兜底规则 → 附警告 |
| `validate_error` / `validate_point` | 按 `ERROR_REQUIRED` / `POINT_REQUIRED` 与区段表逐条查 |
| `scan_sensitive` | 全仓文本扫 `SENSITIVE` 黑名单 |

## 必填字段

```
错题：id subject exam date chapter point qtype cause value status
      first_wrong last_review review_count next_review verified
错题正文区段：## 我的错解 / ## 正解思路 / ## 一句话教训 / ## 这题的价值
知识点：id title kind created updated
```

## 最小用法

```
python tools/Check/ValidateRecords.py
BIOVAULT_HOME=/path/to/data python tools/Check/ValidateRecords.py   # 临时指定数据根
```

输出每条 `FAIL` / `WARN`，末尾一行 `RESULT: OK` 或 `RESULT: FAIL`。

## 注意事项

- **BOM 会让校验静默失效**：带 BOM 的文件会被当成「没有 front matter」，于是必填字段一条都不查、看起来全绿。PowerShell 5.1 的 `Set-Content -Encoding utf8` 正好写 BOM
- **必须递归**：`points/` 按章分了子目录，只扫一层会把 19 张卡读成 0 张还照样 `RESULT: OK`。零记录、目录缺失都会出 `WARN`，别忽略它们——它们是「校验没真的跑」的唯一信号
- **脱敏失败用专门的退出码 `5`**：它和「格式写错」不是一回事，混在一起会让人以为改改缩进就好
- **枚举只认 `reference/`**：不要在脚本里再抄一份列表，两处真源必然漂移
- **`verified: false` 不算错误**：那是待复核状态，不是坏数据。复核由人做，校验器不替人拍板
