#include <zephyr/kernel.h>
#include <zephyr/drivers/pwm.h>
#include "Mcal_Pwm.h"

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

#if DT_NODE_EXISTS(ZEPHYR_USER_NODE) && DT_NODE_HAS_PROP(ZEPHYR_USER_NODE, pwms)
static const struct pwm_dt_spec s_pwm_motor = PWM_DT_SPEC_GET(ZEPHYR_USER_NODE);
#else
static const struct pwm_dt_spec s_pwm_motor = {0};
#endif

Std_ReturnType Mcal_Pwm_Init(void)
{
    if (s_pwm_motor.dev == NULL || !pwm_is_ready_dt(&s_pwm_motor)) {
        return E_NOT_OK;
    }

    /* Configure initial state to idle (0% duty cycle) */
    uint32 period = (s_pwm_motor.period > 0u) ? s_pwm_motor.period : PWM_PERIOD_NS;
    int ret = pwm_set_dt(&s_pwm_motor, period, 0u);
    if (ret < 0) {
        return E_NOT_OK;
    }

    return E_OK;
}

Std_ReturnType Pwm_SetDutyCycle(Pwm_ChannelType ChannelNumber, float32 DutyPercent)
{
    if (ChannelNumber >= PWM_CH_MAX) {
        return E_NOT_OK;
    }

    if (s_pwm_motor.dev == NULL || !pwm_is_ready_dt(&s_pwm_motor)) {
        return E_NOT_OK;
    }

    /* Clamp duty cycle percentage between 0.0% and 100.0% */
    if (DutyPercent < 0.0f) {
        DutyPercent = 0.0f;
    } else if (DutyPercent > 100.0f) {
        DutyPercent = 100.0f;
    }

    uint32 period = (s_pwm_motor.period > 0u) ? s_pwm_motor.period : PWM_PERIOD_NS;
    uint32 pulse = (uint32)((DutyPercent / 100.0f) * (float32)period);
    if (pulse > period) {
        pulse = period;
    }

    int ret = pwm_set_pulse_dt(&s_pwm_motor, pulse);
    if (ret < 0) {
        return E_NOT_OK;
    }

    return E_OK;
}

void Pwm_SetOutputToIdle(Pwm_ChannelType ChannelNumber)
{
    if (ChannelNumber >= PWM_CH_MAX) {
        return;
    }

    if (s_pwm_motor.dev != NULL && pwm_is_ready_dt(&s_pwm_motor)) {
        (void)pwm_set_pulse_dt(&s_pwm_motor, 0u);
    }
}
