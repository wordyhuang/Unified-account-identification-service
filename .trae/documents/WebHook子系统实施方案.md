# WebHook 子系统实施方案

> **创建时间**: 2026-07-07 16:00  
> **最后修改**: 2026-07-07 16:00  
> **版本**: V1.0  
> **适用对象**: 开发团队  
> **核心目标**: 在统一账号标识服务中增加异步 WebHook 推送子系统，支持第三方应用订阅和接收全量业务事件

---

## 一、需求概要

在统一账号标识服务中增加 WebHook 子系统，使得注册的第三方应用（Application）能够订阅并接收本系统中发生的业务事件推送。

### 决策记录

| 决策项 | 选择 | 理由 |
|---|---|---|
| 事件范围 | 全量业务事件 | 覆盖认证、用户管理、应用管理、权限、OAuth2 等所有可观察事件 |
| 推送方式 | 异步推送 | 不阻塞主 API 响应，引入 Celery + Redis |
| 配置层级 | 应用级别 | 每个 Application 独立配置自身 WebHook |
| 异步基础设施 | Celery + Redis | 功能成熟，支持定时重试、任务状态管理 |
| 安全机制 | Token + HMAC 签名 | Token 做身份识别，HMAC-SHA256 签名确保请求完整性和不可抵赖 |
| 管理方式 | 管理后台页面 | 在 admin-panel 中增加 WebHook 配置管理 CRUD |

---

## 二、当前状态分析

### 现有体系

- **Python Django 3.2 + DRF**，MySQL 数据库
- 9 个 Django App 模块：accounts, applications, openapi, oauth2, admin_panel, rbac, users, audit, tags
- `redis>=5.0` 已存在于 `requirements.txt` 中，但目前仅在开发环境使用 LocMemCache
- 无消息队列、无 Celery、无事件系统、无 WebHook 机制
- 管理后台 `admin_panel` 是 SPA 结构（`index.html` + `admin.js` + `admin.css`）
- API 响应格式统一：`{code, message, data}`
- 项目有 Docker 部署（`Dockerfile` + `docker-compose.yml`）

### 需要改动的地方

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `requirements.txt` | 修改 | 新增 `celery>=5.3` |
| `config/settings.py` | 修改 | 新增 Celery 配置、Redis 配置、INSTALLED_APPS 新增 webhooks |
| `config/celery.py` | 新建 | Celery 应用实例 |
| `config/__init__.py` | 修改 | 确保 Celery 自动加载 |
| `apps/webhooks/` | 新建 | 完整的 Django App |
| `apps/admin_panel/views.py` | 修改 | 新增 WebHook 管理视图 |
| `apps/admin_panel/urls.py` | 修改 | 新增 WebHook 管理路由 |
| `config/urls.py` | 修改 | 注册新路由 |
| `common/errors.py` | 修改 | 新增 WebHook 相关错误码 |
| `.env.example` | 修改 | 新增 Celery/Redis 配置项 |
| `docker-compose.yml` | 修改 | 新增 Redis 服务、Celery Worker 服务 |

---

## 三、详细设计方案

### 3.1 事件体系定义

事件用点号分隔的字符串标识，按模块划分：

```
# 认证事件
user.login               # 登录成功
user.login_failed        # 登录失败
user.logout              # 登出
user.token_refreshed     # Token 刷新

# 用户管理事件
user.created             # 用户创建
user.updated             # 用户信息更新
user.deleted             # 用户删除
user.password_changed    # 密码修改
user.status_changed      # 用户状态变更（启用/禁用）
user.social_bound        # 社交账号绑定
user.social_unbound      # 社交账号解绑

# 应用管理事件
application.created      # 应用创建
application.updated      # 应用更新
application.status_changed  # 应用状态变更
application.secret_regenerated  # 应用密钥重生成

# 权限事件
role.assigned            # 角色分配
role.revoked             # 角色解除
permission.changed       # 权限变更
user.role_changed        # 用户角色变更

# OAuth2 事件
oauth2.authorized        # OAuth2 授权成功
oauth2.token_issued      # OAuth2 Token 签发
```

### 3.2 数据模型

#### WebHookConfig

```python
class WebHookConfig(models.Model):
    app = models.ForeignKey("applications.Application", on_delete=models.CASCADE, related_name="webhook_configs")
    url = models.URLField(max_length=1024, verbose_name="WebHook URL")
    secret_token = models.CharField(max_length=128, verbose_name="签名密钥")
    events = CompatibleJSONField(null=True, blank=True, verbose_name="订阅事件列表", 
                                  help_text="null 表示接收全部事件，数组格式如 [\"user.login\", \"user.created\"]")
    is_active = models.BooleanField(default=True, verbose_name="启用状态")
    max_retries = models.PositiveSmallIntegerField(default=3, verbose_name="最大重试次数")
    timeout = models.PositiveSmallIntegerField(default=10, verbose_name="请求超时(秒)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhook_config"
        verbose_name = "WebHook 配置"
```

#### WebHookDeliveryLog

```python
class WebHookDeliveryLog(models.Model):
    STATUS_CHOICES = (
        ("pending", "待发送"),
        ("success", "发送成功"),
        ("failed", "发送失败"),
    )
    config = models.ForeignKey(WebHookConfig, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=64, db_index=True, verbose_name="事件类型")
    event_id = models.CharField(max_length=64, db_index=True, verbose_name="事件唯一ID")
    request_url = models.URLField(max_length=1024, verbose_name="请求URL")
    request_headers = CompatibleJSONField(null=True, blank=True, verbose_name="请求头")
    request_body = CompatibleJSONField(verbose_name="请求体")
    response_status = models.SmallIntegerField(null=True, blank=True, verbose_name="响应状态码")
    response_body = models.TextField(null=True, blank=True, verbose_name="响应体")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending", db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=1, verbose_name="尝试次数")
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name="下次重试时间")
    error_message = models.TextField(null=True, blank=True, verbose_name="错误信息")
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="耗时(毫秒)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "webhook_delivery_log"
        verbose_name = "WebHook 投递日志"
```

### 3.3 事件推送流程

```
业务代码 → dispatch_event() → 查询匹配的 WebHookConfig → 创建 DeliveryLog(待发送) 
         → 异步 Celery Task(send_webhook.delay()) → HTTP POST → 更新 DeliveryLog
```

**详细流程：**

1. **业务代码侧**：在各个业务模块的关键操作点调用 `dispatch_event(event_type, event_data, app=None)`
2. **调度器**：`dispatch_event()` 查询所有与 `app` 关联且 `is_active=True` 的 WebHookConfig，过滤出订阅了该事件类型的配置
3. **创建日志**：为每个匹配的配置创建一条 `WebHookDeliveryLog`，状态为 `pending`
4. **异步推送**：`send_webhook.delay(config_id, log_id)` 将任务加入 Celery 队列
5. **发送请求**：Celery Worker 执行 HTTP POST 到目标 URL
   - Header: `Content-Type: application/json`
   - Header: `X-WebHook-Event: {event_type}`
   - Header: `X-WebHook-Event-Id: {event_id}`
   - Header: `X-WebHook-Signature: {HMAC-SHA256(secret_token, body)}`
   - Header: `X-WebHook-Timestamp: {unix_timestamp}`
   - Body: 标准事件负载体
6. **更新日志**：根据响应结果更新状态、状态码、响应体、耗时等
7. **失败重试**：若失败且未达到 `max_retries`，设置 `next_retry_at`（指数退避：2^n 分钟）

### 3.4 事件负载格式

```json
{
  "event_type": "user.login",
  "event_id": "evt_xxxxxxxxxxxxxxxx",
  "event_time": "2026-07-07T15:30:00",
  "tenant_id": 1,
  "app_id": 1,
  "data": {
    "user_id": 123,
    "username": "zhangsan",
    "login_method": "password",
    "ip_address": "192.168.1.1"
  }
}
```

### 3.5 安全性设计

- **Secret Token**：每个 WebHookConfig 独立生成，存储在数据库中
- **HMAC-SHA256 签名**：使用 `secret_token` 对请求体进行 `HMAC-SHA256` 签名，通过 `X-WebHook-Signature` 请求头发送
- **时间戳防重放**：`X-WebHook-Timestamp` 头部携带发送时间，接收方可以拒绝时间差超过 5 分钟的回调
- **事件 ID 幂等**：`event_id` 全局唯一，接收方可用它做去重
- **敏感事件签名**：对涉及敏感数据的事件（密码变更、Token 签发等），使用系统级 `WEBHOOK_SYSTEM_SECRET` 额外签名，接收方可以验证签名确认事件确由本系统发出

### 3.6 Celery 集成

#### `config/celery.py`

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("unified_auth")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

#### 新增配置项

```python
# settings.py
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Shanghai"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30

# WebHook 系统密钥（用于敏感事件签名）
WEBHOOK_SYSTEM_SECRET = os.getenv("WEBHOOK_SYSTEM_SECRET", "")
```

### 3.7 文件变更清单

#### 新增文件

| 文件路径 | 说明 |
|---|---|
| `apps/webhooks/__init__.py` | App 初始化 |
| `apps/webhooks/models.py` | WebHookConfig + WebHookDeliveryLog 模型 |
| `apps/webhooks/tasks.py` | Celery 异步任务（send_webhook） |
| `apps/webhooks/dispatcher.py` | 事件调度器（dispatch_event 函数） |
| `apps/webhooks/signature.py` | HMAC 签名工具 |
| `apps/webhooks/event_types.py` | 事件类型常量定义 |
| `apps/webhooks/admin.py` | Django Admin 注册 |
| `apps/webhooks/apps.py` | Django AppConfig |
| `config/celery.py` | Celery 应用实例 |

#### 修改文件

| 文件路径 | 改动内容 |
|---|---|
| `requirements.txt` | 新增 `celery>=5.3,<6.0` |
| `config/__init__.py` | 添加 `from .celery import app as celery_app` |
| `config/settings.py` | INSTALLED_APPS 添加 webhooks；新增 Celery/Redis 配置项 |
| `config/urls.py` | 添加 `api/v1/admin/webhooks/` 路由 |
| `apps/admin_panel/urls.py` | 新增 WebHook 配置 CRUD 路由、投递日志查询路由 |
| `apps/admin_panel/views.py` | 新增 WebHook 管理视图函数 |
| `common/errors.py` | 新增 WebHook 相关错误码 |
| `.env.example` | 新增 Celery/Redis 相关环境变量 |
| `docker-compose.yml` | 新增 Redis 服务、Celery Worker 服务 |
| `Dockerfile` | 无改动（已基于 requirements.txt 安装依赖） |

#### 埋点变更（需要注入 dispatch_event 调用的文件）

以下已有业务代码需要在关键操作点插入 `dispatch_event()` 调用：

| 文件 | 埋点位置 |
|---|---|
| `apps/accounts/views.py` | 登录成功/失败、登出、Token刷新 |
| `apps/accounts/views.py` | 用户创建/更新/删除、状态变更、密码修改 |
| `apps/accounts/views.py` | 社交账号绑定/解绑 |
| `apps/applications/views.py` | 应用创建/更新/状态变更/密钥重生成（待确认是否有独立视图） |
| `apps/rbac/views.py` | 角色分配/解除（待确认视图位置） |
| `apps/oauth2/views.py` | OAuth2 授权成功、Token 签发 |

---

## 四、实施计划

### 阶段一：基础设施搭建

1. 创建 `apps/webhooks/` App 骨架
2. 定义模型 `WebHookConfig` 和 `WebHookDeliveryLog`
3. 创建 `config/celery.py`
4. 更新 `settings.py` 添加 Celery 配置和 `INSTALLED_APPS`
5. 更新 `requirements.txt` 添加 `celery`
6. 更新 `__init__.py`
7. 执行 migrate

### 阶段二：核心功能实现

1. 实现 `event_types.py` - 事件类型常量
2. 实现 `signature.py` - HMAC 签名工具
3. 实现 `dispatcher.py` - 事件调度器
4. 实现 `tasks.py` - Celery 异步任务（发送 + 重试逻辑）

### 阶段三：管理后台集成

1. 在 `admin_panel` 中添加 WebHook 配置管理的视图和路由
2. 在 `admin_panel` 中添加投递日志查看视图和路由
3. 更新前端（`admin.js`）增加 WebHook 管理界面

### 阶段四：业务埋点

在各业务模块的关键操作点插入 `dispatch_event()` 调用

### 阶段五：部署配置

1. 更新 `docker-compose.yml` 添加 Redis 和 Celery Worker
2. 更新 `.env.example` 添加新配置项

---

## 五、假设与风险

| 假设/风险 | 说明 | 缓解措施 |
|---|---|---|
| Redis 可用性 | Celery 依赖 Redis，Redis 宕机则 WebHook 无法投递 | Celery 任务持久化可配置；WebHook 投递失败记录在数据库中可重试 |
| WebHook 接收方可用性 | 第三方接收方宕机会导致推送失败 | 指数退避重试，最大 3 次；管理后台可手动重试 |
| WebHook 推送延迟 | 异步推送存在秒级延迟，对实时性要求极高的场景可能不适用 | 可通过 Celery 优先级队列降低延迟 |
| 管理后台 SPA 改动 | 前端文件 `admin.js` 未阅读，可能需额外的前端开发工作 | 准备评估是否需前后端联调 |

---

## 六、验证标准

1. 管理后台可以创建/编辑/启用/禁用 WebHook 配置
2. 业务触发（如用户登录）后，Celery Worker 成功向配置的 URL 推送事件
3. 投递日志记录完整（请求体、响应状态、耗时、错误信息等）
4. 失败自动重试（最多 3 次，指数退避）
5. 接收方可验证 HMAC 签名
6. docker-compose 可正常启动 Celery Worker
7. 原有业务功能不受影响
