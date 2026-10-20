# Config（常量与异常）

## 常量

| 名称 | 值/作用 |
|---|---|
| `BASE_URL` | `https://hfs-be.yunxiao.com` |
| `DEVICE_TYPE` | `"3"`，所有请求必带 |
| `TIMEOUT` | 默认 20 秒 |
| `TOKEN_HEADER` | `hfs-token` |
| `DEFAULT_LIMIT` | 考试列表默认 10 场 |
| `OUTPUT_ROOT` | `%TEMP%\BestGrade` |
| `USER_AGENT` | 固定桌面 UA |

## 异常

- `BestGradeError`：默认 `exitCode = 3`，可带 `code`（接口码）与 `status`（HTTP 码）。
- `UsageError`：`exitCode = 2`，用于参数缺失、选择歧义。

## 工具函数

- `outputRoot()`：返回输出根目录。
- `safeName(value, fallback)`：把考试名/科目名收敛为安全目录名（去非法字符、截 60 字符）。
- `maskAccount(name)`：账号脱敏，日志/报错用。

模块只依赖标准库，不导入其他业务模块，避免循环依赖。
