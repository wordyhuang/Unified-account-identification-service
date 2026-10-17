> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-10-17 14:10:00
> **当前版本**: V_1.0
> **适用对象**: 对接本服务的 AI Agent、外部应用开发者、C 端 App / H5 开发者
> **核心目标**: 提供 `/api/v1/auth/*` 全部客户端认证接口的完整定义
> **文档简略描述**: 本子文档是主路由 `AI_API_ROUTING_GUIDE_v1.0.md` 的 A 类子文档，覆盖登录、登出、Token 刷新、用户自助资料等接口的入参、出参与错误码。

---

# 认证 API 子文档 `/api/v1/auth/`

> AI 对接前请先读本文件，不要仅凭主路由概览作答。

## 大纲

- [1. 认证方式](#1-认证方式)
- [2. 接口清单](#2-接口清单)
- [3. 通用错误码](#3-通用错误码)
- [4. 文档版本与变更记录](#4-文档版本与变更记录)

---

## 1. 认证方式

| 场景             | 请求方式                                  |
| -------------- | ------------------------------------- |
| 匿名接口（登录/发短信等） | 无需 Header                             |
| 需登录的接口         | `Authorization: Bearer <access_token>` |
| 刷新 Token       | Body 中传 `refresh_token`               |

Token 时效：`access_token` 2 小时；`refresh_token` 30 天。

---

## 2. 接口清单

### 2.1 密码登录 `POST /api/v1/auth/login`

**入参**（JSON Body）:

```json
{
  "username": "user@example.com",
  "password": "your_password"
}
```

**出参** `data`:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 7200,
  "user": { "id": 1, "username": "user@example.com", "nickname": "..." }
}
```

**错误码**: `1001` 账号或密码错误；`1002` 账号被禁用。

---

### 2.2 发送短信验证码 `POST /api/v1/auth/sms/send`

**入参**:

```json
{ "phone": "13800001111", "scene": "login" }
```

`scene` 可选值: `login`、`reset_password`、`bind_phone`。

---

### 2.3 校验短信验证码 `POST /api/v1/auth/sms/verify`

**入参**:

```json
{ "phone": "13800001111", "code": "123456", "scene": "login" }
```

**出参**: 校验通过返回一次性 `sms_token`，用于换取登录态。

---

### 2.4 短信验证码登录 `POST /api/v1/auth/sms/login`

**入参**:

```json
{ "phone": "13800001111", "code": "123456" }
```

**出参**: 同 §2.1。

---

### 2.5 发送改密验证码 `POST /api/v1/auth/sms/send/pwd`

- 需 Access Token
- 入参: `{ "phone": "13800001111" }`

---

### 2.6 社交登录 `POST /api/v1/auth/social/login`

**入参**:

```json
{ "provider": "github|google|...", "code": "oauth_code", "redirect_uri": "..." }
```

---

### 2.7 微信小程序登录 `POST /api/v1/auth/wechat/login`

**入参**:

```json
{
  "app_key": "wx_app_key",
  "code": "wx_js_code",
  "encrypted_data": "...",
  "iv": "..."
}
```

> 若返回 `-10801 微信应用未配置`：说明请求未带 `app_key`，或该应用的 `wechat_mp_app_id` / `wechat_mp_app_secret` 未在管理后台保存成功。

---

### 2.8 刷新 Token `POST /api/v1/auth/token/refresh`

**入参**:

```json
{ "refresh_token": "eyJ..." }
```

**出参**: 同 §2.1，返回一对新的 Token。

---

### 2.9 登出 `POST /api/v1/auth/logout`

- 需 Access Token
- 入参: 无
- 行为: 将当前 `access_token` 加入黑名单直至自然过期。

---

### 2.10 获取当前用户 `GET /api/v1/auth/me` / `PUT /api/v1/auth/me`

- 需 Access Token
- GET 返回当前用户基础信息
- PUT 入参示例: `{ "nickname": "新昵称" }`

---

### 2.11 修改密码 `PATCH /api/v1/auth/me/password`

**入参**:

```json
{ "old_password": "...", "new_password": "..." }
```

---

### 2.12 短信重置密码 `POST /api/v1/auth/me/password/reset`

**入参**:

```json
{ "phone": "13800001111", "code": "123456", "new_password": "..." }
```

---

### 2.13 用户资料 `GET/PUT /api/v1/auth/me/profile`

- 需 Access Token
- 管理扩展字段，例如真实姓名、性别、头像 URL 等。

---

## 3. 通用错误码

| code  | 含义                |
| ----- | ----------------- |
| 0     | 成功                |
| 1001  | 账号或密码错误           |
| 1002  | 账号被禁用             |
| 1003  | 验证码错误 / 已过期       |
| 1004  | Token 失效 / 已过期    |
| 1005  | 频率超限              |
| -10801 | 微信应用未配置           |

---

## 4. 文档版本与变更记录

| 版本    | 日期         | 变更说明             |
| ----- | ---------- | ---------------- |
| V_1.0 | 2026-10-17 | 首版从主路由拆出独立子文档    |
