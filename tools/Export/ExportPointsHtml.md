# ExportPointsHtml.py

## 职责

把知识点卡**渲染成一个单文件 HTML**，手机上翻、复习前扫一眼用。

只读，不改数据仓任何文件；生成物随时可删可重建。

## 对应数据

`<数据根>/data/subjects/生物/points/**/KP-*.md` —— **递归**扫子目录
（实际结构是 `points/神经调节/`、`points/体液调节/`、`points/内环境与稳态/`）。
front-matter 取 `id` / `title` / `kind` / `chapter` / `point`，正文转 HTML。

只收文件名以 `KP-` 开头的 `.md`：`points/` 里若混进别的笔记，不该被当成卡片。

## 方法清单

| 方法 | 作用 |
|---|---|
| `resolve_points_dir` | `BIOVAULT_HOME` > `config.json dataRoot`，失败退出 `6`；再拼出 `points/` |
| `parse_front_matter` | 手写 YAML 子集解析；**先剥 UTF-8 BOM** |
| `inline` | 行内 `**粗体**` / `` `代码` `` |
| `md_to_html` | 正文块级渲染：标题、列表、表格、引用；**跨行 `**加粗**` 也能配对** |
| `join_lines` | 把同一段落的多行折成一行（Markdown 软换行） |
| `render_table` | `\|` 表格转 `<table>` |
| `main` | 收集卡片 → 统计 chapter/kind → 注入筛选条 → 写文件 |

## 最小用法

```
python tools/Export/ExportPointsHtml.py                       # 写到 DEFAULT_OUT
python tools/Export/ExportPointsHtml.py D:\cards.html         # 指定输出
```

输出形如 `wrote <path> (<n> cards, <bytes> bytes)`。

## 页面能力

- 双筛选条：章 / 类型，可叠加；`重置` 清空
- 搜索框：匹配标题与正文
- 计数条实时显示当前命中数
- **零依赖**：没有 CDN、没有构建步骤，双击就能看，断网也能用

## 注意事项

- **必须递归**：卡在章子目录里；只扫一层会生成一个「0 张卡」的空页面，看着像还没有知识点。0 张时脚本会往 stderr 打 `WARNING`
- **生成物不要手改**：下次导出会被覆盖；要改内容改 `points/*.md`
- **`DEFAULT_OUT` 是写死的 `D:\...`**：换机器时传参覆盖，别去改脚本
- 文件名里仍带旧项目名 `bio-error-vault`，只是输出文件名，与数据无关
- 卡片数为 0 时会生成一个空页而不是报错——先确认 `points/` 是否真的为空
- 改本文件后重跑 `python tools/Export/ExportPointsHtml.py` 并目视检查筛选与搜索
