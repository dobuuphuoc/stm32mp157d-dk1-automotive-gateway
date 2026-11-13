#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/irq.h>
#include "Mcal_Icu.h"

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

/* Devicetree GPIO specifications for Encoder Channels A & B */
#if DT_NODE_EXISTS(ZEPHYR_USER_NODE)
static const struct gpio_dt_spec s_enc_a = GPIO_DT_SPEC_GET(ZEPHYR_USER_NODE, enc_a_gpios);
static const struct gpio_dt_spec s_enc_b = GPIO_DT_SPEC_GET(ZEPHYR_USER_NODE, enc_b_gpios);
#else
static const struct gpio_dt_spec s_enc_a = {0};
static const struct gpio_dt_spec s_enc_b = {0};
#endif

/* Periodic 1 kHz encoder polling timer (safely avoids EXTI BusFault) */
static struct k_timer s_enc_poll_timer;

/* 4x Quadrature State Machine Lookup Table
 * Transition index: (prev_state << 2) | curr_state
 * Output delta: +1 (Forward), -1 (Reverse), 0 (No change or Glitch/Invalid)
 */
static const sint8 k_quad_table[16] = {
    0, -1,  1,  0,
    1,  0,  0, -1,
   -1,  0,  0,  1,
    0,  1, -1,  0
};
#define s_quad_lut k_quad_table

/* Encoder State Variables */
static volatile uint8 s_prev_state = 0u;
static volatile sint32 s_pulse_accum = 0;
static volatile sint32 s_total_pulses = 0;
static float32 s_filtered_rpm = 0.0f;

/*
 * Pin sampling and quadrature decoding helper.
 * Called by periodic 1 kHz polling timer to safely sample encoder pins
 * without accessing EXTI controller (preventing Cortex-M4 BusFault).
 */
static void Icu_SamplePins(void)
{
    unsigned int key = irq_lock();

    int a = gpio_pin_get_dt(&s_enc_a);
    int b = gpio_pin_get_dt(&s_enc_b);
    uint8 curr_state = (uint8)(((a > 0 ? 1 : 0) << 1) | (b > 0 ? 1 : 0));

    uint8 idx = (uint8)((s_prev_state << 2) | curr_state);
    sint8 delta = k_quad_table[idx & 0x0Fu];
    s_prev_state = curr_state;

    s_pulse_accum += delta;
    s_total_pulses += delta;

    irq_unlock(key);
}

/*
 * Periodic 1 kHz (1 ms) Encoder Polling Timer Callback
 * Safely samples Encoder Phase A and Phase B without touching EXTI controller.
 */
static void Icu_TimerCallback(struct k_timer *timer_id)
{
    ARG_UNUSED(timer_id);

    Icu_SamplePins();
}

Std_ReturnType Mcal_Icu_Init(void)
{
    if (s_enc_a.port == NULL || !gpio_is_ready_dt(&s_enc_a)) {
        return E_NOT_OK;
    }
    if (s_enc_b.port == NULL || !gpio_is_ready_dt(&s_enc_b)) {
        return E_NOT_OK;
    }

    int ret = gpio_pin_configure_dt(&s_enc_a, GPIO_INPUT);
    if (ret < 0) {
        return E_NOT_OK;
    }

    ret = gpio_pin_configure_dt(&s_enc_b, GPIO_INPUT);
    if (ret < 0) {
        return E_NOT_OK;
    }

    /* Initialize initial state from hardware pin levels */
    int a = gpio_pin_get_dt(&s_enc_a);
    int b = gpio_pin_get_dt(&s_enc_b);
    s_prev_state = (uint8)(((a > 0 ? 1 : 0) << 1) | (b > 0 ? 1 : 0));
    s_pulse_accum = 0;
    s_total_pulses = 0;
    s_filtered_rpm = 0.0f;

    /* Start periodic 1 kHz (1 ms) timer polling safely without EXTI interrupts */
    k_timer_init(&s_enc_poll_timer, Icu_TimerCallback, NULL);
    k_timer_start(&s_enc_poll_timer, K_MSEC(1), K_MSEC(1));

    return E_OK;
}

void Icu_Update10ms(void)
{
    /* Atomically read and clear 10ms accumulated pulse count */
    unsigned int key = irq_lock();
    sint32 delta = s_pulse_accum;
    s_pulse_accum = 0;
    irq_unlock(key);

    /* Use magnitude abs_delta to prevent negative-RPM positive-feedback runaway
     * regardless of reversed Motor +/- or Encoder A/B wire polarity */
    sint32 abs_delta = (delta < 0) ? -delta : delta;

    /* Compute raw shaft speed in RPM:
     * raw_rpm = (abs_delta * 60.0f) / (ICU_ENC_COUNTS_PER_REV * ICU_SAMPLE_PERIOD_S)
     */
    float32 raw_rpm = ((float32)abs_delta * 60.0f) / (ICU_ENC_COUNTS_PER_REV * ICU_SAMPLE_PERIOD_S);

    /* Exponential Moving Average (EMA) low-pass filter: 30% new sample, 70% filtered */
    s_filtered_rpm = (ICU_RPM_EMA_ALPHA * raw_rpm) + ((1.0f - ICU_RPM_EMA_ALPHA) * s_filtered_rpm);
}

float32 Icu_GetSpeedRpm(void)
{
    return s_filtered_rpm;
}

sint32 Icu_GetTotalPulses(void)
{
    unsigned int key = irq_lock();
    sint32 total = s_total_pulses;
    irq_unlock(key);
    return total;
}

void Icu_ResetTotalPulses(void)
{
    unsigned int key = irq_lock();
    s_total_pulses = 0;
    irq_unlock(key);
}
