# 统一账户认证服务 - OpenAPI 客户端示例

为开发者提供多语言示例代码，帮助您快速对接统一账户认证服务。

## 目录

- [项目介绍](#项目介绍)
- [快速开始](#快速开始)
  - [Node.js](#nodejs)
  - [Python](#python)
  - [PHP](#php)
- [获取 AppKey 和 AppSecret](#获取-appkey-和-appsecret)
- [API 接口文档](#api-接口文档)

## 项目介绍

本目录包含了以下语言的 SDK 示例：

| 语言          | 文件                                                                                                                                       | 说明                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| Node.js/浏览器 | [js/openapi\_client.js](file:///e:/framework/Unified%20account%20identification%20service/code/client_demo/js/openapi_client.js)         | 支持 Node.js 环境和浏览器环境 |
| Python      | [python/openapi\_client.py](file:///e:/framework/Unified%20account%20identification%20service/code/client_demo/python/openapi_client.py) | 基于 `requests` 库实现   |
| PHP         | [php/openapi\_client.php](file:///e:/framework/Unified%20account%20identification%20service/code/client_demo/php/openapi_client.php)     | 零依赖实现，使用 PHP 原生函数   |

## 快速开始

### Node.js

```bash
cd js/

# 编辑 demo.js 中的 APP_KEY 和 APP_SECRET

# 运行示例
node demo.js
```

**使用方式：**

```javascript
const { OpenAPIClient } = require('./openapi_client');

const client = new OpenAPIClient(
  '你的APP_KEY',
  '你的APP_SECRET',
  'http://localhost:8000'
);

// 验证 Token
const result = await client.verifyToken('用户JWT_TOKEN');

// 查询用户列表
const users = await client.listUsers();
```

### Python

```bash
cd python/
pip install requests

# 编辑 openapi_client.py 中的 APP_KEY 和 APP_SECRET

# 运行示例
python3 openapi_client.py
```

**使用方式：**

```python
from openapi_client import OpenAPIClient

client = OpenAPIClient(
  app_key="你的APP_KEY",
  app_secret="你的APP_SECRET",
  base_url="http://localhost:8000"
)

# 验证 Token
result = client.verify_token("用户JWT_TOKEN")

# 查询用户列表
users = client.list_users()
```

### PHP

```bash
cd php/

# 编辑 openapi_client.php 中的 $appKey 和 $appSecret

# 运行 OpenAPI 调用示例
php openapi_client.php

# 运行微信扫码登录示例
php -S localhost:8080 -t ./
# 然后浏览器访问 http://localhost:8080/php/wechat_login.php
```

**OpenAPI 基础使用方式：**

```php
require_once 'openapi_client.php';

$client = new OpenAPIClient(
  '你的APP_KEY',
  '你的APP_SECRET',
  'http://localhost:8000'
);

// 验证 Token
$result = $client->verifyToken('用户JWT_TOKEN');

// 查询用户列表
$users = $client->listUsers();
```

**微信扫码登录示例：**

微信扫码登录（`wechat_web`）的完整示例文件：[php/wechat_login.php](file:///e:/framework/Unified%20account%20identification%20service/code/client_demo/php/wechat_login.php)

该文件演示了完整的 OAuth2 授权码流程：

1. 用户点击"微信登录"，跳转到微信授权页面
2. 用户使用微信扫码授权
3. 微信回调携带 `code` 跳回本页面
4. 调用 `socialLogin('wechat_web', $code, $appKey)` 完成登录
5. 使用返回的 `access_token` 获取用户信息

**前置条件（使用微信登录前需完成）：**

1. 在 [微信开放平台](https://open.weixin.qq.com) 注册网页应用，获取 AppID
2. 在微信开放平台配置授权回调域名（指向你的服务器）
3. 在"统一账号识别管理平台"的应用配置中，填写微信网页应用的 AppID 和 AppSecret
4. 编辑 `wechat_login.php`，填入你的 `WECHAT_APP_ID` 和 `CALLBACK_URL`

```php
// wechat_login.php 配置区示例
define('APP_KEY', '你的APP_KEY');
define('APP_SECRET', '你的APP_SECRET');
define('WECHAT_APP_ID', 'wx1234567890abcdef');   // 微信开放平台 AppID
define('CALLBACK_URL', 'http://your-domain.com/php/wechat_login.php');  // 回调地址
```

## 获取 AppKey 和 AppSecret

1. 登录到“**统一账号识别管理平台**”。
2. 进入「应用管理」->「新建应用」
3. 填写应用信息后，点击「保存」
4. 页面会显示 `AppKey` 和 `AppSecret`，请妥善保存（仅显示一次）

## API 接口文档

完整 API 文档请查看官方API说明文档。

### 开放 API（OpenAPI）

| 方法                                              | 说明             |
| ----------------------------------------------- | -------------- |
| `verifyToken(token)`                            | 验证用户 Token 有效性 |
| `listUsers()`                                   | 查询用户列表         |
| `createUser(username, password, userType, ...)` | 创建新用户          |
| `getUser(userId)`                               | 获取用户详情         |
| `updateUser(userId, data)`                      | 更新用户信息         |
| `toggleUserStatus(userId, status)`              | 启用/禁用用户        |
| `checkPermission(userId, permissionCode)`       | 检查用户权限         |

### 用户认证 API（Auth）

| 方法                                                      | 说明         |
| ------------------------------------------------------- | ---------- |
| `login(username, password)`                             | 用户名密码登录    |
| `smsSend(phone)`                                        | 发送短信验证码    |
| `smsLogin(phone, code)`                                 | 短信验证码登录    |
| `socialLogin(provider, code)`                           | 社交登录       |
| `refreshToken(refreshToken)`                            | 刷新 Token   |
| `getUserinfo(accessToken)`                              | 获取当前登录用户信息 |
| `updateUserinfo(accessToken, data)`                     | 更新个人信息     |
| `changePassword(accessToken, oldPassword, newPassword)` | 修改密码       |
| `logout(accessToken)`                                   | 登出         |

## 签名机制

所有 OpenAPI 请求均需要验证签名，签名流程如下：

1. 计算 `app_secret_hash = SHA256(app_secret)`
2. 生成当前 Unix 时间戳 `timestamp`（秒）
3. 构造签名原文：`"{}" + timestamp`
4. 使用 `HMAC-SHA256` 计算签名：`signature = HMAC-SHA256(app_secret_hash, 签名原文)`
5. 在请求头中携带：
   - `X-App-Key`: 应用的 AppKey
   - `X-Timestamp`: 当前时间戳
   - `X-Signature`: 生成的签名

## 常见问题

**1. 如何切换环境？**

在初始化客户端时，修改 `base_url` 参数即可：

```javascript
const client = new OpenAPIClient(
  APP_KEY,
  APP_SECRET,
  'https://api.yourcompany.com'  // 正式环境地址
);
```

**2. 安全建议**

- 不要在前端（浏览器）暴露 AppSecret
- 生产环境中 AppSecret 建议使用环境变量或配置文件存储
- 定期更换 AppSecret

