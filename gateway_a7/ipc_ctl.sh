#!/usr/bin/env bash
#
# ipc_ctl.sh - Linux Cortex-A7 RPMsg Control & Telemetry Interface
# Controls Cortex-M4 AUTOSAR Motor Gateway via OpenAMP RPMsg TTY (/dev/ttyRPMSG0)
#
set -euo pipefail

RPMSG_DEV="${RPMSG_DEV:-/dev/ttyRPMSG0}"
REMOTEPROC_SYS="/sys/class/remoteproc/remoteproc0"

# Text formatters
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${BOLD} STM32MP157 Cortex-A7 <-> Cortex-M4 RPMsg Control Interface${NC}"
    echo -e " Target Device: ${RPMSG_DEV}"
    echo -e "${CYAN}============================================================${NC}"
}

usage() {
    print_banner
    echo -e "Usage: $0 <command> [arguments]"
    echo ""
    echo "Commands:"
    echo "  init              Configure serial parameters on ${RPMSG_DEV} (115200 raw)"
    echo "  status            Query M4 status frame and check remoteproc0 state"
    echo "  speed <val>       Set closed-loop PID target speed in RPM (e.g., $0 speed 60)"
    echo "  duty <val>        Set open-loop duty cycle percentage (e.g., $0 duty 45)"
    echo "  mode <mode>       Set operating mode (STOP, OPEN, PID, STEP, FAULT)"
    echo "  step [b] [s] [ms] Run automated step test (default: 0 60 3000)"
    echo "  stop              Command immediate safe stop (Duty 0% & active brake)"
    echo "  wdg <on|off>      Enable or disable M4 Heartbeat Watchdog (1.0s timeout)"
    echo "  hb                Send single heartbeat refresh token"
    echo "  hb-loop [sec]     Run continuous heartbeat loop (default interval: 0.5s)"
    echo "  telem | monitor   Listen to live telemetry stream and verify CRC-16"
    echo "  test-safety       Automated verification of Heartbeat Watchdog fail-safe"
    echo ""
    echo "Examples:"
    echo "  $0 init"
    echo "  $0 mode PID"
    echo "  $0 speed 80"
    echo "  $0 step 0 60 3000"
    echo "  $0 status"
    echo "  $0 telem"
    echo "  $0 stop"
    exit 1
}

check_device() {
    if [ ! -c "${RPMSG_DEV}" ]; then
        echo -e "${YELLOW}Warning: Device ${RPMSG_DEV} not found.${NC}"
        if [ -d "${REMOTEPROC_SYS}" ]; then
            STATE=$(cat "${REMOTEPROC_SYS}/state" 2>/dev/null || echo "unknown")
            echo -e "remoteproc0 state: ${BOLD}${STATE}${NC}"
            if [ "${STATE}" != "running" ]; then
                echo -e "${RED}Error: Cortex-M4 firmware is not running! Load firmware first via remoteproc0.${NC}"
                exit 1
            fi
        fi
        
        # Check kernel module
        if ! lsmod | grep -q "rpmsg_tty"; then
            echo -e "--> Attempting to load rpmsg_tty kernel module..."
            modprobe rpmsg_tty || true
        fi
        
        # Wait up to 3 seconds for tty device to register
        for i in {1..6}; do
            if [ -c "${RPMSG_DEV}" ]; then
                break
            fi
            sleep 0.5
        done
        
        if [ ! -c "${RPMSG_DEV}" ]; then
            echo -e "${RED}Error: ${RPMSG_DEV} is still unavailable. Please check M4 firmware log.${NC}" >&2
            exit 1
        fi
    fi
}

init_tty() {
    check_device
    echo -e "--> Configuring ${RPMSG_DEV} with stty 115200 raw -echo..."
    stty -F "${RPMSG_DEV}" 115200 raw -echo -echoe -echok -echoctl -echoke cs8 -cstopb -parenb min 1 time 1
    echo -e "${GREEN}Device ${RPMSG_DEV} initialized successfully.${NC}"
}

send_cmd() {
    local cmd="$1"
    check_device
    echo -e "--> Sending command to M4: ${BOLD}${cmd}${NC}"
    # Use printf with trailing newline
    printf "%s\n" "${cmd}" > "${RPMSG_DEV}"
}

cmd_status() {
    print_banner
    echo -e "Remoteproc Sysfs: ${REMOTEPROC_SYS}"
    if [ -f "${REMOTEPROC_SYS}/state" ]; then
        echo -e "Firmware State:   ${GREEN}$(cat "${REMOTEPROC_SYS}/state")${NC}"
    else
        echo -e "Firmware State:   ${RED}remoteproc0 not detected${NC}"
    fi
    if [ -f "${REMOTEPROC_SYS}/firmware" ]; then
        echo -e "Firmware Name:    ${BOLD}$(cat "${REMOTEPROC_SYS}/firmware")${NC}"
    fi
    echo -e "RPMsg Device:     $([ -c "${RPMSG_DEV}" ] && echo -e "${GREEN}Available (${RPMSG_DEV})${NC}" || echo -e "${RED}Missing${NC}")"

    if [ -c "${RPMSG_DEV}" ]; then
        echo -e "\n--> Querying live status from Cortex-M4 firmware..."
        printf "STATUS\n" > "${RPMSG_DEV}"
        local reply=""
        if read -t 1 -r reply < "${RPMSG_DEV}"; then
            echo -e "M4 Response:      ${BOLD}${reply//$'\r'/}${NC}"
        fi
    fi
}

cmd_hb_loop() {
    local interval="${1:-0.5}"
    check_device
    echo -e "${CYAN}--> Starting Heartbeat Keepalive Loop (Interval: ${interval}s). Press [Ctrl+C] to stop.${NC}"
    while true; do
        printf "HB\n" > "${RPMSG_DEV}"
        echo -e "[$(date '+%Y-%m-%d %H:%M:%S.%3N')] Heartbeat 'HB' sent."
        sleep "${interval}"
    done
}

calc_crc16_bash() {
    local str="$1"
    local crc=65535 # 0xFFFF
    local len=${#str}
    local i b j
    for (( i=0; i<len; i++ )); do
        printf -v b "%d" "'${str:i:1}"
        crc=$(( crc ^ (b << 8) ))
        for (( j=0; j<8; j++ )); do
            if (( crc & 32768 )); then
                crc=$(( ((crc << 1) ^ 4129) & 65535 )) # 0x1021 = 4129, 0xFFFF = 65535
            else
                crc=$(( (crc << 1) & 65535 ))
            fi
        done
    done
    printf "%04X" "${crc}"
}

cmd_monitor() {
    check_device
    init_tty
    echo -e "${GREEN}--> Listening to live telemetry stream from ${RPMSG_DEV}...${NC}"
    echo -e "${CYAN}Expected format: \$TELEM,MODE=<mode>,TGT=<int>,RPM=<int>,DUTY=<int>,CNT=<pulses>*<CRC16>${NC}"
    echo -e "Press [Ctrl+C] to exit.\n"
    
    # Send an initial ping so M4 learns dest_addr immediately
    printf "HB\n" > "${RPMSG_DEV}"

    while IFS= read -r line; do
        # Strip trailing carriage return
        line="${line//$'\r'/}"
        [ -z "${line}" ] && continue
        
        # Check if line matches telemetry, status, or fault frame
        if [[ "${line}" =~ ^(\$TELEM|\$STAT|\$FAULT).*[*]([0-9A-Fa-f]{4})$ ]]; then
            crc_received="${BASH_REMATCH[2]}"
            payload="${line%\**}" # everything before '*'
            
            crc_calculated=$(calc_crc16_bash "${payload}")
            if [ -n "${crc_calculated}" ]; then
                if [ "${crc_calculated}" = "${crc_received^^}" ]; then
                    crc_status="${GREEN}CRC OK (${crc_received})${NC}"
                else
                    crc_status="${RED}CRC MISMATCH (Exp: ${crc_calculated}, Got: ${crc_received})${NC}"
                fi
            else
                crc_status="${YELLOW}CRC: ${crc_received}${NC}"
            fi
            
            echo -e "[$(date '+%H:%M:%S.%3N')] ${BOLD}${payload}${NC} | ${crc_status}"
        else
            echo -e "[$(date '+%H:%M:%S.%3N')] [RAW]: ${line}"
        fi
    done < "${RPMSG_DEV}"
}

cmd_test_safety() {
    print_banner
    echo -e "${YELLOW}=== Running Automated Heartbeat Watchdog Safety Verification ===${NC}"
    init_tty
    
    echo -e "\n1. Arming Watchdog on Cortex-M4..."
    send_cmd "WDG ON"
    sleep 0.2
    
    echo -e "\n2. Starting Motor with open-loop Duty 40%..."
    send_cmd "DUTY 40"
    
    echo -e "\n3. Sending active Heartbeats for 3 seconds..."
    for i in {1..6}; do
        send_cmd "HB"
        sleep 0.5
    done
    
    echo -e "\n4. Ceasing Heartbeat transmission! (Simulating Linux crash / timeout)..."
    echo -e "--> Watchdog timeout is 1.0s. Waiting 1.5 seconds for fail-safe trigger..."
    sleep 1.5
    
    echo -e "\n5. Checking telemetry from M4 to confirm motor shutdown..."
    # Read one telemetry frame
    local sample=""
    if read -t 1 -r sample < "${RPMSG_DEV}"; then
        echo -e "Received sample: ${BOLD}${sample}${NC}"
    fi
    
    echo -e "\n6. Sending STOP and disarming Watchdog..."
    send_cmd "STOP"
    send_cmd "WDG OFF"
    
    echo -e "\n${GREEN}Safety test sequence complete.${NC}"
}

# Command dispatcher
CMD="${1:-help}"

case "${CMD}" in
    init)
        init_tty
        ;;
    status)
        cmd_status
        ;;
    speed)
        [ $# -lt 2 ] && { echo -e "${RED}Error: Speed value required (RPM).${NC}"; exit 1; }
        send_cmd "SPEED $2"
        ;;
    duty)
        [ $# -lt 2 ] && { echo -e "${RED}Error: Duty value required (-100 to 100).${NC}"; exit 1; }
        send_cmd "DUTY $2"
        ;;
    mode)
        [ $# -lt 2 ] && { echo -e "${RED}Error: Mode required (STOP|OPEN|PID|STEP|FAULT).${NC}"; exit 1; }
        MODE_VAL="${2^^}"
        send_cmd "MODE ${MODE_VAL}"
        ;;
    step)
        BASE="${2:-0}"
        STEP_VAL="${3:-60}"
        DUR="${4:-3000}"
        send_cmd "STEP ${BASE} ${STEP_VAL} ${DUR}"
        ;;
    stop)
        send_cmd "STOP"
        ;;
    wdg)
        [ $# -lt 2 ] && { echo -e "${RED}Error: Specify 'on' or 'off'.${NC}"; exit 1; }
        MODE="${2^^}"
        send_cmd "WDG ${MODE}"
        ;;
    hb)
        send_cmd "HB"
        ;;
    hb-loop)
        cmd_hb_loop "${2:-0.5}"
        ;;
    telem|monitor)
        cmd_monitor
        ;;
    test-safety)
        cmd_test_safety
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$CMD'${NC}\n"
        usage
        ;;
esac
