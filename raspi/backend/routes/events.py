"""
routes/events.py — Endpoint kontrol event: flush, lockdown, unlock gate.

Lockdown disimpan di DUA tempat supaya konsisten:
- gate:status:{id}         → dibaca dashboard untuk tampilan
- gate:lockdown:active     → dibaca AnomalyDetector dan receiver (_poll_lockdown)
- gate:lockdown:{id}       → detail lockdown (reason, locked_at)
"""

from fastapi import APIRouter
from backend.services.redis_service import r
import time

router = APIRouter(prefix="/api", tags=["events"])


@router.delete("/flush")
def api_flush():
    """Hapus semua data — registrasi + event log."""
    keys = list(r.scan_iter("gate:*"))
    if keys:
        r.delete(*keys)
    return {"status": "flushed", "deleted": len(keys)}


@router.delete("/flush-event")
def api_flush_event():
    """Flush event log saja, data registrasi peserta tetap."""
    for key in ["gate:log", "gate:uid:seen"]:
        r.delete(key)
    for key in list(r.scan_iter("gate:stats:*")) + list(r.scan_iter("gate:event:*")):
        r.delete(key)
    r.delete("gate:counter:total_entry")
    for uid in r.smembers("gate:registered:all"):
        r.hset(f"gate:registered:{uid}", "last_entry", "-")
    return {"status": "event flushed"}


@router.post("/lockdown/{gate_id}")
def api_lockdown(gate_id: int):
    """Kunci gate secara remote. Gate_id 0 = semua gate."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    def _lock(gid: int):
        r.set(f"gate:status:{gid}", "locked")
        r.hset(f"gate:lockdown:{gid}", mapping={
            "gate_id":   gid,
            "reason":    "MANUAL",
            "locked_at": now,
        })
        r.sadd("gate:lockdown:active", str(gid))

    if gate_id == 0:
        for key in r.scan_iter("gate:stats:*"):
            gid = int(key.split(":")[-1])
            _lock(gid)
        return {"status": "all locked"}

    _lock(gate_id)
    return {"status": "locked", "gate_id": gate_id}

@router.post("/unlock/{gate_id}")
def api_unlock(gate_id: int):
    """Buka kunci gate. Gate_id 0 = semua gate."""

    def _unlock(gid: int):
        r.set(f"gate:status:{gid}", "open")
        r.delete(f"gate:lockdown:{gid}")
        r.srem("gate:lockdown:active", str(gid))

    if gate_id == 0:
        # Unlock semua yang ada di active set
        locked = list(r.smembers("gate:lockdown:active"))
        for gid in locked:
            _unlock(int(gid))
        # Cleanup gate:status juga
        for key in r.scan_iter("gate:status:*"):
            r.set(key, "open")
        r.delete("gate:lockdown:active")
        return {"status": "all unlocked"}

    _unlock(gate_id)
    return {"status": "unlocked", "gate_id": gate_id}


@router.get("/gate-status")
def api_gate_status():
    """
    Status semua gate — gabungan dari gate:status:* dan gate:lockdown:active
    supaya konsisten antara Ops View dan Data View.
    """
    result = {}

    # Dari gate:status:*
    for key in r.scan_iter("gate:status:*"):
        gid = key.split(":")[-1]
        result[f"gate_{gid}"] = r.get(key) or "open"

    # Override dengan gate:lockdown:active (sumber kebenaran anomaly detector)
    for gid in r.smembers("gate:lockdown:active"):
        result[f"gate_{gid}"] = "locked"

    return result
