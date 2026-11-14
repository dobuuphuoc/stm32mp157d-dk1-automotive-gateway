/**
 * @file test_m4_asw.c
 * @brief Host Unit Test Suite for Cortex-M4 AUTOSAR ASW Software Components:
 *        - Swc_SensorManager (Sensor acquisition & vibration vector magnitude)
 *        - Swc_SafetyManager (Crash detection, PIR intrusion, and fault classification)
 *        - Swc_MotorControl  (Closed-loop PI speed control, overshoot reduction, reverse)
 *
 * Demonstrates 100% hardware/BSW independence of the ASW layer via clean
 * in-memory mock RTE functions (Rte_Read_*, Rte_Write_*, Rte_Call_*).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <math.h>

#include "std_types.h"
#include "Rte.h"
#include "Swc_SensorManager.h"
#include "Swc_SafetyManager.h"
#include "Swc_MotorControl.h"

/* ==========================================================================
 * In-Memory RTE Mock State & Data Structures
 * ========================================================================== */

static MotorControl_ModeType       s_mock_motor_mode               = MOTOR_MODE_STOPPED;
static float32                     s_mock_speed_rpm                = 0.0f;
static float32                     s_mock_duty_percentage          = 0.0f;
static float32                     s_mock_target_speed_rpm         = 0.0f;
static float32                     s_mock_target_duty_percentage   = 0.0f;
static MotorControl_StepConfigType s_mock_step_config              = {0.0f, 0.0f, 0u, 0u};
static boolean                     s_mock_emergency_stop           = FALSE;
static Sensor_DataType             s_mock_sensor_data              = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, FALSE};
static Safety_FaultReasonType      s_mock_safety_fault             = SAFETY_OK;

/* Mock Return Values for Hardware/Driver Callbacks */
static float32                     s_mock_env_temp                 = 25.0f;
static float32                     s_mock_env_hum                  = 50.0f;
static Std_ReturnType              s_mock_env_ret                  = E_OK;

static float32                     s_mock_accel_x                  = 0.0f;
static float32                     s_mock_accel_y                  = 0.0f;
static float32                     s_mock_accel_z                  = 1.0f;
static Std_ReturnType              s_mock_accel_ret                = E_OK;

static boolean                     s_mock_pir_detected             = FALSE;
static Std_ReturnType              s_mock_pir_ret                  = E_OK;

/* Mock Call Tracking Counters & Arguments */
static uint32                      s_mock_estop_call_count         = 0u;
static uint32                      s_mock_ipc_fault_notice_count   = 0u;
static char                        s_mock_last_fault_notice[64]    = {0};

/* Helper function to reset all mock state between tests */
static void Mock_ResetAll(void)
{
    s_mock_motor_mode             = MOTOR_MODE_STOPPED;
    s_mock_speed_rpm              = 0.0f;
    s_mock_duty_percentage        = 0.0f;
    s_mock_target_speed_rpm       = 0.0f;
    s_mock_target_duty_percentage = 0.0f;
    memset(&s_mock_step_config, 0, sizeof(s_mock_step_config));
    s_mock_emergency_stop         = FALSE;
    memset(&s_mock_sensor_data, 0, sizeof(s_mock_sensor_data));
    s_mock_safety_fault           = SAFETY_OK;

    s_mock_env_temp               = 25.0f;
    s_mock_env_hum                = 50.0f;
    s_mock_env_ret                = E_OK;

    s_mock_accel_x                = 0.0f;
    s_mock_accel_y                = 0.0f;
    s_mock_accel_z                = 1.0f;
    s_mock_accel_ret              = E_OK;

    s_mock_pir_detected           = FALSE;
    s_mock_pir_ret                = E_OK;

    s_mock_estop_call_count       = 0u;
    s_mock_ipc_fault_notice_count = 0u;
    memset(s_mock_last_fault_notice, 0, sizeof(s_mock_last_fault_notice));
}

/* ==========================================================================
 * Mock RTE Port Implementation (Satisfies Rte.h)
 * ========================================================================== */

void Rte_Init(void)
{
}

void Rte_TimerEvent_10ms(void)
{
}

Std_ReturnType Rte_Read_rpMotorMode(MotorControl_ModeType *mode)
{
    if (mode == NULL) {
        return E_NOT_OK;
    }
    *mode = s_mock_motor_mode;
    return E_OK;
}

Std_ReturnType Rte_Write_ppMotorMode(MotorControl_ModeType mode)
{
    s_mock_motor_mode = mode;
    return E_OK;
}

Std_ReturnType Rte_Read_rpSpeed_rpm(float32 *speed)
{
    if (speed == NULL) {
        return E_NOT_OK;
    }
    *speed = s_mock_speed_rpm;
    return E_OK;
}

Std_ReturnType Rte_Write_ppDuty_percentage(float32 duty)
{
    s_mock_duty_percentage = duty;
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetSpeed_rpm(float32 *target_rpm)
{
    if (target_rpm == NULL) {
        return E_NOT_OK;
    }
    *target_rpm = s_mock_target_speed_rpm;
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetSpeed_rpm(float32 target_rpm)
{
    s_mock_target_speed_rpm = target_rpm;
    return E_OK;
}

Std_ReturnType Rte_Read_rpTargetDuty_percentage(float32 *target_duty)
{
    if (target_duty == NULL) {
        return E_NOT_OK;
    }
    *target_duty = s_mock_target_duty_percentage;
    return E_OK;
}

Std_ReturnType Rte_Write_ppTargetDuty_percentage(float32 target_duty)
{
    s_mock_target_duty_percentage = target_duty;
    return E_OK;
}

Std_ReturnType Rte_Read_rpStepConfig(MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    *config = s_mock_step_config;
    return E_OK;
}

Std_ReturnType Rte_Write_ppStepConfig(const MotorControl_StepConfigType *config)
{
    if (config == NULL) {
        return E_NOT_OK;
    }
    s_mock_step_config = *config;
    return E_OK;
}

Std_ReturnType Rte_Read_rpEmergencyStop(boolean *estop)
{
    if (estop == NULL) {
        return E_NOT_OK;
    }
    *estop = s_mock_emergency_stop;
    return E_OK;
}

Std_ReturnType Rte_Write_ppEmergencyStop(boolean estop)
{
    s_mock_emergency_stop = estop;
    return E_OK;
}

Std_ReturnType Rte_Read_rpSensorData(Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    *data = s_mock_sensor_data;
    return E_OK;
}

Std_ReturnType Rte_Write_ppSensorData(const Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    s_mock_sensor_data = *data;
    return E_OK;
}

Std_ReturnType Rte_Read_rpSafetyFault(Safety_FaultReasonType *fault)
{
    if (fault == NULL) {
        return E_NOT_OK;
    }
    *fault = s_mock_safety_fault;
    return E_OK;
}

Std_ReturnType Rte_Write_ppSafetyFault(Safety_FaultReasonType fault)
{
    s_mock_safety_fault = fault;
    return E_OK;
}

Std_ReturnType Rte_Call_rpEnvSensor_Read(float32 *temp_c, float32 *hum_pct)
{
    if ((temp_c == NULL) || (hum_pct == NULL)) {
        return E_NOT_OK;
    }
    *temp_c = s_mock_env_temp;
    *hum_pct = s_mock_env_hum;
    return s_mock_env_ret;
}

Std_ReturnType Rte_Call_rpAccel_Read(float32 *ax_g, float32 *ay_g, float32 *az_g)
{
    if ((ax_g == NULL) || (ay_g == NULL) || (az_g == NULL)) {
        return E_NOT_OK;
    }
    *ax_g = s_mock_accel_x;
    *ay_g = s_mock_accel_y;
    *az_g = s_mock_accel_z;
    return s_mock_accel_ret;
}

Std_ReturnType Rte_Call_rpPirSensor_Read(boolean *pir_detected)
{
    if (pir_detected == NULL) {
        return E_NOT_OK;
    }
    *pir_detected = s_mock_pir_detected;
    return s_mock_pir_ret;
}

Std_ReturnType Rte_Call_rpActuator_EmergencyStop(void)
{
    s_mock_estop_call_count++;
    return E_OK;
}

Std_ReturnType Rte_Call_rpIpc_SendFaultNotice(const char *reason)
{
    s_mock_ipc_fault_notice_count++;
    if (reason != NULL) {
        strncpy(s_mock_last_fault_notice, reason, sizeof(s_mock_last_fault_notice) - 1);
        s_mock_last_fault_notice[sizeof(s_mock_last_fault_notice) - 1] = '\0';
    }
    return E_OK;
}

void Rte_Get_Dht11Stats(uint32 *ok_cnt, uint32 *err_cnt)
{
    if (ok_cnt != NULL) {
        *ok_cnt = 0u;
    }
    if (err_cnt != NULL) {
        *err_cnt = 0u;
    }
}

MotorControl_ModeType Rte_Get_MotorMode(void)
{
    return s_mock_motor_mode;
}

void Rte_Set_MotorMode(MotorControl_ModeType mode)
{
    s_mock_motor_mode = mode;
}

const char *Rte_Get_MotorModeString(MotorControl_ModeType mode)
{
    switch (mode) {
    case MOTOR_MODE_STOPPED:     return "STOPPED";
    case MOTOR_MODE_OPEN_LOOP:   return "OPEN_LOOP";
    case MOTOR_MODE_CLOSED_LOOP: return "CLOSED_LOOP";
    case MOTOR_MODE_STEP_TEST:   return "STEP_TEST";
    case MOTOR_MODE_FAULT:       return "FAULT";
    default:                     return "UNKNOWN";
    }
}

float32 Rte_Get_ppDuty_percentage(void)
{
    return s_mock_duty_percentage;
}

void Rte_Set_rpSpeed_rpm(float32 speed)
{
    s_mock_speed_rpm = speed;
}

float32 Rte_Get_rpSpeed_rpm(void)
{
    return s_mock_speed_rpm;
}

float32 Rte_Get_ppTargetSpeed_rpm(void)
{
    return s_mock_target_speed_rpm;
}

void Rte_Set_rpTargetSpeed_rpm(float32 target_rpm)
{
    s_mock_target_speed_rpm = target_rpm;
}

float32 Rte_Get_TargetDuty_percentage(void)
{
    return s_mock_target_duty_percentage;
}

void Rte_Set_TargetDuty_percentage(float32 target_duty)
{
    s_mock_target_duty_percentage = target_duty;
}

void Rte_Get_StepConfig(MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        *config = s_mock_step_config;
    }
}

void Rte_Set_StepConfig(const MotorControl_StepConfigType *config)
{
    if (config != NULL) {
        s_mock_step_config = *config;
    }
}

boolean Rte_Get_EmergencyStop(void)
{
    return s_mock_emergency_stop;
}

void Rte_Set_EmergencyStop(boolean estop)
{
    s_mock_emergency_stop = estop;
}

void Rte_Get_SensorData(Sensor_DataType *data)
{
    if (data != NULL) {
        *data = s_mock_sensor_data;
    }
}

Safety_FaultReasonType Rte_Get_SafetyFault(void)
{
    return s_mock_safety_fault;
}

void Rte_Set_SafetyFault(Safety_FaultReasonType fault)
{
    s_mock_safety_fault = fault;
}

/* ==========================================================================
 * Test Cases
 * ========================================================================== */

/**
 * @brief Test 1: SensorManager Data Acquisition & Vector Magnitude
 *
 * Verifies that Runnable_SensorManager_100ms():
 * 1. Calls Rte_Call_rpAccel_Read and latches ax=0.0g, ay=0.0g, az=4.0g.
 * 2. Computes resultant acceleration magnitude |a| = sqrt(ax^2 + ay^2 + az^2) == 4.0g.
 * 3. Calls Rte_Call_rpEnvSensor_Read and latches temp=28.5 degC, hum=65.0%.
 * 4. Calls Rte_Call_rpPirSensor_Read and latches pir_detected=TRUE.
 * 5. Writes all results to Rte_Write_ppSensorData and exposes via Swc_SensorManager_GetSensors.
 */
static void test_sensor_manager(void)
{
    printf("[TEST 1/5] SensorManager Data Acquisition & Magnitude Computation...\n");
    Mock_ResetAll();

    /* Initialize Sensor Manager */
    Swc_SensorManager_Init();

    /* Configure mock hardware sensor values */
    s_mock_accel_x      = 0.0f;
    s_mock_accel_y      = 0.0f;
    s_mock_accel_z      = 4.0f;
    s_mock_accel_ret    = E_OK;

    s_mock_env_temp     = 28.5f;
    s_mock_env_hum      = 65.0f;
    s_mock_env_ret      = E_OK;

    s_mock_pir_detected = TRUE;
    s_mock_pir_ret      = E_OK;

    /* Execute the 100ms periodic runnable */
    Runnable_SensorManager_100ms();

    /* Verify published sensor data via RTE */
    assert(fabsf(s_mock_sensor_data.accel_x_g - 0.0f) < 0.001f);
    assert(fabsf(s_mock_sensor_data.accel_y_g - 0.0f) < 0.001f);
    assert(fabsf(s_mock_sensor_data.accel_z_g - 4.0f) < 0.001f);
    assert(fabsf(s_mock_sensor_data.accel_mag_g - 4.0f) < 0.001f);
    assert(fabsf(s_mock_sensor_data.temperature_c - 28.5f) < 0.001f);
    assert(fabsf(s_mock_sensor_data.humidity_pct - 65.0f) < 0.001f);
    assert(s_mock_sensor_data.pir_detected == TRUE);

    /* Verify data retrieval via SWC getter API */
    Sensor_DataType getter_data;
    Std_ReturnType ret = Swc_SensorManager_GetSensors(&getter_data);
    assert(ret == E_OK);
    assert(fabsf(getter_data.accel_mag_g - 4.0f) < 0.001f);
    assert(fabsf(getter_data.temperature_c - 28.5f) < 0.001f);
    assert(fabsf(getter_data.humidity_pct - 65.0f) < 0.001f);
    assert(getter_data.pir_detected == TRUE);

    printf("  -> PASS: accel_mag_g = %.2fg (expected 4.00g), temp = %.1fC, hum = %.1f%%, PIR = TRUE\n",
           s_mock_sensor_data.accel_mag_g, s_mock_sensor_data.temperature_c,
           s_mock_sensor_data.humidity_pct);
}

/**
 * @brief Test 2: SafetyManager — 3.5g Crash / Vibration Shock Detection
 *
 * Verifies that when accel_mag_g >= 3.5g (e.g. 3.8g):
 * 1. Runnable_SafetyCheck_10ms() detects severe impact shock.
 * 2. Triggers SAFETY_FAULT_CRASH immediately.
 * 3. Transitions MotorMode to MOTOR_MODE_FAULT.
 * 4. Sets EmergencyStop = TRUE and duty to 0.0%.
 * 5. Calls Rte_Call_rpActuator_EmergencyStop() to engage active dynamic braking.
 * 6. Emits a non-blocking IPC fault notification containing "CRASH".
 */
static void test_safety_manager_crash_detection(void)
{
    printf("[TEST 2/5] SafetyManager 3.5g Crash Detection & E-Stop Trigger...\n");
    Mock_ResetAll();

    Swc_SafetyManager_Init();

    /* Setup initial operating condition: closed-loop motor running normally */
    s_mock_motor_mode               = MOTOR_MODE_CLOSED_LOOP;
    s_mock_duty_percentage          = 50.0f;
    s_mock_emergency_stop           = FALSE;
    s_mock_safety_fault             = SAFETY_OK;
    s_mock_sensor_data.accel_mag_g  = 3.8f; /* Crash shock > 3.5g threshold */
    s_mock_sensor_data.pir_detected = FALSE;

    /* Execute the 10ms safety supervision runnable */
    Runnable_SafetyCheck_10ms();

    /* Assertions verifying crash response */
    assert(Swc_SafetyManager_GetFault() == SAFETY_FAULT_CRASH);
    assert(s_mock_safety_fault == SAFETY_FAULT_CRASH);
    assert(s_mock_motor_mode == MOTOR_MODE_FAULT);
    assert(s_mock_emergency_stop == TRUE);
    assert(fabsf(s_mock_duty_percentage - 0.0f) < 0.001f);
    assert(s_mock_estop_call_count >= 1u);
    assert(s_mock_ipc_fault_notice_count >= 1u);
    assert(strstr(s_mock_last_fault_notice, "CRASH") != NULL);

    printf("  -> PASS: Crash detected at 3.8g. Fault: %s, Mode: FAULT, E-Stop: TRUE, Notice: '%s'\n",
           Swc_SafetyManager_GetFaultString(Swc_SafetyManager_GetFault()),
           s_mock_last_fault_notice);
}

/**
 * @brief Test 3: SafetyManager — PIR Intrusion while Motor Running
 *
 * Verifies that:
 * 1. When PIR is enabled, pir_detected == TRUE, and motor is in CLOSED_LOOP:
 *    Runnable_SafetyCheck_10ms() triggers SAFETY_FAULT_PIR and latches E-Stop.
 * 2. When motor is STOPPED, PIR presence does NOT trigger a safety fault.
 * 3. When PIR supervision is disabled via Swc_SafetyManager_SetPirEnable(FALSE),
 *    PIR motion does NOT trigger a safety fault even when motor is running.
 */
static void test_safety_manager_pir_intrusion(void)
{
    printf("[TEST 3/5] SafetyManager PIR Intrusion Supervision...\n");
    Mock_ResetAll();

    Swc_SafetyManager_Init();
    Swc_SafetyManager_SetPirEnable(TRUE);

    /* Case 3a: Motor stopped, PIR active -> should NOT trip fault */
    s_mock_motor_mode               = MOTOR_MODE_STOPPED;
    s_mock_sensor_data.accel_mag_g  = 1.0f;
    s_mock_sensor_data.pir_detected = TRUE;
    s_mock_emergency_stop           = FALSE;
    s_mock_safety_fault             = SAFETY_OK;

    Runnable_SafetyCheck_10ms();
    assert(Swc_SafetyManager_GetFault() == SAFETY_OK);
    assert(s_mock_emergency_stop == FALSE);

    /* Case 3b: Motor running in CLOSED_LOOP, PIR active -> MUST trip SAFETY_FAULT_PIR */
    s_mock_motor_mode = MOTOR_MODE_CLOSED_LOOP;
    Runnable_SafetyCheck_10ms();

    assert(Swc_SafetyManager_GetFault() == SAFETY_FAULT_PIR);
    assert(s_mock_safety_fault == SAFETY_FAULT_PIR);
    assert(s_mock_motor_mode == MOTOR_MODE_FAULT);
    assert(s_mock_emergency_stop == TRUE);
    assert(strstr(s_mock_last_fault_notice, "PIR") != NULL);

    /* Case 3c: Clear fault, disable PIR supervision, re-run -> should NOT trip fault */
    Swc_SafetyManager_ClearFault();
    assert(Swc_SafetyManager_GetFault() == SAFETY_OK);
    assert(s_mock_emergency_stop == FALSE);

    Swc_SafetyManager_SetPirEnable(FALSE);
    s_mock_motor_mode               = MOTOR_MODE_CLOSED_LOOP;
    s_mock_sensor_data.pir_detected = TRUE;
    s_mock_sensor_data.accel_mag_g  = 1.0f;

    Runnable_SafetyCheck_10ms();
    assert(Swc_SafetyManager_GetFault() == SAFETY_OK);
    assert(s_mock_emergency_stop == FALSE);

    /* Restore PIR enable for subsequent tests */
    Swc_SafetyManager_SetPirEnable(TRUE);

    printf("  -> PASS: PIR correctly trips E-Stop during motor run and ignores motion when stopped/disabled.\n");
}

/**
 * @brief Test 4: SafetyManager — Manual vs Watchdog E-Stop Fault Classification
 *
 * Verifies that:
 * 1. When EmergencyStop == TRUE and SafetyFault == SAFETY_FAULT_MANUAL,
 *    Runnable_SafetyCheck_10ms() classifies it as SAFETY_FAULT_MANUAL (not WDG).
 * 2. When EmergencyStop == TRUE and SafetyFault == SAFETY_FAULT_WDG,
 *    Runnable_SafetyCheck_10ms() classifies it as SAFETY_FAULT_WDG (not MANUAL).
 */
static void test_safety_manager_estop_classification(void)
{
    printf("[TEST 4/5] SafetyManager Manual vs Watchdog E-Stop Classification...\n");
    Mock_ResetAll();

    Swc_SafetyManager_Init();

    /* Subtest 4a: Manual E-Stop Classification */
    s_mock_sensor_data.accel_mag_g  = 1.0f;
    s_mock_sensor_data.pir_detected = FALSE;
    s_mock_motor_mode               = MOTOR_MODE_CLOSED_LOOP;
    s_mock_emergency_stop           = TRUE;
    s_mock_safety_fault             = SAFETY_FAULT_MANUAL;
    s_mock_last_fault_notice[0]     = '\0';

    Runnable_SafetyCheck_10ms();
    assert(Swc_SafetyManager_GetFault() == SAFETY_FAULT_MANUAL);
    assert(Swc_SafetyManager_GetFault() != SAFETY_FAULT_WDG);
    assert(s_mock_safety_fault == SAFETY_FAULT_MANUAL);
    assert(s_mock_motor_mode == MOTOR_MODE_FAULT);
    assert(strstr(s_mock_last_fault_notice, "MANUAL") != NULL);

    /* Subtest 4b: IPC Heartbeat Watchdog Timeout Classification */
    Swc_SafetyManager_ClearFault();
    s_mock_sensor_data.accel_mag_g  = 1.0f;
    s_mock_sensor_data.pir_detected = FALSE;
    s_mock_motor_mode               = MOTOR_MODE_CLOSED_LOOP;
    s_mock_emergency_stop           = TRUE;
    s_mock_safety_fault             = SAFETY_FAULT_WDG;
    s_mock_last_fault_notice[0]     = '\0';

    Runnable_SafetyCheck_10ms();
    assert(Swc_SafetyManager_GetFault() == SAFETY_FAULT_WDG);
    assert(Swc_SafetyManager_GetFault() != SAFETY_FAULT_MANUAL);
    assert(s_mock_safety_fault == SAFETY_FAULT_WDG);
    assert(s_mock_motor_mode == MOTOR_MODE_FAULT);
    assert(strstr(s_mock_last_fault_notice, "WATCHDOG") != NULL);

    printf("  -> PASS: E-Stop correctly distinguishes MANUAL_ESTOP from WATCHDOG_TIMEOUT.\n");
}

/**
 * @brief Test 5: MotorControl — Closed-Loop PI, Overshoot Reduction, and Bidirectional Reverse
 *
 * Verifies that Runnable_MotorControl_10ms():
 * 1. Forward closed-loop (target_rpm = 80.0, current_rpm = 0.0) outputs positive duty >= 25.0%.
 * 2. Overshoot reduction (target_rpm = 60.0, current_rpm = 120.0 sustained) allows duty to drop
 *    below the active threshold (25.0%) down towards 0.0% to brake motor rapidly.
 * 3. Reverse closed-loop (target_rpm = -60.0, current_rpm = 0.0) outputs negative duty.
 */
static void test_motor_control_closed_loop_and_overshoot(void)
{
    printf("[TEST 5/5] MotorControl Closed-Loop PI, Overshoot & Bidirectional RPM...\n");
    Mock_ResetAll();

    Swc_MotorControl_Init();

    /* Subtest 5a: Forward Closed-Loop Start (target=80 RPM, speed=0 RPM) */
    s_mock_emergency_stop   = FALSE;
    s_mock_motor_mode       = MOTOR_MODE_CLOSED_LOOP;
    s_mock_target_speed_rpm = 80.0f;
    s_mock_speed_rpm        = 0.0f;

    Runnable_MotorControl_10ms();

    assert(s_mock_duty_percentage >= 25.0f);
    assert(s_mock_duty_percentage <= 85.0f);
    printf("  -> Subtest 5a (Forward +80 RPM): duty = %.2f%% (>= 25.0%%, <= 85.0%%) [PASS]\n",
           s_mock_duty_percentage);

    /* Subtest 5b: Sustained Overshoot (target=60 RPM, actual=120 RPM) */
    Swc_MotorControl_Init();
    s_mock_motor_mode       = MOTOR_MODE_CLOSED_LOOP;
    s_mock_target_speed_rpm = 60.0f;
    s_mock_speed_rpm        = 120.0f; /* Error = -60 RPM */

    /* Run several iterations to allow negative integral accumulation */
    for (int step = 0; step < 10; ++step) {
        Runnable_MotorControl_10ms();
    }

    assert(s_mock_duty_percentage < 25.0f);
    assert(s_mock_duty_percentage >= 0.0f);
    printf("  -> Subtest 5b (Overshoot 120 vs 60 RPM): duty = %.2f%% (< 25.0%%, >= 0.0%%) [PASS]\n",
           s_mock_duty_percentage);

    /* Subtest 5c: Reverse Closed-Loop (target=-60 RPM, speed=0 RPM) */
    Swc_MotorControl_Init();
    s_mock_motor_mode       = MOTOR_MODE_CLOSED_LOOP;
    s_mock_target_speed_rpm = -60.0f;
    s_mock_speed_rpm        = 0.0f;

    Runnable_MotorControl_10ms();

    assert(s_mock_duty_percentage < 0.0f);
    assert(s_mock_duty_percentage <= -25.0f);
    assert(s_mock_duty_percentage >= -85.0f);
    printf("  -> Subtest 5c (Reverse -60 RPM): duty = %.2f%% (negative, <= -25.0%%) [PASS]\n",
           s_mock_duty_percentage);

    /* Subtest 5d: Additional coverage - Open-Loop, Stopped, and Emergency Stop */
    Swc_MotorControl_Init();
    s_mock_motor_mode             = MOTOR_MODE_OPEN_LOOP;
    s_mock_target_duty_percentage = 42.5f;
    Runnable_MotorControl_10ms();
    assert(fabsf(s_mock_duty_percentage - 42.5f) < 0.01f);

    /* Emergency Stop overrides running mode */
    s_mock_emergency_stop = TRUE;
    Runnable_MotorControl_10ms();
    assert(s_mock_motor_mode == MOTOR_MODE_FAULT);
    assert(fabsf(s_mock_duty_percentage - 0.0f) < 0.001f);

    printf("  -> Subtest 5d (Open-Loop & E-Stop Override): [PASS]\n");
}

/* ==========================================================================
 * Main Test Runner
 * ========================================================================== */

int main(void)
{
    printf("====================================================================\n");
    printf("   CORTEX-M4 AUTOSAR ASW HOST UNIT TEST SUITE (C99)\n");
    printf("   Components: Swc_SensorManager, Swc_SafetyManager, Swc_MotorControl\n");
    printf("====================================================================\n\n");

    test_sensor_manager();
    test_safety_manager_crash_detection();
    test_safety_manager_pir_intrusion();
    test_safety_manager_estop_classification();
    test_motor_control_closed_loop_and_overshoot();

    printf("\n====================================================================\n");
    printf("   ALL 5 CORTEX-M4 ASW HOST UNIT TESTS PASSED SUCCESSFULLY! (100%%)\n");
    printf("====================================================================\n");

    return 0;
}
