> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-10-17 14:10:00
> **当前版本**: V_1.0
> **适用对象**: 对接本服务的 AI Agent、Web 管理后台前端开发者、企业管理员
> **核心目标**: 提供 `/api/v1/admin/*` 全部企业管理后台接口的完整清单与认证要求
> **文档简略描述**: 本子文档是主路由 `AI_API_ROUTING_GUIDE_v1.0.md` 的 C 类子文档。

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
| POST           | `/users/<id>/reset-password`   | 重置密码           |
| GET/PUT        | `/users/<id>/roles`           | 用户角色管理         |
| GET/PUT        | `/users/<id>/profile`          | 用户资料管理         |
| GET/POST       | `/users/import`               | 用户导入           |
| GET            | `/users/export`               | 用户导出           |

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

> 权限配置链路: `应用 → 角色（AppRoleBinding）→ 权限`。绑定入口在 `PUT /applications/<id>` 时传入 `role_ids`。

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

---

## 3. 文档版本与变更记录

| 版本    | 日期         | 变更说明                          |
| ----- | ---------- | ----------------------------- |
| V_1.0 | 2026-10-17 | 从原 README 概览拆出独立子文档              |
