#!/bin/bash
################################################################################
# File: install_autostart_service.sh
# Path: /home/nav01/zj_humanoid/scripts/install_autostart_service.sh
# Description: Install a systemd service that launches the robot stack on boot.
################################################################################

set -euo pipefail

# ======================== Logging Helpers ========================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n========================================"
    echo "$1"
    echo "========================================\n"
}

# ======================== Constants ========================
SERVICE_NAME="zj_humanoid.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
WORKSPACE_ROOT="/home/nav01/zj_humanoid"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_TEMPLATE="${SCRIPT_DIR}/${SERVICE_NAME}"
RUN_SCRIPT="${WORKSPACE_ROOT}/run.sh"
SERVICE_USER="root"
SERVICE_GROUP="root"
LOG_DIR="${WORKSPACE_ROOT}/logs"
ROS_LOG_DIR="${LOG_DIR}/ros"
RUN_LOG_FILE="${LOG_DIR}/run.log"
LOGROTATE_CONF="/etc/logrotate.d/zj_humanoid"

print_usage() {
    cat <<USAGE
Usage: sudo ${WORKSPACE_ROOT}/scripts/install_autostart_service.sh [install|uninstall]

Commands:
  install    Install or update the zj_humanoid systemd service (default if omitted)
  uninstall  Disable and remove the zj_humanoid systemd service
USAGE
}

# ======================== Guards ========================
if [[ $(id -u) -ne 0 ]]; then
    log_error "This installer must be executed with root privileges."
    log_info "Hint: sudo ${WORKSPACE_ROOT}/scripts/install_autostart_service.sh"
    exit 1
fi

COMMAND="${1:-install}"

install_service() {
    if [[ ! -f "${RUN_SCRIPT}" ]]; then
        log_error "Missing startup script: ${RUN_SCRIPT}"
        exit 1
    fi

    if [[ ! -f "${SERVICE_TEMPLATE}" ]]; then
        log_error "Missing service template: ${SERVICE_TEMPLATE}"
        exit 1
    fi

    chmod +x "${RUN_SCRIPT}"
    log_info "Ensured ${RUN_SCRIPT} is executable."

    log_info "Ensuring log directories exist"
    mkdir -p "${LOG_DIR}" "${ROS_LOG_DIR}"
    chmod 755 "${LOG_DIR}" "${ROS_LOG_DIR}" >/dev/null 2>&1 || true
    touch "${RUN_LOG_FILE}"
    chmod 644 "${RUN_LOG_FILE}" >/dev/null 2>&1 || true

    log_info "Configuring logrotate policy at ${LOGROTATE_CONF}"
    cat <<EOF > "${LOGROTATE_CONF}"
${RUN_LOG_FILE} ${ROS_LOG_DIR}/*.log {
    size 20M
    rotate 10
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
    log_info "Service output will stream to ${RUN_LOG_FILE}"

    log_info "Writing systemd service to ${SERVICE_PATH}"
    cp "${SERVICE_TEMPLATE}" "${SERVICE_PATH}"

    log_info "Reloading systemd daemon"
    systemctl daemon-reload

    # Check if service is masked and unmask it if necessary
    if systemctl is-enabled "${SERVICE_NAME}" 2>&1 | grep -q "masked"; then
        log_warn "Service is masked. Unmasking ${SERVICE_NAME}"
        systemctl unmask "${SERVICE_NAME}"
    fi

    if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
        log_info "Service already enabled."
    else
        log_info "Enabling ${SERVICE_NAME}"
        systemctl enable "${SERVICE_NAME}"
    fi

    log_info "Starting ${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}" || systemctl start "${SERVICE_NAME}"

    log_info "Service status summary:"
    systemctl --no-pager --full status "${SERVICE_NAME}" || true

    log_section "Installation complete. The robot stack will start at boot."
    log_info "Use 'sudo systemctl restart ${SERVICE_NAME}' to restart manually."
    log_info "Use 'sudo systemctl disable ${SERVICE_NAME}' to disable autostart."
}

uninstall_service() {
    log_section "Uninstalling ${SERVICE_NAME}"

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log_info "Stopping ${SERVICE_NAME}"
        systemctl stop "${SERVICE_NAME}"
    else
        log_info "Service is not running."
    fi

    # Unmask service if it's masked
    if systemctl is-enabled "${SERVICE_NAME}" 2>&1 | grep -q "masked"; then
        log_info "Unmasking ${SERVICE_NAME}"
        systemctl unmask "${SERVICE_NAME}"
    fi

    if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
        log_info "Disabling ${SERVICE_NAME}"
        systemctl disable "${SERVICE_NAME}"
    else
        log_info "Service already disabled."
    fi

    if [[ -f "${SERVICE_PATH}" ]]; then
        log_info "Removing ${SERVICE_PATH}"
        rm -f "${SERVICE_PATH}"
    else
        log_info "Service file already removed."
    fi

    log_info "Reloading systemd daemon"
    systemctl daemon-reload
    systemctl reset-failed "${SERVICE_NAME}" >/dev/null 2>&1 || true

    if [[ -f "${LOGROTATE_CONF}" ]]; then
        log_info "Removing logrotate configuration ${LOGROTATE_CONF}"
        rm -f "${LOGROTATE_CONF}"
    fi

    log_section "Uninstall complete. The service will not start at boot."
}

case "${COMMAND}" in
    install)
        log_section "Installing ${SERVICE_NAME}"
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    -h|--help|help)
        print_usage
        exit 0
        ;;
    *)
        log_error "Unknown command: ${COMMAND}"
        print_usage
        exit 1
        ;;
esac
