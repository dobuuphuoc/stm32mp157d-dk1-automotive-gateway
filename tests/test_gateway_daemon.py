#!/usr/bin/env python3
"""
Unit tests for automotive domain gateway daemon (gateway_a7/gateway_daemon.py).
Compatible with both pytest and python -m unittest.
"""

import os
import sys
import json
import socket
import select
import tempfile
import unittest
from unittest.mock import MagicMock

# Ensure parent directory is on sys.path so gateway_a7 can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gateway_a7.gateway_daemon import (
    crc16_ccitt,
    SqliteDatabase,
    SimpleMqttClient,
    GatewayDaemon,
    DEVICE_ID,
)


class TestCrc16Ccitt(unittest.TestCase):
    """Test CRC-16-CCITT calculation (Poly 0x1021, Init 0xFFFF)."""

    def test_standard_test_vector(self):
        # Standard CCITT check value for "123456789" is 0x29B1
        data = b"123456789"
        expected = 0x29B1
        self.assertEqual(crc16_ccitt(data), expected)

    def test_empty_bytes(self):
        self.assertEqual(crc16_ccitt(b""), 0xFFFF)

    def test_telemetry_payload_deterministic(self):
        payload = b"$TELEM,MODE=PID,TGT=10,RPM=9,DUTY=78,CNT=2287,PIR=0,VIB=980,TMP=248,HUM=380,FLT=0,DHT=3/0"
        crc1 = crc16_ccitt(payload)
        crc2 = crc16_ccitt(payload)
        self.assertEqual(crc1, crc2)
        self.assertEqual(crc1, 0x0C65)

    def test_fault_payload_deterministic(self):
        payload = b"$FAULT,REASON=CRASH_VIBRATION"
        crc1 = crc16_ccitt(payload)
        crc2 = crc16_ccitt(payload)
        self.assertEqual(crc1, crc2)
        self.assertEqual(crc1, 0x94F9)

    def test_tamper_detection_single_bit(self):
        original = b"$TELEM,MODE=PID,TGT=10,RPM=9,DUTY=78,CNT=2287"
        crc_orig = crc16_ccitt(original)

        tampered = b"$TELEM,MODE=PID,TGT=10,RPM=8,DUTY=78,CNT=2287"
        crc_tampered = crc16_ccitt(tampered)

        self.assertNotEqual(crc_orig, crc_tampered)


class TestSqliteDatabase(unittest.TestCase):
    """Test SqliteDatabase schema, batched inserts, parameterized queries, and injection protection."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_telemetry.db")
        self.db = SqliteDatabase(self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_init_and_tables_created(self):
        rows = self.db.execute("SELECT name FROM sqlite_master WHERE type='table';")
        self.assertIn("telemetry_history", rows)
        self.assertIn("safety_events", rows)

    def test_insert_telemetry_and_flush(self):
        sample = {
            "mode": "PID",
            "tgt": 15.0,
            "rpm": 14.8,
            "duty": 72.5,
            "cnt": 1024,
            "pir": 1,
            "vib": 350,
            "tmp": 25.4,
            "hum": 45.0,
            "flt": 0,
        }
        self.db.insert_telemetry(sample)
        self.db.flush()

        recent = self.db.query_recent(limit=5)
        self.assertEqual(len(recent), 1)
        row = recent[0]
        # Columns: id, timestamp, mode, actual_rpm, duty_pct, pir_motion, vibration_mg, temp_c, hum_pct, fault_code
        self.assertEqual(row[2], "PID")
        self.assertAlmostEqual(row[3], 14.8, places=2)
        self.assertAlmostEqual(row[4], 72.5, places=2)
        self.assertEqual(row[5], 1)
        self.assertEqual(row[6], 350)
        self.assertAlmostEqual(row[7], 25.4, places=2)
        self.assertAlmostEqual(row[8], 45.0, places=2)
        self.assertEqual(row[9], 0)

    def test_auto_batch_flush_on_20_records(self):
        for i in range(25):
            self.db.insert_telemetry({"mode": "TEST", "tgt": float(i), "rpm": float(i)})
        # The first 20 records must have triggered an auto-flush
        # Let's inspect directly via sqlite3 cursor without calling self.db.flush()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM telemetry_history;")
        count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 20)

    def test_log_safety_event_sql_injection_defense(self):
        """Verify parameterized queries safely escape malicious SQL injection strings."""
        sqli_payload = "MANUAL'; DROP TABLE safety_events; --"
        raw_frame = "$FAULT,REASON=" + sqli_payload + "*1234"

        # Log malicious event
        self.db.log_safety_event("CRITICAL_FAULT", sqli_payload, raw_frame)

        # 1. Table must NOT be dropped
        rows = self.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='safety_events';")
        self.assertIn("safety_events", rows)

        # 2. Record must be safely inserted containing the raw literal SQL injection string
        events = self.db.query_events(limit=5)
        self.assertEqual(len(events), 1)
        # Columns: id, timestamp, event_type, reason, raw_frame
        self.assertEqual(events[0][2], "CRITICAL_FAULT")
        self.assertEqual(events[0][3], sqli_payload)
        self.assertEqual(events[0][4], raw_frame)

    def test_query_recent_ordering_and_limit(self):
        for i in range(10):
            self.db.insert_telemetry({"mode": f"M_{i}", "rpm": float(i)})
        self.db.flush()

        res_5 = self.db.query_recent(limit=5)
        self.assertEqual(len(res_5), 5)
        # Should be descending order by id
        self.assertEqual(res_5[0][2], "M_9")
        self.assertEqual(res_5[4][2], "M_5")

    def test_query_events_ordering_and_limit(self):
        for i in range(8):
            self.db.log_safety_event("FAULT", f"REASON_{i}", f"FRAME_{i}")

        events = self.db.query_events(limit=4)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0][3], "REASON_7")
        self.assertEqual(events[3][3], "REASON_4")


class TestSimpleMqttClient(unittest.TestCase):
    """Test pure-socket MQTT client protocol framing, publish, subscribe, and polling."""

    def test_encode_remaining_length(self):
        encode = SimpleMqttClient._encode_remaining_length
        self.assertEqual(bytes(encode(0)), b"\x00")
        self.assertEqual(bytes(encode(64)), b"\x40")
        self.assertEqual(bytes(encode(127)), b"\x7F")
        self.assertEqual(bytes(encode(128)), b"\x80\x01")
        self.assertEqual(bytes(encode(16383)), b"\xFF\x7F")
        self.assertEqual(bytes(encode(16384)), b"\x80\x80\x01")

    def test_connect_handshake(self):
        # Create loopback server socket to mock an MQTT broker
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        host, port = server.getsockname()

        client = SimpleMqttClient(host=host, port=port, client_id="TEST-CLIENT-01")

        # In non-blocking / accept flow
        server.settimeout(2.0)
        import threading

        def broker_side():
            conn, _ = server.accept()
            # Expect CONNECT packet: starts with 0x10
            pkt = conn.recv(1024)
            self.assertEqual(pkt[0], 0x10)
            self.assertIn(b"MQTT", pkt)
            self.assertIn(b"TEST-CLIENT-01", pkt)
            # Send CONNACK (0x20, 0x02, 0x00, 0x00)
            conn.sendall(b"\x20\x02\x00\x00")
            conn.close()

        th = threading.Thread(target=broker_side)
        th.start()

        ok = client.connect()
        th.join()
        server.close()

        self.assertTrue(ok)
        self.assertTrue(client.connected)
        client.disconnect()
        self.assertFalse(client.connected)

    def test_publish_packet_construction(self):
        s_cli, s_broker = socket.socketpair()
        client = SimpleMqttClient()
        client.sock = s_cli
        client.connected = True

        topic = "automotive/ecu/telemetry"
        msg = '{"speed":10.5}'
        client.publish(topic, msg)

        # Receive from mock broker
        raw_pkt = s_broker.recv(1024)
        # Byte 0: 0x30 (PUBLISH QoS 0)
        self.assertEqual(raw_pkt[0], 0x30)

        # Parse topic length
        # Remaining length starts at byte 1 (1 byte for len < 128)
        rem_len = raw_pkt[1]
        t_len = (raw_pkt[2] << 8) | raw_pkt[3]
        rx_topic = raw_pkt[4 : 4 + t_len].decode("utf-8")
        rx_payload = raw_pkt[4 + t_len :].decode("utf-8")

        self.assertEqual(rx_topic, topic)
        self.assertEqual(rx_payload, msg)

        client.disconnect()
        s_cli.close()
        s_broker.close()

    def test_subscribe_packet_and_ack(self):
        s_cli, s_broker = socket.socketpair()
        client = SimpleMqttClient()
        client.sock = s_cli
        client.connected = True

        import threading

        def mock_broker():
            req = s_broker.recv(1024)
            # Verify SUBSCRIBE byte (0x82)
            self.assertEqual(req[0], 0x82)
            self.assertIn(b"automotive/ecu/control", req)
            # Reply with SUBACK (0x90, rem_len 3, packet ID 1, QoS 0 granted)
            s_broker.sendall(b"\x90\x03\x00\x01\x00")

        th = threading.Thread(target=mock_broker)
        th.start()

        res = client.subscribe("automotive/ecu/control")
        th.join()

        self.assertTrue(res)
        client.disconnect()
        s_cli.close()
        s_broker.close()

    def test_poll_messages_handles_publish_and_pingresp(self):
        s_cli, s_broker = socket.socketpair()
        client = SimpleMqttClient()
        client.sock = s_cli
        client.connected = True

        # Construct incoming PUBLISH packet on topic "automotive/ecu/control" with payload "SPEED 20"
        topic = b"automotive/ecu/control"
        payload = b"SPEED 20"
        rem_len = 2 + len(topic) + len(payload)
        pub_pkt = bytearray([0x30, rem_len, len(topic) >> 8, len(topic) & 0xFF]) + topic + payload

        # Construct PINGRESP packet (0xD0, 0x00)
        pingresp_pkt = b"\xd0\x00"

        # Construct second PUBLISH packet with payload "ESTOP"
        payload2 = b"ESTOP"
        rem_len2 = 2 + len(topic) + len(payload2)
        pub_pkt2 = bytearray([0x30, rem_len2, len(topic) >> 8, len(topic) & 0xFF]) + topic + payload2

        # Send all in one stream to broker socket
        s_broker.sendall(pub_pkt + pingresp_pkt + pub_pkt2)

        # Allow socket buffer to settle
        r, _, _ = select.select([s_cli], [], [], 0.5)
        self.assertTrue(bool(r))

        messages = client.poll_messages()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], ("automotive/ecu/control", "SPEED 20"))
        self.assertEqual(messages[1], ("automotive/ecu/control", "ESTOP"))
        self.assertEqual(len(client.rx_buf), 0)

        client.disconnect()
        s_cli.close()
        s_broker.close()


class TestGatewayDaemon(unittest.TestCase):
    """Test GatewayDaemon frame parsing, CRC verification, DB storage, and TCP broadcasting."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_daemon.db")
        self.daemon = GatewayDaemon(
            dev_path="/dev/null",
            db_path=self.db_path,
            mqtt_host="127.0.0.1",
            mqtt_port=1883,
        )
        self.daemon.mqtt.connected = False  # Keep disconnected by default

    def tearDown(self):
        self.daemon.db.close()
        self.temp_dir.cleanup()

    def test_parse_valid_telemetry_frame(self):
        """Valid $TELEM frame updates telemetry, inserts into DB, and broadcasts to TCP clients."""
        payload = "$TELEM,MODE=PID,TGT=10.0,RPM=9.8,DUTY=75.5,CNT=500,PIR=1,VIB=820,TMP=265,HUM=410,FLT=0,DHT=3/0"
        crc = crc16_ccitt(payload.encode("ascii"))
        valid_frame = f"{payload}*{crc:04X}"

        # Setup mock TCP client using socketpair
        s_cli, s_dash = socket.socketpair()
        self.daemon.tcp_clients.append(s_cli)

        self.daemon.parse_and_process_line(valid_frame)

        # 1. Telemetry object updated
        self.assertIsNotNone(self.daemon.latest_telemetry)
        telem = self.daemon.latest_telemetry
        self.assertEqual(telem["mode"], "PID")
        self.assertAlmostEqual(telem["tgt"], 10.0)
        self.assertAlmostEqual(telem["rpm"], 9.8)
        self.assertAlmostEqual(telem["duty"], 75.5)
        self.assertEqual(telem["cnt"], 500)
        self.assertEqual(telem["pir"], 1)
        self.assertEqual(telem["vib"], 820)
        self.assertAlmostEqual(telem["tmp"], 26.5)  # 265 / 10.0
        self.assertAlmostEqual(telem["hum"], 41.0)  # 410 / 10.0
        self.assertEqual(telem["flt"], 0)

        # 2. Inserted into SQLite DB
        recent = self.daemon.db.query_recent(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0][2], "PID")

        # 3. Broadcast to TCP client
        rx_data = s_dash.recv(1024).decode("utf-8")
        self.assertEqual(rx_data.strip(), valid_frame)

        # 4. CRC errors should remain 0
        self.assertEqual(self.daemon.crc_err_count, 0)

        s_cli.close()
        s_dash.close()

    def test_corrupted_telemetry_frame_rejected(self):
        """Corrupted $TELEM frame with invalid CRC is rejected, crc_err_count incremented, not in DB."""
        payload = "$TELEM,MODE=PID,TGT=10.0,RPM=9.8,DUTY=75.5,CNT=500,PIR=1,VIB=820,TMP=265,HUM=410,FLT=0,DHT=3/0"
        corrupted_frame = f"{payload}*FFFF"  # Invalid CRC

        s_cli, s_dash = socket.socketpair()
        self.daemon.tcp_clients.append(s_cli)

        initial_errs = self.daemon.crc_err_count
        self.daemon.parse_and_process_line(corrupted_frame)

        # 1. crc_err_count incremented
        self.assertEqual(self.daemon.crc_err_count, initial_errs + 1)

        # 2. Not stored in DB
        recent = self.daemon.db.query_recent(limit=5)
        self.assertEqual(len(recent), 0)

        # 3. Not broadcast to TCP dashboard
        s_dash.setblocking(False)
        r, _, _ = select.select([s_dash], [], [], 0.05)
        self.assertEqual(len(r), 0)

        # 4. latest_telemetry remains None
        self.assertIsNone(self.daemon.latest_telemetry)

        s_cli.close()
        s_dash.close()

    def test_malformed_frames_handled_gracefully(self):
        """Test frames without asterisk or bad hex CRC."""
        self.daemon.parse_and_process_line("")
        self.daemon.parse_and_process_line("NO_ASTERISK_FRAME")
        self.assertEqual(self.daemon.crc_err_count, 0)

        # Bad hex string for CRC
        self.daemon.parse_and_process_line("$TELEM,MODE=PID*ZZZZ")
        self.assertEqual(self.daemon.crc_err_count, 1)

    def test_parse_valid_fault_frame(self):
        """Valid $FAULT frame logs safety event into safety_events table."""
        payload = "$FAULT,REASON=CRASH_VIBRATION"
        crc = crc16_ccitt(payload.encode("ascii"))
        fault_frame = f"{payload}*{crc:04X}"

        s_cli, s_dash = socket.socketpair()
        self.daemon.tcp_clients.append(s_cli)

        self.daemon.parse_and_process_line(fault_frame)

        # 1. Logged to safety_events
        events = self.daemon.db.query_events(limit=5)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][2], "FAULT")
        self.assertEqual(events[0][3], "CRASH_VIBRATION")
        self.assertEqual(events[0][4], fault_frame)

        # 2. Broadcast to TCP client
        rx_data = s_dash.recv(1024).decode("utf-8")
        self.assertEqual(rx_data.strip(), fault_frame)

        s_cli.close()
        s_dash.close()

    def test_mqtt_telemetry_published_when_connected(self):
        self.daemon.mqtt.connected = True
        self.daemon.mqtt.publish = MagicMock()

        payload = "$TELEM,MODE=PID,TGT=10,RPM=9,DUTY=78,CNT=100,PIR=0,VIB=500,TMP=250,HUM=400,FLT=0,DHT=3/0"
        crc = crc16_ccitt(payload.encode("ascii"))
        frame = f"{payload}*{crc:04X}"

        self.daemon.parse_and_process_line(frame)

        self.daemon.mqtt.publish.assert_called_once()
        topic, raw_json = self.daemon.mqtt.publish.call_args[0]
        self.assertEqual(topic, GatewayDaemon.TOPIC_TELEMETRY)
        data = json.loads(raw_json)
        self.assertEqual(data["device_id"], DEVICE_ID)
        self.assertEqual(data["motor"]["mode"], "PID")
        self.assertEqual(data["motor"]["target_rpm"], 10.0)

    def test_mqtt_alert_published_when_connected(self):
        self.daemon.mqtt.connected = True
        self.daemon.mqtt.publish = MagicMock()

        payload = "$FAULT,REASON=EMERGENCY_STOP_BUTTON"
        crc = crc16_ccitt(payload.encode("ascii"))
        frame = f"{payload}*{crc:04X}"

        self.daemon.parse_and_process_line(frame)

        self.daemon.mqtt.publish.assert_called_once()
        topic, raw_json = self.daemon.mqtt.publish.call_args[0]
        self.assertEqual(topic, GatewayDaemon.TOPIC_ALERT)
        data = json.loads(raw_json)
        self.assertEqual(data["device_id"], DEVICE_ID)
        self.assertEqual(data["event"], "EMERGENCY_STOP")
        self.assertEqual(data["reason"], "EMERGENCY_STOP_BUTTON")

    def test_process_mqtt_commands(self):
        self.daemon.mqtt.connected = True
        self.daemon.mqtt.poll_messages = MagicMock(
            return_value=[
                (GatewayDaemon.TOPIC_CONTROL, "SPEED 20"),
                (GatewayDaemon.TOPIC_CONTROL, "ESTOP"),
                ("other/irrelevant/topic", "IGNORED"),
            ]
        )
        self.daemon.send_m4 = MagicMock()

        self.daemon.process_mqtt_commands()

        self.assertEqual(self.daemon.send_m4.call_count, 2)
        self.daemon.send_m4.assert_any_call("SPEED 20")
        self.daemon.send_m4.assert_any_call("ESTOP")


if __name__ == "__main__":
    unittest.main()
