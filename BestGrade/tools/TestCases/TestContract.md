# TestContract（离线契约）

```bash
python tools/TestCases/TestContract.py
```

不需要账号、不联网。覆盖：

| 检查 | 内容 |
|---|---|
| compileall | `tools/` 全量编译 |
| import | 门面与 6 个业务模块可导入 |
| CLI help | 顶层与 `students/images` 子命令 `--help` 正常 |
| py/md 配对 | 每个 `.py` 旁有同名 `.md` |
| 禁词 | 文档/代码零命中（词表以 Base64 存储，避免扫描器自命中） |
| 凭据 | 手机号、密码赋值字面量、`hfs-token` 令牌字面量 |
| 绝对路径 | 不出现本机用户目录 |
| 密码保真 | 密码中的点号与首尾空格按原样编码，不被 strip |
| VERSION | 语义化版本 |
| SKILL | frontmatter `name: BestGrade`、标题、`reference/api.md` |

任一失败退出码 1，并打印文件名与原因。
