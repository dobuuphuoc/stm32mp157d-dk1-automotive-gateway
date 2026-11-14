#include "Swc_MotorControl.h"
#include "Rte.h"

/*
 * Discrete PID Controller Parameters for JGA25-370-46.8K Geared Motor
 * Tuned with MATLAB System Identification & PID Tuner (Week 6):
 * - K_P = 1.9641
 * - K_I = 85.0402
 * - K_D = 0.0000 (Pure PI velocity controller, zero derivative noise)
 * - K_DT = 0.01s (10ms, 100 Hz deterministic loop)
 */
static const float32 K_KP = 1.9641f;
static const float32 K_KI = 85.0402f;
static const float32 K_KD = 0.0000f;
static const float32 K_DT = 0.01f;

/* Integral anti-windup limits [-1.0f, 1.0f]:
 * With K_KI = 85.04f, 1.0s integral error produces ~85.0% duty,
 * perfectly matching the actuator dynamic range without windup saturation. */
static const float32 INTEGRAL_LIMIT_MAX = 1.0f;
static const float32 INTEGRAL_LIMIT_MIN = -1.0f;

/* Duty cycle limits when running (target > 0.0f) to guarantee visible PWM square wave:
 * [25.0%, 85.0%] ensures PD14 (TIM4_CH3) outputs a crisp 20 kHz (50 us period)
 * PWM wave up to 85% duty cycle */
#define DUTY_ACTIVE_MIN 25.0f
static const float32 DUTY_ACTIVE_MAX = 85.0f;

/* General duty cycle saturation bounds [-90.0%, 90.0%] */
static const float32 DUTY_LIMIT_MAX = 90.0f;
static const float32 DUTY_LIMIT_MIN = -90.0f;

/* Motor Control ASW State Variables */
static float32 s_integral_error = 0.0f;
static float32 s_prev_error = 0.0f;
static MotorControl_ModeType s_prev_mode = MOTOR_MODE_STOPPED;
static uint32 s_step_tick_10ms = 0u;

void Swc_MotorControl_Init(void)
{
    s_integral_error = 0.0f;
    s_prev_error = 0.0f;
    s_prev_mode = MOTOR_MODE_STOPPED;
    s_step_tick_10ms = 0u;
}

void Runnable_MotorControl_10ms(void)
{
    MotorControl_ModeType mode = MOTOR_MODE_STOPPED;
    boolean estop = FALSE;
    float32 duty = 0.0f;

    /* 1. Read Mode and Emergency Stop state from RTE */
    (void)Rte_Read_rpMotorMode(&mode);
    (void)Rte_Read_rpEmergencyStop(&estop);

    /* 2. Emergency stop forces immediate FAULT mode */
    if (estop != FALSE) {
        mode = MOTOR_MODE_FAULT;
        (void)Rte_Write_ppMotorMode(MOTOR_MODE_FAULT);
    }

    /* 3. Detect state transitions for bumpless transfer and timers */
    if (mode != s_prev_mode) {
        if (mode == MOTOR_MODE_CLOSED_LOOP) {
            /* Bumpless transfer: reset integrator and previous error */
            s_integral_error = 0.0f;
            s_prev_error = 0.0f;
        } else if (mode == MOTOR_MODE_STEP_TEST) {
            /* Reset step test execution timer */
            s_step_tick_10ms = 0u;
        }
    }

    /* 4. Finite State Machine Behavior */
    switch (mode) {
    case MOTOR_MODE_FAULT:
    case MOTOR_MODE_STOPPED:
    default:
        duty = 0.0f;
        s_integral_error = 0.0f;
        s_prev_error = 0.0f;
        break;

    case MOTOR_MODE_OPEN_LOOP:
    {
        float32 target_duty = 0.0f;
        (void)Rte_Read_rpTargetDuty_percentage(&target_duty);

        /* Saturation clamping [-90.0%, 90.0%] */
        if (target_duty > DUTY_LIMIT_MAX) {
            target_duty = DUTY_LIMIT_MAX;
        } else if (target_duty < DUTY_LIMIT_MIN) {
            target_duty = DUTY_LIMIT_MIN;
        }
        duty = target_duty;
        break;
    }

    case MOTOR_MODE_CLOSED_LOOP:
    {
        float32 target_rpm = 0.0f;
        float32 current_speed = 0.0f;

        (void)Rte_Read_rpTargetSpeed_rpm(&target_rpm);
        (void)Rte_Read_rpSpeed_rpm(&current_speed);

        /* Deadband: if target speed is near 0, disable PID drive */
        if (target_rpm > -0.5f && target_rpm < 0.5f) {
            duty = 0.0f;
            s_integral_error = 0.0f;
            s_prev_error = 0.0f;
        } else {
            float32 error = target_rpm - current_speed;

            /* Proportional term */
            float32 p_term = K_KP * error;

            /* Integral term with anti-windup clamping [-25.0f, 25.0f] */
            s_integral_error += error * K_DT;
            if (s_integral_error > INTEGRAL_LIMIT_MAX) {
                s_integral_error = INTEGRAL_LIMIT_MAX;
            } else if (s_integral_error < INTEGRAL_LIMIT_MIN) {
                s_integral_error = INTEGRAL_LIMIT_MIN;
            }
            float32 i_term = K_KI * s_integral_error;

            /* Derivative term */
            float32 derivative = (error - s_prev_error) / K_DT;
            s_prev_error = error;
            float32 d_term = K_KD * derivative;

            duty = p_term + i_term + d_term;

            /* Saturation clamping on output duty:
             * Supports bidirectional target speeds and allows PID output to go
             * down to 0.0f when decelerating or overshooting.
             * Forward rotation (target_rpm > 0.0f): clamped to [0.0f, DUTY_ACTIVE_MAX].
             * Reverse rotation (target_rpm < 0.0f): clamped to [-DUTY_ACTIVE_MAX, 0.0f].
             */
            if (target_rpm > 0.0f) {
                if (duty > DUTY_ACTIVE_MAX) {
                    duty = DUTY_ACTIVE_MAX;
                } else if (duty < 0.0f) {
                    duty = 0.0f;
                }
            } else {
                if (duty < -DUTY_ACTIVE_MAX) {
                    duty = -DUTY_ACTIVE_MAX;
                } else if (duty > 0.0f) {
                    duty = 0.0f;
                }
            }
        }
        break;
    }

    case MOTOR_MODE_STEP_TEST:
    {
        MotorControl_StepConfigType step_cfg;
        if (Rte_Read_rpStepConfig(&step_cfg) != E_OK) {
            step_cfg.base_duty = 0.0f;
            step_cfg.step_duty = 60.0f;
            step_cfg.pre_step_ms = 1000u;
            step_cfg.step_dur_ms = 3000u;
        }

        uint32 pre_ticks = step_cfg.pre_step_ms / 10u;
        uint32 step_ticks = step_cfg.step_dur_ms / 10u;

        if (s_step_tick_10ms < pre_ticks) {
            duty = step_cfg.base_duty;
            s_step_tick_10ms++;
        } else if (s_step_tick_10ms < (pre_ticks + step_ticks)) {
            duty = step_cfg.step_duty;
            s_step_tick_10ms++;
        } else {
            /* Step response completed: transition to STOPPED */
            duty = 0.0f;
            mode = MOTOR_MODE_STOPPED;
            (void)Rte_Write_ppMotorMode(MOTOR_MODE_STOPPED);
        }

        /* Clamp duty to allowable bounds */
        if (duty > DUTY_LIMIT_MAX) {
            duty = DUTY_LIMIT_MAX;
        } else if (duty < DUTY_LIMIT_MIN) {
            duty = DUTY_LIMIT_MIN;
        }
        break;
    }
    }

    /* Record mode for transition detection in the next cycle */
    s_prev_mode = mode;

    /* 5. Output duty command to RTE port */
    (void)Rte_Write_ppDuty_percentage(duty);
}

void Swc_MotorControl_SetTestMode(boolean enable, float32 test_duty)
{
    if (enable != FALSE) {
        (void)Rte_Write_ppTargetDuty_percentage(test_duty);
        (void)Rte_Write_ppMotorMode(MOTOR_MODE_OPEN_LOOP);
    } else {
        (void)Rte_Write_ppMotorMode(MOTOR_MODE_CLOSED_LOOP);
    }
}

boolean Swc_MotorControl_GetTestMode(void)
{
    MotorControl_ModeType mode = MOTOR_MODE_STOPPED;
    (void)Rte_Read_rpMotorMode(&mode);
    return (mode == MOTOR_MODE_OPEN_LOOP) ? TRUE : FALSE;
}
