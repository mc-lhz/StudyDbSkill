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

`<数据根>/data/subjects/生物/points/<章>/KP-*.md` —— 按 front-matter 的 `id` 定位
（缺失时回落到文件名），递归扫描子目录。**只写这一个目录。**

schema 1.13 起没有 `errors/` 了：复习状态（`status` / `review_count` /
`last_review` / `next_review`）挂在知识点卡自己身上。一张卡可能挂多条错题证据，
但**复习状态是整卡共享的**——你复习的是这个知识点，不是那一道题。

## 方法清单

| 方法 | 作用 |
|---|---|
| `plan` | 纯函数，算 `(updates, 说明)`，不碰文件——测试直接驱动它 |
| `patch_front_matter` | 逐行替换指定 key，其余原样 |
| `read_text` / `write_text` | 记住并还原换行风格，避免整文件 diff |
| `apply_one` | 写 → **回读校验** → 不一致就抛 |
| `index_records` | 递归扫 `points/<章>/`，`id → (path, meta)` |
| `detect_cause` | 错因不在 front-matter，从 `## 错题证据` 的「错因：」行读取；多块时 会但粗心 优先 |

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
- **错因从证据块读**：卡里没有 `cause` 字段时，`会但粗心` 守卫靠 `## 错题证据` 里的「错因：」行生效；把那一行删了，守卫就静默失效
- 与 `Queue.py` 的分工：`Queue.py` 只读、永不写；`Mark.py` 只写、不排序
- 测试见 `tools/TestCases/TestMark.py`，含 3 条反向用例 + 变异测试验证过会红
