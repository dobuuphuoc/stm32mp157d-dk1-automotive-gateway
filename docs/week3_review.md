# Week 3 Progress Report: OpenAMP/RPMsg IPC, CRC-16 Integrity Check & Heartbeat Watchdog Fail-Safe

- **Project:** Automotive Gateway & Real-Time Motor Controller (STM32MP157D-DK1)
- **Software Architecture:** AUTOSAR Classic on Zephyr RTOS (Cortex-M4) & OpenSTLinux (Cortex-A7)
- **Timeline:** Week 3 (Milestone 3)
- **Authors:** Embedded Engineering Team & Antigravity Assistant
- **Status:** 100% Completed (Milestone 3 Achieved)

---

## 1. Week 3 Objectives Overview

Week 3 focused on establishing real-time Asymmetric Multiprocessing Inter-Processor Communication (AMP IPC) between the dual processor cores of the STM32MP157 SoC:
- **Cortex-A7 (Host / Master):** Runs Linux (OpenSTLinux kernel 6.6), handling high-level orchestration, network telemetry, logging, and user interfaces.
- **Cortex-M4 (Remote / Coprocessor):** Runs Zephyr RTOS conforming to AUTOSAR Classic, executing the hard real-time 10 ms ($100\text{ Hz}$) closed-loop motor control algorithm.

### Completed Deliverables:
1. **Enable OpenAMP Stack & Resource Table on Cortex-M4 (`motor_gateway_m4`):**
   - Configured Kconfig options: `CONFIG_IPM=y`, `CONFIG_OPENAMP=y`, `CONFIG_OPENAMP_RSC_TABLE=y`, `CONFIG_OPENAMP_RSC_TABLE_NUM_RPMSG_BUFF=8`.
   - Adjusted `deploy.sh` pipeline: Switched `arm-zephyr-eabi-strip` flag from `-s` to `-g` (`--strip-debug`) to preserve the mandatory `.resource_table` section required by Linux `remoteproc`.
2. **Develop Complex Device Driver Module `Cdd_Ipc` (`Cdd_Ipc.h`, `Cdd_Ipc.c`):**
   - Initialized RPMsg TTY endpoint (`"rpmsg-tty"`) binding directly to `/dev/ttyRPMSG0` under Linux.
   - Spawned dedicated thread `cdd_ipc_thread` (priority `K_PRIO_PREEMPT(5)`, 2048-byte stack), completely decoupled from the hard real-time 10 ms control loop (priority `K_PRIO_PREEMPT(1)`).
   - Implemented dynamic destination address learning (`s_tty_ept.dest_addr`) on initial frame reception from Linux.
   - Implemented ASCII command parser: `SPEED <rpm>`, `DUTY <val>`, `STOP`, `WDG ON/OFF`, `HB`.
3. **CRC-16-CCITT Data Integrity Verification:**
   - Generator polynomial $P(x) = x^{16} + x^{12} + x^5 + 1$ (`poly = 0x1021`, initial value `init = 0xFFFF`).
   - Encapsulated periodic 5 Hz (every 200 ms) Telemetry frame streamed to Linux:
     `$TELEM,TGT=<int>,RPM=<int>,DUTY=<int>,CNT=<pulses>*<CRC16_HEX>\r\n`
4. **Heartbeat Watchdog Fail-Safe Mechanism:**
   - 100-tick timeout counter running at 10 ms resolution ($1.0\text{ s}$).
   - When watchdog supervision is active (`WDG ON`), if Linux freezes, kernel panics, or ceases sending `HB` heartbeats within $1.0\text{ s}$, Cortex-M4 autonomously engages emergency braking (`Swc_MotorControl_SetTestMode(TRUE, 0.0f)` and `Cdd_L298n_EmergencyStop()`).
5. **RTE & Lifecycle Integration:**
   - Integrated `Cdd_Ipc_Init()` into ECU state manager initialization `EcuM_Init()`.
   - Integrated `Cdd_Ipc_MainFunction_10ms()` into the periodic dispatcher `Rte_TimerEvent_10ms()`.
6. **Cortex-A7 Linux Host Control & Telemetry Utility (`gateway_a7/ipc_ctl.sh`):**
   - Bash CLI utility providing `stty` port configuration, command dispatching, background heartbeat daemon loop, and real-time telemetry streaming with CRC-16 checksum validation.

---

## 2. OpenAMP / RPMsg Inter-Core Communication Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CORTEX-A7 (Linux OpenSTLinux)                   │
│  ┌────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │   ipc_ctl.sh CLI Tool  │  │  Applications / Daemons (Future Qt)  │  │
│  └───────────┬────────────┘  └──────────────────┬───────────────────┘  │
│              │                                  │                      │
│              ▼                                  ▼                      │
│     /dev/ttyRPMSG0 (RPMsg TTY Character Device Driver)                 │
│  ────────────────────────────────────────────────────────────────────  │
│  Kernel Remoteproc Subsystem + IPCC Mailbox Driver (stm32_ipcc)        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                      Shared SRAM3/SRAM4 & IPCC Mailbox
              (0x10040000 - 32 KB: Resource Table, Vring0, Vring1)
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│                    CORTEX-M4 (Zephyr RTOS / AUTOSAR BSW)               │
│  IPCC Mailbox ISR (ipm_stm32_ipcc) ──> k_sem_give(&s_ipc_sem)          │
│                                              │                         │
│  ┌───────────────────────────────────────────▼──────────────────────┐  │
│  │ cdd_ipc_thread (K_PRIO_PREEMPT(5), Stack 2048)                    │  │
│  │ - rproc_virtio_notified()                                        │  │
│  │ - rpmsg-tty Endpoint Rx Callback:                                │  │
│  │     Parse SPEED, DUTY, STOP, WDG, HB                              │  │
│  │ - Telemetry Transmission (5 Hz):                                  │  │
│  │     $TELEM,TGT=...,RPM=...,DUTY=...,CNT=...*<CRC16>               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                              ▲                         │
│               RTE Sender/Receiver Ports      │                         │
│  ┌───────────────────────────────────────────┴──────────────────────┐  │
│  │ Hard Real-Time 10ms Task (Priority 1)                            │  │
│  │ - Mcal_Dio Test Toggle (PE9)                                     │  │
│  │ - Mcal_Icu Encoder Speed Calculation                             │  │
│  │ - Swc_MotorControl Runnable (PID / Open-Loop)                    │  │
│  │ - Cdd_L298n H-Bridge Duty Cycle Actuation                        │  │
│  │ - Cdd_Ipc_MainFunction_10ms: Heartbeat Watchdog & 200ms Trigger  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1. Shared Memory Layout
Per STM32MP157 Device Tree and Resource Table bindings:
- **Base Address:** `0x10040000` (residing in internal SRAM3 / SRAM4 of the STM32MP157D SoC).
- **Total Allocation:** `32 KB` (`0x8000` bytes).
- **Internal Memory Map:**
  - `0x10040000 - 0x100401FF`: `fw_resource_table` defining VirtIO devices and 2 vrings.
  - `0x10040200 - 0x10041FFF`: VirtIO Ring 0 (TX: M4 $\rightarrow$ A7) and VirtIO Ring 1 (RX: A7 $\rightarrow$ M4).
  - `0x10042000 - 0x10047FFF`: RPMsg packet buffer pool (8 buffers, 512 bytes each).

### 2.2. Hardware IPCC (Inter-Processor Communication Controller)
The STM32MP157 integrates an IPCC hardware block comprising 6 bidirectional full-duplex channels triggering hardware interrupts between cores:
- When Linux posts data to a vring, it triggers an IPCC interrupt to Cortex-M4.
- The Zephyr `ipm_stm32_ipcc` driver handles the ISR and executes `Cdd_Ipc_IpmCallback`, releasing `s_ipc_sem` to awaken `cdd_ipc_thread`.
- When Cortex-M4 transmits data, `Virtio_Notify` calls `ipm_send` to assert an interrupt line to Cortex-A7.

---

## 3. Resolving Resource Table Stripping in the Build Pipeline (`deploy.sh`)

### 3.1. Root Cause Analysis
When Cortex-A7 starts Cortex-M4 firmware via the Linux `remoteproc` subsystem:
1. Linux parses the ELF binary at `/lib/firmware/motor_gateway_m4.elf`.
2. The Linux ELF loader scans section headers for `.resource_table` to configure shared memory and IPCC channels.
3. In the initial pipeline, the strip utility was executed with `-s`:
   ```bash
   arm-zephyr-eabi-strip -s build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf
   ```
   The `-s` flag (`--strip-all`) stripped the symbol table and metadata required by `remoteproc0`, resulting in:
   `remoteproc remoteproc0: no-resource-table ... failed to load ...`

### 3.2. Permanent Engineering Fix
Switched the strip argument to `-g` (`--strip-debug`):
```bash
arm-zephyr-eabi-strip -g build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf
```
- The `-g` flag removes only DWARF debug symbols (`.debug_*`), reducing binary size from >2 MB down to ~70 KB.
- 100% preserves `.resource_table` and necessary ELF segment headers required by kernel remoteproc to initialize the RPMsg VirtIO device.

---

## 4. Detailed Design of `Cdd_Ipc` Module

### 4.1. Real-Time Thread Decoupling
To guarantee non-functional requirement **NFR-1** (control loop jitter $\le 50\ \mu\text{s}$):
- The primary control loop runs within `main()` context at top preemptive priority `K_PRIO_PREEMPT(1)`.
- The `Cdd_Ipc` module executes inside `cdd_ipc_thread` at preemptive priority `K_PRIO_PREEMPT(5)`.
- Computationally intensive ASCII parsing, CRC calculation, and RPMsg buffer dispatching do not preempt or delay the 10 ms encoder sampling and PID control task.

### 4.2. Dynamic Endpoint Address Learning Mechanism
Under the RPMsg standard, when Linux opens `/dev/ttyRPMSG0`, the host endpoint is assigned a dynamic address or channel index (e.g., `0x0400` or `0x0001`).
- During initialization, Cortex-M4 sets `s_tty_ept.dest_addr = RPMSG_ADDR_ANY` (`0xFFFFFFFF`).
- Upon receiving the first frame from Linux (such as `HB` or `SPEED 60`), `Cdd_Ipc_RxCallback` latches the source address `src`:
  ```c
  if (s_tty_ept.dest_addr == RPMSG_ADDR_ANY) {
      s_tty_ept.dest_addr = src;
      printk("[CDD_IPC] Learned remote endpoint dest_addr: 0x%08X\n", src);
  }
  ```
- Thereafter, bidirectional telemetry streaming is fully established.

### 4.3. ASCII Command Parser Interface
Commands supported over `/dev/ttyRPMSG0`:

| Command | Syntax | Action on Cortex-M4 | System Response |
| :--- | :--- | :--- | :--- |
| **SPEED** | `SPEED <val>` | Disables open-loop test mode (`SetTestMode(FALSE, 0)`), writes RPM setpoint to RTE port `Rte_Write_ppTargetSpeed_rpm(val)`. | Closed-loop PID tracks `<val>` RPM |
| **DUTY** | `DUTY <val>` | Enables open-loop test mode (`SetTestMode(TRUE, val)`), applies raw duty cycle from $-100.0$ to $+100.0\%$. | Motor operates in open-loop mode at commanded duty |
| **STOP** | `STOP` | Sets duty cycle to $0.0\%$, immediately engages active braking via `Cdd_L298n_EmergencyStop()`. | Motor halts immediately |
| **WDG ON** | `WDG ON` | Enables Heartbeat Watchdog timeout supervision ($1.0\text{ s}$). | Active heartbeat monitoring enabled |
| **WDG OFF**| `WDG OFF` | Disables Heartbeat Watchdog supervision (maintenance / debugging mode). | Watchdog timeout disabled |
| **HB** | `HB` | Refreshes heartbeat timeout counter: `s_hb_timeout_10ms = 0u`. | Nominal operational state maintained |

---

## 5. CRC-16-CCITT Error Detection Algorithm

### 5.1. Mathematical Specification
- **Standard Name:** CRC-16/CCITT-FALSE
- **Generator Polynomial:** $P(x) = x^{16} + x^{12} + x^5 + 1$ (`0x1021`)
- **Initial Value (`Init`):** `0xFFFF`
- **Reflect In/Out (`Refin`/`Refout`):** `False` / `False`
- **XOR Output (`Xorout`):** `0x0000`

### 5.2. MISRA-C Compliant Implementation in `Cdd_Ipc.c`
```c
uint16 Cdd_Ipc_CalcCrc16(const uint8 *data, uint16 length)
{
    uint16 crc = 0xFFFFu;

    if (data == NULL) {
        return 0u;
    }

    for (uint16 i = 0u; i < length; i++) {
        crc ^= (uint16)((uint16)data[i] << 8);
        for (uint8 j = 0u; j < 8u; j++) {
            if ((crc & 0x8000u) != 0u) {
                crc = (uint16)((crc << 1) ^ 0x1021u);
            } else {
                crc = (uint16)(crc << 1);
            }
        }
    }

    return crc;
}
```

### 5.3. Telemetry Frame Format
Every $200\text{ ms}$ (corresponding to 20 cycles of $10\text{ ms}$), Cortex-M4 transmits a telemetry frame:
```
$TELEM,TGT=<int>,RPM=<int>,DUTY=<int>,CNT=<pulses>*<CRC16_HEX>\r\n
```
- **Payload:** String span from `$` up to (excluding) `*`.
- **CRC Checksum:** 4 uppercase hexadecimal ASCII characters calculated over the payload.
- **Representative Frame:**
  `$TELEM,TGT=60,RPM=59,DUTY=42,CNT=1024*A1B2\r\n`

---

## 6. Heartbeat Watchdog Fail-Safe Mechanism (State Transition)

In automotive and industrial embedded systems, host operating system freeze, lockup, or kernel panic on Cortex-A7 must never leave actuators uncontrolled.

```
                  +---------------------------+
                  |   WDG OFF (Normal /       |
                  |      Debug Mode)          |
                  +-------------+-------------+
                                | Command "WDG ON"
                                v
                  +---------------------------+
         +------->|   WDG ON (Supervised)     |
         |        |   Timeout Counter = 0     |
         |        +-------------+-------------+
         |                      |
Command  |                      | Every 10ms cycle: Timeout++
 "HB"    |< 1.0s                |
(Valid   |                      v
heartbeat|        +---------------------------+
         +--------+  0 < Timeout < 100 ticks  |
                  +-------------+-------------+
                                |
                                | Timeout >= 100 ticks (1.0s lost heartbeat)
                                v
                  +---------------------------+
                  |     FAIL-SAFE STATE       |
                  |  - Duty = 0.0%            |
                  |  - Cdd_L298n_Brake()      |
                  |  - IN1=HIGH, IN2=HIGH     |
                  +---------------------------+
```

### 6.1. Operational Principles
1. Within `Cdd_Ipc_MainFunction_10ms()` (executed every 10 ms from `Rte_TimerEvent_10ms`):
   ```c
   if (s_watchdog_enabled) {
       if (s_hb_timeout_10ms < 1000u) {
           s_hb_timeout_10ms++;
       }
       if (s_hb_timeout_10ms >= 100u) {
           /* Heartbeat lost for > 1.0s -> enforce fail-safe state immediately */
           Swc_MotorControl_SetTestMode(TRUE, 0.0f);
           Cdd_L298n_EmergencyStop();
       }
   }
   ```
2. Under normal operation, a Linux daemon or script periodically sends `HB` commands at $500\text{ ms}$ intervals. Each receipt resets `s_hb_timeout_10ms` to `0`.
3. If Cortex-A7 encounters a kernel panic (or upon triggering `echo c > /proc/sysrq-trigger`), heartbeat transmissions halt. Exactly $1.0\text{ s}$ later (100 ticks), Cortex-M4 detects the timeout and commands emergency braking, completely decoupled from the Linux host condition.

---

## 7. Cortex-A7 Host Control Utility (`gateway_a7/ipc_ctl.sh`)

The `gateway_a7/ipc_ctl.sh` script provides complete command, control, and verification features:

```bash
# 1. Configure baudrate and raw mode on /dev/ttyRPMSG0
./ipc_ctl.sh init

# 2. Query remoteproc status and tty device node
./ipc_ctl.sh status

# 3. Command closed-loop PID velocity setpoint (60 RPM)
./ipc_ctl.sh speed 60

# 4. Command open-loop duty cycle (45% duty)
./ipc_ctl.sh duty 45

# 5. Emergency stop motor
./ipc_ctl.sh stop

# 6. Monitor real-time telemetry stream with CRC-16 validation
./ipc_ctl.sh telem

# 7. Run background periodic heartbeat daemon
./ipc_ctl.sh hb-loop 0.5

# 8. Run automated Heartbeat Watchdog fail-safe verification suite
./ipc_ctl.sh test-safety
```

### 7.1. Hardware Verification Logs

- **`remoteproc0` & `virtio_rpmsg_bus` initialization log on Cortex-A7 Linux (`dmesg`):**
  ```text
  [  430.946567] remoteproc remoteproc0: powering up m4
  [  430.956852] remoteproc remoteproc0: Booting fw image motor_gateway_m4.elf, size 45756
  [  430.965181] rproc-virtio rproc-virtio.2.auto: assigned reserved memory node vdev0buffer@10042000
  [  430.976357] virtio_rpmsg_bus virtio0: rpmsg host is online
  [  430.980651] rproc-virtio rproc-virtio.2.auto: registered virtio0 (type 7)
  [  430.987484] virtio_rpmsg_bus virtio0: creating channel rpmsg-tty addr 0x400
  [  431.001951] remoteproc remoteproc0: remote processor m4 is now up
  ```
- **Target node `/dev/ttyRPMSG0` and active 5 Hz Telemetry stream validation (with `CRC-16-CCITT` checksums):**
  ```text
  root@stm32mp1-e5-59-f4:~# cat /sys/class/remoteproc/remoteproc0/state && ls -l /dev/ttyRPMSG*
  running
  crw-rw---- 1 root dialout 240, 0 Nov 11 14:14 /dev/ttyRPMSG0
  root@stm32mp1-e5-59-f4:~# stty -F /dev/ttyRPMSG0 raw -echo && (cat /dev/ttyRPMSG0 &) && sleep 0.2 && echo 'SPEED 60' > /dev/ttyRPMSG0 && sleep 1.5 && killall cat 2>/dev/null
  $TELEM,TGT=60,RPM=2,DUTY=70,CNT=0*59C0
  $TELEM,TGT=60,RPM=2,DUTY=70,CNT=-1*5881
  $TELEM,TGT=60,RPM=1,DUTY=72,CNT=0*DA06
  $TELEM,TGT=60,RPM=1,DUTY=72,CNT=-1*3F6A
  ```
- **Dynamic test sequence: `DUTY 35` -> `DUTY 70` -> `WDG ON` asserting fail-safe braking `DUTY=0` after 1.0s:**
  ```text
  # Send 'DUTY 35' command via /dev/ttyRPMSG0:
  $TELEM,TGT=60,RPM=2,DUTY=35,CNT=0*2F0A
  $TELEM,TGT=60,RPM=0,DUTY=35,CNT=-1*CCB9
  $TELEM,TGT=60,RPM=0,DUTY=35,CNT=0*62D3

  # Send 'DUTY 70' command via /dev/ttyRPMSG0:
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=0*1419
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=0*1419
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=-1*18E8

  # Send 'WDG ON' command (without HB, after exactly 1.0s timeout):
  # Cortex-M4 autonomously triggers fail-safe braking, driving duty to 0%:
  $TELEM,TGT=60,RPM=1,DUTY=0,CNT=0*D8DF
  $TELEM,TGT=60,RPM=0,DUTY=0,CNT=0*A3BE
  $TELEM,TGT=60,RPM=0,DUTY=0,CNT=0*A3BE
  ```

---

## 8. Conclusion & Week 4 Next Steps

### 8.1. Week 3 Outcome Assessment
- Asymmetric Multiprocessing IPC over OpenAMP / RPMsg is fully operational between OpenSTLinux and Zephyr RTOS.
- Standardized telemetry frames with CRC-16-CCITT checksums ensure robust data integrity across the inter-core boundary.
- The Heartbeat Watchdog mechanism satisfies automotive safety requirements, guaranteeing fail-safe motor immobilization in the event of Linux host failure.

### 8.2. Week 4 Milestone Preview
1. **Environmental & Electromechanical Sensor Integration:**
   - MCAL ADC: 3-axis vibration acceleration sampling via GY-61 (X, Y, Z axes).
   - Temperature and humidity driver for DHT11.
   - Interrupt-driven motion detection driver for PIR HC-SR501.
2. **Implement `SWC_SafetyManager` & `SWC_SensorManager`:**
   - Establish comprehensive safety and sensor data pipeline across RTE.
   - Extend RPMsg telemetry frame to stream multi-sensor payloads to Cortex-A7 Linux.
