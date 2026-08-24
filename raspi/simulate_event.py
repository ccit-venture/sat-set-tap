#!/usr/bin/env python3
"""
simulate_event.py — Simulasi event realistis untuk Sat Set Tap.

Cara kerja:
  1. Buat sepasang virtual serial port via socat (PTY)
  2. Script ini tulis ke satu ujung (master)
  3. receiver.py baca dari ujung lain (slave) — seolah-olah dari ESP32
  4. Pipeline lengkap: simulator → virtual serial → receiver → Redis → dashboard

Pipeline yang diuji:
  parse_serial_line → parse_hex_packet → CRC validation → store_tap
  → Redis → WebSocket broadcast → dashboard

Skenario default (bisa diubah via argumen):
  - 100 UID terdaftar, 3 gate
  - Phase 1 (menit 0-2):  registrasi massal semua UID
  - Phase 2 (menit 2-5):  burst masuk — 80% peserta tap dalam 3 menit
  - Phase 3 (menit 5-8):  normal flow, ada denied & tailgating sesekali
  - Phase 4 (menit 8-10): burst kedua gelombang telat, ada unknown flood

Usage:
  # 1. Jalankan socat dulu di terminal terpisah:
  socat -d -d pty,raw,echo=0 pty,raw,echo=0

  # Catat dua path PTY yang muncul, misal:
  # /dev/pts/3  (master — untuk simulator ini)
  # /dev/pts/4  (slave  — untuk receiver.py)

  # 2. Jalankan receiver dengan slave port:
  python3 receiver/receiver.py --serial /dev/pts/4 --redis-pass <pass>

  # 3. Jalankan simulator dengan master port:
  python3 simulate_event.py --port /dev/pts/3 --uids 100 --gates 3 --duration 10

  # Atau pakai --auto untuk socat otomatis (butuh socat terinstall):
  python3 simulate_event.py --auto --uids 100 --gates 3 --duration 10 --redis-pass <pass>
"""

import argparse
import os
import random
import subprocess
import sys
import time
import threading
import re

# ── Tambah path receiver supaya bisa import packet builder ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "receiver"))
from packet import build_hex_packet, Command


# ── Konstanta ────────────────────────────────────────────────
BAUDRATE      = 115200
HEARTBEAT_INTERVAL = 10   # detik antar heartbeat per gate
LOG_PREFIX    = {
    "info":  "\033[32m[SIM]\033[0m",
    "warn":  "\033[33m[SIM]\033[0m",
    "error": "\033[31m[SIM]\033[0m",
    "dim":   "\033[90m[SIM]\033[0m",
}


def log(level, msg):
    print(f"{LOG_PREFIX.get(level,'[SIM]')} {msg}", flush=True)


# ── UID generator ────────────────────────────────────────────
def gen_uids(n: int) -> list[str]:
    """Generate n UID unik 4-byte (8 char hex), format e-KTP."""
    uids = set()
    while len(uids) < n:
        uid = f"{random.randint(0x10000000, 0xFFFFFFFF):08X}"
        uids.add(uid)
    return list(uids)


def gen_unknown_uid() -> str:
    """UID yang tidak terdaftar — untuk simulasi denied_unregistered."""
    return f"{random.randint(0x10000000, 0xFFFFFFFF):08X}"


# ── Serial writer ────────────────────────────────────────────
def write_tap(ser_file, gate_id: int, uid: str, rssi: int = None):
    """Kirim satu TAP_REQUEST ke virtual serial."""
    if rssi is None:
        rssi = random.randint(-90, -55)  # RSSI realistis LoRa dalam ruangan
    hex_pkt = build_hex_packet(Command.TAP_REQUEST, gate_id, uid)
    line    = f"DATA:{hex_pkt}:{rssi}\n"
    ser_file.write(line.encode("ascii"))
    ser_file.flush()
    return hex_pkt


def write_heartbeat(ser_file, gate_id: int):
    """Kirim HEARTBEAT dari gate."""
    rssi    = random.randint(-85, -60)
    hex_pkt = build_hex_packet(Command.HEARTBEAT, gate_id, "00000000")
    line    = f"DATA:{hex_pkt}:{rssi}\n"
    ser_file.write(line.encode("ascii"))
    ser_file.flush()


def write_latency(ser_file, gate_id: int, ms: int):
    """Kirim latency report dari gate."""
    line = f"[LATENCY] gate={gate_id} ms={ms}\n"
    ser_file.write(line.encode("ascii"))
    ser_file.flush()


# ── Heartbeat thread ─────────────────────────────────────────
def heartbeat_loop(ser_file, gate_ids: list, stop_event: threading.Event):
    """Kirim heartbeat dari semua gate setiap HEARTBEAT_INTERVAL detik."""
    while not stop_event.is_set():
        for gid in gate_ids:
            if stop_event.is_set(): break
            write_heartbeat(ser_file, gid)
            log("dim", f"❤ HEARTBEAT Gate {gid}")
            time.sleep(0.1)
        stop_event.wait(HEARTBEAT_INTERVAL)


# ── Registrasi ke Redis langsung ─────────────────────────────
def register_uids(uids: list, token_max: int, redis_pass: str):
    """
    Daftarkan semua UID ke Redis sebelum simulasi dimulai.
    Ini menggantikan registration_station.py — untuk simulasi tidak perlu
    hardware Arduino, cukup tulis langsung ke Redis.
    """
    try:
        import redis
        r = redis.Redis(
            host="localhost", port=6379,
            password=redis_pass if redis_pass else None,
            decode_responses=True,
        )
        r.ping()
    except Exception as e:
        log("error", f"Tidak bisa konek Redis: {e}")
        log("error", "Pastikan receiver sudah jalan dan Redis aktif.")
        sys.exit(1)

    log("info", f"Mendaftarkan {len(uids)} UID ke Redis...")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    pipe = r.pipeline()
    for uid in uids:
        name = f"Peserta-{uid[:4]}"
        key  = f"gate:registered:{uid}"
        pipe.hset(key, mapping={
            "uid":           uid,
            "name":          name,
            "token_max":     token_max,
            "token_left":    token_max,
            "registered_at": now,
            "last_entry":    "-",
        })
        pipe.sadd("gate:registered:all", uid)
    pipe.execute()
    log("info", f"✓ {len(uids)} UID terdaftar")
    return r


# ── Skenario simulasi ────────────────────────────────────────
def run_simulation(
    ser_file,
    uids:        list,
    gate_ids:    list,
    duration:    int,
    stop_event:  threading.Event,
):
    """
    Jalankan skenario simulasi event realistis.

    Timeline (proporsi dari total durasi):
      0-20%  : Phase 1 — warmup, beberapa orang datang lebih awal
      20-60% : Phase 2 — burst utama, mayoritas peserta masuk
      60-80% : Phase 3 — normal flow, ada anomali sesekali
      80-100%: Phase 4 — gelombang akhir, ada unknown flood
    """
    n_uids  = len(uids)
    n_gates = len(gate_ids)
    start   = time.time()
    end     = start + (duration * 60)

    # Tentukan UID yang "belum pernah masuk" — untuk burst phase
    unqueued = list(uids)
    random.shuffle(unqueued)

    def elapsed():
        return time.time() - start

    def remaining():
        return end - time.time()

    def pct():
        return elapsed() / (duration * 60)

    tap_count = 0
    deny_count = 0

    log("info", f"Simulasi dimulai — {n_uids} UID, {n_gates} gate, {duration} menit")
    log("info", "─" * 50)

    # ── Phase 1: Warmup (0-20% durasi) ───────────────────────
    warmup_end = start + (duration * 60 * 0.20)
    warmup_uids = unqueued[:max(1, n_uids // 5)]
    unqueued    = unqueued[len(warmup_uids):]

    log("info", f"Phase 1: Warmup — {len(warmup_uids)} orang datang awal")
    for uid in warmup_uids:
        if time.time() > warmup_end or stop_event.is_set(): break
        gate = random.choice(gate_ids)
        write_tap(ser_file, gate, uid)
        lat  = random.randint(20, 80)
        write_latency(ser_file, gate, lat)
        tap_count += 1
        log("dim", f"  TAP uid={uid} gate={gate}")
        time.sleep(random.uniform(2.0, 5.0))  # orang datang pelan-pelan

    # ── Phase 2: Burst utama (20-60% durasi) ─────────────────
    burst_end  = start + (duration * 60 * 0.60)
    burst_uids = unqueued[:max(1, int(n_uids * 0.65))]
    unqueued   = unqueued[len(burst_uids):]

    log("warn", f"Phase 2: BURST — {len(burst_uids)} orang masuk dalam waktu singkat")
    for uid in burst_uids:
        if time.time() > burst_end or stop_event.is_set(): break
        gate = random.choice(gate_ids)
        write_tap(ser_file, gate, uid)
        lat  = random.randint(15, 45)
        write_latency(ser_file, gate, lat)
        tap_count += 1

        # Sesekali ada yang tap 2x cepat (tailgating)
        if random.random() < 0.05:
            time.sleep(random.uniform(0.3, 0.8))
            write_tap(ser_file, gate, uid, rssi=random.randint(-95, -70))
            tap_count += 1
            log("warn", f"  TAILGATING uid={uid} gate={gate}")

        time.sleep(random.uniform(0.2, 1.2))  # burst — orang datang cepat

    # ── Phase 3: Normal flow + anomali (60-80% durasi) ───────
    normal_end = start + (duration * 60 * 0.80)
    log("info", "Phase 3: Normal flow — ada denied & cross-gate sesekali")

    tapped = list(set(uids) - set(unqueued))  # yang sudah masuk
    while time.time() < normal_end and not stop_event.is_set():
        roll = random.random()

        if roll < 0.15 and tapped:
            # UID tidak terdaftar
            uid  = gen_unknown_uid()
            gate = random.choice(gate_ids)
            write_tap(ser_file, gate, uid, rssi=random.randint(-105, -85))
            deny_count += 1
            log("dim", f"  UNKNOWN uid={uid} gate={gate}")

        elif roll < 0.25 and len(tapped) >= 2 and n_gates > 1:
            # Rapid cross-gate — UID sama tap dua gate berbeda cepat
            uid    = random.choice(tapped)
            gate_a = random.choice(gate_ids)
            gate_b = random.choice([g for g in gate_ids if g != gate_a])
            write_tap(ser_file, gate_a, uid)
            time.sleep(random.uniform(0.5, 2.0))
            write_tap(ser_file, gate_b, uid)
            tap_count += 2
            log("warn", f"  CROSS-GATE uid={uid} {gate_a}→{gate_b}")

        elif unqueued:
            # Orang yang belum masuk akhirnya datang
            uid  = unqueued.pop(0)
            gate = random.choice(gate_ids)
            write_tap(ser_file, gate, uid)
            lat  = random.randint(25, 100)
            write_latency(ser_file, gate, lat)
            tap_count += 1
            tapped.append(uid)

        time.sleep(random.uniform(1.0, 3.0))

    # ── Phase 4: Unknown flood + gelombang akhir (80-100%) ───
    log("warn", "Phase 4: Gelombang akhir + unknown flood")
    flood_gate = random.choice(gate_ids)
    log("warn", f"  Unknown flood di Gate {flood_gate}")

    # Kirim 5 UID tidak terdaftar cepat-cepat → trigger UNKNOWN_FLOOD
    for _ in range(6):
        if stop_event.is_set(): break
        uid = gen_unknown_uid()
        write_tap(ser_file, flood_gate, uid, rssi=random.randint(-110, -90))
        deny_count += 1
        time.sleep(0.4)

    # Sisa unqueued yang belum masuk
    while unqueued and time.time() < end and not stop_event.is_set():
        uid  = unqueued.pop(0)
        gate = random.choice(gate_ids)
        write_tap(ser_file, gate, uid)
        tap_count += 1
        time.sleep(random.uniform(0.5, 2.0))

    # ── Selesai ───────────────────────────────────────────────
    elapsed_min = elapsed() / 60
    log("info", "─" * 50)
    log("info", f"Simulasi selesai dalam {elapsed_min:.1f} menit")
    log("info", f"Total tap terkirim : {tap_count}")
    log("info", f"Total denied       : {deny_count}")
    log("info", f"UID berhasil masuk : {n_uids - len(unqueued)}/{n_uids}")


# ── Auto socat ───────────────────────────────────────────────
def start_socat():
    """
    Jalankan socat dan parse dua PTY path yang dibuat.
    Return (master_path, slave_path, process).
    """
    proc = subprocess.Popen(
        ["socat", "-d", "-d", "pty,raw,echo=0", "pty,raw,echo=0"],
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
    )
    ptys = []
    log("info", "Menunggu socat membuat virtual serial ports...")
    while len(ptys) < 2:
        line = proc.stderr.readline().decode("utf-8", errors="ignore")
        match = re.search(r"(/dev/pts/\d+|/dev/pty\w+)", line)
        if match:
            ptys.append(match.group(1))
        if proc.poll() is not None:
            log("error", "socat gagal dijalankan.")
            sys.exit(1)
    time.sleep(0.5)  # tunggu port siap
    log("info", f"Virtual serial: master={ptys[0]}  slave={ptys[1]}")
    return ptys[0], ptys[1], proc


# ── Main ─────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Sat Set Tap — Event Simulator")
    ap.add_argument("--port",       default=None,   help="Master PTY path (jika socat manual)")
    ap.add_argument("--auto",       action="store_true", help="Jalankan socat otomatis")
    ap.add_argument("--uids",       type=int, default=100,  help="Jumlah peserta (default: 100)")
    ap.add_argument("--gates",      type=int, default=2,    help="Jumlah gate (default: 2)")
    ap.add_argument("--duration",   type=int, default=10,   help="Durasi simulasi dalam menit (default: 10)")
    ap.add_argument("--token-max",  type=int, default=3,    help="Token per peserta (default: 3)")
    ap.add_argument("--redis-pass", default="",      help="Password Redis")
    ap.add_argument("--slave-port", default=None,    help="Slave PTY untuk receiver (hanya info, tidak dipakai simulator)")
    args = ap.parse_args()

    socat_proc = None

    # ── Setup virtual serial ──────────────────────────────────
    if args.auto:
        master_port, slave_port, socat_proc = start_socat()
        log("info", f"\nJalankan receiver di terminal lain:")
        log("info", f"  python3 receiver/receiver.py --serial {slave_port} --redis-pass {args.redis_pass or '<pass>'}\n")
        log("info", "Tekan Enter setelah receiver siap...")
        input()
    elif args.port:
        master_port = args.port
    else:
        log("error", "Gunakan --auto atau --port <master_pty>")
        log("error", "Contoh: python3 simulate_event.py --auto --uids 100 --gates 2 --duration 10")
        sys.exit(1)

    # ── Generate & register UID ───────────────────────────────
    gate_ids = list(range(1, args.gates + 1))
    uids     = gen_uids(args.uids)
    register_uids(uids, args.token_max, args.redis_pass)

    # ── Buka serial port ──────────────────────────────────────
    try:
        ser_file = open(master_port, "wb", buffering=0)
    except Exception as e:
        log("error", f"Gagal buka {master_port}: {e}")
        sys.exit(1)

    log("info", f"Serial OK: {master_port}")
    time.sleep(1)  # tunggu receiver siap baca

    # ── Start heartbeat thread ────────────────────────────────
    stop_event = threading.Event()
    hb_thread  = threading.Thread(
        target=heartbeat_loop,
        args=(ser_file, gate_ids, stop_event),
        daemon=True,
    )
    hb_thread.start()
    log("info", f"Heartbeat thread started untuk gate {gate_ids}")

    # ── Run simulasi ──────────────────────────────────────────
    try:
        run_simulation(ser_file, uids, gate_ids, args.duration, stop_event)
    except KeyboardInterrupt:
        log("warn", "Simulasi dihentikan manual.")
    finally:
        stop_event.set()
        ser_file.close()
        if socat_proc:
            socat_proc.terminate()
            log("info", "socat dihentikan.")

    log("info", "Done. Cek dashboard untuk hasil simulasi.")


if __name__ == "__main__":
    main()
