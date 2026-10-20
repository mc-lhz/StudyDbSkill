# Auth（登录与身份上下文）

**什么凭据都不落盘。** 密码只在 `login` 那一次的命令行里存在；
token 由 CLI 打印到标准输出，后续命令用 `--token` 传入。

## `login(username, password)`

- 密码做 Base64 后提交 `POST /v2/users/sessions`；**按原样编码，不 strip、不忽略点号**（含首尾点与空格）。
- 固定 `roleType=2, loginType=1, rememberMe=2`。
- 成功后把 `data.token` 写入 `self.token`，`tokenSource="login"`，并保存 `loginInfo`。
- 缺账号/密码抛 `UsageError`；响应无 token 抛 `BestGradeError`。
- **不写任何文件。**

## `useToken(token)`

直接采用外部传入的 token，不发起登录请求，`tokenSource="provided"`。
空 token 抛 `UsageError`（会先 strip 掉复制时带上的换行/空格）。

## `switchStudent(student)`

- 接受学生字典或 `studentId` 字符串。
- `POST /v2/user-center/sessions`，body `{studentId, deviceType:"3"}`。
- 保存 `self.student` 与 `self.studentId`。
- ⚠️ **每次命令都要切换**：复用 token 只省掉登录，不省会话里的学生上下文。

## `isAuthError(exc)`

判断是否是会话失效：HTTP `401/403`，或文案含「登录 / 会话 / 失效 / 过期 / 未授权」。
接口没有文档化的过期码，所以退一步看状态与文案——宁可多登一次，
也不要拿废 token 反复失败。

## 凭据策略

| 凭据 | 去向 |
|---|---|
| 密码 | **只在进程内存**，不写盘、不读环境变量、不缓存 |
| token | 只在进程内存；需要跨命令复用时就由用户/AI 从 `login` 的输出里取 |

早期版本每次命令都重新登录，逐科目取图会产生大量调用，既慢又容易触发风控；
现在拆成「`login` 换 token」+「`--token` 查询」两步，**仍不在磁盘上留任何凭据**。

⚠️ `login` 会把 token 打到标准输出——这意味着它会出现在终端回滚、
对话记录或日志里。这是显式选择的取舍：换掉的是「不落盘」，
不是「不会泄露」，不要在共享机器或会被录屏的环境里用。
