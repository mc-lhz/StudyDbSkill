# 接口契约（只读）

## 通用

- 网关：`https://hfs-be.yunxiao.com`
- 请求头：`deviceType: 3`；登录后所有请求带 `hfs-token: <data.token>`。
- 请求体：`Content-Type: application/json`，UTF-8。
- 统一信封：`{"code":0,"msg":"...","data":...}`；`code != 0` 即失败。
  少数端点用 `{"meta":{"code":...},"data":...}`，传输层两种都识别。
- 本文件只记录已实测的读接口。

## 1. 登录

```
POST /v2/users/sessions
```

```json
{
  "loginName": "<账号>",
  "password": "<密码的 Base64>",
  "roleType": 2,
  "loginType": 1,
  "rememberMe": 2
}
```

`data` 关键字段：`token`、`userId`、`studentId`、`roleType`、`needUpdatePassword`。
后续请求使用 `data.token`，不是 `fdToken`。

## 2. 绑定学生

```
GET /v2/user-center/related-students
```

`data` 是**数组**，元素字段：

| 字段 | 说明 |
|---|---|
| `studentId` | 切换学生用的 id |
| `studentName` | 姓名 |
| `grade` / `class` | 年级 / 班级 |
| `schoolName` / `schoolId` | 学校 |
| `xuehao` / `kaohao` | 学号 / 考号 |
| `linkedTime` / `changeBindTime` | 绑定时间（毫秒） |
| `isVirtual` | 虚拟学生标记 |

同名学生会以多条记录出现，必须用 `studentId` 区分。

## 3. 切换学生

```
POST /v2/user-center/sessions
{"studentId":"<id>","deviceType":"3"}
```

成功后 `data` 至少含 `studentId`；之后考试接口按该学生返回。

## 4. 考试列表

```
GET /v3/exam/list?start=0&limit=10
```

`data`：

| 字段 | 说明 |
|---|---|
| `list` | 考试数组，按时间倒序 |
| `totalCount` | 总场次 |
| `isStrongBaseSchool` | 学校标记 |
| `limitTip` | 次数限制提示（可能为空） |

`list[]` 关键字段：`examId`、`name`、`time`（毫秒）、`score`、`manfen`、
`classRank`/`gradeRank`（隐藏时为 `-1`，字符串版为 `**`）、`className`。

## 5. 考试元数据

```
GET /v3/exam/{examId}/overview
```

`data` 主要字段：

| 字段 | 说明 |
|---|---|
| `examId` / `name` / `time` / `type` / `mode` | 基本信息 |
| `score` / `manfen` | 总分 / 满分 |
| `classRank` / `gradeRank` / `groupRank` | 排名，隐藏为 `-1` |
| `classStuNum` / `gradeStuNum` | 参考人数 |
| `papers` | 科目数组 |

`papers[]`：

| 字段 | 说明 |
|---|---|
| `paperId` | 形如 `<id>-<schoolId>` |
| `pid` | 32 位十六进制，图片接口必传 |
| `name` / `subject` | 科目全名 / 简称 |
| `score` / `manfen` | 得分 / 满分 |
| `type` / `selectType` / `gradingType` | 科目类型标记 |
| `hasTeacherComment` / `comment` | 教师评语可用性 |

## 6. 原卷图片

```
GET /v3/exam/{examId}/papers/{paperId}/paper-picture?pid={pid}
```

`data` 是图片 URL 数组（JPG），按页顺序排列。学校未上传时 `data` 为空。

> 不要走 `/v2/online-exams/token` + 独立阅卷网关：那是**在线作业/测验**的原卷链路，
> 正式考试不在其中，会返回 `code:10402 获取阅卷token失败`。

## 7. 答题卡图片与批注

```
GET /v3/exam/{examId}/papers/{paperId}/answer-picture?pid={pid}
```

`data`：

| 字段 | 说明 |
|---|---|
| `url` | 答题卡页面 PNG（原尺寸） |
| `urlResize` | 缩略图（带 `x-bce-process=image/resize`） |
| `questions` | 题目批注数组 |
| `score` | 本卷得分 |
| `isScoreConvert` / `isShuangPing` / `isExam2` | 计分与渲染标记 |

`questions[]` 关键字段：

| 字段 | 说明 |
|---|---|
| `id` / `type` | 题号 / 题型（2 为客观题） |
| `score` / `manfen` | 得分 / 满分；`-100` 表示未作答 |
| `isRateLow` | 低得分率标记 |
| `answerOption[]` | 客观题每个选项的 `index`、`right`、`x/y/w/h` |
| `url[]` | 主观题区域链接，`@` 后含 `cox_/coy_/w_/h_` 坐标 |
| `remark2[]` | 教师批注（`i` 对应 `url` 页序，`x/y` 为相对偏移） |

`url` 中坐标的解析方式：URL 解码后取 `@` 之后、`|` 之前的内容，按 `,` 分段，
再按 `_` 拆成 `cox/coy/w/h`。

## 8. 错误与限制

| 现象 | 原因 |
|---|---|
| `code:10402 获取阅卷token失败` | 用了在线作业链路，或该考试没有在线作业 |
| `data.url` 为空 | 学校未上传答题卡，或该科未扫描 |
| 排名为 `-1` / `**` | 学校关闭排名展示 |
| 题目详情只有 1 题 | 非会员被服务端截断（`show:0`），本工具不使用 |

图片链接带签名与有效期（约 7 天），过期后重新调用接口获取。

## 9. 只读边界

已封装：登录、学生列表/切换、考试列表、overview、原卷/答题卡。
未封装：提交、修改、删除、教师端、他人数据、题目详情。
