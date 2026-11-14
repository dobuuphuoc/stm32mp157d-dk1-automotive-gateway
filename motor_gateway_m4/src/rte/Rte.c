#include <zephyr/kernel.h>
#include <zephyr/spinlock.h>
#include "Rte.h"
#include "Mcal_Dio.h"
#include "Mcal_Icu.h"
#include "Mcal_Adc.h"
#include "Cdd_L298n.h"
#include "Cdd_Ipc.h"
#include "Cdd_Dht11.h"
#include "Swc_MotorControl.h"
#include "Swc_SensorManager.h"
#include "Swc_SafetyManager.h"

/* RTE Spinlock for multi-threaded state protection */
static struct k_spinlock s_rte_lock;

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
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
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
    k_spin_unlock(&s_rte_lock, key);

    (void)Mcal_Adc_Init();
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
    float32 measured_speed = Icu_GetSpeedRpm();
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_speed_rpm = measured_speed;
    k_spin_unlock(&s_rte_lock, key);

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
    key = k_spin_lock(&s_rte_lock);
    boolean estop_active = s_rte_emergency_stop;
    MotorControl_ModeType cur_mode = s_rte_motor_mode;
    float32 cur_duty = s_rte_duty_percentage;
    k_spin_unlock(&s_rte_lock, key);

    if ((estop_active != FALSE) || (cur_mode == MOTOR_MODE_FAULT)) {
        Cdd_L298n_EmergencyStop();
    } else if (cur_mode == MOTOR_MODE_STOPPED) {
        (void)Cdd_L298n_SetCommand(L298N_DIR_COAST, 0.0f);
    } else {
        if (cur_duty > 0.5f) {
            (void)Cdd_L298n_SetCommand(L298N_DIR_FORWARD, cur_duty);
        } else if (cur_duty < -0.5f) {
            (void)Cdd_L298n_SetCommand(L298N_DIR_REVERSE, -cur_duty);
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
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *mode = s_rte_motor_mode;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppMotorMode(MotorControl_ModeType mode)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_motor_mode = mode;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpSpeed_rpm(float32 *speed)
{
    if (speed == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *speed = s_rte_speed_rpm;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppDuty_percentage(float32 duty)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_duty_percentage = duty;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetSpeed_rpm(float32 *target_rpm)
{
    if (target_rpm == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *target_rpm = s_rte_target_speed_rpm;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetSpeed_rpm(float32 target_rpm)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_target_speed_rpm = target_rpm;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetDuty_percentage(float32 *target_duty)
{
    if (target_duty == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *target_duty = s_rte_target_duty_percentage;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetDuty_percentage(float32 target_duty)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_target_duty_percentage = target_duty;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpStepConfig(MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *config = s_rte_step_config;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppStepConfig(const MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_step_config = *config;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpEmergencyStop(boolean *estop)
{
    if (estop == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *estop = s_rte_emergency_stop;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppEmergencyStop(boolean estop)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_emergency_stop = estop;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpSensorData(Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *data = s_rte_sensor_data;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppSensorData(const Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_sensor_data = *data;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Read_rpSafetyFault(Safety_FaultReasonType *fault)
{
    if (fault == NULL) {
        return E_NOT_OK;
    }
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    *fault = s_rte_safety_fault;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

Std_ReturnType Rte_Write_ppSafetyFault(Safety_FaultReasonType fault)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_safety_fault = fault;
    k_spin_unlock(&s_rte_lock, key);
    return E_OK;
}

/* ========================================================================= */
/* RTE BSW-side Accessor APIs                                                */
/* ========================================================================= */

MotorControl_ModeType Rte_Get_MotorMode(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    MotorControl_ModeType mode = s_rte_motor_mode;
    k_spin_unlock(&s_rte_lock, key);
    return mode;
}

void Rte_Set_MotorMode(MotorControl_ModeType mode)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_motor_mode = mode;
    k_spin_unlock(&s_rte_lock, key);
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
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    float32 duty = s_rte_duty_percentage;
    k_spin_unlock(&s_rte_lock, key);
    return duty;
}

void Rte_Set_rpSpeed_rpm(float32 speed)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_speed_rpm = speed;
    k_spin_unlock(&s_rte_lock, key);
}

float32 Rte_Get_rpSpeed_rpm(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    float32 speed = s_rte_speed_rpm;
    k_spin_unlock(&s_rte_lock, key);
    return speed;
}

float32 Rte_Get_ppTargetSpeed_rpm(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    float32 tgt = s_rte_target_speed_rpm;
    k_spin_unlock(&s_rte_lock, key);
    return tgt;
}

void Rte_Set_rpTargetSpeed_rpm(float32 target_rpm)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_target_speed_rpm = target_rpm;
    k_spin_unlock(&s_rte_lock, key);
}

float32 Rte_Get_TargetDuty_percentage(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    float32 duty = s_rte_target_duty_percentage;
    k_spin_unlock(&s_rte_lock, key);
    return duty;
}

void Rte_Set_TargetDuty_percentage(float32 target_duty)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_target_duty_percentage = target_duty;
    k_spin_unlock(&s_rte_lock, key);
}

void Rte_Get_StepConfig(MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
        *config = s_rte_step_config;
        k_spin_unlock(&s_rte_lock, key);
    }
}

void Rte_Set_StepConfig(const MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
        s_rte_step_config = *config;
        k_spin_unlock(&s_rte_lock, key);
    }
}

boolean Rte_Get_EmergencyStop(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    boolean estop = s_rte_emergency_stop;
    k_spin_unlock(&s_rte_lock, key);
    return estop;
}

void Rte_Set_EmergencyStop(boolean estop)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_emergency_stop = estop;
    k_spin_unlock(&s_rte_lock, key);
}

void Rte_Get_SensorData(Sensor_DataType *data)
{
    if (data != NULL) {
        k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
        *data = s_rte_sensor_data;
        k_spin_unlock(&s_rte_lock, key);
    }
}

Safety_FaultReasonType Rte_Get_SafetyFault(void)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    Safety_FaultReasonType fault = s_rte_safety_fault;
    k_spin_unlock(&s_rte_lock, key);
    return fault;
}

void Rte_Set_SafetyFault(Safety_FaultReasonType fault)
{
    k_spinlock_key_t key = k_spin_lock(&s_rte_lock);
    s_rte_safety_fault = fault;
    k_spin_unlock(&s_rte_lock, key);
}

/* ========================================================================= */
/* RTE Client-Server ports to IoHwAb / CDD / MCAL drivers                    */
/* ========================================================================= */

Std_ReturnType Rte_Call_rpPirSensor_Read(boolean *pir_detected)
{
    if (pir_detected == NULL) {
        return E_NOT_OK;
    }
    *pir_detected = (Dio_ReadChannel(DIO_CH_PIR_PE13) == STD_HIGH) ? TRUE : FALSE;
    return E_OK;
}

Std_ReturnType Rte_Call_rpActuator_EmergencyStop(void)
{
    Cdd_L298n_EmergencyStop();
    return E_OK;
}

Std_ReturnType Rte_Call_rpIpc_SendFaultNotice(const char *reason)
{
    Cdd_Ipc_SendFaultNotice(reason);
    return E_OK;
}

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

/* GY-61 ADC path: reads 3-axis accelerometer via MCAL ADC driver */
Std_ReturnType Rte_Call_rpAccel_Read(float32 *ax_g, float32 *ay_g, float32 *az_g)
{
    return Mcal_Adc_ReadGy61(ax_g, ay_g, az_g);
}
