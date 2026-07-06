# 统一账户认证服务 - 宝塔面板站点初始化指南

## 前提条件

> 以下步骤假设你**已在宝塔面板创建好 Python 站点**，项目代码已上传到站点根目录，依赖尚未安装，数据库尚未初始化。

***

## 第一步：安装依赖

### 方式 A：使用宝塔面板的 Python 管理器（推荐）

1. 进入宝塔面板 → 「软件商店」→ 找到已安装的「Python 管理器」
2. 点击「设置」→「版本管理」
3. 找到你的站点，点击右侧「依赖管理」
4. 在「项目依赖」中添加以下包（每行一个）：

```
django>=3.2,<4.0
djangorestframework>=3.14,<3.15
django-cors-headers>=3.13,<4.0
PyJWT>=2.8,<3.0
cryptography>=42.0,<43.0
pymysql>=1.0,<2.0
redis>=5.0,<6.0
requests>=2.31,<3.0
python-dotenv>=1.0,<2.0
gunicorn>=22.0,<23.0
aliyun-python-sdk-dysmsapi>=2.1.2,<3.0
```

1. 点击「安装」，等待安装完成

### 方式 B：通过 SSH 终端手动安装

```bash
# 进入站点目录（路径根据实际情况修改）
cd /www/wwwroot/unified_auth

# 激活虚拟环境（宝塔面板创建的 Python 项目通常有独立虚拟环境）
# 方式 1：宝塔自动创建的 venv
source /www/wwwroot/unified_auth/venv/bin/activate

# 方式 2：宝塔面板的 Python 管理器创建的虚拟环境
# 路径通常为 ~/.pyenv/versions/x.x.x/envs/站点名/
source ~/.pyenv/versions/3.10/envs/unified_auth/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

> **提示**：如果 cryptography 安装失败（提示缺少 Rust 编译器），先升级 pip 再重试：
>
> ```bash
> pip install --upgrade pip
> pip install cryptography==42.0.5
> ```

***

## 第二步：配置 .env 文件

在站点目录下创建 `.env` 文件（从 `.env.example` 复制后修改）：

```bash
cd /www/wwwroot/unified_auth
cp .env.example .env
```

编辑 `.env`，参考以下配置按实际情况修改：

```ini
# ==================== Django ====================
# 必填：Django 密钥，建议使用随机 50 位以上的字符串
# 生成方法：python -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=your-secret-key-here

# 必填：生产环境必须设为 False
DJANGO_DEBUG=False

# 必填：允许访问的域名，多个用逗号分隔
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# ==================== 数据库 ====================
# 开发环境使用 SQLite（无需修改）
DB_ENGINE=sqlite
DB_NAME=db.sqlite3

# 生产环境使用 MySQL（使用宝塔面板创建的数据库）
# DB_ENGINE=django.db.backends.mysql
# DB_NAME=unified_auth          # 与宝塔面板创建的数据库名一致
# DB_USER=unified_auth          # 与宝塔面板创建的数据库用户名一致
# DB_PASSWORD=your-db-password   # 宝塔面板设置的数据库密码
# DB_HOST=127.0.0.1
# DB_PORT=3306

# ==================== JWT ====================
# 必填：JWT 密钥，建议使用随机 32 位以上的字符串
# 生成方法：python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-jwt-secret-key

# ==================== 超级管理员账户 ====================
# 必填：超管账号和密码，JSON 数组格式
# 注意：密码强度需符合下面的 PASSWORD_MIN_LENGTH 要求
SUPERADMIN_ACCOUNTS=[{"username":"admin","password":"YourStrongPassword123!"}]

# 初始化管理员密码（执行 init_data 时创建的管理员用户密码）
ADMIN_INIT_PASSWORD=YourStrongPassword123!

# ==================== 短信配置（可选） ====================
# 如果需要短信登录功能，配置阿里云短信
# SMS_PROVIDER=aliyun
# SMS_ACCESS_KEY_ID=your-access-key-id
# SMS_ACCESS_KEY_SECRET=your-access-key-secret
# SMS_SIGN_NAME=你的公司
# SMS_TEMPLATE_CODE=SMS_xxxxxxx

# ==================== 安全策略（可选） ====================
# 密码最小长度（默认 8）
# PASSWORD_MIN_LENGTH=8
# 密码必须包含大写字母（默认 True）
# PASSWORD_MUST_HAVE_UPPER=True
# 登录锁定阈值（默认 5 次）
# ACCOUNT_LOCKOUT_THRESHOLD=5
```

> **安全提醒**：
>
> - `DJANGO_SECRET_KEY` 和 `JWT_SECRET_KEY` 必须修改为随机字符串，切勿使用默认值
> - `SUPERADMIN_ACCOUNTS` 中的管理员密码必须符合密码策略要求（长度≥8，需包含大写字母）
> - 数据库密码使用宝塔面板设置的强密码

***

## 第三步：初始化数据库

```bash
cd /www/wwwroot/unified_auth

# 激活虚拟环境（路径根据实际情况调整）
source /www/wwwroot/unified_auth/venv/bin/activate

# 生成数据库迁移文件
python manage.py makemigrations

# 执行数据库迁移
python manage.py migrate

# 初始化预置数据（创建默认租户、权限、角色、管理员用户等）
python manage.py init_data

# 收集静态文件（让 Nginx 能正确访问）
python manage.py collectstatic --noinput
```

> **如果使用 MySQL 数据库**，在执行迁移前确保：
>
> 1. 宝塔面板中 MySQL 服务已启动
> 2. 已创建 `unified_auth` 数据库
> 3. `.env` 中 `DB_ENGINE` 已切换为 `django.db.backends.mysql` 且配置正确

***

## 第四步：验证服务

### 检查数据库连接

```bash
source /www/wwwroot/unified_auth/venv/bin/activate
cd /www/wwwroot/unified_auth
python manage.py dbshell
# 如果连接成功，会进入 MySQL/SQLite 命令行，输入 \q 退出
```

### 测试 Django 服务

```bash
# 临时启动 Django 开发服务器测试
python manage.py runserver 0.0.0.0:8000
# 访问 http://your-domain.com:8000/admin-panel/ 查看是否正常
# 按 Ctrl+C 停止开发服务器
```

### 验证静态文件

```bash
curl http://your-domain.com/static/admin_panel/js/admin.js
# 如果返回 JavaScript 内容，说明静态文件配置正确
```

***

## 第五步：配置宝塔面板 Python 项目

> 以下步骤在宝塔面板「网站」中找到你的站点，进入站点设置完成配置。

| 配置项         | 推荐值                              | 说明             |
| ----------- | -------------------------------- | -------------- |
| 项目路径        | `/www/wwwroot/unified_auth`      | 代码所在目录         |
| 启动脚本        | `config/wsgi.py`                 | Django WSGI 入口 |
| 监听端口        | `8000`                           | Gunicorn 监听端口  |
| 虚拟环境        | `/www/wwwroot/unified_auth/venv` | pip 安装依赖的虚拟环境  |
| Gunicorn 配置 | `gunicorn.conf.py`               | 项目根目录下的配置文件    |

点击「提交」后，宝塔面板会自动启动 Gunicorn 进程。

***

## 常见问题排查

### Q1：访问页面显示 502 Bad Gateway

**原因**：Gunicorn 未启动或启动失败

**排查步骤**：

```bash
# 1. 检查 Gunicorn 进程是否运行
ps aux | grep gunicorn

# 2. 查看 Gunicorn 错误日志
cat /www/wwwroot/unified_auth/logs/gunicorn_error.log

# 3. 手动启动测试
cd /www/wwwroot/unified_auth
source venv/bin/activate
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --log-level debug
# 观察是否有报错信息
```

### Q2：数据库连接失败（MySQL）

**原因**：数据库配置错误或 MySQL 服务未启动

**排查步骤**：

```bash
# 1. 检查 MySQL 服务状态
systemctl status mysql   # Ubuntu/Debian
systemctl status mysqld  # CentOS

# 2. 测试数据库连接
mysql -u unified_auth -p -h 127.0.0.1 unified_auth

# 3. 确认 .env 中 DB_HOST 是否为 127.0.0.1（不是 localhost）
```

### Q3：静态文件显示 404

**原因**：`collectstatic` 未执行或 Nginx 静态文件目录配置错误

**排查步骤**：

```bash
# 1. 确认静态文件目录存在
ls /www/wwwroot/unified_auth/static/

# 2. 确认 Nginx 配置中的静态文件路径
# 宝塔面板「网站目录」中：静态文件目录 -> /www/wwwroot/unified_auth/static
```

### Q4：cryptography 安装失败

**原因**：pip 版本过低，无法获取预编译 wheel

**解决方法**：

```bash
pip install --upgrade pip
pip install cryptography==42.0.5
```

***

## 快速检查清单

- [ ] 依赖已通过 pip 安装完成
- [ ] `.env` 文件已创建且 `DJANGO_SECRET_KEY` 已修改为随机密钥
- [ ] `.env` 中 `DB_ENGINE` 配置正确（MySQL 或 SQLite）
- [ ] `python manage.py migrate` 执行成功
- [ ] `python manage.py init_data` 执行成功
- [ ] `python manage.py collectstatic --noinput` 执行成功
- [ ] 宝塔面板 Python 项目配置正确（端口 8000、启动脚本 wsgi.py）
- [ ] 宝塔面板 Nginx 已配置反向代理到 8000 端口
- [ ] 管理后台 <http://your-domain.com/admin-panel/> 可正常访问

***

## 登录信息

| 项目       | 值                                     |
| -------- | ------------------------------------- |
| 管理后台地址   | `http://your-domain.com/admin-panel/` |
| 默认管理员用户名 | `admin`（由 `SUPERADMIN_ACCOUNTS` 配置）   |
| 默认管理员密码  | 由 `.env` 中的 `ADMIN_INIT_PASSWORD` 指定  |

> **首次登录后请立即修改默认密码！**

