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

> **📖 给开发者 / AI Agent 的强指令（动手改代码前必读）**
>
> 当你要为这个项目**写代码、改 bug、加功能**时，请**严格遵守**以下顺序：
>
> 1. **不要**上来就翻代码。先打开主路由文档 [`document/archive/DEVELOPMENT_ROUTING_GUIDE_v1.0.md`](document/archive/DEVELOPMENT_ROUTING_GUIDE_v1.0.md)。
> 2. 在主路由文档的"任务类型索引"中，根据你要做的事（需求理解 / 核心模块 / 微信集成 / 开放API回调 / 超管后台 / 测试）跳到对应的设计文档：
>    - 需求评审、业务边界不清 → `document/统一账号识别服务-需求规格说明书_v1.0.md`
>    - 搭项目骨架、模块划分、表结构、认证中间件 → `document/统一账号识别服务-实现计划_v1.0.md`
>    - 企业微信扫码登录 / 手机号获取 → `document/企业微信登录集成设计文档_v1.1.md`
>    - 开放 API 回调 / Webhook → `document/回调模块实施计划（独立模块）_v1.0.md`
>    - 超级管理员后台 → `document/超级管理员后台与全模块完整设计文档_v1.7.md`
>    - 写测试 / 压测 → `document/统一账号识别服务-系统测试计划_v1.0.md`
> 3. **不要**直接凭 README 的目录结构或代码注释就动手，必须先进入对应设计文档理解业务边界与数据模型。
>
> 另外：如果你只是要**对接 API**（调用接口、查入参出参），直接查阅第六章「API 清单路由」，从 [`document/apis/`](document/apis/) 目录的 5 份清单文档中按 URL 前缀选择对应子清单。

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
SUPERADMIN_ACCOUNTS=[{"username":"admin","password":"1C5G7JI@adD2"}]

# 初始化管理员密码
ADMIN_INIT_PASSWORD=admin123456
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
|            | `DJANGO_DEBUG`                                                                                           | 调试模式（生产环境设为 False）                                         |
|            | `ALLOWED_HOSTS`                                                                                          | 允许的主机名，逗号分隔                                                |
| **数据库**    | `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`                                   | 数据库连接信息                                                    |
| **JWT**    | `JWT_SECRET_KEY`                                                                                         | JWT 签名密钥（生产环境务必修改）                                         |
|            | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`                                                                        | Access Token 有效期（默认 120 分钟）                                |
|            | `JWT_REFRESH_TOKEN_EXPIRE_DAYS`                                                                          | Refresh Token 有效期（默认 30 天）                                 |
| **超级管理员**  | `SUPERADMIN_ACCOUNTS`                                                                                    | JSON 数组格式，如 `[{"username":"admin","password":"admin123"}]` |
| **邮件服务**   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_FROM_NAME` | SMTP 邮件发送配置                                                |
| **短信服务**   | `SMS_PROVIDER`, `SMS_ACCESS_KEY_ID`, `SMS_ACCESS_KEY_SECRET`, `SMS_SIGN_NAME`, `SMS_TEMPLATE_CODE`       | 阿里云短信配置                                                    |
| **安全策略**   | `PASSWORD_MIN_LENGTH`                                                                                    | 密码最小长度（默认 8）                                               |
|            | `PASSWORD_MUST_HAVE_DIGIT`                                                                               | 密码必须包含数字                                                   |
|            | `PASSWORD_MUST_HAVE_UPPER`                                                                               | 密码必须包含大写字母                                                 |
|            | `ACCOUNT_LOCKOUT_THRESHOLD`                                                                              | 登录锁定阈值（默认 5 次）                                             |
|            | `ACCOUNT_LOCKOUT_MINUTES`                                                                                | 锁定时长（默认 30 分钟）                                             |
| **限流**     | `RATE_LIMIT_IP_DEFAULT`                                                                                  | IP 级限流（默认 60 次/分钟）                                         |
|            | `RATE_LIMIT_APP_DEFAULT`                                                                                 | AppKey 级限流（默认 1000 次/分钟）                                   |

***

## 三、打包发布

项目通过打包脚本生成部署包，脚本位于 `scripts/package.py`（工作区根目录下执行）。

### 3.1 执行打包

```bash
# 在工作区根目录执行
python scripts/package.py
```

### 3.2 打包内容

| 内容 | 来源 | 打包位置 |
|---|---|---|
| 工程代码 | `code/unified_auth/`（含 `*.py/*.md/*.html/*.js/*.sql/.env.example` 等） | `code/dist/` 按原目录结构 |
| 路由文档 | `document/apis/` 下 5 份 API 清单（无版本号、始终最新版）+ `DEVELOPMENT_ROUTING_GUIDE_v1.0.md` + `管理员后台操作手册` | `code/dist/document/` |
| 主入口 README | 工作区根目录 `README.md` | `code/dist/README.md` |
| 部署说明 | 脚本自动生成 | `code/dist/UPDATE_NOTES.txt` |

**自动排除**：`tests/`、`__pycache__`、`.git`、`node_modules`、`.env`、`db_init.sql`、接口调试临时文件等；其余设计文档（需求规格、实现计划、企业微信设计等）仅保留在本地 `document/`，不进入部署包。

**迁移检测**：脚本自动扫描 `apps/*/migrations/` 下的迁移文件并写入 UPDATE_NOTES.txt，提醒部署时执行 `python manage.py migrate`。

### 3.3 打包产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 部署目录 | `code/dist/` | 可直接上传到服务器替换旧版本 |
| 发布压缩包 | `output/unified_auth_<YYYY-MM-DD>.zip` | 每次打包覆盖当日同名包 |
| 打包日志 | `log/package/<YYYY-MM-DD>.log` | 记录拷贝明细与跳过的文档 |

### 3.4 上线步骤（详见 UPDATE_NOTES.txt）

1. 备份现有数据库与 `.env` 配置
2. 停止服务
3. 用 `code/dist/` 内容替换服务器代码目录（`.env` 不在包内，不会被覆盖）
4. 如有迁移文件：`python manage.py migrate`
5. 启动服务

### 3.5 部署后 AI 对接

`code/dist/` 内已包含 README 与 `document/apis/` 全部 API 清单，AI Agent 在服务器上可直接按 README 第六章「API 清单路由」找到权威接口定义。

***

## 四、部署指南

### 4.1 Docker 部署（推荐）

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

### 4.2 手动部署（Linux）

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

### 4.3 环境变量清单（生产环境必改项）

| 变量                     | 说明        | 建议值                                   |
| ---------------------- | --------- | ------------------------------------- |
| `DJANGO_SECRET_KEY`    | Django 密钥 | 随机 50 位以上字符串                          |
| `DJANGO_DEBUG`         | 调试模式      | `False`                               |
| `ALLOWED_HOSTS`        | 允许的域名     | `your-domain.com,api.your-domain.com` |
| `JWT_SECRET_KEY`       | JWT 密钥    | 随机 32 位以上字符串                          |
| `DB_PASSWORD`          | 数据库密码     | 符合密码策略的强密码                            |
| `SUPERADMIN_ACCOUNTS`  | 超管账户      | 设置强密码                                 |
| `CORS_ALLOWED_ORIGINS` | 允许的跨域来源   | 前端域名列表                                |

### 4.4 生产环境安全检查清单

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` 改为随机密钥
- [ ] `JWT_SECRET_KEY` 与 Django Secret Key 不同
- [ ] 数据库使用独立用户，密码强度足够
- [ ] 超级管理员账户密码强度足够
- [ ] Nginx 配置 HTTPS（推荐 Let's Encrypt）
- [ ] 关闭不必要的端口（MySQL 端口不对外暴露）
- [ ] 定期备份数据库
- [ ] 开启 Gunicorn 访问日志

### 4.5 宝塔面板部署指南

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

## 五、管理命令

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

## 六、API 清单路由

> 本 README **不包含任何 API 明细列表**。所有接口的权威定义统一由 `document/apis/` 目录下的 API 清单文档提供（文件名不带版本号，始终为最新版；历史版本在 `document/archive/`）。
> 完整模块设计背景见 [超级管理员后台与全模块完整设计文档_v1.7.md](document/超级管理员后台与全模块完整设计文档_v1.7.md)。

### 6.1 API 清单目录

| 清单文档 | 覆盖 URL 前缀 | 适用读者 |
|---|---|---|
| [API_01_AUTH.md](document/apis/API_01_AUTH.md) | `/api/v1/auth/*` | App / H5 客户端开发者（登录、短信、社交登录、改密、强制改密策略） |
| [API_02_OPEN.md](document/apis/API_02_OPEN.md) | `/api/v1/open/*` | 第三方应用服务端（AppKey+Signature 签名对接、用户管理开放接口） |
| [API_03_ADMIN.md](document/apis/API_03_ADMIN.md) | `/api/v1/admin/*` | 租户管理员、管理后台前端（用户/应用/角色/部门/标签/审计/短信/邀请码/补全码） |
| [API_04_SUPERADMIN.md](document/apis/API_04_SUPERADMIN.md) | `/api/v1/superadmin/*` | 超级管理员（租户管理、模拟模式、全局报表） |
| [API_05_PUBLIC.md](document/apis/API_05_PUBLIC.md) | `/api/v1/public/*` 及公开页面 | 扫码页面对接、集成测试（邀请码注册、资料补全码、短链） |

### 6.2 给 AI Agent 的强指令（对接本服务前必读）

> 如果你是 AI Agent（包括但不限于 Cursor / Trae / 各类 Coding Agent）即将对接本服务，请**严格遵守**以下顺序：
>
> 1. **根据调用者身份 + URL 前缀**，从上方 5.1 清单目录中选择对应清单文档。
> 2. **只以清单文档为权威**，查看其中的入参、出参、认证方式、错误码与示例。
> 3. **不要**凭本 README 或训练记忆回答接口细节；README 不维护 API 列表。

### 6.3 认证方式速记

仅用于快速判断该读哪份清单，具体规则以清单文档为准：

| 你的身份 | 前缀 | 认证方式 |
|---|---|---|
| App/H5 终端用户 | `/api/v1/auth/` | URL 参数 `?access_token=<应用级Token>`（+ 用户 Token） |
| 第三方应用服务端 | `/api/v1/open/` | Header `X-App-Key/X-Timestamp/X-Signature` 或 URL access_token |
| 租户管理员 | `/api/v1/admin/` | Header `Authorization: Bearer <后台登录Token>` |
| 超级管理员 | `/api/v1/superadmin/` | 同上，且需 `is_superuser=True` |
| 匿名扫码用户 | `/api/v1/public/` | 码即凭证，无需登录（IP 限流保护） |

***

## 七、中间件架构

### 7.1 执行顺序

```
请求 → RateLimitMiddleware → AppAuthenticationMiddleware → TokenAuthenticationMiddleware
     → AdminAuthenticationMiddleware → PermissionMiddleware → AuditLogMiddleware → 视图
```

### 7.2 各中间件职责

| 中间件                             | 路由范围             | 职责                                              |
| ------------------------------- | ---------------- | ----------------------------------------------- |
| `RateLimitMiddleware`           | 全局               | IP 级和 AppKey 级限流，基于 Token Bucket 算法             |
| `AppAuthenticationMiddleware`   | `/api/v1/open/`  | 通过 AppKey/AppSecret 认证应用，设置 `request.tenant_id` |
| `TokenAuthenticationMiddleware` | 全局               | 验证 JWT Token，设置 `request.user`                  |
| `AdminAuthenticationMiddleware` | `/api/v1/admin/` | 校验管理员身份（`is_staff` 或 `is_superuser`）            |
| `PermissionMiddleware`          | `/api/v1/open/`  | 校验开放 API 的权限码                                   |
| `AuditLogMiddleware`            | 非 GET 请求         | 记录写操作的审计日志                                      |

***

## 八、测试

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

## 九、常见问题

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
