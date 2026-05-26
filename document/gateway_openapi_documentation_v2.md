# 统一账户认证服务 - API对接文档

## 概述

欢迎使用统一账户认证服务！本文档为外部开发者提供完整的API对接指南，帮助您快速集成统一认证能力。

**服务地址**: `http://localhost:8000`（开发环境）

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

```python
import hmac
import hashlib

# 签名公式
signature = hmac.new(
    app_secret.encode('utf-8'),
    (timestamp + request_body).encode('utf-8'),
    hashlib.sha256
).hexdigest()
```

**注意事项**:

- 请求体为空时，签名仅使用timestamp
- timestamp必须为字符串格式
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

| 参数 | 必填 | 说明         |
| -- | -- | ---------- |
| 无  | -  | 不支持分页和搜索参数 |

**成功响应** (200):

```json
{
    "code": 0,
    "message": "success",
    "data": {
        "users": [
            {
                "id": 1,
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
    "code": 4001,
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
        "permission_code": "user.view",
        "has_permission": true
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
    "code": 4001,
    "message": "密码错误"
}
```

**失败响应** (403):

```json
{
    "code": 4003,
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
    "phone": "string (必填，最大20字符，中国大陆手机号)"
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
| `access_token`  | string | JWT Token，有效期默认30分钟   |
| `refresh_token` | string | 刷新Token，有效期24小时，一次性使用 |
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
    "code": "string (必填，最大512字符，第三方授权码)"
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
    "code": 4006,
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
    "code": 4001,
    "message": "原密码错误"
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

***

## 对接示例

### Python示例

```python
import requests
import time
import hmac
import hashlib

APP_KEY = "your_app_key"
# 注意：此处需使用 app_secret 的 SHA256 哈希值进行签名
APP_SECRET_HASH = hashlib.sha256("your_app_secret".encode()).hexdigest()
BASE_URL = "http://localhost:8000"

def generate_signature(timestamp, body_str=""):
    message = f"{body_str}{timestamp}".encode("utf-8")
    return hmac.new(
        APP_SECRET_HASH.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()

def verify_token(user_token):
    timestamp = str(int(time.time()))
    body = '{"token":"%s"}' % user_token
    signature = generate_signature(timestamp, body)
    
    headers = {
        "Content-Type": "application/json",
        "X-App-Key": APP_KEY,
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/open/verify_token",
        headers=headers,
        data=body
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
// 注意：此处需使用 app_secret 的 SHA256 哈希值进行签名
const APP_SECRET_HASH = crypto.createHash('sha256').update('your_app_secret').digest('hex');
const BASE_URL = 'http://localhost:8000';

function generateSignature(timestamp, bodyStr = '') {
    const message = `${bodyStr}${timestamp}`;
    return crypto
        .createHmac('sha256', APP_SECRET_HASH)
        .update(message)
        .digest('hex');
}

async function verifyToken(userToken) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const body = JSON.stringify({ token: userToken });
    const signature = generateSignature(timestamp, body);
    
    const response = await fetch(`${BASE_URL}/api/v1/open/verify_token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-App-Key': APP_KEY,
            'X-Timestamp': timestamp,
            'X-Signature': signature
        },
        body: body
    });
    
    return response.json();
}

// 使用示例
verifyToken('user_jwt_token').then(console.log);
```

***

## 最佳实践

### 1. Token管理

- 将access\_token存储在安全的地方（如HttpOnly Cookie）
- 设置合理的Token过期时间
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
- **文档版本**: v2.0
- **最后更新**: 2024年

***

## 附录：权限编码列表

| 权限编码              | 权限名称 | 说明        |
| ----------------- | ---- | --------- |
| `user.view`       | 用户查看 | 查看用户列表和详情 |
| `user.create`     | 用户创建 | 创建新用户     |
| `user.update`     | 用户修改 | 修改用户信息    |
| `user.delete`     | 用户删除 | 删除用户      |
| `user.status`     | 用户状态 | 启用/禁用用户   |
| `app.view`        | 应用查看 | 查看应用列表    |
| `app.create`      | 应用创建 | 创建应用      |
| `role.view`       | 角色查看 | 查看角色列表    |
| `role.create`     | 角色创建 | 创建角色      |
| `permission.view` | 权限查看 | 查看权限列表    |

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

