#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/ipm.h>
#include <zephyr/sys/printk.h>
#include <openamp/open_amp.h>
#include <metal/alloc.h>
#include <metal/device.h>
#include <metal/io.h>
#include <resource_table.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "Cdd_Ipc.h"
#include "Mcal_Icu.h"
#include "Rte.h"
#include "Swc_SafetyManager.h"

/* Shared memory parameters from Device Tree chosen nodes */
#if DT_HAS_CHOSEN(zephyr_ipc_shm)
#define SHM_NODE        DT_CHOSEN(zephyr_ipc_shm)
#define SHM_START_ADDR  DT_REG_ADDR(SHM_NODE)
#define SHM_SIZE        DT_REG_SIZE(SHM_NODE)
#else
#define SHM_START_ADDR  0x10040000u
#define SHM_SIZE        0x00020000u
#endif

#define SHM_DEVICE_NAME "openamp_shm"
#define VRING_COUNT     2

/* Watchdog timeout ticks (100 ticks @ 10ms = 1.0s timeout) */
#define WDG_TIMEOUT_TICKS 100u

/* IPM Mailbox Handle for STM32MP1 IPCC */
#if DT_HAS_CHOSEN(zephyr_ipc)
static const struct device *const s_ipm_handle = DEVICE_DT_GET(DT_CHOSEN(zephyr_ipc));
#elif DT_NODE_HAS_STATUS(DT_NODELABEL(mailbox), okay)
static const struct device *const s_ipm_handle = DEVICE_DT_GET(DT_NODELABEL(mailbox));
#else
static const struct device *const s_ipm_handle = NULL;
#endif

/* OpenAMP & VirtIO structures */
static struct rpmsg_virtio_device s_rvdev;
static struct rpmsg_device *s_rpdev = NULL;
static struct rpmsg_endpoint s_tty_ept;

static struct metal_io_region s_shm_io_region;
static struct metal_io_region s_rsc_io_region;
static struct metal_io_region *s_shm_io = NULL;
static struct metal_io_region *s_rsc_io = NULL;

/* Synchronization & Scheduling Primitives */
K_SEM_DEFINE(s_ipc_sem, 0, 100);
static volatile boolean s_send_telem_requested = FALSE;
static volatile boolean s_watchdog_enabled = FALSE;
static volatile uint32 s_hb_timeout_10ms = 0u;
static uint32 s_telem_tick_count = 0u;

/* Forward declarations */
void Cdd_Ipc_ThreadEntry(void *p1, void *p2, void *p3);
static int Cdd_Ipc_RxCallback(struct rpmsg_endpoint *ept, void *data,
                             size_t len, uint32_t src, void *priv);
static void Cdd_Ipc_SendTelemetry(void);
static void Cdd_Ipc_SendStatus(void);
static void Cdd_Ipc_ProcessCommand(char *cmd);

/* Zephyr Preemptive Thread Definition for OpenAMP RPMsg Worker */
K_THREAD_DEFINE(cdd_ipc_thread, 4096, Cdd_Ipc_ThreadEntry, NULL, NULL, NULL, K_PRIO_PREEMPT(5), 0, 0);

/* CRC-16-CCITT (poly = 0x1021, init = 0xFFFF, refin = false, refout = false) */
uint16 Cdd_Ipc_CalcCrc16(const uint8 *data, uint16 length)
{
    uint16 crc = 0xFFFFu;

    if (data == NULL) {
        return 0u;
    }

    for (uint16 i = 0u; i < length; i++) {
        crc ^= (uint16)((uint16)data[i] << 8);
        for (uint8 j = 0u; j < 8u; j++) {
            if ((crc & 0x8000u) != 0u) {
                crc = (uint16)((crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16)(crc << 1);
            }
        }
    }

    return crc;
}

/* IPM Mailbox Interrupt Callback */
static void Cdd_Ipc_IpmCallback(const struct device *dev, void *context,
                                uint32_t id, volatile void *data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(context);
    ARG_UNUSED(id);
    ARG_UNUSED(data);

    k_sem_give(&s_ipc_sem);
}

/* Virtqueue Kick Notification Callback */
static int Virtio_Notify(void *priv, uint32_t id)
{
    ARG_UNUSED(priv);
    if (s_ipm_handle != NULL && device_is_ready(s_ipm_handle)) {
        (void)ipm_send(s_ipm_handle, 0, id, NULL, 0);
    }
    return 0;
}

/* Platform-specific VirtIO & RPMsg device initialization */
static struct rpmsg_device *Platform_Create_Rpmsg_Vdev(void)
{
    void *rsc_table = NULL;
    int rsc_size = 0;
    struct fw_rsc_vdev_vring *vring_rsc;
    struct virtio_device *vdev;
    struct metal_init_params metal_params = METAL_INIT_DEFAULTS;
    metal_phys_addr_t shm_physmap = SHM_START_ADDR;
    metal_phys_addr_t rsc_physmap;
    int ret;

    ret = metal_init(&metal_params);
    if (ret != 0) {
        printk("[CDD_IPC] metal_init failed: %d\n", ret);
        return NULL;
    }

    rsc_table_get(&rsc_table, &rsc_size);
    if (rsc_table == NULL) {
        printk("[CDD_IPC] rsc_table_get returned NULL!\n");
        return NULL;
    }

    rsc_physmap = (metal_phys_addr_t)(uintptr_t)rsc_table;

    metal_io_init(&s_shm_io_region, (void *)SHM_START_ADDR, &shm_physmap,
                  SHM_SIZE, -1, 0, NULL);
    s_shm_io = &s_shm_io_region;

    metal_io_init(&s_rsc_io_region, rsc_table, &rsc_physmap,
                  rsc_size, -1, 0, NULL);
    s_rsc_io = &s_rsc_io_region;

    /* Register IPCC Mailbox interrupt callback */
    if (s_ipm_handle != NULL && device_is_ready(s_ipm_handle)) {
        ipm_register_callback(s_ipm_handle, Cdd_Ipc_IpmCallback, NULL);
        (void)ipm_set_enabled(s_ipm_handle, 1);
    } else {
        printk("[CDD_IPC] Warning: IPM device not ready or null\n");
    }

    /* Create OpenAMP VirtIO device (RPMSG_REMOTE = Cortex-M4 slave/device) */
    vdev = rproc_virtio_create_vdev(RPMSG_REMOTE, 0,
                                    rsc_table_to_vdev(rsc_table),
                                    s_rsc_io, NULL, Virtio_Notify, NULL);
    if (vdev == NULL) {
        printk("[CDD_IPC] rproc_virtio_create_vdev failed!\n");
        return NULL;
    }

    printk("[CDD_IPC] Synchronizing: Waiting for Linux Cortex-A7 remoteproc ready...\n");
    rproc_virtio_wait_remote_ready(vdev);
    printk("[CDD_IPC] Linux Cortex-A7 remoteproc DRIVER_OK established!\n");

    /* Initialize VirtIO vring 0 */
    vring_rsc = rsc_table_get_vring0(rsc_table);
    ret = rproc_virtio_init_vring(vdev, 0, vring_rsc->notifyid,
                                  (void *)vring_rsc->da, s_shm_io,
                                  vring_rsc->num, vring_rsc->align);
    if (ret != 0) {
        printk("[CDD_IPC] rproc_virtio_init_vring 0 failed: %d\n", ret);
        return NULL;
    }

    /* Initialize VirtIO vring 1 */
    vring_rsc = rsc_table_get_vring1(rsc_table);
    ret = rproc_virtio_init_vring(vdev, 1, vring_rsc->notifyid,
                                  (void *)vring_rsc->da, s_shm_io,
                                  vring_rsc->num, vring_rsc->align);
    if (ret != 0) {
        printk("[CDD_IPC] rproc_virtio_init_vring 1 failed: %d\n", ret);
        return NULL;
    }

    /* Initialize RPMsg VirtIO device */
    ret = rpmsg_init_vdev(&s_rvdev, vdev, NULL, s_shm_io, NULL);
    if (ret != 0) {
        printk("[CDD_IPC] rpmsg_init_vdev failed: %d\n", ret);
        return NULL;
    }

    return rpmsg_virtio_get_rpmsg_device(&s_rvdev);
}

/* Format and transmit one-shot Status frame */
static void Cdd_Ipc_SendStatus(void)
{
    const char *mode_str = Rte_Get_MotorModeString(Rte_Get_MotorMode());
    float32 tgt_speed = Rte_Get_ppTargetSpeed_rpm();
    float32 cur_speed = Icu_GetSpeedRpm();
    float32 cur_duty  = Rte_Get_ppDuty_percentage();
    const char *wdg_str = s_watchdog_enabled ? "ON" : "OFF";
    int estop_val = (Rte_Get_EmergencyStop() != FALSE) ? 1 : 0;

    char payload[96];
    char frame[128];

    int len = snprintf(payload, sizeof(payload),
                       "$STAT,MODE=%s,TGT=%d,RPM=%d,DUTY=%d,WDG=%s,ESTOP=%d",
                       mode_str, (int)tgt_speed, (int)cur_speed, (int)cur_duty, wdg_str, estop_val);
    if (len > 0) {
        uint16 crc = Cdd_Ipc_CalcCrc16((const uint8 *)payload, (uint16)len);
        int frame_len = snprintf(frame, sizeof(frame), "%s*%04X\r\n", payload, crc);
        if (frame_len > 0 && s_tty_ept.dest_addr != RPMSG_ADDR_ANY) {
            (void)rpmsg_send(&s_tty_ept, frame, frame_len);
        }
    }
}

/* Transmit immediate Safety Fault Notification frame */
static volatile boolean s_fault_pending = FALSE;
static char s_fault_reason[24];

/* Non-blocking: called from 10ms RT task, frame is sent later by IPC thread */
void Cdd_Ipc_SendFaultNotice(const char *reason)
{
    const char *r = (reason != NULL) ? reason : "UNKNOWN";
    size_t i = 0u;
    while ((r[i] != '\0') && (i < (sizeof(s_fault_reason) - 1u))) {
        s_fault_reason[i] = r[i];
        i++;
    }
    s_fault_reason[i] = '\0';
    s_fault_pending = TRUE;
    k_sem_give(&s_ipc_sem);
}

static void Cdd_Ipc_FlushFault(void)
{
    if ((s_fault_pending == FALSE) || (s_tty_ept.dest_addr == RPMSG_ADDR_ANY)) {
        return;
    }
    s_fault_pending = FALSE;
    char payload[48];
    char frame[64];
    int len = snprintf(payload, sizeof(payload), "$FAULT,REASON=%s", s_fault_reason);
    if (len > 0) {
        uint16 crc = Cdd_Ipc_CalcCrc16((const uint8 *)payload, (uint16)len);
        int frame_len = snprintf(frame, sizeof(frame), "%s*%04X\r\n", payload, crc);
        if (frame_len > 0) {
            (void)rpmsg_send(&s_tty_ept, frame, frame_len);
        }
    }
}

/* Command string parsing and execution */
static void Cdd_Ipc_ProcessCommand(char *cmd)
{
    while (*cmd == ' ' || *cmd == '\t' || *cmd == '\r' || *cmd == '\n') {
        cmd++;
    }

    char *end = cmd + strlen(cmd);
    while (end > cmd && (*(end - 1) == ' ' || *(end - 1) == '\t' ||
                         *(end - 1) == '\r' || *(end - 1) == '\n')) {
        end--;
        *end = '\0';
    }

    if (*cmd == '\0') {
        return;
    }

    if (strcmp(cmd, "HB") == 0) {
        s_hb_timeout_10ms = 0u;
    } else if (strcmp(cmd, "PIR ON") == 0) {
        Swc_SafetyManager_SetPirEnable(TRUE);
        printk("[CDD_IPC] CMD PIR ON: PIR safety supervision enabled\n");
    } else if (strcmp(cmd, "PIR OFF") == 0) {
        Swc_SafetyManager_SetPirEnable(FALSE);
        printk("[CDD_IPC] CMD PIR OFF: PIR safety supervision disabled\n");
    } else if (strcmp(cmd, "CLEAR") == 0 || strcmp(cmd, "RESET") == 0) {
        Swc_SafetyManager_ClearFault();
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_MotorMode(MOTOR_MODE_STOPPED);
        Rte_Set_TargetDuty_percentage(0.0f);
        Rte_Set_rpTargetSpeed_rpm(0.0f);
        printk("[CDD_IPC] CMD CLEAR: Safety faults reset and motor returned to STOPPED\n");
    } else if (strcmp(cmd, "ESTOP") == 0) {
        Rte_Set_EmergencyStop(TRUE);
        Rte_Set_MotorMode(MOTOR_MODE_FAULT);
        Rte_Set_TargetDuty_percentage(0.0f);
        Rte_Set_rpTargetSpeed_rpm(0.0f);
        Cdd_Ipc_SendFaultNotice("MANUAL_ESTOP");
        printk("[CDD_IPC] CMD ESTOP: Forced manual emergency stop\n");
    } else if (strcmp(cmd, "WDG ON") == 0) {
        s_watchdog_enabled = TRUE;
        s_hb_timeout_10ms = 0u;
        printk("[CDD_IPC] CMD WDG ON: Watchdog enabled (1.0s timeout)\n");
    } else if (strcmp(cmd, "WDG OFF") == 0) {
        s_watchdog_enabled = FALSE;
        s_hb_timeout_10ms = 0u;
        Rte_Set_EmergencyStop(FALSE);
        printk("[CDD_IPC] CMD WDG OFF: Watchdog disabled\n");
    } else if (strcmp(cmd, "STOP") == 0) {
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_MotorMode(MOTOR_MODE_STOPPED);
        Rte_Set_TargetDuty_percentage(0.0f);
        Rte_Set_rpTargetSpeed_rpm(0.0f);
        printk("[CDD_IPC] CMD STOP: Motor stopped safely\n");
    } else if (strncmp(cmd, "SPEED", 5) == 0 && (cmd[5] == ' ' || cmd[5] == '\t' || cmd[5] == '\0')) {
        char *arg = &cmd[5];
        while (*arg == ' ' || *arg == '\t') {
            arg++;
        }
        float32 speed_val = (float32)strtod(arg, NULL);
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_rpTargetSpeed_rpm(speed_val);
        Rte_Set_MotorMode((speed_val > -0.5f && speed_val < 0.5f) ? MOTOR_MODE_STOPPED : MOTOR_MODE_CLOSED_LOOP);
        printk("[CDD_IPC] CMD SPEED: %d RPM (Closed-loop PID)\n", (int)speed_val);
    } else if (strncmp(cmd, "DUTY", 4) == 0 && (cmd[4] == ' ' || cmd[4] == '\t' || cmd[4] == '\0')) {
        char *arg = &cmd[4];
        while (*arg == ' ' || *arg == '\t') {
            arg++;
        }
        float32 duty_val = (float32)strtod(arg, NULL);
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_TargetDuty_percentage(duty_val);
        Rte_Set_MotorMode((duty_val > -0.5f && duty_val < 0.5f) ? MOTOR_MODE_STOPPED : MOTOR_MODE_OPEN_LOOP);
        printk("[CDD_IPC] CMD DUTY: %d%% (Open-loop)\n", (int)duty_val);
    } else if (strncmp(cmd, "MODE", 4) == 0 && (cmd[4] == ' ' || cmd[4] == '\t')) {
        char *arg = &cmd[4];
        while (*arg == ' ' || *arg == '\t') {
            arg++;
        }
        if (strcmp(arg, "STOP") == 0) {
            Rte_Set_EmergencyStop(FALSE);
            Rte_Set_MotorMode(MOTOR_MODE_STOPPED);
            printk("[CDD_IPC] CMD MODE: STOPPED\n");
        } else if (strcmp(arg, "OPEN") == 0) {
            Rte_Set_EmergencyStop(FALSE);
            Rte_Set_MotorMode(MOTOR_MODE_OPEN_LOOP);
            printk("[CDD_IPC] CMD MODE: OPEN_LOOP\n");
        } else if (strcmp(arg, "PID") == 0) {
            Rte_Set_EmergencyStop(FALSE);
            Rte_Set_MotorMode(MOTOR_MODE_CLOSED_LOOP);
            printk("[CDD_IPC] CMD MODE: CLOSED_LOOP (PID)\n");
        } else if (strcmp(arg, "STEP") == 0) {
            Rte_Set_EmergencyStop(FALSE);
            Rte_Set_MotorMode(MOTOR_MODE_STEP_TEST);
            printk("[CDD_IPC] CMD MODE: STEP_TEST\n");
        } else if (strcmp(arg, "FAULT") == 0) {
            Rte_Set_EmergencyStop(TRUE);
            Rte_Set_MotorMode(MOTOR_MODE_FAULT);
            printk("[CDD_IPC] CMD MODE: FAULT (Emergency Stop)\n");
        } else {
            printk("[CDD_IPC] Warning: Unrecognized mode '%s'\n", arg);
        }
    } else if (strncmp(cmd, "STEP", 4) == 0 && (cmd[4] == ' ' || cmd[4] == '\t' || cmd[4] == '\0')) {
        char *arg = &cmd[4];
        while (*arg == ' ' || *arg == '\t') {
            arg++;
        }
        float32 base_duty = 0.0f;
        float32 step_duty = 60.0f;
        uint32 dur_ms = 3000u;

        if (*arg != '\0') {
            char *next_ptr = NULL;
            base_duty = (float32)strtod(arg, &next_ptr);
            if (next_ptr != NULL && next_ptr != arg) {
                arg = next_ptr;
                step_duty = (float32)strtod(arg, &next_ptr);
                if (next_ptr != NULL && next_ptr != arg) {
                    arg = next_ptr;
                    unsigned long d = strtoul(arg, NULL, 10);
                    if (d > 0u) {
                        dur_ms = (uint32)d;
                    }
                }
            }
        }

        MotorControl_StepConfigType cfg;
        cfg.base_duty = base_duty;
        cfg.step_duty = step_duty;
        cfg.pre_step_ms = 500u;
        cfg.step_dur_ms = dur_ms;
        Rte_Set_StepConfig(&cfg);
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_MotorMode(MOTOR_MODE_STEP_TEST);
        printk("[CDD_IPC] CMD STEP: Base=%.1f%%, Step=%.1f%%, Pre=500ms, Dur=%u ms\n",
               (double)base_duty, (double)step_duty, (unsigned int)dur_ms);
    } else if (strcmp(cmd, "STATUS") == 0) {
        Cdd_Ipc_SendStatus();
        printk("[CDD_IPC] CMD STATUS: Status frame sent\n");
    } else {
        printk("[CDD_IPC] Warning: Unrecognized command '%s'\n", cmd);
    }
}

/* RPMsg endpoint receive callback */
static int Cdd_Ipc_RxCallback(struct rpmsg_endpoint *ept, void *data,
                             size_t len, uint32_t src, void *priv)
{
    ARG_UNUSED(ept);
    ARG_UNUSED(priv);

    if (data == NULL || len == 0) {
        return RPMSG_SUCCESS;
    }

    /* Learn destination address on first received packet from Linux /dev/ttyRPMSG0 */
    if (s_tty_ept.dest_addr == RPMSG_ADDR_ANY) {
        s_tty_ept.dest_addr = src;
        printk("[CDD_IPC] Learned remote endpoint dest_addr: 0x%08X\n", (unsigned int)src);
    }

    char rx_buf[128];
    size_t copy_len = (len < (sizeof(rx_buf) - 1u)) ? len : (sizeof(rx_buf) - 1u);
    memcpy(rx_buf, data, copy_len);
    rx_buf[copy_len] = '\0';

    char *line = rx_buf;
    while (*line != '\0') {
        char *newline = strpbrk(line, "\r\n");
        if (newline != NULL) {
            *newline = '\0';
            Cdd_Ipc_ProcessCommand(line);
            line = newline + 1;
        } else {
            Cdd_Ipc_ProcessCommand(line);
            break;
        }
    }

    return RPMSG_SUCCESS;
}

/* Telemetry frame formatting and transmission */
static void Cdd_Ipc_SendTelemetry(void)
{
    const char *mode_str = Rte_Get_MotorModeString(Rte_Get_MotorMode());
    float32 tgt_speed = Rte_Get_ppTargetSpeed_rpm();
    float32 cur_speed = Icu_GetSpeedRpm();
    float32 cur_duty  = Rte_Get_ppDuty_percentage();
    sint32  pulses    = Icu_GetTotalPulses();
    Sensor_DataType sens;
    Rte_Get_SensorData(&sens);

    /* Integer-only formatting (no float printf -> small, deterministic stack) */
    int vib_mg = (int)(sens.accel_mag_g * 1000.0f);
    int tmp_x10 = (int)(sens.temperature_c * 10.0f);
    int flt = (int)Rte_Get_SafetyFault();
    int hum_x10 = (int)(sens.humidity_pct * 10.0f);
    uint32 dok = 0u, der = 0u;
    Rte_Get_Dht11Stats(&dok, &der);

    char payload[160];
    char frame[176];
    int len = snprintf(payload, sizeof(payload),
                       "$TELEM,MODE=%s,TGT=%d,RPM=%d,DUTY=%d,CNT=%ld,PIR=%d,VIB=%d,TMP=%d,HUM=%d,FLT=%d,DHT=%lu/%lu",
                       mode_str, (int)tgt_speed, (int)cur_speed, (int)cur_duty, (long)pulses,
                       (sens.pir_detected != FALSE) ? 1 : 0, vib_mg, tmp_x10, hum_x10, flt, (unsigned long)dok, (unsigned long)der);
    if (len > 0) {
        uint16 crc = Cdd_Ipc_CalcCrc16((const uint8 *)payload, (uint16)len);
        int frame_len = snprintf(frame, sizeof(frame), "%s*%04X\r\n", payload, crc);
        if (frame_len > 0 && s_tty_ept.dest_addr != RPMSG_ADDR_ANY) {
            (void)rpmsg_send(&s_tty_ept, frame, frame_len);
        }
    }
}

/* OpenAMP RPMsg Worker Thread Entry Point */
void Cdd_Ipc_ThreadEntry(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);

    printk("[CDD_IPC] Thread started. Initializing OpenAMP RPMsg...\n");

    s_rpdev = Platform_Create_Rpmsg_Vdev();
    if (s_rpdev == NULL) {
        printk("[CDD_IPC] Fatal: Platform_Create_Rpmsg_Vdev failed!\n");
        return;
    }

    int ret = rpmsg_create_ept(&s_tty_ept, s_rpdev, "rpmsg-tty",
                               RPMSG_ADDR_ANY, RPMSG_ADDR_ANY,
                               Cdd_Ipc_RxCallback, NULL);
    if (ret != 0) {
        printk("[CDD_IPC] Fatal: rpmsg_create_ept 'rpmsg-tty' failed: %d\n", ret);
        return;
    }

    printk("[CDD_IPC] OpenAMP RPMsg 'rpmsg-tty' endpoint created successfully.\n");

    while (1) {
        (void)k_sem_take(&s_ipc_sem, K_FOREVER);

        /* Process inbound virtqueue messages */
        if (s_rvdev.vdev != NULL) {
            rproc_virtio_notified(s_rvdev.vdev, RSC_NOTIFY_ID_ANY);
        }

        /* Transmit outbound telemetry frame */
        if (s_send_telem_requested && (s_tty_ept.dest_addr != RPMSG_ADDR_ANY)) {
            s_send_telem_requested = FALSE;
            Cdd_Ipc_SendTelemetry();
        }

        /* Transmit pending safety fault frame */
        Cdd_Ipc_FlushFault();
    }
}

/* CDD IPC Initialization */
Std_ReturnType Cdd_Ipc_Init(void)
{
    s_send_telem_requested = FALSE;
    s_watchdog_enabled = FALSE;
    s_hb_timeout_10ms = 0u;
    s_telem_tick_count = 0u;
    s_tty_ept.dest_addr = RPMSG_ADDR_ANY;

    return E_OK;
}

/* CDD IPC 10ms Periodic Execution */
void Cdd_Ipc_MainFunction_10ms(void)
{
    /* 1. Track Heartbeat Watchdog (100 ticks = 1.0s timeout) */
    if (s_watchdog_enabled) {
        if (s_hb_timeout_10ms < 1000u) {
            s_hb_timeout_10ms++;
        }
        if (s_hb_timeout_10ms >= WDG_TIMEOUT_TICKS) {
            /* Heartbeat lost -> trigger immediate safe stop / fault mode */
            Rte_Set_EmergencyStop(TRUE);
            Rte_Set_MotorMode(MOTOR_MODE_FAULT);
            Rte_Set_TargetDuty_percentage(0.0f);
            Rte_Set_rpTargetSpeed_rpm(0.0f);
        }
    }

    /* 2. Schedule Telemetry Frame:
     * - In MOTOR_MODE_STEP_TEST: 100 Hz (every 10ms tick) for high-fidelity MATLAB SysID data
     * - In other modes: 5 Hz (every 200ms / 20 ticks) for standard monitoring
     */
    if (Rte_Get_MotorMode() == MOTOR_MODE_STEP_TEST) {
        s_telem_tick_count = 0u;
        if (s_tty_ept.dest_addr != RPMSG_ADDR_ANY) {
            s_send_telem_requested = TRUE;
            k_sem_give(&s_ipc_sem);
        }
    } else {
        s_telem_tick_count++;
        if (s_telem_tick_count >= 20u) {
            s_telem_tick_count = 0u;
            if (s_tty_ept.dest_addr != RPMSG_ADDR_ANY) {
                s_send_telem_requested = TRUE;
                k_sem_give(&s_ipc_sem);
            }
        }
    }
}

/* Status queries */
boolean Cdd_Ipc_IsConnected(void)
{
    return (s_tty_ept.dest_addr != RPMSG_ADDR_ANY) ? TRUE : FALSE;
}

boolean Cdd_Ipc_IsWatchdogEnabled(void)
{
    return s_watchdog_enabled;
}
