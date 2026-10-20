# HttpTransport（传输层）

`Http` 负责所有网络 IO：JSON 请求、信封校验、鉴权头、图片下载。

## 方法

| 方法 | 说明 |
|---|---|
| `get_json(path, params=None, auth=True)` | GET 并返回 `data` |
| `post_json(path, body, params=None, auth=True)` | POST JSON 并返回 `data` |
| `request(method, path, body, params, auth)` | 底层方法 |
| `download(url, dest)` | 下载图片，返回 `(path, bytes, kind)` |

## 行为

- 自动拼 `deviceType`、`User-Agent`；有 token 时加 `hfs-token`。
- 识别两种信封：顶层 `code` 与 `meta.code`；非 0 抛 `BestGradeError`，保留 `msg`。
- HTTP 错误先尝试解析响应体里的 `msg`，再退回 `HTTP <code>`。
- 图片下载校验 PNG/JPEG magic，不是图片就报“链接可能已过期”，不会把 HTML 存成 PNG。
- 写文件用临时文件 + `os.replace`，避免半截文件。

## 安全

不打印请求头、token、密码；错误信息只含接口 `msg` 或网络原因。
