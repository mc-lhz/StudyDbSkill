# Auth（登录与切换）

## `login(username, password)`

- 密码做 Base64 后提交 `POST /v2/users/sessions`；**按原样编码，不 strip、不忽略点号**（含首尾点与空格）。
- 固定 `roleType=2, loginType=1, rememberMe=2`。
- 成功后把 `data.token` 写入 `self.token`，并保存 `login_info`。
- 缺账号/密码抛 `UsageError`；响应无 token 抛 `BestGradeError`。

## `switch_student(student)`

- 接受学生字典或 `studentId` 字符串。
- `POST /v2/user-center/sessions`，body `{studentId, deviceType:"3"}`。
- 保存 `self.student` 与 `self.student_id`。

## `ensure_token()`

未登录时抛 `BestGradeError`，供后续接口调用前自检。

## 凭据策略

只存在进程内存；不读环境变量、不写配置文件、不缓存 token。
