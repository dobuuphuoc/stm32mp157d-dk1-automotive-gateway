#include "Swc_SafetyManager.h"
#include "Rte.h"

#define SAFETY_CRASH_THRESHOLD_G   3.5f

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
    (void)Rte_Call_rpActuator_EmergencyStop();                                   /* < 5 ms (NFR-2) */
    (void)Rte_Call_rpIpc_SendFaultNotice(Swc_SafetyManager_GetFaultString(reason)); /* non-blocking */
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
        (void)Rte_Call_rpActuator_EmergencyStop();
        return;
    }

    MotorControl_ModeType mode = MOTOR_MODE_STOPPED;
    (void)Rte_Read_rpMotorMode(&mode);
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
    boolean estop = FALSE;
    (void)Rte_Read_rpEmergencyStop(&estop);
    if (estop != FALSE) {
        Safety_FaultReasonType rte_fault = SAFETY_OK;
        (void)Rte_Read_rpSafetyFault(&rte_fault);
        if (rte_fault != SAFETY_OK) {
            Safety_TriggerEStop(rte_fault);
        } else {
            Safety_TriggerEStop(SAFETY_FAULT_MANUAL);
        }
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
