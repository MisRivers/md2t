#!/bin/bash
# md2t 部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印信息
echo -e "${GREEN}=== md2t 部署脚本 ===${NC}"

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${YELLOW}Python 版本: $python_version${NC}"

# 创建虚拟环境
echo -e "${YELLOW}创建虚拟环境...${NC}"
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装依赖...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 检查环境变量
if [ -z "$SECRET_KEY" ]; then
    echo -e "${RED}警告: 未设置 SECRET_KEY 环境变量${NC}"
    echo -e "${YELLOW}请设置强密钥: export SECRET_KEY=your-secret-key${NC}"
fi

if [ -z "$ADMIN_PASSWORD_HASH" ]; then
    echo -e "${RED}警告: 未设置 ADMIN_PASSWORD_HASH 环境变量${NC}"
    echo -e "${YELLOW}将使用默认密码: admin123${NC}"
fi

# 初始化数据库
echo -e "${YELLOW}初始化数据库...${NC}"
python3 -c "from app import init_db; init_db()"

# 测试启动
echo -e "${YELLOW}测试启动...${NC}"
timeout 5 python3 app.py &
sleep 3
kill %1 2>/dev/null || true

echo -e "${GREEN}=== 部署完成 ===${NC}"
echo ""
echo "启动命令:"
echo "  开发模式: python3 app.py"
echo "  生产模式: gunicorn -c gunicorn.conf.py wsgi:app"
echo ""
echo "后台管理地址: http://localhost:5000/admin/login"
echo "默认账号: admin / admin123"
