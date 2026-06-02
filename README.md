# 统一账号识别服务

面向中小企业的统一身份认证与用户管理 SaaS 服务，支持私有化部署。

## 功能特性

- **多租户数据隔离** — 每个租户拥有独立的数据空间
- **统一认证登录** — 支持密码登录、短信验证码登录、社交登录（微信/钉钉/飞书）
- **企业级用户管理** — 用户 CRUD、批量操作、导入/导出、重置密码
- **接入应用管理** — 应用注册、AppKey/AppSecret 认证、权限配置
- **基于角色的权限控制（RBAC）** — 角色定义、权限分配、用户绑定角色
- **组织架构管理** — 树形部门管理，用户关联部门
- **操作审计日志** — 全量操作记录、导出、筛选
- **开放 API** — 应用可通过开放接口对接用户体系
- **超级管理员后台** — 平台总览、租户管理、模拟租户、全局配置
- **统计报表** — 登录趋势、用户增长、活跃分析、应用调用统计

## 技术栈

| 组件   | 技术                                      |
| ---- | --------------------------------------- |
| 后端框架 | Django 3.2 + Django REST Framework 3.14 |
| 数据库  | MySQL 8.0（生产）/ SQLite（开发）               |
| 缓存   | Redis（可选）/ 本地内存缓存                       |
| 容器化  | Docker + Docker Compose                 |
| 前端   | 原生 JavaScript + Chart.js（仪表盘图表）         |
| 认证   | JWT（PyJWT）                              |
| 部署   | Gunicorn + Nginx（推荐）                    |

## 目录结构

```
unified_auth/
├── apps/
│   ├── accounts/          # 账号/认证/租户模块
│   ├── admin_panel/       # 管理后台 UI + API
│   │   ├── templates/     # HTML 模板
│   │   └── static/        # 前端静态资源（JS/CSS）
│   ├── applications/      # 应用管理模块
│   ├── audit/             # 审计日志模块
│   ├── openapi/           # 开放 API 模块
│   ├── rbac/              # 角色权限（RBAC）模块
│   └── users/             # 用户管理模块
├── common/                # 通用工具（认证、响应、错误码）
├── config/                # Django 配置
│   ├── settings.py        # 主配置
│   ├── urls.py            # 根路由
│   └── wsgi.py            # WSGI 入口
├── middlewares/           # 网关中间件
│   ├── rate_limit.py      # 限流中间件
│   ├── app_auth.py        # 应用认证中间件
│   ├── token_auth.py      # Token 认证中间件
│   ├── admin_auth.py      # 管理后台认证中间件
│   ├── permission.py      # 权限校验中间件
│   └── audit_log.py       # 审计日志中间件
├── services/              # 外部服务（短信等）
├── tests/                 # 测试用例
├── .env                   # 配置文件（非版本库）
├── .env.example           # 配置模板
├── Dockerfile             # Docker 镜像构建
├── docker-compose.yml     # Docker Compose 编排
├── entrypoint.sh          # 容器启动脚本
├── manage.py              # Django 管理入口
├── requirements.txt       # Python 依赖
└── pytest.ini             # 测试配置
```

***

## 一、快速开始（开发环境）

### 1. 前置条件

- Python 3.8+
- MySQL 5.5（可选，开发可用 SQLite）
- Redis（可选，不使用缓存时自动降级为本地内存缓存）

### 2. 克隆并安装依赖

```bash
git clone <repo-url>
cd unified_auth

pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，开发环境最小配置：

```ini
# Django
DJANGO_SECRET_KEY=dev-secret-key
DJANGO_DEBUG=True

# 数据库 - 使用 SQLite（开发推荐）
DB_ENGINE=sqlite
DB_NAME=db.sqlite3

# JWT
JWT_SECRET_KEY=dev-jwt-secret

# 超级管理员账户
SUPERADMIN_ACCOUNTS=[{"username":"admin","password":"admin123"}]

# 初始化管理员密码
ADMIN_INIT_PASSWORD=admin123
```

### 4. 初始化数据库

```bash
python manage.py migrate
python manage.py init_data
```

### 5. 启动开发服务器

```bash
python manage.py runserver 0.0.0.0:8000
```

### 6. 访问

| 页面           | 地址                                         |
| ------------ | ------------------------------------------ |
| 管理后台         | <http://localhost:8000/admin-panel/>       |
| Django Admin | <http://localhost:8000/admin/>             |
| DRF 浏览 API   | <http://localhost:8000/api/v1/auth/login/> |

***

## 二、配置说明

### 2.1 数据库配置

**开发环境（SQLite）：**

```ini
DB_ENGINE=sqlite
DB_NAME=db.sqlite3
```

**生产环境（MySQL）：**

```ini
DB_ENGINE=django.db.backends.mysql
DB_NAME=unified_auth
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 2.2 完整配置项

配置文件 [.env](file:///e:/framework/Unified%20account%20identification%20service/code/unified_auth/.env) 分为以下几组：

| 配置组        | 环境变量                                                                                                     | 说明                                                         |
| ---------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **Django** | `DJANGO_SECRET_KEY`                                                                                      | Django 密钥（生产环境务必修改）                                        |
| <br />     | `DJANGO_DEBUG`                                                                                           | 调试模式（生产环境设为 False）                                         |
| <br />     | `ALLOWED_HOSTS`                                                                                          | 允许的主机名，逗号分隔                                                |
| **数据库**    | `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`                                   | 数据库连接信息                                                    |
| **JWT**    | `JWT_SECRET_KEY`                                                                                         | JWT 签名密钥（生产环境务必修改）                                         |
| <br />     | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`                                                                        | Access Token 有效期（默认 120 分钟）                                |
| <br />     | `JWT_REFRESH_TOKEN_EXPIRE_DAYS`                                                                          | Refresh Token 有效期（默认 30 天）                                 |
| **超级管理员**  | `SUPERADMIN_ACCOUNTS`                                                                                    | JSON 数组格式，如 `[{"username":"admin","password":"admin123"}]` |
| **邮件服务**   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_FROM_NAME` | SMTP 邮件发送配置                                                |
| **短信服务**   | `SMS_PROVIDER`, `SMS_ACCESS_KEY_ID`, `SMS_ACCESS_KEY_SECRET`, `SMS_SIGN_NAME`, `SMS_TEMPLATE_CODE`       | 阿里云短信配置                                                    |
| **安全策略**   | `PASSWORD_MIN_LENGTH`                                                                                    | 密码最小长度（默认 8）                                               |
| <br />     | `PASSWORD_MUST_HAVE_DIGIT`                                                                               | 密码必须包含数字                                                   |
| <br />     | `PASSWORD_MUST_HAVE_UPPER`                                                                               | 密码必须包含大写字母                                                 |
| <br />     | `ACCOUNT_LOCKOUT_THRESHOLD`                                                                              | 登录锁定阈值（默认 5 次）                                             |
| <br />     | `ACCOUNT_LOCKOUT_MINUTES`                                                                                | 锁定时长（默认 30 分钟）                                             |
| **限流**     | `RATE_LIMIT_IP_DEFAULT`                                                                                  | IP 级限流（默认 60 次/分钟）                                         |
| <br />     | `RATE_LIMIT_APP_DEFAULT`                                                                                 | AppKey 级限流（默认 1000 次/分钟）                                   |

***

## 三、部署指南

### 3.1 Docker 部署（推荐）

#### 构建并启动

```bash
# 进入项目根目录
cd code/unified_auth

# 编辑配置
cp .env.example .env
# 修改 .env 中的生产环境配置

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### docker-compose.yml 说明

[compose 文件](file:///e:/framework/Unified%20account%20identification%20service/code/unified_auth/docker-compose.yml) 包含两个服务：

- **db** — MySQL 8.0 数据库，自动健康检查
- **web** — Django 应用，Gunicorn 4 workers 运行

#### 容器启动流程（Dockerfile）

1. 基于 `python:3.10-slim` 镜像
2. 安装 MySQL 客户端依赖
3. 安装 Python 依赖
4. 收集静态文件
5. 通过 `entrypoint.sh` 执行：迁移 → 初始化数据 → 收集静态文件 → 启动 Gunicorn

### 3.2 手动部署（Linux）

```bash
# 1. 安装系统依赖
apt update && apt install -y python3.10 python3.10-venv mysql-server nginx

# 2. 创建数据库
mysql -u root -p
CREATE DATABASE unified_auth DEFAULT CHARACTER SET utf8mb4;
CREATE USER 'unified_auth'@'localhost' IDENTIFIED BY 'your-strong-password';
GRANT ALL ON unified_auth.* TO 'unified_auth'@'localhost';
FLUSH PRIVILEGES;

# 3. 部署应用
cd /opt
git clone <repo-url>
cd unified_auth
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn mysqlclient

# 4. 配置
cp .env.example .env
# 编辑 .env，配置数据库连接和生产环境参数

# 5. 初始化
python manage.py migrate
python manage.py init_data
python manage.py collectstatic --noinput

# 6. 启动 Gunicorn
gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --access-logfile /var/log/unified_auth/access.log \
    --error-logfile /var/log/unified_auth/error.log \
    --daemon

# 7. 配置 Nginx 反向代理
cat > /etc/nginx/sites-available/unified_auth << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /opt/unified_auth/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/unified_auth /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 3.3 环境变量清单（生产环境必改项）

| 变量                     | 说明        | 建议值                                   |
| ---------------------- | --------- | ------------------------------------- |
| `DJANGO_SECRET_KEY`    | Django 密钥 | 随机 50 位以上字符串                          |
| `DJANGO_DEBUG`         | 调试模式      | `False`                               |
| `ALLOWED_HOSTS`        | 允许的域名     | `your-domain.com,api.your-domain.com` |
| `JWT_SECRET_KEY`       | JWT 密钥    | 随机 32 位以上字符串                          |
| `DB_PASSWORD`          | 数据库密码     | 符合密码策略的强密码                            |
| `SUPERADMIN_ACCOUNTS`  | 超管账户      | 设置强密码                                 |
| `CORS_ALLOWED_ORIGINS` | 允许的跨域来源   | 前端域名列表                                |

### 3.4 生产环境安全检查清单

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` 改为随机密钥
- [ ] `JWT_SECRET_KEY` 与 Django Secret Key 不同
- [ ] 数据库使用独立用户，密码强度足够
- [ ] 超级管理员账户密码强度足够
- [ ] Nginx 配置 HTTPS（推荐 Let's Encrypt）
- [ ] 关闭不必要的端口（MySQL 端口不对外暴露）
- [ ] 定期备份数据库
- [ ] 开启 Gunicorn 访问日志

### 3.5 宝塔面板部署指南

以下步骤适用于使用宝塔 Linux 面板（BT Panel）部署本项目的场景。

#### 3.5.1 环境准备

在宝塔面板的「软件商店」中安装以下软件：

| 软件        | 版本要求       | 用途     |
| --------- | ---------- | ------ |
| Nginx     | 1.20+      | 反向代理   |
| MySQL     | 8.0        | 数据库    |
| Python    | 3.8 - 3.10 | 项目运行环境 |
| Redis（可选） | 6.0+       | 缓存加速   |

#### 3.5.2 创建站点

1. 进入宝塔面板 → **网站** → **添加站点**
2. 填写域名，选择 **纯静态**（不需要 PHP）
3. 创建成功后进入 **站点根目录**

#### 3.5.3 上传项目代码

```bash
# 进入站点目录（假设为 /www/wwwroot/your-domain.com）
cd /www/wwwroot/your-domain.com

# 上传项目代码后将项目放在此目录，或使用 Git 克隆
# 项目路径结构：/www/wwwroot/your-domain.com/unified_auth/...
```

#### 3.5.4 创建数据库

1. 宝塔面板 → **数据库** → **添加数据库**
2. 填写数据库名称（如 `unified_auth`）
3. 设置用户名和密码
4. 字符集选择 **utf8mb4**
5. 记录下数据库名称、用户名、密码备用

#### 3.5.5 配置 Python 虚拟环境

```bash
# 进入站点目录
cd /www/wwwroot/your-domain.com

# 安装 Python 虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
pip install gunicorn mysqlclient
```

#### 3.5.6 配置环境变量

```bash
cd /www/wwwroot/your-domain.com/unified_auth
cp .env.example .env
```

编辑 `.env` 文件，配置生产环境参数：

```ini
DJANGO_SECRET_KEY=<生成一个随机密钥>
DJANGO_DEBUG=False
ALLOWED_HOSTS=your-domain.com

# MySQL 数据库配置（使用宝塔创建的数据库信息）
DB_ENGINE=django.db.backends.mysql
DB_NAME=unified_auth
DB_USER=unified_auth
DB_PASSWORD=<数据库密码>
DB_HOST=127.0.0.1
DB_PORT=3306

JWT_SECRET_KEY=<生成一个不同的随机密钥>

SUPERADMIN_ACCOUNTS=[{"username":"admin","password":"<设置强密码>"}]
ADMIN_INIT_PASSWORD=<设置强密码>
```

#### 3.5.7 初始化项目

```bash
cd /www/wwwroot/your-domain.com/unified_auth
source ../venv/bin/activate

# 执行数据库迁移
python manage.py migrate

# 初始化基础数据
python manage.py init_data

# 收集静态文件
python manage.py collectstatic --noinput
```

#### 3.5.8 配置 Supervisor 进程守护

在宝塔面板中安装 **Supervisor管理器**，然后添加守护进程：

- **名称**：`unified_auth`
- **启动用户**：`www`
- **运行目录**：`/www/wwwroot/your-domain.com/unified_auth`
- **启动命令**：

```bash
/www/wwwroot/your-domain.com/venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8001 \
    --workers 4 \
    --access-logfile /www/wwwroot/your-domain.com/logs/access.log \
    --error-logfile /www/wwwroot/your-domain.com/logs/error.log
```

> 注意：使用 `127.0.0.1:8001` 而非 `0.0.0.0:8000`，避免直接对外暴露端口，由 Nginx 反向代理。

#### 3.5.9 配置 Nginx 反向代理

在 **网站设置** → **反向代理** 中：

1. 添加反向代理规则：
   - **代理名称**：`unified_auth`
   - **目标 URL**：`http://127.0.0.1:8001`
   - **发送域名**：`$host`
2. 或者直接编辑 Nginx 配置文件（**网站设置** → **配置文件**）：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 静态文件直接由 Nginx 处理，不转发给后端
    location /static/ {
        alias /www/wwwroot/your-domain.com/unified_auth/static/;
        expires 30d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（如需）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 禁止访问敏感文件
    location ~ /\.env {
        deny all;
    }
    location ~ /\.git {
        deny all;
    }
}
```

#### 3.5.10 配置 HTTPS（推荐）

1. 宝塔面板 → **网站** → 选择站点 → **SSL**
2. 选择 **Let's Encrypt** 免费证书
3. 勾选域名后点击 **申请**
4. 申请成功后开启 **强制 HTTPS**

#### 3.5.11 验证部署

| 检查项     | 地址                                                           | 预期结果     |
| ------- | ------------------------------------------------------------ | -------- |
| 管理后台    | `http://your-domain.com/admin-panel/`                        | 显示登录页    |
| API 可用性 | `curl http://127.0.0.1:8001/api/v1/auth/login/`              | 返回 JSON  |
| 静态文件    | `curl http://your-domain.com/static/admin_panel/js/admin.js` | 返回 JS 内容 |

#### 3.5.12 错误排查

| 问题                        | 可能原因                      | 解决方法                                    |
| ------------------------- | ------------------------- | --------------------------------------- |
| 502 Bad Gateway           | Gunicorn 未启动              | 检查 Supervisor 是否正常运行，查看日志               |
| 静态文件 404                  | `collectstatic` 未执行或路径不对  | 检查 Nginx `alias` 路径是否与 `STATIC_ROOT` 一致 |
| 页面白屏/JS 错误                | 静态文件路径配置错误                | 核对 `static/` 目录是否存在于项目根目录               |
| 数据库连接失败                   | 数据库凭据错误或未创建               | 检查 `.env` 数据库配置，在宝塔面板确认数据库状态            |
| 500 Internal Server Error | Django DEBUG=False 未捕获的错误 | 查看 `error.log` 获取详细错误信息                 |

***

## 四、管理命令

### 初始化基础数据

```bash
python manage.py init_data
```

该命令会创建：

- 默认租户（如果不存在）
- 默认管理员用户（使用 `.env` 中的 `ADMIN_INIT_PASSWORD`）
- 基础权限数据
- 默认角色

### 数据库迁移

```bash
# 创建迁移文件
python manage.py makemigrations

# 执行迁移
python manage.py migrate
```

### 其他常用命令

```bash
# 创建数据库迁移文件
python manage.py makemigrations <app_name>

# 查看 SQL
python manage.py sqlmigrate <app_name> <migration_id>

# Django Shell
python manage.py shell

# 创建超级用户
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic --noinput

# 测试
python manage.py test
```

***

## 五、API 概览

### 5.1 客户端认证 API `/api/v1/auth/`

| 方法    | 路径                   | 功能       | 认证方式          |
| ----- | -------------------- | -------- | ------------- |
| POST  | `/login`             | 密码登录     | 无             |
| POST  | `/sms/send`          | 发送短信验证码  | 无             |
| POST  | `/sms/login`         | 短信验证码登录  | 无             |
| POST  | `/social/login`      | 社交登录     | 无             |
| POST  | `/refresh`           | 刷新 Token | Refresh Token |
| POST  | `/logout`            | 登出       | Access Token  |
| GET   | `/userinfo`          | 获取当前用户信息 | Access Token  |
| PUT   | `/userinfo`          | 修改用户信息   | Access Token  |
| PATCH | `/userinfo/password` | 修改密码     | Access Token  |
| GET   | `/profile`           | 获取用户资料   | Access Token  |
| PUT   | `/profile/update`    | 更新用户资料   | Access Token  |

### 5.2 开放 API `/api/v1/open/`

通过 AppKey/AppSecret 签名认证，提供用户管理系统对接接口。

| 方法    | 路径                   | 功能         | 权限码                |
| ----- | -------------------- | ---------- | ------------------ |
| POST  | `/verify_token`      | 验证用户 Token | `token:verify`     |
| GET   | `/users`             | 查询用户列表     | `user:read`        |
| GET   | `/users/<id>`        | 获取用户详情     | `user:read`        |
| POST  | `/users`             | 创建用户       | `user:create`      |
| PUT   | `/users/<id>`        | 修改用户信息     | `user:update`      |
| PATCH | `/users/<id>/status` | 启用/禁用用户    | `user:update`      |
| POST  | `/check_permission`  | 检查用户权限      | `permission:check` |
| GET   | `/user/profile/by_token` | 通过Token获取用户资料 | `user:profile:read` |
| PUT   | `/user/profile/by_token` | 通过Token修改用户资料 | `user:profile:update` |
| GET   | `/wechat/access_token` | 获取微信AccessToken（自动缓存） | `wechat:access_token` |
| POST  | `/wechat/get_phone_number` | 获取微信用户手机号 | `wechat:phone` |

> 开放 API 通过中间件自动实现租户数据隔离，每个应用只能操作所属租户的数据。

### 5.3 企业管理后台 API `/api/v1/admin/`

需要管理员登录 Token（`is_staff=True`）。

| 方法             | 路径                                     | 功能         |
| -------------- | -------------------------------------- | ---------- |
| GET            | `/stats`                               | 仪表盘统计      |
| GET            | `/recent-activities`                   | 最近操作动态     |
| GET            | `/stats/login-trend`                   | 登录趋势       |
| GET            | `/stats/login-distribution`            | 登录方式分布     |
| GET            | `/stats/user-growth`                   | 用户增长趋势     |
| GET            | `/stats/user-type-distribution`        | 用户类型分布     |
| GET            | `/stats/active-users`                  | 活跃用户统计     |
| GET/POST       | `/users`                               | 用户列表/创建    |
| GET/PUT/DELETE | `/users/<id>`                          | 用户详情/编辑/删除 |
| PATCH          | `/users/<id>/status`                   | 用户状态切换     |
| POST           | `/users/<id>/reset-password`           | 重置密码       |
| GET/PUT        | `/users/<id>/roles`                    | 用户角色管理     |
| GET/PUT        | `/users/<id>/profile`                  | 用户资料管理     |
| GET/POST       | `/applications`                        | 应用列表/创建    |
| GET/PUT        | `/applications/<id>`                   | 应用详情/编辑    |
| PATCH          | `/applications/<id>/status`            | 应用状态切换     |
| POST           | `/applications/<id>/regenerate-secret` | 重新生成密钥     |
| GET            | `/applications/<id>/permissions`       | 应用权限配置     |
| GET            | `/applications/<id>/api-stats`         | 应用API调用统计  |
| GET/POST       | `/roles`                               | 角色列表/创建    |
| GET/PUT        | `/roles/<id>`                          | 角色详情/编辑    |
| GET            | `/departments`                         | 部门列表（树形）   |
| GET/POST       | `/departments`                         | 部门创建       |
| GET/PUT/DELETE | `/departments/<id>`                    | 部门管理       |
| GET/POST       | `/users/import`                        | 用户导入       |
| GET            | `/users/export`                        | 用户导出       |
| GET            | `/audit-logs`                          | 审计日志列表     |
| GET            | `/audit-logs/export`                   | 审计日志导出     |
| GET            | `/permissions`                         | 权限列表       |

### 5.4 超级管理员 API `/api/v1/superadmin/`

需要超级管理员身份（`is_superuser=True`）。

| 方法             | 路径                                 | 功能        |
| -------------- | ---------------------------------- | --------- |
| GET            | `/global-stats`                    | 平台总览统计    |
| GET/POST       | `/tenants`                         | 租户列表/创建   |
| GET/PUT/DELETE | `/tenants/<id>`                    | 租户管理      |
| GET            | `/audit-logs`                      | 全局审计日志    |
| GET            | `/audit-logs/export`               | 审计日志导出    |
| GET            | `/api-stats`                       | 全局API调用统计 |
| GET            | `/platform-config`                 | 全局配置查看    |
| POST           | `/impersonate/<tenant_id>`         | 模拟进入租户    |
| POST           | `/impersonate/exit`                | 退出模拟模式    |
| GET            | `/stats/tenant-growth`             | 租户增长趋势    |
| GET            | `/stats/tenant-activity-ranking`   | 租户活跃度排行   |
| GET            | `/stats/global-user-growth`        | 全局用户增长    |
| GET            | `/stats/global-login-trend`        | 全局登录趋势    |
| GET            | `/stats/global-login-distribution` | 全局登录分布    |
| GET            | `/stats/app-call-ranking`          | 应用调用排行    |

***

## 六、中间件架构

### 6.1 执行顺序

```
请求 → RateLimitMiddleware → AppAuthenticationMiddleware → TokenAuthenticationMiddleware
     → AdminAuthenticationMiddleware → PermissionMiddleware → AuditLogMiddleware → 视图
```

### 6.2 各中间件职责

| 中间件                             | 路由范围             | 职责                                              |
| ------------------------------- | ---------------- | ----------------------------------------------- |
| `RateLimitMiddleware`           | 全局               | IP 级和 AppKey 级限流，基于 Token Bucket 算法             |
| `AppAuthenticationMiddleware`   | `/api/v1/open/`  | 通过 AppKey/AppSecret 认证应用，设置 `request.tenant_id` |
| `TokenAuthenticationMiddleware` | 全局               | 验证 JWT Token，设置 `request.user`                  |
| `AdminAuthenticationMiddleware` | `/api/v1/admin/` | 校验管理员身份（`is_staff` 或 `is_superuser`）            |
| `PermissionMiddleware`          | `/api/v1/open/`  | 校验开放 API 的权限码                                   |
| `AuditLogMiddleware`            | 非 GET 请求         | 记录写操作的审计日志                                      |

***

## 七、测试

### 运行所有测试

```bash
pytest
```

### 运行指定测试文件

```bash
pytest tests/test_accounts.py -v
pytest tests/test_admin.py -v
pytest tests/test_openapi.py -v
pytest tests/test_superadmin.py -v
pytest tests/test_gateway.py -v
```

### 测试配置

测试使用独立的 SQLite 内存数据库，每次运行前自动创建、结束后自动销毁，不会影响开发/生产数据。

***

## 八、常见问题

### Q: 启动后访问管理后台出现 403？

A: 确认 Token 有效，且用户为管理员（`is_staff=True`）。初始化数据时会自动创建管理员。

### Q: 如何修改超级管理员密码？

A: 修改 `.env` 中的 `SUPERADMIN_ACCOUNTS` 配置后重启服务。

### Q: 如何切换数据库从 SQLite 到 MySQL？

A: 修改 `.env` 中的 `DB_ENGINE` 和相关配置，执行 `python manage.py migrate`。

### Q: 开放 API 调用返回 401？

A: 确认使用了正确的 AppKey 和 AppSecret，签名算法正确。

### Q: 如何查看 API 调用统计？

A: 企业管理后台 → 应用管理 → 点击应用的"API统计"按钮。

### Q: 如何配置邮件发送功能？

A: 在 `.env` 中配置 `EMAIL_*` 相关参数并重启服务。
