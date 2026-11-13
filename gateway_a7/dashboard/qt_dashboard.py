#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
DIGITAL COCKPIT & AUTOMOTIVE DOMAIN GATEWAY DASHBOARD
================================================================================
Target:      STM32MP157D-DK1 (Heterogeneous Multi-Core System)
Subsystems:  Cortex-M4 (AUTOSAR Classic PID 100Hz) <-> Cortex-A7 (OpenSTLinux)
Theme:       High-End Digital Cockpit / Instrument Cluster (Virtual Cockpit)
================================================================================
"""

import sys, os, time, math, socket
from collections import deque

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
        QLinearGradient, QRadialGradient, QConicalGradient, QPainterPath
    )
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
        QComboBox, QFrame, QSplitter, QStatusBar, QDialog
    )
    import pyqtgraph as pg
except ImportError:
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPolygonF,
        QLinearGradient, QRadialGradient, QConicalGradient, QPainterPath
    )
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QSlider, QSpinBox, QDoubleSpinBox,
        QComboBox, QFrame, QSplitter, QStatusBar, QDialog
    )
    import pyqtgraph as pg

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


# ==============================================================================
# CRC-16-CCITT VERIFICATION
# ==============================================================================
def compute_crc16_ccitt(data_bytes: bytes) -> int:
    crc = 0xFFFF
    for b in data_bytes:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


# ==============================================================================
# CUSTOM AUTOMOTIVE CIRCULAR GAUGE (Speedometer & Power / G-Force)
# ==============================================================================
class AutomotiveGauge(QWidget):
    def __init__(self, title="SPEED", unit="RPM", min_val=0.0, max_val=30.0,
                 major_ticks=6, minor_ticks=4, color_theme="cyan", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.min_val = min_val
        self.max_val = max_val
        self.major_ticks = major_ticks
        self.minor_ticks = minor_ticks
        self.color_theme = color_theme

        self.current_value = 0.0
        self.target_value = 0.0
        self.setMinimumSize(220, 220)

        # Smooth animation timer
        self._display_val = 0.0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(25)  # 40 FPS needle smoothing

    def set_value(self, val: float):
        self.current_value = max(self.min_val, min(self.max_val, val))

    def set_target(self, tgt: float):
        self.target_value = max(self.min_val, min(self.max_val, tgt))
        self.update()

    def _animate_step(self):
        diff = self.current_value - self._display_val
        if abs(diff) > 0.02:
            self._display_val += diff * 0.25
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing if hasattr(QPainter, 'Antialiasing') else QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        side = min(w, h)
        p.translate(w / 2.0, h / 2.0)
        scale = side / 260.0
        p.scale(scale, scale)

        cx, cy = 0.0, 0.0
        r_outer = 120.0
        r_dial = 108.0

        # 1. Outer Metallic Bezel Ring
        grad_bezel = QRadialGradient(cx, cy, r_outer)
        grad_bezel.setColorAt(0.85, QColor(25, 28, 42))
        grad_bezel.setColorAt(0.95, QColor(45, 52, 75))
        grad_bezel.setColorAt(1.0, QColor(15, 17, 26))
        p.setPen(QPen(QColor(60, 70, 95), 1.5))
        p.setBrush(QBrush(grad_bezel))
        p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)

        # 2. Dark Dial Face
        grad_face = QRadialGradient(cx, cy, r_dial)
        grad_face.setColorAt(0.0, QColor(14, 16, 26))
        grad_face.setColorAt(0.8, QColor(18, 21, 33))
        grad_face.setColorAt(1.0, QColor(24, 28, 44))
        p.setPen(Qt.NoPen if hasattr(Qt, 'NoPen') else Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad_face))
        p.drawEllipse(QPointF(cx, cy), r_dial, r_dial)

        # Gauge sweep: 135 deg (bottom-left) to 405 deg (bottom-right) -> 270 deg span
        start_angle = 135.0
        sweep_angle = 270.0

        # Theme Colors
        if self.color_theme == "cyan":
            arc_color = QColor(0, 210, 255)
            glow_color = QColor(0, 230, 118)
        elif self.color_theme == "amber":
            arc_color = QColor(255, 171, 0)
            glow_color = QColor(255, 82, 82)
        else:
            arc_color = QColor(0, 230, 118)
            glow_color = QColor(0, 210, 255)

        # 3. Background Track Arc
        p.setPen(QPen(QColor(40, 48, 70), 8, Qt.SolidLine if hasattr(Qt, 'SolidLine') else Qt.PenStyle.SolidLine,
                      Qt.RoundCap if hasattr(Qt, 'RoundCap') else Qt.PenCapStyle.RoundCap))
        rect_track = QRectF(cx - 90, cy - 90, 180, 180)
        p.drawArc(rect_track, int(-135 * 16), int(-sweep_angle * 16))

        # 4. Active Progress Glow Arc
        frac = (self._display_val - self.min_val) / max(0.001, (self.max_val - self.min_val))
        frac = max(0.0, min(1.0, frac))
        active_sweep = frac * sweep_angle

        if active_sweep > 0.5:
            pen_active = QPen(arc_color, 8, Qt.SolidLine if hasattr(Qt, 'SolidLine') else Qt.PenStyle.SolidLine,
                              Qt.RoundCap if hasattr(Qt, 'RoundCap') else Qt.PenCapStyle.RoundCap)
            p.setPen(pen_active)
            p.drawArc(rect_track, int(-135 * 16), int(-active_sweep * 16))

        # 5. Target Setpoint Marker (Red Notch on Dial)
        if self.target_value > 0:
            tgt_frac = (self.target_value - self.min_val) / max(0.001, (self.max_val - self.min_val))
            tgt_deg = start_angle + tgt_frac * sweep_angle
            tgt_rad = math.radians(tgt_deg)
            tx1 = cx + 84 * math.cos(tgt_rad)
            ty1 = cy + 84 * math.sin(tgt_rad)
            tx2 = cx + 96 * math.cos(tgt_rad)
            ty2 = cy + 96 * math.sin(tgt_rad)
            p.setPen(QPen(QColor(255, 59, 92), 3))
            p.drawLine(QPointF(tx1, ty1), QPointF(tx2, ty2))

        # 6. Scale Ticks & Numerical Labels
        total_intervals = self.major_ticks
        font_ticks = QFont("Arial", 8, QFont.Bold)
        p.setFont(font_ticks)

        for i in range(total_intervals + 1):
            f_tick = i / float(total_intervals)
            deg = start_angle + f_tick * sweep_angle
            rad = math.radians(deg)

            # Major tick line
            x1 = cx + 86 * math.cos(rad)
            y1 = cy + 86 * math.sin(rad)
            x2 = cx + 98 * math.cos(rad)
            y2 = cy + 98 * math.sin(rad)
            p.setPen(QPen(QColor(180, 195, 220), 2))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # Major tick label
            val = self.min_val + f_tick * (self.max_val - self.min_val)
            val_str = f"{int(val)}" if (self.max_val >= 10) else f"{val:.1f}"
            tx = cx + 70 * math.cos(rad)
            ty = cy + 70 * math.sin(rad) + 4
            p.setPen(QColor(160, 175, 205))
            p.drawText(QRectF(tx - 18, ty - 10, 36, 20),
                       Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter, val_str)

            # Minor ticks
            if i < total_intervals:
                for m in range(1, self.minor_ticks + 1):
                    f_min = f_tick + (m / (self.minor_ticks + 1.0)) * (1.0 / total_intervals)
                    m_deg = start_angle + f_min * sweep_angle
                    m_rad = math.radians(m_deg)
                    mx1 = cx + 91 * math.cos(m_rad)
                    my1 = cy + 91 * math.sin(m_rad)
                    mx2 = cx + 97 * math.cos(m_rad)
                    my2 = cy + 97 * math.sin(m_rad)
                    p.setPen(QPen(QColor(90, 105, 135), 1))
                    p.drawLine(QPointF(mx1, my1), QPointF(mx2, my2))

        # 7. Needle Indicator
        needle_deg = start_angle + frac * sweep_angle
        needle_rad = math.radians(needle_deg)
        tip_x = cx + 92 * math.cos(needle_rad)
        tip_y = cy + 92 * math.sin(needle_rad)

        base_rad1 = needle_rad + math.pi / 2.0
        base_rad2 = needle_rad - math.pi / 2.0
        bx1 = cx + 6 * math.cos(base_rad1)
        by1 = cy + 6 * math.sin(base_rad1)
        bx2 = cx + 6 * math.cos(base_rad2)
        by2 = cy + 6 * math.sin(base_rad2)

        tail_x = cx - 18 * math.cos(needle_rad)
        tail_y = cy - 18 * math.sin(needle_rad)

        needle_poly = QPolygonF([QPointF(tip_x, tip_y), QPointF(bx1, by1),
                                 QPointF(tail_x, tail_y), QPointF(bx2, by2)])
        p.setPen(Qt.NoPen if hasattr(Qt, 'NoPen') else Qt.PenStyle.NoPen)
        grad_needle = QLinearGradient(bx1, by1, bx2, by2)
        grad_needle.setColorAt(0.0, QColor(255, 60, 60))
        grad_needle.setColorAt(1.0, QColor(255, 140, 0))
        p.setBrush(QBrush(grad_needle))
        p.drawPolygon(needle_poly)

        # 8. Center Hub Cap
        grad_hub = QRadialGradient(cx, cy, 18)
        grad_hub.setColorAt(0.0, QColor(80, 95, 130))
        grad_hub.setColorAt(0.6, QColor(35, 40, 60))
        grad_hub.setColorAt(1.0, QColor(15, 18, 28))
        p.setPen(QPen(QColor(100, 120, 160), 1.5))
        p.setBrush(QBrush(grad_hub))
        p.drawEllipse(QPointF(cx, cy), 18, 18)

        # 9. Digital Center Readout
        p.setFont(QFont("Arial", 16, QFont.Bold))
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(cx - 50, cy + 24, 100, 28),
                   Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                   f"{self._display_val:.1f}")

        p.setFont(QFont("Arial", 8, QFont.Bold))
        p.setPen(arc_color)
        p.drawText(QRectF(cx - 50, cy + 50, 100, 16),
                   Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                   self.unit)

        # Title at Top Inside
        p.setFont(QFont("Arial", 9, QFont.Bold))
        p.setPen(QColor(140, 155, 185))
        p.drawText(QRectF(cx - 60, cy - 50, 120, 18),
                   Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                   self.title)


# ==============================================================================
# CAR CHASSIS WIREFRAME & ACTIVE RADAR WIDGET
# ==============================================================================
class VehicleCockpitCenter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 240)
        self.pir_detected = False
        self.shock_val = 0.98
        self.motor_rpm = 0.0
        self.drive_mode = "PID"
        self.radar_phase = 0.0

        # Radar animation
        self.radar_timer = QTimer(self)
        self.radar_timer.timeout.connect(self._step_radar)
        self.radar_timer.start(50)

    def _step_radar(self):
        self.radar_phase += 0.15
        if self.radar_phase > 3.0:
            self.radar_phase = 0.0
        self.update()

    def update_state(self, pir: bool, shock_g: float, rpm: float, mode: str):
        self.pir_detected = pir
        self.shock_val = shock_g
        self.motor_rpm = rpm
        self.drive_mode = mode
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing if hasattr(QPainter, 'Antialiasing') else QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0 + 10

        # 1. Background Card
        p.setPen(QPen(QColor(35, 42, 65), 1))
        p.setBrush(QBrush(QColor(16, 19, 30)))
        p.drawRoundedRect(QRectF(10, 10, w - 20, h - 20), 10, 10)

        # 2. Top-Down Car Silhouette
        car_w = 64
        car_h = 130
        car_rect = QRectF(cx - car_w / 2.0, cy - car_h / 2.0, car_w, car_h)

        # Body shadow/halo
        p.setPen(Qt.NoPen if hasattr(Qt, 'NoPen') else Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 30, 50, 120))
        p.drawRoundedRect(car_rect.adjusted(-6, -6, 6, 6), 18, 18)

        # Body outline
        grad_car = QLinearGradient(cx, cy - car_h / 2.0, cx, cy + car_h / 2.0)
        grad_car.setColorAt(0.0, QColor(40, 50, 75))
        grad_car.setColorAt(0.5, QColor(25, 32, 50))
        grad_car.setColorAt(1.0, QColor(35, 45, 68))
        p.setPen(QPen(QColor(0, 210, 255), 1.8))
        p.setBrush(QBrush(grad_car))
        p.drawRoundedRect(car_rect, 14, 14)

        # Windshield & Roof Glass
        p.setPen(QPen(QColor(0, 180, 240, 180), 1.2))
        p.setBrush(QColor(10, 15, 25, 220))
        glass_rect = QRectF(cx - car_w * 0.35, cy - car_h * 0.25, car_w * 0.7, car_h * 0.45)
        p.drawRoundedRect(glass_rect, 6, 6)

        # 4 Wheels
        p.setPen(Qt.NoPen if hasattr(Qt, 'NoPen') else Qt.PenStyle.NoPen)
        p.setBrush(QColor(70, 85, 115))
        # Front-left, Front-right, Rear-left, Rear-right
        wh_w, wh_h = 10, 22
        p.drawRoundedRect(QRectF(cx - car_w / 2.0 - 6, cy - car_h * 0.35, wh_w, wh_h), 3, 3)
        p.drawRoundedRect(QRectF(cx + car_w / 2.0 - 4, cy - car_h * 0.35, wh_w, wh_h), 3, 3)
        p.drawRoundedRect(QRectF(cx - car_w / 2.0 - 6, cy + car_h * 0.15, wh_w, wh_h), 3, 3)
        p.drawRoundedRect(QRectF(cx + car_w / 2.0 - 4, cy + car_h * 0.15, wh_w, wh_h), 3, 3)

        # Rear Axle Motor Drive Animation (Glowing Green Axle if moving)
        if self.motor_rpm > 0.5:
            p.setPen(QPen(QColor(0, 230, 118), 3))
            p.drawLine(QPointF(cx - car_w * 0.45, cy + car_h * 0.25),
                       QPointF(cx + car_w * 0.45, cy + car_h * 0.25))
            p.setPen(QPen(QColor(0, 230, 118), 1))
            p.setBrush(QColor(0, 230, 118, 120))
            p.drawEllipse(QPointF(cx, cy + car_h * 0.25), 6, 6)

        # 3. Front PIR Sensor Radar Cones
        bumper_y = cy - car_h / 2.0
        radar_color = QColor(255, 59, 92) if self.pir_detected else QColor(0, 230, 118)

        for ring in [1, 2, 3]:
            r_rad = 18 * ring + (self.radar_phase * 6)
            alpha = max(0, int(220 - r_rad * 2.5))
            c = QColor(radar_color.red(), radar_color.green(), radar_color.blue(), alpha)
            p.setPen(QPen(c, 2, Qt.SolidLine if hasattr(Qt, 'SolidLine') else Qt.PenStyle.SolidLine))
            # Arc radiating forward (angles 30 deg to 150 deg)
            rect_rad = QRectF(cx - r_rad, bumper_y - r_rad, r_rad * 2, r_rad * 2)
            p.drawArc(rect_rad, 45 * 16, 90 * 16)

        # Radar text badge
        p.setFont(QFont("Arial", 8, QFont.Bold))
        if self.pir_detected:
            p.setPen(QColor(255, 59, 92))
            p.drawText(QRectF(15, 18, w - 30, 18),
                       Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                       "⚠ RADAR: OBSTACLE DETECTED")
        else:
            p.setPen(QColor(0, 230, 118))
            p.drawText(QRectF(15, 18, w - 30, 18),
                       Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                       "RADAR: CLEAR (PIR SENSOR)")

        # 4. G-Force Accelerometer Bubble (In Center of Car)
        p.setPen(QPen(QColor(80, 100, 140, 160), 1))
        p.setBrush(Qt.NoBrush if hasattr(Qt, 'NoBrush') else Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 14, 14)

        g_color = QColor(255, 59, 92) if (self.shock_val >= 2.5) else QColor(0, 210, 255)
        p.setPen(Qt.NoPen if hasattr(Qt, 'NoPen') else Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g_color))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

        p.setFont(QFont("Arial", 8, QFont.Bold))
        p.setPen(QColor(160, 180, 210))
        p.drawText(QRectF(15, h - 36, w - 30, 18),
                   Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else Qt.AlignmentFlag.AlignCenter,
                   f"LATERAL SHOCK: {self.shock_val:.2f} g")


# ==============================================================================
# TELL-TALE WARNING BAR (ISO 2575 Automotive Symbols)
# ==============================================================================
class AutomotiveTellTaleBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("telltaleBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)

        self.pill_brake = QLabel("🛑 BRAKE")
        self.pill_pir = QLabel("🚶 OBSTACLE")
        self.pill_shock = QLabel("💥 CRASH")
        self.pill_wdg = QLabel("⚡ WDG ALIVE")
        self.pill_temp = QLabel("🌡️ 26.2°C")
        self.pill_hum = QLabel("💧 38.0%")

        for p in [self.pill_brake, self.pill_pir, self.pill_shock, self.pill_wdg, self.pill_temp, self.pill_hum]:
            p.setObjectName("telltalePill")
            layout.addWidget(p)
        layout.addStretch()

    def update_states(self, flt: int, pir: int, vib: int, temp: float, hum: float):
        # E-Stop Brake
        if flt != 0:
            self.pill_brake.setText("🛑 E-STOP ACTIVE")
            self.pill_brake.setStyleSheet("color: #ff3b5c; font-weight: bold; background: #3d1420; padding: 4px 8px; border-radius: 4px;")
        else:
            self.pill_brake.setText("🟢 SYSTEM READY")
            self.pill_brake.setStyleSheet("color: #00e676; font-weight: bold; background: #143322; padding: 4px 8px; border-radius: 4px;")

        # PIR
        if pir:
            self.pill_pir.setStyleSheet("color: #ff3b5c; font-weight: bold; background: #3d1420; padding: 4px 8px; border-radius: 4px;")
        else:
            self.pill_pir.setStyleSheet("color: #8b949e; background: #1e2233; padding: 4px 8px; border-radius: 4px;")

        # Shock
        if vib >= 2500:
            self.pill_shock.setText(f"💥 SHOCK {vib/1000.0:.1f}g")
            self.pill_shock.setStyleSheet("color: #ff3b5c; font-weight: bold; background: #3d1420; padding: 4px 8px; border-radius: 4px;")
        else:
            self.pill_shock.setText(f"🛡️ NORMAL ({vib/1000.0:.2f}g)")
            self.pill_shock.setStyleSheet("color: #8b949e; background: #1e2233; padding: 4px 8px; border-radius: 4px;")

        # Temp & Hum
        self.pill_temp.setText(f"🌡️ {temp:.1f}°C")
        self.pill_hum.setText(f"💧 {hum:.1f}%")


# ==============================================================================
# COMMUNICATION WORKER THREAD (SERIAL / TCP / SIMULATION)
# ==============================================================================
class CommWorker(QThread):
    sig_telemetry = pyqtSignal(dict)
    sig_fault = pyqtSignal(dict)
    sig_status = pyqtSignal(str, bool)
    sig_stats = pyqtSignal(int, int, float)

    def __init__(self, mode="demo", port="/dev/ttyACM0", baud=115200, host="10.8.82.37", tcp_port=8888):
        super().__init__()
        self.mode = mode
        self.port = port
        self.baud = baud
        self.host = host
        self.tcp_port = tcp_port
        self.running = True
        self.ser = None
        self.sock = None
        self.rx_count = 0
        self.err_count = 0
        self.tx_queue = deque()

        # Demo simulation state
        self.sim_tgt = 12.0
        self.sim_rpm = 12.0
        self.sim_duty = 55.0
        self.sim_cnt = 0
        self.sim_mode = "PID"
        self.sim_flt = 0
        self.sim_vib = 980
        self.sim_pir = 0

    def send_command(self, cmd_str: str):
        self.tx_queue.append(cmd_str.strip())

    def run(self):
        if self.mode == "demo":
            self._run_demo()
        elif self.mode == "tcp":
            self._run_tcp()
        else:
            self._run_serial()

    def _run_serial(self):
        if not HAS_SERIAL:
            self.sig_status.emit("Loi: chua cai dat thu vien pyserial!", False)
            return
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            self.sig_status.emit(f"Da ket noi Serial {self.port} @ {self.baud}", True)
            self.ser.write(b'\x03\n')
            time.sleep(0.2)
            self.ser.reset_input_buffer()
            self.ser.write(b"cat /dev/ttyRPMSG0\n")
            time.sleep(0.2)
        except Exception as e:
            self.sig_status.emit(f"Loi ket noi Serial: {str(e)}", False)
            return

        buf = ""
        while self.running:
            while self.tx_queue:
                cmd = self.tx_queue.popleft()
                try:
                    payload = f"\x03\necho '{cmd}' > /dev/ttyRPMSG0\ncat /dev/ttyRPMSG0\n".encode()
                    self.ser.write(payload)
                except Exception as e:
                    self.sig_status.emit(f"Loi truyen lenh: {e}", True)

            try:
                raw = self.ser.read(256).decode(errors="ignore")
                if raw:
                    buf += raw
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.strip():
                            self._parse_line(line)
            except Exception as e:
                self.sig_status.emit(f"Loi doc Serial: {e}", False)
                break
            time.sleep(0.01)

        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b'\x03\n')
                self.ser.close()
            except:
                pass
        self.sig_status.emit("Da ngat ket noi Serial.", False)

    def _run_tcp(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3.0)
            self.sock.connect((self.host, self.tcp_port))
            self.sock.settimeout(0.1)
            self.sig_status.emit(f"Da ket noi TCP {self.host}:{self.tcp_port}", True)
        except Exception as e:
            self.sig_status.emit(f"Khong the ket noi TCP {self.host}:{self.tcp_port} ({e})", False)
            return

        buf = ""
        while self.running:
            while self.tx_queue:
                cmd = self.tx_queue.popleft()
                try:
                    self.sock.sendall((cmd + "\n").encode())
                except:
                    break
            try:
                chunk = self.sock.recv(512).decode(errors="ignore")
                if chunk:
                    buf += chunk
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.strip():
                            self._parse_line(line)
            except socket.timeout:
                pass
            except:
                break
            time.sleep(0.01)

        if self.sock:
            try: self.sock.close()
            except: pass
        self.sig_status.emit("Da ngat ket noi TCP.", False)

    def _run_demo(self):
        self.sig_status.emit("Dang chay che do DEMO SIMULATION (Ao hoa phan cung)", True)
        dt = 0.05
        t = 0.0
        a = math.exp(-dt / 0.0461)
        b = 0.1873 * (1 - a)
        kp, ki, integral = 1.9641, 85.0402, 0.0

        while self.running:
            t += dt
            while self.tx_queue:
                cmd = self.tx_queue.popleft().strip()
                if cmd.startswith("SPEED"):
                    try:
                        self.sim_tgt = float(cmd.split()[1])
                        self.sim_mode = "PID"
                    except: pass
                elif cmd.startswith("STEP") or cmd.startswith("DUTY"):
                    try:
                        self.sim_duty = float(cmd.split()[1])
                        self.sim_mode = "OPEN"
                    except: pass
                elif cmd == "STOP":
                    self.sim_mode = "STOP"
                    self.sim_tgt = 0.0
                    self.sim_duty = 0.0
                elif cmd == "ESTOP":
                    self.sim_mode = "FAULT"
                    self.sim_flt = 4
                    self.sim_duty = 0.0
                elif cmd == "CLEAR":
                    self.sim_flt = 0
                    self.sim_mode = "STOP"
                    self.sim_duty = 0.0
                elif cmd == "SHOCK":
                    self.sim_vib = 3606
                    self.sim_flt = 2
                    self.sim_mode = "FAULT"
                    self.sim_duty = 0.0
                elif cmd == "PIR ON":
                    self.sim_pir = 1
                    if self.sim_mode != "STOP":
                        self.sim_flt = 1
                        self.sim_mode = "FAULT"
                        self.sim_duty = 0.0
                elif cmd == "PIR OFF":
                    self.sim_pir = 0

            if self.sim_flt != 0:
                self.sim_duty = 0.0
                self.sim_rpm = max(0.0, self.sim_rpm * 0.85)
                if self.sim_vib > 1000:
                    self.sim_vib = int(self.sim_vib * 0.9 + 980 * 0.1)
            elif self.sim_mode == "PID":
                err = self.sim_tgt - self.sim_rpm
                integral = max(-50.0, min(50.0, integral + err * dt))
                u = kp * err + ki * integral * 0.01
                self.sim_duty = max(0.0, min(100.0, u))
                self.sim_rpm = a * self.sim_rpm + b * self.sim_duty + (math.sin(t * 8) * 0.12)
            elif self.sim_mode == "OPEN":
                self.sim_rpm = a * self.sim_rpm + b * self.sim_duty
            else:
                self.sim_duty = 0.0
                self.sim_rpm = max(0.0, self.sim_rpm * 0.9)

            self.sim_cnt += int(self.sim_rpm * 2059.2 * dt / 60.0)

            telem_dict = {
                "MODE": self.sim_mode,
                "TGT": round(self.sim_tgt, 1),
                "RPM": round(self.sim_rpm, 1),
                "DUTY": round(self.sim_duty, 1),
                "CNT": self.sim_cnt,
                "PIR": self.sim_pir,
                "VIB": self.sim_vib + int(math.sin(t * 4) * 15),
                "TMP": 26.2 + round(math.sin(t * 0.1) * 0.2, 1),
                "HUM": 38.0 + round(math.cos(t * 0.1) * 0.4, 1),
                "FLT": self.sim_flt,
                "TIMESTAMP": time.strftime("%H:%M:%S")
            }
            self.rx_count += 1
            self.sig_telemetry.emit(telem_dict)
            self.sig_stats.emit(self.rx_count, self.err_count, 100.0)

            if self.sim_flt != 0 and self.sim_mode == "FAULT":
                rmap = {1: "PIR_OBSTACLE", 2: "CRASH_VIBRATION", 4: "MANUAL_ESTOP"}
                self.sig_fault.emit({"REASON": rmap.get(self.sim_flt, "FAULT"), "TIMESTAMP": time.strftime("%H:%M:%S")})

            time.sleep(dt)

    def _parse_line(self, line: str):
        line = line.strip()
        if "$TELEM" in line:
            line = line[line.find("$TELEM"):]
        elif "$FAULT" in line:
            line = line[line.find("$FAULT"):]
        else:
            return

        if "*" in line:
            payload, crc_str = line.split("*", 1)
            calc_crc = compute_crc16_ccitt(payload.encode())
            try:
                if calc_crc != int(crc_str.strip().upper(), 16):
                    self.err_count += 1
                    return
            except:
                self.err_count += 1
                return
        else:
            payload = line

        self.rx_count += 1
        pass_rate = (self.rx_count / max(1, self.rx_count + self.err_count)) * 100.0
        self.sig_stats.emit(self.rx_count, self.err_count, pass_rate)

        if "$TELEM" in payload:
            data = {}
            for token in payload.replace("$TELEM,", "").split(","):
                if "=" in token:
                    k, v = token.split("=", 1)
                    k, v = k.strip(), v.strip()
                    try:
                        if k in ["TGT", "RPM", "DUTY"]: data[k] = float(v)
                        elif k in ["CNT", "PIR", "VIB", "FLT"]: data[k] = int(v)
                        elif k in ["TMP", "HUM"]: data[k] = float(v) / 10.0
                        else: data[k] = v
                    except: data[k] = v
            data["TIMESTAMP"] = time.strftime("%H:%M:%S")
            self.sig_telemetry.emit(data)
        elif "$FAULT" in payload:
            reason = payload.split("REASON=")[1].split(",")[0].strip() if "REASON=" in payload else "UNKNOWN"
            self.sig_fault.emit({"REASON": reason, "TIMESTAMP": time.strftime("%H:%M:%S")})

    def stop(self):
        self.running = False
        self.wait(1000)


# ==============================================================================
# MAIN DIGITAL COCKPIT WINDOW
# ==============================================================================
class AutomotiveCockpitWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STM32MP157 Automotive Virtual Cockpit & Domain Gateway (AUTOSAR / OpenSTLinux)")
        self.resize(1380, 880)

        self.history_len = 250
        self.time_history = deque(maxlen=self.history_len)
        self.target_rpm_history = deque(maxlen=self.history_len)
        self.actual_rpm_history = deque(maxlen=self.history_len)
        self.vib_history = deque(maxlen=self.history_len)
        self.start_time = time.time()
        self.comm_worker = None

        self._init_ui()
        self._apply_cockpit_theme()
        self.combo_conn.setCurrentText("Demo Simulation")
        self._toggle_connection()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. TOP STATUS & CONNECTIVITY BAR
        top_bar = QFrame(); top_bar.setObjectName("topBar")
        tbl = QHBoxLayout(top_bar); tbl.setContentsMargins(14, 6, 14, 6)

        title_box = QVBoxLayout()
        t1 = QLabel("STM32MP157 DIGITAL COCKPIT INSTRUMENT CLUSTER"); t1.setObjectName("clusterTitle")
        t2 = QLabel("AUTOSAR Classic Chassis ECU (Cortex-M4 100Hz) ◄══ OpenAMP RPMsg ══► Telematics Gateway (Cortex-A7)"); t2.setObjectName("clusterSub")
        title_box.addWidget(t1); title_box.addWidget(t2)
        tbl.addLayout(title_box); tbl.addStretch()

        self.combo_conn = QComboBox()
        self.combo_conn.addItems(["Demo Simulation", "Serial (/dev/ttyACM0)", "TCP (10.8.82.37:8888)"])
        self.combo_conn.setFixedWidth(190)
        self.btn_connect = QPushButton("CONNECT"); self.btn_connect.setObjectName("btnConnect"); self.btn_connect.setFixedWidth(110)
        self.btn_connect.clicked.connect(self._toggle_connection)
        self.lbl_conn_ind = QLabel("● DISCONNECTED"); self.lbl_conn_ind.setObjectName("connStatusDisconnected")

        tbl.addWidget(QLabel("Link:")); tbl.addWidget(self.combo_conn); tbl.addWidget(self.btn_connect); tbl.addWidget(self.lbl_conn_ind)
        main_layout.addWidget(top_bar)

        # 2. TELL-TALE WARNING STRIP
        self.telltale = AutomotiveTellTaleBar()
        main_layout.addWidget(self.telltale)

        # 3. MAIN COCKPIT CLUSTER (GAUGE 1 - CAR GRAPHIC - GAUGE 2)
        cluster_frame = QFrame(); cluster_frame.setObjectName("clusterFrame")
        cfl = QHBoxLayout(cluster_frame); cfl.setContentsMargins(16, 12, 16, 12); cfl.setSpacing(18)

        # Gauge 1: Speedometer (Motor Velocity RPM)
        self.gauge_speed = AutomotiveGauge(title="MOTOR SPEED", unit="RPM", min_val=0.0, max_val=30.0,
                                           major_ticks=6, minor_ticks=4, color_theme="cyan")
        cfl.addWidget(self.gauge_speed, stretch=1)

        # Center: 3D Car Wireframe & Radar
        self.car_display = VehicleCockpitCenter()
        cfl.addWidget(self.car_display, stretch=1)

        # Gauge 2: Power / Duty Cycle (%)
        self.gauge_duty = AutomotiveGauge(title="MOTOR POWER", unit="DUTY %", min_val=0.0, max_val=100.0,
                                          major_ticks=5, minor_ticks=4, color_theme="amber")
        cfl.addWidget(self.gauge_duty, stretch=1)

        main_layout.addWidget(cluster_frame, stretch=0)

        # 4. LOWER DECK: DRIVE CONTROLS (PRND) & REAL-TIME OSCILLOSCOPE
        lower_deck = QHBoxLayout(); lower_deck.setSpacing(10)

        # 4.1 Drive Shifter & Command Center
        ctrl_card = QFrame(); ctrl_card.setObjectName("controlCard")
        ccl = QVBoxLayout(ctrl_card); ccl.setContentsMargins(14, 12, 14, 12); ccl.setSpacing(10)

        lbl_drive = QLabel("TRANSMISSION & DRIVE SELECTOR"); lbl_drive.setObjectName("cardHeader")
        ccl.addWidget(lbl_drive)

        # PRND Mode Buttons
        prnd_box = QHBoxLayout()
        self.btn_mode_p = QPushButton("P"); self.btn_mode_p.setObjectName("btnPrnd")
        self.btn_mode_d = QPushButton("D (PID)"); self.btn_mode_d.setObjectName("btnPrndActive")
        self.btn_mode_s = QPushButton("S (STEP)"); self.btn_mode_s.setObjectName("btnPrnd")
        self.btn_mode_p.clicked.connect(lambda: self._set_drive_mode("STOP"))
        self.btn_mode_d.clicked.connect(lambda: self._set_drive_mode("PID"))
        self.btn_mode_s.clicked.connect(lambda: self._set_drive_mode("OPEN"))
        prnd_box.addWidget(self.btn_mode_p); prnd_box.addWidget(self.btn_mode_d); prnd_box.addWidget(self.btn_mode_s)
        ccl.addLayout(prnd_box)

        # Speed Stepper & Presets
        ccl.addWidget(QLabel("Cruise Control Setpoint (RPM):"))
        sp_layout = QHBoxLayout()
        self.slider_speed = QSlider(Qt.Horizontal if hasattr(Qt, 'Horizontal') else Qt.Orientation.Horizontal)
        self.slider_speed.setRange(0, 30); self.slider_speed.setValue(12)
        self.spin_speed = QSpinBox(); self.spin_speed.setRange(0, 30); self.spin_speed.setValue(12)
        self.slider_speed.valueChanged.connect(self.spin_speed.setValue)
        self.spin_speed.valueChanged.connect(self.slider_speed.setValue)
        sp_layout.addWidget(self.slider_speed); sp_layout.addWidget(self.spin_speed)
        ccl.addLayout(sp_layout)

        pre_box = QHBoxLayout()
        for r in [8, 10, 12, 15]:
            bp = QPushButton(f"{r} RPM"); bp.setObjectName("btnPreset")
            bp.clicked.connect(lambda ch, v=r: self._preset_speed(v))
            pre_box.addWidget(bp)
        ccl.addLayout(pre_box)

        self.btn_apply = QPushButton("⚡ ENGAGE SPEED"); self.btn_apply.setObjectName("btnEngage")
        self.btn_apply.clicked.connect(self._apply_control)
        ccl.addWidget(self.btn_apply)

        # Safety E-Stop & Clear Buttons
        ccl.addWidget(QFrame(frameShape=QFrame.HLine if hasattr(QFrame, 'HLine') else QFrame.Shape.HLine))
        self.btn_estop = QPushButton("🛑 EMERGENCY BRAKE (ESTOP)"); self.btn_estop.setObjectName("btnEstopBig")
        self.btn_estop.clicked.connect(self._trigger_estop)
        ccl.addWidget(self.btn_estop)

        self.btn_clear = QPushButton("🔄 RELEASE BRAKE / CLEAR"); self.btn_clear.setObjectName("btnClearSoft")
        self.btn_clear.clicked.connect(self._clear_fault)
        ccl.addWidget(self.btn_clear)

        sim_tools = QHBoxLayout()
        self.btn_t_pir = QPushButton("Sim PIR"); self.btn_t_pir.clicked.connect(self._sim_pir)
        self.btn_t_shk = QPushButton("Sim 3.5g Shock"); self.btn_t_shk.clicked.connect(self._sim_shock)
        sim_tools.addWidget(self.btn_t_pir); sim_tools.addWidget(self.btn_t_shk)
        ccl.addLayout(sim_tools)

        ccl.addStretch()
        lower_deck.addWidget(ctrl_card, stretch=1)

        # 4.2 High-Speed Real-Time Telemetry Oscilloscope
        chart_card = QFrame(); chart_card.setObjectName("chartCard")
        ccl2 = QVBoxLayout(chart_card); ccl2.setContentsMargins(12, 10, 12, 10); ccl2.setSpacing(6)

        ch_head = QHBoxLayout()
        ch_title = QLabel("TELEMATICS DYNAMICS WAVEFORM (Closed-Loop PID @ 100 Hz)"); ch_title.setObjectName("cardHeader")
        self.lbl_nfr5_badge = QLabel("e_ss: 0.00 RPM (PASSED NFR-5)"); self.lbl_nfr5_badge.setObjectName("badgePass")
        ch_head.addWidget(ch_title); ch_head.addStretch(); ch_head.addWidget(self.lbl_nfr5_badge)
        ccl2.addLayout(ch_head)

        self.plot_speed = pg.PlotWidget()
        self.plot_speed.setBackground("#10131e")
        self.plot_speed.showGrid(x=True, y=True, alpha=0.25)
        self.plot_speed.setLabel("left", "Speed", units="RPM")
        self.plot_speed.setLabel("bottom", "Time", units="s")
        self.plot_speed.addLegend(offset=(10, 8))
        self.curve_tgt = self.plot_speed.plot(pen=pg.mkPen(color='#ff3b5c', width=2, style=Qt.DashLine if hasattr(Qt, 'DashLine') else Qt.PenStyle.DashLine), name="Target Setpoint")
        self.curve_rpm = self.plot_speed.plot(pen=pg.mkPen(color='#00e676', width=2.5), name="Measured Motor Speed")
        ccl2.addWidget(self.plot_speed)

        lower_deck.addWidget(chart_card, stretch=2)
        main_layout.addLayout(lower_deck, stretch=1)

        # 5. BOTTOM STATUS BAR
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.lbl_stats = QLabel("Telemetry: 0 frames | CRC-16 Check: 100.0% | Status: Online")
        self.status_bar.addPermanentWidget(self.lbl_stats)

    # --------------------------------------------------------------------------
    # CONTROLS & EVENT HANDLERS
    # --------------------------------------------------------------------------
    def _toggle_connection(self):
        if self.comm_worker and self.comm_worker.isRunning():
            self.comm_worker.stop()
            self.comm_worker = None
            self.btn_connect.setText("CONNECT")
            self.lbl_conn_ind.setText("● DISCONNECTED")
            self.lbl_conn_ind.setObjectName("connStatusDisconnected")
            self._apply_cockpit_theme()
            return

        choice = self.combo_conn.currentText()
        if "Demo" in choice:
            self.comm_worker = CommWorker(mode="demo")
        elif "Serial" in choice:
            self.comm_worker = CommWorker(mode="serial", port="/dev/ttyACM0")
        else:
            self.comm_worker = CommWorker(mode="tcp", host="10.8.82.37", tcp_port=8888)

        self.comm_worker.sig_telemetry.connect(self._on_telemetry)
        self.comm_worker.sig_fault.connect(self._on_fault)
        self.comm_worker.sig_status.connect(self._on_status)
        self.comm_worker.sig_stats.connect(self._on_stats)
        self.comm_worker.start()

        self.btn_connect.setText("DISCONNECT")
        self.lbl_conn_ind.setText("● CONNECTED")
        self.lbl_conn_ind.setObjectName("connStatusConnected")
        self._apply_cockpit_theme()

    def _on_status(self, msg: str, is_ok: bool):
        self.status_bar.showMessage(msg, 4000)

    def _on_stats(self, rx: int, err: int, rate: float):
        self.lbl_stats.setText(f"Telemetry: {rx:,} frames | CRC-16 Check: {rate:.1f}% | Errors: {err}")

    def _set_drive_mode(self, mode: str):
        if mode == "STOP":
            self.btn_mode_p.setObjectName("btnPrndActive")
            self.btn_mode_d.setObjectName("btnPrnd")
            self.btn_mode_s.setObjectName("btnPrnd")
            if self.comm_worker: self.comm_worker.send_command("STOP")
        elif mode == "PID":
            self.btn_mode_p.setObjectName("btnPrnd")
            self.btn_mode_d.setObjectName("btnPrndActive")
            self.btn_mode_s.setObjectName("btnPrnd")
            self._apply_control()
        else:
            self.btn_mode_p.setObjectName("btnPrnd")
            self.btn_mode_d.setObjectName("btnPrnd")
            self.btn_mode_s.setObjectName("btnPrndActive")
            if self.comm_worker: self.comm_worker.send_command("STEP 50")
        self._apply_cockpit_theme()

    def _preset_speed(self, r: int):
        self.spin_speed.setValue(r)
        self._set_drive_mode("PID")

    def _apply_control(self):
        if self.comm_worker:
            rpm = self.spin_speed.value()
            self.comm_worker.send_command(f"SPEED {rpm}")
            self.gauge_speed.set_target(rpm)
            self.status_bar.showMessage(f"Cruise Control Set: {rpm} RPM", 3000)

    def _trigger_estop(self):
        if self.comm_worker: self.comm_worker.send_command("ESTOP")

    def _clear_fault(self):
        if self.comm_worker: self.comm_worker.send_command("CLEAR")

    def _sim_pir(self):
        if self.comm_worker:
            pir = getattr(self.comm_worker, "sim_pir", 0)
            self.comm_worker.send_command("PIR OFF" if pir else "PIR ON")

    def _sim_shock(self):
        if self.comm_worker: self.comm_worker.send_command("SHOCK")

    def _on_telemetry(self, d: dict):
        now = time.time() - self.start_time
        rpm = float(d.get("RPM", 0.0))
        tgt = float(d.get("TGT", 0.0))
        duty = float(d.get("DUTY", 0.0))
        vib = int(d.get("VIB", 980))
        pir = int(d.get("PIR", 0))
        flt = int(d.get("FLT", 0))
        temp = float(d.get("TMP", 26.2))
        hum = float(d.get("HUM", 38.0))

        # Update Gauges
        self.gauge_speed.set_value(rpm)
        self.gauge_speed.set_target(tgt)
        self.gauge_duty.set_value(duty)

        # Update Car Silhouette & Radar
        self.car_display.update_state(bool(pir), vib / 1000.0, rpm, d.get("MODE", "PID"))

        # Update Tell-Tale Warnings
        self.telltale.update_states(flt, pir, vib, temp, hum)

        # Update Oscilloscope Plot
        self.time_history.append(now)
        self.target_rpm_history.append(tgt)
        self.actual_rpm_history.append(rpm)
        self.curve_tgt.setData(list(self.time_history), list(self.target_rpm_history))
        self.curve_rpm.setData(list(self.time_history), list(self.actual_rpm_history))

        # Check NFR-5 Steady-State Error Requirement (e_ss <= 2.0 RPM)
        if tgt > 0:
            ess = abs(tgt - rpm)
            if ess <= 2.0:
                self.lbl_nfr5_badge.setText(f"e_ss: {ess:.2f} RPM (PASSED NFR-5)")
                self.lbl_nfr5_badge.setObjectName("badgePass")
            else:
                self.lbl_nfr5_badge.setText(f"e_ss: {ess:.2f} RPM (Transient)")
                self.lbl_nfr5_badge.setObjectName("badgeWarn")
        else:
            self.lbl_nfr5_badge.setText("e_ss: 0.00 RPM (PASSED NFR-5)")
            self.lbl_nfr5_badge.setObjectName("badgePass")

        self._apply_cockpit_theme()

    def _on_fault(self, fd: dict):
        reason = fd.get("REASON", "FAULT")
        self.status_bar.showMessage(f"🚨 BLACKBOX RECORDER EVENT: {reason}", 6000)

    # --------------------------------------------------------------------------
    # STYLING (AUTOMOTIVE VIRTUAL COCKPIT DARK THEME)
    # --------------------------------------------------------------------------
    def _apply_cockpit_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0d14;
            }
            #topBar, #clusterFrame, #controlCard, #chartCard {
                background-color: #121622;
                border: 1px solid #1f2538;
                border-radius: 8px;
            }
            #clusterTitle {
                color: #00d2ff;
                font-size: 13pt;
                font-weight: bold;
                letter-spacing: 1px;
            }
            #clusterSub {
                color: #7b8599;
                font-size: 8pt;
            }
            #cardHeader {
                color: #00d2ff;
                font-size: 9pt;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            #connStatusConnected {
                color: #00e676;
                font-weight: bold;
            }
            #connStatusDisconnected {
                color: #ff3b5c;
                font-weight: bold;
            }
            QLabel {
                color: #d8e2ec;
                font-size: 9pt;
            }
            #badgePass {
                background-color: #103322;
                color: #00e676;
                font-weight: bold;
                border: 1px solid #00e676;
                border-radius: 4px;
                padding: 3px 8px;
            }
            #badgeWarn {
                background-color: #382c10;
                color: #ffab00;
                font-weight: bold;
                border: 1px solid #ffab00;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QPushButton {
                background-color: #1c2234;
                color: #e6edf3;
                border: 1px solid #2d3652;
                border-radius: 5px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #273049;
                border-color: #00d2ff;
            }
            #btnPrnd {
                background-color: #161c2b;
                color: #8b949e;
                font-size: 10pt;
                border: 1px solid #232b40;
                padding: 8px;
            }
            #btnPrndActive {
                background-color: #00e676;
                color: #09120e;
                font-size: 10pt;
                font-weight: bold;
                border: 1px solid #00e676;
                padding: 8px;
            }
            #btnEngage {
                background-color: #00b0ff;
                color: #0a111a;
                font-size: 10pt;
                padding: 8px;
            }
            #btnEngage:hover {
                background-color: #40c4ff;
            }
            #btnEstopBig {
                background-color: #ff1744;
                color: #ffffff;
                font-size: 10pt;
                padding: 9px;
            }
            #btnEstopBig:hover {
                background-color: #d50000;
            }
            #btnClearSoft {
                background-color: #ffab00;
                color: #141006;
                padding: 6px;
            }
            #btnPreset {
                background-color: #181f30;
                color: #a0aec0;
                border: 1px solid #26314c;
            }
            #btnPreset:hover {
                background-color: #222c45;
                color: #ffffff;
                border-color: #00d2ff;
            }
            QComboBox, QSpinBox {
                background-color: #181f30;
                color: #ffffff;
                border: 1px solid #2d3652;
                border-radius: 4px;
                padding: 4px;
            }
            QStatusBar {
                background-color: #0d1017;
                color: #7b8599;
            }
        """)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = AutomotiveCockpitWindow()
    win.show()
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


if __name__ == "__main__":
    main()
