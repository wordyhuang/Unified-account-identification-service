> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-10-17 14:10:00
> **当前版本**: V_1.0
> **适用对象**: 对接本服务的 AI Agent、外部应用开发者
> **核心目标**: 提供 `/api/v1/open/*` 全部开放接口的完整定义、签名算法与权限码清单
> **文档简略描述**: 本子文档是主路由 `AI_API_ROUTING_GUIDE_v1.0.md` 的 B 类子文档。历史合订版见 `document/archive/gateway_openapi_documentation_v2.md`，细节以此子文档为准。

---

# 开放 API 子文档 `/api/v1/open/`

> AI 对接前请先读本文件。

## 大纲

- [1. 认证与签名算法](#1-认证与签名算法)
- [2. 权限码清单](#2-权限码清单)
- [3. 接口清单](#3-接口清单)
- [4. 轮询缓存指引](#4-轮询缓存指引)
- [5. 常见错误码](#5-常见错误码)
- [6. 文档版本与变更记录](#6-文档版本与变更记录)

---

## 1. 认证与签名算法

所有 `/api/v1/open/*` 接口必须同时携带：

| Header / 参数                   | 说明                                              |
| ---------------------------- | ----------------------------------------------- |
| `X-App-Key`                  | 管理后台分配的应用 Key                                  |
| `X-Timestamp`                | Unix 秒级时间戳，与服务器时差 > 5 分钟会拒绝                     |
| `X-Signature`                | HMAC-SHA256 签名                                     |
| `access_token`（URL 或 Body） | 终端用户的 access_token                                |

**签名算法**:

```
string_to_sign = HTTP_METHOD + "\n"
               + REQUEST_PATH + "\n"
               + X-Timestamp + "\n"
               + SORTED_QUERY_STRING

signature = HMAC_SHA256(app_secret, string_to_sign)  # Hex
```

服务端会在中间件中按相同规则重放校验，失败则返回 401。

---

## 2. 权限码清单

| 权限码                  | 说明              |
| -------------------- | --------------- |
| `token:verify`       | 验证用户 token       |
| `user:read`          | 查询用户            |
| `user:create`         | 创建用户            |
| `user:update`        | 修改用户            |
| `permission:check`    | 检查用户权限          |
| `user:profile:read`  | 按 token 读用户资料    |
| `user:profile:update`| 按 token 改用户资料     |
| `wechat:access_token` | 获取微信 access_token |
| `wechat:phone`        | 获取微信用户手机号       |

> 应用的权限通过"应用 → 角色 → 权限"链路授权，管理入口见 `API_03_ADMIN_v1.0.md` 中的"应用权限配置"。

---

## 3. 接口清单

### 3.1 验证用户 Token `POST /api/v1/open/verify_token`

- 权限码: `token:verify`
- 入参: `{ "access_token": "eyJ..." }`
- 出参:

  ```json
  {
    "valid": true,
    "user_id": 123,
    "username": "user@example.com",
    "expires_at": 1731800000
  }
  ```

---

### 3.2 用户列表 `GET /api/v1/open/users`

- 权限码: `user:read`
- Query: `page`、`page_size`、`keyword`、`status`

### 3.3 用户详情 `GET /api/v1/open/users/<id>`

- 权限码: `user:read`

### 3.4 创建用户 `POST /api/v1/open/users`

- 权限码: `user:create`
- 入参示例: `{ "username": "...", "password": "...", "nickname": "..." }`

### 3.5 修改用户 `PUT /api/v1/open/users/<id>`

- 权限码: `user:update`

### 3.6 启用/禁用用户 `PATCH /api/v1/open/users/<id>/status`

- 权限码: `user:update`
- 入参: `{ "status": "active" | "disabled" }`

### 3.7 检查用户权限 `POST /api/v1/open/check_permission`

- 权限码: `permission:check`
- 入参: `{ "user_id": 123, "permission_code": "user:read" }`
- 出参: `{ "has": true }`

### 3.8 通过 Token 获取用户资料 `GET /api/v1/open/user/profile/by_token`

- 权限码: `user:profile:read`
- Query: `access_token`

### 3.9 通过 Token 修改用户资料 `PUT /api/v1/open/user/profile/by_token`

- 权限码: `user:profile:update`
- Query: `access_token`
- Body: 资料字段

### 3.10 获取微信 AccessToken `GET /api/v1/open/wechat/access_token`

- 权限码: `wechat:access_token`
- 服务端自动缓存，避免触发微信配额。

### 3.11 获取微信用户手机号 `POST /api/v1/open/wechat/get_phone_number`

- 权限码: `wechat:phone`
- 入参: `{ "access_token": "eyJ...", "code": "wx_phone_code" }`

---

## 4. 轮询缓存指引

> 对接方若以"定时重复请求"方式使用 `verify_token`，强烈建议在**自己服务的本地**做缓存：
>
> - Token 本身是 JWT，已含 `exp`。
> - 缓存键: `access_token`；缓存值: `valid / user_id / expires_at`。
> - 缓存时长: 取 `min(expires_at - now, 客户端自定义上限)`。
> - 不要每次都打本服务 `verify_token`，会浪费对方与本服务的计算资源。

---

## 5. 常见错误码

| code  | 含义                |
| ----- | ----------------- |
| 0     | 成功                |
| 2001  | 签名校验失败            |
| 2002  | 时间戳过期             |
| 2003  | 应用未找到 / 已停用       |
| 2004  | 权限不足              |
| 2005  | Token 无效           |
| 2006  | 租户数据隔离拒绝（越权）     |

---

## 6. 文档版本与变更记录

| 版本    | 日期         | 变更说明                              |
| ----- | ---------- | --------------------------------- |
| V_1.0 | 2026-10-17 | 从原合订版 `gateway_openapi_documentation_v2.md` 拆出独立子文档 |
