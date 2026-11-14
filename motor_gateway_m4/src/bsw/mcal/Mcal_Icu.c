#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/irq.h>
#include "Mcal_Icu.h"

#define ZEPHYR_USER_NODE DT_PATH(zephyr_user)

/* Devicetree GPIO specifications for Encoder Channels A & B (Fallback mode) */
#if DT_NODE_EXISTS(ZEPHYR_USER_NODE)
static const struct gpio_dt_spec s_enc_a = GPIO_DT_SPEC_GET(ZEPHYR_USER_NODE, enc_a_gpios);
static const struct gpio_dt_spec s_enc_b = GPIO_DT_SPEC_GET(ZEPHYR_USER_NODE, enc_b_gpios);
#else
static const struct gpio_dt_spec s_enc_a = {0};
static const struct gpio_dt_spec s_enc_b = {0};
#endif

/* Hardware TIM3 Register Mapping (STM32MP157 APB1 @ 0x40000400) */
#ifndef TIM3_BASE
#define TIM3_BASE 0x40000400UL
#endif

typedef struct {
    volatile uint32 CR1;
    volatile uint32 CR2;
    volatile uint32 SMCR;
    volatile uint32 DIER;
    volatile uint32 SR;
    volatile uint32 EGR;
    volatile uint32 CCMR1;
    volatile uint32 CCMR2;
    volatile uint32 CCER;
    volatile uint32 CNT;
    volatile uint32 PSC;
    volatile uint32 ARR;
} Stm32_Tim_RegType;

#define TIM3_REG ((Stm32_Tim_RegType *)TIM3_BASE)

static volatile boolean s_tim3_hw_active = FALSE;
static volatile sint16 s_prev_tim3_cnt = 0;

/* Periodic 1 kHz encoder polling timer (safely avoids EXTI BusFault in GPIO fallback) */
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
    Std_ReturnType status = E_NOT_OK;

    /* 1. Attempt hardware TIM3 Quadrature Encoder initialization */
#if defined(CONFIG_SOC_SERIES_STM32MP1X) || defined(TIM3_BASE)
    TIM3_REG->CR1 &= ~0x0001u;             /* Stop counter before configuring */
    TIM3_REG->PSC = 0u;                    /* No prescaler */
    TIM3_REG->ARR = 0xFFFFu;               /* Full 16-bit range */
    TIM3_REG->CCMR1 = 0x0101u;             /* CC1 -> TI1FP1, CC2 -> TI2FP2 */
    TIM3_REG->CCER = 0x0000u;              /* Active high polarity for both channels */
    TIM3_REG->SMCR = (TIM3_REG->SMCR & ~0x0007u) | 0x0003u; /* SMS = 011: Encoder mode 3 */
    TIM3_REG->CNT = 0u;
    TIM3_REG->CR1 |= 0x0001u;              /* CEN = 1: Enable counter */
    s_tim3_hw_active = TRUE;
    s_prev_tim3_cnt = 0;
    status = E_OK;
#endif

    /* 2. Configure GPIO pins for fallback quadrature decoder */
    if (s_enc_a.port != NULL && gpio_is_ready_dt(&s_enc_a) &&
        s_enc_b.port != NULL && gpio_is_ready_dt(&s_enc_b)) {

        int ret_a = gpio_pin_configure_dt(&s_enc_a, GPIO_INPUT);
        int ret_b = gpio_pin_configure_dt(&s_enc_b, GPIO_INPUT);
        if (ret_a == 0 && ret_b == 0) {
            int a = gpio_pin_get_dt(&s_enc_a);
            int b = gpio_pin_get_dt(&s_enc_b);
            s_prev_state = (uint8)(((a > 0 ? 1 : 0) << 1) | (b > 0 ? 1 : 0));
            s_pulse_accum = 0;

            if (!s_tim3_hw_active) {
                /* Start periodic 1 kHz timer polling in GPIO fallback mode */
                k_timer_init(&s_enc_poll_timer, Icu_TimerCallback, NULL);
                k_timer_start(&s_enc_poll_timer, K_MSEC(1), K_MSEC(1));
            }
            status = E_OK;
        }
    }

    s_total_pulses = 0;
    s_filtered_rpm = 0.0f;

    return status;
}

void Icu_Update10ms(void)
{
    sint32 delta = 0;

    if (s_tim3_hw_active) {
        uint16 curr_cnt = (uint16)(TIM3_REG->CNT & 0xFFFFu);
        delta = (sint16)(curr_cnt - (uint16)s_prev_tim3_cnt);
        s_prev_tim3_cnt = (sint16)curr_cnt;

        unsigned int key = irq_lock();
        s_total_pulses += delta;
        irq_unlock(key);
    } else {
        /* Atomically read and clear 10ms accumulated pulse count */
        unsigned int key = irq_lock();
        delta = s_pulse_accum;
        s_pulse_accum = 0;
        irq_unlock(key);
    }

    /* Keep signed delta to preserve negative RPM during reverse rotation!
     * inst_rpm = ((float32)delta * 60.0f) / (ICU_ENC_COUNTS_PER_REV * ICU_SAMPLE_PERIOD_S)
     *          = ((float32)delta * 6000.0f) / ICU_ENC_COUNTS_PER_REV
     */
    float32 inst_rpm = ((float32)delta * 6000.0f) / ICU_ENC_COUNTS_PER_REV;

    /* Exponential Moving Average (EMA) low-pass filter: 30% new sample, 70% filtered */
    s_filtered_rpm = (ICU_RPM_EMA_ALPHA * inst_rpm) + ((1.0f - ICU_RPM_EMA_ALPHA) * s_filtered_rpm);
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
    if (s_tim3_hw_active) {
        TIM3_REG->CNT = 0u;
        s_prev_tim3_cnt = 0;
    }
    irq_unlock(key);
}
