#!/usr/bin/env bash
#
# deploy.sh - Build, strip, transfer and restart Cortex-M4 firmware on STM32MP157D-DK1
#
set -euo pipefail

BOARD_IP="${BOARD_IP:-${1:-192.168.0.15}}"
BOARD_USER="${BOARD_USER:-root}"
BOARD_TARGET="stm32mp157c_dk2"
REMOTEPROC="/sys/class/remoteproc/remoteproc0"
REMOTE_FW_DIR="/lib/firmware"
FW_NAME="motor_gateway_m4.elf"
LOCAL_STRIPPED_ELF="${HOME}/${FW_NAME}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================================"
echo " STM32MP157 Cortex-M4 Firmware Deployment"
echo " Target Board: ${BOARD_TARGET}"
echo " Board IP:     ${BOARD_IP}"
echo " Firmware:     ${FW_NAME}"
echo "============================================================"

# 1. Build Zephyr firmware
echo "--> [1/5] Building Zephyr application..."
cd "${PROJECT_DIR}"
west build -b "${BOARD_TARGET}" . -p auto -- -DDTC_OVERLAY_FILE=boards/stm32mp157c_dk2.overlay

BUILD_ELF="${PROJECT_DIR}/build/zephyr/zephyr.elf"
if [ ! -f "${BUILD_ELF}" ]; then
    echo "Error: Build output ${BUILD_ELF} does not exist!" >&2
    exit 1
fi

# 2. Strip debug symbols into ~/motor_gateway_m4.elf (using -g / --strip-debug to preserve .resource_table section)
echo "--> [2/5] Stripping ELF debug symbols to ${LOCAL_STRIPPED_ELF}..."
ZEPHYR_STRIP="${HOME}/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-strip"
if [ -x "${ZEPHYR_STRIP}" ]; then
    "${ZEPHYR_STRIP}" -g "${BUILD_ELF}" -o "${LOCAL_STRIPPED_ELF}"
elif command -v arm-zephyr-eabi-strip >/dev/null 2>&1; then
    arm-zephyr-eabi-strip -g "${BUILD_ELF}" -o "${LOCAL_STRIPPED_ELF}"
else
    echo "Warning: strip tool not found. Copying unstripped binary..."
    cp -f "${BUILD_ELF}" "${LOCAL_STRIPPED_ELF}"
fi

if [ "${BOARD_IP}" = "serial" ]; then
    SERIAL_DEV="${2:-/dev/ttyACM0}"
    echo "--> [3-5] Deploying over Serial (${SERIAL_DEV}) using gzip+base64..."
    sudo stty -F "${SERIAL_DEV}" 115200 raw -echo
    {
        echo ""
        echo "echo stop > ${REMOTEPROC}/state 2>/dev/null || true"
        echo "cat << 'EOF_FW' | base64 -d | gunzip > ${REMOTE_FW_DIR}/${FW_NAME}"
        gzip -c "${LOCAL_STRIPPED_ELF}" | base64
        echo "EOF_FW"
        echo "chmod +x ${REMOTE_FW_DIR}/${FW_NAME}"
        echo "echo '${FW_NAME}' > ${REMOTEPROC}/firmware"
        echo "echo start > ${REMOTEPROC}/state"
    } | sudo tee "${SERIAL_DEV}" > /dev/null
    echo "============================================================"
    echo " Serial deployment sent to ${SERIAL_DEV}!"
    echo "============================================================"
    exit 0
fi

# 3. Stop running remoteproc instance on target
echo "--> [3/5] Stopping remote Cortex-M4 firmware if active..."
ssh "${BOARD_USER}@${BOARD_IP}" "
    if [ -f ${REMOTEPROC}/state ] && grep -q 'running' ${REMOTEPROC}/state; then
        echo stop > ${REMOTEPROC}/state || true
        echo 'remoteproc0 stopped.'
    else
        echo 'remoteproc0 is not in running state.'
    fi
"

# 4. Transfer stripped ELF via scp -O (legacy scp protocol supported by Dropbear/OpenSSH)
echo "--> [4/5] Transferring ${FW_NAME} to ${BOARD_IP}:${REMOTE_FW_DIR}/..."
scp -O "${LOCAL_STRIPPED_ELF}" "${BOARD_USER}@${BOARD_IP}:${REMOTE_FW_DIR}/${FW_NAME}"

# 5. Load and start the firmware
echo "--> [5/5] Launching Cortex-M4 firmware..."
ssh "${BOARD_USER}@${BOARD_IP}" "
    echo '${FW_NAME}' > ${REMOTEPROC}/firmware
    echo start > ${REMOTEPROC}/state
    echo -n 'remoteproc0 state: '
    cat ${REMOTEPROC}/state
"

echo "============================================================"
echo " Deployment completed successfully!"
echo "============================================================"
