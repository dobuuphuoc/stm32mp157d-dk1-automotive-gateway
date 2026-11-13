/*
 * CDD_Dht11 - DHT11 single-wire temperature / humidity driver (PE12, Arduino D13)
 *
 * Protocol (DHT11 datasheet):
 *   Host : pull line LOW >= 18 ms, then release (pull-up -> HIGH)
 *   DHT  : LOW 80 us, HIGH 80 us (response)
 *   40 bits: each = LOW ~50 us + HIGH 26-28 us ('0') or ~70 us ('1')
 *   Frame: RH_int, RH_dec, T_int, T_dec, checksum(sum of 4 bytes)
 *
 * Real-time design:
 *   - Runs in its own low-priority thread (never inside the 10 ms control task).
 *   - Bit sampling starts right after a 10 ms RTE tick has finished
 *     (Cdd_Dht11_TickSync), so the ~4.5 ms frame fits inside the idle window
 *     and is not preempted by the PID loop. No irq_lock -> PID jitter unaffected.
 *   - A corrupted frame (checksum error) is simply discarded; last good value is kept.
 */
#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include "Cdd_Dht11.h"

#define DHT11_PIN             12u
#define DHT11_PERIOD_MS       2000
#define DHT11_START_LOW_MS    20
#define DHT11_BIT_THRESH_US   45u

#if DT_NODE_EXISTS(DT_NODELABEL(gpioe))
static const struct device *const s_gpio = DEVICE_DT_GET(DT_NODELABEL(gpioe));
#else
static const struct device *const s_gpio = NULL;
#endif

K_SEM_DEFINE(s_dht_tick_sem, 0, 1);
static Cdd_Dht11_DataType s_dht;
static volatile boolean s_dht_inited = FALSE;

static inline uint32 Dht_Us(uint32 cycles)
{
    return (uint32)k_cyc_to_us_floor32(cycles);
}

/* Wait while pin == level; returns elapsed us or 0xFFFFFFFF on timeout */
static uint32 Dht_WaitWhile(int level, uint32 timeout_us)
{
    uint32 t0 = k_cycle_get_32();
    while (gpio_pin_get(s_gpio, DHT11_PIN) == level) {
        if (Dht_Us(k_cycle_get_32() - t0) > timeout_us) {
            return 0xFFFFFFFFu;
        }
    }
    return Dht_Us(k_cycle_get_32() - t0);
}

static boolean Dht_ReadFrame(uint8 out[5])
{
    /* 1. Start signal: LOW >= 18 ms */
    (void)gpio_pin_configure(s_gpio, DHT11_PIN, GPIO_OUTPUT_LOW);
    k_msleep(DHT11_START_LOW_MS);

    /* 2. Align with the end of a 10 ms control tick (jitter-free window) */
    k_sem_reset(&s_dht_tick_sem);
    if (k_sem_take(&s_dht_tick_sem, K_MSEC(30)) != 0) {
        /* RTE not running: proceed anyway */
    }

    /* 3. Release line -> input with pull-up */
    (void)gpio_pin_configure(s_gpio, DHT11_PIN, GPIO_INPUT | GPIO_PULL_UP);

    /* 4. Response: HIGH (release) -> LOW 80us -> HIGH 80us -> LOW (bit 0 start) */
    if (Dht_WaitWhile(1, 200u) == 0xFFFFFFFFu) { return FALSE; }
    if (Dht_WaitWhile(0, 120u) == 0xFFFFFFFFu) { return FALSE; }
    if (Dht_WaitWhile(1, 120u) == 0xFFFFFFFFu) { return FALSE; }

    /* 5. 40 data bits */
    for (uint8 i = 0u; i < 40u; i++) {
        if (Dht_WaitWhile(0, 100u) == 0xFFFFFFFFu) { return FALSE; }   /* ~50us LOW */
        uint32 high_us = Dht_WaitWhile(1, 120u);                         /* 26-70us HIGH */
        if (high_us == 0xFFFFFFFFu) { return FALSE; }
        out[i / 8u] = (uint8)(out[i / 8u] << 1);
        if (high_us > DHT11_BIT_THRESH_US) {
            out[i / 8u] |= 1u;
        }
    }

    /* 6. Checksum */
    uint8 sum = (uint8)(out[0] + out[1] + out[2] + out[3]);
    return (sum == out[4]) ? TRUE : FALSE;
}

static void Cdd_Dht11_Thread(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1); ARG_UNUSED(p2); ARG_UNUSED(p3);

    k_msleep(1500); /* DHT11 power-up stabilisation (>1 s) */

    while (1) {
        if (s_gpio != NULL && device_is_ready(s_gpio)) {
            uint8 f[5] = {0u, 0u, 0u, 0u, 0u};
            if (Dht_ReadFrame(f) != FALSE) {
                float32 t = (float32)(f[2] & 0x7Fu) + ((float32)(f[3] & 0x7Fu) * 0.1f);
                if ((f[3] & 0x80u) != 0u) {
                    t = -t;
                }
                s_dht.temperature_c = t;
                s_dht.humidity_pct = (float32)f[0] + ((float32)f[1] * 0.1f);
                s_dht.valid = TRUE;
                s_dht.ok_count++;
            } else {
                s_dht.err_count++;
            }
            (void)gpio_pin_configure(s_gpio, DHT11_PIN, GPIO_INPUT | GPIO_PULL_UP);
        }
        k_msleep(DHT11_PERIOD_MS);
    }
}

/* Priority 10: below RTE 10 ms task (1) and IPC thread (5) */
K_THREAD_DEFINE(cdd_dht11_thread, 2048, Cdd_Dht11_Thread, NULL, NULL, NULL,
                K_PRIO_PREEMPT(10), 0, 0);

Std_ReturnType Cdd_Dht11_Init(void)
{
    s_dht.temperature_c = 0.0f;
    s_dht.humidity_pct = 0.0f;
    s_dht.ok_count = 0u;
    s_dht.err_count = 0u;
    s_dht.valid = FALSE;
    s_dht_inited = TRUE;
    return E_OK;
}

void Cdd_Dht11_TickSync(void)
{
    k_sem_give(&s_dht_tick_sem);
}

void Cdd_Dht11_GetLatest(Cdd_Dht11_DataType *data)
{
    if (data != NULL) {
        unsigned int key = irq_lock();
        *data = s_dht;
        irq_unlock(key);
    }
}
