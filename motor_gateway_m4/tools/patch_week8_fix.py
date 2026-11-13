import os, re, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/zephyrproject/motor_gateway_m4")

def rd(p):
    with open(os.path.join(BASE, p), "r", newline="") as f:
        return f.read().replace("\r\n", "\n")

def wr(p, s):
    with open(os.path.join(BASE, p), "w", newline="\n") as f:
        f.write(s)

def ok(name, cond):
    print(("  [OK]   " if cond else "  [FAIL] ") + name)

# ---------------- Cdd_Ipc.c ----------------
P = "src/bsw/cdd/Cdd_Ipc.c"
c = rd(P)
if '#include "Swc_SafetyManager.h"' not in c:
    c = c.replace('#include "Rte.h"', '#include "Rte.h"\n#include "Swc_SafetyManager.h"', 1)
c = c.replace("K_THREAD_DEFINE(cdd_ipc_thread, 2048,", "K_THREAD_DEFINE(cdd_ipc_thread, 4096,")

FAULT_FN = r'''static volatile boolean s_fault_pending = FALSE;
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
'''
if "Cdd_Ipc_FlushFault" not in c:
    c, n = re.subn(r"void Cdd_Ipc_SendFaultNotice\(const char \*reason\)\n\{.*?\n\}\n",
                   lambda m: FAULT_FN, c, count=1, flags=re.S)
ok("Fault notice -> deferred (non-blocking)", "Cdd_Ipc_FlushFault(void)" in c)

TELEM_FN = r'''static void Cdd_Ipc_SendTelemetry(void)
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

    char payload[128];
    char frame[144];
    int len = snprintf(payload, sizeof(payload),
                       "$TELEM,MODE=%s,TGT=%d,RPM=%d,DUTY=%d,CNT=%ld,PIR=%d,VIB=%d,TMP=%d,FLT=%d",
                       mode_str, (int)tgt_speed, (int)cur_speed, (int)cur_duty, (long)pulses,
                       (sens.pir_detected != FALSE) ? 1 : 0, vib_mg, tmp_x10, flt);
    if (len > 0) {
        uint16 crc = Cdd_Ipc_CalcCrc16((const uint8 *)payload, (uint16)len);
        int frame_len = snprintf(frame, sizeof(frame), "%s*%04X\r\n", payload, crc);
        if (frame_len > 0 && s_tty_ept.dest_addr != RPMSG_ADDR_ANY) {
            (void)rpmsg_send(&s_tty_ept, frame, frame_len);
        }
    }
}
'''
c, n = re.subn(r"static void Cdd_Ipc_SendTelemetry\(void\)\n\{.*?\n\}\n", lambda m: TELEM_FN, c, count=1, flags=re.S)
ok("Telemetry integer format (PIR/VIB/TMP/FLT)", n == 1)

if "        Cdd_Ipc_FlushFault();" not in c:
    c = c.replace("            Cdd_Ipc_SendTelemetry();\n        }\n",
                  "            Cdd_Ipc_SendTelemetry();\n        }\n\n        /* Transmit pending safety fault frame */\n        Cdd_Ipc_FlushFault();\n", 1)
ok("IPC thread flushes fault frames", "        Cdd_Ipc_FlushFault();" in c)

HB = '    if (strcmp(cmd, "HB") == 0) {\n        s_hb_timeout_10ms = 0u;\n'
if "CMD CLEAR" not in c:
    c = c.replace(HB, HB + r'''    } else if (strcmp(cmd, "CLEAR") == 0 || strcmp(cmd, "RESET") == 0) {
        Swc_SafetyManager_ClearFault();
        Rte_Set_EmergencyStop(FALSE);
        Rte_Set_MotorMode(MOTOR_MODE_STOPPED);
        Rte_Set_TargetDuty_percentage(0.0f);
        Rte_Set_rpTargetSpeed_rpm(0.0f);
        printk("[CDD_IPC] CMD CLEAR: Safety faults reset\n");
    } else if (strcmp(cmd, "ESTOP") == 0) {
        Rte_Set_EmergencyStop(TRUE);
        Rte_Set_MotorMode(MOTOR_MODE_FAULT);
        Rte_Set_TargetDuty_percentage(0.0f);
        Rte_Set_rpTargetSpeed_rpm(0.0f);
        Cdd_Ipc_SendFaultNotice("MANUAL_ESTOP");
        printk("[CDD_IPC] CMD ESTOP: Manual emergency stop\n");
''', 1)
if '"PIR ON"' not in c:
    c = c.replace(HB, HB + r'''    } else if (strcmp(cmd, "PIR ON") == 0) {
        Swc_SafetyManager_SetPirEnable(TRUE);
        printk("[CDD_IPC] CMD PIR ON: PIR safety supervision enabled\n");
    } else if (strcmp(cmd, "PIR OFF") == 0) {
        Swc_SafetyManager_SetPirEnable(FALSE);
        printk("[CDD_IPC] CMD PIR OFF: PIR safety supervision disabled\n");
''', 1)
ok("Commands CLEAR/ESTOP/PIR ON/PIR OFF", ("CMD CLEAR" in c) and ('"PIR ON"' in c))
wr(P, c)

# ---------------- Rte.c ----------------
P = "src/rte/Rte.c"
r = rd(P)
r = r.replace("s_rte_motor_mode = MOTOR_MODE_CLOSED_LOOP;", "s_rte_motor_mode = MOTOR_MODE_STOPPED;")
r = r.replace("s_rte_target_speed_rpm = 60.0f;", "s_rte_target_speed_rpm = 0.0f;")
for a, b in (('"STOPPED"', '"STOP"'), ('"OPEN_LOOP"', '"OPEN"'), ('"CLOSED_LOOP"', '"PID"'), ('"STEP_TEST"', '"STEP"')):
    r = r.replace("return " + a + ";", "return " + b + ";")
ok("Rte boot mode = STOPPED, mode strings STOP/OPEN/PID/STEP", "MOTOR_MODE_CLOSED_LOOP;" not in r.split("void Rte_TimerEvent_10ms")[0])
wr(P, r)

# ---------------- Swc_SafetyManager ----------------
wr("src/asw/Swc_SafetyManager.h", r'''#ifndef SWC_SAFETY_MANAGER_H
#define SWC_SAFETY_MANAGER_H

#include "std_types.h"

void Swc_SafetyManager_Init(void);
void Runnable_SafetyCheck_10ms(void);
void Swc_SafetyManager_ClearFault(void);
void Swc_SafetyManager_SetPirEnable(boolean enable);
Safety_FaultReasonType Swc_SafetyManager_GetFault(void);
const char *Swc_SafetyManager_GetFaultString(Safety_FaultReasonType reason);

#endif /* SWC_SAFETY_MANAGER_H */
''')

wr("src/asw/Swc_SafetyManager.c", r'''#include "Swc_SafetyManager.h"
#include "Rte.h"
#include "Cdd_Ipc.h"
#include "Cdd_L298n.h"

#define SAFETY_CRASH_THRESHOLD_G   2.5f

static Safety_FaultReasonType s_current_fault = SAFETY_OK;
static boolean s_estop_active = FALSE;
static volatile boolean s_pir_enabled = TRUE;

static void Safety_TriggerEStop(Safety_FaultReasonType reason)
{
    s_current_fault = reason;
    s_estop_active = TRUE;
    (void)Rte_Write_ppEmergencyStop(TRUE);
    (void)Rte_Write_ppSafetyFault(reason);
    (void)Rte_Write_ppMotorMode(MOTOR_MODE_FAULT);
    (void)Rte_Write_ppDuty_percentage(0.0f);
    Cdd_L298n_EmergencyStop();                                   /* < 5 ms (NFR-2) */
    Cdd_Ipc_SendFaultNotice(Swc_SafetyManager_GetFaultString(reason)); /* non-blocking */
}

void Swc_SafetyManager_Init(void)
{
    s_current_fault = SAFETY_OK;
    s_estop_active = FALSE;
    (void)Rte_Write_ppEmergencyStop(FALSE);
    (void)Rte_Write_ppSafetyFault(SAFETY_OK);
}

void Runnable_SafetyCheck_10ms(void)
{
    Sensor_DataType sens;
    (void)Rte_Read_rpSensorData(&sens);

    /* Latched fault: keep actuator in safe state until explicit CLEAR */
    if (s_estop_active != FALSE) {
        (void)Rte_Write_ppEmergencyStop(TRUE);
        (void)Rte_Write_ppMotorMode(MOTOR_MODE_FAULT);
        Cdd_L298n_EmergencyStop();
        return;
    }

    MotorControl_ModeType mode = Rte_Get_MotorMode();
    boolean running = ((mode == MOTOR_MODE_OPEN_LOOP) || (mode == MOTOR_MODE_CLOSED_LOOP) ||
                       (mode == MOTOR_MODE_STEP_TEST)) ? TRUE : FALSE;

    /* 1. FR-M6: PIR presence while motor is running */
    if ((s_pir_enabled != FALSE) && (running != FALSE) && (sens.pir_detected != FALSE)) {
        Safety_TriggerEStop(SAFETY_FAULT_PIR);
        return;
    }

    /* 2. Crash / abnormal vibration */
    if (sens.accel_mag_g > SAFETY_CRASH_THRESHOLD_G) {
        Safety_TriggerEStop(SAFETY_FAULT_CRASH);
        return;
    }

    /* 3. E-Stop requested by BSW (Watchdog timeout or manual ESTOP command) */
    if (Rte_Get_EmergencyStop() != FALSE) {
        Safety_TriggerEStop((Rte_Get_MotorMode() == MOTOR_MODE_FAULT && Cdd_Ipc_IsWatchdogEnabled() != FALSE)
                            ? SAFETY_FAULT_WDG : SAFETY_FAULT_MANUAL);
        return;
    }
}

void Swc_SafetyManager_ClearFault(void)
{
    s_current_fault = SAFETY_OK;
    s_estop_active = FALSE;
    (void)Rte_Write_ppEmergencyStop(FALSE);
    (void)Rte_Write_ppSafetyFault(SAFETY_OK);
    (void)Rte_Write_ppMotorMode(MOTOR_MODE_STOPPED);
    (void)Rte_Write_ppDuty_percentage(0.0f);
}

void Swc_SafetyManager_SetPirEnable(boolean enable)
{
    s_pir_enabled = enable;
}

Safety_FaultReasonType Swc_SafetyManager_GetFault(void)
{
    return s_current_fault;
}

const char *Swc_SafetyManager_GetFaultString(Safety_FaultReasonType reason)
{
    switch (reason) {
    case SAFETY_OK:           return "OK";
    case SAFETY_FAULT_PIR:    return "PIR_OBSTACLE";
    case SAFETY_FAULT_CRASH:  return "CRASH_VIBRATION";
    case SAFETY_FAULT_WDG:    return "WATCHDOG_TIMEOUT";
    case SAFETY_FAULT_MANUAL: return "MANUAL_ESTOP";
    default:                  return "UNKNOWN_FAULT";
    }
}
''')
ok("Swc_SafetyManager rewritten (PIR enable, deferred fault)", True)
print(">>> PATCH DONE:", BASE)
