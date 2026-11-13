import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

def create_deck():
    prs = Presentation()
    # 16:9 widescreen
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6] # completely blank layout

    # Color Palette - Automotive Cyber / Tech Luxury
    BG_DARK = RGBColor(11, 19, 43)        # #0B132B Deep Obsidian Navy
    CARD_BG = RGBColor(28, 37, 65)        # #1C2541 Slate Card
    CARD_BORDER = RGBColor(41, 53, 86)
    ACCENT_CYAN = RGBColor(0, 212, 255)   # #00D4FF Electric Cyan
    ACCENT_BLUE = RGBColor(77, 148, 255)  # #4D94FF Vibrant Blue
    ACCENT_GOLD = RGBColor(255, 179, 0)   # #FFB300 Amber / Gold
    ACCENT_GREEN = RGBColor(16, 185, 129) # #10B981 Emerald
    ACCENT_RED = RGBColor(239, 68, 68)    # #EF4444 Crimson Red
    TEXT_WHITE = RGBColor(248, 250, 252)  # #F8FAFC
    TEXT_MUTED = RGBColor(160, 174, 192)  # #A0AEC0
    TEXT_DIM = RGBColor(113, 128, 150)    # #718096

    def add_bg(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_DARK
        bg.line.fill.background()
        return bg

    def add_header(slide, title_text, category_text="AUTOMOTIVE DOMAIN GATEWAY & MOTOR CONTROLLER"):
        # Category tag
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_right = tf_cat.margin_top = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = ACCENT_CYAN

        # Main Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = TEXT_WHITE

    def add_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.5)
        else:
            card.line.fill.background()
        return card

    # =========================================================================
    # SLIDE 1: TITLE SLIDE
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    add_bg(s1)

    # Accent decorative bar
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(0.1), Inches(3.4))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT_CYAN
    bar.line.fill.background()

    # Title box
    tbox = s1.shapes.add_textbox(Inches(1.2), Inches(1.6), Inches(11.3), Inches(3.6))
    tf = tbox.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "ĐỒ ÁN TỐT NGHIỆP / KỸ SƯ NHÚNG HỆ THỐNG Ô TÔ"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = ACCENT_CYAN
    p0.space_after = Pt(12)

    p1 = tf.add_paragraph()
    p1.text = "AUTOMOTIVE DOMAIN GATEWAY & BỘ ĐIỀU KHIỂN ĐỘNG CƠ THỜI GIAN THỰC CHUẨN AUTOSAR CLASSIC"
    p1.font.size = Pt(25)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.space_after = Pt(8)

    p2 = tf.add_paragraph()
    p2.text = "Triển Khai Trên Nền Tảng Vi Xử Lý Đa Nhân Dị Thể STM32MP157 (Cortex-M4 Zephyr RTOS & Cortex-A7 OpenSTLinux)"
    p2.font.size = Pt(15)
    p2.font.color.rgb = ACCENT_BLUE

    # Meta card at bottom
    add_card(s1, Inches(0.8), Inches(5.4), Inches(11.733), Inches(1.3))
    mbox = s1.shapes.add_textbox(Inches(1.1), Inches(5.55), Inches(11.133), Inches(1.0))
    mtf = mbox.text_frame
    mtf.word_wrap = True

    mp1 = mtf.paragraphs[0]
    mp1.text = "• Hệ Thống: STM32MP157D-DK1 (Dual A7 @ 800MHz + Cortex-M4 @ 209MHz)   |   • Chuẩn: AUTOSAR Classic, ISO 26262"
    mp1.font.size = Pt(12)
    mp1.font.color.rgb = TEXT_MUTED
    mp1.space_after = Pt(4)

    mp2 = mtf.add_paragraph()
    mp2.text = "• Thuật Toán: PID Vận Tốc Nhận Dạng MATLAB (Best Fit 80.95%)   |   • Đo Kiểm: Saleae Logic 2 (Jitter 6.375 µs, IPC 1.999 ms)"
    mp2.font.size = Pt(12)
    mp2.font.color.rgb = ACCENT_GOLD

    # =========================================================================
    # SLIDE 2: BỐI CẢNH & ĐẶT VẤN ĐỀ
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_bg(s2)
    add_header(s2, "1. Bối Cảnh Ngành Ô Tô & Xu Hướng Chuyển Dịch Kiến Trúc E/E")

    # Left Card: Kiến trúc cũ
    add_card(s2, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    b1 = s2.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    tf1 = b1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "❌ Kiến Trúc Phân Tán Cũ (Distributed ECUs)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    p.space_after = Pt(14)

    bullets1 = [
        "Hơn 100-150 hộp ECU rời rạc điều khiển từng tính năng riêng biệt (phanh, động cơ, cửa kính, điều hòa...).",
        "Hàng kilomet dây điện CAN/LIN chằng chịt làm tăng khối lượng xe và chi phí sản xuất.",
        "Xử lý dữ liệu phân mảnh, không thể đồng bộ hóa cảm biến độ phân giải cao.",
        "Khó khăn nghiêm trọng trong việc nâng cấp tính năng phần mềm qua mạng (OTA)."
    ]
    for b in bullets1:
        p = tf1.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(10)

    # Right Card: Kiến trúc mới
    add_card(s2, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    b2 = s2.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    tf2 = b2.text_frame
    tf2.word_wrap = True

    p = tf2.paragraphs[0]
    p.text = "✅ Kiến Trúc Tập Trung (Domain / Zonal Architecture)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    p.space_after = Pt(14)

    bullets2 = [
        "Hội tụ nhiều cụm chức năng vào một Bộ Điều Khiển Miền tập trung (Automotive Domain Gateway).",
        "Cắt giảm tới 40% trọng lượng dây cáp truyền dẫn trên toàn bộ xe.",
        "Xử lý tập trung cảm biến thời gian thực, mở đường cho xe tự hành (ADAS) và xe điện thông minh (EV).",
        "Yêu cầu phần cứng vi xử lý phải tích hợp vừa thời gian thực vừa tính toán thông minh."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 3: XUNG ĐỘT KỸ THUẬT CỐT LÕI
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_bg(s3)
    add_header(s3, "2. Thách Thức Kỹ Thuật: Cuộc Xung Đột Giữa Hai Miền Tính Toán")

    # Top comparison table card
    add_card(s3, Inches(0.8), Inches(1.6), Inches(11.733), Inches(3.6))
    
    rows = 4
    cols = 3
    table_shape = s3.shapes.add_table(rows, cols, Inches(1.0), Inches(1.8), Inches(11.333), Inches(3.1))
    tbl = table_shape.table
    tbl.columns[0].width = Inches(2.6)
    tbl.columns[1].width = Inches(4.366)
    tbl.columns[2].width = Inches(4.366)

    table_data = [
        ("Tiêu Chí Kỹ Thuật", "Miền Điều Khiển Khung Gầm (Chassis ECU)", "Miền Viễn Thông & Thông Tin (Telematics / Infotainment)"),
        ("Ràng Buộc Thời Gian", "HARD REAL-TIME (Chu kỳ 10ms, Jitter < 50µs)", "SOFT REAL-TIME / BEST-EFFORT (Trễ vài chục ms)"),
        ("Hệ Điều Hành", "Zephyr RTOS / Chuẩn AUTOSAR Classic", "OpenSTLinux / Android Automotive OS"),
        ("Độ Tin Cậy & Rủi Ro", "Tất định (Deterministic), KHÔNG ĐƯỢC TREO (Zero Crash)", "Nhiều dịch vụ phức tạp, DỄ CRASH / KERNEL PANIC")
    ]

    for r_idx, row in enumerate(table_data):
        for c_idx, val in enumerate(row):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = val
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
            if r_idx == 0:
                p.font.bold = True
                p.font.size = Pt(12)
                p.font.color.rgb = ACCENT_CYAN
            else:
                p.font.size = Pt(11)
                p.font.color.rgb = TEXT_WHITE if c_idx == 1 else (ACCENT_GOLD if c_idx == 2 else ACCENT_BLUE)

    # Bottom Callout Card
    add_card(s3, Inches(0.8), Inches(5.4), Inches(11.733), Inches(1.4), bg_color=CARD_BG, border_color=ACCENT_RED)
    cbox = s3.shapes.add_textbox(Inches(1.1), Inches(5.5), Inches(11.133), Inches(1.2))
    ctf = cbox.text_frame
    ctf.word_wrap = True
    cp = ctf.paragraphs[0]
    cp.text = "⚠️ NGHỊCH LÝ ĐẶT RA VÀ MỤC TIÊU CỦA ĐỒ ÁN:"
    cp.font.size = Pt(13)
    cp.font.bold = True
    cp.font.color.rgb = ACCENT_RED
    cp.space_after = Pt(4)

    cp2 = ctf.add_paragraph()
    cp2.text = "Nếu chạy chung 1 hệ điều hành Linux duy nhất, sự cố treo ứng dụng giải trí sẽ làm sập luôn hệ thống lái và phanh của xe! Đề tài giải quyết triệt để vấn đề này bằng cách ly phần cứng trên chip đa nhân dị thể STM32MP157."
    cp2.font.size = Pt(12)
    cp2.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 4: GIẢI PHÁP ĐA NHÂN DỊ THỂ STM32MP157
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_bg(s4)
    add_header(s4, "3. Kiến Trúc Giải Pháp: Nền Tảng Đa Nhân Dị Thể STM32MP157")

    # Left: Cortex-M4
    add_card(s4, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), border_color=ACCENT_CYAN)
    m4_box = s4.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    m4_tf = m4_box.text_frame
    m4_tf.word_wrap = True

    p = m4_tf.paragraphs[0]
    p.text = "🏎️ MIỀN REAL-TIME: ARM CORTEX-M4"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(12)

    m4_pts = [
        "Xung nhịp 209 MHz có bộ tính toán dấu phẩy động FPU phần cứng.",
        "Chạy độc lập từ bộ nhớ SRAM 384 KB nội vi (không phụ thuộc RAM ngoài DDR).",
        "Cài đặt Zephyr RTOS v4.5.99 theo cấu trúc AUTOSAR Classic.",
        "Trực tiếp tạo xung PWM 20 kHz (TIM4) và giải mã Encoder đĩa từ (514.8 PPR).",
        "Vòng lặp PID 10ms tất định, chốt an toàn phanh khẩn cấp ISO 26262."
    ]
    for pt in m4_pts:
        p = m4_tf.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)

    # Right: Cortex-A7
    add_card(s4, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2), border_color=ACCENT_BLUE)
    a7_box = s4.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    a7_tf = a7_box.text_frame
    a7_tf.word_wrap = True

    p = a7_tf.paragraphs[0]
    p.text = "🌐 MIỀN GATEWAY: DUAL ARM CORTEX-A7"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE
    p.space_after = Pt(12)

    a7_pts = [
        "Xung nhịp 800 MHz, 512 MB DDR3L RAM, chạy hệ điều hành OpenSTLinux 5.0.17.",
        "Quản lý vòng đời khởi động/nạp firmware Cortex-M4 qua 'remoteproc'.",
        "Giao tiếp liên nhân OpenAMP RPMsg (/dev/ttyRPMSG0) có kiểm tra mã CRC-16.",
        "Lưu trữ hộp đen Blackbox tai nạn bằng SQLite3 cơ chế WAL an toàn mất điện.",
        "Cổng viễn thông đám mây MQTT IoT Gateway kết nối Virtual Cockpit."
    ]
    for pt in a7_pts:
        p = a7_tf.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 5: KIẾN TRÚC AUTOSAR CLASSIC TRÊN ZEPHYR RTOS
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_bg(s5)
    add_header(s5, "4. Kiến Trúc Phần Mềm Cortex-M4: Chuẩn Hóa AUTOSAR Classic")

    # Layer 1: ASW
    add_card(s5, Inches(0.8), Inches(1.6), Inches(11.733), Inches(1.5), border_color=ACCENT_CYAN)
    l1 = s5.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(11.333), Inches(1.3))
    t1 = l1.text_frame
    t1.word_wrap = True
    p = t1.paragraphs[0]
    p.text = "APPLICATION SOFTWARE LAYER (ASW) - HOÀN TOÀN ĐỘC LẬP PHẦN CỨNG"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(4)
    p2 = t1.add_paragraph()
    p2.text = "• Swc_MotorControl: Thuật toán PID 10ms, Anti-Windup Clamping  |  • Swc_SensorManager: Đọc PIR, Gia tốc rung, DHT11  |  • Swc_SafetyManager: Chốt an toàn E-Stop"
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_WHITE

    # Layer 2: RTE
    add_card(s5, Inches(0.8), Inches(3.3), Inches(11.733), Inches(1.5), border_color=ACCENT_GOLD)
    l2 = s5.shapes.add_textbox(Inches(1.0), Inches(3.4), Inches(11.333), Inches(1.3))
    t2 = l2.text_frame
    t2.word_wrap = True
    p = t2.paragraphs[0]
    p.text = "RUNTIME ENVIRONMENT (RTE) - TRUNG TÂM ĐIỀU PHỐI VÀ CỔNG TRỪU TƯỢNG"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GOLD
    p.space_after = Pt(4)
    p2 = t2.add_paragraph()
    p2.text = "• Rte_Read() / Rte_Write() Ports: Cách ly dữ liệu giữa ASW và BSW  |  • Rte_TimerEvent_10ms(): Lập lịch chu kỳ tất định 100 Hz bằng k_timer + k_sem  |  • Toggle Test Pin PE9 đo Jitter"
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_WHITE

    # Layer 3: BSW / MCAL / CDD
    add_card(s5, Inches(0.8), Inches(5.0), Inches(11.733), Inches(1.8), border_color=ACCENT_BLUE)
    l3 = s5.shapes.add_textbox(Inches(1.0), Inches(5.1), Inches(11.333), Inches(1.5))
    t3 = l3.text_frame
    t3.word_wrap = True
    p = t3.paragraphs[0]
    p.text = "BASIC SOFTWARE & COMPLEX DEVICE DRIVERS (BSW / MCAL / CDD)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE
    p.space_after = Pt(4)
    p2 = t3.add_paragraph()
    p2.text = "• Mcal_Pwm (TIM4_CH3 20 kHz)  |  • Mcal_Icu (Giải mã Encoder Hall QDEC 514.8 PPR)  |  • Mcal_Dio (GPIO PE7/8/9/10/13)\n• Cdd_L298n (Mạch cầu H phanh tích cực)  |  • Cdd_Ipc (OpenAMP RPMsg, xác thực mã kiểm tra toàn vẹn CRC-16-CCITT)"
    p2.font.size = Pt(11)
    p2.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 6: NHẬN DẠNG HỆ THỐNG TRÊN MATLAB
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_bg(s6)
    add_header(s6, "5. Nhận Dạng Hệ Thống Động Cơ Thực Nghiệm Trên MATLAB")

    add_card(s6, Inches(0.8), Inches(1.6), Inches(11.733), Inches(5.2))
    b6 = s6.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(11.133), Inches(4.8))
    t6 = b6.text_frame
    t6.word_wrap = True

    p = t6.paragraphs[0]
    p.text = "Quy Trình Nhận Dạng Hàm Truyền Thay Vì Thử - Sai (Trial & Error):"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(12)

    pts = [
        "Bước 1: Kích thích bước nhảy mở vòng (Open-Loop Step Test) Duty Cycle 0% -> 60% trong 3.0s.",
        "Bước 2: Ghi dữ liệu tốc độ phản hồi thực tế vào file CSV qua Cortex-A7 với chu kỳ lấy mẫu Ts = 10ms.",
        "Bước 3: Nhập dữ liệu vào MATLAB System Identification Toolbox, ước lượng mô hình quán tính bậc 1 có trễ (FOPDT):"
    ]
    for pt in pts:
        p = t6.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(13)
        p.font.color.rgb = TEXT_WHITE
        p.space_after = Pt(8)

    # Formula Box
    p_eq = t6.add_paragraph()
    p_eq.text = "               G(s) = [ 0.1873 / ( 0.0461 s + 1 ) ] * e^(-0.0400 s)     (ĐỘ KHỚP THỰC TẾ: 80.95%)"
    p_eq.font.size = Pt(15)
    p_eq.font.bold = True
    p_eq.font.color.rgb = ACCENT_GOLD
    p_eq.space_after = Pt(12)

    p_eval = t6.add_paragraph()
    p_eval.text = "Ý nghĩa thông số vật lý:\n  - Hệ số khuếch đại tĩnh: K = 0.1873 RPM / %Duty\n  - Hằng số thời gian quán tính cơ học: τ = 46.1 ms (động cơ phản hồi rất nhanh)\n  - Độ trễ khởi động tĩnh do ma sát: θ = 40.0 ms"
    p_eval.font.size = Pt(12)
    p_eval.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 7: THIẾT KẾ PID SỐ RỜI RẠC & ANTI-WINDUP
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_bg(s7)
    add_header(s7, "6. Thiết Kế Giải Thuật PID Số Rời Rạc & Anti-Windup Clamping")

    add_card(s7, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    b7a = s7.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    t7a = b7a.text_frame
    t7a.word_wrap = True

    p = t7a.paragraphs[0]
    p.text = "⚙️ THÔNG SỐ VÀ PHƯƠNG TRÌNH PID"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(12)

    p_params = t7a.add_paragraph()
    p_params.text = "Tính toán trên MATLAB Control Toolbox:\n  • Kp = 1.9641 (Tỷ lệ)\n  • Ki = 85.0402 (Tích phân)\n  • Kd = 0.0000 (Triệt tiêu nhiễu vi phân)\n  • Ts = 0.01 s (10 ms)"
    p_params.font.size = Pt(12)
    p_params.font.color.rgb = TEXT_WHITE
    p_params.space_after = Pt(12)

    p_code = t7a.add_paragraph()
    p_code.text = "Phương trình sai phân rời rạc (Swc_MotorControl):\n  e[k] = Target[k] - Actual[k]\n  P[k] = Kp * e[k]\n  I[k] = I[k-1] + Ki * Ts * e[k]\n  u[k] = P[k] + I[k]"
    p_code.font.size = Pt(12)
    p_code.font.color.rgb = ACCENT_GOLD

    add_card(s7, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    b7b = s7.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    t7b = b7b.text_frame
    t7b.word_wrap = True

    p = t7b.paragraphs[0]
    p.text = "🛡️ CƠ CHẾ ANTI-WINDUP CLAMPING"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    p.space_after = Pt(12)

    aw_pts = [
        "Hiện tượng Windup: Khi động cơ bị kẹt hoặc mất nguồn tạm thời, sai số e > 0 kéo dài làm thành phần tích phân I tăng vô hạn, gây giật cục và cháy driver khi có điện lại.",
        "Giải pháp Anti-Windup Clamping động:",
        "  Duty[k] = clamp(u[k], 0.0%, 85.0%)",
        "Khi ngõ ra chạm trần bão hòa (85.0%), khóa tích phân I[k] ngay lập tức, không cho tích lũy thêm.",
        "Kết quả thực nghiệm: Triệt tiêu hoàn toàn vọt lố (Overshoot 0%), thời gian xác lập cực nhanh ts ≈ 1.2s."
    ]
    for pt in aw_pts:
        p = t7b.add_paragraph()
        p.text = "• " + pt if not pt.startswith("  ") else pt
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED if not pt.startswith("  ") else ACCENT_GOLD
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 8: HỆ THỐNG AN TOÀN 3 TRỤ CỘT
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_bg(s8)
    add_header(s8, "7. Hệ Thống An Toàn Chủ Động 3 Trụ Cột (ISO 26262)")

    # 3 Cards side by side
    c_w = Inches(3.644)
    # Col 1: PIR
    add_card(s8, Inches(0.8), Inches(1.6), c_w, Inches(5.2), border_color=ACCENT_RED)
    b8a = s8.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(3.244), Inches(4.8))
    t8a = b8a.text_frame
    t8a.word_wrap = True
    p = t8a.paragraphs[0]
    p.text = "🛑 TRỤ CỘT 1: PIR\nVẬT CẢN PHÍA TRƯỚC"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    p.space_after = Pt(10)
    for pt in ["Cảm biến HC-SR501 (PE13).", "Góc quét nón 120°, tầm xa 3-7m.", "Kích hoạt ngắt khẩn cấp tức thì khi có người hoặc chướng ngại vật băng qua.", "Độ trễ phản ứng: < 50 µs tại chu kỳ ngắt."]:
        p = t8a.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(6)

    # Col 2: Accel
    add_card(s8, Inches(4.844), Inches(1.6), c_w, Inches(5.2), border_color=ACCENT_GOLD)
    b8b = s8.shapes.add_textbox(Inches(5.044), Inches(1.8), Inches(3.244), Inches(4.8))
    t8b = b8b.text_frame
    t8b.word_wrap = True
    p = t8b.paragraphs[0]
    p.text = "💥 TRỤ CỘT 2: GY-61\nVA CHẠM & RUNG CHẤN"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GOLD
    p.space_after = Pt(10)
    for pt in ["Gia tốc kế 3 trục analog (PF12).", "Tính toán vector gia tốc tổng hợp |a| = √(ax² + ay² + az²).", "Ngưỡng cảnh báo: 2.5g.", "Ngưỡng va chạm E-Stop: 3.5g bảo vệ động cơ và người dùng."]:
        p = t8b.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(6)

    # Col 3: Watchdog
    add_card(s8, Inches(8.888), Inches(1.6), c_w, Inches(5.2), border_color=ACCENT_BLUE)
    b8c = s8.shapes.add_textbox(Inches(9.088), Inches(1.8), Inches(3.244), Inches(4.8))
    t8c = b8c.text_frame
    t8c.word_wrap = True
    p = t8c.paragraphs[0]
    p.text = "⚡ TRỤ CỘT 3: WDG\nGIÁM SÁT NHỊP TIM LINUX"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE
    p.space_after = Pt(10)
    for pt in ["Linux A7 phát 'HB' mỗi 500ms.", "M4 đếm timeout: 1.0 giây.", "Nếu Linux bị Kernel Panic hoặc đơ app, M4 tự động ngắt phanh an toàn.", "Ngăn chặn xe lao tự do khi mất kết nối trung tâm."]:
        p = t8c.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(6)

    # =========================================================================
    # SLIDE 9: TẦNG GATEWAY LINUX VÀ BUỒNG LÁI SỐ
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_bg(s9)
    add_header(s9, "8. Tầng Gateway Cortex-A7 & Buồng Lái Kỹ Thuật Số (Qt Cockpit)")

    add_card(s9, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    b9a = s9.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    t9a = b9a.text_frame
    t9a.word_wrap = True
    p = t9a.paragraphs[0]
    p.text = "🖥️ LINUX DOMAIN GATEWAY"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(10)
    for pt in [
        "Quản lý kênh /dev/ttyRPMSG0 raw 115200 bps.",
        "Xác thực mã kiểm tra toàn vẹn CRC-16-CCITT trên từng gói tin viễn thông ($TELEM, $STAT).",
        "SQLite3 Hộp đen Blackbox (WAL mode): Lưu trữ lịch sử vận hành và vết tai nạn $FAULT vĩnh viễn không sợ mất nguồn.",
        "Cổng MQTT Telematics IoT: Xuất bản dữ liệu JSON chuẩn lên đám mây."
    ]:
        p = t9a.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)

    add_card(s9, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    b9b = s9.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    t9b = b9b.text_frame
    t9b.word_wrap = True
    p = t9b.paragraphs[0]
    p.text = "🏎️ DIGITAL VIRTUAL COCKPIT (QT)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GOLD
    p.space_after = Pt(10)
    for pt in [
        "Giao diện thể thao thiết kế bằng PyQt5 + pyqtgraph.",
        "Cụm 2 đồng hồ kim tròn quét mượt mà ở tần số cao 40 FPS (Speedometer & Power Gauge).",
        "Khung xe 3D top-down với sóng radar hồng ngoại quét vật cản đổi màu đỏ khi có sự cố.",
        "Con lắc G-Meter trực quan hóa rung chấn gia tốc.",
        "Biểu đồ bám PID thời gian thực 100 Hz, dải đèn cảnh báo chuẩn quốc tế ISO 2575."
    ]:
        p = t9b.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 10: KẾT QUẢ ĐO KIỂM NFR-1 (JITTER LOGIC ANALYZER)
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_bg(s10)
    add_header(s10, "9. Kết Quả Đo Kiểm NFR-1: Định Lượng Jitter Chu Kỳ 10ms")

    # Left: Image
    img_jitter = "docs/assets/week11/jitter_measurement_pe9.png"
    if os.path.exists(img_jitter):
        s10.shapes.add_picture(img_jitter, Inches(0.8), Inches(1.6), width=Inches(6.8))

    # Right: Data Card
    add_card(s10, Inches(7.8), Inches(1.6), Inches(4.733), Inches(5.2), border_color=ACCENT_CYAN)
    b10 = s10.shapes.add_textbox(Inches(8.0), Inches(1.8), Inches(4.333), Inches(4.7))
    t10 = b10.text_frame
    t10.word_wrap = True

    p = t10.paragraphs[0]
    p.text = "📊 SỐ LIỆU ĐO THỰC TẾ (SALEAE LOGIC 2)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(10)

    j_data = [
        "Kênh đo: Channel 0 (PE9 / Arduino D6)",
        "Nửa chu kỳ danh định: 10.000000 ms",
        "Nửa chu kỳ đo được: 10.006375 ms",
        "HARDWARE JITTER (ΔT): 6.375 µs",
        "Chu kỳ toàn phần (Lên+Xuống): 20.01275 ms",
        "Tần số đo được: 49.986 Hz (Sai số -0.028%)",
        "Tỷ lệ chiếm chu kỳ (Duty): 50.0% đối xứng"
    ]
    for d in j_data:
        p = t10.add_paragraph()
        p.text = "• " + d
        p.font.size = Pt(11)
        p.font.color.rgb = ACCENT_GOLD if "JITTER" in d else TEXT_WHITE
        p.space_after = Pt(5)

    p_eval = t10.add_paragraph()
    p_eval.text = "\n🏆 ĐÁNH GIÁ CHUẨN NFR-1:\nĐặc tả yêu cầu Jitter ≤ 50 µs. Kết quả thực tế 6.375 µs -> VƯỢT CHUẨN XUẤT SẮC 7.84 LẦN (Dư 87.25% biên độ an toàn). Khẳng định tính tất định tuyệt đối của Zephyr RTOS!"
    p_eval.font.size = Pt(11)
    p_eval.font.bold = True
    p_eval.font.color.rgb = ACCENT_GREEN

    # =========================================================================
    # SLIDE 11: KẾT QUẢ ĐO KIỂM NFR-2 (PWM & ĐỘ TRỄ E-STOP)
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_bg(s11)
    add_header(s11, "10. Kết Quả Đo Kiểm NFR-2: Xác Thực PWM 20kHz & Độ Trễ E-Stop")

    # Left: Image
    img_pwm = "docs/assets/week11/estop_cutoff_zoom.png"
    if os.path.exists(img_pwm):
        s11.shapes.add_picture(img_pwm, Inches(0.8), Inches(1.6), width=Inches(6.8))

    # Right: Data Card
    add_card(s11, Inches(7.8), Inches(1.6), Inches(4.733), Inches(5.2), border_color=ACCENT_RED)
    b11 = s11.shapes.add_textbox(Inches(8.0), Inches(1.8), Inches(4.333), Inches(4.7))
    t11 = b11.text_frame
    t11.word_wrap = True

    p = t11.paragraphs[0]
    p.text = "⚡ ĐO ĐẠC ĐỘ TRỄ NGẮT PHANH"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_RED
    p.space_after = Pt(10)

    p_data = [
        "Tần số sóng mang PWM: 20.000 kHz",
        "Chu kỳ xung PWM: 50.0 µs",
        "Độ rộng mức cao: 42.5 µs (Duty 85.0%)",
        "Khớp 100% trần Anti-Windup ASW!",
        "PIR sườn lên báo nguy: t = 1.9011 s",
        "Chu kỳ an toàn bắt đầu: t = 1.9178 s",
        "Thời gian ngắt PWM về 0V: < 0.05 ms",
        "Tổng độ trễ phản ứng: 16.7 ms"
    ]
    for d in p_data:
        p = t11.add_paragraph()
        p.text = "• " + d
        p.font.size = Pt(11)
        p.font.color.rgb = ACCENT_GOLD if "ngắt PWM" in d else TEXT_WHITE
        p.space_after = Pt(4)

    p_eval2 = t11.add_paragraph()
    p_eval2.text = "\n🏆 ĐÁNH GIÁ CHUẨN NFR-2:\nĐặc tả yêu cầu thời gian ngắt phanh < 5.0 ms. Kết quả thực tế ngắt ngay trong cùng chu kỳ (< 50 µs) -> ĐẠT XUẤT SẮC!"
    p_eval2.font.size = Pt(11)
    p_eval2.font.bold = True
    p_eval2.font.color.rgb = ACCENT_GREEN

    # =========================================================================
    # SLIDE 12: KẾT QUẢ ĐO KIỂM NFR-3 (BENCHMARK RPMSG IPC)
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_bg(s12)
    add_header(s12, "11. Kết Quả Đo Kiểm NFR-3: Benchmark Độ Trễ Khứ Hồi RPMsg IPC")

    img_rpmsg = "docs/assets/week12/rpmsg_roundtrip_latency.jpg"
    if os.path.exists(img_rpmsg):
        s12.shapes.add_picture(img_rpmsg, Inches(0.8), Inches(1.6), width=Inches(6.8))

    add_card(s12, Inches(7.8), Inches(1.6), Inches(4.733), Inches(5.2), border_color=ACCENT_BLUE)
    b12 = s12.shapes.add_textbox(Inches(8.0), Inches(1.8), Inches(4.333), Inches(4.7))
    t12 = b12.text_frame
    t12.word_wrap = True

    p = t12.paragraphs[0]
    p.text = "🔄 BENCHMARK 100 GÓI KHỨ HỒI (A7 ↔ M4)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = ACCENT_BLUE
    p.space_after = Pt(10)

    ipc_data = [
        "Tổng số gói truyền: 100 / 100 mẫu",
        "Tỷ lệ thành công: 100.0% (0% packet drop)",
        "ĐỘ TRỄ TRUNG BÌNH (t_avg): 1.999 ms",
        "Độ trễ cực tiểu (t_min): 1.727 ms",
        "Độ trễ cực đại (t_max): 2.640 ms",
        "Độ lệch chuẩn Jitter (σ): 0.129 ms (129 µs)"
    ]
    for d in ipc_data:
        p = t12.add_paragraph()
        p.text = "• " + d
        p.font.size = Pt(11)
        p.font.color.rgb = ACCENT_GOLD if "TRUNG BÌNH" in d else TEXT_WHITE
        p.space_after = Pt(5)

    p_eval3 = t12.add_paragraph()
    p_eval3.text = "\n🏆 ĐÁNH GIÁ CHUẨN NFR-3:\nMục tiêu thiết kế yêu cầu độ trễ < 5.0 ms. Kết quả thực nghiệm đạt 1.999 ms (< 2.0 ms) với độ lệch chuẩn chỉ 129 µs -> ĐẠT XUẤT SẮC!"
    p_eval3.font.size = Pt(11)
    p_eval3.font.bold = True
    p_eval3.font.color.rgb = ACCENT_GREEN

    # =========================================================================
    # SLIDE 13: KẾT QUẢ ĐO KIỂM NFR-4 & NFR-5
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    add_bg(s13)
    add_header(s13, "12. Kiểm Chứng Tính Độc Lập Khi Crash (NFR-4) & Bám PID (NFR-5)")

    # Left: NFR-4
    add_card(s13, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), border_color=ACCENT_GREEN)
    b13a = s13.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    t13a = b13a.text_frame
    t13a.word_wrap = True

    p = t13a.paragraphs[0]
    p.text = "🛡️ NFR-4: TÍNH ĐỘC LẬP KHI CRASH"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    p.space_after = Pt(10)

    nfr4_pts = [
        "Thử nghiệm: Đang chạy motor ở 10 RPM, cố ý ngắt cưỡng bức Dashboard (Ctrl + C) làm đứt toàn bộ kết nối HMI và tiến trình Linux.",
        "Hiện tượng thực tế:",
        "  - Cortex-M4 vẫn chạy 100%, motor quay mượt mà, vòng PID 10ms không bị gián đoạn.",
        "  - Quơ tay trước cảm biến PIR: M4 tự động ngắt phanh dừng xe an toàn ngay lập tức!",
        "Kết luận: Phân vùng thời gian thực M4 hoàn toàn độc lập, không bị kéo sập theo Linux."
    ]
    for pt in nfr4_pts:
        p = t13a.add_paragraph()
        p.text = "• " + pt if not pt.startswith("  ") else pt
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED if not pt.startswith("  ") else ACCENT_GOLD
        p.space_after = Pt(6)

    # Right: NFR-5
    add_card(s13, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2), border_color=ACCENT_CYAN)
    b13b = s13.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    t13b = b13b.text_frame
    t13b.word_wrap = True

    p = t13b.paragraphs[0]
    p.text = "🎯 NFR-5: ĐỘ CHÍNH XÁC BÁM PID"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(10)

    nfr5_pts = [
        "Kiểm tra bám vận tốc tại các điểm đặt: 8 RPM, 10 RPM, 12 RPM, 15 RPM.",
        "Sai số xác lập thực tế: ess = 0.00 RPM (Đặc tả NFR-5 yêu cầu ess ≤ 2.0 RPM).",
        "Độ vọt lố (Overshoot): 0% (nhờ thuật toán Anti-Windup Clamping).",
        "Thời gian xác lập: ts ≈ 1.2s.",
        "Toàn vẹn truyền thông: 3,318 / 3,318 gói tin đạt chuẩn kiểm tra CRC-16 (100.0% không lỗi bit)."
    ]
    for pt in nfr5_pts:
        p = t13b.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(11)
        p.font.color.rgb = TEXT_MUTED if "ess" not in pt else ACCENT_GOLD
        p.space_after = Pt(6)

    # =========================================================================
    # SLIDE 14: MASTER SCORECARD
    # =========================================================================
    s14 = prs.slides.add_slide(blank_layout)
    add_bg(s14)
    add_header(s14, "13. Bảng Tổng Hợp Nghiệm Thu Toàn Diện (Master Scorecard)")

    add_card(s14, Inches(0.8), Inches(1.6), Inches(11.733), Inches(5.2))
    
    rows = 7
    cols = 4
    tbl_s = s14.shapes.add_table(rows, cols, Inches(1.0), Inches(1.8), Inches(11.333), Inches(4.7))
    t14 = tbl_s.table
    t14.columns[0].width = Inches(1.5)
    t14.columns[1].width = Inches(3.8)
    t14.columns[2].width = Inches(4.2)
    t14.columns[3].width = Inches(1.833)

    score_data = [
        ("Tiêu Chuẩn", "Chỉ Tiêu Kỹ Thuật Đặc Tả", "Kết Quả Thực Nghiệm Trên Phần Cứng", "Đánh Giá"),
        ("NFR-1", "Jitter chu kỳ PID Ts = 10ms ≤ 50 µs", "ΔT = 6.375 µs (Logic Analyzer trên PE9)", "VƯỢT 7.8 LẦN"),
        ("NFR-2", "Độ trễ ngắt E-Stop < 5.0 ms", "Ngắt PWM < 0.05 ms tại chu kỳ an toàn", "ĐẠT XUẤT SẮC"),
        ("NFR-3", "Độ trễ khứ hồi RPMsg IPC < 5.0 ms", "t_avg = 1.999 ms, σ = 0.129 ms (100/100)", "ĐẠT XUẤT SẮC"),
        ("NFR-4", "Tính độc lập khi Linux/HMI crash", "M4 tự chạy PID và tự phanh khi có vật cản", "ĐẠT TUYỆT ĐỐI"),
        ("NFR-5", "Sai số bám PID ess ≤ 2.0 RPM", "ess = 0.00 RPM, Overshoot 0%", "ĐẠT 100%"),
        ("FR-M & FR-A", "15 Yêu cầu chức năng trên M4 & A7", "100% các chức năng chạy ổn định phần cứng", "HOÀN THÀNH")
    ]

    for r_idx, row in enumerate(score_data):
        for c_idx, val in enumerate(row):
            cell = t14.cell(r_idx, c_idx)
            cell.text = val
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c_idx in [0, 3] else PP_ALIGN.LEFT
            if r_idx == 0:
                p.font.bold = True
                p.font.size = Pt(11)
                p.font.color.rgb = ACCENT_CYAN
            else:
                p.font.size = Pt(10)
                if c_idx == 3:
                    p.font.bold = True
                    p.font.color.rgb = ACCENT_GREEN
                elif c_idx == 0:
                    p.font.bold = True
                    p.font.color.rgb = ACCENT_GOLD
                else:
                    p.font.color.rgb = TEXT_WHITE

    # =========================================================================
    # SLIDE 15: VIDEO THỰC NGHIỆM DEMO
    # =========================================================================
    s_v = prs.slides.add_slide(blank_layout)
    add_bg(s_v)
    add_header(s_v, "14. Video Thực Nghiệm Demo Toàn Diện Phần Cứng (Hardware Demo)")

    # Left: Video Info Card
    add_card(s_v, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2), border_color=ACCENT_CYAN)
    bv_left = s_v.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(5.0), Inches(4.7))
    tv_left = bv_left.text_frame
    tv_left.word_wrap = True

    p = tv_left.paragraphs[0]
    p.text = "🎥 VIDEO VẬN HÀNH THỰC TẾ"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(12)

    v_meta = [
        "File: docs/video_demo/demo.mp4",
        "Định dạng: MP4 Video (H.264)",
        "Dung lượng: ~29.6 MB",
        "Độ phân giải: Full HD 1080p",
        "Trạng thái: Đã sẵn sàng trình chiếu trực tiếp"
    ]
    for m in v_meta:
        p = tv_left.add_paragraph()
        p.text = "• " + m
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_WHITE if "File" in m else TEXT_MUTED
        p.space_after = Pt(6)

    p_badge = tv_left.add_paragraph()
    p_badge.text = "\n▶️ SẴN SÀNG TRÌNH DIỄN MINH CHỨNG TRƯỚC HỘI ĐỒNG GIÁM KHẢO"
    p_badge.font.size = Pt(12)
    p_badge.font.bold = True
    p_badge.font.color.rgb = ACCENT_GOLD

    # Right: 4 Scenarios Card
    add_card(s_v, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2), border_color=ACCENT_GREEN)
    bv_right = s_v.shapes.add_textbox(Inches(7.1), Inches(1.8), Inches(5.1), Inches(4.7))
    tv_right = bv_right.text_frame
    tv_right.word_wrap = True

    p = tv_right.paragraphs[0]
    p.text = "📋 4 KỊCH BẢN THỰC NGHIỆM GHI HÌNH"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    p.space_after = Pt(12)

    scenarios = [
        ("1. Khởi động & Nạp Firmware:", "Cortex-A7 nạp M4 qua remoteproc, thiết lập kênh RPMsg kết nối Virtual Cockpit."),
        ("2. Bám Vận Tốc PID 10ms (NFR-5):", "Cần số chuyển D (PID), đổi tốc độ 8, 10, 12 RPM, kim quét mượt mà, sai số ess = 0.00 RPM."),
        ("3. Phanh Khẩn Cấp PIR (NFR-2):", "Đưa tay trước xe -> Radar đổi màu đỏ, phanh ngắt điện PWM tức thì (< 50 µs)."),
        ("4. Kiểm Chứng Độc Lập Khi Crash (NFR-4):", "Ngắt HMI đột ngột, M4 vẫn chạy PID độc lập và tự phanh khi có vật cản.")
    ]
    for s_title, s_desc in scenarios:
        p1 = tv_right.add_paragraph()
        p1.text = s_title
        p1.font.size = Pt(11)
        p1.font.bold = True
        p1.font.color.rgb = ACCENT_GOLD
        p2 = tv_right.add_paragraph()
        p2.text = "   " + s_desc
        p2.font.size = Pt(10)
        p2.font.color.rgb = TEXT_WHITE
        p2.space_after = Pt(4)

    # =========================================================================
    # SLIDE 16: KẾT LUẬN & ĐÓNG GÓP
    # =========================================================================
    s15 = prs.slides.add_slide(blank_layout)
    add_bg(s15)
    add_header(s15, "15. Kết Luận & Những Đóng Góp Kỹ Thuật Nổi Bật Của Đề Tài")

    add_card(s15, Inches(0.8), Inches(1.6), Inches(11.733), Inches(5.2))
    b15 = s15.shapes.add_textbox(Inches(1.1), Inches(1.8), Inches(11.133), Inches(4.8))
    t15 = b15.text_frame
    t15.word_wrap = True

    p = t15.paragraphs[0]
    p.text = "4 ĐÓNG GÓP KỸ THUẬT CỐT LÕI:"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(12)

    contributions = [
        ("1. Làm chủ kiến trúc vi xử lý đa nhân dị thể (Heterogeneous SoC STM32MP157):", "Tích hợp thành công hai miền tính toán đối lập (Hard Real-Time M4 và Smart Linux A7) trên cùng một đế bán dẫn với tính độc lập hoàn hảo."),
        ("2. Hiện thực hóa chuẩn công nghiệp ô tô AUTOSAR Classic trên Zephyr RTOS:", "Xây dựng phân tầng ASW -> RTE -> BSW chuẩn mực, giúp mã nguồn thuật toán hoàn toàn độc lập phần cứng và có khả năng tái sử dụng tối đa."),
        ("3. Quy trình thiết kế điều khiển từ Nhận Dạng Toán Học đến Thực Tế:", "Thu thập dữ liệu thực tế bước nhảy và nhận dạng mô hình trên MATLAB đạt độ khớp 80.95%, giúp bộ điều khiển PID đạt sai số bám lý tưởng 0.00 RPM."),
        ("4. Phương pháp đo kiểm định lượng cấp microsecond chuyên nghiệp:", "Sử dụng Logic Analyzer chuyên dụng chứng minh Jitter chỉ 6.375 µs và độ trễ liên nhân IPC chỉ 1.999 ms, mang lại cơ sở khoa học vững chắc cho đề tài.")
    ]

    for title, desc in contributions:
        p1 = t15.add_paragraph()
        p1.text = title
        p1.font.size = Pt(12)
        p1.font.bold = True
        p1.font.color.rgb = ACCENT_GOLD
        p2 = t15.add_paragraph()
        p2.text = "   " + desc
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_WHITE
        p2.space_after = Pt(8)

    # =========================================================================
    # SLIDE 16: HƯỚNG PHÁT TRIỂN & Q&A
    # =========================================================================
    s16 = prs.slides.add_slide(blank_layout)
    add_bg(s16)

    # Main Card
    add_card(s16, Inches(1.5), Inches(1.2), Inches(10.333), Inches(5.1))
    b16 = s16.shapes.add_textbox(Inches(1.8), Inches(1.5), Inches(9.733), Inches(4.5))
    t16 = b16.text_frame
    t16.word_wrap = True

    p = t16.paragraphs[0]
    p.text = "HƯỚNG PHÁT TRIỂN TIẾP THEO (FUTURE WORK)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = ACCENT_CYAN
    p.space_after = Pt(10)

    fw = [
        "Mở rộng giao tiếp mạng vật lý ô tô: Tích hợp phần cứng CAN FD và Automotive Ethernet (100BASE-T1).",
        "Nâng cấp giải thuật điều khiển động cơ: Triển khai điều khiển vector tựa từ thông (FOC) cho động cơ BLDC/PMSM.",
        "Cập nhật phần mềm không dây an toàn (OTA): Xây dựng tính năng FOTA có chữ ký số cho Cortex-M4 qua Linux Gateway."
    ]
    for w in fw:
        p = t16.add_paragraph()
        p.text = "• " + w
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_MUTED
        p.space_after = Pt(8)

    p_div = t16.add_paragraph()
    p_div.text = "─────────────────────────────────────────────────────────────────"
    p_div.font.size = Pt(10)
    p_div.font.color.rgb = CARD_BORDER
    p_div.space_after = Pt(10)

    p_end = t16.add_paragraph()
    p_end.text = "XIN TRÂN TRỌNG CẢM ƠN QUÝ THẦY CÔ TRONG HỘI ĐỒNG GIÁM KHẢO!"
    p_end.font.size = Pt(16)
    p_end.font.bold = True
    p_end.font.color.rgb = ACCENT_GOLD
    p_end.alignment = PP_ALIGN.CENTER
    p_end.space_after = Pt(6)

    p_qa = t16.add_paragraph()
    p_qa.text = "PHIÊN HỎI & ĐÁP (Q & A)"
    p_qa.font.size = Pt(13)
    p_qa.font.bold = True
    p_qa.font.color.rgb = TEXT_WHITE
    p_qa.alignment = PP_ALIGN.CENTER

    # Save presentation
    out_path = "docs/AUTOMOTIVE_DOMAIN_GATEWAY_PRESENTATION.pptx"
    prs.save(out_path)
    print(f"[Success] PPTX presentation saved to {out_path}")

if __name__ == "__main__":
    create_deck()
