# AGENTS.md

生物错题仓（BioErrorVault）开发契约。**动手前必读，改动前先看这份。**

## 架构：三层分离 + 双仓

```
工具层  tools/BioErrorVault.py 门面  数据根解析 · schema 读写 · 枚举校验
           ↓
真源层  data/exams/  errors/  points/  assets/     ← git 逐行追踪 diff，人和 AI 只改这里
           ↓ RebuildIndexes.py 全量重建
派生层  data/indexes/  point-map · weak-spots · orphan-points · queue · glossary
```

- **真源层**：手工与 AI 写入，git 逐行追踪 diff
- **派生层**：脚本生成，可随时全量重建。**禁止手工编辑**——改了状态就漂移，
  重建时静默丢失，而且 git diff 会被淹掉
- **工具层**：无状态，可分发

### 双仓

| 仓 | 路径 | git | 能否开源 |
|---|---|---|---|
| 工具仓 | `~/.config/opencode/skills/bio-error-vault/` | 可设 remote | 可（打包排除 `data/`） |
| 数据仓 | `~/Documents/bio-error-data/` | **禁止设 remote** | **绝不可** |

**数据仓禁止 `git remote add`。** 错题含学校名、手写姓名、考号、含水印的卷子照片，
推到公开仓即使后来删文件，**git 历史里仍找得回来**。这不是道德说教，是 git 的物理特性。

两仓关联：数据根解析优先级 `BIOVAULT_HOME` 环境变量 > `config.json` 的 `dataRoot` > **报错退出码 6**。
**解析失败绝不静默回落到 `examples/`。**

---

## 目录与命名

```
tools/
  BioErrorVault/         门面：数据根解析 · schema 读写 · 枚举校验
  Exams/                 RegisterExam.py
  Errors/                AddError.py  Confirm.py  ListErrors.py
  Points/                AddPoint.py  LinkError.py  ListPoints.py
  Capture/               FromPhoto.py       拍图 → 草稿（不直接落库）
  Assets/                AttachImage.py      图片归档 · 命名 · 相对路径
  Rebuild/               RebuildIndexes.py   唯一派生生成器
  Review/                Queue.py  Mark.py
  Stats/                 Weakness.py  Health.py
  TestCases/             TestContract.py  TestSchema.py
  Release/               PackSkill.py
reference/               taxonomy.md · causes.md · kinds.md   ← 三份枚举真源
examples/                虚构夹具
```

- **目录大驼峰**（`ErrorVault/`），**模块文件大驼峰**（`AddError.py`），
  类大驼峰，方法小驼峰，常量 UPPER_SNAKE。禁下划线与短横线做目录/模块名
- **文件名不得重复所在目录名**（不要 `Errors/Errors.py`）
- **⚠️ 任何目录名与模块文件名都不得与标准库同名**，不只是目录。
  Python 跑 `python tools/Errors/AddError.py` 时 `tools/Errors/` 会进 `sys.path[0]`，
  里面的 `queue.py` / `types.py` / `code.py` / `time.py` 会**遮蔽标准库**并炸掉。
  已确认安全的现有名字：`Exams` `Errors` `Points` `Capture` `Assets` `Rebuild`
  `Review` `Stats` `TestCases` `Release` `BioErrorVault`
- 每业务一目录，每 `.py` 配同名 `.md`（职责 / 对应数据 / 方法清单 / 最小用法 / 注意事项）
- 每个业务目录必须有 `__init__.py`，否则退化成 namespace package
- 新增业务域 = 新目录 + `__init__.py` + 模块 + 同名 `.md` + 门面注册

---

## 数据契约

### 错题 24 字段 / 知识点 11 字段

schema 见 `SKILL.md`。**改动 schema 必须三处同步**：`SKILL.md`、`reference/` 相应真源、
`TestCases/TestSchema.py` 的断言。

### 三份真源，改枚举只改这三份

| 文件 | 内容 | 校验 |
|---|---|---|
| `reference/taxonomy.md` | 教材树 5 章 18 节，**两层封顶** | `chapter` + `point` 必填于错题 |
| `reference/causes.md` | 11 个错因 | `cause` 必填，枚举外 → 退出码 4 |
| `reference/kinds.md` | 8 种知识点类型 | `kind` 必填，枚举外 → 退出码 4 |

**枚举外的值一律拒绝，不允许塞 `other`。** 分类体系从「凑合用 other」开始腐化。
`qtype` 是唯一允许 `其他` 的字段。

### 归属规则

- 错题：`chapter` / `point` **必填**（不归位则统计失去意义）
- 知识点：`chapter` / `point` **可选**，但**不绑时 `tags` 必填 ≥1**，
  否则计入「无归属知识点」，`Health.py` 告警
  ——**兜底规则必须存在**，否则「可绑可不绑」会退化成「谁也不绑」

### 状态机

```
新错 ──订正──> 已订正 ──隔天重做对──> 已复现 ──隔周再做对──> 已掌握（退队列）
                    ↑                        │
                    └──── 重做错 ────────────┘  间隔重置 1 天，状态降级
```

间隔重复：**`1 → 3 → 7 → 15 → 30` 天**。不做 SM-2，高中生版本够用。

**`会但粗心` 类错题不允许一次过 `已掌握`**，强制至少两次间隔。
这是唯一「靠多刷能改、但不做专门训练就复发」且最易误判成「我会了」的错因。

---

## ⚠️ 硬闸门：`verified`

**任何 AI 生成内容（`cause` 判断、正解、知识点草稿、拍图识别）一律 `verified: false`。**
未确认记录**不进统计、不进复习队列**。

理由：生物术语错一个字母（`线粒体基质`→`线粒体基质胶`）、过程阶段记错，
照着背就是学错东西，**比不学更糟**。

`Health.py` 在未确认记录 >20 条时告警。
**不要为了让统计好看而批量刷 `verified: true`——闸门一松，统计全部失效。**

---

## 写操作契约

### 退出码（统一，每个 CLI 一致，让 skill 能可靠分支）

| 码 | 含义 |
|---|---|
| `0` | 成功 |
| `2` | 参数错 |
| `3` | id 冲突 |
| `4` | 枚举校验失败（taxonomy / causes / kinds） |
| `5` | 需显式确认的写操作（缺 `--yes`） |
| `6` | 数据根不存在 |

**失败绝不当成功。** 写操作后必须回读校验，不以「没抛异常」为成功判据。

### 确认与预览

- 写操作必须显式 `--yes`（代表已确认）
- 只读预览用 `--dry-run`（连图片都不落盘）
- 删除类操作默认 `--dry-run` 先看目标，再显式 `--yes`；**删除不可撤销**

### 日志分工

给用户和 AI 看的结论一律 `print` 走 **stdout**；
内部诊断走 **stderr** + verbose 环境变量 `BIOVAULT_VERBOSE=1` 或 `--verbose`。
两者混流会让 skill 解析失败。

---

## 平台陷阱（Windows + PowerShell 5.1）

以下每一条都是**踩过的坑**，不要重新踩：

- **PowerShell 5.1 不要用 `Get-Content` / `Set-Content` 处理 UTF-8 中文**——会乱码。
  用文件工具或 python。本仓库全是中文，改动一律走 `write` / `edit` 工具或 python
- **控制台是 GBK 码页**，`Get-ChildItem` 输出的中文目录名显示成 `????`，
  **那是显示问题不是文件问题**。验证真实名字用 python 的 `os.walk`（配 `PYTHONIOENCODING=utf-8`）
- **⚠️ argparse 的 help 字符串里不能留裸 `%`**：`--help` 会对 help 再做一次 `%` 格式化，
  ``ValueError: unsupported format character 'T'`` 就是这么来的。
  ``"默认 %%TEMP%%\\%s" % NAME`` 这种「先 %% 转义再 % 代入」的写法也不行——
  `%` 运算后仍会留下裸 `%`。**help 文案里索性别用 `%`**
- **⚠️ 改这些文件不要用 PowerShell here-string**：`@"..."@` 里写反引号，
  反引号被当转义符吃掉，代码标记损坏、`\t` 被解释成 TAB。要批量改就写补丁脚本文件再执行
- **git 大小写**：仓库设 `core.ignorecase=false`；仅改大小写必须 `git rm --cached` + `git add` 两步。
  Windows 文件系统大小写不敏感，`git mv A a` 可能「假成功」，
  **必须走临时名两段式**（`git mv A A__tmp && git mv A__tmp a`），改完用 `git ls-files` 复核。
  ⚠️ Windows 上 Python 导入也不敏感，改错大小写测试仍可能全绿——
  改名后必须按 `git ls-files` 跑一次大小写审计，别只信测试结果
- 禁止用正则批量替换文件名或字段名——会误伤 API 路径与字段名；逐条精确替换 + 断言内容完好

---

## 测试

- `TestCases/TestContract.py` —— 仓库契约与卫生审计（**离线、无网络、无凭据**）
- `TestCases/TestSchema.py` —— schema 校验与枚举约束
- **每加一条红线，必须配一条能证明它会红的反向用例**——
  恒 PASS 的检查是装饰品，只说明它对当前这版代码成立。
  反向用例**不得真删**：只 monkeypatch 或改临时副本，`finally` 还原
- 测试用 `examples/` 的**虚构夹具**，不用真实错题

---

## 健康指标（`Stats/Health.py` 的自检）

| 指标 | 健康值 | 超标含义 |
|---|---|---|
| 孤儿知识点占比 | <30% | 知识库在空转，该删或该练 |
| 单 KP 被引用次数 | 3-8 次 | >10 该变主攻；=0 该删或该练 |
| 无归属知识点数 | 0 | tags 兜底规则被绕过 |
| 错因分布 | 无单一因 >50% | 学习方式要调，不是难度问题 |
| 录入/复习比 | ≥1:3 | 录得多练得少 = 又一个笔记本 |
| `verified: false` 积压 | <20 条 | AI 生成内容在堆积污染 |

**录入/复习比**是这套系统的生死线。错题本的最大死法是「录得很勤，复习很少」，
最后变成第二本翻不动的笔记本。

---

## RAG 上线判据

暂不做。判据写死，避免以后凭感觉加依赖：

- 知识点 <300 条 → 不上
- **`git grep` 连续两周真的没找到想要的东西** → 上
  （核心判据是**失败体验**，不是条目数，数量只是代理指标）
- 出现「我想找和『明明会却算错』类似的东西」→ `cause` 标签失效，上

引入知识点后模糊检索需求会明显上升（自由文本 + tag 语义），
但结构化过滤 + git grep 仍能覆盖绝大部分场景。先做结构化，不是妥协。

---

## 版本与发布

- **版本号唯一落点是仓库根 `VERSION`**，与 release tag 逐字一致（含 `v` 前缀）
- **禁止在 README / SKILL / 代码注释里手写版本号**——多处必然漂移，文档只说「见 VERSION」
- 命名：beta 期 `v0.1.0-beta.N`（点分，semver 预发布标识符；**不要写成 `betaN`**，`beta.2` 与 `beta.10` 才排得对），功能冻结后转 `v0.1.0`，破坏性改动才升 minor
- **打包必须排除 `data/`**（用 `git ls-files` 取源，额外排除 `.github/`、`.gitignore`、`data/`）
- 发版前必跑：`compileall` + `TestContract.py` + `TestSchema.py`

---

## 依赖

**只用标准库。** 本项目不引入 pandas / numpy / openpyxl / PyYAML——

schema 解析用标准库 `re` + 手写 YAML frontmatter 读写（格式受控，够用）；
xlsx 导出若需要，用 `zipfile` + SpreadsheetML（沿用 591iqAutomatic 的 `XlsxWriter` 思路）。

理由：保持「装上 Python 就能跑」。高中生环境装依赖是失败率最高的环节。

---

## ⚠️ 最重要的提醒

这套系统的价值在于「复习时真的会打开它」。
哪天觉得维护它比直接翻卷子还累，一定是 schema 太重或录入太慢——
**砍工具，不砍复习。** 沉没成本是最大的陷阱。