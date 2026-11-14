#!/usr/bin/env python3
"""
=============================================================================
 gateway_daemon.py - Automotive Domain Gateway Daemon (Cortex-A7 OpenSTLinux)
=============================================================================
 Part of STM32MP157D-DK1 Automotive Gateway & Real-Time Motor Controller (Week 9)
 
 Key Features:
 1. IPC Manager (/dev/ttyRPMSG0):
    - Reads high-frequency telemetry ($TELEM) & safety alerts ($FAULT)
    - Full CRC-16-CCITT verification matching Cortex-M4 Cdd_Ipc
    - Automatic Heartbeat generator (500ms) to feed M4 Watchdog
 2. Local SQLite3 Database Engine:
    - Standard library sqlite3 engine with WAL journal mode
    - 'telemetry_history': Time-series engine metrics & sensor data with batched commits
    - 'safety_events': Tamper-proof blackbox accident & E-Stop recorder
 3. MQTT Telematics IoT Gateway:
    - Lightweight pure-socket MQTT v3.1.1 client (No external pip packages)
    - Publishes JSON telemetry to: automotive/ecu/telemetry
    - Publishes instant alerts to:  automotive/ecu/alert
    - Subscribes to commands on:   automotive/ecu/control
 4. Non-blocking TCP Server Bridge:
    - Multiplexed raw telemetry broadcast to remote dashboards (e.g. qt_dashboard.py)
    - Ingests remote control commands and forwards to Cortex-M4 over RPMsg
 5. Systemd Auto-recovery & Diagnostic CLI
=============================================================================
"""

import os
import sys
import time
import socket
import select
import sqlite3
import argparse
import json
import re

try:
    import termios
except ImportError:
    termios = None

# =============================================================================
# Configuration & Constants
# =============================================================================
DEFAULT_RPMSG_DEV = "/dev/ttyRPMSG0"
DEFAULT_DB_PATH   = "/home/root/telemetry.db"
DEFAULT_MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
DEFAULT_MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
DEFAULT_TCP_HOST  = os.environ.get("GATEWAY_TCP_HOST", "0.0.0.0")
DEFAULT_TCP_PORT  = int(os.environ.get("GATEWAY_TCP_PORT", 8888))
DEVICE_ID         = "STM32MP157-GATEWAY-01"

# =============================================================================
# CRC-16-CCITT Verification (Poly: 0x1021, Init: 0xFFFF)
# =============================================================================
def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

# =============================================================================
# Standard SQLite3 Database Interface (WAL mode + Batched Commits)
# =============================================================================
class SqliteDatabase:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception:
                pass
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self._uncommitted_count = 0
        self._last_commit_time = time.time()
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                mode TEXT,
                target_rpm REAL,
                actual_rpm REAL,
                duty_pct REAL,
                pulse_cnt INTEGER,
                pir_motion INTEGER,
                vibration_mg INTEGER,
                temp_c REAL,
                hum_pct REAL,
                fault_code INTEGER
            );

            CREATE TABLE IF NOT EXISTS safety_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                event_type TEXT,
                reason TEXT,
                raw_frame TEXT
            );
            """)

    def flush(self):
        """Commit any pending batch to the database."""
        if self._uncommitted_count > 0:
            try:
                self.conn.commit()
            except Exception as e:
                print(f"[SQLITE_ERR] flush error: {e}")
            self._uncommitted_count = 0
            self._last_commit_time = time.time()

    def close(self):
        self.flush()
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass

    def insert_telemetry(self, d: dict):
        """Insert telemetry row with batched commits (batch >= 20 or elapsed >= 0.5s)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry_history (
                mode, target_rpm, actual_rpm, duty_pct, pulse_cnt,
                pir_motion, vibration_mg, temp_c, hum_pct, fault_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            str(d.get("mode", "UNKNOWN")),
            float(d.get("tgt", 0.0)),
            float(d.get("rpm", 0.0)),
            float(d.get("duty", 0.0)),
            int(d.get("cnt", 0)),
            int(d.get("pir", 0)),
            int(d.get("vib", 0)),
            float(d.get("tmp", 0.0)),
            float(d.get("hum", 0.0)),
            int(d.get("flt", 0))
        ))
        self._uncommitted_count += 1
        now = time.time()
        if self._uncommitted_count >= 20 or (now - self._last_commit_time) >= 0.5:
            self.flush()

    log_telemetry = insert_telemetry

    def log_safety_event(self, event_type: str, reason: str, raw_frame: str):
        """Blackbox recorder: logs safety event and commits immediately."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO safety_events (event_type, reason, raw_frame)
            VALUES (?, ?, ?);
        """, (str(event_type), str(reason), str(raw_frame)))
        self.conn.commit()
        self._uncommitted_count = 0
        self._last_commit_time = time.time()

    def query_recent(self, limit: int = 10) -> list:
        self.flush()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, mode, actual_rpm, duty_pct,
                   pir_motion, vibration_mg, temp_c, hum_pct, fault_code
            FROM telemetry_history
            ORDER BY id DESC LIMIT ?;
        """, (limit,))
        return cursor.fetchall()

    def query_events(self, limit: int = 10) -> list:
        self.flush()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, event_type, reason, raw_frame
            FROM safety_events
            ORDER BY id DESC LIMIT ?;
        """, (limit,))
        return cursor.fetchall()

    def execute(self, sql_commands: str, params=()) -> str:
        """Pipes SQL commands for backward compatibility and CLI inspections."""
        self.flush()
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql_commands, params)
            rows = cursor.fetchall()
            if rows:
                return "\n".join("|".join(str(val) for val in row) for row in rows)
            self.conn.commit()
            return ""
        except Exception as e:
            return f"SQLITE_ERR: {e}"

# =============================================================================
# Lightweight Pure-Socket MQTT Client (Zero external pip dependencies)
# =============================================================================
class SimpleMqttClient:
    def __init__(self, host=DEFAULT_MQTT_HOST, port=DEFAULT_MQTT_PORT, client_id=DEVICE_ID):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.sock = None
        self.connected = False
        self.rx_buf = bytearray()

    @staticmethod
    def _encode_remaining_length(length: int) -> bytearray:
        enc = bytearray()
        val = length
        while True:
            b = val % 128
            val //= 128
            if val > 0:
                b |= 128
            enc.append(b)
            if val <= 0:
                break
        return enc

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1.0)
            self.sock.connect((self.host, self.port))
            
            # MQTT Connect Packet v3.1.1
            cid_bytes = self.client_id.encode('utf-8')
            payload = bytearray([0x00, len(cid_bytes)]) + cid_bytes
            var_header = b"\x00\x04MQTT\x04\x02\x00<\x00"  # Clean session, keepalive 60s
            rem_len = len(var_header) + len(payload)
            pkt = bytearray([0x10]) + self._encode_remaining_length(rem_len) + var_header + payload
            
            self.sock.sendall(pkt)
            ack = self.sock.recv(4)
            if len(ack) >= 4 and ack[0] == 0x20 and ack[3] == 0x00:
                self.connected = True
                self.rx_buf = bytearray()
                return True
        except Exception:
            pass
        self.disconnect()
        return False

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.rx_buf = bytearray()

    def publish(self, topic: str, msg: str):
        if not self.connected or not self.sock:
            return
        try:
            t_bytes = topic.encode('utf-8')
            p_bytes = msg.encode('utf-8')
            rem_len = 2 + len(t_bytes) + len(p_bytes)
            rem_enc = self._encode_remaining_length(rem_len)
            pkt = (bytearray([0x30]) + rem_enc + 
                   bytearray([len(t_bytes) >> 8, len(t_bytes) & 0xFF]) + 
                   t_bytes + p_bytes)
            self.sock.sendall(pkt)
        except Exception:
            self.disconnect()

    def subscribe(self, topic: str) -> bool:
        """MQTT SUBSCRIBE packet (0x82) with packet ID 1 and QoS 0."""
        if not self.connected or not self.sock:
            return False
        try:
            t_bytes = topic.encode('utf-8')
            payload = (bytearray([0x00, 0x01]) + 
                       bytearray([len(t_bytes) >> 8, len(t_bytes) & 0xFF]) + 
                       t_bytes + bytearray([0x00]))
            rem_enc = self._encode_remaining_length(len(payload))
            pkt = bytearray([0x82]) + rem_enc + payload
            self.sock.sendall(pkt)
            
            ack = self.sock.recv(5)
            if len(ack) >= 3 and ack[0] == 0x90:
                return True
            return True
        except Exception:
            self.disconnect()
            return False

    def ping(self):
        """Send MQTT PINGREQ (0xC0, 0x00)."""
        if self.connected and self.sock:
            try:
                self.sock.sendall(b"\xc0\x00")
            except Exception:
                self.disconnect()

    def poll_messages(self) -> list:
        """
        Polls incoming MQTT messages using select.select without blocking.
        Parses PUBLISH packets (0x30..0x3F) into (topic, payload_str) tuples.
        Handles PINGRESP (0xD0) and SUBACK (0x90).
        """
        messages = []
        if not self.connected or not self.sock:
            return messages

        try:
            r, _, _ = select.select([self.sock], [], [], 0.0)
            if r:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.disconnect()
                    return messages
                self.rx_buf.extend(chunk)
        except Exception:
            self.disconnect()
            return messages

        idx = 0
        buf_len = len(self.rx_buf)
        while idx < buf_len:
            pkt_type_flags = self.rx_buf[idx]
            pkt_type = pkt_type_flags & 0xF0

            rem_len = 0
            multiplier = 1
            len_bytes = 0
            pos = idx + 1
            while pos < buf_len:
                byte = self.rx_buf[pos]
                pos += 1
                len_bytes += 1
                rem_len += (byte & 127) * multiplier
                multiplier *= 128
                if (byte & 128) == 0:
                    break
                if len_bytes > 4:
                    break
            else:
                break

            total_pkt_len = 1 + len_bytes + rem_len
            if buf_len - idx < total_pkt_len:
                break

            packet_data = self.rx_buf[pos : idx + total_pkt_len]

            if pkt_type == 0xD0:
                # PINGRESP
                pass
            elif pkt_type == 0x90:
                # SUBACK
                pass
            elif pkt_type == 0x30:
                # PUBLISH
                qos = (pkt_type_flags >> 1) & 0x03
                if len(packet_data) >= 2:
                    tlen = (packet_data[0] << 8) | packet_data[1]
                    topic = packet_data[2 : 2 + tlen].decode('utf-8', errors='ignore')
                    data_offset = 2 + tlen
                    if qos > 0:
                        data_offset += 2
                    payload_str = packet_data[data_offset:].decode('utf-8', errors='ignore')
                    messages.append((topic, payload_str))

            idx += total_pkt_len

        if idx > 0:
            self.rx_buf = self.rx_buf[idx:]
        return messages

# =============================================================================
# Linux Automotive Gateway Daemon Core
# =============================================================================
class GatewayDaemon:
    TOPIC_CONTROL = "automotive/ecu/control"
    TOPIC_TELEMETRY = "automotive/ecu/telemetry"
    TOPIC_ALERT = "automotive/ecu/alert"

    def __init__(self, dev_path=DEFAULT_RPMSG_DEV, db_path=DEFAULT_DB_PATH,
                 mqtt_host=DEFAULT_MQTT_HOST, mqtt_port=DEFAULT_MQTT_PORT,
                 tcp_host=DEFAULT_TCP_HOST, tcp_port=DEFAULT_TCP_PORT):
        self.dev_path = dev_path
        self.db = SqliteDatabase(db_path)
        self.mqtt = SimpleMqttClient(host=mqtt_host, port=mqtt_port)
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.tcp_server_sock = None
        self.tcp_clients = []
        self.tcp_client_buffers = {}
        self.fd = None
        self.running = False
        self.last_hb = 0.0
        self.last_mqtt_retry = 0.0
        self.rx_buffer = ""
        self.crc_err_count = 0
        self.latest_telemetry = None

    def init_port(self):
        if not os.path.exists(self.dev_path):
            raise FileNotFoundError(f"RPMsg device {self.dev_path} not found. Is M4 firmware started?")
        
        flags = os.O_RDWR
        if hasattr(os, "O_NOCTTY"):
            flags |= os.O_NOCTTY
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        self.fd = os.open(self.dev_path, flags)
        if termios is not None:
            try:
                attrs = termios.tcgetattr(self.fd)
                attrs[0] = 0  # iflag (raw)
                attrs[1] = 0  # oflag (raw)
                attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | termios.B115200
                attrs[3] = 0  # lflag (raw)
                attrs[4] = termios.B115200
                attrs[5] = termios.B115200
                termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            except Exception as e:
                print(f"[WARN] termios config: {e}")

    def init_tcp_bridge(self):
        try:
            self.tcp_server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.tcp_server_sock.bind((self.tcp_host, self.tcp_port))
            self.tcp_server_sock.listen(5)
            self.tcp_server_sock.setblocking(False)
            print(f"[TCP_BRIDGE] Listening on {self.tcp_host}:{self.tcp_port}")
        except Exception as e:
            print(f"[WARN] TCP bridge bind error ({self.tcp_host}:{self.tcp_port}): {e}")
            self.tcp_server_sock = None

    def _remove_tcp_client(self, client):
        if client in self.tcp_clients:
            self.tcp_clients.remove(client)
        self.tcp_client_buffers.pop(client, None)
        try:
            client.close()
        except Exception:
            pass

    def broadcast_tcp(self, line: str):
        if not self.tcp_clients:
            return
        msg = (line.strip() + "\n").encode('utf-8')
        dead_clients = []
        for client in self.tcp_clients:
            try:
                client.sendall(msg)
            except Exception:
                dead_clients.append(client)
        for client in dead_clients:
            self._remove_tcp_client(client)

    def process_mqtt_commands(self):
        if not self.mqtt.connected:
            return
        messages = self.mqtt.poll_messages()
        for topic, payload in messages:
            if topic == self.TOPIC_CONTROL:
                cmd = payload.strip()
                if cmd:
                    print(f"[MQTT_CMD] Forwarding to M4: '{cmd}'")
                    self.send_m4(cmd)

    def send_m4(self, cmd: str):
        if self.fd is not None:
            try:
                data = (cmd.strip() + "\r\n").encode('ascii')
                os.write(self.fd, data)
            except Exception as e:
                print(f"[WARN] send_m4 error: {e}")

    def parse_and_process_line(self, line: str):
        line = line.strip()
        if not line or "*" not in line:
            return

        payload, crc_hex = line.split("*", 1)
        try:
            expected_crc = int(crc_hex, 16)
        except ValueError:
            self.crc_err_count += 1
            return

        # Check CRC-16-CCITT
        calc_crc = crc16_ccitt(payload.encode('ascii'))
        if calc_crc != expected_crc:
            self.crc_err_count += 1
            print(f"[CRC_ERROR] Frame: {line} (Calc: 0x{calc_crc:04X} != Exp: 0x{expected_crc:04X})")
            return

        # Broadcast verified frame to TCP dashboard clients
        self.broadcast_tcp(line)

        # 1. Parse Telemetry Frame:
        # $TELEM,MODE=PID,TGT=10,RPM=9,DUTY=78,CNT=2287,PIR=0,VIB=980,TMP=248,HUM=380,FLT=0,DHT=3/0
        if payload.startswith("$TELEM"):
            parts = payload.split(",")[1:]
            d = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    d[k] = v
            
            telem_data = {
                "mode": d.get("MODE", "UNKNOWN"),
                "tgt":  float(d.get("TGT", 0.0)),
                "rpm":  float(d.get("RPM", 0.0)),
                "duty": float(d.get("DUTY", 0.0)),
                "cnt":  int(d.get("CNT", 0)),
                "pir":  int(d.get("PIR", 0)),
                "vib":  int(d.get("VIB", 0)),
                "tmp":  float(d.get("TMP", 0.0)) / 10.0,
                "hum":  float(d.get("HUM", 0.0)) / 10.0,
                "flt":  int(d.get("FLT", 0)),
                "dht":  d.get("DHT", "0/0")
            }

            self.latest_telemetry = telem_data

            # Log to SQLite Database
            self.db.insert_telemetry(telem_data)

            # Publish to MQTT Broker
            if self.mqtt.connected:
                mqtt_payload = {
                    "device_id": DEVICE_ID,
                    "timestamp": time.time(),
                    "motor": {
                        "mode": telem_data["mode"],
                        "target_rpm": telem_data["tgt"],
                        "actual_rpm": telem_data["rpm"],
                        "duty_pct": telem_data["duty"],
                        "pulse_cnt": telem_data["cnt"]
                    },
                    "sensors": {
                        "pir_motion": telem_data["pir"],
                        "vibration_mg": telem_data["vib"],
                        "temperature_c": telem_data["tmp"],
                        "humidity_pct": telem_data["hum"]
                    },
                    "safety": {
                        "fault_code": telem_data["flt"]
                    }
                }
                self.mqtt.publish(self.TOPIC_TELEMETRY, json.dumps(mqtt_payload))

            print(f"[{telem_data['mode']}] RPM:{telem_data['rpm']:4.1f} | DUTY:{telem_data['duty']:4.1f}% | PIR:{telem_data['pir']} | VIB:{telem_data['vib']:4d}mg | T:{telem_data['tmp']:4.1f}C | H:{telem_data['hum']:4.1f}% | FLT:{telem_data['flt']}")

        # 2. Parse Safety Alert Frame: $FAULT,REASON=CRASH_VIBRATION
        elif payload.startswith("$FAULT"):
            reason = "UNKNOWN"
            if "REASON=" in payload:
                reason = payload.split("REASON=", 1)[1]
            
            print(f"\n[!!! SAFETY ALERT CRITICAL !!!] E-STOP TRIGGERED: {reason}")
            # Record to SQLite Blackbox
            self.db.log_safety_event("FAULT", reason, line)

            # Publish High-Priority MQTT Alert
            if self.mqtt.connected:
                alert_payload = {
                    "device_id": DEVICE_ID,
                    "timestamp": time.time(),
                    "event": "EMERGENCY_STOP",
                    "reason": reason,
                    "raw_frame": line
                }
                self.mqtt.publish(self.TOPIC_ALERT, json.dumps(alert_payload))

    def run(self):
        print("==================================================================")
        print(f"   Automotive Gateway Daemon Started on {DEVICE_ID}")
        print(f"   IPC Port: {self.dev_path} | SQLite: {self.db.db_path}")
        print(f"   TCP Bridge: {self.tcp_host}:{self.tcp_port}")
        print("==================================================================")
        
        self.init_port()
        self.init_tcp_bridge()
        self.running = True
        
        # Initial Handshake & Sync
        self.send_m4("STATUS")
        time.sleep(0.1)
        self.send_m4("CLEAR")
        time.sleep(0.1)

        # Connect MQTT in background and subscribe to control commands
        if self.mqtt.connect():
            self.mqtt.subscribe(self.TOPIC_CONTROL)

        try:
            while self.running:
                now = time.time()

                # 1. Heartbeat generator (every 500ms)
                if now - self.last_hb >= 0.5:
                    self.send_m4("HB")
                    self.last_hb = now

                # 2. MQTT connection keepalive / retry (every 10s)
                if not self.mqtt.connected and (now - self.last_mqtt_retry >= 10.0):
                    self.last_mqtt_retry = now
                    if self.mqtt.connect():
                        self.mqtt.subscribe(self.TOPIC_CONTROL)

                # 3. Process incoming MQTT control commands
                self.process_mqtt_commands()

                # 4. Multiplex I/O: RPMsg device and TCP bridge sockets
                read_fds = []
                if self.fd is not None:
                    read_fds.append(self.fd)
                if self.tcp_server_sock is not None:
                    read_fds.append(self.tcp_server_sock)
                read_fds.extend(self.tcp_clients)

                try:
                    r, _, _ = select.select(read_fds, [], [], 0.05)
                except Exception:
                    read_fds = [s for s in read_fds if s not in self.tcp_clients]
                    self.tcp_clients = []
                    continue

                for src in r:
                    # Case A: RPMsg serial char dev
                    if src == self.fd:
                        chunk = os.read(self.fd, 512).decode('ascii', errors='ignore')
                        self.rx_buffer += chunk
                        while "\n" in self.rx_buffer:
                            line, self.rx_buffer = self.rx_buffer.split("\n", 1)
                            stripped = line.strip()
                            if stripped:
                                self.parse_and_process_line(stripped)

                    # Case B: New TCP dashboard client connection
                    elif src == self.tcp_server_sock:
                        try:
                            client_sock, client_addr = self.tcp_server_sock.accept()
                            client_sock.setblocking(False)
                            self.tcp_clients.append(client_sock)
                            self.tcp_client_buffers[client_sock] = ""
                            print(f"[TCP_BRIDGE] Dashboard connected from {client_addr}")
                        except Exception as e:
                            print(f"[WARN] TCP accept error: {e}")

                    # Case C: Incoming command from connected TCP dashboard client
                    elif src in self.tcp_clients:
                        try:
                            data = src.recv(1024).decode('utf-8', errors='ignore')
                            if not data:
                                self._remove_tcp_client(src)
                            else:
                                self.tcp_client_buffers[src] += data
                                while "\n" in self.tcp_client_buffers[src]:
                                    cmd, self.tcp_client_buffers[src] = self.tcp_client_buffers[src].split("\n", 1)
                                    cmd = cmd.strip()
                                    if cmd:
                                        print(f"[TCP_BRIDGE] Received command: '{cmd}'")
                                        self.send_m4(cmd)
                        except Exception:
                            self._remove_tcp_client(src)

        except KeyboardInterrupt:
            print("\n[DAEMON] Stopping Gateway Daemon...")
        finally:
            self.running = False
            self.db.close()
            self.mqtt.disconnect()
            for c in list(self.tcp_clients):
                self._remove_tcp_client(c)
            if self.tcp_server_sock is not None:
                try:
                    self.tcp_server_sock.close()
                except Exception:
                    pass
            if self.fd is not None:
                try:
                    os.close(self.fd)
                except Exception:
                    pass

# =============================================================================
# CLI Subcommands & Diagnostics
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Automotive Domain Gateway Daemon & Tool")
    parser.add_argument("--run", action="store_true", help="Start the main gateway daemon")
    parser.add_argument("--query-db", action="store_true", help="Show last 10 telemetry rows from SQLite")
    parser.add_argument("--query-events", action="store_true", help="Show blackbox safety events")
    parser.add_argument("--cmd", type=str, help="Send a command to M4 (e.g. 'SPEED 10', 'ESTOP')")
    parser.add_argument("--db-path", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite DB")
    parser.add_argument("--dev", type=str, default=DEFAULT_RPMSG_DEV, help="RPMsg character device")
    parser.add_argument("--tcp-host", type=str, default=DEFAULT_TCP_HOST, help="TCP server bridge bind host")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_TCP_PORT, help="TCP server bridge bind port")
    parser.add_argument("--mqtt-host", type=str, default=DEFAULT_MQTT_HOST, help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=DEFAULT_MQTT_PORT, help="MQTT broker port")
    args = parser.parse_args()

    db = SqliteDatabase(args.db_path)

    if args.query_db:
        print("\n=== RECENT TELEMETRY HISTORY (FROM SQLITE) ===")
        rows = db.query_recent(10)
        print(f"{'ID':<5} | {'Timestamp':<19} | {'Mode':<5} | {'RPM':<5} | {'Duty':<5} | {'PIR':<3} | {'VIB(mg)':<7} | {'Temp':<5} | {'Hum':<5} | {'FLT'}")
        print("-" * 80)
        for r in rows:
            print(f"{r[0]:<5} | {str(r[1]):<19} | {str(r[2]):<5} | {r[3]:<5.1f} | {r[4]:<5.1f} | {r[5]:<3} | {r[6]:<7} | {r[7]:<5.1f} | {r[8]:<5.1f} | {r[9]}")
        db.close()
        return

    if args.query_events:
        print("\n=== BLACKBOX SAFETY EVENTS (FROM SQLITE) ===")
        rows = db.query_events(10)
        print(f"{'ID':<5} | {'Timestamp':<19} | {'Type':<6} | {'Reason':<16} | {'Raw Frame'}")
        print("-" * 80)
        for r in rows:
            print(f"{r[0]:<5} | {str(r[1]):<19} | {str(r[2]):<6} | {str(r[3]):<16} | {r[4]}")
        db.close()
        return

    if args.cmd:
        print(f">>> Sending Command to M4: '{args.cmd}'")
        daemon = GatewayDaemon(dev_path=args.dev, db_path=args.db_path,
                               mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port,
                               tcp_host=args.tcp_host, tcp_port=args.tcp_port)
        daemon.init_port()
        daemon.send_m4(args.cmd)
        if daemon.fd is not None:
            os.close(daemon.fd)
        return

    # Default action: Run Daemon
    daemon = GatewayDaemon(dev_path=args.dev, db_path=args.db_path,
                           mqtt_host=args.mqtt_host, mqtt_port=args.mqtt_port,
                           tcp_host=args.tcp_host, tcp_port=args.tcp_port)
    daemon.run()

if __name__ == "__main__":
    main()
