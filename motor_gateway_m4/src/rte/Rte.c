#include "Rte.h"
#include "Mcal_Dio.h"
#include "Mcal_Icu.h"
#include "Cdd_L298n.h"
#include "Cdd_Ipc.h"
#include "Cdd_Dht11.h"
#include "Swc_MotorControl.h"
#include "Swc_SensorManager.h"
#include "Swc_SafetyManager.h"

/* RTE Internal Signal & Mode Buffers */
static uint32 s_tick_count_10ms = 0u;
static uint32 s_sensor_tick_count = 0u;
static float32 s_rte_speed_rpm = 0.0f;
static float32 s_rte_duty_percentage = 0.0f;
static float32 s_rte_target_speed_rpm = 0.0f;
static MotorControl_ModeType s_rte_motor_mode = MOTOR_MODE_STOPPED;
static float32 s_rte_target_duty_percentage = 50.0f;
static MotorControl_StepConfigType s_rte_step_config = { 0.0f, 60.0f, 1000u, 3000u };
static boolean s_rte_emergency_stop = FALSE;
static Sensor_DataType s_rte_sensor_data;
static Safety_FaultReasonType s_rte_safety_fault = SAFETY_OK;

void Rte_Init(void)
{
    s_tick_count_10ms = 0u;
    s_sensor_tick_count = 0u;
    s_rte_speed_rpm = 0.0f;
    s_rte_duty_percentage = 0.0f;
    s_rte_target_speed_rpm = 0.0f;
    s_rte_motor_mode = MOTOR_MODE_STOPPED;
    s_rte_target_duty_percentage = 50.0f;
    s_rte_step_config.base_duty = 0.0f;
    s_rte_step_config.step_duty = 60.0f;
    s_rte_step_config.pre_step_ms = 1000u;
    s_rte_step_config.step_dur_ms = 3000u;
    s_rte_emergency_stop = FALSE;
    s_rte_safety_fault = SAFETY_OK;

    (void)Cdd_Dht11_Init();
    Swc_SensorManager_Init();
    Swc_SafetyManager_Init();
}

void Rte_TimerEvent_10ms(void)
{
    /* 1. FR-M10: Toggle Test Pin PE9 at cycle start for Logic Analyzer jitter measurement */
    (void)Dio_FlipChannel(DIO_CH_TEST_PE9);

    /* 2. Process quadrature encoder pulse accumulation into speed */
    Icu_Update10ms();

    /* 3. Latch measured filtered speed to RTE port */
    s_rte_speed_rpm = Icu_GetSpeedRpm();

    /* 4. Dispatch periodic 100ms Sensor Manager Runnable (every 10 ticks) */
    s_sensor_tick_count++;
    if (s_sensor_tick_count >= 10u) {
        s_sensor_tick_count = 0u;
        Runnable_SensorManager_100ms();
    }

    /* 5. Dispatch periodic 10ms Safety Check Runnable (High Priority Safety Decision) */
    Runnable_SafetyCheck_10ms();

    /* 6. Dispatch periodic 10ms Motor Control Runnable */
    Runnable_MotorControl_10ms();

    /* 7. Actuate Motor via CDD L298N driver based on mode, e-stop, and RTE Duty Cycle */
    if ((s_rte_emergency_stop != FALSE) || (s_rte_motor_mode == MOTOR_MODE_FAULT)) {
        Cdd_L298n_EmergencyStop();
    } else if (s_rte_motor_mode == MOTOR_MODE_STOPPED) {
        (void)Cdd_L298n_SetCommand(L298N_DIR_COAST, 0.0f);
    } else {
        if (s_rte_duty_percentage > 0.5f) {
            (void)Cdd_L298n_SetCommand(L298N_DIR_FORWARD, s_rte_duty_percentage);
        } else if (s_rte_duty_percentage < -0.5f) {
            (void)Cdd_L298n_SetCommand(L298N_DIR_REVERSE, -s_rte_duty_percentage);
        } else {
            (void)Cdd_L298n_SetCommand(L298N_DIR_COAST, 0.0f);
        }
    }

    /* 8. Execute periodic CDD IPC 10ms (Watchdog tracking & telemetry scheduling) */
    Cdd_Ipc_MainFunction_10ms();

    /* Open jitter-free window for DHT11 sampling thread */
    Cdd_Dht11_TickSync();

    /* 9. Status heartbeat LED: toggle every 25 ticks (250ms) */
    s_tick_count_10ms++;
    if (s_tick_count_10ms >= 25u) {
        s_tick_count_10ms = 0u;
        (void)Dio_FlipChannel(DIO_CH_STATUS_LED);
    }
}

/* ========================================================================= */
/* RTE ASW Sender-Receiver & Mode Port APIs                                  */
/* ========================================================================= */

Std_ReturnType Rte_Read_rpMotorMode(MotorControl_ModeType *mode)
{
    if (mode == NULL) {
        return E_NOT_OK;
    }
    *mode = s_rte_motor_mode;
    return E_OK;
}

Std_ReturnType Rte_Write_ppMotorMode(MotorControl_ModeType mode)
{
    s_rte_motor_mode = mode;
    return E_OK;
}

Std_ReturnType Rte_Read_rpSpeed_rpm(float32 *speed)
{
    if (speed == NULL) {
        return E_NOT_OK;
    }
    *speed = s_rte_speed_rpm;
    return E_OK;
}

Std_ReturnType Rte_Write_ppDuty_percentage(float32 duty)
{
    s_rte_duty_percentage = duty;
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetSpeed_rpm(float32 *target_rpm)
{
    if (target_rpm == NULL) {
        return E_NOT_OK;
    }
    *target_rpm = s_rte_target_speed_rpm;
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetSpeed_rpm(float32 target_rpm)
{
    s_rte_target_speed_rpm = target_rpm;
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetDuty_percentage(float32 *target_duty)
{
    if (target_duty == NULL) {
        return E_NOT_OK;
    }
    *target_duty = s_rte_target_duty_percentage;
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetDuty_percentage(float32 target_duty)
{
    s_rte_target_duty_percentage = target_duty;
    return E_OK;
}

Std_ReturnType Rte_Read_rpStepConfig(MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    *config = s_rte_step_config;
    return E_OK;
}

Std_ReturnType Rte_Write_ppStepConfig(const MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    s_rte_step_config = *config;
    return E_OK;
}

Std_ReturnType Rte_Read_rpEmergencyStop(boolean *estop)
{
    if (estop == NULL) {
        return E_NOT_OK;
    }
    *estop = s_rte_emergency_stop;
    return E_OK;
}

Std_ReturnType Rte_Write_ppEmergencyStop(boolean estop)
{
    s_rte_emergency_stop = estop;
    return E_OK;
}

/* ========================================================================= */
/* RTE BSW-side Accessor APIs                                                */
/* ========================================================================= */

MotorControl_ModeType Rte_Get_MotorMode(void)
{
    return s_rte_motor_mode;
}

void Rte_Set_MotorMode(MotorControl_ModeType mode)
{
    s_rte_motor_mode = mode;
}

const char *Rte_Get_MotorModeString(MotorControl_ModeType mode)
{
    switch (mode) {
    case MOTOR_MODE_STOPPED:
        return "STOP";
    case MOTOR_MODE_OPEN_LOOP:
        return "OPEN";
    case MOTOR_MODE_CLOSED_LOOP:
        return "PID";
    case MOTOR_MODE_STEP_TEST:
        return "STEP";
    case MOTOR_MODE_FAULT:
        return "FAULT";
    default:
        return "UNKNOWN";
    }
}

float32 Rte_Get_ppDuty_percentage(void)
{
    return s_rte_duty_percentage;
}

void Rte_Set_rpSpeed_rpm(float32 speed)
{
    s_rte_speed_rpm = speed;
}

float32 Rte_Get_rpSpeed_rpm(void)
{
    return s_rte_speed_rpm;
}

float32 Rte_Get_ppTargetSpeed_rpm(void)
{
    return s_rte_target_speed_rpm;
}

void Rte_Set_rpTargetSpeed_rpm(float32 target_rpm)
{
    s_rte_target_speed_rpm = target_rpm;
}

float32 Rte_Get_TargetDuty_percentage(void)
{
    return s_rte_target_duty_percentage;
}

void Rte_Set_TargetDuty_percentage(float32 target_duty)
{
    s_rte_target_duty_percentage = target_duty;
}

void Rte_Get_StepConfig(MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        *config = s_rte_step_config;
    }
}

void Rte_Set_StepConfig(const MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        s_rte_step_config = *config;
    }
}

boolean Rte_Get_EmergencyStop(void)
{
    return s_rte_emergency_stop;
}

void Rte_Set_EmergencyStop(boolean estop)
{
    s_rte_emergency_stop = estop;
}

Std_ReturnType Rte_Read_rpSensorData(Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    *data = s_rte_sensor_data;
    return E_OK;
}

Std_ReturnType Rte_Write_ppSensorData(const Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    s_rte_sensor_data = *data;
    return E_OK;
}

Std_ReturnType Rte_Read_rpSafetyFault(Safety_FaultReasonType *fault)
{
    if (fault == NULL) {
        return E_NOT_OK;
    }
    *fault = s_rte_safety_fault;
    return E_OK;
}

Std_ReturnType Rte_Write_ppSafetyFault(Safety_FaultReasonType fault)
{
    s_rte_safety_fault = fault;
    return E_OK;
}

void Rte_Get_SensorData(Sensor_DataType *data)
{
    if (data != NULL) {
        *data = s_rte_sensor_data;
    }
}

Safety_FaultReasonType Rte_Get_SafetyFault(void)
{
    return s_rte_safety_fault;
}

/* ========================================================================= */
/* RTE Client-Server ports to IoHwAb / CDD sensor drivers                    */
/* ========================================================================= */
Std_ReturnType Rte_Call_rpEnvSensor_Read(float32 *temp_c, float32 *hum_pct)
{
    Cdd_Dht11_DataType d;
    Cdd_Dht11_GetLatest(&d);
    if ((temp_c == NULL) || (hum_pct == NULL) || (d.valid == FALSE)) {
        return E_NOT_OK;
    }
    *temp_c = d.temperature_c;
    *hum_pct = d.humidity_pct;
    return E_OK;
}

void Rte_Get_Dht11Stats(uint32 *ok_cnt, uint32 *err_cnt)
{
    Cdd_Dht11_DataType d;
    Cdd_Dht11_GetLatest(&d);
    if (ok_cnt != NULL) { *ok_cnt = d.ok_count; }
    if (err_cnt != NULL) { *err_cnt = d.err_count; }
}

/* GY-61 ADC path: implemented in Mcal_Adc step (returns E_NOT_OK until then) */
Std_ReturnType Rte_Call_rpAccel_Read(float32 *ax_g, float32 *ay_g, float32 *az_g)
{
    (void)ax_g; (void)ay_g; (void)az_g;
    return E_NOT_OK;
}
