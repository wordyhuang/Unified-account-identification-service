> **文档创建时间**: 2026-10-17 14:10:00
> **最后修改时间**: 2026-10-17 14:10:00
> **当前版本**: V_1.0
> **适用对象**: 对接本服务的 AI Agent、平台运营方、超级管理员
> **核心目标**: 提供 `/api/v1/superadmin/*` 全部超级管理员接口的完整清单
> **文档简略描述**: 本子文档是主路由 `AI_API_ROUTING_GUIDE_v1.0.md` 的 D 类子文档。

---

# 超级管理员 API 子文档 `/api/v1/superadmin/`

> AI 对接前请先读本文件。

## 大纲

- [1. 认证要求](#1-认证要求)
- [2. 接口清单](#2-接口清单)
- [3. 文档版本与变更记录](#3-文档版本与变更记录)

---

## 1. 认证要求

- Header: `Authorization: Bearer <access_token>`
- 用户必须满足 `is_superuser = True`
- 可跨租户操作，需特别注意数据影响面

---

## 2. 接口清单

### 2.1 平台总览

| 方法  | 路径                    | 功能         |
| --- | --------------------- | ---------- |
| GET | `/global-stats`       | 平台总览统计     |
| GET | `/platform-config`    | 全局配置查看     |

### 2.2 租户管理

| 方法             | 路径                  | 功能         |
| -------------- | ------------------- | ---------- |
| GET/POST       | `/tenants`          | 租户列表 / 创建   |
| GET/PUT/DELETE | `/tenants/<id>`      | 租户管理       |

### 2.3 审计 / 统计

| 方法   | 路径                  | 功能         |
| ---- | ------------------- | ---------- |
| GET  | `/audit-logs`        | 全局审计日志    |
| GET  | `/audit-logs/export` | 审计日志导出     |
| GET  | `/api-stats`         | 全局 API 调用统计 |

### 2.4 模拟进入租户

| 方法   | 路径                        | 功能       |
| ---- | ------------------------- | -------- |
| POST | `/impersonate/<tenant_id>` | 模拟进入租户   |
| POST | `/impersonate/exit`       | 退出模拟模式   |

### 2.5 趋势 / 排行

| 方法  | 路径                                | 功能         |
| --- | --------------------------------- | ---------- |
| GET | `/stats/tenant-growth`           | 租户增长趋势     |
| GET | `/stats/tenant-activity-ranking` | 租户活跃度排行    |
| GET | `/stats/global-user-growth`      | 全局用户增长     |
| GET | `/stats/global-login-trend`      | 全局登录趋势     |
| GET | `/stats/global-login-distribution` | 全局登录分布     |
| GET | `/stats/app-call-ranking`        | 应用调用排行     |

---

## 3. 文档版本与变更记录

| 版本    | 日期         | 变更说明                     |
| ----- | ---------- | ------------------------ |
| V_1.0 | 2026-10-17 | 从原 README 概览拆出独立子文档         |
