"""
services/gate_service.py — Logic untuk stats, analytics, network, load balance.

Semua fungsi get_*_data() yang dulu ada di dashboard.py dipindah ke sini.
Route handler di routes/ cukup panggil fungsi dari sini — tidak ada
logic di dalam route handler.

Kenapa dipisah:
- Bisa di-test tanpa perlu jalankan HTTP server.
- Route handler jadi pendek dan mudah dibaca.
- Kalau perlu ganti sumber data (misal dari Redis ke DB lain),
  cukup ubah di sini, route tidak perlu disentuh.
"""

import json
import time
from datetime import datetime
from collections import defaultdict

from backend.services.redis_service import r


def get_stats() -> dict:
    """
    Statistik utama: total peserta terdaftar, sudah masuk, total tap,
    status per gate, dan jumlah gate online.

    total_entry pakai counter O(1) gate:counter:total_entry —
    tidak loop semua UID terdaftar (lihat redis_handler.py untuk
    penjelasan kenapa ini penting untuk performa saat peserta ribuan).
    """
    total_reg   = r.scard("gate:registered:all") or 0
    total_entry = int(r.get("gate:counter:total_entry") or 0)
    gate_stats  = {}
    now         = datetime.now()
    HB_TIMEOUT  = 45  # detik — 3× interval heartbeat 15 detik

    for key in r.scan_iter("gate:stats:*"):
        gid  = key.split(":")[-1]
        data = r.hgetall(key)
        gate_stats[f"gate_{gid}"] = {
            "total_tap": int(data.get("total_tap", 0)),
            "last_seen": data.get("last_seen", "-"),
        }

    for hb_key in r.scan_iter("gate:heartbeat:*"):
        gid       = hb_key.split(":")[-1]
        hb_data   = r.hgetall(hb_key)
        gate_name = f"gate_{gid}"
        if gate_name not in gate_stats:
            gate_stats[gate_name] = {"total_tap": 0, "last_seen": "-"}
        last_hb = hb_data.get("last_heartbeat", "")
        online  = False
        if last_hb:
            try:
                hb_time = datetime.strptime(last_hb, "%Y-%m-%dT%H:%M:%S")
                online  = (now - hb_time).total_seconds() < HB_TIMEOUT
            except Exception:
                pass
        gate_stats[gate_name]["online"] = online

    locked_gates = r.smembers("gate:lockdown:active")
    for gate_name, info in gate_stats.items():
        gid = gate_name.replace("gate_", "")
        info["locked"] = gid in locked_gates

    online_count = sum(1 for g in gate_stats.values() if g.get("online"))
    return {
        "total_registered":     total_reg,
        "total_entry":          total_entry,
        "total_unique_entries": total_entry,
        "total_tap":            sum(g["total_tap"] for g in gate_stats.values()),
        "gates":                gate_stats,
        "online_gates":         online_count,
        "timestamp":            time.strftime("%H:%M:%S"),
    }


def get_analytics() -> dict:
    """
    Data untuk chart tap per menit, per gate.
    Ambil 1000 entri terakhir dari gate:log dan kelompokkan per menit.
    """
    entries  = r.lrange("gate:log", 0, 999)
    per_all  = defaultdict(lambda: {"allowed": 0, "denied": 0})
    per_gate = defaultdict(lambda: defaultdict(lambda: {"allowed": 0, "denied": 0}))

    for raw in entries:
        try:
            e      = json.loads(raw)
            ts     = e.get("server_timestamp") or e.get("timestamp", "")
            if not ts or "T" not in ts:
                continue
            minute  = ts[:16].replace("T", " ")
            status  = e.get("status", "")
            gate_id = str(e.get("gate_id", "all"))
            key     = "allowed" if status == "allowed" else "denied"
            per_all[minute][key]           += 1
            per_gate[gate_id][minute][key] += 1
        except Exception:
            continue

    sorted_minutes = sorted(per_all.keys())[-30:]
    gates_data = {}
    for gid, minutes in per_gate.items():
        gates_data[f"gate_{gid}"] = {
            "allowed": [minutes.get(m, {}).get("allowed", 0) for m in sorted_minutes],
            "denied":  [minutes.get(m, {}).get("denied",  0) for m in sorted_minutes],
        }

    return {
        "labels":      sorted_minutes,
        "all_allowed": [per_all[m]["allowed"] for m in sorted_minutes],
        "all_denied":  [per_all[m]["denied"]  for m in sorted_minutes],
        "gates":       gates_data,
    }


def get_load_balance() -> dict:
    """
    Deteksi ketidakseimbangan beban antar gate.
    Kalau gate paling ramai > 40% lebih sibuk dari gate paling sepi,
    return suggestion untuk redirect peserta.
    """
    gate_stats = {}
    for key in r.scan_iter("gate:stats:*"):
        gid = key.split(":")[-1]
        data = r.hgetall(key)
        gate_stats[gid] = int(data.get("total_tap", 0))

    if not gate_stats:
        return {"status": "no_data", "suggestion": None, "gates": {}}

    total    = sum(gate_stats.values()) or 1
    busiest  = max(gate_stats, key=gate_stats.get)
    quietest = min(gate_stats, key=gate_stats.get)
    busy_pct = (gate_stats[busiest]  / total) * 100
    quiet_pct= (gate_stats[quietest] / total) * 100

    suggestion = None
    if len(gate_stats) > 1 and (busy_pct - quiet_pct) > 40:
        suggestion = {
            "from_gate": busiest,
            "to_gate":   quietest,
            "message":   (
                f"Gate {busiest} terlalu ramai ({gate_stats[busiest]} tap). "
                f"Arahkan ke Gate {quietest} ({gate_stats[quietest]} tap)."
            ),
            "severity": "high" if (busy_pct - quiet_pct) > 60 else "medium",
        }

    return {
        "status":   "ok",
        "suggestion": suggestion,
        "gates":    gate_stats,
        "busiest":  busiest,
        "quietest": quietest,
    }


def get_network() -> dict:
    """
    Latency dan RSSI per gate dari Redis.
    Latency dari gate:latency:{gid} (list integer ms).
    RSSI dari 200 entri terakhir gate:log.
    """
    gate_ids = set()
    for key in r.scan_iter("gate:latency:*"):
        gate_ids.add(int(key.split(":")[-1]))

    result = {}
    for gid in sorted(gate_ids):
        latencies = r.lrange(f"gate:latency:{gid}", 0, -1)
        nums = [int(x) for x in latencies]

        rssi_values = []
        for raw in r.lrange("gate:log", 0, 199):
            try:
                e = json.loads(raw)
                if e.get("gate_id") == gid and "rssi" in e and e["rssi"] != 0:
                    rssi_values.append(e["rssi"])
            except Exception:
                pass
        rssi_values = rssi_values[-20:]

        result[f"gate_{gid}"] = {
            "latency": {
                "current": nums[-1]  if nums else 0,
                "min":     min(nums) if nums else 0,
                "max":     max(nums) if nums else 0,
                "avg":     round(sum(nums) / len(nums)) if nums else 0,
                "samples": len(nums),
                "history": nums[-20:],
            },
            "rssi": {
                "current": rssi_values[-1]  if rssi_values else 0,
                "avg":     round(sum(rssi_values) / len(rssi_values)) if rssi_values else 0,
                "min":     min(rssi_values) if rssi_values else 0,
                "history": rssi_values[-20:],
            },
        }
    return result
