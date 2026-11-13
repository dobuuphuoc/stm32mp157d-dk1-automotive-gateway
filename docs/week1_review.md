# Week 1 Technical Report & Engineering Log

**Project:** STM32MP157D-DK1 Automotive Gateway & Motor Controller  
**Architecture:** Asymmetric Multiprocessing (AMP) — Cortex-A7 (OpenSTLinux) + Cortex-M4 (AUTOSAR Classic on Zephyr RTOS)  
**Completion Timeline:** Week 1 & Week 2 Initialization  
**Reference Document:** [requirements_stm32mp157_motor_gateway.md](../requirement/requirements_stm32mp157_motor_gateway.md)

---

## 1. Executive Summary

During Week 1, 100% of target objectives across hardware bring-up, Linux OS deployment on Cortex-A7, Ubuntu 22.04 cross-compilation toolchain, and the AUTOSAR Classic compliant real-time software framework on Cortex-M4 were successfully achieved.

| Week 1 Target Objective | Status | Artifact / Verification Result |
|---|:---:|---|
| **SD Card Flashing & OpenSTLinux Boot** | ✅ **100% Completed** | Utilized [create_sdcard_raw.py](../create_sdcard_raw.py) to flash raw image; development board successfully booted **OpenSTLinux 5.0.17** running **Linux Kernel 6.6.129 SMP PREEMPT** on the dual-core Cortex-A7. |
| **Serial Console & Ethernet Networking** | ✅ **100% Completed** | UART Console port `ttySTM0` operates stably at 115200 bps (connected to workstation via COM5 on Hercules). Ethernet interface `end0` configured with static IP `192.168.0.15`; verified SSH and SCP connectivity with low latency (< 1 ms). |
| **`remoteproc0` Subsystem** | ✅ **100% Completed** | Verified `/sys/class/remoteproc/remoteproc0`, confirming Cortex-A7 Linux is fully operational for power management, firmware loading, and lifecycle monitoring of Cortex-M4. |
| **Cross-Compile Environment (Ubuntu VM)** | ✅ **100% Completed** | Built complete toolchain on Ubuntu 22.04 LTS (VMware): upgraded **Python 3.12** (`~/.venv312`), **CMake 4.4.4**, **Zephyr RTOS v4.5.99** with modules `hal_stm32`, `cmsis`, `open-amp`, `libmetal`, and **Zephyr SDK 1.0.1** (`arm-zephyr-eabi` GCC 14.3.0). |
| **M4 Blinky Proof-of-Concept** | ✅ **100% Completed** | Successfully compiled `blinky.elf` firmware, optimized binary size via `strip` (reduced footprint from **565 KB** to **27 KB**), deployed via SCP, and booted on Cortex-M4. Orange LED6 (LD6) toggles at a 1 s period completely independent of Linux. |
| **M4 AUTOSAR Classic Project Framework** | ✅ **100% Completed** | Structured [`motor_gateway_m4`](../motor_gateway_m4) conforming to AUTOSAR Classic layers: Application Layer ([`Swc_MotorControl`](../motor_gateway_m4/src/asw)), Runtime Environment ([`Rte`](../motor_gateway_m4/src/rte)), MCAL ([`Mcal_Dio`](../motor_gateway_m4/src/bsw/mcal)), Device Tree Overlay ([`stm32mp157c_dk2.overlay`](../motor_gateway_m4/boards/stm32mp157c_dk2.overlay)), and automated 1-click deployment script [deploy.sh](../motor_gateway_m4/deploy.sh). |

---

## 2. Development Workflow & Architecture

The distributed Asymmetric Multiprocessing (AMP) architecture provides an end-to-end toolchain spanning the workstation down to the heterogeneous STM32MP157 SoC:

```mermaid
flowchart TD
    subgraph PC["Workstation / Host PC (Windows 11)"]
        direction TB
        VSC["IDE / Editor / Git Workspace"]
        TER["Hercules / PuTTY (COM5 @ 115200 bps - UART Console A7)"]
        LA["Logic Analyzer Software (Saleae / PulseView)"]
    end

    subgraph VM["Cross-Compile Machine (Ubuntu 22.04 VMware)"]
        direction TB
        ENV["Python 3.12 venv (~/.venv312) + CMake 4.4.4"]
        SDK["Zephyr SDK 1.0.1 (arm-zephyr-eabi-gcc 14.3.0)"]
        SRC["Zephyr Source & motor_gateway_m4"]
        WEST["west build -> zephyr.elf"]
        STRIP["arm-zephyr-eabi-strip -s -> motor_gateway_m4.elf (27 KB)"]
        DEPLOY["deploy.sh Automation Script"]
        
        ENV --> WEST
        SDK --> WEST
        SRC --> WEST
        WEST --> STRIP
        STRIP --> DEPLOY
    end

    subgraph DK1["STM32MP157D-DK1 Board"]
        subgraph A7["Cortex-A7 Core (Dual 800 MHz)"]
            OS["OpenSTLinux 5.0.17 (Kernel 6.6.129 SMP PREEMPT)"]
            NET["Ethernet end0 (IP: 192.168.0.15)"]
            SSH["Dropbear SSH Server (Port 22)"]
            FWDIR["/lib/firmware/motor_gateway_m4.elf"]
            RPROC["Linux remoteproc0 Subsystem\n(/sys/class/remoteproc/remoteproc0)"]
        end

        subgraph M4["Cortex-M4 Core (209 MHz - Real-Time)"]
            RTOS["Zephyr RTOS Kernel (Preemptive Priority 1)"]
            AUTOSAR["AUTOSAR Classic Software Stack\n(ASW: Swc_MotorControl | RTE | MCAL: Dio)"]
            TIMER["Hardware Periodic Timer (Ts = 10 ms)"]
            PE9["PE9 Test Pin (Arduino D6 - Jitter Probe)"]
        end
    end

    VSC -.->|Sync Code| SRC
    DEPLOY ==>|scp -O via LAN 192.168.0.15| FWDIR
    DEPLOY -.->|ssh remoteproc control| RPROC
    RPROC ==>|Provide clock / Reset / Load ELF into SRAM| M4
    TER <==|USB-C ST-LINK VCP| OS
    PE9 ==>|Attach logic probe| LA
```

### Component Responsibilities
1. **x86_64 Workstation / Ubuntu VM (Build Environment):**
   - Manages source code repositories and cross-compiles Zephyr RTOS applications for ARM Cortex-M4 (`arm-zephyr-eabi`).
   - Strips ELF binaries via `arm-zephyr-eabi-strip` to eliminate non-essential metadata/debug symbols prior to network transfer.
   - Automates firmware deployment and target control via SSH and SCP over LAN.
2. **Cortex-A7 (High-Performance Linux Host - Vehicle Gateway):**
   - Runs embedded **OpenSTLinux**, providing high-performance multitasking, TCP/IP Ethernet networking (`end0`), and high-level platform services (SSH, Daemons, future MQTT, and Qt GUI).
   - Acts as the Host Master managing the complete lifecycle of the Cortex-M4 core via the standard Linux kernel `remoteproc` subsystem.
   - Serves as the centralized repository for firmware binaries under `/lib/firmware/`.
3. **Cortex-M4 (Deterministic Real-Time Controller):**
   - Executes independently on **Zephyr RTOS** at 209 MHz directly from internal RETRAM/SRAM.
   - Executes hard real-time tasks: $10\text{ ms}$ closed-loop PID control, Hall encoder pulse decoding, H-bridge PWM generation, and fail-safe safety interrupts.
   - Fully immune to latency, jitter, or crash/kernel panic occurrences on the Cortex-A7 Linux host.

---

## 3. Engineering Troubleshooting Log

During Week 1 system bring-up, five critical technical roadblocks were systematically resolved. The table below summarizes the symptoms, root causes, and standard engineering solutions:

| # | Issue / Error Symptom | Root Cause | Standard Engineering Fix |
|---|---|---|---|
| **1** | **SSH Connection timed out** when connecting to IP `10.8.82.33`. | Host workstation was connected via corporate/campus Wi-Fi enforcing AP Isolation and resided on a different subnet than the DK1 board Ethernet port. | Moved VM and DK1 board to a common isolated local switch/subnet; configured static IP **`192.168.0.15`** on board interface `end0`; verified ping round-trip time `< 1 ms`. |
| **2** | **DNS resolution failure & network loss on Ubuntu VM** (`Temporary failure resolving`, `Destination Host Unreachable`). | VMware Workstation virtual network adapter conflicted between Bridged and NAT modes during host Wi-Fi network roaming; `/etc/resolv.conf` lacked public DNS servers. | Set VM network adapter to **NAT** (or physical host bridged adapter); configured static DNS servers `nameserver 8.8.8.8` and `nameserver 1.1.1.1` in `systemd-resolved`. |
| **3** | **VM disk exhaustion** (`No space left on device`) during `west update`. | Default Zephyr manifest pulled dozens of unused chip vendor HALs (NXP, Espressif, Microchip, TI, etc.) and deep multi-gigabyte git histories. | Optimized fetch using `--narrow` and shallow depth: <br>`west update --narrow -o=--depth=1`<br>Retained only essential modules for STM32MP1: `hal_stm32`, `cmsis`, `open-amp`, `libmetal`, and `picolibc`. |
| **4** | **Toolchain version incompatibility** during Zephyr SDK 1.0.1 installation: default CMake was 3.22.1 (< 3.28.0) and default Python was 3.10 (< 3.12). | Zephyr RTOS (v4.5.99) and SDK 1.0.1 require newer toolchain standards than packages provided in standard Ubuntu 22.04 LTS apt repositories. | Added PPA `ppa:deadsnakes/ppa` to install **Python 3.12**, isolated the environment using virtualenv (`python3.12 -m venv ~/.venv312`), and upgraded **CMake** to version **4.4.4** and **west** via `pip`. |
| **5** | **SCP transfer failure** (`subsystem request for sftp failed`, `Connection closed`). | OpenSTLinux distribution uses lightweight **Dropbear SSH**, which does not bundle SFTP server subsystems expected by modern OpenSSH 9+ clients by default. | Appended flag **`-O`** to `scp` command (`scp -O ...`) to enforce the standard **Legacy SCP Protocol**, ensuring 100% Dropbear compatibility. Integrated into [deploy.sh](../motor_gateway_m4/deploy.sh). |

---

## 4. Command Quick Reference

Standard operating commands for daily engineering workflow:

### 4.1 Build Environment (Ubuntu 22.04 VM)
```bash
# 1. Activate Python 3.12 venv and export Zephyr SDK environment variables
source ~/.venv312/bin/activate
export ZEPHYR_SDK_INSTALL_DIR=$HOME/zephyr-sdk-1.0.1

# 2. Navigate to M4 project directory
cd ~/stm32mp157d-dk1/motor_gateway_m4

# 3. Compile and deploy firmware automatically to target via a single command:
./deploy.sh 192.168.0.15
```

### 4.2 Manual Build & Strip Steps (Ubuntu VM)
```bash
# Compile Zephyr with Device Tree Overlay for PE9, PE10, and PH6
west build -b stm32mp157c_dk2 . -p auto -- -DDTC_OVERLAY_FILE=boards/stm32mp157c_dk2.overlay

# Strip binary (reducing size from 565 KB to 27 KB)
~/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-strip -s build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf

# Transfer to Cortex-A7 Linux via Legacy SCP protocol
scp -O ~/motor_gateway_m4.elf root@192.168.0.15:/lib/firmware/motor_gateway_m4.elf
```

### 4.3 Cortex-M4 Lifecycle Management via Linux Console (Cortex-A7)
```bash
# Query current Cortex-M4 status (running or offline)
cat /sys/class/remoteproc/remoteproc0/state

# Stop Cortex-M4 execution
echo stop > /sys/class/remoteproc/remoteproc0/state

# Set target firmware image in /lib/firmware/
echo motor_gateway_m4.elf > /sys/class/remoteproc/remoteproc0/firmware

# Start Cortex-M4 execution
echo start > /sys/class/remoteproc/remoteproc0/state

# View kernel ring buffer log
dmesg | tail -n 20
```

### 4.4 Serial Fallback Deployment (ST-LINK `/dev/ttyACM0` Without LAN)
When RJ45 Ethernet is unavailable, connect the USB ST-LINK interface to the virtual machine (**VM $\rightarrow$ Removable Devices $\rightarrow$ STMicroelectronics STM32 STLink $\rightarrow$ Connect**) and run:
```bash
# Automatically build, strip, and stream directly over /dev/ttyACM0 serial (Base64 + Gzip ~6KB):
./deploy.sh serial
```

---

## 5. M4 AUTOSAR Classic Project Structure & Jitter Measurement Setup

Cortex-M4 firmware is organized according to **AUTOSAR Classic** architectural layering under [`motor_gateway_m4/`](../motor_gateway_m4):

```
motor_gateway_m4/
├── CMakeLists.txt                  <- Zephyr CMake build script linking ASW, RTE, and BSW source directories
├── prj.conf                        <- Zephyr Kconfig: Preemption, GPIO, hardware FPU, and Timers
├── deploy.sh                       <- Automated deployment script: West build -> Strip ELF -> SCP -> Remoteproc restart
├── boards/
│   └── stm32mp157c_dk2.overlay     <- Device Tree Overlay: Node bindings for PE9 (test pin), PE10 (IN1), and PH6 (IN2)
└── src/
    ├── main.c                      <- System entry point, EcuM_Init(), periodic 10ms task (k_timer + k_sem)
    ├── std_types.h                 <- AUTOSAR standard platform types (uint8, float32, Std_ReturnType, E_OK, etc.)
    ├── asw/                        <- Application Layer (100% hardware-independent ASW)
    │   ├── Swc_MotorControl.h      <- Interface definition for Runnable_MotorControl_10ms()
    │   └── Swc_MotorControl.c      <- Closed-loop PID velocity control and open-loop step test algorithms
    ├── rte/                        <- Runtime Environment (RTE)
    │   ├── Rte.h                   <- Sender-Receiver Ports: Rte_Read_rpSpeed_rpm(), Rte_Write_ppDuty_percentage()
    │   └── Rte.c                   <- Concurrency-safe global buffers and runnable dispatcher
    └── bsw/                        <- Basic Software Layer (BSW)
        └── mcal/                   <- Microcontroller Abstraction Layer (MCAL)
            ├── Mcal_Dio.h          <- Channel definitions for DIO_CH_TEST_PE9, DIO_CH_L298N_IN1, DIO_CH_L298N_IN2
            └── Mcal_Dio.c          <- Direct STM32MP1 GPIO manipulation via Zephyr GPIO driver APIs
```

### Periodic Jitter Measurement via Logic Analyzer for $T_s = 10\text{ ms}$ (FR-M10 & NFR-1)

To validate real-time determinism and low latency on Cortex-M4 running Zephyr RTOS per requirement **NFR-1** ($T_s = 10\text{ ms}$, $\text{Jitter} \le 50\ \mu\text{s}$), `Rte_TimerEvent_10ms()` in [`Rte.c`](../motor_gateway_m4/src/rte/Rte.c) invokes [`Dio_FlipChannel(DIO_CH_TEST_PE9)`](../motor_gateway_m4/src/bsw/mcal/Mcal_Dio.c) as its first instruction on every control period:

```c
void Rte_TimerEvent_10ms(void)
{
    /* Toggle test pin PE9 for hardware jitter measurement on logic analyzer */
    (void)Dio_FlipChannel(DIO_CH_TEST_PE9);

    /* Dispatch motor control runnable */
    Runnable_MotorControl_10ms();
}
```

#### Logic Analyzer Wiring Diagram
The USB Logic Analyzer (Saleae Logic / 24M 8CH) connects to the Arduino header on the STM32MP157D-DK1 board as follows:

| Logic Analyzer Lead | DK1 Board Pin | Header Identifier | Signal Function | Voltage Safety Notes |
|---|---|---|---|---|
| **Channel 0 (CH0 / CH1)** | **Pin PE9** | **CN14 - Pin 6 (Arduino D6)** | Test toggle square wave ($f = 50\text{ Hz}$, $T = 20\text{ ms}$, $10\text{ ms}$ half-period) | **3.3V CMOS** logic level |
| **GND Probe** | **GND Pin** | **CN16 - Pin 6 or CN16 - Pin 7** | Common reference ground | Must be connected prior to signal leads |

> [!IMPORTANT]
> **Jitter Measurement Protocol:**
> 1. Configure logic analyzer sample rate to $\ge 10\text{ MHz}$ (temporal resolution $\le 0.1\ \mu\text{s}$).
> 2. Measure edge-to-edge transition intervals. Ideal nominal half-period pulse width is $10.000\text{ ms}$.
> 3. Period timing deviation $\Delta t = |t_{\text{measured}} - 10\text{ ms}|$ recorded across $\ge 10,000$ samples must satisfy:
>    $$\text{Jitter}_{\max} \le 50\ \mu\text{s}$$

---

## 6. Week 2 Action Plan & Deliverables Checklist

Entering Week 2, the primary focus centers on bringing all actuators and sensors (JGA25-370-46.8K geared DC motor, L298N driver, dual-channel Hall encoder) under full Cortex-M4 real-time control:

- [ ] **Quantify & Measure PE9 Jitter:**
  - Connect Logic Analyzer probes to **PE9 (CN14 Pin 6)** and **GND (CN16 Pin 6)**.
  - Capture waveform traces and log statistical jitter distributions (Mean, Max, Min, Standard Deviation $\sigma$) to `docs/figures/`.
- [ ] **Implement `Mcal_Pwm` and `Cdd_L298n` Modules:**
  - Configure hardware timer **TIM4_CH3 (Pin PD14 - Arduino D3)** for **$20\text{ kHz}$** PWM driving the L298N ENA input.
  - Integrate directional control pins IN1 (**PE10 - Arduino D4**) and IN2 (**PH6 - Arduino D9**); implement active braking (IN1=HIGH, IN2=HIGH).
- [ ] **Implement `Mcal_Icu` / Quadrature Encoder Decoding:**
  - Configure hardware timer **TIM3** in 4x Quadrature Encoder Mode: Channel A on **PC6 (CN2 Pin 13)**, Channel B on **PC7 (CN2 Pin 15)**.
  - Implement output shaft velocity calculation formula:
    $$\omega\ [\text{RPM}] = \frac{\Delta\text{Count}}{\text{CPR}_{\text{output}} \times T_s} \times 60 = \frac{\Delta\text{Count}}{2059.2 \times 0.010} \times 60$$
- [ ] **Update Cortex-A7 Linux Device Tree:**
  - Compile Linux Device Tree Overlay to disable peripheral nodes `tim3` and `tim4` under Linux on Cortex-A7, guaranteeing exclusive hardware register ownership for Cortex-M4 without resource contention.

---
*Document authored and reviewed by the STM32MP157D-DK1 Automotive Gateway Engineering Team.*
