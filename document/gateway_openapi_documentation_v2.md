# 统一账户认证服务 - API对接文档

## 概述

欢迎使用统一账户认证服务！本文档为外部开发者提供完整的API对接指南，帮助您快速集成统一认证能力。

**服务地址**: `http://localhost:8000`（开发环境）

***

## API 设计规范

本文档遵循以下 API 设计规范：

| 规范          | 说明                                                |
| ----------- | ------------------------------------------------- |
| **资源路径**    | 统一使用复数名词（`users`、`permissions`、`tokens`）          |
| **当前用户**    | 使用 `/me` 表示当前认证用户，替代非标准命名（如 `userinfo`）           |
| **HTTP 方法** | `GET` 查询、`POST` 创建、`PUT` 全量更新、`PATCH` 部分更新        |
| **URL 无动词** | 操作由 HTTP Method 表达，URL 中不使用动词（如去除 `update`、`get`） |
| **参数命名**    | 统一使用 `token`、`refresh_token` 等全小写下划线命名            |
| **版本化**     | 所有 API 通过 URL 前缀 `/api/v1/` 进行版本管理                |

***

## 整体流程架构

### 1. 应用注册与配置流程

```
应用方                      管理后台                      认证服务
 ├─ 创建应用─────────────────>│
 │                           │ 生成 app_key 和 app_secret
 │                           ├─ 配置回调地址白名单
 │                           ├─ 分配权限范围
 │<─────────────────────────┤
 │  获取凭证                 │
 │
 │  保存 app_key 和 app_secret
 └─ (妥善保管)
```

### 2. 用户登录与认证流程

#### 密码登录流程

```
用户         应用方                    认证服务
 ├─ 输入账号密码──>│
 │                ├─ 验证账号密码──>│
 │                │                │ 验证通过
 │                │<───────────────┤
 │                │  返回Token对
 │<───────────────┤
 │ 存储Token      │
 │
 ├─ 使用Token────>│
 │                ├─ 校验Token───>│
 │                │                │ 通过
 │                │<───────────────┤
 │                │  返回用户信息
 │<───────────────┤
```

#### 短信验证码登录流程

```
用户         应用方                    认证服务
 ├─ 输入手机号────>│
 │                ├─ 发送验证码───>│
 │                │                │ 生成验证码（5分钟有效）
 │                │                │ 发送短信
 │                │<──发送成功─────┤
 │
 ├─ 输入验证码────>│
 │                ├─ 验证验证码──>│
 │                │                │ 验证通过
 │                │                │ 用户不存在则自动创建
 │                │<───────────────┤
 │                │  返回Token对
 │<───────────────┤
```

#### 社交登录流程

```
用户         应用方                    认证服务                   第三方平台
 ├─ 选择社交登录──>│
 │                ├─ 请求授权URL──>│
 │                │                │ 生成授权链接
 │                │<──授权URL──────┤
 │
 ├─ 在第三方平台─>│
 │ 完成授权
 │                ├─ 使用授权码───>│
 │                │                │ 换取用户信息────────>│
 │                │                │<──用户信息──────────┤
 │                │                │ 用户不存在则自动创建
 │                │<──Token对──────┤
 │<──登录成功───┤
```

#### OAuth2授权流程（第三方应用）

```
用户           第三方应用                     认证服务
 ├─ 点击登录───>│
 │              ├─ 重定向到授权页──>│
 │              │                  │
 │              │<──显示授权页──────┤
 │              │
 ├─ 同意授权────>│
 │              ├─ 获取授权码─────>│
 │              │                  │ 生成授权码（5分钟有效期）
 │              │<──授权码─────────┤
 │              │
 │              ├─ 换取Token──────>│
 │              │                  │ 验证授权码
 │              │                  │ 生成Token（2小时）
 │              │                  │ 和Refresh Token（24小时）
 │              │<──Token对────────┤
 │              │
 │<──登录成功───┤
```

#### Token刷新流程

```
用户         应用方                    认证服务
 │
 │  (Access Token即将过期)
 │
 ├─ 主动刷新─────>│
 │  携带refresh_token
 │                ├─ 验证refresh_token─>│
 │                │                     │ 检查有效性
 │                │                     │ 生成新的Token
 │                │                     │ 可选：生成新的Refresh Token
 │                │<────────────────────┤
 │                │  返回新的Token对
 │<───────────────┤
 │  更新本地Token存储
 │
 ├─ 继续使用新Token─>│
```

### 3. 开放API调用流程

```
应用方                        认证服务
 │
 ├─ (首次) 获取access_token──>│
 │  请求体:
 │  - app_key: 应用Key
 │  - app_secret: 应用密钥
 │                           ├─ 验证app_key/app_secret
 │                           │  生成应用token(JWT, 2小时有效)
 │<──返回 token───────┤
 │
 ├─ (后续) 携带access_token调用API─>│
 │  URL参数:
 │  ?access_token=<应用access_token>
 │
 │                           ├─ 解析access_token
 │                           ├─ 校验access_token有效性
 │                           ├─ 校验接口权限
 │                           ├─ 执行业务逻辑
 │
 │<──响应数据───────────────┤
 │
 ├─ (access_token过期) 重新获取──>│
 │  重复首次流程
 │
 └─ 处理响应
```

***

## 快速开始

### 第一步：获取应用凭证

在使用开放API前，您需要先在管理后台创建应用并获取凭证：

| 参数           | 说明                  |
| ------------ | ------------------- |
| `app_key`    | 应用唯一标识              |
| `app_secret` | 应用密钥（创建时显示一次，请妥善保管） |

### 第二步：获取应用access\_token

开放API采用 **access\_token** 认证。access\_token 是应用级凭证，用于控制接口访问权限。首次使用 AppKey + Secret 换取 access\_token，后续 API 调用通过 URL 查询参数传递。

**每个应用应缓存自己的 access\_token**，在过期前（有效期 2 小时）复用，避免每次请求都重新生成。

```bash
# 获取应用 access_token
curl -X POST http://localhost:8000/api/v1/open/token \
  -H "Content-Type: application/json" \
  -d '{"app_key": "YOUR_APP_KEY", "app_secret": "YOUR_APP_SECRET"}'
```

**成功响应**：

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "expires_in": 7200
    }
}
```

### 第三步：发起API请求

获取 access\_token 后，所有开放API请求通过 URL 查询参数传递 `access_token`：

```bash
# 示例：验证用户Token（注意两个不同概念）
# - ?access_token= : 应用级凭证，控制接口访问权限（URL传递）
# - 请求体中的 "token": 用户的JWT Token，用于用户身份校验（body中传递）
curl -X POST "http://localhost:8000/api/v1/open/token/verify?access_token=<应用access_token>" \
  -H "Content-Type: application/json" \
  -d '{"token": "用户JWTToken"}'
```

> **access\_token 有效期**：2 小时（7200 秒），过期后需重新调用 `/api/v1/open/token` 获取。
> **建议**：将 access\_token 缓存到本地，在过期前复用，避免每次请求都重新生成。

***

## 认证方式详解

本系统的认证涉及两个不同概念：

| 概念                | 用途          | 传递方式                            | 适用场景                       |
| ----------------- | ----------- | ------------------------------- | -------------------------- |
| **access\_token** | 接口访问权限控制    | URL 查询参数 `?access_token=`       | `/api/v1/open/*` 所有开放API接口 |
| **token**（用户JWT）  | 用户身份校验与信息交互 | `Authorization: Bearer <token>` | 用户登录态维护、用户信息调取             |

> **重要区分**：access\_token 是**应用级凭证**，只控制"能不能调这个接口"；token 是**用户级凭证**，标识"当前是哪个用户在操作"。两者用途不同，不可混用。

***

### 1. 应用级认证 — access\_token（接口访问权限）

**适用接口**: `/api/v1/open/*` 下所有接口（除 `POST /api/v1/open/token` 本身外）

**核心概念**：access\_token 是调用开放API的**接口访问凭证**。每个应用独立拥有自己的 access\_token，应在本地缓存复用，过期后重新获取。

**认证流程**:

```
① 首次获取：
   POST /api/v1/open/token
   Body: { app_key, app_secret }
   → 返回 { access_token, expires_in }

② 后续调用：
   在 URL 查询参数中传入 access_token
   GET /api/v1/open/users?access_token=eyJ...
   POST /api/v1/open/permissions/check?access_token=eyJ...
```

**获取 access\_token 请求**:

```json
POST /api/v1/open/token
Content-Type: application/json

{
    "app_key": "your_app_key",
    "app_secret": "your_app_secret"
}
```

**获取 access\_token 响应**:

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "expires_in": 7200
    }
}
```

**access\_token 有效期**:

| 类型                   | 有效期     | 说明                                          |
| -------------------- | ------- | ------------------------------------------- |
| **应用 access\_token** | **2小时** | JWT令牌，用于 `/api/v1/open/*` 接口调用，**不同应用各自独立** |

> **⚠️ 重要注意事项**：
>
> 1. **各自缓存，各自维护**：不同应用申请的 access\_token 互不相同。每个应用应将 access\_token 缓存到本地，在过期前复用，不建议每次都重新生成。
> 2. **过期处理**：access\_token 过期后调用接口返回 401，需重新通过 `/api/v1/open/token` 获取。
> 3. **secret 安全**：`app_secret` 仅在获取 access\_token 时传输一次，后续调用不传输。请妥善保管。
> 4. **建议提前刷新**：在 access\_token 到期前 5-10 分钟重新获取，避免请求中断。

***

### 2. 用户认证 — token（用户身份校验）

**适用接口**: 需要用户登录态认证的接口

**核心概念**：用户 token 是**用户身份凭证**，用户在登录后获得，用于证明"我是谁"以及操作自己的数据。

**请求头格式**:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**获取 token 流程**:

1. 调用 `/api/v1/auth/login` 或 `/api/v1/auth/sms/login` 获取 `token`（用户JWT）和 `refresh_token`
2. 在后续请求的 `Authorization: Bearer` 头中携带 `token`
3. Token 过期时调用 `/api/v1/auth/token/refresh` 刷新

**用户 Token 有效期**:

| Token类型            | 有效期            | 说明                      |
| ------------------ | -------------- | ----------------------- |
| **用户 token**       | **120分钟（2小时）** | JWT访问令牌，用于用户认证场景        |
| **refresh\_token** | **24小时**       | 刷新令牌，用于获取新的 token，一次性使用 |

> **注意**: 建议在 token 到期前 5-10 分钟主动刷新，避免请求中断

***

## 开放API接口列表

> **⚠️ 认证方式（重要）**: 所有开放API接口（`/api/v1/open/*`）均**需要** `access_token` 进行接口访问控制。
>
> **access\_token 传递方式**：通过 URL 查询参数 `?access_token=<应用access_token>` 传递。
>
> - 除 `POST /api/v1/open/token`（获取凭证接口）外，所有接口**都必须**提供该参数
> - access\_token 通过调用 `POST /api/v1/open/token` 获取，每次调用有效期为 2 小时
> - **建议缓存**：不同应用各自缓存自己的 access\_token，过期前复用，避免频繁重新生成
>
> 未提供有效 access\_token 的请求将返回 `401 Unauthorized`。

### 获取应用 access\_token

**接口地址**: `POST /api/v1/open/token`

**access\_token 要求**: 无需提供（本接口用于获取 access\_token，本身不需要认证）

**功能描述**: 使用应用凭证（app\_key + app\_secret）换取 access\_token。获取后应在后续所有开放API接口的 URL 中传入 `?access_token=`。

**请求体**:

```json
{
    "app_key": "string (必填，应用唯一标识)",
    "app_secret": "string (必填，应用密钥)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "expires_in": 7200
    }
}
```

**失败响应** (401):

```json
{
    "code": -10501,
    "message": "AppKey无效"
}
```

***

### 验证用户Token

**接口地址**: `POST /api/v1/open/token/verify`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递（接口访问凭证）

**功能描述**: 验证用户Token的有效性，常用于单点登录场景

**请求体**:

```json
{
    "token": "string (必填，用户的JWT AccessToken，最大长度512)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "valid": true,
        "user_id": 1,
        "tenant_id": 1,
        "user_type": "internal"
    }
}
```

### 查询用户列表

**接口地址**: `GET /api/v1/open/users`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 查询当前租户下的用户列表

**请求参数**:

| 参数 | 必填 | 说明               |
| -- | -- | ---------------- |
| 无  | -  | 返回当前租户下所有用户（不分页） |

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "users": [
            {
                "id": 1,
                "uuid": "a1b2c3d4-...",
                "username": "zhangsan",
                "user_type": "internal",
                "email": "zhangsan@example.com",
                "phone": "13800138000",
                "nickname": "张三",
                "avatar": null,
                "department": "技术部",
                "status": 1,
                "tenant_id": 1,
                "last_login_at": "2024-01-15T09:00:00",
                "created_at": "2024-01-01T10:00:00",
                "tags": [
                    {"id": 1, "name": "VIP用户", "color": "#1890ff"}
                ]
            }
        ],
        "total": 100
    }
}
```

### 创建用户

**接口地址**: `POST /api/v1/open/users`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 创建新用户，支持设置部门和角色。未提供 `username` 时将自动生成唯一账号。

**自动生成规则**: 按以下优先级生成

1. 使用 `phone` 值作为账号
2. 使用 `email` 的 `@` 之前的部分作为账号
3. 生成随机账号（格式：`user_` + 8位随机字符）

**请求体**:

```json
{
    "username": "string (选填，不传则自动生成，最大64字符)",
    "password": "string (必填，8-256字符)",
    "user_type": "string (选填，internal/external，默认internal)",
    "email": "string (选填，邮箱格式)",
    "phone": "string (选填，最大20字符)",
    "nickname": "string (选填，最大128字符)",
    "department": "string (选填，最大128字符)",
    "dept_code": "string (选填，部门编码，最大64字符)",
    "role_codes": ["string (选填，角色编码列表)"]
}
```

**成功响应** (201):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "id": 101,
        "uuid": "a1b2c3d4-...",
        "username": "newuser",
        "user_type": "internal",
        "email": null,
        "phone": null,
        "nickname": null,
        "avatar": null,
        "department": null,
        "status": 1,
        "tenant_id": 1,
        "last_login_at": null,
        "created_at": "2024-01-01T10:00:00",
        "tags": []
    }
}
```

**失败响应** (400):

```json
{
    "code": -10602,
    "message": "用户名已存在"
}
```

### 获取用户详情

**接口地址**: `GET /api/v1/open/users/{user_id}`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 获取单个用户详情

**路径参数**:

| 参数        | 说明   |
| --------- | ---- |
| `user_id` | 用户ID |

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "id": 1,
        "uuid": "a1b2c3d4-...",
        "username": "zhangsan",
        "user_type": "internal",
        "email": "zhangsan@example.com",
        "phone": "13800138000",
        "nickname": "张三",
        "avatar": null,
        "department": "技术部",
        "status": 1,
        "tenant_id": 1,
        "last_login_at": "2024-01-15T09:00:00",
        "created_at": "2024-01-01T10:00:00",
        "tags": [
            {"id": 1, "name": "VIP用户", "color": "#1890ff"}
        ]
    }
}
```

### 更新用户信息

**接口地址**: `PUT /api/v1/open/users/{user_id}`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 更新用户信息，支持修改部门和角色

**请求体**:

```json
{
    "nickname": "string (选填，最大128字符)",
    "email": "string (选填，邮箱格式)",
    "phone": "string (选填，最大20字符)",
    "avatar": "string (选填，URL格式，最大512字符)",
    "department": "string (选填，最大128字符)",
    "dept_code": "string (选填，部门编码，空字符串表示清除部门)",
    "role_codes": ["string (选填，角色编码列表，空数组清除所有角色)"]
}
```

> **手机号唯一性**: 同租户内手机号不可重复。如果将手机号修改为其他用户已使用的号码，将返回 `-10602` 错误（"手机号已被占用"）。不同租户间允许手机号重复。

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "user_id": 1
    }
}
```

### 更新用户状态

**接口地址**: `PATCH /api/v1/open/users/{user_id}/status`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 启用/禁用用户

**请求体**:

```json
{
    "status": "integer (必填，0=禁用，1=启用)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "user_id": 1,
        "user_uuid": "a1b2c3d4-...",
        "status": 1
    }
}
```

### 检查用户权限

**接口地址**: `POST /api/v1/open/permissions/check`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 检查用户是否具有指定权限

**请求体**:

```json
{
    "user_id": "integer (必填，用户ID)",
    "permission_code": "string (必填，权限编码，最大64字符)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "user_id": 1,
        "user_uuid": "a1b2c3d4-...",
        "permission_code": "user.view",
        "has_permission": true
    }
}
```

### 通过Token获取用户资料

**接口地址**: `GET /api/v1/open/users/me/profile`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 通过用户的JWT AccessToken获取其完整资料信息。Token可在 query string 或 request body 中传递。

**权限码**: `user:profile:read`

**请求参数**:

| 参数             | 位置         | 必填 | 说明                         |
| -------------- | ---------- | -- | -------------------------- |
| `access_token` | query/body | ✅  | 用户的JWT AccessToken，最大512字符 |

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "user_id": 1,
        "username": "zhangsan",
        "nickname": "张三",
        "avatar": null,
        "real_name": "张三",
        "gender": "male",
        "birthday": "1990-01-01",
        "id_card": "110****1234",
        "nationality": "中国",
        "address": "北京市朝阳...",
        "zip_code": "100000",
        "emergency_contact": "李四",
        "emergency_phone": "138****8001",
        "job_title": "高级工程师",
        "employee_id": "EMP001",
        "hire_date": "2020-06-01",
        "work_email": "zh****an@company.com",
        "work_phone": "010-****6666",
        "wechat": "zh****an_wx",
        "qq": "12****78",
        "weibo": "zhangsan_wb",
        "bio": "个人简介内容",
        "interests": "编程、阅读、运动",
        "tags": ["技术", "管理"],
        "extra_data": {"source": "invite"}
    }
}
```

**失败响应** (401):

```json
{
    "code": -10002,
    "message": "Token无效"
}
```

### 通过Token修改用户资料

**接口地址**: `PUT /api/v1/open/users/me/profile`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 通过用户的JWT AccessToken更新其个人资料。仅更新请求中携带的字段，未提供的字段保持不变。

**权限码**: `user:profile:update`

**请求体**:

```json
{
    "access_token": "string (必填，用户的JWT AccessToken，最大512字符)",
    "avatar": "string (选填，头像URL)",
    "real_name": "string (选填，真实姓名)",
    "gender": "string (选填，male/female/other)",
    "birthday": "string (选填，日期，如 1990-01-01)",
    "id_card": "string (选填，身份证号)",
    "nationality": "string (选填，国籍)",
    "address": "string (选填，联系地址)",
    "zip_code": "string (选填，邮政编码)",
    "emergency_contact": "string (选填，紧急联系人)",
    "emergency_phone": "string (选填，紧急联系电话)",
    "job_title": "string (选填，职位)",
    "employee_id": "string (选填，员工编号)",
    "hire_date": "string (选填，入职日期)",
    "work_email": "string (选填，工作邮箱)",
    "work_phone": "string (选填，工作电话)",
    "wechat": "string (选填，微信号)",
    "qq": "string (选填，QQ号)",
    "weibo": "string (选填，微博账号)",
    "bio": "string (选填，个人简介)",
    "interests": "string (选填，兴趣爱好)",
    "tags": "array (选填，标签数组)",
    "extra_data": "object (选填，扩展数据)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "profile_id": 1
    }
}
```

**失败响应** (400):

```json
{
    "code": -10602,
    "message": "参数格式错误",
    "data": {
        "access_token": ["该字段是必填项。"]
    }
}
```

***

## 微信小程序辅助接口

小程序可通过以下接口完成在服务端的辅助操作。所有接口使用 **access\_token** 进行接口访问控制，通过 URL 参数 `?access_token=<应用access_token>` 传递。

### 获取微信 AccessToken

**接口地址**: `GET /api/v1/open/wechat/access_token`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 获取微信小程序的接口调用凭证 `access_token`。系统按 `AppID` 自动缓存（缓存7000秒，微信官方有效期7200秒），缓存有效期内直接返回缓存值，不重复请求微信接口。

**权限码**: `wechat:access_token`

**请求头**: 方式一：`X-App-Key`、`X-Timestamp`、`X-Signature` | 方式二：URL `?access_token=<应用AccessToken>`（通过 `/api/v1/open/token` 获取）

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "access_token": "wx_access_token_string",
        "source": "cache",
        "app_id": "wx1234567890abcdef"
    }
}
```

首次获取时 `source` 值为 `wechat`，后续缓存命中时为 `cache`。

### 获取微信用户手机号

**接口地址**: `POST /api/v1/open/wechat/phone`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 通过微信小程序 `getPhoneNumber` 接口返回的临时 `code`，获取用户绑定的真实手机号码。

**权限码**: `wechat:phone`

**请求体**:

```json
{
    "code": "string (必填，微信小程序getPhoneNumber接口返回的临时code)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "phone_number": "8613800138000",
        "country_code": "86",
        "pure_phone_number": "13800138000"
    }
}
```

***

## 用户认证接口

> **⚠️ 认证方式说明**：本小节所有接口均为应用调用，均**需要** `access_token` 进行应用级接口访问控制。
>
> - `access_token` 通过 URL 查询参数 `?access_token=<应用access_token>` 传递
> - `access_token` 通过调用 `POST /api/v1/open/token` 获取，有效期为 2 小时
> - 未提供有效 `access_token` 的请求将返回 `401 Unauthorized`
>
> 注意：`access_token` 是**应用级凭证**（控制接口调用权限），与用户登录后返回的 `token`（用户身份凭证）是两个不同的概念，不可混用。

### 密码登录

**接口地址**: `POST /api/v1/auth/login`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 用户使用密码登录。`username` 字段支持输入**用户名**或**绑定的手机号**两种方式。

**请求体**:

```json
{
    "username": "string (必填，用户名或已绑定的手机号，最大64字符)",
    "password": "string (必填，最大256字符)"
}
```

**成功响应** (200) - 普通用户:

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "user_id": 1,
        "username": "admin",
        "nickname": "管理员",
        "user_type": "internal",
        "is_superuser": false,
        "is_staff": false
    }
}
```

**成功响应** (200) - 超级管理员:

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "username": "superadmin",
        "is_superadmin": true,
        "is_superuser": true,
        "is_staff": true
    }
}
```

**失败响应** (400):

```json
{
    "code": -10602,
    "message": "密码错误"
}
```

**失败响应** (403):

```json
{
    "code": -10102,
    "message": "用户已禁用"
}
```

### 发送短信验证码

**接口地址**: `POST /api/v1/auth/sms/send`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 向指定手机号发送6位数字验证码，用于短信登录。
验证码有效期5分钟，一次性使用（验证后立即失效）。

**请求体**:

```json
{
    "phone": "string (必填，最大20字符，中国大陆手机号)",
    "app_key": "string (选填，应用Key，用于按应用获取租户短信配置)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "phone": "15907073477"
    }
}
```

**失败响应** (429):

```json
{
    "code": -10401,
    "message": "短信发送太频繁，请稍后再试"
}
```

```json
{
    "code": -10401,
    "message": "该手机号今日短信发送次数已达上限"
}
```

```json
{
    "code": -10401,
    "message": "IP请求太频繁，请稍后再试"
}
```

**失败响应** (500):

```json
{
    "code": -10303,
    "message": "短信发送失败"
}
```

> **说明**：
>
> - 验证码由系统随机生成，通过阿里云短信服务发送
> - 若阿里云发送失败（如触发频率限制），接口返回500，服务端会打印验证码到控制台供开发调试
> - 短信服务配置通过环境变量控制（见 `.env` 文件）
>
> **频率限制**：
>
> - **同一手机号冷却期**：每次发送成功后60秒内不可再次发送（可通过环境变量 `SMS_PHONE_COOLDOWN_SECONDS` 调整）
> - **同一手机号每日上限**：每个手机号每天最多发送5条验证码（可通过环境变量 `SMS_PHONE_DAILY_LIMIT` 调整）
> - **同一IP限频**：每个IP每分钟最多发送10条验证码（可通过环境变量 `SMS_IP_RATE_PER_MINUTE` 调整）
> - 超出以上任一限制均返回 HTTP 429 状态码，错误码 `-10401`（`RATE_LIMIT_EXCEEDED`）

### 短信登录

**接口地址**: `POST /api/v1/auth/sms/login`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 使用短信验证码登录，自动注册外部用户（如用户不存在）。

**登录流程**:

```
① POST /api/v1/auth/sms/send    →   发送验证码到手机
              │
              ▼   用户收到短信
② POST /api/v1/auth/sms/login   →   校验验证码
              │
              ├─ 用户不存在 → 自动创建外部用户（username=手机号）
              └─ 用户已存在 → 直接登录
              │
              ▼
③ 返回 JWT Token，后续请求携带 Authorization: Bearer {token}
```

**请求体**:

```json
{
    "phone": "string (必填，最大20字符)",
    "code": "string (必填，最大10字符，即短信中收到的6位验证码)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "user_id": 4,
        "is_new": false
    }
}
```

| 返回字段            | 类型     | 说明                                    |
| --------------- | ------ | ------------------------------------- |
| `token`         | string | JWT Token，有效期120分钟                    |
| `refresh_token` | string | 刷新令牌，用于获取新的Access Token，有效期24小时，一次性使用 |
| `user_id`       | int    | 用户ID                                  |
| `is_new`        | bool   | 是否为新注册用户                              |

**失败响应** (400):

```json
{
    "code": -10302,
    "message": "验证码已过期，请重新获取"
}
```

```json
{
    "code": -10301,
    "message": "验证码错误"
}
```

### 短信验证码验证

**接口地址**: `POST /api/v1/auth/sms/verify`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 验证短信验证码是否正确，**不执行登录操作**。适用于修改手机号前号主确认等场景。

**请求体**:

```json
{
    "phone": "string (必填，最大20字符，接收验证码的手机号)",
    "code": "string (必填，最大10字符，短信中收到的6位验证码)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "verified": true
    }
}
```

**失败响应** (400):

```json
{
    "code": -10302,
    "message": "验证码已过期，请重新获取"
}
```

```json
{
    "code": -10301,
    "message": "验证码错误"
}
```

### 社交登录

**接口地址**: `POST /api/v1/auth/social/login`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 使用第三方社交账号登录

**请求体**:

```json
{
    "provider": "string (必填，支持: wechat_mp/wechat_web/dingtalk/feishu)",
    "code": "string (必填，最大512字符，第三方授权码)",
    "app_key": "string (选填，应用Key，微信登录时用于获取对应的微信配置)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "user_id": 3,
        "is_new": true
    }
}
```

### 刷新Token

**接口地址**: `POST /api/v1/auth/token/refresh`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 使用refresh\_token获取新的access\_token

**请求体**:

```json
{
    "refresh_token": "string (必填，最小32字符)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "new_refresh_token..."
    }
}
```

**失败响应** (401):

```json
{
    "code": -10002,
    "message": "Token无效"
}
```

### 获取用户信息

**接口地址**: `GET /api/v1/auth/me`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 获取当前登录用户信息

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "id": 1,
        "uuid": "a1b2c3d4-...",
        "username": "admin",
        "user_type": "internal",
        "email": "admin@example.com",
        "phone": "13800138000",
        "nickname": "管理员",
        "avatar": null,
        "department": "技术部",
        "status": 1,
        "tenant_id": 1,
        "last_login_at": "2024-01-15T09:00:00",
        "created_at": "2024-01-01T10:00:00",
        "tags": [
            {"id": 1, "name": "VIP用户", "color": "#1890ff"},
            {"id": 2, "name": "管理员", "color": "#52c41a"}
        ]
    }
}
```

### 更新用户信息

**接口地址**: `PUT /api/v1/auth/me`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 更新当前登录用户的个人信息

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**请求体**:

```json
{
    "nickname": "string (选填，最大128字符)",
    "email": "string (选填，邮箱格式)",
    "phone": "string (选填，最大20字符)",
    "avatar": "string (选填，URL格式，最大512字符)"
}
```

> **手机号唯一性**: 同租户内手机号不可重复。如果将手机号修改为其他用户已使用的号码，将返回 `-10602` 错误（"手机号已被占用"）。不同租户间允许手机号重复。

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "user_id": 1
    }
}
```

### 修改密码

**接口地址**: `PATCH /api/v1/auth/me/password`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 修改当前登录用户的密码

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**请求体**:

```json
{
    "old_password": "string (必填，当前密码)",
    "new_password": "string (必填，新密码，8-256字符)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {}
}
```

**失败响应** (400):

```json
{
    "code": -10602,
    "message": "原密码错误"
}
```

### 获取用户资料

**接口地址**: `GET /api/v1/auth/me/profile`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 获取当前登录用户的详细资料（扩展信息）

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "id": 1,
        "avatar": "https://example.com/avatar.png",
        "real_name": "张三",
        "gender": "male",
        "birthday": "1990-01-01",
        "id_card": "110101199001011234",
        "nationality": "中国",
        "address": "北京市朝阳区",
        "zip_code": "100000",
        "emergency_contact": "李四",
        "emergency_phone": "13800138001",
        "job_title": "高级工程师",
        "employee_id": "EMP001",
        "hire_date": "2020-06-01",
        "work_email": "zhangsan@company.com",
        "work_phone": "010-88886666",
        "wechat": "zhangsan_wx",
        "qq": "12345678",
        "weibo": "zhangsan_wb",
        "bio": "个人简介内容",
        "interests": "编程、阅读、运动",
        "tags": ["技术", "管理"],
        "extra_data": {"source": "invite"},
        "created_at": "2024-01-01T10:00:00",
        "updated_at": "2024-01-15T09:00:00"
    }
}
```

### 更新用户资料

**接口地址**: `PUT /api/v1/auth/me/profile`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 更新当前登录用户的详细资料

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**请求体**:

```json
{
    "avatar": "string (选填，头像URL)",
    "real_name": "string (选填，真实姓名)",
    "gender": "string (选填，male/female/other)",
    "birthday": "string (选填，日期，如 1990-01-01)",
    "id_card": "string (选填，身份证号)",
    "nationality": "string (选填，国籍)",
    "address": "string (选填，联系地址)",
    "zip_code": "string (选填，邮政编码)",
    "emergency_contact": "string (选填，紧急联系人)",
    "emergency_phone": "string (选填，紧急联系电话)",
    "job_title": "string (选填，职位)",
    "employee_id": "string (选填，员工编号)",
    "hire_date": "string (选填，入职日期)",
    "work_email": "string (选填，工作邮箱)",
    "work_phone": "string (选填，工作电话)",
    "wechat": "string (选填，微信号)",
    "qq": "string (选填，QQ号)",
    "weibo": "string (选填，微博账号)",
    "bio": "string (选填，个人简介)",
    "interests": "string (选填，兴趣爱好)",
    "tags": "array (选填，标签数组)",
    "extra_data": "object (选填，扩展数据)"
}
```

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "profile_id": 1
    }
}
```

### 登出

**接口地址**: `POST /api/v1/auth/logout`

**access\_token 要求**: ✅ 需要，通过 URL 参数 `?access_token=` 传递

**功能描述**: 用户登出

**认证方式**: Bearer Token（用户身份凭证） + `access_token`（URL参数，应用接口凭证）

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {}
}
```

***

## 错误码速查

| 错误码    | 含义        | HTTP状态码 | 处理建议                       |
| ------ | --------- | ------- | -------------------------- |
| 0      | 成功        | 200/201 | -                          |
| -10001 | Token已过期  | 401     | 使用refresh\_token刷新或重新登录    |
| -10002 | Token无效   | 401     | 重新登录获取新Token               |
| -10003 | 签名无效      | 401     | 检查签名算法和app\_secret         |
| -10101 | 用户不存在     | 404     | 确认用户ID或用户名是否正确             |
| -10102 | 用户已禁用     | 403     | 联系管理员启用账户                  |
| -10103 | 用户访问被拒绝   | 403     | 检查用户应用访问权限                 |
| -10201 | 权限不足      | 403     | 确认用户是否有相应权限                |
| -10202 | 无接口调用权限   | 403     | 确认应用是否绑定了该接口权限             |
| -10301 | 短信验证码错误   | 400     | 检查验证码是否正确                  |
| -10302 | 短信验证码已过期  | 400     | 重新获取验证码                    |
| -10303 | 短信发送失败    | 500     | 稍后重试，检查短信服务配置              |
| -10401 | 限流超限      | 429     | 稍后重试或联系管理员调整限流配置           |
| -10501 | AppKey无效  | 401     | 确认app\_key和app\_secret是否正确 |
| -10502 | 应用已禁用     | 403     | 联系管理员启用应用                  |
| -10601 | 缺少必要参数    | 400     | 检查请求参数是否完整                 |
| -10602 | 参数格式错误    | 400     | 检查请求参数是否正确                 |
| -10801 | 微信未配置     | 400     | 联系管理员配置微信 AppID/AppSecret  |
| -10802 | 微信API调用失败 | 400     | 检查微信授权码是否正确或稍后重试           |

***

## 对接示例

### Python示例

```python
import requests

APP_KEY = "your_app_key"
APP_SECRET = "your_app_secret"
BASE_URL = "http://localhost:8000"


def get_app_token():
    """使用 AppKey + Secret 换取应用 Access Token"""
    response = requests.post(
        f"{BASE_URL}/api/v1/open/token",
        json={"app_key": APP_KEY, "app_secret": APP_SECRET}
    )
    data = response.json()
    return data["data"]["access_token"]  # 返回 JWT Token


def verify_user_token(app_token, user_token):
    """使用应用 Token 验证用户 Token"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {app_token}"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/open/token/verify",
        headers=headers,
        json={"access_token": user_token}
    )
    return response.json()


# 使用示例
app_token = get_app_token()  # ① 获取应用Token（可缓存复用，有效期2小时）
result = verify_user_token(app_token, "user_jwt_token")  # ② 调用API
print(result)
```

### JavaScript示例

```javascript
const BASE_URL = 'http://localhost:8000';
const APP_KEY = 'your_app_key';
const APP_SECRET = 'your_app_secret';

async function getAppToken() {
    // ① 使用 AppKey + Secret 换取应用 Access Token
    const response = await fetch(`${BASE_URL}/api/v1/open/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app_key: APP_KEY, app_secret: APP_SECRET })
    });
    const data = await response.json();
    return data.data.access_token;  // 返回 JWT Token
}

async function verifyUserToken(appToken, userToken) {
    // ② 使用应用 Token 验证用户 Token
    const response = await fetch(`${BASE_URL}/api/v1/open/token/verify`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${appToken}`
        },
        body: JSON.stringify({ access_token: userToken })
    });
    return response.json();
}

// 使用示例
const appToken = await getAppToken();  // 可缓存复用
const result = await verifyUserToken(appToken, 'user_jwt_token');
console.log(result);
```

***

## 最佳实践

### 1. Token管理

- 将token存储在安全的地方（如HttpOnly Cookie）
- **Token有效期为120分钟（2小时）**，建议在到期前5-10分钟主动刷新
- **Refresh Token有效期为24小时**，一次性使用，用于获取新的Token
- 定期刷新Token避免用户重新登录

### 2. Token安全

- 将token存储在安全的地方（如HttpOnly Cookie或服务端缓存）
- 应用access\_token有效期为2小时，建议在到期前5-10分钟重新获取
- 用户token有效期为2小时，建议在到期前5-10分钟主动刷新
- Refresh Token有效期为24小时，一次性使用，用于获取新的用户token
- `app_secret` 应保存在服务端，不要在前端暴露

### 3. 错误处理

- 统一处理401/403错误，引导用户重新登录
- 对限流错误实现指数退避重试
- 记录详细的错误日志便于排查

### 4. 请求优化

- 批量操作使用批量接口
- 合理设置分页大小（如适用）
- 使用缓存减少重复请求

***

## 支持与反馈

如有问题或需要帮助，请联系技术支持团队：

- **技术支持邮箱**: <395051729@qq.com>
- **文档版本**: v3.0
- **最后更新**: 2026-06-24

***

## 附录：权限编码列表

> 以下为系统预置的 API 权限，通过管理命令 `python manage.py init_data` 初始化。
> 应用开通时需在管理后台绑定接口权限，未绑定的接口调用会返回 `-10202` 错误。

| 权限编码                  | 权限名称            | 说明                              | 对应接口                                   |
| --------------------- | --------------- | ------------------------------- | -------------------------------------- |
| `app:token`           | 获取应用Token       | 使用AppKey+Secret换取应用Access Token | `POST /api/v1/open/token`              |
| `token:verify`        | 验证Token         | 验证用户身份Token的有效性                 | `POST /api/v1/open/token/verify`       |
| `user:read`           | 读取用户            | 查询和获取用户的基本信息                    | `GET /api/v1/open/users`               |
| `user:create`         | 创建用户            | 在指定租户下创建新的用户账号                  | `POST /api/v1/open/users`              |
| `user:update`         | 修改用户            | 更新现有用户的信息                       | `PUT /api/v1/open/users/:id`           |
| `user:status`         | 修改用户状态          | 启用/禁用用户账号                       | `PATCH /api/v1/open/users/:id/status`  |
| `permission:check`    | 校验权限            | 校验用户是否拥有指定权限                    | `POST /api/v1/open/permissions/check`  |
| `user:profile:read`   | 读取用户资料          | 通过用户Token读取用户的完整资料信息            | `GET /api/v1/open/users/me/profile`    |
| `user:profile:update` | 修改用户资料          | 通过用户Token更新用户的个人资料信息            | `PUT /api/v1/open/users/me/profile`    |
| `wechat:access_token` | 获取微信AccessToken | 获取微信小程序接口调用凭证                   | `GET /api/v1/open/wechat/access_token` |
| `wechat:phone`        | 获取微信用户手机号       | 通过微信小程序临时code获取手机号              | `POST /api/v1/open/wechat/phone`       |

**权限说明**:

- 应用默认只能调用已绑定的权限接口，通过管理后台「应用管理 → 权限配置」绑定
- 管理员角色（code=admin）自动拥有全部权限
- 自定义角色可在管理后台「角色管理」中创建并分配权限

***

## 附录：用户类型说明

| 用户类型 | 值          | 说明         |
| ---- | ---------- | ---------- |
| 内部用户 | `internal` | 企业内部员工     |
| 外部用户 | `external` | 外部访客、合作伙伴等 |

***

## 附录：社交登录Provider

| Provider | 值            | 说明       |
| -------- | ------------ | -------- |
| 微信小程序    | `wechat_mp`  | 微信小程序登录  |
| 微信网页     | `wechat_web` | 微信网页授权登录 |
| 钉钉       | `dingtalk`   | 钉钉登录     |
| 飞书       | `feishu`     | 飞书登录     |

***

