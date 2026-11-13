# Generates tools/patch_week8_dht11.py (self-contained, paste into Ubuntu VM)
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FILES = ["src/bsw/cdd/Cdd_Dht11.h", "src/bsw/cdd/Cdd_Dht11.c", "src/asw/Swc_SensorManager.c"]

def load(p):
    with open(os.path.join(ROOT, p), "r", newline="") as f:
        return f.read().replace("\r\n", "\n")

PATCH = r'''
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
'''

out = ["import os, sys",
       'BASE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/zephyrproject/motor_gateway_m4")',
       "NEW_FILES = {}"]
for p in FILES:
    s = load(p)
    assert "'''" not in s
    out.append("NEW_FILES[%r] = r'''%s'''" % (p, s))
out.append(PATCH)
with open(os.path.join(HERE, "patch_week8_dht11.py"), "w", newline="\n") as f:
    f.write("\n".join(out))
print("generated tools/patch_week8_dht11.py")
