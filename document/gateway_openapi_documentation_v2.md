# 统一账户认证服务 - API对接文档

## 概述

欢迎使用统一账户认证服务！本文档为外部开发者提供完整的API对接指南，帮助您快速集成统一认证能力。

**服务地址**: `http://localhost:8000`（开发环境）

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
 │              │                  │ 生成Access Token（2小时）
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
 │                │                     │ 生成新的Access Token
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
 ├─ 准备请求参数
 │
 ├─ 生成签名─────────────┐
 │                      │
 │  签名步骤:           │
 │  1. app_secret做SHA256哈希
 │  2. 签名 = HMAC-SHA256(哈希值, "{}" + timestamp)
 │
 ├─ 发送请求────────────>│
 │  请求头:
 │  - X-App-Key: 应用Key
 │  - X-Timestamp: Unix时间戳
 │  - X-Signature: 签名
 │
 │                      ├─ 验证应用Key
 │                      ├─ 验证时间戳（时差≤5分钟）
 │                      ├─ 验证签名
 │                      │
 │                      ├─ 执行业务逻辑
 │
 │<──响应数据───────────┤
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

### 第二步：选择认证方式

根据您的使用场景选择合适的认证方式：

| 场景    | 认证方式             | 适用接口                                       |
| ----- | ---------------- | ------------------------------------------ |
| 服务端调用 | 应用级认证（AppKey+签名） | `/api/v1/open/*`                           |
| 用户操作  | 用户Token认证        | `/api/v1/admin/*`, `/api/v1/auth/userinfo` |
| 用户登录  | 账号密码/短信验证码/社交登录  | `/api/v1/auth/*`                           |

### 第三步：发起请求

```bash
# 示例：验证Token
curl -X POST http://localhost:8000/api/v1/open/verify_token \
  -H "Content-Type: application/json" \
  -H "X-App-Key: YOUR_APP_KEY" \
  -H "X-Timestamp: $(date +%s)" \
  -H "X-Signature: YOUR_SIGNATURE" \
  -d '{"token": "user_jwt_token"}'
```

***

## 认证方式详解

### 1. 应用级认证（推荐服务端使用）

**适用接口**: `/api/v1/open/*` 下所有接口

**请求头要求**:

| 头名称           | 必填 | 说明                      |
| ------------- | -- | ----------------------- |
| `X-App-Key`   | ✅  | 应用密钥，管理后台获取             |
| `X-Timestamp` | ✅  | Unix时间戳（秒），与服务器时差不超过5分钟 |
| `X-Signature` | ✅  | HMAC-SHA256签名           |

**签名生成算法**:

签名固定使用 `{}` 作为消息前缀，不包含请求体内容。

```python
import hmac
import hashlib

# 第一步：对 app_secret 做 SHA256 哈希
APP_SECRET_HASH = hashlib.sha256(app_secret.encode()).hexdigest()

# 第二步：签名公式
signature = hmac.new(
    APP_SECRET_HASH.encode("utf-8"),
    ("{}" + timestamp).encode("utf-8"),
    hashlib.sha256
).hexdigest()
```

**注意事项**:

- 先对 `app_secret` 做 SHA256 哈希得到 `APP_SECRET_HASH`，再用它做 HMAC 签名
- 签名消息固定为 `{}{timestamp}`（空字典 + 时间戳），**不包含请求体内容**
- timestamp 必须为 Unix 秒级时间戳字符串
- 签名不区分大小写

### 2. 用户Token认证

**适用接口**: 用户操作相关接口

**请求头格式**:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**获取Token流程**:

1. 调用 `/api/v1/auth/login` 获取access\_token
2. 使用access\_token访问其他接口
3. Token过期时调用 `/api/v1/auth/refresh` 刷新

**Token有效期**:

| Token类型 | 有效期 | 说明 |
|-----------|--------|------|
| **Access Token** | **120分钟 (2小时)** | JWT访问令牌，用于API调用 |
| **Refresh Token** | **24小时** | 刷新令牌，用于获取新的Access Token，一次性使用 |

> **注意**: 建议在access_token到期前5-10分钟主动刷新，避免请求失败

***

## 开放API接口列表

### 验证Token

**接口地址**: `POST /api/v1/open/verify_token`

**功能描述**: 验证用户Token的有效性，常用于单点登录场景

**请求体**:

```json
{
    "token": "string (必填，用户的JWT Token，最大长度512)"
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
                "created_at": "2024-01-01T10:00:00"
            }
        ],
        "total": 100
    }
}
```

### 创建用户

**接口地址**: `POST /api/v1/open/users`

**功能描述**: 创建新用户，支持设置部门和角色

**请求体**:

```json
{
    "username": "string (必填，最大64字符)",
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
        "created_at": "2024-01-01T10:00:00"
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
        "created_at": "2024-01-01T10:00:00"
    }
}
```

### 更新用户信息

**接口地址**: `PUT /api/v1/open/users/{user_id}`

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

**接口地址**: `POST /api/v1/open/check_permission`

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

**接口地址**: `GET /api/v1/open/user/profile/by_token`

**功能描述**: 通过用户的JWT AccessToken获取其完整资料信息。Token可在 query string 或 request body 中传递。

**认证方式**: AppKey + Signature（应用级认证）

**权限码**: `user:profile:read`

**请求参数**:

| 参数 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| `user_token` | query/body | ✅ | 用户的JWT AccessToken，最大512字符 |

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

**接口地址**: `PUT /api/v1/open/user/profile/by_token`

**功能描述**: 通过用户的JWT AccessToken更新其个人资料。仅更新请求中携带的字段，未提供的字段保持不变。

**认证方式**: AppKey + Signature（应用级认证）

**权限码**: `user:profile:update`

**请求体**:

```json
{
    "user_token": "string (必填，用户的JWT AccessToken，最大512字符)",
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
        "user_token": ["该字段是必填项。"]
    }
}
```

***

## 微信小程序辅助接口

小程序可通过以下接口完成在服务端的辅助操作。所有接口使用 **应用级认证（AppKey + 签名）**，需要在管理后台为应用授予对应的权限。

### 获取微信 AccessToken

**接口地址**: `GET /api/v1/open/wechat/access_token`

**功能描述**: 获取微信小程序的接口调用凭证 `access_token`。系统按 `AppID` 自动缓存（缓存7000秒，微信官方有效期7200秒），缓存有效期内直接返回缓存值，不重复请求微信接口。

**认证方式**: AppKey + Signature（应用级认证）

**权限码**: `wechat:access_token`

**请求头**:

| 头名称 | 必填 | 说明 |
| --- | --- | --- |
| `X-App-Key` | ✅ | 应用密钥，管理后台获取 |
| `X-Timestamp` | ✅ | Unix时间戳（秒），与服务器时差不超过5分钟 |
| `X-Signature` | ✅ | HMAC-SHA256签名（同其他开放API签名规则） |

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

**接口地址**: `POST /api/v1/open/wechat/get_phone_number`

**功能描述**: 通过微信小程序 `getPhoneNumber` 接口返回的临时 `code`，获取用户绑定的真实手机号码。

**认证方式**: AppKey + Signature（应用级认证）

**权限码**: `wechat:phone`

**请求头**: 同开放API标准签名认证。

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

### 密码登录

**接口地址**: `POST /api/v1/auth/login`

**功能描述**: 用户使用用户名密码登录

**请求体**:

```json
{
    "username": "string (必填，最大64字符)",
    "password": "string (必填，最大256字符)"
}
```

**成功响应** (200) - 普通用户:

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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

### 短信登录

**接口地址**: `POST /api/v1/auth/sms/login`

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
③ 返回 JWT Token，后续请求携带 Authorization: Bearer {access_token}
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
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "user_id": 4,
        "is_new": false
    }
}
```

| 返回字段            | 类型     | 说明                    |
| --------------- | ------ | --------------------- |
| `access_token`  | string | JWT Token，有效期120分钟 |
| `refresh_token` | string | 刷新令牌，用于获取新的Access Token，有效期24小时，一次性使用 |
| `user_id`       | int    | 用户ID                  |
| `is_new`        | bool   | 是否为新注册用户              |

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
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "abc123def456...",
        "user_id": 3,
        "is_new": true
    }
}
```

### 刷新Token

**接口地址**: `POST /api/v1/auth/refresh`

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
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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

**接口地址**: `GET /api/v1/auth/userinfo`

**功能描述**: 获取当前登录用户信息

**认证方式**: Bearer Token

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
        "created_at": "2024-01-01T10:00:00"
    }
}
```

### 更新用户信息

**接口地址**: `PUT /api/v1/auth/userinfo`

**功能描述**: 更新当前登录用户的个人信息

**认证方式**: Bearer Token

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

**接口地址**: `PATCH /api/v1/auth/userinfo/password`

**功能描述**: 修改当前登录用户的密码

**认证方式**: Bearer Token

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

**接口地址**: `GET /api/v1/auth/profile`

**功能描述**: 获取当前登录用户的详细资料（扩展信息）

**认证方式**: Bearer Token

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

**接口地址**: `PUT /api/v1/auth/profile/update`

**功能描述**: 更新当前登录用户的详细资料

**认证方式**: Bearer Token

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

**功能描述**: 用户登出

**认证方式**: Bearer Token

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

| 错误码    | 含义       | HTTP状态码 | 处理建议                    |
| ------ | -------- | ------- | ----------------------- |
| 0      | 成功       | 200/201 | -                       |
| -10001 | Token已过期 | 401     | 使用refresh\_token刷新或重新登录 |
| -10002 | Token无效  | 401     | 重新登录获取新Token            |
| -10003 | 签名无效     | 401     | 检查签名算法和app\_secret      |
| -10101 | 用户不存在    | 404     | 确认用户ID或用户名是否正确          |
| -10102 | 用户已禁用    | 403     | 联系管理员启用账户               |
| -10103 | 用户访问被拒绝  | 403     | 检查用户应用访问权限              |
| -10201 | 权限不足     | 403     | 确认用户是否有相应权限             |
| -10202 | 无接口调用权限  | 403     | 确认应用是否绑定了该接口权限          |
| -10301 | 短信验证码错误  | 400     | 检查验证码是否正确               |
| -10302 | 短信验证码已过期 | 400     | 重新获取验证码                 |
| -10303 | 短信发送失败   | 500     | 稍后重试，检查短信服务配置           |
| -10401 | 限流超限     | 429     | 稍后重试或联系管理员调整限流配置        |
| -10501 | AppKey无效 | 401     | 确认X-App-Key是否正确         |
| -10502 | 应用已禁用    | 403     | 联系管理员启用应用               |
| -10601 | 缺少必要参数   | 400     | 检查请求参数是否完整              |
| -10602 | 参数格式错误   | 400     | 检查请求参数是否正确              |
| -10801 | 微信未配置    | 400     | 联系管理员配置微信 AppID/AppSecret |
| -10802 | 微信API调用失败 | 400     | 检查微信授权码是否正确或稍后重试      |

***

## 对接示例

### Python示例

```python
import requests
import time
import hmac
import hashlib

APP_KEY = "your_app_key"
# 签名使用 app_secret 的 SHA256 哈希值
APP_SECRET_HASH = hashlib.sha256("your_app_secret".encode()).hexdigest()
BASE_URL = "http://localhost:8000"

def generate_signature(timestamp):
    # 签名固定使用 "{}" + timestamp，不包含请求体
    message = f"{{}}{timestamp}".encode("utf-8")
    return hmac.new(
        APP_SECRET_HASH.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()

def verify_token(user_token):
    timestamp = str(int(time.time()))
    signature = generate_signature(timestamp)
    
    headers = {
        "Content-Type": "application/json",
        "X-App-Key": APP_KEY,
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/open/verify_token",
        headers=headers,
        json={"token": user_token}
    )
    return response.json()

# 使用示例
result = verify_token("user_jwt_token")
print(result)
```

### JavaScript示例

```javascript
const crypto = require('crypto');

const APP_KEY = 'your_app_key';
// 签名使用 app_secret 的 SHA256 哈希值
const APP_SECRET_HASH = crypto.createHash('sha256').update('your_app_secret').digest('hex');
const BASE_URL = 'http://localhost:8000';

function generateSignature(timestamp) {
    // 签名固定使用 "{}" + timestamp，不包含请求体
    return crypto
        .createHmac('sha256', APP_SECRET_HASH)
        .update('{}' + timestamp)
        .digest('hex');
}

async function verifyToken(userToken) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signature = generateSignature(timestamp);
    
    const response = await fetch(`${BASE_URL}/api/v1/open/verify_token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-App-Key': APP_KEY,
            'X-Timestamp': timestamp,
            'X-Signature': signature
        },
        body: JSON.stringify({ token: userToken })
    });
    
    return response.json();
}

// 使用示例
verifyToken('user_jwt_token').then(console.log);
```

***

## 最佳实践

### 1. Token管理

- 将access_token存储在安全的地方（如HttpOnly Cookie）
- **Access Token有效期为120分钟（2小时）**，建议在到期前5-10分钟主动刷新
- **Refresh Token有效期为24小时**，一次性使用，用于获取新的Access Token
- 定期刷新Token避免用户重新登录

### 2. 签名安全

- 不要在前端暴露app\_secret
- 使用HTTPS传输所有请求
- 定期轮换app\_secret

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
- **文档版本**: v2.1
- **最后更新**: 2026-05-26

***

## 附录：权限编码列表

> 以下为系统预置的 API 权限，通过管理命令 `python manage.py init_data` 初始化。
> 应用开通时需在管理后台绑定接口权限，未绑定的接口调用会返回 `-10202` 错误。

| 权限编码 | 权限名称 | 说明 | 对应接口 |
|---------|---------|------|---------|
| `token:verify` | 验证Token | 验证用户身份Token的有效性 | `POST /api/v1/open/verify_token` |
| `user:read` | 读取用户 | 查询和获取用户的基本信息 | `GET /api/v1/open/users` |
| `user:create` | 创建用户 | 在指定租户下创建新的用户账号 | `POST /api/v1/open/users` |
| `user:update` | 修改用户 | 更新现有用户的信息 | `PUT /api/v1/open/users/:id` |
| `user:status` | 修改用户状态 | 启用/禁用用户账号 | `PATCH /api/v1/open/users/:id/status` |
| `permission:check` | 校验权限 | 校验用户是否拥有指定权限 | `POST /api/v1/open/check_permission` |
| `user:profile:read` | 读取用户资料 | 通过用户Token读取用户的完整资料信息 | `GET /api/v1/open/user/profile/by_token` |
| `user:profile:update` | 修改用户资料 | 通过用户Token更新用户的个人资料信息 | `PUT /api/v1/open/user/profile/by_token` |
| `wechat:access_token` | 获取微信AccessToken | 获取微信小程序接口调用凭证 | `GET /api/v1/open/wechat/access_token` |
| `wechat:phone` | 获取微信用户手机号 | 通过微信小程序临时code获取手机号 | `POST /api/v1/open/wechat/get_phone_number` |

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

---

## 附录：数据模型

### 核心实体关系

```
租户(Tenant) ─── 部门(Department)
    │                  │
    ├── 应用(Application) ─── 回调地址白名单
    │      │
    │      ├── 应用权限绑定(AppRoleBinding)
    │      └── 调用统计(AppApiCallStat)
    │
    └── 用户(User) ─── 社交账号(SocialAccount)
           │              (微信/钉钉/飞书)
           ├── 用户资料(UserProfile)
           ├── 角色(Role) ←── 权限(ApiPermission)
           │      │
           │      └── 用户角色(UserRole)
           └── 审计日志(AuditLog)
```

### 表结构说明

#### 租户表 (tenant)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | `tenant_id` |
| `uuid` | string | UUID | - |
| `name` | string | 企业名称 | - |
| `slug` | string | 唯一标识 | - |
| `status` | bool | 启用状态 | - |
| `sms_provider` | string | 短信服务商 | - |

> 每个租户独立管理自己的用户、应用和角色，数据隔离。

#### 用户表 (user)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | `user_id` |
| `uuid` | string | UUID（不可变） | `uuid` |
| `tenant_id` | int | 所属租户 | `tenant_id` |
| `user_type` | string | internal/external | `user_type` |
| `username` | string | 用户名（唯一） | `username` |
| `email` | string | 邮箱 | `email` |
| `phone` | string | 手机号 | `phone` |
| `nickname` | string | 昵称 | `nickname` |
| `avatar` | string | 头像URL | `avatar` |
| `department` | string | 部门名称 | `department` |
| `dept_id` | int | 关联部门ID | - |
| `status` | int | 1=正常, 0=禁用 | `status` |
| `last_login_at` | datetime | 最后登录时间 | `last_login_at` |
| `is_superuser` | bool | 是否超级管理员 | `is_superuser` |
| `is_staff` | bool | 是否后台管理员 | `is_staff` |
| `created_at` | datetime | 创建时间 | `created_at` |

#### 用户资料表 (user_profile)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | `profile_id` |
| `user_id` | int | 关联用户 | - |
| `real_name` | string | 真实姓名 | `real_name` |
| `gender` | string | male/female/other | `gender` |
| `birthday` | date | 出生日期 | `birthday` |
| `id_card` | string | 身份证号 | `id_card` |
| `job_title` | string | 职位 | `job_title` |
| `employee_id` | string | 员工编号 | `employee_id` |
| `hire_date` | date | 入职日期 | `hire_date` |
| `work_email` | string | 工作邮箱 | `work_email` |
| `emergency_contact` | string | 紧急联系人 | `emergency_contact` |
| `tags` | json | 标签数组 | `tags` |
| `extra_data` | json | 扩展数据 | `extra_data` |

#### 应用表 (application)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | `app_id` |
| `uuid` | string | UUID | - |
| `tenant_id` | int | 所属租户 | - |
| `name` | string | 应用名称 | - |
| `app_key` | string | 应用Key（唯一） | `X-App-Key` |
| `app_secret_hash` | string | AppSecret的SHA256 | 签名验证 |
| `callback_urls` | json | 回调地址白名单 | - |
| `status` | bool | 启用状态 | - |

#### 授权码表 (auth_code)

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 授权码 |
| `app_id` | int | 所属应用 |
| `user_id` | int | 授权用户 |
| `redirect_uri` | string | 回调地址 |
| `state` | string | CSRF状态码 |
| `expires_at` | datetime | 过期时间（5分钟） |
| `is_used` | bool | 是否已使用 |

#### 角色表 (role)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | - |
| `tenant_id` | int | 所属租户 | - |
| `name` | string | 角色名称 | - |
| `code` | string | 角色编码 | `role_codes` |

#### 权限表 (api_permission)

| 字段 | 类型 | 说明 | API中对应 |
|------|------|------|-----------|
| `id` | int | 主键ID | - |
| `code` | string | 权限编码 | `permission_code` |
| `method` | string | HTTP方法 | - |
| `path` | string | API路径 | - |
| `category` | string | 分类 | - |

#### 用户-角色关联表 (user_role)

| 字段 | 说明 |
|------|------|
| `user_id` | 用户ID |
| `role_id` | 角色ID |

> 通过此关联实现用户权限控制，一个用户可以拥有多个角色。

#### 应用-权限绑定表 (app_role_binding)

| 字段 | 说明 |
|------|------|
| `app_id` | 应用ID |
| `permission_id` | 权限ID |

> 控制应用可以调用的API范围，未绑定的接口禁止调用。

#### 审计日志表 (audit_log)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键ID |
| `tenant_id` | int | 所属租户 |
| `actor_name` | string | 操作人 |
| `action` | string | 操作类型（如 login, user.create） |
| `resource_type` | string | 资源类型 |
| `resource_id` | int | 资源ID |
| `detail` | json | 操作详情 |
| `ip_address` | string | 来源IP |
| `created_at` | datetime | 操作时间 |

### API字段与数据库字段映射关系

```
API响应字段        数据库表.字段
─────────────────────────────────
user_id        →    user.id
uuid           →    user.uuid
tenant_id      →    user.tenant_id / application.tenant_id
username       →    user.username
user_type      →    user.user_type
status         →    user.status
profile_id     →    user_profile.id
role_codes     →    role.code
permission_code →   api_permission.code
app_id         →    application.id
app_key        →    application.app_key
```

