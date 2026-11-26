> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-11-25 17:45:00
> **当前版本**: V\_1.1
> **适用对象**: 对接本服务的 AI Agent、外部应用开发者、C 端 App / H5 开发者
> **核心目标**: 提供 `/api/v1/auth/*` 全部客户端认证接口的完整定义
> **文档简略描述**: 在 V\_1.0 基础上补充：应用级 `access_token` URL 参数认证要求、登录响应 `must_change_password` 标志、强制改密拦截规则（-10104）与改密清除行为。

***

# 认证 API 子文档 `/api/v1/auth/`

> AI 对接前请先读本文件，不要仅凭主路由概览作答。

## 大纲

- [1. 认证方式](#1-认证方式)
- [2. 接口清单](#2-接口清单)
- [3. 通用错误码](#3-通用错误码)
- [4. 强制改密策略](#4-强制改密策略)
- [5. 文档版本与变更记录](#5-文档版本与变更记录)

***

## 1. 认证方式

| 场景            | 请求方式                                                                         |
| ------------- | ---------------------------------------------------------------------------- |
| 匿名接口（登录/发短信等） | URL 参数 `?access_token=<应用级Token>`（V\_1.1 新增）                                 |
| 需登录的接口        | URL 参数 `?access_token=<应用级Token>` + `Authorization: Bearer <用户access_token>` |
| 刷新 Token      | Body 中传 `refresh_token`（无需应用 access\_token）                                  |

Token 时效：`access_token` 2 小时；`refresh_token` 30 天。

> **V\_1.1 说明**：`/api/v1/auth/*` 全部路径（除 `/token/refresh`）要求在 URL 查询参数中携带**应用级** `access_token`（由 AppKey+Secret 换取，`token_type=app`）。缺失或无效返回 401（-10501 / -10002）。

***

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
  "user": { "id": 1, "username": "user@example.com", "nickname": "..." },
  "must_change_password": false
}
```

> `must_change_password` 为 `true` 时（管理员重置密码后首次登录），须立即引导用户改密，详见 §4。

**错误码**: `1001` 账号或密码错误；`1002` 账号被禁用。

***

### 2.2 发送短信验证码 `POST /api/v1/auth/sms/send`

**入参**:

```json
{ "phone": "13800001111", "scene": "login" }
```

`scene` 可选值: `login`、`reset_password`、`bind_phone`。

***

### 2.3 校验短信验证码 `POST /api/v1/auth/sms/verify`

**入参**:

```json
{ "phone": "13800001111", "code": "123456", "scene": "login" }
```

**出参**: 校验通过返回一次性 `sms_token`，用于换取登录态。

***

### 2.4 短信验证码登录 `POST /api/v1/auth/sms/login`

**入参**:

```json
{ "phone": "13800001111", "code": "123456" }
```

**出参**: 同 §2.1（含 `must_change_password`）。

***

### 2.5 发送改密验证码 `POST /api/v1/auth/sms/send/pwd`

- 需 Access Token
- 入参: `{ "phone": "13800001111" }`

***

### 2.6 社交登录 `POST /api/v1/auth/social/login`

**入参**:

```json
{ "provider": "github|google|...", "code": "oauth_code", "redirect_uri": "..." }
```

**出参**: 同 §2.1（含 `must_change_password`）。

***

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

**出参**: 同 §2.1（含 `must_change_password`）。

***

### 2.8 刷新 Token `POST /api/v1/auth/token/refresh`

**入参**:

```json
{ "refresh_token": "eyJ..." }
```

**出参**: 同 §2.1，返回一对新的 Token。

***

### 2.9 登出 `POST /api/v1/auth/logout`

- 需 Access Token
- 入参: 无
- 行为: 将当前 `access_token` 加入黑名单直至自然过期。

***

### 2.10 获取当前用户 `GET /api/v1/auth/me` / `PUT /api/v1/auth/me`

- 需 Access Token
- GET 返回当前用户基础信息
- PUT 入参示例: `{ "nickname": "新昵称" }`

***

### 2.11 修改密码 `PATCH /api/v1/auth/me/password`

**入参**:

```json
{ "old_password": "...", "new_password": "..." }
```

> V\_1.1：改密成功后自动清除 `must_change_password` 标志（响应中体现为该用户后续请求恢复放行）。

***

### 2.12 短信重置密码 `POST /api/v1/auth/me/password/reset`

**入参**:

```json
{ "phone": "13800001111", "code": "123456", "new_password": "..." }
```

> V\_1.1：改密成功后自动清除 `must_change_password` 标志。

***

### 2.13 用户资料 `GET/PUT /api/v1/auth/me/profile`

- 需 Access Token
- 管理扩展字段，例如真实姓名、性别、头像 URL 等。

***

## 3. 通用错误码

| code   | 含义                    |
| ------ | --------------------- |
| 0      | 成功                    |
| 1001   | 账号或密码错误               |
| 1002   | 账号被禁用                 |
| 1003   | 验证码错误 / 已过期           |
| 1004   | Token 失效 / 已过期        |
| 1005   | 频率超限                  |
| -10104 | 需强制修改密码（HTTP 403）     |
| -10501 | 缺少/无效应用 access\_token |
| -10801 | 微信应用未配置               |

***

## 4. 强制改密策略 ✅ V\_1.1 新增

管理员在管理后台执行「重置密码」后：服务端生成随机密码（仅响应返回一次），并将该用户置为 `must_change_password=True`。

- 该用户**所有登录端点**响应携带 `must_change_password: true`；
- 登录后除以下白名单路径外，全部请求被中间件拦截返回 `403 / -10104`：
  - `GET/PUT /api/v1/auth/me`
  - `PATCH /api/v1/auth/me/password`
  - `POST /api/v1/auth/logout`
  - `POST /api/v1/auth/token/refresh`
- 通过 `PATCH /me/password` 或短信重置密码成功后，标志自动清除，访问恢复。

> 管理端 API（`/api/v1/admin/*`）不做此拦截，仅通过登录响应标志由前端提示。

***

## 5. 文档版本与变更记录

| 版本     | 日期         | 变更说明                                                                                        |
| ------ | ---------- | ------------------------------------------------------------------------------------------- |
| V\_1.0 | 2026-10-17 | 首版从主路由拆出独立子文档                                                                               |
| V\_1.1 | 2026-11-25 | 新增应用 access\_token URL 参数认证说明、登录响应 must\_change\_password 标志、§4 强制改密策略与 -10104 错误码、改密清除标志说明 |
