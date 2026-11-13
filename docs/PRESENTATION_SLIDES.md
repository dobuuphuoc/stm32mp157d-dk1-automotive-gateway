---
marp: true
theme: default
paginate: true
header: "Automotive Domain Gateway & Real-Time Motor Controller (STM32MP157)"
footer: "Graduation Capstone Project / Automotive Systems Embedded Engineer"
---

# GRADUATION CAPSTONE PROJECT DEFENSE

## AUTOMOTIVE DOMAIN GATEWAY & AUTOSAR CLASSIC-COMPLIANT REAL-TIME MOTOR CONTROLLER ON STM32MP157 HETEROGENEOUS MULTI-CORE PROCESSING PLATFORM

---
**Presented by:** Embedded Systems Engineer  
**Experimental Platform:** STM32MP157D-DK1 (Dual ARM Cortex-A7 @ 800MHz + ARM Cortex-M4 @ 209MHz)  
**Operating Systems:** Zephyr RTOS v4.5.99 & OpenSTLinux 5.0.17  
**Industry Standards:** AUTOSAR Classic Architecture, ISO 26262 Functional Safety  

---

<!-- Speaker Notes:
Distinguished members of the Evaluation Committee, today I would like to present my capstone thesis: Research and Development of an Automotive Domain Gateway and AUTOSAR Classic-Compliant Real-Time Motor Controller on the STM32MP157 Heterogeneous Multi-Core Processing Platform.
-->

---

# 1. PROBLEM STATEMENT: AUTOMOTIVE TECHNOLOGY CONTEXT

### Electrical/Electronic (E/E) Architecture Transition

* **Traditional Distributed Architecture (Distributed ECUs):**
  - Modern vehicles incorporate over $100 \div 150$ discrete Electronic Control Units (ECUs).
  - Kilometers of intricate CAN/LIN wiring harnesses resulting in elevated costs and vehicle weight.
  - Substantial difficulties in lifecycle maintenance, diagnostics, and software updates.

* **Modern Centralized Architecture (Domain / Zonal Architecture):**
  - Consolidates related functional clusters into a centralized processor (**Automotive Domain Gateway**).
  - Reduces wiring harness mass by up to 40%, optimizing manufacturing costs.
  - Establishes the foundation for Advanced Driver Assistance Systems (ADAS) and smart Electric Vehicles (EVs).

---

# 2. CRITICAL CHALLENGES IN SYSTEM INTEGRATION

### The Conflict Between Opposing Computing Domains

| Technical Metric | Chassis Control Domain (Chassis ECU) | Telematics & Infotainment Domain |
| :--- | :--- | :--- |
| **Timing Constraints** | **Hard Real-Time:** Microsecond-level latency, strict $10\text{ ms}$ control loop. | **Soft Real-Time / Best-Effort:** Tolerant to latencies of tens of milliseconds. |
| **Operating System** | Dedicated RTOS (**Zephyr RTOS**) or **AUTOSAR Classic**. | Feature-rich operating system (**Embedded Linux**). |
| **Reliability** | Deterministic, **Zero Crash**, safety-critical. | Complex network services, **susceptible to freezes, RAM exhaustion, and Kernel Panics**. |

> ⚠️ **The Paradox:** Running both workloads on a single monolithic Linux OS poses a catastrophic hazard: an infotainment application freeze or kernel panic can compromise the vehicle's critical steering and braking subsystems!

---

# 3. PROPOSED SOLUTION: STM32MP157 HETEROGENEOUS SOC

### Absolute Hardware Domain Isolation

```
┌────────────────────────────────────────────────────────────────────────┐
│                   STM32MP157D-DK1 HETEROGENEOUS SOC                    │
│                                                                        │
│   ┌────────────────────────────────┐   ┌───────────────────────────┐   │
│   │   CORTEX-A7 GATEWAY DOMAIN     │   │  CORTEX-M4 REAL-TIME ECU  │   │
│   │   (Dual-Core @ 800MHz, Linux)  │   │   (Single-Core @ 209MHz)  │   │
│   │                                │   │                           │   │
│   │   - OpenSTLinux 5.0.17         │   │   - Zephyr RTOS v4.5.99   │   │
│   │   - Linux IPC Daemon           │   │   - AUTOSAR Classic Spec  │   │
│   │   - SQLite3 Blackbox Recorder  │   │   - Motor Closed-Loop PID │   │
│   │   - MQTT Cloud IoT Gateway     │   │   - ISO 26262 E-Stop Lock │   │
│   └───────────────┬────────────────┘   └─────────────▲─────────────┘   │
│                   │                                  │                 │
│                   └──► IPCC Mailbox + RPMsg Shared ◄─┘                 │
└────────────────────────────────────────────────────────────────────────┘
```

* **Cortex-M4:** Executes directly from dedicated internal 384 KB SRAM, completely unaffected even during Linux freezes or kernel panics.
* **Inter-Processor Communication (IPC):** Utilizes OpenAMP RPMsg with **CRC-16-CCITT** integrity validation.

---

# 4. CORTEX-M4 SOFTWARE ARCHITECTURE: AUTOSAR CLASSIC

### 3-Layer Independent Abstraction Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│                   APPLICATION SOFTWARE LAYER (ASW)                     │
│   ┌───────────────────────┐ ┌───────────────────┐ ┌────────────────┐   │
│   │   Swc_MotorControl    │ │ Swc_SensorManager │ │Swc_SafetyManagr│   │
│   │   (PID 10ms Discrete) │ │ (PIR, Accel, DHT) │ │(ISO 26262 Stop)│   │
│   └───────────────────────┘ └───────────────────┘ └────────────────┘   │
├────────────────────────────────────────────────────────────────────────┤
│                       RUNTIME ENVIRONMENT (RTE)                        │
│   - Rte_Read() / Rte_Write() Ports: Complete ASW / Hardware Decoupling │
│   - Rte_TimerEvent_10ms(): Deterministic 100 Hz scheduling (k_timer)   │
├────────────────────────────────────────────────────────────────────────┤
│                       BASIC SOFTWARE (BSW / MCAL / CDD)                │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐   │
│   │ Mcal_Pwm  │ │ Mcal_Icu  │ │ Mcal_Dio  │ │ Cdd_L298n │ │Cdd_Ipc │   │
│   │ (20 kHz)  │ │ (Encoder) │ │ (Test PE9)│ │ (H-Bridge)│ │(RPMsg) │   │
│   └───────────┘ └───────────┘ └───────────┘ └───────────┘ └────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

* **Key Advantage:** Porting to another microcontroller or upgrading sensors keeps **100% of application algorithm source code (ASW) intact** without refactoring.

---

# 5. DATA ACQUISITION & MATLAB SYSTEM IDENTIFICATION

### Rigorous Engineering Methodology Replacing Heuristic "Trial & Error"

* **Step 1: Open-Loop Step Excitation Test:**
  - Cortex-M4 injects a duty cycle step of $0\% \to 60\%$ for $3.0\text{ s}$.
  - Cortex-A7 records velocity transient response to `step_response_60.csv` at sample period $T_s = 10\text{ ms}$.

* **Step 2: FOPDT Transfer Function Identification via MATLAB System Identification Toolbox:**
  - Identified transfer function achieves an experimental **Best Fit** of **80.95%**:

  $$G(s) = \frac{0.1873}{0.0461 s + 1} e^{-0.0400 s}$$

  - Static DC gain: $K = 0.1873\text{ RPM / \%Duty}$
  - Inertial time constant: $\tau = 46.1\text{ ms}$
  - Apparent dead time: $\theta = 40.0\text{ ms}$

---

# 6. DISCRETE PID CONTROLLER DESIGN & ANTI-WINDUP

* **Optimized Control Parameters from MATLAB Control System Toolbox:**
  $$K_P = 1.9641, \quad K_I = 85.0402, \quad K_D = 0.0000, \quad T_s = 10\text{ ms}$$

* **Discrete Difference Equations Implemented in `Swc_MotorControl.c`:**
  - Velocity tracking error: $e[k] = \text{Target}[k] - \text{Actual}[k]$
  - Proportional term: $P[k] = K_P \cdot e[k]$
  - Integral term: $I[k] = I[k-1] + K_I \cdot T_s \cdot e[k]$
  - Control effort: $u[k] = P[k] + I[k]$

* **Anti-Windup Clamping Mechanism:**
  - Under heavy load conditions or when actuator reaches duty ceiling $\text{Duty}_{\text{max}} = 85.0\%$:
  - Immediately freezes the integral accumulator $I[k]$, completely eliminating velocity overshoot and mechanical hunting.

---

# 7. 3-PILLAR ACTIVE SAFETY SYSTEM (ISO 26262)

### Multi-Layer Defensive Architecture Eliminating Hazard Conditions

```
             ┌──────────────────────────────────────────────┐
             │         SWC_SAFETYMANAGER (ISO 26262)        │
             └──────────────────────┬───────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  PILLAR 1: PIR   │       │ PILLAR 2: GY-61  │       │  PILLAR 3: WDG   │
│ Frontal Obstacle │       │Crash & Rollover  │       │ Linux Heartbeat  │
│ 120° Scan Angle  │       │ |a| > 2.5g-3.5g  │       │  Timeout > 1.0s  │
└────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    ▼
                 ┌──────────────────────────────────────┐
                 │ Cdd_L298n_EmergencyStop(): Inhibit   │
                 │ Suppress drive pulse to 0V in <0.05ms│
                 └──────────────────────────────────────┘
```

---

# 8. LINUX GATEWAY TIER (A7) & VIRTUAL COCKPIT INTERFACE (QT)

* **Linux Gateway Daemon (`gateway_daemon.py`):**
  - Manages `/dev/ttyRPMSG0` at $115200\text{ bps}$, verifying **CRC-16-CCITT** checksums.
  - Automatically maintains **Heartbeat (500ms)** to service the M4 software watchdog.
  - SQLite3 database with **WAL (Write-Ahead Logging)** mode: Blackbox recorder providing permanent crash logging for `$FAULT`.
  - MQTT IoT gateway publishing real-time telematics to the cloud.

* **Qt Digital Virtual Cockpit:**
  - Dual analog gauges sweeping smoothly at **$40\text{ FPS}$** (Speedometer & Power Gauge).
  - Top-down vehicle chassis view paired with **infrared radar proximity visualization**.
  - 3-axis G-Meter visualizing vehicle acceleration and vibration transients.
  - Real-time $100\text{ Hz}$ closed-loop velocity tracking graph, ISO 2575 standard automotive telltales.

---

# 9. NFR-1 VERIFICATION: 10ms LOOP EXECUTION JITTER

### Physical Measurement via Saleae Logic 2 on Test Pin `PE9` (Arduino `D6`)

* **Nominal Design Period:** $T_{\text{nominal}} = \mathbf{10.000000\text{ ms}}$
* **Measured Half-Period:** $T_{\text{measured}} = \mathbf{10.006375\text{ ms}}$

$$\text{Hardware Jitter } \Delta T = |10.006375\text{ ms} - 10.000000\text{ ms}| = \mathbf{6.375\ \mu\text{s}}$$

* **Full Cycle Period (Rising + Falling):** $20.01275\text{ ms}$ (Frequency $49.986\text{ Hz}$, error $-0.028\%$).
* **Pulse Duty Cycle:** Perfect $50.0\%$.

> 🏆 **NFR-1 EVALUATION:**
> * Specification requirement: Jitter $\le 50.0\ \mu\text{s}$.
> * Empirical result: $\Delta T = \mathbf{6.375\ \mu\text{s}}$ $\to$ **EXCEEDS SPECIFICATION BY 7.84x** (Margin of $87.25\%$). Confirms absolute hard real-time determinism of Zephyr RTOS!

---

# 10. NFR-2 VERIFICATION: EMERGENCY STOP REACTION TIME

### Brake Latency Measurement upon PIR Obstacle Detection

* **1. Hardware PWM Verification (`PD14` - `TIM4_CH3`):**
  - Carrier frequency: Exactly **$20.000\text{ kHz}$** ($T_{\text{PWM}} = 50.0\ \mu\text{s}$).
  - Pulse active high time: $t_{\text{high}} = 42.5\ \mu\text{s} \implies \text{Duty} = \mathbf{85.0\%}$ (Matches $100\%$ with Anti-Windup clamp).

* **2. PWM Suppression Latency:**
  - PIR sensor rising edge asserts hazard at $t = 1.9011\text{ s}$.
  - At subsequent control tick ($t = 1.9178\text{ s}$), PWM output is immediately suppressed to flat $0\text{V}$:

  $$t_{\text{actuator\_cut}} < \mathbf{0.05\text{ ms}} \quad (\text{NFR-2 Specification: } < 5\text{ ms})$$

  - Total end-to-end response time from sensor trip to actuator cutoff is **$16.7\text{ ms}$**.

> 🏆 **NFR-2 EVALUATION: EXCEEDS REQUIREMENT**

---

# 11. NFR-3 VERIFICATION: RPMSG IPC ROUND-TRIP LATENCY

### Automated 100-Packet Round-Trip Benchmark A7 $\leftrightarrow$ M4 via `/dev/ttyRPMSG0`

```
==========================================================
   RPMSG IPC ROUND-TRIP LATENCY BENCHMARK (NFR-3)
==========================================================
   Valid Responses:      100/100 (100.0%)  -> 0% packet drop
   Average RTT (t_avg):  1.999 ms          -> Target: < 5.0 ms
   Minimum RTT (t_min):  1.727 ms
   Maximum RTT (t_max):  2.640 ms
   Jitter StdDev (σ):    0.129 ms          -> High determinism
==========================================================
   Evaluation: EXCELLENT (t_avg < 5.0 ms, High Real-Time)
==========================================================
```

* **Significance:** The full round trip from Linux User-space $\to$ Vring Kernel $\to$ IPCC Mailbox IRQ $\to$ Cortex-M4 ISR/Task $\to$ Linux response completes in just **$1.999\text{ ms}$**!

> 🏆 **NFR-3 EVALUATION: EXCEEDS REQUIREMENT**

---

# 12. NFR-4 VERIFICATION: INDEPENDENCE DURING LINUX CRASH

### Validating Survival of the Cortex-M4 Real-Time Partition

* **Empirical Stress Test Scenario:**
  1. Motor rotating in steady state at $10\text{ RPM}$.
  2. Forcibly terminate Dashboard process (`Ctrl + C` / SIGKILL) simulating total Linux userspace crash / freeze.
  3. Observe response of Cortex-M4 core and actuator hardware.

* **Empirical Findings:**
  * Telematics link and HMI display are completely disrupted.
  * **Cortex-M4 continues running the closed-loop motor PID at $10\text{ ms}$ uninterrupted with zero hesitation.**
  * When waving hand in front of the PIR sensor, **Cortex-M4 immediately executes autonomous emergency stop**!

> 🏆 **NFR-4 EVALUATION: FULLY COMPLIANT (Absolute Real-Time Domain Isolation).**

---

# 13. NFR-5 VERIFICATION: PID CONTROL TRACKING ACCURACY

### Closed-Loop Velocity Tracking Performance at 100 Hz

* **Steady-State Error:**
  $$e_{ss} = |\text{Target} - \text{Actual}| = \mathbf{0.00\text{ RPM}}$$
  *(NFR-5 Specification: $e_{ss} \le 2.0\text{ RPM}$).*

* **Overshoot:** $\mathbf{0\%}$ (Smooth velocity ramping without overshoot).

* **Settling Time ($t_s$):** $\approx 1.2\text{ s}$.

* **Communication Integrity:** $3,318 / 3,318$ telemetry frames verified by CRC-16 ($100.0\%$, zero corrupted frames).

> 🏆 **NFR-5 EVALUATION: 100% COMPLIANT**

---

# 14. COMPREHENSIVE ACCEPTANCE MATRIX (MASTER SCORECARD)

| Group | Standard / Metric | Specification Target | Experimental Hardware Result | Evaluation |
| :---: | :---: | :--- | :--- | :---: |
| **NFR** | **NFR-1** | PID period $10\text{ ms}$, Jitter $\le 50\ \mu\text{s}$ | $\Delta T = \mathbf{6.375\ \mu\text{s}}$ (Saleae Logic 2 on PE9) | **EXCEEDS BY 7.8x** |
| **NFR** | **NFR-2** | E-Stop cut latency $< 5\text{ ms}$ | $t_{\text{cut}} < \mathbf{0.05\text{ ms}}$ at cut cycle, $16.7\text{ ms}$ total | **EXCELLENT** |
| **NFR** | **NFR-3** | RPMsg IPC RTT latency A7 $\leftrightarrow$ M4 | $t_{\text{avg}} = \mathbf{1.999\text{ ms}}$, $\sigma = 0.129\text{ ms}$ ($100/100$) | **EXCELLENT** |
| **NFR** | **NFR-4** | Independence during Linux/HMI crash | M4 maintains autonomous PID & executes local PIR E-Stop | **PASS (100%)** |
| **NFR** | **NFR-5** | Closed-loop PID velocity accuracy | $e_{ss} = \mathbf{0.00\text{ RPM}}$, zero overshoot ($0\%$) | **PASS (100%)** |
| **NFR** | **NFR-6** | I/O safe operating voltage $\le 3.3\text{V}$ | $100\%$ channels adhere to safe $3.3\text{V}$ logic thresholds | **PASS (100%)** |
| **FR-M** | **FR-M1 $\to$ M10** | Zephyr RTOS, AUTOSAR Classic, PWM 20kHz, Encoder, PID, PIR, GY-61, DHT11, RPMsg, PE9 | Synchronous, robust, full ASW/BSW separation | **100% COMPLETE** |
| **FR-A** | **FR-A1 $\to$ A5** | OpenSTLinux, Linux Daemon, SQLite3 WAL, MQTT Gateway, Qt Digital Cockpit | Telematics ingestion, crash blackbox, 40 FPS cockpit | **100% COMPLETE** |

---

# 15. HARDWARE DEMONSTRATION & VERIFICATION VIDEO

### Experimental Demonstration on STM32MP157D-DK1 Platform

* **Video File Link (Local):** [**video_demo/demo.mp4**](video_demo/demo.mp4) *(Full HD 1080p, ~29.6 MB)*
* **Online Mirror (Google Drive):** [**Google Drive Video Link**](https://drive.google.com/file/d/17d-vMCIrHitZAmdeHGaxqPASsOAnrs6g/view)
* **4 Key Demonstration Scenarios:**
  1. **System Boot & Firmware Bring-Up (IPC Bring-Up):** Cortex-A7 boots Linux, loads Cortex-M4 firmware via `remoteproc0`, establishes RPMsg channel with Virtual Cockpit UI.
  2. **10ms Closed-Loop PID Velocity Tracking (NFR-5):** Electronic PRND shifter engages `D (PID)`, setpoints stepped to 8, 10, 12 RPM, speedometer sweeps smoothly at $40\text{ FPS}$, steady-state error $e_{ss} = 0.00\text{ RPM}$.
  3. **PIR Emergency Stop Interlock (NFR-2):** Hand placed in front of vehicle $\to$ Radar turns red, PWM drive immediately suppressed ($< 50\ \mu\text{s}$).
  4. **Fail-Safe Independence under Linux Crash (NFR-4):** Dashboard abruptly terminated, motor continues closed-loop regulation and successfully executes safety stop upon obstacle detection.

---

# 16. CONCLUSION & TECHNICAL CONTRIBUTIONS

### 4 Key Technical Contributions:
1. **Mastery of Heterogeneous Multi-Core SoC (STM32MP157):** Successfully solved the co-existence challenge between safety-critical hard real-time control and high-level telematics applications.
2. **Implementation of AUTOSAR Classic Architecture:** Realized strict layered abstraction on **Zephyr RTOS**, maximizing code modularity and software reusability across automotive hardware platforms.
3. **Model-Based Control System Design:** Applied empirical system identification on **MATLAB** achieving $80.95\%$ fit, eliminating steady-state velocity tracking error to $0.00\text{ RPM}$.
4. **Rigorous Physical Measurement & Validation:** Quantified loop jitter ($6.375\ \mu\text{s}$), brake latency ($< 0.05\text{ ms}$), and IPC latency ($1.999\text{ ms}$) using industrial Logic Analyzers.

---

# 17. FUTURE WORK & ROADMAP

* **Automotive Physical Bus Expansion:**
  - Integrate **CAN FD** and **Automotive Ethernet (100BASE-T1)** for modern ADAS and sensor fusion interoperability.

* **Advanced Motor Control Algorithms:**
  - Implement Field-Oriented Control (**FOC**) for 3-phase Permanent Magnet Synchronous Motors (PMSM / BLDC) for EV traction drives.

* **Secure Over-The-Air (OTA) Updates:**
  - Build cryptographically signed remote firmware update mechanisms for Cortex-M4 real-time firmware via Linux Gateway.

---

# THANK YOU FOR YOUR ATTENTION!

### QUESTIONS & ANSWERS (Q&A)

*I look forward to receiving feedback and answering questions from the Evaluation Committee!*
