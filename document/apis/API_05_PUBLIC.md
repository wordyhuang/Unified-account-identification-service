> **文档创建时间**: 2026-11-25 17:50:00
> **最后修改时间**: 2026-11-25 23:45:00
> **当前版本**: V_1.1
> **适用对象**: 对接本服务的 AI Agent、H5 注册页开发者、接入方前端开发
> **核心目标**: 提供 `/api/v1/public/*` 公开接口（邀请码自助注册、资料补全码）的完整定义
> **文档简略描述**: V_1.1 新增邀请注册页品牌、可配置字段与文案下发，注册响应返回成功页跳转地址；补充接入方自建注册页的跨域与短链重定向说明

---

# 公开 API 子文档 `/api/v1/public/`

> AI 对接前请先读本文件。

## 大纲

- [1. 认证与安全](#1-认证与安全)
- [2. 邀请码接口](#2-邀请码接口)
- [3. 资料补全码接口](#3-资料补全码接口)
- [4. 页面与短链](#4-页面与短链)
- [5. 错误码](#5-错误码)
- [6. 文档版本与变更记录](#6-文档版本与变更记录)

---

## 1. 认证与安全

- 全部接口**无需登录**；凭证为 32 位随机码本身（不可预测），受 IP 限流保护。
- 码校验三重控制：`status`（启用/停用）、`expires_at`（有效期）、`max_uses/used_count`（次数上限）。
- 多人通用补全会话凭证 `session_token` 仅存服务端缓存（10 分钟 TTL），非 JWT。
- 管理端创建码时即返回 `page_url` / `short_url`（域名取创建请求）。
- **跨域（V_1.1）**：接入方自建注册页可在浏览器直连本组接口。放行 origin 来自启用应用的「回调地址白名单 + 注册页地址 + 成功页地址」，进程内缓存 60 秒；未配置的 origin 预检返回 403。

---

## 2. 邀请码接口

### 2.1 邀请码信息 `GET /api/v1/public/invite/<code>`

**出参** `data`:

```json
{
  "require_phone": true,
  "user_type": "external",
  "expires_at": "2026-12-31T23:59:59",
  "remaining_uses": 9,
  "brand": {
    "name": "演示企业",
    "welcome": "欢迎加入演示企业",
    "theme_color": "#0F766E",
    "logo": ""
  },
  "fields": [
    { "key": "username", "label": "用户名", "type": "text", "required": true, "fixed": true },
    { "key": "password", "label": "密码", "type": "password", "required": true, "fixed": true },
    { "key": "real_name", "label": "真实姓名", "type": "text", "required": true },
    { "key": "gender", "label": "性别", "type": "select", "required": false,
      "options": [{ "value": "male", "label": "男" }, { "value": "female", "label": "女" }] }
  ],
  "texts": { "submit": "立即加入", "success": "", "agreement": "我已阅读并同意服务协议" },
  "app": { "name": "某某业务系统" }
}
```

说明：

| 字段 | 说明 |
|---|---|
| `require_phone` | 该码配置了手机白名单，注册手机号必须命中 |
| `brand` | 租户级品牌；`name` 未配置时回退租户名称 |
| `fields` | **有效注册字段**（邀请码覆盖 > 租户默认 > 系统默认）：`username/password` 恒在前且 `fixed=true`；启用白名单时 `phone` 强制 `required=true` |
| `fields[].type` | `text` / `password` / `textarea` / `select`（含 `options`）/ `date` |
| `texts.submit` | 注册按钮文案，空值回退「注册账号」 |
| `texts.success` | 成功提示，空值使用默认文案，支持 `{username}` 占位 |
| `texts.agreement` | 协议勾选文案，空则不显示勾选 |
| `app` | 绑定接入应用时返回应用名；内置页模式不返回 |

### 2.2 邀请注册 `POST /api/v1/public/invite/<code>/register`

**入参**：按 2.1 返回的 `fields` 提交，键名与 `fields[].key` 一致：

```json
{
  "username": "zhangsan",
  "password": "******",
  "real_name": "张三",
  "gender": "male"
}
```

规则：

- `username`/`password` 必填，密码 ≥ 6 位。
- **字段白名单（V_1.1）**：提交未配置的字段返回 400 / -10602，`message` 形如「不允许提交的字段: email」。
- **必填校验（V_1.1）**：缺少必填项返回 400 / -10602，`message` 形如「缺少必填项: 真实姓名」。
- `select` 取值必须在 `options[].value` 内；`date` 格式为 `YYYY-MM-DD`，否则 400。
- 配置白名单时 `phone` 必须命中，否则 403 / -10704。
- 用户名、手机号、邮箱在租户内唯一，冲突返回 400。
- 采集到的字段按归属分流：`User` 字段（昵称/邮箱/头像/手机号）写用户，资料字段（真实姓名/工号/生日等）写 `UserProfile`。
- 成功后 `used_count+1`，达 `max_uses` 自动停用。
- **防刷频控**：
  - 单 IP 每分钟最多 3 次注册**尝试**（含失败，先于码校验计数），超出返回 429 / -10401；
  - 单个邀请码每日最多 20 次**成功**注册（按码隔离），超出返回 429 / -10401；
  - 均可通过环境变量调整：`INVITE_REGISTER_IP_LIMIT_PER_MINUTE`（默认 3）、`INVITE_REGISTER_CODE_DAILY_LIMIT`（默认 20）。

**出参** `data`:

```json
{
  "user_id": 1,
  "username": "zhangsan",
  "redirect_url": "https://biz.example.com/registered?user_id=1&username=zhangsan&ts=1765000000&sign=..."
}
```

- `redirect_url`：仅当邀请码绑定应用且应用配置了「注册成功跳转地址」时返回（同源校验通过才拼接），否则为 `null`。
- 绑定应用且配置了 Webhook 时，服务端会异步投递 `invite.registered` 事件（见接入手册）。

---

## 3. 资料补全码接口

### 3.1 补全码信息 `GET /api/v1/public/profile-completion/<code>`

**出参** `data`（单人模式 single）:

```json
{
  "mode": "single",
  "username": "zhangsan",
  "allow_repeated": false,
  "fields": [ { "name": "real_name", "label": "真实姓名", "type": "text" } ],
  "prefill": { "real_name": null },
  "expires_at": "2026-12-31T23:59:59"
}
```

**出参** `data`（多人通用模式 shared）: 不返回 `prefill`/`allow_repeated`/`username`（须先验证身份）。

- `fields[].type`: `text` / `date` / `select`（含 `options`）/ `textarea`。

### 3.2 发送身份验证码 `POST /api/v1/public/profile-completion/<code>/verify`（仅 shared）

**入参**: `{ "phone": "13800001111" }`

- 必须是本租户内已绑定该手机号的启用用户，否则 404。
- 复用租户短信渠道发送，频控与普通短信一致。

### 3.3 验证码校验签发会话 `POST /api/v1/public/profile-completion/<code>/login`（仅 shared）

**入参**: `{ "phone": "13800001111", "sms_code": "123456" }`

**出参** `data`:

```json
{
  "session_token": "urlsafe-random-token",
  "expires_in": 600,
  "fields": [ ... ],
  "prefill": { ... }
}
```

### 3.4 提交资料补全 `PUT /api/v1/public/profile-completion/<code>/submit`

- **single**：码本身即凭证，直接提交。
- **shared**：必须携带请求头 `X-Completion-Token: <session_token>`，缺失/无效返回 401 / -10705。

**入参**: 仅允许 `fields` 白名单内的字段，例如：

```json
{ "real_name": "张三", "birthday": "1995-01-01", "bio": "..." }
```

- 含未知字段时 400 / -10602。
- single 且 `allow_repeated=false`：提交一次后码自动停用。
- shared：每次提交 `used_count+1`，达 `max_uses` 自动停用，并销毁本次会话。

**出参** `data`: `{ "user_id": 1 }`

---

## 4. 页面与短链

| 路径 | 说明 |
| --- | --- |
| `/invite/<code>` | 邀请注册页：邀请码**未绑定应用**时渲染 UAIS 内置页；**绑定应用**时 302 跳转到接入方注册页 |
| `/profile-completion/<code>` | 资料补全页（single 直填；shared 手机号 → 3.2 → 3.3 → 3.4） |
| `/s/<short_code>` | 短链：命中邀请码且绑定应用 → 302 到接入方注册页；未绑定 → 302 到 `/invite/<code>`；命中补全码 → 302 到补全页；无效返回 404 |

**接入方注册页跳转参数（V_1.1）**：

```
302 → {registration_page_url}?code={code}&ts={unix_ts}&sign={hmac}
```

- `sign = HMAC_SHA256(app_secret, "{code}.{ts}")` 取前 32 位十六进制，建议接入方校验 5 分钟时效。
- 签名仅用于来源风控，邀请码本身才是唯一凭证。
- 应用未配置注册页地址或地址校验不通过（非同源/内网）时，自动回退渲染内置页。

---

## 5. 错误码

| code  | 含义                        | HTTP |
| ----- | ------------------------- | ---- |
| -10701 | 码无效或已停用                   | 400  |
| -10702 | 码已过期                      | 400  |
| -10703 | 使用次数已达上限                  | 400  |
| -10704 | 手机号不在邀请码白名单内              | 403  |
| -10705 | 补全会话无效或已过期                | 401  |
| -10401 | 请求过于频繁（注册防刷限流）        | 429  |
| -10602 | 参数不合法 / 未配置字段 / 缺少必填项    | 400  |
| -10601 | 缺少必填参数                    | 400  |
| -10101 | 用户不存在（手机号未匹配本企业用户）        | 404  |

---

## 6. 文档版本与变更记录

| 版本    | 日期         | 变更说明             |
| ----- | ---------- | ---------------- |
| V_1.1 | 2026-11-25 | 邀请信息新增 `brand / fields / texts / app`；注册接口按配置校验字段并返回 `redirect_url`；短链支持 302 到接入方注册页（含 `code/ts/sign`）；补充跨域放行规则 |
| V_1.0 | 2026-11-25 | 首版：邀请码自助注册、资料补全码（单人/多人通用、allow_repeated 可重复配置）、短链与页面路由 |
