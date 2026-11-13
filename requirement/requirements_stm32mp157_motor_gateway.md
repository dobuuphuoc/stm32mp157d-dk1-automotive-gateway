# Requirement Gathering: Automotive Gateway & Motor Controller (OpenSTLinux trên A7 + AUTOSAR Classic Architecture trên M4)

**Board:** STM32MP157D-DK1 | **Phiên bản tài liệu:** 0.6 (Chuẩn hóa toàn diện: Kiến trúc phân tầng AUTOSAR Classic trên M4, OpenSTLinux Gateway trên A7, Qt Dashboard, MATLAB Tools, Logic Analyzer, Động cơ JGA25-370-46.8K) | **Ngày:** 05/11/2026

---

## 1. Mục tiêu

Xây dựng hệ thống nhúng lai phân tán mô phỏng kiến trúc điều khiển xe ô tô hiện đại (Automotive Domain/Zone Controller):
- **Cortex-M4 (ECU Điều khiển thời gian thực - Chuẩn AUTOSAR Classic):** Đóng vai trò là một **Chassis/Body ECU**, chạy thuật toán điều khiển PID vận tốc vòng kín, giải mã encoder, giám sát cảm biến và xử lý an toàn mức phần cứng/RTOS. Phần mềm được thiết kế và triển khai tuân thủ **Kiến trúc phân tầng chuẩn AUTOSAR Classic (ASW $\rightarrow$ RTE $\rightarrow$ BSW/MCAL/CDD)** trên nền tảng Zephyr RTOS.
- **Cortex-A7 (Vehicle Gateway / Telematics - OpenSTLinux):** Đóng vai trò là bộ tính toán hiệu năng cao (**Vehicle Gateway / High-Performance Computer**), quản lý mạng Ethernet, CSDL SQLite lưu lịch sử telemetry, broker/client MQTT và cung cấp giao diện Dashboard giám sát thời gian thực bằng **Qt**.
- **Giao tiếp liên nhân (Inter-Core IPC):** Kết nối qua cơ chế **OpenAMP / RPMsg**, tương đương với vai trò mạng truyền thông nội bộ xe (Vehicle Network Bus / SOME/IP rút gọn).

**Giá trị chứng minh của đồ án:**
1. Áp dụng thành công tư duy chuẩn hóa của ngành công nghiệp ô tô: Phân tách hoàn toàn logic ứng dụng điều khiển (**SWC**) khỏi phần cứng bên dưới thông qua tầng trừu tượng **RTE** và **BSW**.
2. Vòng điều khiển thời gian thực và cơ chế an toàn chạy độc lập trên M4, không phụ thuộc và không bị ảnh hưởng bởi độ trễ điều phối của hệ điều hành Linux trên A7.
3. Đo kiểm và định lượng chi tiết Jitter của chu kỳ điều khiển PID trên M4 bằng **Logic Analyzer**.

---

## 2. Phạm vi

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| Thiết kế kiến trúc phần mềm M4 tuân thủ **AUTOSAR Classic** (Application SWCs, RTE, BSW, MCAL, CDD) | Mua stack thương mại (Vector MICROSAR, EB tresos) & sinh mã từ file `.arxml` bản quyền |
| Sử dụng **OpenSTLinux pre-built BSP** trên Cortex-A7 (boot SD, SSH, Ethernet networking) | Tự build Yocto BSP từ đầu |
| Device Tree Overlay cho Linux (disable các peripheral đã bàn giao cho M4) | Thiết kế PCB riêng |
| Giao thức RPMsg nhị phân có kiểm tra tính toàn vẹn CRC16 | Kết nối Wi-Fi (kit DK1 dùng cáp LAN) |
| Dashboard hiển thị và cấu hình tham số viết bằng **Qt** | Tiêu chuẩn an toàn chức năng chứng chỉ ISO 26262 chính thức |
| Nhận dạng hệ thống bằng **System Identification Toolbox (MATLAB)** | Cập nhật firmware qua mạng (FOTA) |
| Thiết kế và kiểm chứng PID bằng **Control System Toolbox (MATLAB)** | Điều khiển động cơ xoay chiều AC |
| Đo đạc Jitter và độ trễ phản ứng bằng **Logic Analyzer** | |

---

## 3. Phần cứng & Thông số kỹ thuật

### 3.1 Thiết bị & Linh kiện
- Kit phát triển: **STM32MP157D-DK1** (Dual Cortex-A7 @ 800MHz + Cortex-M4 @ 209MHz).
- Nguồn cấp: USB Type-C 5V/3A (cho board) và Adapter 12VDC/2A (cho động cơ qua driver L298N).
- Động cơ: **DC Geared Motor JGA25-370-46.8K (12V - 130RPM)** tích hợp đĩa từ Hall Encoder 2 kênh A/B.
- Driver công suất: **L298N H-Bridge Module** (điều khiển PWM + đảo chiều quay và phanh).
- Cảm biến phụ trợ:
  - Cảm biến gia tốc rung: GY-61 (ADXL335 - 3 trục Analog).
  - Cảm biến môi trường: DHT11 (nhiệt độ & độ ẩm - Single Wire Digital).
  - Cảm biến hiện diện: HC-SR501 (PIR Motion Sensor - Digital Interrupt).
- Thiết bị đo lường & debug:
  - **Logic Analyzer** (USB 8/16CH đo jitter chân GPIO toggle và xung encoder).
  - Mạch chuyển đổi USB-UART CP2102 (kết nối UART console riêng cho Cortex-M4).
  - Thẻ nhớ microSD 16GB SanDisk Class 10.

---

### 3.2 Bảng thông số động cơ JGA25-370-46.8K (Datasheet chuẩn)

| Thông số | Giá trị | Đơn vị | Ghi chú kỹ thuật |
|---|---|---|---|
| **Mã hiệu (Part Number)** | **JGA25-370-46.8K** | - | Nhận dạng theo tốc độ không tải 130 RPM |
| **Điện áp định mức (Rated Voltage)** | **12** | V | Cấp từ adapter 12V qua L298N |
| **Tỷ số truyền (Gear Ratio - K)** | **46.8 : 1** | - | Hộp số bánh răng kim loại 25mm |
| **Tốc độ không tải (Rotating Speed)** | **130 ± 10%** | RPM | Đo trên trục ra hộp số |
| **Dòng không tải (No-load Current)** | **0.07** | A | |
| **Tốc độ định mức (Rated Speed)** | **100 ± 10%** | RPM | Tại điểm tải định mức |
| **Dòng định mức (Rated Current)** | **0.3** | A | |
| **Mô-men xoắn định mức (Rated Torque)** | **0.9** | kg·cm | $\approx 0.088\text{ N}\cdot\text{m}$ |
| **Mô-men xoắn giữ/hãm (Stall Torque)** | **4.4** | kg·cm | $\approx 0.431\text{ N}\cdot\text{m}$ |
| **Dòng giữ/hãm (Stall Current)** | **1.8** | A | Dòng kẹt trục cực đại |
| **Chiều dài hộp số (Gearbox Size)** | **21** | mm | Khối lượng tổng $\approx 88\text{ g}$ |

#### Thông số Encoder Hall tích hợp:
- **Đĩa từ gắn trục rotor (trước hộp số):** **11 PPR** (xung/pha/vòng rotor).
- **Chế độ đọc Quadrature x4 (TIM3 QDEC):** $11 \times 4 = 44\text{ counts/vòng rotor}$.
- **Độ phân giải trên trục ra (Output Shaft):**
  $$\text{PPR}_{\text{output}} = 11 \times 46.8 = 514.8\text{ pulses/vòng}$$
  $$\text{CPR}_{\text{output (4x)}} = 44 \times 46.8 = 2059.2\text{ counts/vòng}$$
- **Mức logic tín hiệu encoder:** Nguồn cấp **3.3V** từ kit DK1, tín hiệu ra 3.3V tương thích trực tiếp STM32MP1 GPIO.

---

## 4. Kiến trúc phần mềm Cortex-M4 theo chuẩn AUTOSAR Classic

Toàn bộ phần mềm trên Cortex-M4 được chia làm 3 tầng độc lập: **Application Layer (ASW)**, **Runtime Environment (RTE)** và **Basic Software (BSW)**.

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
│  - Điều phối Runnable Entities theo sự kiện thời gian (Rte_TimerEvent_10ms,...)   │
│  - API truyền nhận dữ liệu giữa các SWC và giữa SWC với BSW                       │
│  - Rte_Read_*, Rte_Write_*, Rte_Call_*                                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│                         BASIC SOFTWARE LAYER (BSW)                               │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Services Layer:                                                            │  │
│  │  - OS (Zephyr RTOS Kernel wrapper: Task 10ms, Task 100ms, ISR handling)    │  │
│  │  - EcuM (ECU State Management: STARTUP, RUN, SHUTDOWN)                     │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ ECU Abstraction Layer (ECUAL):                                             │  │
│  │  - IoHwAb (Trừu tượng hóa chân I/O, chuyển đổi ADC volt sang gia tốc g)    │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ Complex Device Drivers (CDD):                                              │  │
│  │  - CDD_RPMsg (Giao tiếp OpenAMP RPMsg với Cortex-A7 Linux)                 │  │
│  │  - CDD_L298N (Xử lý cầu H: chiều quay IN1/IN2 và phanh ngắn mạch)         │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │ Microcontroller Abstraction Layer (MCAL):                                  │  │
│  │  - Dio (Digital I/O)      - Pwm (Pulse Width Modulation - TIM4)            │  │
│  │  - Icu / Qdec (TIM3 QDEC) - Adc (Analog-to-Digital Converter)              │  │
│  │  - Gpt (General Purpose Timer - System Tick / Timing)                      │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Chi tiết các Software Components (Application Layer)

1. **`SWC_MotorControl`:**
   - Hoàn toàn độc lập với phần cứng.
   - Chứa **Runnable_MotorControl_10ms**: Chạy chu kỳ $T_s = 10\text{ ms}$. Đọc vận tốc hiện tại từ Port qua hàm `Rte_Read_rpSpeed_rpm()`, tính toán sai số $e[k]$, thực thi phương trình sai phân PID rời rạc (có Anti-windup), xuất Duty ra Port `Rte_Write_ppDuty_percentage()`.
   - Chế độ **Open-loop Step Mode**: Kích thích nhảy cấp duty để lấy dữ liệu nhận dạng MATLAB.

2. **`SWC_SensorManager`:**
   - Chứa **Runnable_ReadAnalogSensors_50ms**: Đọc ADC 3 trục từ GY-61, tính vector gia tốc rung động tổng hợp.
   - Chứa **Runnable_ReadEnvSensors_2s**: Kích hoạt đọc nhiệt độ/độ ẩm từ DHT11.
   - Ghi dữ liệu cảm biến ra các Sender-Receiver Ports để cung cấp cho RTE.

3. **`SWC_SafetyManager`:**
   - Chứa **Runnable_SafetyCheck_10ms**: Nhận trạng thái PIR, ngưỡng rung và heartbeat từ RTE.
   - Nếu phát hiện rung bất thường, chuyển động PIR khi đang chạy, hoặc mất heartbeat quá $1.0\text{ s}$, SWC này sẽ gửi cờ báo khẩn cấp `Rte_Write_ppEmergencyStop(TRUE)`.

---

## 5. Yêu cầu chức năng chi tiết

### 5.1 Phía Cortex-M4 (AUTOSAR Classic)

| ID | Module / SWC | Yêu cầu chức năng | Mức |
|---|---|---|:---:|
| **FR-M1** | `MCAL_Icu` / `IoHwAb` | Đọc encoder qua chế độ phần cứng TIM3 Quadrature Decoder, chu kỳ $10\text{ ms}$, tính chính xác RPM trục ra. | **M** |
| **FR-M2** | `MCAL_Pwm` / `CDD_L298N` | Tạo xung PWM 20 kHz (TIM4_CH3, PD14) điều khiển ENA; điều khiển logic chân IN1/IN2 (PE10, PH6) để đảo chiều hoặc phanh chủ động. | **M** |
| **FR-M3** | `SWC_MotorControl` | Thuật toán PID rời rạc chu kỳ $10\text{ ms}$, kiểu dữ liệu `float` (tận dụng phần cứng FPU Cortex-M4), có giới hạn bão hòa $0 \div 100\%$ và cơ chế chống bão hòa tích phân (Anti-windup Clamping). Công thức bám sát mô hình xuất từ MATLAB. | **M** |
| **FR-M4** | `SWC_SensorManager` | Lấy mẫu 3 kênh ADC đọc GY-61, tính vector biên độ gia tốc rung động. | **S** |
| **FR-M5** | `SWC_SensorManager` | Thu thập nhiệt độ và độ ẩm từ DHT11 mỗi $\ge 2\text{ s}$. | **S** |
| **FR-M6** | `SWC_SafetyManager` | Bắt ngắt từ HC-SR501 trên chân PE13, cảnh báo hiện diện. | **S** |
| **FR-M7** | `SWC_SafetyManager` | Kích hoạt phanh khẩn cấp (Duty = 0%, IN1=1, IN2=1) khi có sự cố. Tự trị 100%, không cần A7 can thiệp. | **M** |
| **FR-M8** | `CDD_RPMsg` / `RTE` | Đóng gói và gửi khung tin Telemetry (RPM, Duty, Rung, Nhiệt/Ẩm, Trạng thái) lên A7; giải mã khung tin lệnh từ A7 (Setpoint, thông số PID, lệnh chạy/dừng). | **M** |
| **FR-M9** | `SWC_MotorControl` | Chế độ chạy chu trình mở vòng (Open-loop Step Response), gửi chuỗi mẫu $(t, u, \omega)$ để lưu CSV phục vụ MATLAB. | **M** |
| **FR-M10**| `MCAL_Dio` | Đảo trạng thái (toggle) chân Test Pin (PE9) tại thời điểm bắt đầu mỗi chu kỳ PID $10\text{ ms}$ để đo **Jitter** bằng Logic Analyzer. | **M** |

---

### 5.2 Phía Cortex-A7 (OpenSTLinux Gateway)

| ID | Yêu cầu chức năng | Chi tiết kỹ thuật | Mức |
|---|---|---|:---:|
| **FR-A1** | Quản lý vòng đời M4 | Tự động nạp file firmware Zephyr (`.elf`) vào Cortex-M4 khi hệ thống Linux khởi động qua subsystem `remoteproc`. | **M** |
| **FR-A2** | IPC Communication Daemon | Daemon viết bằng C/C++ đọc/ghi qua thiết bị `/dev/rpmsg_ctrl*` / `/dev/rpmsg*`, kiểm tra mã kiểm soát lỗi CRC16. | **M** |
| **FR-A3** | Lưu trữ SQLite | Lưu lịch sử vận hành, telemetry và nhật ký sự kiện dừng khẩn cấp vào CSDL SQLite cục bộ trên thẻ SD. | **S** |
| **FR-A4** | Cầu nối MQTT | Đóng gói telemetry thành bản tin JSON gửi lên MQTT broker; nhận lệnh điều khiển setpoint/PID từ xa qua MQTT topic. | **S** |
| **FR-A5** | **Giao diện Dashboard (Qt)** | Ứng dụng GUI viết bằng Qt: hiển thị biểu đồ tốc độ thực tế vs Setpoint, trạng thái cảm biến, nút Start/Stop, slider điều khiển tốc độ và giao diện tinh chỉnh trực tiếp tham số $K_p, K_i, K_d$. | **M** |
| **FR-A6** | Giữ nhịp Heartbeat | Định kỳ gửi gói tin ping ($500\text{ ms}$) xuống M4 để báo hiệu Linux đang hoạt động bình thường. | **M** |
| **FR-A7** | Thu thập Log cho MATLAB | Xuất dữ liệu nhận dạng hệ thống ra file định dạng `.csv` (`timestamp, duty, rpm`) để nạp trực tiếp vào workspace của MATLAB. | **M** |

---

## 6. Quy trình điều khiển & Thiết kế PID rời rạc (MATLAB)

```
[M4: Step Test (Duty nhảy cấp)] 
             │
             ▼
   [CSV Data: (t, u, y)] 
             │
             ▼
[System Identification Toolbox] ──> Hàm truyền G(s) = K / (τs + 1) * e^(-θs)
             │
             ▼
 [Control System Toolbox]      ──> Rời rạc hóa c2d(G(s), Ts, 'zoh')
                                   Thiết kế PID bằng pidtune / PID Tuner
             │
             ▼
[Tham số Kp, Ki, Kd & Công thức số] ──> Cài đặt vào SWC_MotorControl & Qt Dashboard
```

1. **Thu thập dữ liệu:** M4 chạy chế độ mở vòng `SWC_MotorControl`, kích thích chuỗi bước nhảy Duty (40% $\rightarrow$ 60% $\rightarrow$ 80%). A7 ghi file `step_response.csv` ($T_s = 10\text{ ms}$).
2. **Nhận dạng mô hình (System Identification Toolbox):**
   - Import dữ liệu bằng đối tượng `iddata(rpm, duty, 0.01)`.
   - Khử offset và bù vùng chết điện áp của L298N (sụt áp diode $\approx 2\text{V}$) bằng `detrend`.
   - Ước lượng hàm truyền bậc 1 có trễ bằng `tfest(data, 1, 0, 'IODelay', NaN)`.
   - Kiểm tra độ tương thích mô hình bằng `compare(data, sys)`.
3. **Thiết kế & Rời rạc hóa (Control System Toolbox):**
   - Rời rạc hóa mô hình liên tục về miền z bằng phương pháp Zero-Order Hold: `sys_d = c2d(sys, Ts, 'zoh')`.
   - Tinh chỉnh tham số bằng `pidtune(sys, 'PI')` hoặc công cụ **PID Tuner** đồ họa.
   - Đảm bảo dự trữ pha $\text{PM} \ge 60^\circ$, độ vọt lố $\text{Overshoot} < 10\%$, thời gian xác lập $t_s < 300\text{ ms}$.
   - Lựa chọn phương pháp tích phân số: Backward Euler hoặc Trapezoidal (Tustin).
4. **Cài đặt vào Software Component M4:**
   - Lập trình phương trình sai phân trực tiếp trong `SWC_MotorControl` theo đúng định dạng công thức MATLAB đã chọn:
     $$u[k] = K_p e[k] + K_i T_s \sum_{j=0}^{k} e[j] + K_d \frac{e[k] - e[k-1]}{T_s}$$
   - Bổ sung logic bão hòa ngõ ra ($0 \div 100\%$) kết hợp thuật toán Clamping Anti-windup.
5. **Kiểm chứng thực tế:**
   - Chạy đáp ứng vòng kín thực tế, vẽ đồ thị so sánh giữa mô phỏng MATLAB và thực nghiệm thu nhận được trên Qt Dashboard.

---

## 7. Yêu cầu phi chức năng (Non-Functional Requirements)

| ID | Chỉ số / Yêu cầu | Ngưỡng mục tiêu | Phương pháp kiểm chứng |
|---|---|---|---|
| **NFR-1** | Chu kỳ vòng lặp PID | $T_s = 10\text{ ms}$, Jitter $\le 50\ \mu\text{s}$ | **Logic Analyzer** kẹp chân Test GPIO (PE9) trên M4 |
| **NFR-2** | Thời gian đáp ứng an toàn | $< 5\text{ ms}$ từ khi sự kiện kích hoạt | Đo khoảng thời gian giữa cạnh kích hoạt PIR/rung đến khi PWM = 0 trên Logic Analyzer |
| **NFR-3** | Độ trễ RPMsg Round-trip | Báo cáo thống kê trung bình / cực đại | Tính timestamp khứ hồi A7 $\rightarrow$ M4 $\rightarrow$ A7 |
| **NFR-4** | Tính độc lập khi crash | Linux kernel panic không làm ảnh hưởng M4 | Cố ý kích hoạt `echo c > /proc/sysrq-trigger` và kiểm tra phản ứng của động cơ |
| **NFR-5** | Độ chính xác điều khiển | Sai số xác lập $e_{ss} \le 2\text{ RPM}$, Overshoot $< 10\%$ | Đánh giá qua dữ liệu step response từ Qt Dashboard |
| **NFR-6** | An toàn điện áp I/O | Mức điện áp logic tuyệt đối không vượt quá $3.3\text{V}$ | Kiểm tra bằng đồng hồ VOM/Logic Analyzer trước khi cắm dây vào kit |

---

## 8. Bảng phân bổ chân STM32MP157D-DK1

| Chức năng | Chân MCU | Vị trí Header | Tầng phần mềm M4 | Ghi chú & Device Tree Linux |
|---|---|---|---|---|
| **Console UART M4** | PE8 / PE7 | Header Arduino D1 / D0 | `MCAL_Uart` | UART debug riêng của M4 (115200 bps) |
| **PWM Động cơ (ENA)** | PD14 | Header Arduino D3 | `MCAL_Pwm` | TIM4_CH3 (Disable TIM4 trong Linux DT) |
| **Hướng quay IN1 (L298N)** | PE10 | Header Arduino D4 | `CDD_L298N` / `MCAL_Dio` | GPIO Output |
| **Hướng quay IN2 (L298N)** | PH6 | Header Arduino D9 | `CDD_L298N` / `MCAL_Dio` | GPIO Output |
| **Encoder Pha A** | PC6 | Header CN2 Pin 13 | `MCAL_Icu` / `QDEC` | TIM3_CH1 (Disable TIM3 trong Linux DT) |
| **Encoder Pha B** | PC7 | Header CN2 Pin 15 | `MCAL_Icu` / `QDEC` | TIM3_CH2 (Disable USART6 trong Linux DT) |
| **Test Pin (Đo Jitter)** | PE9 | Header Arduino D6 | `MCAL_Dio` | Nối kênh CH1 Logic Analyzer |
| **GY-61 (Trục X, Y, Z)** | PF14, PF13, PF12 | Header Analog A2, A3, A5 | `MCAL_Adc` | Disable ADC tương ứng trong Linux DT |
| **DHT11 Data** | PE12 | Header Arduino D13 | `IoHwAb` / `MCAL_Dio` | Disable SPI4 trong Linux DT |
| **HC-SR501 PIR Out** | PE13 | Header Arduino D12 | `MCAL_Dio` (Ext Interrupt) | Bắt ngắt ngoài cạnh lên |

---

## 9. Đấu nối nguồn & Tiếp địa

```
[Adapter 12V DC] ──┬── (+) 12V ───────> [L298N VMS (Power In)]
                  └── (–) GND ──┬────> [L298N GND]
                                │
[DK1 Board 5V/3A] ──── GND ─────┴────> [GND chung tín hiệu]
```

- **Quy tắc bất di bất dịch:** Nối chung GND giữa Adapter 12V, Driver L298N và STM32MP157D-DK1.
- **Tuyệt đối không cấp chân 5V của module L298N vào board DK1** (nguy cơ sốc áp hỏng chip nguồn PMIC của kit).
- Nguồn cấp cho mạch Encoder Hall: Lấy từ chân **3.3V** của board DK1 để đảm bảo logic xung A/B trả về đúng chuẩn 3.3V.

---

## 10. Kế hoạch thực hiện (11–13 Tuần)

```
Tuần 1:    Setup OpenSTLinux, cấu hình mạng SSH/Ethernet, đo đạc xác nhận phần cứng bằng Logic Analyzer
Tuần 2:    Bring-up Zephyr RTOS trên Cortex-M4, cài đặt tầng MCAL (Dio, Pwm, Icu/Qdec, Adc)
Tuần 3:    Xây dựng tầng CDD_RPMsg và thiết lập giao tiếp liên nhân OpenAMP/RPMsg với Linux A7
Tuần 4:    Thiết kế khung kiến trúc AUTOSAR: Xây dựng RTE và cấu trúc SWC_MotorControl
Tuần 5:    Thu thập dữ liệu đáp ứng bước nhảy mở vòng (Open-loop Step Test) qua A7 lưu file CSV
Tuần 6:    Nhận dạng hệ thống trên MATLAB (System Identification) & Thiết kế PID số (Control System Toolbox)
Tuần 7:    Cài đặt thuật toán PID rời rạc vào SWC_MotorControl, kiểm chứng bão hòa & Anti-windup
Tuần 8:    Phát triển SWC_SensorManager (GY-61, DHT11) và SWC_SafetyManager (PIR, phanh khẩn cấp)
Tuần 9:    Phát triển Linux IPC Daemon, SQLite logging và MQTT Gateway trên Cortex-A7
Tuần 10:   Xây dựng giao diện Dashboard thời gian thực bằng Qt trên Cortex-A7
Tuần 11:   Đo đạc định lượng Jitter vòng lặp PID bằng Logic Analyzer, đo thời gian dừng khẩn cấp
Tuần 12-13: Thử nghiệm toàn diện, đánh giá hiệu năng, kiểm chứng tính độc lập khi Linux crash, hoàn thiện báo cáo
```

---

## 11. Bảng theo dõi trạng thái các vấn đề kỹ thuật

| # | Hạng mục | Trạng thái | Giải pháp kỹ thuật |
|---|---|---|---|
| 1 | **Kiến trúc phần mềm Cortex-M4** | ✅ **Đã chốt** | Phân tầng chuẩn **AUTOSAR Classic (ASW $\rightarrow$ RTE $\rightarrow$ BSW/MCAL/CDD)** trên nền Zephyr RTOS. |
| 2 | **Hệ điều hành Cortex-A7** | ✅ **Đã chốt** | Sử dụng **OpenSTLinux Pre-built image**, bỏ hoàn toàn việc build Yocto từ đầu. |
| 3 | **Giao diện Dashboard** | ✅ **Đã chốt** | Viết bằng **Qt** (C++). |
| 4 | **Thiết bị đo kiểm Jitter** | ✅ **Đã có** | Dùng **Logic Analyzer** kẹp chân GPIO Test Pin (PE9). |
| 5 | **Công cụ tính toán điều khiển** | ✅ **Đã có license** | **MATLAB + System Identification Toolbox + Control System Toolbox**. |
| 6 | **Thông số động cơ** | ✅ **Đã xác nhận** | **JGA25-370-46.8K** (Tỷ số truyền **46.8:1**, Tốc độ không tải 130 RPM @ 12V). |
| 7 | **Độ phân giải Encoder** | ✅ **Đã xác nhận** | Đĩa từ **11 PPR** ($514.8\text{ PPR}$ trục ra, $2059.2\text{ CPR}$ ở chế độ đọc 4x). |
| 8 | **Ngưỡng an toàn thực nghiệm** | ❓ **Cần thử nghiệm** | Sẽ xác định ngưỡng rung GY-61 và timeout mất heartbeat thực tế tại Tuần 8. |
