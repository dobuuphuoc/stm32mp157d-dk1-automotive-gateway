# Báo Cáo Kỹ Thuật Tuần 1 & Nhật Ký Kỹ Sư (Week 1 Review & Engineering Log)

**Dự án:** STM32MP157D-DK1 Automotive Gateway & Motor Controller  
**Kiến trúc:** Asymmetric Multiprocessing (AMP) — Cortex-A7 (OpenSTLinux) + Cortex-M4 (AUTOSAR Classic trên Zephyr RTOS)  
**Thời gian hoàn thành:** Tuần 1 & Khởi tạo Tuần 2  
**Tài liệu tham chiếu:** [requirements_stm32mp157_motor_gateway.md](file:///c:/Study/Personal_project/stm32mp157d-dk1/requirement/requirements_stm32mp157_motor_gateway.md)

---

## 1. Tổng Quan Kết Quả Tuần 1 (Executive Summary)

Trong Tuần 1, toàn bộ các hạng mục mục tiêu nền tảng phần cứng, hệ điều hành Linux trên Cortex-A7, môi trường Cross-Compile trên máy ảo Ubuntu 22.04, và khung phần mềm thời gian thực chuẩn **AUTOSAR Classic** trên Cortex-M4 đã được hoàn thành **100%**.

| Hạng mục mục tiêu Tuần 1 | Trạng thái | Minh chứng / Kết quả cụ thể |
|---|:---:|---|
| **Flash thẻ nhớ & Boot OpenSTLinux** | ✅ **100% Hoàn thành** | Sử dụng script [create_sdcard_raw.py](file:///c:/Study/Personal_project/stm32mp157d-dk1/create_sdcard_raw.py) nạp ảnh đĩa thô; kit khởi động thành công bản phát hành **OpenSTLinux 5.0.17** với **Linux Kernel 6.6.129 SMP PREEMPT** trên nhân kép Cortex-A7. |
| **Serial Console & Mạng Ethernet** | ✅ **100% Hoàn thành** | Cổng UART Console `ttySTM0` hoạt động ổn định ở tốc độ 115200 bps (kết nối máy trạm qua cổng COM5 trên phần mềm Hercules). Cổng mạng Ethernet `end0` nhận IP tĩnh `192.168.0.15`, kiểm tra SSH và SCP thông suốt với độ trễ thấp (< 1 ms). |
| **Subsystem `remoteproc0`** | ✅ **100% Hoàn thành** | Kiểm tra `/sys/class/remoteproc/remoteproc0` xác nhận nhân Linux Cortex-A7 sẵn sàng điều khiển cấp nguồn, nạp firmware và giám sát trạng thái nhân Cortex-M4. |
| **Môi trường Cross-Compile (Ubuntu VM)** | ✅ **100% Hoàn thành** | Xây dựng hoàn chỉnh môi trường phát triển trên Ubuntu 22.04 LTS (VMware): nâng cấp **Python 3.12** (`~/.venv312`), **CMake 4.4.4**, **Zephyr RTOS v4.5.99** cùng các module `hal_stm32`, `cmsis`, `open-amp`, `libmetal`, và **Zephyr SDK 1.0.1** (`arm-zephyr-eabi` GCC 14.3.0). |
| **Blinky Proof-of-Concept M4** | ✅ **100% Hoàn thành** | Biên dịch thành công firmware `blinky.elf`, tối ưu hóa kích thước bằng lệnh `strip` (giảm dung lượng từ **565 KB** xuống **27 KB**), nạp qua SCP và khởi chạy thành công trên Cortex-M4. **LED6 màu cam (LD6)** chớp tắt chu kỳ 1s độc lập hoàn toàn với Linux. |
| **Khung dự án AUTOSAR Classic M4** | ✅ **100% Hoàn thành** | Khởi tạo cấu trúc dự án [`motor_gateway_m4`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4) phân tầng chuẩn AUTOSAR Classic: Application Layer ([`Swc_MotorControl`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/src/asw)), Runtime Environment ([`Rte`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/src/rte)), MCAL ([`Mcal_Dio`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/src/bsw/mcal)), Device Tree Overlay ([`stm32mp157c_dk2.overlay`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/boards/stm32mp157c_dk2.overlay)), và kịch bản nạp 1-click [deploy.sh](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/deploy.sh). |

---

## 2. Kiến Trúc Môi Trường Làm Việc (Development Workflow)

Kiến trúc triển khai phân tán Asymmetric Multiprocessing (AMP) của hệ thống được tổ chức khép kín từ máy trạm đến phần cứng vi xử lý heterogenous STM32MP157:

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
    RPROC ==>|Cấp clock / Reset / Load ELF vào SRAM| M4
    TER <==|USB-C ST-LINK VCP| OS
    PE9 ==>|Kẹp probe đo xung| LA
```

### Phân Định Trách Nhiệm Từng Thành Phần
1. **Workstation x86_64 / Ubuntu VM (Build Environment):**
   - Đảm nhiệm toàn bộ việc quản lý mã nguồn, biên dịch chéo (Cross-compilation) ứng dụng Zephyr RTOS cho kiến trúc ARM Cortex-M4 (`arm-zephyr-eabi`).
   - Rút gọn kích thước nhị phân bằng công cụ `arm-zephyr-eabi-strip` để loại bỏ metadata/debug symbols không cần thiết trước khi truyền qua mạng.
   - Điều khiển tự động hóa quy trình nạp firmware thông qua giao thức SSH và SCP qua mạng LAN.
2. **Cortex-A7 (High-Performance Linux Host - Vehicle Gateway):**
   - Chạy hệ điều hành nhúng **OpenSTLinux** cung cấp khả năng đa nhiệm mạnh mẽ, mạng TCP/IP Ethernet (`end0`), và các dịch vụ tầng cao (SSH, Daemon, MQTT, Qt GUI sau này).
   - Đóng vai trò là Host Master điều khiển toàn diện vòng đời (Life-cycle Management) của nhân Cortex-M4 thông qua subsystem chuẩn của Linux Kernel: `remoteproc`.
   - Nơi lưu trữ tập trung các file firmware nhị phân tại phân vùng `/lib/firmware/`.
3. **Cortex-M4 (Deterministic Real-Time Controller):**
   - Chạy độc lập trên nền **Zephyr RTOS** ở xung nhịp 209 MHz, thực thi trực tiếp từ bộ nhớ RETRAM/SRAM nội của vi điều khiển.
   - Thực thi các tác vụ thời gian thực cứng (Hard Real-Time): điều khiển vòng kín PID $10\text{ ms}$, đọc xung encoder Hall, điều chế xung PWM điều khiển cầu H, và ngắt bảo vệ an toàn.
   - Hoàn toàn miễn nhiễm với độ trễ (latency/jitter) hoặc sự cố sụp đổ (crash/kernel panic) của nhân Linux Cortex-A7.

---

## 3. Nhật Ký Xử Lý Sự Cố Kỹ Thuật (Troubleshooting Log)

Trong quá trình khởi tạo hệ thống Tuần 1, nhóm kỹ sư đã giải quyết triệt để 5 rào cản kỹ thuật quan trọng. Bảng dưới đây tổng hợp chi tiết hiện tượng, nguyên nhân gốc rễ và giải pháp kỹ thuật chuẩn hóa:

| # | Vấn đề / Hiện tượng lỗi | Nguyên nhân gốc rễ (Root Cause) | Giải pháp kỹ thuật chuẩn (Permanent Fix) |
|---|---|---|---|
| **1** | **SSH Connection timed out** khi kết nối đến IP `10.8.82.33`. | Máy tính Host kết nối qua mạng Wi-Fi của công ty/trường học có tính năng AP Isolation (cách ly thiết bị) và khác lớp mạng con (subnet) với cổng Ethernet của board DK1. | Chuyển máy ảo và board về chung một switch/dải mạng LAN nội bộ; cấu hình cấp phát IP cố định cho cổng Ethernet `end0` của board là **`192.168.0.15`**, ping kiểm tra round-trip time `< 1 ms`. |
| **2** | **Lỗi phân giải tên miền & mất mạng trên Ubuntu VM** (`Temporary failure resolving`, `Destination Host Unreachable`). | Cấu hình mạng máy ảo VMware Workstation bị xung đột giữa chế độ Bridged và NAT khi máy chủ Windows đổi mạng; file `/etc/resolv.conf` thiếu máy chủ DNS công cộng. | Thiết lập Network Adapter của VM ở chế độ **NAT** (hoặc Bridged chuẩn card vật lý); cập nhật DNS máy chủ tĩnh `nameserver 8.8.8.8` và `nameserver 1.1.1.1` vào cấu hình `systemd-resolved`. |
| **3** | **Đầy bộ nhớ đĩa máy ảo** (`No space left on device`) khi chạy lệnh `west update`. | Kho nguồn Zephyr mặc định chứa hàng chục module, driver cho tất cả các họ chip (NXP, Espressif, Microchip, TI,...) và toàn bộ lịch sử git commit hàng chục gigabyte. | Tối ưu hóa lệnh clone bằng cờ `--narrow` và giới hạn độ sâu commit: <br>`west update --narrow -o=--depth=1`<br>Chỉ giữ lại các module thiết yếu cho vi xử lý STM32MP1: `hal_stm32`, `cmsis`, `open-amp`, `libmetal`, `picolibc`. |
| **4** | **Xung đột phiên bản phần mềm** khi cài đặt Zephyr SDK 1.0.1: CMake mặc định 3.22.1 (< 3.28.0) và Python mặc định 3.10 (< 3.12). | Phiên bản Zephyr RTOS mới nhất (v4.5.99) và SDK 1.0.1 yêu cầu chuẩn toolchain cao hơn các gói mặc định có sẵn trong kho apt của Ubuntu 22.04 LTS. | Thêm PPA `ppa:deadsnakes/ppa` để cài đặt **Python 3.12**, cô lập môi trường bằng Virtual Environment (`python3.12 -m venv ~/.venv312`), sau đó dùng `pip` nâng cấp **CMake** lên phiên bản **4.4.4** và **west** mới nhất. |
| **5** | **Lỗi truyền file SCP** (`subsystem request for sftp failed`, `Connection closed`). | Bản phân phối OpenSTLinux sử dụng máy chủ SSH thu nhỏ **Dropbear SSH**, mặc định không tích hợp subsystem SFTP mà các công cụ SCP OpenSSH hiện đại (OpenSSH 9+) cố gắng sử dụng trước. | Sử dụng cờ **`-O`** trong lệnh `scp` (`scp -O ...`) để ép buộc công cụ truyền file qua giao thức **Legacy SCP Protocol** chuẩn, tương thích 100% với Dropbear. Đã tích hợp sẵn vào script [deploy.sh](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/deploy.sh). |

---

## 4. Sổ Tay Lệnh Nhanh (Quick Command Cheatsheet)

Dành cho kỹ sư vận hành thao tác hàng ngày:

### 4.1 Môi Trường Biên Dịch (Ubuntu 22.04 VM)
```bash
# 1. Kích hoạt Virtual Environment Python 3.12 & nạp cấu hình môi trường Zephyr
source ~/.venv312/bin/activate
export ZEPHYR_SDK_INSTALL_DIR=$HOME/zephyr-sdk-1.0.1

# 2. Di chuyển vào thư mục dự án M4
cd ~/stm32mp157d-dk1/motor_gateway_m4

# 3. Biên dịch và nạp tự động xuống board chỉ bằng 1 câu lệnh duy nhất:
./deploy.sh 192.168.0.15
```

### 4.2 Thao Tác Thủ Công Trên Máy Ảo (Build & Strip)
```bash
# Biên dịch Zephyr kèm Device Tree Overlay cho chân PE9, PE10, PH6
west build -b stm32mp157c_dk2 . -p auto -- -DDTC_OVERLAY_FILE=boards/stm32mp157c_dk2.overlay

# Rút gọn nhị phân (giảm từ 565 KB xuống 27 KB)
~/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-strip -s build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf

# Nạp sang Linux A7 qua giao thức Legacy SCP
scp -O ~/motor_gateway_m4.elf root@192.168.0.15:/lib/firmware/motor_gateway_m4.elf
```

### 4.3 Quản Lý Nhân Cortex-M4 Từ Linux Console (Cortex-A7)
```bash
# Kiểm tra trạng thái hiện tại của M4 (running hoặc offline)
cat /sys/class/remoteproc/remoteproc0/state

# Dừng thực thi Cortex-M4
echo stop > /sys/class/remoteproc/remoteproc0/state

# Thiết lập file firmware đích trong thư mục /lib/firmware/
echo motor_gateway_m4.elf > /sys/class/remoteproc/remoteproc0/firmware

# Khởi động lại nhân Cortex-M4
echo start > /sys/class/remoteproc/remoteproc0/state

# Xem nhật ký log của hệ thống kernel
dmesg | tail -n 20
```

### 4.4 Nạp Firmware Khi Không Có Cáp Mạng LAN (Qua Cổng Serial ST-LINK `/dev/ttyACM0`)
Khi không cắm dây mạng LAN RJ45, kết nối thiết bị USB ST-LINK vào máy ảo (**VM $\rightarrow$ Removable Devices $\rightarrow$ STMicroelectronics STM32 STLink $\rightarrow$ Connect**) và chạy:
```bash
# Tự động Build, Strip và truyền thẳng qua cổng Serial /dev/ttyACM0 (Base64 + Gzip ~6KB):
./deploy.sh serial
```

---

## 5. Cấu Trúc Khung Dự Án AUTOSAR Classic M4 & Thiết Lập Đo Jitter

Mã nguồn trên nhân Cortex-M4 được cấu trúc hóa chặt chẽ theo phân tầng kiến trúc **AUTOSAR Classic** tại thư mục [`motor_gateway_m4/`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4):

```
motor_gateway_m4/
├── CMakeLists.txt                  <- Kịch bản build Zephyr CMake, liên kết các thư mục nguồn ASW, RTE, BSW
├── prj.conf                        <- Cấu hình Zephyr Kconfig: Preemption, GPIO, FPU hardware, Timer
├── deploy.sh                       <- Kịch bản Bash tự động: West Build -> Strip ELF -> SCP -> Remoteproc Restart
├── boards/
│   └── stm32mp157c_dk2.overlay     <- Device Tree Overlay: Khai báo chân PE9 (Test Pin), PE10 (IN1), PH6 (IN2)
└── src/
    ├── main.c                      <- Điểm vào hệ thống, EcuM_Init(), Task định kỳ 10ms (k_timer + k_sem)
    ├── std_types.h                 <- Khai báo các kiểu dữ liệu chuẩn AUTOSAR (uint8, float32, Std_ReturnType, E_OK,...)
    ├── asw/                        <- Tầng ứng dụng (Application Layer - Độc lập phần cứng 100%)
    │   ├── Swc_MotorControl.h      <- Định nghĩa Interface Runnable_MotorControl_10ms()
    │   └── Swc_MotorControl.c      <- Cài đặt thuật toán điều khiển PID vận tốc động cơ & Step Open-loop
    ├── rte/                        <- Tầng môi trường thực thi (Runtime Environment)
    │   ├── Rte.h                   <- Sender-Receiver Ports: Rte_Read_rpSpeed_rpm(), Rte_Write_ppDuty_percentage()
    │   └── Rte.c                   <- Quản lý bộ đệm biến toàn cục chia sẻ an toàn và điều phối Runnable
    └── bsw/                        <- Tầng phần mềm cơ sở (Basic Software Layer)
        └── mcal/                   <- Tầng trừu tượng hóa vi điều khiển (Microcontroller Abstraction Layer)
            ├── Mcal_Dio.h          <- Định nghĩa kênh DIO_CH_TEST_PE9, DIO_CH_L298N_IN1, DIO_CH_L298N_IN2
            └── Mcal_Dio.c          <- Điều khiển trực tiếp GPIO vi điều khiển STM32MP1 qua Zephyr GPIO Driver API
```

### Cơ Chế Đo Jitter Chu Kỳ $T_s = 10\text{ ms}$ Bằng Logic Analyzer (FR-M10 & NFR-1)

Để chứng minh tính tiền định (Determinism) và độ trễ thấp của Zephyr RTOS trên nhân Cortex-M4 theo yêu cầu **NFR-1** ($T_s = 10\text{ ms}$, $\text{Jitter} \le 50\ \mu\text{s}$), hàm `Rte_TimerEvent_10ms()` trong [`Rte.c`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/src/rte/Rte.c) gọi trực tiếp hàm [`Dio_FlipChannel(DIO_CH_TEST_PE9)`](file:///c:/Study/Personal_project/stm32mp157d-dk1/motor_gateway_m4/src/bsw/mcal/Mcal_Dio.c) tại dòng đầu tiên của mỗi chu kỳ điều khiển:

```c
void Rte_TimerEvent_10ms(void)
{
    /* Toggle chân Test Pin PE9 để đo kiểm Jitter thực tế trên Logic Analyzer */
    (void)Dio_FlipChannel(DIO_CH_TEST_PE9);

    /* Thực thi Runnable điều khiển động cơ */
    Runnable_MotorControl_10ms();
}
```

#### Sơ Đồ Đấu Nối Thiết Bị Đo Logic Analyzer
Kỹ sư sử dụng thiết bị USB Logic Analyzer (Saleae Logic / 24M 8CH) đấu nối vào hàng rào cắm Arduino Header trên kit STM32MP157D-DK1 theo bảng sau:

| Đầu nối Logic Analyzer | Vị trí cắm trên Kit DK1 | Ký hiệu Header | Chức năng tín hiệu | Ghi chú an toàn điện áp |
|---|---|---|---|---|
| **Channel 0 (CH0 / CH1)** | **Pin PE9** | **CN14 - Pin 6 (Arduino D6)** | Xung vuông Test Toggle ($f = 50\text{ Hz}$, $T = 20\text{ ms}$, mỗi nửa chu kỳ $10\text{ ms}$) | Điện áp logic **3.3V CMOS** |
| **GND Probe** | **Chân GND** | **CN16 - Pin 6 hoặc CN16 - Pin 7** | Tiếp địa chung tham chiếu điện áp | Bắt buộc phải cắm trước khi kết nối tín hiệu |

> [!IMPORTANT]
> **Quy tắc đo kiểm Jitter:**
> 1. Thiết lập tần số lấy mẫu trên phần mềm Logic Analyzer $\ge 10\text{ MHz}$ (độ phân giải thời gian $\le 0.1\ \mu\text{s}$).
> 2. Đo khoảng thời gian giữa hai cạnh liên tiếp (Edge-to-Edge). Độ rộng xung chuẩn lý tưởng là $10.000\text{ ms}$.
> 3. Độ sai lệch thời gian $\Delta t = |t_{\text{measured}} - 10\text{ ms}|$ được ghi nhận qua $\ge 10,000$ mẫu phải thỏa mãn:
>    $$\text{Jitter}_{\max} \le 50\ \mu\text{s}$$

---

## 6. Kế Hoạch Công Việc Tuần 2 (Next Steps & Checklist)

Bước sang Tuần 2, trọng tâm dự án tập trung vào việc đưa toàn bộ phần cứng ngoại vi chấp hành và cảm biến (Động cơ JGA25-370-46.8K, Driver L298N, Encoder Hall 2 kênh) vào kiểm soát của nhân Cortex-M4:

- [ ] **Đo kiểm & Định lượng Jitter chân PE9:**
  - Kẹp Logic Analyzer vào chân **PE9 (CN14 Pin 6)** và **GND (CN16 Pin 6)**.
  - Chụp ảnh sóng thực tế, thu thập bảng phân phối Jitter thống kê (Mean, Max, Min, Standard Deviation $\sigma$) để lưu trữ vào thư mục `docs/figures/`.
- [ ] **Hoàn thiện tầng `Mcal_Pwm` và `Cdd_L298n`:**
  - Cấu hình Timer **TIM4_CH3 (Chân PD14 - Arduino D3)** phát xung PWM tần số **$20\text{ kHz}$** điều khiển chân ENA của driver L298N.
  - Tích hợp điều khiển hướng quay IN1 (**PE10 - Arduino D4**) và IN2 (**PH6 - Arduino D9**), cài đặt tính năng phanh chủ động ngắn mạch (Active Braking: IN1=HIGH, IN2=HIGH).
- [ ] **Hoàn thiện tầng `Mcal_Icu` / `Qdec` giải mã Encoder Hall:**
  - Cấu hình phần cứng Timer **TIM3** ở chế độ Quadrature Encoder Mode (4x): Kênh A nối chân **PC6 (CN2 Pin 13)**, Kênh B nối chân **PC7 (CN2 Pin 15)**.
  - Lập trình thuật toán tính toán vận tốc trục ra theo công thức:
    $$\omega\ [\text{RPM}] = \frac{\Delta\text{Count}}{\text{CPR}_{\text{output}} \times T_s} \times 60 = \frac{\Delta\text{Count}}{2059.2 \times 0.010} \times 60$$
- [ ] **Cập nhật Device Tree Linux trên Cortex-A7:**
  - Biên dịch Device Tree Overlay trên Linux để vô hiệu hóa (disabled) các ngoại vi `tim3`, `tim4` trên nhân Cortex-A7, đảm bảo Cortex-M4 nắm độc quyền thanh ghi phần cứng mà không bị xung đột tài nguyên.

---
*Tài liệu được soạn thảo và kiểm duyệt bởi kỹ sư phụ trách dự án STM32MP157D-DK1 Automotive Gateway.*
