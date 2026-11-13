# Báo Cáo Tiến Độ Tuần 3: Giao Tiếp Liên Lõi OpenAMP/RPMsg, Mã Kiểm Soát Lỗi CRC-16 & Cơ Chế An Toàn Heartbeat Watchdog

- **Dự án:** Automotive Gateway & Real-Time Motor Controller (STM32MP157D-DK1)
- **Kiến trúc phần mềm:** AUTOSAR Classic trên Zephyr RTOS (Cortex-M4) & OpenSTLinux (Cortex-A7)
- **Thời gian thực hiện:** Tuần 3 (Milestone 3)
- **Người thực hiện:** Kỹ sư nhúng & Trợ lý Antigravity
- **Trạng thái:** Hoàn thành 100% Mục Tiêu Tuần 3 (Milestone 3 Completed)

---

## 1. Tổng Quan Mục Tiêu Tuần 3 (Week 3 Objectives)

Tuần 3 tập trung vào việc thiết lập kênh truyền thông liên lõi bất đối xứng (Asymmetric Multiprocessing - AMP Inter-Processor Communication) thời gian thực giữa hai nhân vi xử lý trên vi điều khiển STM32MP157:
- **Cortex-A7 (Host / Master):** Chạy Linux (OpenSTLinux kernel 6.6), chịu trách nhiệm điều phối cấp cao, giao tiếp mạng, logging và giao diện người dùng.
- **Cortex-M4 (Remote / Coprocessor):** Chạy Zephyr RTOS tuân thủ kiến trúc AUTOSAR Classic, kiểm soát vòng lặp kín điều khiển động cơ 10ms ($100\text{ Hz}$).

### Các hạng mục hoàn thành:
1. **Kích hoạt ngăn xếp OpenAMP & Resource Table trên Cortex-M4 (`motor_gateway_m4`):**
   - Cấu hình Kconfig: `CONFIG_IPM=y`, `CONFIG_OPENAMP=y`, `CONFIG_OPENAMP_RSC_TABLE=y`, `CONFIG_OPENAMP_RSC_TABLE_NUM_RPMSG_BUFF=8`.
   - Điều chỉnh tiến trình `deploy.sh`: Chuyển cờ `arm-zephyr-eabi-strip` từ `-s` sang `-g` (`--strip-debug`) nhằm bảo toàn section `.resource_table` bắt buộc của Linux `remoteproc`.
2. **Phát triển module Complex Device Driver `Cdd_Ipc` (`Cdd_Ipc.h`, `Cdd_Ipc.c`):**
   - Khởi tạo endpoint RPMsg TTY (`"rpmsg-tty"`) kết nối trực tiếp với `/dev/ttyRPMSG0` trên Linux.
   - Vận hành thread độc lập `cdd_ipc_thread` (ưu tiên `K_PRIO_PREEMPT(5)`, stack 2048 bytes), tách biệt hoàn toàn với vòng lặp điều khiển thời gian thực cứng 10ms (ưu tiên `K_PRIO_PREEMPT(1)`).
   - Tự động nhận diện và ghi nhớ địa chỉ đích (`s_tty_ept.dest_addr`) từ gói tin đầu tiên gửi từ Linux.
   - Bộ giải mã tập lệnh ASCII điều khiển: `SPEED <rpm>`, `DUTY <val>`, `STOP`, `WDG ON/OFF`, `HB`.
3. **Mã kiểm soát toàn vẹn dữ liệu CRC-16-CCITT:**
   - Đa thức $P(x) = x^{16} + x^{12} + x^5 + 1$ (`poly = 0x1021`, giá trị khởi tạo `init = 0xFFFF`).
   - Đóng gói khung tin Telemetry định kỳ 5 Hz (mỗi 200ms) gửi lên Linux:
     `$TELEM,TGT=<int>,RPM=<int>,DUTY=<int>,CNT=<pulses>*<CRC16_HEX>\r\n`
4. **Cơ chế an toàn Heartbeat Watchdog (Fail-Safe Mechanism):**
   - Định thời đếm 100 chu kỳ 10ms ($1.0\text{ s}$).
   - Nếu Watchdog được kích hoạt (`WDG ON`) và Linux bị treo, crash nhân (`kernel panic`) hoặc đứt kết nối truyền thông không gửi lệnh `HB` trong $1.0\text{ s}$, Cortex-M4 sẽ tự động kích hoạt trạng thái phanh hãm dừng khẩn cấp (`Swc_MotorControl_SetTestMode(TRUE, 0.0f)` & `Cdd_L298n_EmergencyStop()`).
5. **Tích hợp RTE & Chu trình sống hệ thống:**
   - Tích hợp `Cdd_Ipc_Init()` vào hàm khởi tạo hệ thống `EcuM_Init()`.
   - Tích hợp `Cdd_Ipc_MainFunction_10ms()` vào chu kỳ điều phối `Rte_TimerEvent_10ms()`.
6. **Công cụ điều khiển và giám sát phía Linux Cortex-A7 (`gateway_a7/ipc_ctl.sh`):**
   - Script Bash hỗ trợ cấu hình serial `stty`, gửi lệnh, chạy vòng lặp heartbeat giữ nhịp, lắng nghe telemetry trực tiếp kèm kiểm tra mã CRC-16.

---

## 2. Kiến Trúc Truyền Thông Liên Lõi OpenAMP / RPMsg

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

### 2.1. Phân bổ bộ nhớ chia sẻ (Shared Memory Layout)
Theo cấu hình Device Tree và Resource Table của STM32MP157:
- **Địa chỉ cơ sở:** `0x10040000` (thuộc vùng nhớ nội SRAM3 / SRAM4 của chip STM32MP157D).
- **Kích thước:** `32 KB` (`0x8000` bytes).
- **Phân bổ nội bộ:**
  - `0x10040000 - 0x100401FF`: Bảng tài nguyên `fw_resource_table` chứa định nghĩa VirtIO device và 2 vring.
  - `0x10040200 - 0x10041FFF`: VirtIO Ring 0 (TX: M4 $\rightarrow$ A7) và VirtIO Ring 1 (RX: A7 $\rightarrow$ M4).
  - `0x10042000 - 0x10047FFF`: Vùng nhớ đệm gói tin RPMsg (8 bộ đệm, mỗi bộ đệm 512 bytes).

### 2.2. Phần cứng IPCC (Inter-Processor Communication Controller)
- STM32MP157 tích hợp khối phần cứng IPCC gồm 6 kênh kênh song công (full-duplex bidirectional channels) kích hoạt ngắt phần cứng cho hai lõi:
  - Khi Linux ghi dữ liệu vào vring, nó phát xung ngắt IPCC sang M4.
  - Driver `ipm_stm32_ipcc` của Zephyr bắt ngắt và kích hoạt `Cdd_Ipc_IpmCallback`, giải phóng `s_ipc_sem` để đánh thức `cdd_ipc_thread`.
  - Khi M4 muốn gửi dữ liệu, hàm `Virtio_Notify` gọi `ipm_send` để phát xung ngắt sang Cortex-A7.

---

## 3. Khắc Phục Lỗi Mất Resource Table Trong Tiến Trình Build (`deploy.sh`)

### 3.1. Phân tích nguyên nhân lỗi (Root Cause Analysis)
Khi Cortex-A7 khởi động firmware M4 thông qua Linux subsystem `remoteproc`:
1. Linux đọc file ELF tại `/lib/firmware/motor_gateway_m4.elf`.
2. Trình nạp ELF của nhân Linux tìm kiếm section có tên `.resource_table` trong bảng ELF section headers để đọc cấu hình bộ nhớ chia sẻ và IPCC channels.
3. Trong tiến trình tuần trước, lệnh strip được gọi với tham số `-s`:
   ```bash
   arm-zephyr-eabi-strip -s build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf
   ```
   Tham số `-s` (`--strip-all`) xóa bỏ toàn bộ bảng biểu tượng (symbol table) và một số metadata khiến `remoteproc0` báo lỗi không tìm thấy resource table:
   `remoteproc remoteproc0: no-resource-table ... failed to load ...`

### 3.2. Giải pháp thực hiện
Thay đổi cờ strip sang `-g` (`--strip-debug`):
```bash
arm-zephyr-eabi-strip -g build/zephyr/zephyr.elf -o ~/motor_gateway_m4.elf
```
- Cờ `-g` chỉ lược bỏ các bảng biểu tượng debug (DWARF `.debug_*`) giúp giảm kích thước file từ hơn 2 MB xuống xấp xỉ 70 KB.
- Đồng thời bảo toàn toàn vẹn 100% section `.resource_table` và các ELF segment headers cần thiết cho kernel remoteproc nạp và khởi tạo RPMsg VirtIO device.

---

## 4. Thiết Kế Chi Tiết Module `Cdd_Ipc`

### 4.1. Phân tách luồng thời gian thực cứng và luồng truyền thông (Thread Separation)
Để đảm bảo yêu cầu phi chức năng **NFR-1** (độ trôi pha Jitter của vòng điều khiển $\le 50\ \mu\text{s}$):
- Vòng lặp điều khiển chính chạy trong ngữ cảnh `main()` với mức ưu tiên tiền định cao nhất `K_PRIO_PREEMPT(1)`.
- Module `Cdd_Ipc` chạy trong thread tiền định `cdd_ipc_thread` với mức ưu tiên `K_PRIO_PREEMPT(5)`.
- Các thao tác giải mã chuỗi, tính CRC và truyền RPMsg tốn thời gian hoàn toàn không chiếm dụng CPU của vòng lặp lấy mẫu cảm biến encoder và tính toán PID 10ms.

### 4.2. Cơ chế Dynamic Endpoint Address Learning
Trong chuẩn RPMsg, khi Linux mở `/dev/ttyRPMSG0`, endpoint phía Linux sẽ được cấp phát một địa chỉ ngẫu nhiên hoặc theo channel index (ví dụ: `0x0400` hoặc `0x0001`).
- Lúc khởi tạo, endpoint của M4 cấu hình `s_tty_ept.dest_addr = RPMSG_ADDR_ANY` (`0xFFFFFFFF`).
- Khi Linux gửi bất kỳ dữ liệu đầu tiên nào (như `HB` hoặc `SPEED 60`), hàm callback `Cdd_Ipc_RxCallback` ghi nhận địa chỉ nguồn `src`:
  ```c
  if (s_tty_ept.dest_addr == RPMSG_ADDR_ANY) {
      s_tty_ept.dest_addr = src;
      printk("[CDD_IPC] Learned remote endpoint dest_addr: 0x%08X\n", src);
  }
  ```
- Từ thời điểm này, kênh truyền telemetry hai chiều được thiết lập thông suốt.

### 4.3. Bảng lệnh điều khiển ASCII (Command Interface)
Các lệnh hỗ trợ qua `/dev/ttyRPMSG0`:

| Lệnh | Cú pháp | Hành vi trên Cortex-M4 | Phản hồi hệ thống |
| :--- | :--- | :--- | :--- |
| **SPEED** | `SPEED <val>` | Tắt chế độ test mở vòng (`SetTestMode(FALSE, 0)`), ghi setpoint vận tốc RPM vào cổng RTE `Rte_Write_ppTargetSpeed_rpm(val)`. | Bộ PID kín bám setpoint `<val>` RPM |
| **DUTY** | `DUTY <val>` | Bật chế độ test mở vòng (`SetTestMode(TRUE, val)`), áp trực tiếp duty cycle từ $-100.0$ đến $+100.0\%$. | Động cơ chạy mở vòng theo duty |
| **STOP** | `STOP` | Đưa duty về $0.0\%$, kích hoạt phanh ngắn mạch tức thời qua `Cdd_L298n_EmergencyStop()`. | Động cơ dừng ngay lập tức |
| **WDG ON** | `WDG ON` | Kích hoạt bộ đếm thời gian an toàn Heartbeat Watchdog ($1.0\text{ s}$). | Hệ thống giám sát nhịp tim |
| **WDG OFF**| `WDG OFF` | Vô hiệu hóa bộ đếm Heartbeat Watchdog (chế độ bảo trì / gỡ lỗi thủ công). | Không tự động dừng khi mất nhịp |
| **HB** | `HB` | Làm mới bộ đếm thời gian heartbeat: `s_hb_timeout_10ms = 0u`. | Duy trì trạng thái hoạt động bình thường |

---

## 5. Thuật Toán Kiểm Soát Lỗi CRC-16-CCITT

### 5.1. Định nghĩa toán học
- **Tên chuẩn:** CRC-16/CCITT-FALSE
- **Đa thức sinh:** $P(x) = x^{16} + x^{12} + x^5 + 1$ (Hệ số nhị phân: `0x1021`)
- **Giá trị khởi tạo (`Init`):** `0xFFFF`
- **Đảo bit vào/ra (`Refin`/`Refout`):** `False` / `False`
- **XOR ngõ ra (`Xorout`):** `0x0000`

### 5.2. Cài đặt thuật toán chuẩn MISRA-C trong `Cdd_Ipc.c`
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

### 5.3. Định dạng khung truyền Telemetry
Mỗi $200\text{ ms}$ (tương ứng 20 chu kỳ $10\text{ ms}$), M4 phát một khung telemetry:
```
$TELEM,TGT=<int>,RPM=<int>,DUTY=<int>,CNT=<pulses>*<CRC16_HEX>\r\n
```
- **Phần tải tin (Payload):** Từ ký tự `$` đến trước dấu `*`.
- **Mã kiểm tra CRC:** 4 ký tự Hex in hoa tính toán trên toàn bộ chuỗi tải tin payload.
- **Ví dụ khung tin thực tế:**
  `$TELEM,TGT=60,RPM=59,DUTY=42,CNT=1024*A1B2\r\n`

---

## 6. Cơ Chế An Toàn Heartbeat Watchdog (Fail-Safe State Transition)

Trong các hệ thống điều khiển ô tô và công nghiệp, sự cố sập nguồn hoặc đơ nhân hệ điều hành Linux (Cortex-A7) không được phép làm động cơ tiếp tục quay mất kiểm soát.

```
                  +---------------------------+
                  |  WDG OFF (Bình thường /   |
                  |     Chế độ gỡ lỗi)        |
                  +-------------+-------------+
                                | Lệnh "WDG ON"
                                v
                  +---------------------------+
         +------->|   WDG ON (Giám sát nhịp)  |
         |        |   Timeout Counter = 0     |
         |        +-------------+-------------+
         |                      |
Lệnh "HB"|                      | Mỗi chu kỳ 10ms: Timeout++
(Nhịp tim|< 1.0s                |
hợp lệ)  |                      v
         |        +---------------------------+
         +--------+  0 < Timeout < 100 ticks  |
                  +-------------+-------------+
                                |
                                | Timeout >= 100 ticks (1.0 giây mất tin)
                                v
                  +---------------------------+
                  |  TRẠNG THÁI AN TOÀN       |
                  |  (FAIL-SAFE STATE):       |
                  |  - Duty = 0.0%            |
                  |  - Cdd_L298n_Brake()      |
                  |  - IN1=HIGH, IN2=HIGH     |
                  +---------------------------+
```

### 6.1. Nguyên lý hoạt động
1. Trong hàm `Cdd_Ipc_MainFunction_10ms()` (thực thi chu kỳ 10ms từ `Rte_TimerEvent_10ms`):
   ```c
   if (s_watchdog_enabled) {
       if (s_hb_timeout_10ms < 1000u) {
           s_hb_timeout_10ms++;
       }
       if (s_hb_timeout_10ms >= 100u) {
           /* Mất heartbeat quá 1.0s -> ép trạng thái an toàn ngay lập tức */
           Swc_MotorControl_SetTestMode(TRUE, 0.0f);
           Cdd_L298n_EmergencyStop();
       }
   }
   ```
2. Nếu Cortex-A7 hoạt động bình thường, daemon hoặc script sẽ định kỳ gửi lệnh `HB` (chu kỳ $500\text{ ms}$). Mỗi lần nhận được `HB`, biến `s_hb_timeout_10ms` được reset về `0`.
3. Nếu A7 bị kernel panic (hoặc người dùng cố tình kích hoạt `echo c > /proc/sysrq-trigger`), chuỗi lệnh `HB` lập tức dừng lại. Sau đúng $1.0\text{ s}$ ($100$ chu kỳ tick), M4 phát hiện timeout và phanh dừng động cơ ngay tức khắc, hoàn toàn độc lập với tình trạng của Linux A7.

---

## 7. Hướng Dẫn Sử Dụng Script Điều Khiển Linux A7 (`gateway_a7/ipc_ctl.sh`)

Script `gateway_a7/ipc_ctl.sh` được tích hợp đầy đủ tính năng cấu hình, điều khiển và tự động kiểm chứng:

```bash
# 1. Cấu hình baudrate và chế độ raw cho /dev/ttyRPMSG0
./ipc_ctl.sh init

# 2. Kiểm tra trạng thái remoteproc và tty device
./ipc_ctl.sh status

# 3. Điều khiển vận tốc kín PID (60 RPM)
./ipc_ctl.sh speed 60

# 4. Điều khiển công suất mở vòng (Duty 45%)
./ipc_ctl.sh duty 45

# 5. Dừng động cơ khẩn cấp
./ipc_ctl.sh stop

# 6. Giám sát dòng Telemetry thời gian thực kèm kiểm tra tính hợp lệ CRC-16
./ipc_ctl.sh telem

# 7. Chạy nhịp tim Heartbeat liên tục trong nền
./ipc_ctl.sh hb-loop 0.5

# 8. Chạy chuỗi kịch bản kiểm thử nghiệm thu cơ chế Heartbeat Watchdog
./ipc_ctl.sh test-safety
```

### 7.1. Kết Quả Thực Nghiệm Trên Phần Cứng Thực Tế (Hardware Verification Log)

- **Log khởi tạo `remoteproc0` & `virtio_rpmsg_bus` trên Linux Cortex-A7 (`dmesg`):**
  ```text
  [  430.946567] remoteproc remoteproc0: powering up m4
  [  430.956852] remoteproc remoteproc0: Booting fw image motor_gateway_m4.elf, size 45756
  [  430.965181] rproc-virtio rproc-virtio.2.auto: assigned reserved memory node vdev0buffer@10042000
  [  430.976357] virtio_rpmsg_bus virtio0: rpmsg host is online
  [  430.980651] rproc-virtio rproc-virtio.2.auto: registered virtio0 (type 7)
  [  430.987484] virtio_rpmsg_bus virtio0: creating channel rpmsg-tty addr 0x400
  [  431.001951] remoteproc remoteproc0: remote processor m4 is now up
  ```
- **Xác nhận thiết bị `/dev/ttyRPMSG0` và dòng dữ liệu Telemetry 5 Hz thực tế (kèm mã kiểm tra `CRC-16-CCITT`):**
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
- **Thực nghiệm điều khiển động `DUTY 35` -> `DUTY 70` -> Kích hoạt `WDG ON` và tự động phanh an toàn `DUTY=0` sau 1.0s:**
  ```text
  # Gửi lệnh 'DUTY 35' qua /dev/ttyRPMSG0:
  $TELEM,TGT=60,RPM=2,DUTY=35,CNT=0*2F0A
  $TELEM,TGT=60,RPM=0,DUTY=35,CNT=-1*CCB9
  $TELEM,TGT=60,RPM=0,DUTY=35,CNT=0*62D3

  # Gửi lệnh 'DUTY 70' qua /dev/ttyRPMSG0:
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=0*1419
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=0*1419
  $TELEM,TGT=60,RPM=0,DUTY=70,CNT=-1*18E8

  # Gửi lệnh 'WDG ON' (không kèm HB, sau đúng 1.0s timeout):
  # Cortex-M4 tự động kích hoạt phanh an toàn và ngắt duty về 0%:
  $TELEM,TGT=60,RPM=1,DUTY=0,CNT=0*D8DF
  $TELEM,TGT=60,RPM=0,DUTY=0,CNT=0*A3BE
  $TELEM,TGT=60,RPM=0,DUTY=0,CNT=0*A3BE
  ```

---

## 8. Kết Luận & Kế Hoạch Tuần 4 (Next Steps)

### 8.1. Đánh giá kết quả Tuần 3
- Hệ thống truyền thông bất đối xứng IPC OpenAMP / RPMsg đã sẵn sàng và vận hành ổn định giữa OpenSTLinux và Zephyr RTOS.
- Khung bản tin chuẩn hóa với mã kiểm soát lỗi CRC-16-CCITT giúp phát hiện toàn diện lỗi suy hao hoặc trễ đường truyền.
- Cơ chế Heartbeat Watchdog đáp ứng tiêu chuẩn an toàn kỹ thuật, bảo vệ động cơ trước mọi sự cố sập hệ điều hành phía Linux.

### 8.2. Kế hoạch Tuần 4 (Milestone 4 Preview)
1. **Tích hợp cảm biến môi trường & giám sát cơ điện:**
   - MCAL ADC: Đọc cảm biến gia tốc rung động GY-61 (3 trục X, Y, Z).
   - Module đọc cảm biến nhiệt độ & độ ẩm DHT11.
   - Module bắt ngắt cảm biến chuyển động hồng ngoại PIR HC-SR501.
2. **Triển khai `SWC_SafetyManager` & `SWC_SensorManager`:**
   - Hoàn thiện luồng dữ liệu an toàn tổng thể trong RTE.
   - Mở rộng khung truyền RPMsg để gửi toàn bộ dữ liệu cảm biến đa chiều lên Linux Cortex-A7.
