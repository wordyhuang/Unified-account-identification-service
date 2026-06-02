#!/bin/bash
###在宝塔面板执行此命令。
### chmod +x linux_setup.sh
### ./linux_setup.sh
### 

# 统一账户认证服务 - 站点初始化脚本
# ==========================================
# 适用场景：已在宝塔面板创建 Python 站点并安装依赖后，
# 执行剩余的初始化步骤（数据库迁移、初始化数据、收集静态文件等）
# ==========================================

APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV_DIR=""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}  统一账户认证服务 - 站点初始化${NC}"
echo -e "${CYAN}==========================================${NC}"
echo -e "项目目录: ${APP_DIR}"

# 自动检测虚拟环境
if [ -d "${APP_DIR}/venv" ]; then
    VENV_DIR="${APP_DIR}/venv"
elif [ -d "/www/wwwroot/$(basename ${APP_DIR})/venv" ]; then
    VENV_DIR="/www/wwwroot/$(basename ${APP_DIR})/venv"
else
    # 尝试查找上级目录中的 venv（宝塔面板常见位置）
    for candidate in "${APP_DIR}/venv" "${APP_DIR}/../venv" "/www/wwwroot/$(basename ${APP_DIR})/venv"; do
        CANDIDATE=$(cd "$(dirname "$candidate")" 2>/dev/null && pwd)/$(basename "$candidate")
        if [ -f "${CANDIDATE}/bin/activate" ]; then
            VENV_DIR="$CANDIDATE"
            break
        fi
    done
fi

# 如果仍未找到，提示用户输入
if [ -z "$VENV_DIR" ] || [ ! -f "${VENV_DIR}/bin/activate" ]; then
    echo -e "${YELLOW}未自动检测到虚拟环境，请手动输入 venv 路径${NC}"
    echo -e "${YELLOW}（留空则跳过虚拟环境激活，使用系统 Python）${NC}"
    read -p "venv 路径: " CUSTOM_VENV
    if [ -n "$CUSTOM_VENV" ]; then
        VENV_DIR="$CUSTOM_VENV"
    fi
fi

activate_venv() {
    if [ -n "$VENV_DIR" ] && [ -f "${VENV_DIR}/bin/activate" ]; then
        source "${VENV_DIR}/bin/activate"
        echo -e "${GREEN}已激活虚拟环境: ${VENV_DIR}${NC}"
    fi
}

deactivate_venv() {
    if [ -n "$VENV_DIR" ] && [ -f "${VENV_DIR}/bin/activate" ]; then
        deactivate 2>/dev/null || true
    fi
}

# ============================================
STEP=0
TOTAL=5

# --------------------------------------------------
STEP=$((STEP+1))
echo -e "\n${YELLOW}[${STEP}/${TOTAL}] 检查 Python 环境...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "${RED}错误：未找到 Python，请先安装 Python 3.8+${NC}"
    exit 1
fi
echo -e "Python: $($PYTHON --version 2>&1)"
echo -e "Django: $($PYTHON -m django --version 2>&1)"

# --------------------------------------------------
STEP=$((STEP+1))
echo -e "\n${YELLOW}[${STEP}/${TOTAL}] 创建必要目录...${NC}"
mkdir -p "${APP_DIR}/logs"
mkdir -p "${APP_DIR}/static"
mkdir -p "${APP_DIR}/media"
echo -e "  ${GREEN}✓${NC} logs/"
echo -e "  ${GREEN}✓${NC} static/"
echo -e "  ${GREEN}✓${NC} media/"

# --------------------------------------------------
STEP=$((STEP+1))
echo -e "\n${YELLOW}[${STEP}/${TOTAL}] 配置环境变量...${NC}"
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    echo -e "  ${YELLOW}已从 .env.example 创建 .env 文件${NC}"
    echo -e "  ${YELLOW}请编辑 ${APP_DIR}/.env 配置数据库连接参数后重新运行本脚本${NC}"
    echo -e "  ${YELLOW}关键配置项：${NC}"
    echo -e "    DJANGO_SECRET_KEY  - Django 密钥（随机 50 位字符串）"
    echo -e "    DJANGO_DEBUG       - 生产环境设为 False"
    echo -e "    DB_ENGINE          - django.db.backends.mysql"
    echo -e "    DB_NAME            - 数据库名"
    echo -e "    DB_USER            - 数据库用户"
    echo -e "    DB_PASSWORD        - 数据库密码"
    echo -e "    DB_HOST            - 数据库地址"
    echo -e "    JWT_SECRET_KEY     - JWT 密钥（随机 32 位字符串）"
    echo -e "    ADMIN_INIT_PASSWORD - 管理员初始密码"
    exit 0
fi
echo -e "  ${GREEN}✓${NC} .env 文件已存在"

# 检查关键配置项
if grep -q "your-secret-key" "${APP_DIR}/.env" 2>/dev/null; then
    echo -e "  ${YELLOW}⚠ 警告：DJANGO_SECRET_KEY 仍为默认值，建议修改为随机密钥${NC}"
fi
if grep -q "change-me" "${APP_DIR}/.env" 2>/dev/null; then
    echo -e "  ${YELLOW}⚠ 警告：存在默认占位值，请检查 .env 配置${NC}"
fi

# --------------------------------------------------
STEP=$((STEP+1))
echo -e "\n${YELLOW}[${STEP}/${TOTAL}] 执行数据库迁移...${NC}"
activate_venv
cd "${APP_DIR}"

echo -e "  ${CYAN}[1/3]${NC} 生成迁移文件..."
$PYTHON manage.py makemigrations 2>&1 | sed 's/^/    /'
if [ $? -ne 0 ]; then
    echo -e "  ${RED}✗ makemigrations 失败${NC}"
    deactivate_venv
    exit 1
fi

echo -e "  ${CYAN}[2/3]${NC} 执行数据库迁移..."
$PYTHON manage.py migrate 2>&1 | sed 's/^/    /'
if [ $? -ne 0 ]; then
    echo -e "  ${RED}✗ migrate 失败${NC}"
    echo -e "  ${YELLOW}请检查 .env 中的数据库连接配置是否正确${NC}"
    deactivate_venv
    exit 1
fi

echo -e "  ${CYAN}[3/3]${NC} 初始化基础数据..."
$PYTHON manage.py init_data 2>&1 | sed 's/^/    /'
if [ $? -ne 0 ]; then
    echo -e "  ${RED}✗ init_data 失败${NC}"
    deactivate_venv
    exit 1
fi
echo -e "  ${GREEN}✓${NC} 数据库初始化完成"

# --------------------------------------------------
STEP=$((STEP+1))
echo -e "\n${YELLOW}[${STEP}/${TOTAL}] 收集静态文件...${NC}"
$PYTHON manage.py collectstatic --noinput 2>&1 | tail -3 | sed 's/^/  /'
if [ $? -ne 0 ]; then
    echo -e "  ${RED}✗ collectstatic 失败${NC}"
    deactivate_venv
    exit 1
fi
echo -e "  ${GREEN}✓${NC} 静态文件已收集到 static/"

# 设置目录权限
echo -e "\n${YELLOW}[权限] 设置目录权限...${NC}"
chmod -R 755 "${APP_DIR}/static" 2>/dev/null
chmod -R 755 "${APP_DIR}/media" 2>/dev/null
chmod -R 755 "${APP_DIR}/logs" 2>/dev/null
# 如果存在 www 用户，设置属主
if id www &>/dev/null; then
    chown -R www:www "${APP_DIR}/logs" 2>/dev/null
    chown -R www:www "${APP_DIR}/static" 2>/dev/null
    chown -R www:www "${APP_DIR}/media" 2>/dev/null
    echo -e "  ${GREEN}✓${NC} 目录属主已设置为 www"
elif id www-data &>/dev/null; then
    chown -R www-data:www-data "${APP_DIR}/logs" 2>/dev/null
    chown -R www-data:www-data "${APP_DIR}/static" 2>/dev/null
    chown -R www-data:www-data "${APP_DIR}/media" 2>/dev/null
    echo -e "  ${GREEN}✓${NC} 目录属主已设置为 www-data"
else
    echo -e "  ${YELLOW}⚠ 未检测到 www/www-data 用户，跳过属主设置${NC}"
    echo -e "  ${YELLOW}  如在宝塔面板下运行，请手动设置权限：${NC}"
    echo -e "  ${YELLOW}  chown -R www:www ${APP_DIR}/logs ${APP_DIR}/static ${APP_DIR}/media${NC}"
fi

deactivate_venv

# ============================================
echo -e "\n${GREEN}==========================================${NC}"
echo -e "${GREEN}  站点初始化完成！${NC}"
echo -e "${GREEN}==========================================${NC}"
echo -e ""
echo -e "后续步骤："
echo -e "  1. 在宝塔面板「网站」→ 进入站点设置"
echo -e "  2. 「Python 项目」选项卡，确认配置："
echo -e "     - 项目路径: ${APP_DIR}"
echo -e "     - 启动脚本: config/wsgi.py"
echo -e "     - 监听端口: 8000"
echo -e "     - Gunicorn 配置: gunicorn.conf.py"
echo -e "  3. 点击「提交」启动站点"
echo -e ""
echo -e "访问地址："
echo -e "  管理后台: http://your-domain.com/admin-panel/"
echo -e "  默认管理员账号: admin"
echo -e "  默认管理员密码: 查看 .env 中的 ADMIN_INIT_PASSWORD"
echo -e ""
echo -e "${YELLOW}安全提醒：首次登录后请立即修改默认密码！${NC}"