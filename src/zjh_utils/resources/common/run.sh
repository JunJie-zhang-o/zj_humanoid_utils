#!/bin/bash
################################################################################
# File: run.sh
# Path: /home/nav01/zj_humanoid/run.sh
# Description: SDK startup script
# Features:
#   1. Configure environment variables
#   2. Back up previous configuration
#   3. Launch the robot system
#
# Usage:
#   When using sudo, preserve environment variables with -E flag:
#   $ sudo -E ./run.sh
#   
#   Or set ROBOT_TYPE before running:
#   $ sudo ROBOT_TYPE=I2 -E ./run.sh
################################################################################

set -e  # Exit immediately on any error
VERSION="V1.1.0"
export ROBOT_TYPE=""
# ======================== Color Definitions ========================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

if [ ! -t 1 ]; then
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    NC=''
fi

# ======================== Logging Helpers ========================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}>>>${NC} $1"
}

show_version() {
    echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     ZJ Humanoid Robot SDK              ║${NC}"
    echo -e "${CYAN}║     Version: ${VERSION}                    ║${NC}"
    echo -e "${CYAN}║     $(date '+%Y-%m-%d %H:%M:%S')               ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# ======================== Path Definitions ========================
WORKSPACE_ROOT="/home/nav01/zj_humanoid"
CONFIG_DIR="${WORKSPACE_ROOT}/config"
STARTUP_DIR="${WORKSPACE_ROOT}/startup"
LOG_DIR="${WORKSPACE_ROOT}/logs"
SCRIPT_DIR="${WORKSPACE_ROOT}/scripts"
SHARED_DIR="${WORKSPACE_ROOT}/shared"
ORIN_DIR="${WORKSPACE_ROOT}/orin"

# ======================== Logging Setup ========================
initialize_logging() {
    mkdir -p "${LOG_DIR}"
    chmod 755 "${LOG_DIR}" >/dev/null 2>&1 || true

    export RUN_LOG_FILE="${LOG_DIR}/run.log"
    
    local MAX_LOG_SIZE=$((10 * 1024 * 1024))
    local MAX_LOG_FILES=5
    
    if [ -f "${RUN_LOG_FILE}" ]; then
        local current_size=$(stat -f%z "${RUN_LOG_FILE}" 2>/dev/null || stat -c%s "${RUN_LOG_FILE}" 2>/dev/null || echo 0)
        
        if [ "$current_size" -ge "$MAX_LOG_SIZE" ]; then
            log_info "Log rotation triggered"
            
            for i in $(seq $((MAX_LOG_FILES - 1)) -1 1); do
                if [ -f "${LOG_DIR}/run.log.$i" ]; then
                    mv "${LOG_DIR}/run.log.$i" "${LOG_DIR}/run.log.$((i + 1))"
                fi
            done
            
            mv "${RUN_LOG_FILE}" "${LOG_DIR}/run.log.1"
            
            if [ -f "${LOG_DIR}/run.log.$((MAX_LOG_FILES + 1))" ]; then
                rm -f "${LOG_DIR}/run.log.$((MAX_LOG_FILES + 1))"
            fi
        fi
    fi
    
    touch "${RUN_LOG_FILE}"
    chmod 644 "${RUN_LOG_FILE}" >/dev/null 2>&1 || true
}

# ======================== Environment Configuration ========================
setup_environment() {
    log_step "Configuring environment..."
    
    export ROSCONSOLE_FORMAT='[${severity}] [${time}]: ${message}'
    export ROBOT_TYPE="${ROBOT_TYPE:-I2}"
    export ROBOT_NAME="${ROBOT_NAME:-zj_humanoid}"
    export ROS_FILE_LOG_DIR="${ROS_FILE_LOG_DIR:-/tmp/zj_humanoid_ros_logs}"
    export ROS_LOG_DIR="${ROS_FILE_LOG_DIR}"
    mkdir -p "${ROS_LOG_DIR}"
    chmod 755 "${ROS_LOG_DIR}" >/dev/null 2>&1 || true
    export PYTHONUNBUFFERED=1
    export ROSCONSOLE_STDOUT_LINE_BUFFERED=1
    
    case "$ROBOT_TYPE" in
        WA1|WA2)
            export ROS_IP="192.168.217.66"
            export ROS_MASTER_URI="http://192.168.217.1:11311"
            ;;
        *)
            export ROS_IP="192.168.217.66"
            export ROS_MASTER_URI="http://192.168.217.100:11311"
            ;;
    esac
    
    export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:/opt/ros/noetic/lib/pico_runtime"
    
    case "$ROBOT_TYPE" in
        WA1)
            export UPLIMB_CONFIG_FILE_PATH="/opt/ros/noetic/share/pico_runtime/uplimb/config/robot_define_WA1.yaml"
            ;;
        WA2)
            export UPLIMB_CONFIG_FILE_PATH="/opt/ros/noetic/share/pico_runtime/uplimb/config/robot_define_wa2.yaml"
            ;;
        H1|I2)
            export UPLIMB_CONFIG_FILE_PATH="/opt/ros/noetic/share/pico_runtime/uplimb/config/robot_define_upper_body.yaml"
            ;;
        I180)
            export UPLIMB_CONFIG_FILE_PATH="/opt/ros/noetic/share/pico_runtime/uplimb/config/robot_define_i180.yaml"
            ;;
        *)
            log_error "Unknown robot type: $ROBOT_TYPE (Supported: WA1, WA2, H1, I2, I180)"
            return 1
            ;;
    esac
    
    log_info "ROBOT_TYPE=${ROBOT_TYPE}, ROS_MASTER=${ROS_MASTER_URI}"
    
    return 0
}

# ======================== Directory Checks ========================
check_directories() {
    local directories=("$CONFIG_DIR" "$STARTUP_DIR" "$LOG_DIR" "$SCRIPT_DIR" "$SHARED_DIR")
    
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
        fi
    done
}

# ======================== ROS Environment Checks ========================
check_ros_environment() {
    log_step "Checking ROS environment..."
    
    if [ -f "/opt/ros/noetic/setup.bash" ]; then
        source /opt/ros/noetic/setup.bash
        
        ADDITIONAL_WORKSPACES="${ADDITIONAL_ROS_WORKSPACES:-/home/nav01/catkin_ws_amp_show}"
        
        if [ -n "$ADDITIONAL_WORKSPACES" ]; then
            IFS=':' read -r -a _wss_arr <<< "$ADDITIONAL_WORKSPACES"
            for ws in "${_wss_arr[@]}"; do
                if [ -f "$ws/devel/setup.bash" ]; then
                    source "$ws/devel/setup.bash"
                elif [ -f "$ws/install/setup.bash" ]; then
                    source "$ws/install/setup.bash"
                fi
            done
        fi
    else
        log_error "ROS installation not found"
        return 1
    fi
    
    if ! rostopic list &> /dev/null; then
        log_warn "Starting ROS Master..."
        roscore &
        sleep 3
    fi
    
    log_info "ROS environment ready"
    return 0
}

# ======================== Enable Core Dump ========================
enable_core_dump() {
    ulimit -c unlimited
    
    local core_pattern="/tmp/core.%e.%p.%t"
    
    if [ -w "/proc/sys/kernel/core_pattern" ]; then
        echo "$core_pattern" > /proc/sys/kernel/core_pattern
    fi
    
    return 0
}

# ======================== Start Robot System ========================
start_robot_system() {
    log_step "Starting robot system..."
    
    local startup_script="${STARTUP_DIR}/startup_manager.py"
    
    if [ ! -f "$startup_script" ]; then
        log_error "Startup script missing: $startup_script"
        return 1
    fi
    
    chmod +x "$startup_script"
    python3 "$startup_script"
    
    return $?
}

# ======================== Cleanup Handler ========================
cleanup() {
    log_info "Cleanup completed"
}

# ======================== Main Flow ========================
main() {
    show_version
    initialize_logging
    
    trap cleanup EXIT INT TERM
    
    check_directories || exit 1
    setup_environment || exit 1
    check_ros_environment || exit 1
    enable_core_dump || exit 1
    start_robot_system
    
    exit $?
}

# ======================== Script Entry Point ========================
mkdir -p "${WORKSPACE_ROOT}/logs"
RUN_LOG_FILE="${WORKSPACE_ROOT}/logs/run.log"

exec > >(exec stdbuf -oL tee -a "$RUN_LOG_FILE") 2>&1

main "$@"