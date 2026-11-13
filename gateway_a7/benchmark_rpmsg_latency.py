#!/usr/bin/env python3
"""
=============================================================================
 benchmark_rpmsg_latency.py - Round-Trip Latency Benchmark (NFR-3)
=============================================================================
 Measures round-trip latency between Cortex-A7 (Linux) and Cortex-M4 (Zephyr)
 over the OpenAMP RPMsg IPC channel (/dev/ttyRPMSG0).
 
 Metric measured:
   t_rtt = t_reply_received - t_cmd_sent (Round-Trip Time)
=============================================================================
"""

import os
import sys
import time
import termios

DEFAULT_DEV = "/dev/ttyRPMSG0"
SAMPLES = 100

def set_raw_mode(fd):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0 # iflag
    attrs[1] = 0 # oflag
    attrs[2] &= ~termios.CSIZE
    attrs[2] |= termios.CS8 # cflag
    attrs[3] = 0 # lflag (no echo, no icanon)
    attrs[4] = termios.B115200 # ispeed
    attrs[5] = termios.B115200 # ospeed
    attrs[6][termios.VMIN] = 1
    attrs[6][termios.VTIME] = 1 # 100ms timeout
    termios.tcsetattr(fd, termios.TCSANOW, attrs)

def main():
    dev_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEV
    count = int(sys.argv[2]) if len(sys.argv) > 2 else SAMPLES

    if not os.path.exists(dev_path):
        print(f"[Error] RPMsg device '{dev_path}' not found!")
        sys.exit(1)

    print("=============================================================")
    print(" STM32MP157 OpenAMP RPMsg Round-Trip Latency Benchmark (NFR-3)")
    print(f" Target Device: {dev_path} | Iterations: {count}")
    print("=============================================================")

    try:
        fd = os.open(dev_path, os.O_RDWR | os.O_NOCTTY)
    except Exception as e:
        print(f"[Error] Failed to open {dev_path}: {e}")
        sys.exit(1)

    try:
        set_raw_mode(fd)
    except Exception as e:
        print(f"[Warning] Failed to set termios raw mode: {e}")

    # Warmup ping
    print("--> Warming up RPMsg endpoint...")
    for _ in range(5):
        os.write(fd, b"STATUS\n")
        time.sleep(0.05)
        # Flush any incoming bytes
        try:
            while True:
                r = os.read(fd, 256)
                if len(r) < 256:
                    break
        except Exception:
            pass

    latencies_ms = []
    print(f"--> Measuring {count} round-trip requests (Command: STATUS)...")

    for i in range(count):
        t0 = time.perf_counter()
        os.write(fd, b"STATUS\n")

        # Read until newline
        buf = bytearray()
        timeout = False
        while True:
            try:
                ch = os.read(fd, 1)
                if not ch:
                    if time.perf_counter() - t0 > 0.5:
                        timeout = True
                        break
                    continue
                buf.extend(ch)
                if ch == b"\n":
                    break
            except Exception:
                if time.perf_counter() - t0 > 0.5:
                    timeout = True
                    break

        t1 = time.perf_counter()
        if not timeout and len(buf) > 0:
            rtt = (t1 - t0) * 1000.0
            latencies_ms.append(rtt)
        else:
            print(f"  [Iter {i+1}] Timeout waiting for reply")

        time.sleep(0.01) # 10ms pacing between requests

    os.close(fd)

    if not latencies_ms:
        print("[Error] No successful responses received from Cortex-M4.")
        sys.exit(1)

    # Statistics
    avg_rtt = sum(latencies_ms) / len(latencies_ms)
    min_rtt = min(latencies_ms)
    max_rtt = max(latencies_ms)
    variance = sum((x - avg_rtt) ** 2 for x in latencies_ms) / len(latencies_ms)
    stddev = variance ** 0.5

    print("\n=============================================================")
    print(" BENCHMARK RESULTS (OpenAMP RPMsg IPC Round-Trip Latency)")
    print("=============================================================")
    print(f" Total Samples Transmitted:   {count}")
    print(f" Valid Replies Received:      {len(latencies_ms)} ({len(latencies_ms)/count*100:.1f}%)")
    print(f" Average Latency (t_avg):     {avg_rtt:.3f} ms")
    print(f" Minimum Latency (t_min):     {min_rtt:.3f} ms")
    print(f" Maximum Latency (t_max):     {max_rtt:.3f} ms")
    print(f" Standard Deviation (sigma):  {stddev:.3f} ms")
    print("-------------------------------------------------------------")
    if avg_rtt < 5.0:
        print(" Assessment: EXCELLENT (t_avg < 5.0 ms, High Determinism)")
    elif avg_rtt < 10.0:
        print(" Assessment: GOOD (t_avg < 10.0 ms, Suitable for Telematics)")
    else:
        print(" Assessment: ACCEPTABLE (t_avg >= 10.0 ms)")
    print("=============================================================")

if __name__ == "__main__":
    main()
