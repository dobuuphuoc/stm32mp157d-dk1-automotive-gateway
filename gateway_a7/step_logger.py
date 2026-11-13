#!/usr/bin/env python3
"""
step_logger.py - Automotive Gateway Open-Loop Step Response Logger & Analyzer
Part of Automotive Domain Gateway & Real-Time Motor Controller Project (Week 5)

Collects 10ms high-resolution telemetry from Cortex-M4 via /dev/ttyRPMSG0
during MOTOR_MODE_STEP_TEST for MATLAB System Identification.
"""

import os
import sys
import time
import select
import termios
import argparse
import csv
import re

DEFAULT_DEV = '/dev/ttyRPMSG0'

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

def configure_port(dev_path):
    if not os.path.exists(dev_path):
        raise FileNotFoundError(f"Device {dev_path} not found! Is remoteproc running?")
    fd = os.open(dev_path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0  # iflag
        attrs[1] = 0  # oflag
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | termios.B115200
        attrs[3] = 0  # lflag
        attrs[4] = termios.B115200  # ispeed
        attrs[5] = termios.B115200  # ospeed
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception as e:
        print(f"[WARN] termios config on {dev_path}: {e}")
    return fd

def flush_rx(fd, duration=0.3):
    end = time.time() + duration
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                os.read(fd, 4096)
            except BlockingIOError:
                pass

def send_command(fd, cmd_str):
    line = cmd_str.strip() + '\r\n'
    os.write(fd, line.encode('ascii'))
    time.sleep(0.05)

def parse_telemetry_line(line):
    line = line.strip()
    if not line.startswith('$TELEM,') or '*' not in line:
        return None
    
    parts = line.split('*')
    if len(parts) != 2:
        return None
    
    payload, crc_str = parts[0], parts[1]
    try:
        expected_crc = int(crc_str, 16)
    except ValueError:
        return None
    
    calc_crc = crc16_ccitt(payload.encode('ascii'))
    if calc_crc != expected_crc:
        return None
    
    fields = {}
    tokens = payload[7:].split(',')
    for t in tokens:
        if '=' in t:
            k, v = t.split('=', 1)
            fields[k] = v
            
    try:
        mode = fields.get('MODE', 'UNKNOWN')
        tgt  = float(fields.get('TGT', 0))
        rpm  = float(fields.get('RPM', 0))
        duty = float(fields.get('DUTY', 0))
        cnt  = int(fields.get('CNT', 0))
        return {
            'mode': mode,
            'target': tgt,
            'rpm': rpm,
            'duty': duty,
            'count': cnt
        }
    except ValueError:
        return None

def run_single_step_test(fd, base_duty, step_duty, dur_ms, pre_step_ms=1000):
    total_expected_ms = pre_step_ms + dur_ms + 1000
    timeout_s = (total_expected_ms / 1000.0) + 2.0
    
    print(f"\n[STEP_TEST] Starting: Base={base_duty}%, Step={step_duty}%, Dur={dur_ms}ms, Pre={pre_step_ms}ms")
    flush_rx(fd, 0.4)
    
    cmd = f"STEP {base_duty} {step_duty} {dur_ms}"
    send_command(fd, cmd)
    
    records = []
    t_start = None
    step_finished = False
    deadline = time.time() + timeout_s
    buf = ""
    
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                chunk = os.read(fd, 2048).decode('ascii', errors='ignore')
            except BlockingIOError:
                continue
            
            buf += chunk
            while '\n' in buf:
                line, buf = buf.split('\n', 1)
                parsed = parse_telemetry_line(line)
                if parsed:
                    now = time.time()
                    if t_start is None:
                        t_start = now
                    
                    rel_time_s = round(now - t_start, 4)
                    parsed['time_s'] = rel_time_s
                    records.append(parsed)
                    
                    if len(records) > 10 and parsed['mode'] == 'STOP':
                        step_finished = True
                        break
            if step_finished:
                break
                
    print(f"[STEP_TEST] Completed. Captured {len(records)} samples in {rel_time_s:.2f}s.")
    return records

def analyze_step_data(records, base_duty, step_duty):
    if not records:
        return {}
    
    step_samples = [r for r in records if abs(r['duty'] - step_duty) < 2.0]
    if not step_samples:
        step_samples = records[int(len(records)*0.3):]
    
    last_samples = step_samples[-max(10, int(len(step_samples)*0.3)):]
    steady_state_rpm = sum(r['rpm'] for r in last_samples) / len(last_samples)
    base_rpm = records[0]['rpm'] if records else 0.0
    
    delta_rpm = steady_state_rpm - base_rpm
    delta_duty = step_duty - base_duty
    static_gain_k = (delta_rpm / delta_duty) if abs(delta_duty) > 0.1 else 0.0
    
    rpm_10 = base_rpm + 0.10 * delta_rpm
    rpm_90 = base_rpm + 0.90 * delta_rpm
    
    t_10 = None
    t_90 = None
    for r in step_samples:
        if t_10 is None and r['rpm'] >= rpm_10:
            t_10 = r['time_s']
        if t_90 is None and r['rpm'] >= rpm_90:
            t_90 = r['time_s']
            
    rise_time_s = (t_90 - t_10) if (t_10 is not None and t_90 is not None) else None
    
    return {
        'base_duty': base_duty,
        'step_duty': step_duty,
        'steady_state_rpm': round(steady_state_rpm, 2),
        'static_gain_k': round(static_gain_k, 3),
        'rise_time_s': round(rise_time_s, 3) if rise_time_s else "N/A",
        'sample_count': len(records)
    }

def save_csv(records, filename):
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['time_s', 'duty_pct', 'rpm', 'pulse_cnt', 'mode', 'target_rpm'])
        for r in records:
            writer.writerow([r['time_s'], r['duty'], r['rpm'], r['count'], r['mode'], r['target']])
    print(f"[CSV] Saved {len(records)} rows to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Automotive Gateway Open-Loop Step Response Logger")
    parser.add_argument('--dev', default=DEFAULT_DEV, help="RPMsg TTY device (default: /dev/ttyRPMSG0)")
    parser.add_argument('--step', type=float, default=60.0, help="Step duty percent (default: 60.0)")
    parser.add_argument('--base', type=float, default=0.0, help="Base duty percent (default: 0.0)")
    parser.add_argument('--dur', type=int, default=3000, help="Step duration in ms (default: 3000)")
    parser.add_argument('--pre', type=int, default=1000, help="Pre-step duration in ms (default: 1000)")
    parser.add_argument('--out', default='gateway_a7/data/step_response.csv', help="Output CSV path")
    parser.add_argument('--all', action='store_true', help="Run automated 3-step suite (40%, 60%, 80%)")
    args = parser.parse_args()

    print("==================================================================")
    print("  Automotive Gateway - Open-Loop Step Response Acquisition Tool   ")
    print(f"  Target Device: {args.dev}")
    print("==================================================================")

    fd = configure_port(args.dev)
    
    try:
        if args.all:
            duty_levels = [40.0, 60.0, 80.0]
            summary_table = []
            combined_records = []
            t_offset = 0.0
            
            for d in duty_levels:
                csv_path = f"gateway_a7/data/step_response_{int(d)}.csv"
                recs = run_single_step_test(fd, base_duty=0.0, step_duty=d, dur_ms=args.dur, pre_step_ms=args.pre)
                save_csv(recs, csv_path)
                stats = analyze_step_data(recs, base_duty=0.0, step_duty=d)
                summary_table.append(stats)
                
                for r in recs:
                    r_comb = dict(r)
                    r_comb['time_s'] += t_offset
                    combined_records.append(r_comb)
                if recs:
                    t_offset = combined_records[-1]['time_s'] + 1.0
                
                print(f"[COOLDOWN] Letting motor settle for 2.0s before next step...")
                time.sleep(2.0)
                
            save_csv(combined_records, "gateway_a7/data/step_response_combined.csv")
            
            print("\n==================================================================")
            print("  WEEK 5 STEP TEST RESULTS SUMMARY (MATLAB SysID Ready)           ")
            print("==================================================================")
            print(f"{'Step Duty':<12} | {'Steady RPM':<14} | {'Gain K (RPM/%)':<16} | {'Rise Time tr':<12} | {'Samples':<8}")
            print("-" * 70)
            for s in summary_table:
                print(f"{s['step_duty']:<5}%      | {s['steady_state_rpm']:<14} | {s['static_gain_k']:<16} | {str(s['rise_time_s']):<12} | {s['sample_count']:<8}")
            print("==================================================================")
        else:
            recs = run_single_step_test(fd, base_duty=args.base, step_duty=args.step, dur_ms=args.dur, pre_step_ms=args.pre)
            save_csv(recs, args.out)
            stats = analyze_step_data(recs, args.base, args.step)
            print(f"\n[ANALYSIS] Steady-State Speed: {stats.get('steady_state_rpm')} RPM")
            print(f"[ANALYSIS] Static Gain K:      {stats.get('static_gain_k')} RPM/%")
            print(f"[ANALYSIS] Rise Time (10-90%): {stats.get('rise_time_s')} s")
    finally:
        send_command(fd, "STOP")
        os.close(fd)
        print("[EXIT] Safety stop issued. Port closed.")

if __name__ == '__main__':
    main()
