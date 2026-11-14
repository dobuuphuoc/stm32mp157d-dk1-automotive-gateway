# Requirements Specification: Automotive Gateway & Motor Controller (OpenSTLinux on A7 + AUTOSAR Classic Architecture on M4)

**Board:** STM32MP157D-DK1 | **Document Version:** 0.6 (Comprehensive Standardization: AUTOSAR Classic Layered Architecture on M4, OpenSTLinux Gateway on A7, Qt Dashboard, MATLAB Tools, Logic Analyzer, JGA25-370-46.8K Motor) | **Date:** 05/11/2026

---

## 1. Objectives

Construct a hybrid distributed embedded system modeling modern automotive domain/zone controller architecture (Automotive Domain/Zone Controller):
- **Cortex-M4 (Real-Time Control ECU - AUTOSAR Classic Compliant):** Acts as a **Chassis/Body ECU**, running closed-loop velocity PID control algorithms, encoder decoding, sensor monitoring, and hardware/RTOS-level safety handling. The software is designed and implemented in strict compliance with the **AUTOSAR Classic Standard Layered Architecture (ASW $\rightarrow$ RTE $\rightarrow$ BSW/MCAL/CDD)** on top of the Zephyr RTOS platform.
- **Cortex-A7 (Vehicle Gateway / Telematics - OpenSTLinux):** Acts as a **Vehicle Gateway / High-Performance Computer**, managing Ethernet networking, SQLite database for telemetry logging, MQTT broker/client, and providing a real-time monitoring Dashboard using **Qt**.
- **Inter-Core Communication (Inter-Core IPC):** Connected via **OpenAMP / RPMsg**, representing the intra-vehicle communication network (Vehicle Network Bus / lightweight SOME/IP equivalent).

**Demonstrated Project Values:**
1. Successful adoption of modern automotive standardization principles: Completely decoupling application control logic (**SWC**) from underlying hardware via **RTE** and **BSW** abstraction layers.
2. Real-time control loops and safety mechanisms execute autonomously on M4, remaining entirely independent of and unaffected by Linux operating system scheduling latencies on A7.
3. Detailed measurement and quantification of M4 PID control loop Jitter using a **Logic Analyzer**.

---

## 2. Scope

| In Scope | Out of Scope |
|---|---|
| Design M4 software architecture conforming to **AUTOSAR Classic** (Application SWCs, RTE, BSW, MCAL, CDD) | Purchasing commercial stacks (Vector MICROSAR, EB tresos) & generating code from proprietary `.arxml` files |
| Utilize **OpenSTLinux pre-built BSP** on Cortex-A7 (SD boot, SSH, Ethernet networking) | Building custom Yocto BSP from scratch |
| Device Tree Overlay for Linux (disable peripherals handed over to M4) | Custom PCB design |
| Binary RPMsg protocol with CRC-16 integrity verification | Wi-Fi connectivity (DK1 kit uses wired LAN cable) |
| Dashboard visualization and parameter configuration developed in **Qt** | Formal certified ISO 26262 functional safety compliance audit |
| System identification using **System Identification Toolbox (MATLAB)** | Firmware Over-The-Air updates (FOTA) |
| PID design and validation using **Control System Toolbox (MATLAB)** | AC motor control |
| Jitter and reaction latency measurement using **Logic Analyzer** | |

---

## 3. Hardware & Technical Specifications

### 3.1 Devices & Components
- Development board: **STM32MP157D-DK1** (Dual Cortex-A7 @ 800MHz + Cortex-M4 @ 209MHz).
- Power supply: USB Type-C 5V/3A (for board) and 12VDC/2A Adapter (for motor via L298N driver).
- Motor: **DC Geared Motor JGA25-370-46.8K (12V - 130RPM)** with integrated 2-channel A/B magnetic Hall Encoder.
- Power driver: **L298N H-Bridge Module** (PWM speed control + direction reversal and active braking).
- Auxiliary sensors:
  - Vibration acceleration sensor: GY-61 (ADXL335 - 3-axis Analog).
  - Environmental sensor: DHT11 (temperature & humidity - Single Wire Digital).
  - Presence sensor: HC-SR501 (PIR Motion Sensor - Digital Interrupt).
- Measurement & debugging equipment:
  - **Logic Analyzer** (USB 8/16CH measuring GPIO toggle jitter and encoder pulses).
  - USB-UART CP2102 converter (dedicated UART console for Cortex-M4).
  - microSD card 16GB SanDisk Class 10.

---

### 3.2 JGA25-370-46.8K Motor Specifications (Standard Datasheet)

| Parameter | Value | Unit | Technical Notes |
|---|---|---|---|
| **Part Number** | **JGA25-370-46.8K** | - | Identified by 130 RPM no-load speed |
| **Rated Voltage** | **12** | V | Supplied from 12V adapter via L298N |
| **Gear Ratio (K)** | **46.8 : 1** | - | 25mm all-metal spur gearbox |
| **Rotating Speed (No-load)** | **130 ± 10%** | RPM | Measured on gearbox output shaft |
| **No-load Current** | **0.07** | A | |
| **Rated Speed** | **100 ± 10%** | RPM | At rated load operating point |
| **Rated Current** | **0.3** | A | |
| **Rated Torque** | **0.9** | kg·cm | $\approx 0.088\text{ N}\cdot\text{m}$ |
| **Stall Torque** | **4.4** | kg·cm | $\approx 0.431\text{ N}\cdot\text{m}$ |
| **Stall Current** | **1.8** | A | Maximum locked-rotor current |
| **Gearbox Size** | **21** | mm | Total mass $\approx 88\text{ g}$ |

#### Integrated Hall Encoder Specifications:
- **Magnetic disc attached to rotor shaft (before gearbox):** **11 PPR** (pulses/phase/rotor revolution).
- **Quadrature x4 decoding mode (TIM3 QDEC):** $11 \times 4 = 44\text{ counts/rotor revolution}$.
- **Output shaft resolution:**
  $$\text{PPR}_{\text{output}} = 11 \times 46.8 = 514.8\text{ pulses/revolution}$$
  $$\text{CPR}_{\text{output (4x)}} = 44 \times 46.8 = 2059.2\text{ counts/revolution}$$
- **Encoder signal logic level:** Supplied with **3.3V** from DK1 board, 3.3V output signals directly compatible with STM32MP1 GPIOs.

---

## 4. Cortex-M4 Software Architecture Conforming to AUTOSAR Classic

The entire software architecture on Cortex-M4 is decoupled into 3 independent layers: **Application Layer (ASW)**, **Runtime Environment (RTE)**, and **Basic Software (BSW)**.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          APPLICATION LAYER (ASW)                                 │
│  ┌───────────────────────┐  ┌─────────────────────────┐  ┌────────────────────┐  │
│  │   SWC_MotorControl    │  │    SWC_SensorManager    │  │  SWC_SafetyManager │  │
│  │ ───────────────────── │  │ ─────────────────────── │  │ ────────────────── │  │
│  │ - PID Algorithm       │  │ - Read GY-61 (3-ch ADC) │  │ - Fault Detection  │  │
│  │ - Open-loop Step Test │  │ - Read DHT11 (Temp/Hum) │  │ - Safe State / Stop│  │
│  │ - Setpoint Tracking   │  │ - Read PIR (Motion)     │  │ - Heartbeat Monitor│  │
│  └───────────▲───────────┘  └────────────▲────────────┘  └─────────▲──────────┘  │
│              │ Ports (S/R, C/S)          │ Ports (S/R)             │ Ports (S/R) │
├──────────────┴───────────────────────────┴─────────────────────────┴─────────────┤
│                       RUNTIME ENVIRONMENT (RTE)                                  │
│  - Dispatch Runnable Entities based on timing events (Rte_TimerEvent_10ms,...)   │
│  - Data exchange APIs between SWCs and between SWCs and BSW                      │
│  - Rte_Read_*, Rte_Write_*, Rte_Call_*                                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│                         BASIC SOFTWARE LAYER (BSW)                               │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Services Layer:                                                            │  │
│  │  - OS (Zephyr RTOS Kernel wrapper: Task 10ms, Task 100ms, ISR handling)    │  │
│  │  - EcuM (ECU State Management: STARTUP, RUN, SHUTDOWN)                     │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ ECU Abstraction Layer (ECUAL):                                             │  │
│  │  - IoHwAb (I/O pin abstraction, ADC voltage to g-acceleration conversion)  │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ Complex Device Drivers (CDD):                                              │  │
│  │  - CDD_RPMsg (OpenAMP RPMsg inter-core communication with Cortex-A7 Linux) │  │
│  │  - CDD_L298N (H-Bridge handling: IN1/IN2 direction and dynamic braking)    │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ Microcontroller Abstraction Layer (MCAL):                                  │  │
│  │  - Dio (Digital I/O)      - Pwm (Pulse Width Modulation - TIM4)            │  │
│  │  - Icu / Qdec (TIM3 QDEC) - Adc (Analog-to-Digital Converter)              │  │
│  │  - Gpt (General Purpose Timer - System Tick / Timing)                      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Detailed Software Components (Application Layer)

1. **`SWC_MotorControl`:**
   - Completely decoupled from hardware.
   - Contains **Runnable_MotorControl_10ms**: Executes periodically at $T_s = 10\text{ ms}$. Reads current velocity from Port via `Rte_Read_rpSpeed_rpm()`, computes error $e[k]$, executes discrete difference PID equation (with Anti-windup), and outputs Duty to Port `Rte_Write_ppDuty_percentage()`.
   - **Open-loop Step Mode**: Provides step excitation of duty cycle to acquire system identification data for MATLAB.

2. **`SWC_SensorManager`:**
   - Contains **Runnable_ReadAnalogSensors_50ms**: Reads 3 ADC channels from GY-61, computes composite vibration acceleration vector.
   - Contains **Runnable_ReadEnvSensors_2s**: Triggers temperature and humidity acquisition from DHT11.
   - Writes sensor telemetry to Sender-Receiver Ports exposed to RTE.

3. **`SWC_SafetyManager`:**
   - Contains **Runnable_SafetyCheck_10ms**: Receives PIR status, vibration limits, and heartbeat from RTE.
   - If anomalous vibration, active PIR motion during operation, or heartbeat loss exceeding $1.0\text{ s}$ occurs, this SWC immediately asserts the emergency flag `Rte_Write_ppEmergencyStop(TRUE)`.

---

## 5. Detailed Functional Requirements

### 5.1 Cortex-M4 (AUTOSAR Classic)

| ID | Module / SWC | Functional Requirement | Priority |
|---|---|---|:---:|
| **FR-M1** | `MCAL_Icu` / `IoHwAb` | Read encoder via TIM3 Quadrature Decoder hardware mode at $10\text{ ms}$ interval, accurately calculate output shaft RPM. | **M** |
| **FR-M2** | `MCAL_Pwm` / `CDD_L298N` | Generate 20 kHz PWM (TIM4_CH3, PD14) driving ENA; control logic pins IN1/IN2 (PE10, PH6) for directional rotation and active braking. | **M** |
| **FR-M3** | `SWC_MotorControl` | Discrete PID algorithm at $10\text{ ms}$ period, `float` data type (leveraging Cortex-M4 hardware FPU), with saturation limit $0 \div 100\%$ and Anti-windup Clamping. Formula strictly adheres to MATLAB exported model. | **M** |
| **FR-M4** | `SWC_SensorManager` | Sample 3 ADC channels reading GY-61, compute composite vibration acceleration amplitude vector. | **S** |
| **FR-M5** | `SWC_SensorManager` | Acquire temperature and humidity from DHT11 every $\ge 2\text{ s}$. | **S** |
| **FR-M6** | `SWC_SafetyManager` | Capture interrupt from HC-SR501 on pin PE13, assert presence detection alert. | **S** |
| **FR-M7** | `SWC_SafetyManager` | Trigger emergency stop (Duty = 0%, IN1=1, IN2=1) upon fault detection. 100% autonomous, requiring zero A7 intervention. | **M** |
| **FR-M8** | `CDD_RPMsg` / `RTE` | Packetize and transmit Telemetry frames (RPM, Duty, Vibration, Temp/Humidity, Status) to A7; decode command frames from A7 (Setpoint, PID parameters, Run/Stop commands). | **M** |
| **FR-M9** | `SWC_MotorControl` | Open-loop Step Response operating mode, transmitting sample series $(t, u, \omega)$ to save CSV for MATLAB. | **M** |
| **FR-M10**| `MCAL_Dio` | Toggle state on Test Pin (PE9) at the start of each $10\text{ ms}$ PID cycle to measure **Jitter** via Logic Analyzer. | **M** |

---

### 5.2 Cortex-A7 (OpenSTLinux Gateway)

| ID | Functional Requirement | Technical Details | Priority |
|---|---|---|:---:|
| **FR-A1** | M4 Lifecycle Management | Automatically load Zephyr firmware binary (`.elf`) into Cortex-M4 during Linux system boot via `remoteproc` subsystem. | **M** |
| **FR-A2** | IPC Communication Daemon | Daemon written in C/C++ reading/writing via `/dev/rpmsg_ctrl*` / `/dev/rpmsg*` character devices, verifying CRC16 checksum. | **M** |
| **FR-A3** | SQLite Storage | Persist operational history, telemetry, and emergency stop logs into local SQLite database on SD card. | **S** |
| **FR-A4** | MQTT Gateway Bridge | Package telemetry into JSON payloads published to MQTT broker; receive remote setpoint/PID commands via MQTT topics. | **S** |
| **FR-A5** | **Dashboard GUI (Qt)** | Graphical GUI application developed in Qt: display live speed vs Setpoint plots, sensor states, Start/Stop buttons, speed control slider, and interactive tuning interface for $K_p, K_i, K_d$ parameters. | **M** |
| **FR-A6** | Heartbeat Watchdog | Periodically send ping frames ($500\text{ ms}$) to M4 signaling healthy Linux operation. | **M** |
| **FR-A7** | MATLAB Log Collection | Export system identification logs to `.csv` format (`timestamp, duty, rpm`) for direct import into MATLAB workspace. | **M** |

---

## 6. Control Workflow & Discrete PID Design (MATLAB)

```
[M4: Step Test (Step Duty Excitation)] 
             │
             ▼
    [CSV Data: (t, u, y)] 
             │
             ▼
[System Identification Toolbox] ──> Transfer Function G(s) = K / (τs + 1) * e^(-θs)
             │
             ▼
 [Control System Toolbox]       ──> Discretization c2d(G(s), Ts, 'zoh')
                                    PID Tuning via pidtune / PID Tuner
             │
             ▼
[Kp, Ki, Kd & Difference Eq]    ──> Implement in SWC_MotorControl & Qt Dashboard
```

1. **Data Acquisition:** M4 operates in `SWC_MotorControl` open-loop mode, exciting sequential Duty steps (40% $\rightarrow$ 60% $\rightarrow$ 80%). A7 records `step_response.csv` ($T_s = 10\text{ ms}$).
2. **Model Identification (System Identification Toolbox):**
   - Import dataset using `iddata(rpm, duty, 0.01)` object.
   - Remove offset and compensate for L298N dead zone voltage (diode forward drop $\approx 2\text{V}$) using `detrend`.
   - Estimate first-order plus dead time (FOPDT) transfer function using `tfest(data, 1, 0, 'IODelay', NaN)`.
   - Validate model fit percentage via `compare(data, sys)`.
3. **Design & Discretization (Control System Toolbox):**
   - Discretize continuous model to z-domain using Zero-Order Hold: `sys_d = c2d(sys, Ts, 'zoh')`.
   - Tune parameters using `pidtune(sys, 'PI')` or the interactive **PID Tuner** GUI.
   - Ensure Phase Margin $\text{PM} \ge 60^\circ$, $\text{Overshoot} < 10\%$, and settling time $t_s < 300\text{ ms}$.
   - Select numerical integration method: Backward Euler or Trapezoidal (Tustin).
4. **Implementation in M4 Software Component:**
   - Program discrete difference equation directly in `SWC_MotorControl` following the selected MATLAB numerical format:
     $$u[k] = K_p e[k] + K_i T_s \sum_{j=0}^{k} e[j] + K_d \frac{e[k] - e[k-1]}{T_s}$$
   - Add output saturation limiting logic ($0 \div 100\%$) combined with Clamping Anti-windup algorithm.
5. **Empirical Verification:**
   - Execute closed-loop step response on physical hardware, plotting real-time tracking curves to compare MATLAB simulation against actual measurements on Qt Dashboard.

---

## 7. Non-Functional Requirements (NFR)

| ID | Metric / Requirement | Target Threshold | Verification Method |
|---|---|---|---|
| **NFR-1** | PID Loop Execution Period | $T_s = 10\text{ ms}$, Jitter $\le 50\ \mu\text{s}$ | **Logic Analyzer** probing GPIO Test Pin (PE9) on M4 |
| **NFR-2** | Safety Reaction Time | $< 5\text{ ms}$ from trigger event occurrence | Measure elapsed time between PIR/shock trigger edge and PWM = 0 on Logic Analyzer |
| **NFR-3** | RPMsg Round-trip Latency | Statistical report of average / maximum | Calculate round-trip timestamps A7 $\rightarrow$ M4 $\rightarrow$ A7 |
| **NFR-4** | Crash Independence | Linux kernel panic does not compromise M4 | Intentionally trigger `echo c > /proc/sysrq-trigger` and verify motor stability |
| **NFR-5** | Control Tracking Accuracy | Steady-state error $e_{ss} \le 2\text{ RPM}$, Overshoot $< 10\%$ | Evaluate step response data recorded via Qt Dashboard |
| **NFR-6** | I/O Voltage Safety | Logic voltage levels must never exceed $3.3\text{V}$ | Verify using Digital Multimeter / Logic Analyzer prior to connecting kit |

---

## 8. STM32MP157D-DK1 Pin Allocation Table

| Function | MCU Pin | Header Location | M4 Software Layer | Notes & Linux Device Tree |
|---|---|---|---|---|
| **M4 Console UART** | PE8 / PE7 | Arduino Header D1 / D0 | `MCAL_Uart` | Dedicated M4 debug UART (115200 bps) |
| **Motor PWM (ENA)** | PD14 | Arduino Header D3 | `MCAL_Pwm` | TIM4_CH3 (Disable TIM4 in Linux DT) |
| **Direction IN1 (L298N)** | PE10 | Arduino Header D4 | `CDD_L298N` / `MCAL_Dio` | GPIO Output |
| **Direction IN2 (L298N)** | PH6 | Arduino Header D9 | `CDD_L298N` / `MCAL_Dio` | GPIO Output |
| **Encoder Phase A** | PC6 | Header CN2 Pin 13 | `MCAL_Icu` / `QDEC` | TIM3_CH1 (Disable TIM3 in Linux DT) |
| **Encoder Phase B** | PC7 | Header CN2 Pin 15 | `MCAL_Icu` / `QDEC` | TIM3_CH2 (Disable USART6 in Linux DT) |
| **Test Pin (Jitter Profiling)** | PE9 | Arduino Header D6 | `MCAL_Dio` | Connected to Logic Analyzer CH1 |
| **GY-61 (X, Y, Z axes)** | PF14, PF13, PF12 | Analog Header A2, A3, A5 | `MCAL_Adc` | Disable corresponding ADCs in Linux DT |
| **DHT11 Data** | PE12 | Arduino Header D13 | `IoHwAb` / `MCAL_Dio` | Disable SPI4 in Linux DT |
| **HC-SR501 PIR Out** | PE13 | Arduino Header D12 | `MCAL_Dio` (Ext Interrupt) | Capture external rising edge interrupt |

---

## 9. Power Supply & Grounding Scheme

```
[Adapter 12V DC] ──┬── (+) 12V ───────> [L298N VMS (Power In)]
                  └── (–) GND ──┬────> [L298N GND]
                                │
[DK1 Board 5V/3A] ──── GND ─────┴────> [Common Signal GND]
```

- **Fundamental Rule:** Common ground (GND) must be tied between 12V Adapter, L298N Driver, and STM32MP157D-DK1.
- **Never connect the 5V terminal of the L298N module to the DK1 board** (risk of overvoltage damaging onboard PMIC power supply circuitry).
- Power supply for Hall Encoder circuit: Drawn from the **3.3V** pin of the DK1 board to ensure return A/B pulse logic strictly conforms to 3.3V levels.

---

## 10. Implementation Roadmap (11–13 Weeks)

```
Week 1:    Setup OpenSTLinux, configure SSH/Ethernet network, verify hardware with Logic Analyzer
Week 2:    Bring up Zephyr RTOS on Cortex-M4, implement MCAL layer (Dio, Pwm, Icu/Qdec, Adc)
Week 3:    Develop CDD_RPMsg layer and establish OpenAMP/RPMsg inter-core IPC with Linux A7
Week 4:    Design AUTOSAR architectural framework: Implement RTE and SWC_MotorControl skeleton
Week 5:    Collect open-loop step response data via A7 and export to CSV files
Week 6:    System identification in MATLAB (System Identification) & Digital PID design (Control System Toolbox)
Week 7:    Implement discrete PID algorithm into SWC_MotorControl, verify saturation & Anti-windup
Week 8:    Develop SWC_SensorManager (GY-61, DHT11) and SWC_SafetyManager (PIR, emergency stop)
Week 9:    Develop Linux IPC Daemon, SQLite logging, and MQTT Gateway on Cortex-A7
Week 10:   Build real-time Dashboard interface using Qt on Cortex-A7
Week 11:   Quantitatively measure PID loop Jitter via Logic Analyzer, measure emergency stop latency
Week 12-13: Comprehensive testing, performance evaluation, verify independence during Linux crash, finalize report
```

---

## 11. Technical Status & Issue Tracking Table

| # | Item | Status | Technical Resolution |
|---|---|---|---|
| 1 | **Cortex-M4 Software Architecture** | ✅ **Finalized** | Layered **AUTOSAR Classic (ASW $\rightarrow$ RTE $\rightarrow$ BSW/MCAL/CDD)** architecture on Zephyr RTOS. |
| 2 | **Cortex-A7 Operating System** | ✅ **Finalized** | Utilize **OpenSTLinux Pre-built image**, completely eliminating custom Yocto build from scratch. |
| 3 | **Dashboard Interface** | ✅ **Finalized** | Developed in **Qt** (C++). |
| 4 | **Jitter Measurement Equipment** | ✅ **Available** | Employ **Logic Analyzer** connected to GPIO Test Pin (PE9). |
| 5 | **Control Design Tools** | ✅ **Licensed** | **MATLAB + System Identification Toolbox + Control System Toolbox**. |
| 6 | **Motor Specifications** | ✅ **Confirmed** | **JGA25-370-46.8K** (Gear ratio **46.8:1**, No-load speed 130 RPM @ 12V). |
| 7 | **Encoder Resolution** | ✅ **Confirmed** | Magnetic disc **11 PPR** ($514.8\text{ PPR}$ output shaft, $2059.2\text{ CPR}$ in 4x mode). |
| 8 | **Empirical Safety Thresholds** | ✅ **3.5g (Verified via Mcal_Adc & ASW Unit Tests)** | Determine GY-61 vibration thresholds ($\ge 3.5g$) and heartbeat timeout ($1.0\text{ s}$). |
