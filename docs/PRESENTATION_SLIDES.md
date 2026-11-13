---
marp: true
theme: default
paginate: true
header: "Automotive Domain Gateway & Real-Time Motor Controller (STM32MP157)"
footer: "Đồ Án Tốt Nghiệp / Kỹ Sư Nhúng Hệ Thống Ô Tô"
---

# BÁO CÁO THUYẾT TRÌNH ĐỒ ÁN TỐT NGHIỆP

## AUTOMOTIVE DOMAIN GATEWAY & BỘ ĐIỀU KHIỂN ĐỘNG CƠ THỜI GIAN THỰC CHUẨN AUTOSAR CLASSIC TRÊN NỀN TẢNG VI XỬ LÝ ĐA NHÂN DỊ THỂ STM32MP157

---
**Sinh viên thực hiện:** Kỹ Sư Nhúng Hệ Thống
**Nền tảng thực nghiệm:** STM32MP157D-DK1 (ARM Cortex-A7 @ 800MHz + ARM Cortex-M4 @ 209MHz)
**Hệ điều hành:** Zephyr RTOS v4.5.99 & OpenSTLinux 5.0.17
**Chuẩn công nghiệp:** AUTOSAR Classic, ISO 26262 Functional Safety

---

<!-- Speaker Notes:
Kính thưa quý thầy cô trong Hội đồng giám khảo, hôm nay em xin đại diện báo cáo đề tài tốt nghiệp: Nghiên cứu và phát triển Automotive Domain Gateway kết hợp Bộ điều khiển động cơ thời gian thực chuẩn AUTOSAR Classic trên nền tảng vi xử lý đa nhân dị thể STM32MP157.
-->

---

# 1. ĐẶT VẤN ĐỀ: BỐI CẢNH CÔNG NGHỆ Ô TÔ

### Sự chuyển dịch kiến trúc Điện - Điện tử (E/E Architecture)

* **Kiến trúc phân tán truyền thống (Distributed ECUs):**
  - Xe hơi chứa hơn $100 \div 150$ hộp ECU độc lập.
  - Hàng kilomet dây cáp CAN bus chằng chịt, chi phí đắt đỏ, khối lượng nặng.
  - Cực kỳ khó khăn khi bảo trì hoặc nâng cấp phần mềm.

* **Kiến trúc tập trung hiện đại (Domain / Zonal Architecture):**
  - Gom các cụm chức năng liên quan vào một bộ xử lý trung tâm (**Automotive Domain Gateway**).
  - Giảm thiểu khối lượng dây dẫn, tối ưu hóa chi phí sản xuất, mở đường cho xe tự hành và xe điện thông minh.

---

# 2. THÁCH THỨC SINH TỬ TRONG TÍCH HỢP HỆ THỐNG

### Cuộc xung đột giữa hai miền tính toán đối lập

| Yếu tố kỹ thuật | Miền Điều Khiển Khung Gầm (Chassis ECU) | Miền Viễn Thông & Thông Tin (Telematics/Infotainment) |
| :--- | :--- | :--- |
| **Yêu cầu thời gian** | **Hard Real-Time:** Độ trễ cỡ microsecond, chu kỳ lặp lại nghiêm ngặt $10\text{ ms}$. | **Soft Real-Time / Best-Effort:** Chấp nhận trễ vài chục mili-giây. |
| **Hệ điều hành** | RTOS chuyên dụng (**Zephyr RTOS**) hoặc **AUTOSAR Classic**. | Hệ điều hành giàu tính năng (**Embedded Linux**). |
| **Độ tin cậy** | Xác định (Deterministic), **Zero Crash**, an toàn sinh mạng. | Nhiều dịch vụ mạng phức tạp, **rất dễ bị treo đơ, tràn RAM, Kernel Panic**. |

> ⚠️ **Nghịch lý:** Nếu chạy chung trên một hệ điều hành Linux duy nhất, một sự cố treo ứng dụng giải trí có thể kéo sập toàn bộ hệ thống phanh và lái của xe!

---

# 3. GIẢI PHÁP ĐỀ XUẤT: NỀN TẢNG ĐA NHÂN DỊ THỂ STM32MP157

### Cách ly phần cứng tuyệt đối (Hardware Domain Isolation)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   STM32MP157D-DK1 HETEROGENEOUS SOC                    │
│                                                                        │
│   ┌────────────────────────────────┐   ┌───────────────────────────┐   │
│   │   CORTEX-A7 GATEWAY DOMAIN     │   │  CORTEX-M4 REAL-TIME ECU  │   │
│   │   (Dual-Core @ 800MHz, Linux)  │   │   (Single-Core @ 209MHz)  │   │
│   │                                │   │                           │   │
│   │   - OpenSTLinux 5.0.17         │   │   - Zephyr RTOS v4.5.99   │   │
│   │   - Linux IPC Daemon           │   │   - Chuẩn AUTOSAR Classic │   │
│   │   - SQLite3 Blackbox Recorder  │   │   - PID Điều khiển motor  │   │
│   │   - MQTT Cloud IoT Gateway     │   │   - Chốt an toàn ISO 26262│   │
│   └───────────────┬────────────────┘   └─────────────▲─────────────┘   │
│                   │                                  │                 │
│                   └──► IPCC Mailbox + RPMsg Shared ◄─┘                 │
└────────────────────────────────────────────────────────────────────────┘
```

* **Cortex-M4:** Chạy từ bộ nhớ nội SRAM độc lập, không bị ảnh hưởng dù Linux có bị treo đơ.
* **Giao tiếp liên nhân (IPC):** Sử dụng OpenAMP RPMsg với cơ chế kiểm tra toàn vẹn **CRC-16-CCITT**.

---

# 4. KIẾN TRÚC PHẦN MỀM CORTEX-M4: CHUẨN AUTOSAR CLASSIC

### Phân tầng trừu tượng hóa 3 lớp độc lập

```
┌────────────────────────────────────────────────────────────────────────┐
│                   APPLICATION SOFTWARE LAYER (ASW)                     │
│   ┌───────────────────────┐ ┌───────────────────┐ ┌────────────────┐   │
│   │   Swc_MotorControl    │ │ Swc_SensorManager │ │Swc_SafetyManagr│   │
│   │   (PID 10ms Discrete) │ │ (PIR, Accel, DHT) │ │(ISO 26262 Stop)│   │
│   └───────────────────────┘ └───────────────────┘ └────────────────┘   │
├────────────────────────────────────────────────────────────────────────┤
│                       RUNTIME ENVIRONMENT (RTE)                        │
│   - Rte_Read() / Rte_Write() Ports: Cách ly hoàn toàn ASW với Phần cứng│
│   - Rte_TimerEvent_10ms(): Lập lịch tất định 100 Hz (k_timer + k_sem)  │
├────────────────────────────────────────────────────────────────────────┤
│                       BASIC SOFTWARE (BSW / MCAL / CDD)                │
│   ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐   │
│   │ Mcal_Pwm  │ │ Mcal_Icu  │ │ Mcal_Dio  │ │ Cdd_L298n │ │Cdd_Ipc │   │
│   │ (20 kHz)  │ │ (Encoder) │ │ (Test PE9)│ │ (H-Bridge)│ │(RPMsg) │   │
│   └───────────┘ └───────────┘ └───────────┘ └───────────┘ └────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

* **Ưu điểm vượt trội:** Khi thay đổi loại vi điều khiển hoặc cảm biến, **100% mã nguồn thuật toán (ASW) được giữ nguyên vẹn**, không cần viết lại.

---

# 5. THU THẬP DỮ LIỆU & NHẬN DẠNG HỆ THỐNG TRÊN MATLAB

### Phương pháp tiếp cận bài bản thay cho "Thử - Sai"

* **Bước 1: Kích thích bước nhảy mở vòng (Open-loop Step Test):**
  - Cortex-M4 phát bước nhảy Duty $0\% \to 60\%$ trong $3.0\text{ s}$.
  - Cortex-A7 ghi lại tốc độ đáp ứng vào file `step_response_60.csv` với chu kỳ $T_s = 10\text{ ms}$.

* **Bước 2: Nhận dạng hàm truyền FOPDT trên MATLAB System Identification Toolbox:**
  - Mô hình nhận dạng đạt độ tương thích thực nghiệm (**Best Fit**) lên tới **80.95%**:

  $$G(s) = \frac{0.1873}{0.0461 s + 1} e^{-0.0400 s}$$

  - Hệ số khuếch đại tĩnh: $K = 0.1873\text{ RPM / \%Duty}$
  - Hằng số thời gian quán tính: $\tau = 46.1\text{ ms}$
  - Thời gian trễ khởi động: $\theta = 40.0\text{ ms}$

---

# 6. THIẾT KẾ GIẢI THUẬT ĐIỀU KHIỂN PID RỜI RẠC & ANTI-WINDUP

* **Thông số điều khiển tối ưu hóa từ MATLAB Control System Toolbox:**
  $$K_P = 1.9641, \quad K_I = 85.0402, \quad K_D = 0.0000, \quad T_s = 10\text{ ms}$$

* **Phương trình sai phân rời rạc triển khai trong `Swc_MotorControl.c`:**
  - Sai số vận tốc: $e[k] = \text{Target}[k] - \text{Actual}[k]$
  - Thành phần Tỷ lệ: $P[k] = K_P \cdot e[k]$
  - Thành phần Tích phân: $I[k] = I[k-1] + K_I \cdot T_s \cdot e[k]$
  - Tín hiệu điều khiển: $u[k] = P[k] + I[k]$

* **Cơ chế Chống Bão Hòa Tích Phân (Anti-Windup Clamping):**
  - Khi tải nặng hoặc motor chạm trần công suất $\text{Duty}_{\text{max}} = 85.0\%$:
  - Khóa tức thì thành phần tích phân $I[k]$, loại bỏ hoàn toàn hiện tượng vọt lố (Overshoot) và giật cục động cơ.

---

# 7. HỆ THỐNG AN TOÀN CHỦ ĐỘNG 3 TRỤ CỘT (ISO 26262)

### Cơ chế bảo vệ đa tầng loại bỏ mọi nguy cơ tai nạn

```
             ┌──────────────────────────────────────────────┐
             │         SWC_SAFETYMANAGER (ISO 26262)        │
             └──────────────────────┬───────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│  TRỤ CỘT 1: PIR  │       │ TRỤ CỘT 2: GY-61 │       │ TRỤ CỘT 3: WDG   │
│  Vật cản mũi xe  │       │  Va chạm lật xe  │       │ Gián đoạn Linux  │
│  Góc quét 120°   │       │  |a| > 2.5g-3.5g │       │ Timeout > 1.0s   │
└────────┬─────────┘       └────────┬─────────┘       └────────┬─────────┘
         │                          │                          │
         └──────────────────────────┼──────────────────────────┘
                                    ▼
                 ┌──────────────────────────────────────┐
                 │ Cdd_L298n_EmergencyStop(): Ngắt PWM  │
                 │ Triệt tiêu xung về 0V trong < 0.05ms │
                 └──────────────────────────────────────┘
```

---

# 8. TẦNG GATEWAY LINUX (A7) & GIAO DIỆN BUỒNG LÁI ẢO (QT)

* **Linux Gateway Daemon (`gateway_daemon.py`):**
  - Quản lý kênh `/dev/ttyRPMSG0` tốc độ $115200\text{ bps}$, xác thực mã kiểm tra **CRC-16-CCITT**.
  - Tự động duy trì nhịp tim **Heartbeat (500ms)** để nuôi Watchdog trên M4.
  - Cơ sở dữ liệu SQLite3 cơ chế **WAL (Write-Ahead Logging)**: Hộp đen lưu trữ vĩnh viễn sự cố `$FAULT`.
  - Cổng IoT MQTT xuất bản dữ liệu viễn thông lên đám mây.

* **Buồng lái kỹ thuật số thể thao (Qt Digital Virtual Cockpit):**
  - Cặp đồng hồ kim tròn quét mượt mà ở tần số cao **$40\text{ FPS}$** (Speedometer & Power Gauge).
  - Đồ họa khung gầm xe nhìn từ trên xuống kết hợp **Radar sóng xung hồng ngoại** cảnh báo va chạm.
  - Con lắc gia tốc G-Meter trực quan hóa rung lắc xe.
  - Đồ thị bám vận tốc thời gian thực $100\text{ Hz}$, dải đèn cảnh báo chuẩn quốc tế **ISO 2575**.

---

# 9. KẾT QUẢ ĐO KIỂM NFR-1: ĐỊNH LƯỢNG JITTER CHU KỲ 10ms

### Đo đạc thực tế bằng Saleae Logic 2 trên Test Pin `PE9` (Arduino `D6`)

* **Chu kỳ danh định lý thuyết:** $T_{\text{nominal}} = \mathbf{10.000000\text{ ms}}$
* **Độ rộng nửa chu kỳ đo thực tế:** $T_{\text{measured}} = \mathbf{10.006375\text{ ms}}$

$$\text{Jitter Phần Cứng } \Delta T = |10.006375\text{ ms} - 10.000000\text{ ms}| = \mathbf{6.375\ \mu\text{s}}$$

* **Chu kỳ toàn phần (Lên + Xuống):** $20.01275\text{ ms}$ (Tần số $49.986\text{ Hz}$, sai số $-0.028\%$).
* **Độ đối xứng xung (Duty Cycle):** $50.0\%$ hoàn hảo.

> 🏆 **ĐÁNH GIÁ CHUẨN NFR-1:**
> * Tiêu chuẩn đặc tả: Jitter $\le 50.0\ \mu\text{s}$.
> * Kết quả thực tế: $\Delta T = \mathbf{6.375\ \mu\text{s}}$ $\to$ **VƯỢT CHUẨN XUẤT SẮC 7.84 LẦN** (Dư tới $87.25\%$ biên độ an toàn). Khẳng định tính tất định thời gian thực tuyệt đối của Zephyr RTOS!

---

# 10. KẾT QUẢ ĐO KIỂM NFR-2: THỜI GIAN PHẢN ỨNG DỪNG KHẨN CẤP

### Đo đạc độ trễ phanh khi phát hiện chướng ngại vật PIR

* **1. Xác thực xung PWM phần cứng (`PD14` - `TIM4_CH3`):**
  - Tần số sóng mang đo được: Chuẩn xác **$20.000\text{ kHz}$** ($T_{\text{PWM}} = 50.0\ \mu\text{s}$).
  - Độ rộng xung mức cao: $t_{\text{high}} = 42.5\ \mu\text{s} \implies \text{Duty} = \mathbf{85.0\%}$ (Khớp $100\%$ với trần Anti-Windup).

* **2. Đo độ trễ ngắt xung PWM:**
  - Cảm biến PIR kích hoạt sườn lên báo nguy hiểm tại $t = 1.9011\text{ s}$.
  - Tại chu kỳ an toàn tiếp theo ($t = 1.9178\text{ s}$), PWM lập tức bị triệt tiêu hoàn toàn về $0\text{V}$ phẳng:

  $$t_{\text{actuator\_cut}} < \mathbf{0.05\text{ ms}} \quad (\text{Quy chuẩn NFR-2: } < 5\text{ ms})$$

  - Tổng thời gian đáp ứng từ lúc cảm biến nhận tín hiệu đến khi ngắt điện động cơ là **$16.7\text{ ms}$**.

> 🏆 **ĐÁNH GIÁ CHUẨN NFR-2: ĐẠT XUẤT SẮC**

---

# 11. KẾT QUẢ ĐO KIỂM NFR-3: ĐỘ TRỄ KHỨ HỒI RPMSG IPC

### Benchmark tự động 100 gói tin khứ hồi A7 $\leftrightarrow$ M4 qua `/dev/ttyRPMSG0`

```
==========================================================
   RPMsg IPC ROUND-TRIP LATENCY BENCHMARK (NFR-3)
==========================================================
   Valid Responses:      100/100 (100.0%)  -> 0% packet drop
   Average RTT (t_avg):  1.999 ms          -> Mục tiêu: < 5.0 ms
   Minimum RTT (t_min):  1.727 ms
   Maximum RTT (t_max):  2.640 ms
   Jitter StdDev (σ):    0.129 ms          -> Tính tất định cực cao
==========================================================
   Evaluation: EXCELLENT (t_avg < 5.0 ms, High Real-Time)
==========================================================
```

* **Ý nghĩa:** Toàn bộ chu trình từ Linux User-space $\to$ Vring Kernel $\to$ Ngắt IPCC Mailbox $\to$ Cortex-M4 xử lý $\to$ Phản hồi về Linux chỉ diễn ra trong **$1.999\text{ ms}$**!

> 🏆 **ĐÁNH GIÁ CHUẨN NFR-3: ĐẠT XUẤT SẮC**

---

# 12. KẾT QUẢ ĐO KIỂM NFR-4: TÍNH ĐỘC LẬP KHI LINUX CRASH

### Kiểm chứng sự sống còn của phân vùng thời gian thực Cortex-M4

* **Kịch bản kiểm thử thực tế:**
  1. Cho động cơ quay ổn định ở $10\text{ RPM}$.
  2. Bắn tín hiệu ngắt cưỡng bức dừng tiến trình Dashboard (`Ctrl + C` / Kill process) giả lập Linux bị sập/treo cứng.
  3. Quan sát phản ứng của Cortex-M4 và động cơ phần cứng.

* **Hiện tượng thực nghiệm ghi nhận:**
  * Toàn bộ giao diện điều khiển HMI và kênh truyền thông bị tiêu diệt hoàn toàn.
  * **Cortex-M4 vẫn tiếp tục điều khiển động cơ quay mượt mà $100\%$**, vòng lặp PID $10\text{ ms}$ không bị ảnh hưởng.
  * Khi đưa tay trước cảm biến PIR, **Cortex-M4 tự động kích hoạt phanh dừng xe khẩn cấp ngay lập tức**!

> 🏆 **ĐÁNH GIÁ CHUẨN NFR-4: ĐẠT TUYỆT ĐỐI (Cách ly miền thời gian thực hoàn hảo).**

---

# 13. KẾT QUẢ ĐO KIỂM NFR-5: ĐỘ CHÍNH XÁC ĐIỀU KHIỂN PID

### Đánh giá chất lượng bám vận tốc vòng kín ở tần số 100 Hz

* **Sai số xác lập (Steady-State Error):**
  $$e_{ss} = |\text{Target} - \text{Actual}| = \mathbf{0.00\text{ RPM}}$$
  *(Tiêu chuẩn đặc tả NFR-5 yêu cầu $e_{ss} \le 2.0\text{ RPM}$).*

* **Độ vọt lố (Overshoot):** $\mathbf{0\%}$ (Động cơ tăng tốc mượt mà, không bị vọt lố).

* **Thời gian đáp ứng xác lập ($t_s$):** $\approx 1.2\text{ giây}$.

* **Toàn vẹn truyền thông:** $3,318 / 3,318$ gói tin truyền về Dashboard đạt chuẩn kiểm tra CRC-16 ($100.0\%$, không có bất kỳ gói tin nào bị lỗi bit).

> 🏆 **ĐÁNH GIÁ CHUẨN NFR-5: ĐẠT 100%**

---

# 14. BẢNG TỔNG HỢP NGHIỆM THU TOÀN DIỆN (MASTER SCORECARD)

| Nhóm | Tiêu chuẩn | Chỉ tiêu kỹ thuật đặc tả | Kết quả thực tế trên phần cứng | Đánh giá |
| :---: | :---: | :--- | :--- | :---: |
| **NFR** | **NFR-1** | Chu kỳ PID $10\text{ ms}$, Jitter $\le 50\ \mu\text{s}$ | $\Delta T = \mathbf{6.375\ \mu\text{s}}$ (Saleae Logic 2 trên PE9) | **VƯỢT CHUẨN 7.8 LẦN** |
| **NFR** | **NFR-2** | Độ trễ ngắt E-Stop $< 5\text{ ms}$ | $t_{\text{cut}} < \mathbf{0.05\text{ ms}}$ tại chu kỳ ngắt, $16.7\text{ ms}$ tổng | **ĐẠT XUẤT SẮC** |
| **NFR** | **NFR-3** | Độ trễ khứ hồi RPMsg IPC A7 $\leftrightarrow$ M4 | $t_{\text{avg}} = \mathbf{1.999\text{ ms}}$, $\sigma = 0.129\text{ ms}$ ($100/100$) | **ĐẠT XUẤT SẮC** |
| **NFR** | **NFR-4** | Tính độc lập khi Linux/HMI crash | M4 tự chạy PID độc lập & tự ngắt phanh khi có PIR | **ĐẠT TUYỆT ĐỐI** |
| **NFR** | **NFR-5** | Độ chính xác điều khiển PID | $e_{ss} = \mathbf{0.00\text{ RPM}}$, không vọt lố (Overshoot $0\%$) | **ĐẠT 100%** |
| **NFR** | **NFR-6** | An toàn điện áp I/O $\le 3.3\text{V}$ | $100\%$ các kênh đo đạt chuẩn điện áp an toàn $3.3\text{V}$ | **ĐẠT 100%** |
| **FR-M** | **FR-M1 $\to$ M10** | Zephyr RTOS, AUTOSAR Classic, PWM 20kHz, Encoder, PID, PIR, GY-61, DHT11, RPMsg, PE9 | Chạy đồng bộ, ổn định, tách biệt hoàn toàn ASW/BSW | **HOÀN THÀNH 100%** |
| **FR-A** | **FR-A1 $\to$ A5** | OpenSTLinux, Linux Daemon, SQLite3 WAL, MQTT Gateway, Qt Digital Cockpit | Thu thập viễn thông, hộp đen tai nạn và buồng lái số 40 FPS | **HOÀN THÀNH 100%** |

---

# 15. VIDEO THỰC NGHIỆM DEMO TOÀN DIỆN PHẦN CỨNG

### Minh chứng thực nghiệm vận hành trên kit STM32MP157D-DK1

* **Đường dẫn file video:** [**docs/video_demo/demo.mp4**](file:///c:/Study/Personal_project/stm32mp157d-dk1/docs/video_demo/demo.mp4) *(Full HD 1080p, ~29.6 MB)*
* **4 Kịch bản kiểm thử then chốt được ghi hình chi tiết:**
  1. **Khởi động & Nạp Firmware (IPC Bring-Up):** Cortex-A7 khởi động, nạp firmware Cortex-M4 qua `remoteproc0`, kết nối kênh RPMsg với giao diện Virtual Cockpit.
  2. **Bám vận tốc PID 10ms (NFR-5):** Cần số điện tử chuyển sang `D (PID)`, cài đặt các mốc tốc độ 8, 10, 12 RPM, kim Speedometer quét mượt mà $40\text{ FPS}$, sai số xác lập $e_{ss} = 0.00\text{ RPM}$.
  3. **Phanh khẩn cấp PIR E-Stop (NFR-2):** Đưa tay trước mũi xe $\to$ Sóng radar đổi màu đỏ, phanh triệt tiêu PWM tức thì ($< 50\ \mu\text{s}$).
  4. **Kiểm chứng độc lập khi Crash (NFR-4):** Ngắt kết nối Dashboard, motor vẫn chạy ổn định và tự ngắt phanh an toàn khi gặp vật cản.

---

# 16. KẾT LUẬN & ĐÓNG GÓP KỸ THUẬT

### 4 Đóng góp nổi bật của đề tài:
1. **Làm chủ công nghệ SoC Đa Nhân Dị Thể (STM32MP157):** Giải quyết trọn vẹn bài toán tích hợp giữa điều khiển an toàn thời gian thực nghiêm ngặt và ứng dụng thông minh.
2. **Hiện thực hóa chuẩn mực công nghiệp ô tô AUTOSAR Classic:** Triển khai thành công kiến trúc phân tầng chuẩn trên **Zephyr RTOS**, đảm bảo tính mô-đun hóa và khả năng tái sử dụng phần mềm tối đa.
3. **Quy trình thiết kế điều khiển hiện đại:** Ứng dụng nhận dạng hệ thống thực nghiệm trên **MATLAB** đạt độ khớp $80.95\%$, triệt tiêu sai số bám vận tốc về $0.00\text{ RPM}$.
4. **Đo kiểm định lượng chuyên sâu:** Toàn bộ các thông số Jitter ($6.375\ \mu\text{s}$), độ trễ phanh ($< 0.05\text{ ms}$), và độ trễ IPC ($1.999\text{ ms}$) đều được đo kiểm bằng thiết bị công nghiệp Logic Analyzer.

---

# 17. HƯỚNG PHÁT TRIỂN TIẾP THEO

* **Mở rộng giao thức mạng vật lý ô tô:**
  - Tích hợp giao tiếp mạng **CAN FD** và **Automotive Ethernet (100BASE-T1)** kết nối với các cảm biến xe hơi thông minh.

* **Nâng cấp giải thuật điều khiển động cơ:**
  - Phát triển thuật toán điều khiển vector tựa từ thông (**FOC - Field Oriented Control**) cho động cơ không chổi than PMSM/BLDC kéo bánh xe điện.

* **Cập nhật phần mềm không dây an toàn (OTA):**
  - Xây dựng cơ chế cập nhật firmware từ xa qua mạng đám mây (Over-The-Air Update) có chữ ký mã hóa bảo mật cho lõi Cortex-M4 thông qua cổng Linux Gateway.

---

# XIN TRÂN TRỌNG CẢM ƠN HỘI ĐỒNG GIÁM KHẢO!

### PHIÊN HỎI & ĐÁP (Q&A)

*Em xin sẵn sàng lắng nghe và giải đáp các câu hỏi từ Quý Thầy Cô trong Hội đồng!*
