#!/bin/bash
################################################################################
# 文件: install.sh
# 位置: /home/nav01/zj_humanoid/scripts/install.sh
# 说明: SDK 安装脚本
# 功能: 初始化文件系统结构，设置权限，安装依赖
################################################################################

set -e

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 工作空间根目录
WORKSPACE_ROOT="/home/nav01/zj_humanoid"

# 创建目录结构
create_directory_structure() {
    log_info "创建目录结构..."
    
    mkdir -p "${WORKSPACE_ROOT}/shared"
    mkdir -p "${WORKSPACE_ROOT}/orin"
    mkdir -p "${WORKSPACE_ROOT}/dists/v1.0.0"
    mkdir -p "${WORKSPACE_ROOT}/config"
    mkdir -p "${WORKSPACE_ROOT}/logs"
    mkdir -p "${WORKSPACE_ROOT}/scripts"
    mkdir -p "${WORKSPACE_ROOT}/startup"
    
    log_info "✓ 目录结构创建完成"
}

# 设置权限
set_permissions() {
    log_info "设置文件权限..."
    
    # run.sh 可执行
    chmod +x "${WORKSPACE_ROOT}/run.sh"
    
    # 所有脚本可执行
    find "${WORKSPACE_ROOT}/scripts" -type f -name "*.sh" -exec chmod +x {} \;
    find "${WORKSPACE_ROOT}/startup" -type f -name "*.py" -exec chmod +x {} \;
    
    log_info "✓ 权限设置完成"
}

# 安装依赖
install_dependencies() {
    log_info "检查依赖..."
    
    # 检查 Python3
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    log_info "✓ 依赖检查完成"
}

# 显示安装信息
show_info() {
    echo ""
    echo "========================================"
    echo "  SDK 安装完成"
    echo "========================================"
    echo ""
    echo "目录结构:"
    echo "  ${WORKSPACE_ROOT}/"
    echo "  ├── shared/       # Orin 单向映射内容"
    echo "  ├── orin/         # Orin 映射到 Pico 的内容"
    echo "  ├── dists/        # deb 包存放"
    echo "  ├── config/       # 配置文件"
    echo "  ├── logs/         # 日志存储"
    echo "  ├── scripts/      # 脚本"
    echo "  ├── startup/      # 启动文件"
    echo "  └── run.sh        # 启动脚本"
    echo ""
    echo "使用方法:"
    echo "  1. 设置机器人类型 (可选):"
    echo "     export ROBOT_TYPE=WA1  # WA1, WA2, H1, I2, I180"
    echo ""
    echo "  2. 启动系统:"
    echo "     cd ${WORKSPACE_ROOT}"
    echo "     ./run.sh"
    echo ""
}

# 主流程
main() {
    log_info "开始安装 SDK..."
    
    create_directory_structure
    set_permissions
    install_dependencies
    
    show_info
}

main "$@"
