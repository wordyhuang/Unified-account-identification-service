> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-11-26 16:35:00
> **当前版本**: V_1.7
> **适用对象**: 对接本服务的 AI Agent、Web 管理后台前端开发者、企业管理员
> **核心目标**: 提供 `/api/v1/admin/*` 全部企业管理后台接口的完整清单与认证要求
> **文档简略描述**: 在 V_1.6 基础上做租户隔离加固：应用角色绑定的 `role_ids` 必须属于当前租户（跨租户返回 400），管理端对非用户 Token 返回 401

---

# 企业管理后台 API 子文档 `/api/v1/admin/`

> AI 对接前请先读本文件。

## 大纲

- [1. 认证要求](#1-认证要求)
- [2. 接口清单](#2-接口清单)
- [3. 文档版本与变更记录](#3-文档版本与变更记录)

---

## 1. 认证要求

- Header: `Authorization: Bearer <access_token>`
- 用户必须满足 `is_staff = True`
- 数据范围: 当前管理员所属租户内的数据

---

## 2. 接口清单

### 2.1 仪表盘

| 方法  | 路径                      | 功能        |
| --- | ----------------------- | --------- |
| GET | `/stats`                | 仪表盘统计     |
| GET | `/recent-activities`    | 最近操作动态    |
| GET | `/stats/login-trend`    | 登录趋势      |
| GET | `/stats/login-distribution` | 登录方式分布    |
| GET | `/stats/user-growth`    | 用户增长趋势    |
| GET | `/stats/user-type-distribution` | 用户类型分布    |
| GET | `/stats/active-users`   | 活跃用户统计    |

### 2.2 用户管理

| 方法             | 路径                            | 功能             |
| -------------- | ----------------------------- | -------------- |
| GET/POST       | `/users`                      | 用户列表 / 创建       |
| GET/PUT/DELETE | `/users/<id>`                 | 用户详情 / 编辑 / 删除  |
| PATCH          | `/users/<id>/status`           | 用户状态切换         |
| POST           | `/users/<id>/reset-password`   | 重置密码（见下方说明）    |
| GET/PUT        | `/users/<id>/roles`           | 用户角色管理         |
| GET/PUT        | `/users/<id>/profile`          | 用户资料管理         |
| GET/POST       | `/users/import`               | 用户导入           |
| GET            | `/users/export`               | 用户导出           |

> **重置密码 ✅ V_1.1 更新**：`POST /users/<id>/reset-password` 不再接收 `new_password` 参数。服务端生成 12 位随机密码（含大写/小写/数字/符号），响应 `data` 为 `{ "password": "...", "must_change_password": true }`，随机密码**仅本次响应返回一次**；同时该用户被置为强制改密（下次登录后仅可访问个人信息与改密接口，其余请求 403/-10104，见 API_01_AUTH §4）。用户序列化（GET /users）新增 `must_change_password` 字段。

### 2.3 应用管理

| 方法       | 路径                                     | 功能                |
| -------- | -------------------------------------- | ----------------- |
| GET/POST | `/applications`                        | 应用列表 / 创建         |
| GET/PUT  | `/applications/<id>`                    | 应用详情 / 编辑         |
| PATCH    | `/applications/<id>/status`             | 应用状态切换            |
| POST     | `/applications/<id>/regenerate-secret` | 重新生成应用密钥（需用户主动点击） |
| GET      | `/applications/<id>/secret`            | 只读查看当前密钥          |
| GET      | `/applications/<id>/permissions`         | 查看当前应用拥有的权限       |
| GET      | `/applications/<id>/api-stats`           | 应用 API 调用统计       |

> 权限配置链路: `应用 → 角色（AppRoleBinding）→ 权限`。绑定入口在 `PUT /applications/<id>` 与 `PUT /applications/<id>/roles` 传入 `role_ids`。**角色必须属于当前租户**：存在跨租户或不存在角色时整批拒绝，返回 400 `-10602` 并列出非法 id。

**两个地址白名单 ✅ V_1.2 更新（原共用 callback_urls，现已按用途分离）**：

| 字段 | 类型 | 语义 | 消费方 |
|---|---|---|---|
| `callback_urls` | URL 列表 | **授权回调地址**（精确 URL 匹配） | 仅 OAuth2 授权码流程的 `redirect_uri` 白名单 |
| `cors_origins` | URL/域 列表 | **跨域/页面对接域**（origin 级匹配） | 动态 CORS 放行；`registration_page_url` / `registration_success_url` / `webhook_url` 的同源信任基准 |

> 存量数据：迁移 0010 已自动把原 `callback_urls` 的 origin 复制到 `cors_origins`，存量应用行为不变。创建/编辑时两个字段均可独立传参，应用序列化同时返回两者。

**邀请注册页接入（✅ V_1.2 新增）**：创建/编辑应用可直接传以下三个字段，序列化同样返回：

| 字段 | 类型 | 说明 |
|---|---|---|
| `registration_page_url` | URL(512) | 接入方自建注册页；绑定本应用的邀请码短链会 302 到此地址 |
| `registration_success_url` | URL(512) | 注册成功后浏览器跳转地址 |
| `webhook_url` | URL(512) | 注册成功事件回调地址 |

校验规则：三个地址非空时，其 origin 必须命中该应用 `cors_origins` 白名单（否则 400「…必须与跨域/页面对接域白名单同源，且不能指向内网地址」）；生产环境（DEBUG=False）拒绝内网/回环地址。

### 2.4 角色管理

| 方法      | 路径            | 功能       |
| ------- | ------------- | -------- |
| GET/POST | `/roles`      | 角色列表 / 创建 |
| GET/PUT | `/roles/<id>` | 角色详情 / 编辑 |

### 2.5 部门管理

| 方法             | 路径                   | 功能        |
| -------------- | -------------------- | --------- |
| GET/POST       | `/departments`       | 部门列表（树形）/ 创建 |
| GET/PUT/DELETE | `/departments/<id>`  | 部门管理      |

### 2.6 审计 / 权限

| 方法   | 路径                    | 功能       |
| ---- | --------------------- | -------- |
| GET  | `/audit-logs`         | 审计日志列表    |
| GET  | `/audit-logs/export`   | 审计日志导出    |
| GET  | `/permissions`        | 权限列表      |

### 2.7 邀请码与资料补全码

邀请码用于自助注册，资料补全码用于引导用户自助补全资料；均支持短链与二维码分发，详见设计文档 5.16 与 API_05_PUBLIC。

| 方法               | 路径                              | 功能                          |
| ---------------- | ------------------------------- | --------------------------- |
| GET/POST         | `/invite-codes`                 | 邀请码列表（search/status/分页）/ 创建 |
| GET/PATCH/DELETE | `/invite-codes/<id>`            | 邀请码详情 / 配置修改 / 删除 |
| GET/POST         | `/profile-completion-codes`     | 补全码列表 / 创建                  |
| GET/PATCH/DELETE | `/profile-completion-codes/<id>` | 补全码详情 / 配置修改 / 删除 |
| GET              | `/profile-completion-fields`    | 补全字段白名单（{name,label,type} 列表，供创建时勾选） |

**创建/修改邀请码（✅ V_1.2 扩展）**：

```json
{
  "remark": "可选备注",
  "user_type": "external",
  "allowed_phones": ["13800001111"],
  "max_uses": 10,
  "expires_at": "2026-12-31T23:59:59",
  "fields": [{ "key": "real_name", "required": true }],
  "app_id": null
}
```

| 字段 | 说明 |
|---|---|
| `allowed_phones` | 注册手机白名单，为 `null` 不限制；格式错误 400 |
| `max_uses` | 防刷必填语义：不传默认 10；范围 1-1000 |
| `fields` | **注册字段覆盖**：`null` 继承租户默认；数组则完全覆盖。元素 `{key, required}`，`key` 必须在字段白名单内；`username/password` 为固定项不可配置（传了返回 400） |
| `app_id` | 绑定的接入应用 id（须属当前租户且启用）；`null` 使用 UAIS 内置注册页 |

列表/详情序列化新增：`fields`、`app_id`、`app_name`、`registration_mode`（`builtin` / `app`）。

**补全码创建入参**：

```json
{
  "mode": "single",
  "user_id": 1,
  "fields": ["nickname", "real_name"],
  "allow_repeated": false,
  "max_uses": null,
  "expires_at": "2026-12-31T23:59:59"
}
```

- `mode=single`：必须传 `user_id`（同租户用户）；`allow_repeated=false` 时提交一次后码自动失效。
- `mode=shared`：不能绑定用户；用户先短信验证身份再补全（多人通用）。
- `fields` 必须为 `/profile-completion-fields` 返回白名单的子集。
- 响应含 `code`、`short_code`、`field_labels`、`page_url`、`short_url`。

### 2.8 邀请注册页配置（✅ V_1.2 新增）

| 方法 | 路径 | 功能 |
|---|---|---|
| GET/PUT | `/invite-brand` | 读取/保存当前租户的注册页品牌、默认字段与文案 |
| GET/PUT | `/completion-brand` | 读取/保存资料补全页租户级默认外观（7 项，逐项回退） |
| GET | `/invite-fields` | 可配置字段注册表（含手机号），供前端渲染多选项 |

**GET/PUT `/invite-brand`**

```json
{
  "brand_name": "演示企业",
  "welcome": "欢迎加入",
  "theme_color": "#0F766E",
  "logo": "data:image/png;base64,...",
  "fields": [{ "key": "real_name", "required": true }, { "key": "nickname", "required": false }],
  "submit_text": "立即加入",
  "success_text": "",
  "agreement": "我已阅读并同意服务协议"
}
```

| 字段 | 约束 |
|---|---|
| `brand_name` | ≤128 字；空则注册页回退租户名称 |
| `welcome` | ≤255 字 |
| `theme_color` | `#RRGGBB` 格式，违规返回 400 |
| `logo` | 图片 URL 或 data URI，长度 ≤ 300000（约 220KB） |
| `fields` | `null` 表示系统默认（昵称 + 手机号）；数组元素 `{key, required}`，`key` 必须在 `/invite-fields` 白名单内；`username/password` 不可配置 |
| `submit_text` | ≤32 字，空回退「注册账号」 |
| `success_text` | ≤255 字，支持 `{username}` 占位 |
| `agreement` | ≤255 字，空则不显示协议勾选 |

保存会写审计日志 `admin.invite_brand.update`。

**GET/PUT `/completion-brand`**

```json
{
  "appearance": {
    "logo": "", "title": "资料完善", "welcome": "",
    "theme_color": "#FF6600", "background": "",
    "button_text": "提交资料", "footer_text": ""
  },
  "appearance_effective": {
    "logo": "", "title": "资料完善", "welcome": "",
    "theme_color": "#FF6600", "background": "",
    "button_text": "提交资料", "footer_text": ""
  }
}
```

- 语义：资料补全页的**租户级默认外观**。生效优先级为 码级 `appearance` > 本租户 `completion_appearance` > 邀请品牌字段（存量回退）> 系统内置默认，字段级回退
- `PUT` 只存显式配置项；传 `{}` 或 `null` 表示清除租户级覆盖，回到邀请品牌字段与系统默认
- 合法键 7 个：`logo` / `title` / `welcome` / `theme_color` / `background` / `button_text` / `footer_text`，校验规则与码级 `appearance` 完全一致（非法键忽略、空值删除）
- 校验：`theme_color` 必须 `#RRGGBB`；`background` 为 `#RRGGBB` 或 https 图片 / data URI；图片长度 ≤ 300000（约 220KB）；`title` ≤50、`welcome` ≤100、`button_text` ≤20、`footer_text` ≤100 字
- `GET` 额外返回 `appearance_effective`，即当前合并后的最终生效值，供前端回显
- 保存写审计日志 `admin.completion_brand.update`

**GET `/invite-fields`**

```json
{
  "code": 0,
  "data": {
    "items": [
      { "key": "nickname", "label": "昵称", "type": "text" },
      { "key": "gender", "label": "性别", "type": "select",
        "options": [{ "value": "male", "label": "男" }] },
      { "key": "phone", "label": "手机号", "type": "text" }
    ]
  }
}
```

返回 18 项：资料字段白名单 17 项 + 特殊字段 `phone`。

### 2.9 管理端登录（✅ V_1.5 新增）

| 方法   | 路径                     | 功能                     |
| ---- | ---------------------- | ---------------------- |
| POST | `/api/v1/admin/login`  | 管理后台登录（超级管理员或租户管理员） |

请求体：

```json
{ "username": "alice", "password": "******", "tenant_id": 1 }
```

`tenant_id` 为可选参数，仅在完成租户选择后传入。处理规则：

1. 先校验超级管理员环境变量凭据，命中则直接返回超管 Token；
2. 普通账号按 `username` 查询（不同租户允许同名），再按密码收窄候选：
   - 恰好一个账号密码匹配 → 直接登录；
   - 多个租户的**管理员**账号密码匹配 → 返回 HTTP 200、`code=-10204`，`data.tenants` 为可选租户列表，前端展示租户选择后带 `tenant_id` 重新提交；
   - 仅匹配到非管理员账号 → `-10201 非管理员无权登录管理后台`；
   - 密码均不匹配 → `-10105 用户名或密码错误`；
   - 指定了 `tenant_id` 但该租户下无此用户名 → `-10101 用户不存在`。

多租户响应示例：

```json
{
  "code": -10204,
  "message": "该用户名在多个租户中存在，请选择租户后登录",
  "data": {
    "tenants": [
      { "tenant_id": 1, "tenant_name": "乾标" },
      { "tenant_id": 2, "tenant_name": "默认企业" }
    ],
    "request_id": "req-..."
  }
}
```

> OAuth2 授权登录页（`/oauth/login`）**按应用所属租户限定**：发起授权时 `app_id` 已写入会话，登录仅在 `app.tenant_id` 范围内匹配用户名，因此同名用户不会产生歧义（无需租户选择）。同时三重拦截跨租户授权：登录页限定租户、`authorize`/`authorize_confirm` 校验已登录用户与应用同租户、`token_exchange` 校验授权码用户与应用同租户（不通过返回 403 `-10201`）。

---

## 3. 文档版本与变更记录

| 版本    | 日期         | 变更说明                          |
| ----- | ---------- | ----------------------------- |
| V_1.0 | 2026-10-17 | 从原 README 概览拆出独立子文档              |
| V_1.1 | 2026-11-25 | reset-password 改为服务端随机密码（仅响应返回一次+强制改密）；用户序列化加 must_change_password；新增 §2.7 邀请码/资料补全码管理与字段白名单接口 |
| V_1.2 | 2026-11-25 | 应用管理新增注册页三个地址；邀请码支持 `fields` 覆盖与 `app_id` 绑定，序列化加 registration_mode；新增 §2.8 `invite-brand` / `invite-fields` |
| V_1.3 | 2026-11-26 | 新增 `completion-brand` 接口（资料补全页租户级默认外观）；明确外观回退链：码级 > 补全页租户默认 > 邀请品牌字段 > 系统默认 |
| V_1.4 | 2026-11-26 | 回调地址按用途拆分：`callback_urls` 收窄为 OAuth2 redirect_uri 白名单；新增 `cors_origins` 管 CORS 与注册页/Webhook 同源信任基准（§2.3）；迁移 0010 自动复制存量 origin |
| V_1.5 | 2026-11-26 | 新增 §2.9 管理端登录：跨租户同名用户按密码收窄候选，多租户命中返回 `-10204` 与候选租户列表，可选择后带 `tenant_id` 重试；OAuth2 登录页同步支持租户选择 |
| V_1.6 | 2026-11-26 | OAuth2 登录改为按应用所属租户限定（同名不再歧义）；`authorize`、`authorize_confirm`、`token_exchange` 增加用户与应用同租户校验，拦截跨租户授权 |
| V_1.7 | 2026-11-26 | 租户隔离加固：应用角色绑定的 `role_ids` 校验必须属于当前租户（跨租户返回 400）；管理端中间件对非用户 Token 返回 401 |
