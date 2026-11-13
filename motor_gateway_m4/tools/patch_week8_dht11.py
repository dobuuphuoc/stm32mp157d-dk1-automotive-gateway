import os, sys
BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/zephyrproject/motor_gateway_m4")
NEW_FILES = {}
NEW_FILES['src/bsw/cdd/Cdd_Dht11.h'] = r'''#ifndef CDD_DHT11_H
#define CDD_DHT11_H

#include "std_types.h"

/* DHT11 measurement snapshot */
typedef struct {
    float32 temperature_c;   /* [degC] */
    float32 humidity_pct;    /* [%RH] */
    uint32  ok_count;        /* number of valid frames (checksum OK) */
    uint32  err_count;       /* number of failed frames (timeout / checksum) */
    boolean valid;           /* TRUE once at least one valid frame received */
} Cdd_Dht11_DataType;

Std_ReturnType Cdd_Dht11_Init(void);
/* Called at the END of every 10 ms RTE tick: gives the DHT11 thread a
 * jitter-free window (~9 ms) to sample the 40-bit frame without colliding
 * with the real-time control task. */
void Cdd_Dht11_TickSync(void);
void Cdd_Dht11_GetLatest(Cdd_Dht11_DataType *data);

#endif /* CDD_DHT11_H */
'''
NEW_FILES['src/bsw/cdd/Cdd_Dht11.c'] = r'''/*
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
'''
NEW_FILES['src/asw/Swc_SensorManager.c'] = r'''#include "Swc_SensorManager.h"
#include "Mcal_Dio.h"
#include "Rte.h"
#include <math.h>

static Sensor_DataType s_sensor_data;

void Swc_SensorManager_Init(void)
{
    s_sensor_data.accel_x_g = 0.0f;
    s_sensor_data.accel_y_g = 0.0f;
    s_sensor_data.accel_z_g = 1.0f;
    s_sensor_data.accel_mag_g = 1.0f;
    s_sensor_data.temperature_c = 0.0f;
    s_sensor_data.humidity_pct = 0.0f;
    s_sensor_data.pir_detected = FALSE;

    (void)Rte_Write_ppSensorData(&s_sensor_data);
}

void Runnable_SensorManager_100ms(void)
{
    /* 1. HC-SR501 PIR (PE13) */
    s_sensor_data.pir_detected = (Dio_ReadChannel(DIO_CH_PIR_PE13) == STD_HIGH) ? TRUE : FALSE;

    /* 2. GY-61 accelerometer (3 x ADC) -> resultant vibration magnitude |a| */
    float32 ax = 0.0f, ay = 0.0f, az = 1.0f;
    if (Rte_Call_rpAccel_Read(&ax, &ay, &az) == E_OK) {
        s_sensor_data.accel_x_g = ax;
        s_sensor_data.accel_y_g = ay;
        s_sensor_data.accel_z_g = az;
        s_sensor_data.accel_mag_g = sqrtf((ax * ax) + (ay * ay) + (az * az));
    }

    /* 3. DHT11 (sampled every 2 s by CDD_Dht11 thread; here we latch the latest valid value) */
    float32 t = 0.0f, h = 0.0f;
    if (Rte_Call_rpEnvSensor_Read(&t, &h) == E_OK) {
        s_sensor_data.temperature_c = t;
        s_sensor_data.humidity_pct = h;
    }

    (void)Rte_Write_ppSensorData(&s_sensor_data);
}

Std_ReturnType Swc_SensorManager_GetSensors(Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    *data = s_sensor_data;
    return E_OK;
}
'''

def rd(p):
    with open(os.path.join(BASE, p), "r", newline="") as f:
        return f.read().replace("\r\n", "\n")

def wr(p, s):
    with open(os.path.join(BASE, p), "w", newline="\n") as f:
        f.write(s)

def ok(name, cond):
    print(("  [OK]   " if cond else "  [FAIL] ") + name)

for p, s in NEW_FILES.items():
    wr(p, s)
    ok("write " + p, True)

# ---- Rte.c ----
r = rd("src/rte/Rte.c")
if '#include "Cdd_Dht11.h"' not in r:
    r = r.replace('#include "Cdd_Ipc.h"', '#include "Cdd_Ipc.h"\n#include "Cdd_Dht11.h"', 1)
if "Cdd_Dht11_Init();" not in r:
    r = r.replace("    Swc_SensorManager_Init();", "    (void)Cdd_Dht11_Init();\n    Swc_SensorManager_Init();", 1)
if "Cdd_Dht11_TickSync();" not in r:
    r = r.replace("    Cdd_Ipc_MainFunction_10ms();\n", "    Cdd_Ipc_MainFunction_10ms();\n\n    /* Open jitter-free window for DHT11 sampling thread */\n    Cdd_Dht11_TickSync();\n", 1)
if "Rte_Call_rpEnvSensor_Read" not in r:
    r += """
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
"""
ok("Rte.c: DHT11 init + tick sync + C/S ports",
   ("Cdd_Dht11_TickSync();" in r) and ("Cdd_Dht11_Init();" in r) and ("Rte_Call_rpAccel_Read" in r))
wr("src/rte/Rte.c", r)

# ---- Rte.h ----
h = rd("src/rte/Rte.h")
if "Rte_Call_rpEnvSensor_Read" not in h:
    decl = """/* RTE Client-Server ports: sensor drivers */
Std_ReturnType Rte_Call_rpEnvSensor_Read(float32 *temp_c, float32 *hum_pct);
Std_ReturnType Rte_Call_rpAccel_Read(float32 *ax_g, float32 *ay_g, float32 *az_g);
void Rte_Get_Dht11Stats(uint32 *ok_cnt, uint32 *err_cnt);

"""
    idx = h.rfind("#endif")
    h = h[:idx] + decl + h[idx:]
ok("Rte.h: declarations", "Rte_Call_rpAccel_Read" in h)
wr("src/rte/Rte.h", h)

# ---- Cdd_Ipc.c telemetry: add HUM + DHT11 ok/err counters ----
c = rd("src/bsw/cdd/Cdd_Ipc.c")
if "HUM=%d" not in c:
    c = c.replace("    int flt = (int)Rte_Get_SafetyFault();\n",
                  "    int flt = (int)Rte_Get_SafetyFault();\n    int hum_x10 = (int)(sens.humidity_pct * 10.0f);\n    uint32 dok = 0u, der = 0u;\n    Rte_Get_Dht11Stats(&dok, &der);\n", 1)
    c = c.replace("    char payload[128];\n    char frame[144];\n", "    char payload[160];\n    char frame[176];\n", 1)
    c = c.replace('PIR=%d,VIB=%d,TMP=%d,FLT=%d",', 'PIR=%d,VIB=%d,TMP=%d,HUM=%d,FLT=%d,DHT=%lu/%lu",', 1)
    c = c.replace("vib_mg, tmp_x10, flt);", "vib_mg, tmp_x10, hum_x10, flt, (unsigned long)dok, (unsigned long)der);", 1)
ok("Cdd_Ipc.c: telemetry HUM + DHT=ok/err", ("HUM=%d" in c) and ("hum_x10, flt, (unsigned long)dok" in c))
wr("src/bsw/cdd/Cdd_Ipc.c", c)

# ---- CMakeLists.txt ----
m = rd("CMakeLists.txt")
if "Cdd_Dht11.c" not in m:
    m = m.replace("    src/bsw/cdd/Cdd_Ipc.c\n", "    src/bsw/cdd/Cdd_Ipc.c\n    src/bsw/cdd/Cdd_Dht11.c\n", 1)
ok("CMakeLists.txt: Cdd_Dht11.c", "Cdd_Dht11.c" in m)
wr("CMakeLists.txt", m)
print(">>> PATCH DHT11 DONE:", BASE)
