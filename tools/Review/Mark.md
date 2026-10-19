# Mark.py

## 职责

记录一次复习结果，推进或**重置**该错题的复习计划。

`Queue.py` 回答「今天该复习谁」；`Mark.py` 才是让队列**真的缩小**的那个。
没有它，`next_review` 永不移动，队列就是一台跑步机。

## 状态机（2026-10-19 用户裁定）

```
     新错 ──对──> 已订正 ──对──> 已复现 ──对──> 已掌握（退队列）
       ↑        ↑         ↑          │
       └────────┴─────────┴──────────┘   做错：一律降到 新错
```

| 动作 | status | review_count | next_review |
|---|---|---|---|
| 做对第 1 次 | `已订正` | `1` | 今天 +1 天 |
| 做对第 2 次 | `已复现` | `2` | 今天 +3 天 |
| 做对第 3 次 | `已掌握` | `3` | 今天 +7 天 |
| **做错** | `新错` | `0` | 今天 +1 天 |

`AGENTS.md` 的 `1→3→7→15→30` 仍成立，只是本模型 3 次即毕业，
15 / 30 留给「已掌握后再次复习」的场景。

## ⚠️ `会但粗心` 守卫独立于阶梯

`AGENTS.md`：`会但粗心` 不允许一次过 `已掌握`，强制至少两次间隔。
这条**不能**靠「阶梯恰好是 3 次」来满足——那是巧合，不是约束。
所以 `MIN_INTERVALS = {"会但粗心": 2}` 是一道**独立守卫**：
就算有人把 `GRADUATE_COUNT` 改成 1，它照样拦得住。

测试 `test_careless_guard_survives_ladder_shortening` 专门证明这一点。

## 安全护栏

- **写操作必须 `--yes`**；不给就只预览，退出码 `5`，**文件逐字节不变**
- **只改 4 个字段**（`status` / `review_count` / `last_review` / `next_review`），
  逐行替换，**不重新序列化**——front-matter 顺序、注释、正文、CRLF 全部原样保留
- **回读校验**：写完重新读、重新解析，字段对不上就报错，**不以「没抛异常」为成功**
- **`verified: false` 默认拒绝**：复习一条从未复核的记录 = 在背未经确认的内容，
  正是硬闸门要拦的事。要强来用 `--force`
- 批量执行时**一条失败不阻断其余**，但退出码会如实反映有失败

## 对应数据

`<数据根>/data/subjects/生物/errors/*.md` —— 按 front-matter 的 `id` 定位
（缺失时回落到文件名）。**只写这一个目录。**

## 方法清单

| 方法 | 作用 |
|---|---|
| `plan` | 纯函数，算 `(updates, 说明)`，不碰文件——测试直接驱动它 |
| `patch_front_matter` | 逐行替换指定 key，其余原样 |
| `read_text` / `write_text` | 记住并还原换行风格，避免整文件 diff |
| `apply_one` | 写 → **回读校验** → 不一致就抛 |
| `index_records` | `id → (path, meta)` |

## 最小用法

```
# 预览（不写）
python tools/Review/Mark.py BIO-20261016-008 --result right

# 真的写
python tools/Review/Mark.py BIO-20261016-008 --result right --yes

# 复习做错
python tools/Review/Mark.py BIO-20261016-008 --result wrong --yes

# 一次记一批（一次复习做一批题）
python tools/Review/Mark.py BIO-20261016-008 BIO-20261016-009 --result right --yes

# 补录旧日期 / 强来未复核的记录 / 机器可读
python tools/Review/Mark.py <id> --result right --date 2026-10-15 --yes
python tools/Review/Mark.py <id> --result right --force --yes
python tools/Review/Mark.py <id> --result right --yes --json
```

## 退出码

| 码 | 含义 |
|---|---|
| `0` | 全部成功 |
| `2` | 参数错 / id 不存在 / 记录未复核（缺 `--force`）/ 回读校验失败 |
| `5` | 缺 `--yes`（只预览，未写入） |
| `6` | 数据根不可解析 |

## 注意事项

- **写完一定要回读校验**：本工具改的是你的学习数据，静默写歪比报错糟得多
- **不要因为想清空队列就狂点 `--result right`**：那等于自欺，间隔重复的前提是结果真实
- 与 `Queue.py` 的分工：`Queue.py` 只读、永不写；`Mark.py` 只写、不排序
- 测试见 `tools/TestCases/TestMark.py`，含 3 条反向用例 + 变异测试验证过会红
