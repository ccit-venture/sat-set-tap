"""
routes/participants.py — Endpoint manajemen peserta.

Mencakup: list peserta, import CSV, revoke UID.
"""

import csv
import io
import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from backend.config import REDIS_HOST, REDIS_PORT, REDIS_PASS
from backend.services.redis_service import r

router = APIRouter(prefix="/api", tags=["participants"])


@router.get("/register")
def api_register_list(limit: int = 200):
    """List semua UID terdaftar, diurutkan dari yang terbaru."""
    uids   = list(r.smembers("gate:registered:all"))[:limit]
    result = []
    for uid in uids:
        data = r.hgetall(f"gate:registered:{uid}")
        if data:
            data["uid"] = uid
            result.append(data)
    return sorted(result, key=lambda x: x.get("registered_at", ""), reverse=True)


@router.delete("/register/{uid}")
def api_revoke_uid(uid: str):
    """
    Hapus satu UID dari registrasi.
    Juga mendekremen counter total_entry kalau UID ini sudah pernah masuk,
    supaya stats tetap akurat (lihat redis_handler.revoke_uid untuk konteks).
    """
    uid = uid.upper()
    if len(uid) != 8 or not all(c in "0123456789ABCDEF" for c in uid):
        raise HTTPException(400, "Format UID tidak valid (8 karakter hex)")

    key = f"gate:registered:{uid}"
    if not r.hexists(key, "uid"):
        raise HTTPException(404, "UID tidak ditemukan")

    last_entry = r.hget(key, "last_entry")
    if last_entry and last_entry != "-":
        r.decr("gate:counter:total_entry")

    r.delete(key)
    r.delete(f"gate:event:{uid}")
    r.srem("gate:registered:all", uid)
    return {"status": "revoked", "uid": uid}


@router.post("/register/import")
async def api_import_uids(upload: UploadFile = File(...)):
    """
    Import massal UID dari file CSV.
    Header wajib: uid, name, token_max (token_max boleh kosong — pakai TOKEN_DEFAULT).
    """
    if not upload.filename or not upload.filename.endswith(".csv"):
        raise HTTPException(400, "Hanya file .csv yang didukung")

    content = await upload.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    rows   = list(reader)
    if not rows:
        raise HTTPException(400, "File CSV kosong atau header tidak ditemukan")
    if "uid" not in rows[0]:
        raise HTTPException(400, "Kolom 'uid' wajib ada di header CSV")

    # Import pakai GateRedis supaya token, last_entry, dll. di-set konsisten
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../receiver"))
    from redis_handler import GateRedis
    db     = GateRedis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS)
    result = db.import_uids(rows)
    result["filename"] = upload.filename
    return result


@router.get("/log/export")
def api_log_export():
    """Export event log ke CSV, siap download."""
    import json
    entries = [json.loads(e) for e in r.lrange("gate:log", 0, -1)]
    output  = io.StringIO()
    writer  = csv.writer(output)
    writer.writerow([
        "timestamp", "gate_id", "ktp_uid", "status",
        "name", "token_left", "token_max", "crc_valid", "rssi",
    ])
    for e in reversed(entries):
        writer.writerow([
            e.get("server_timestamp") or e.get("timestamp", ""),
            e.get("gate_id",    ""),
            e.get("ktp_uid",    ""),
            e.get("status",     ""),
            e.get("name",       ""),
            e.get("token_left", ""),
            e.get("token_max",  ""),
            e.get("crc_valid",  ""),
            e.get("rssi",       ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gate_log.csv"},
    )

@router.post("/register/{uid}/checkin")
def api_manual_checkin(uid: str, body: dict):
    """
    Manual Check-In oleh panitia dari Data View.
    Mencatat gate_id dan alasan di log supaya bisa diaudit.
    """
    uid      = uid.upper()
    gate_id  = int(body.get("gate_id", 0))
    reason   = str(body.get("reason", "manual check-in"))[:100]
    now      = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    key = f"gate:registered:{uid}"
    if not r.hexists(key, "uid"):
        raise HTTPException(404, "UID tidak ditemukan")

    data       = r.hgetall(key)
    token_left = int(data.get("token_left", 0))
    token_max  = int(data.get("token_max",  3))

    if token_left <= 0:
        raise HTTPException(400, "Token peserta sudah habis")

    new_token = token_left - 1
    is_first  = data.get("last_entry", "-") == "-"

    # Update registrasi
    r.hset(key, "last_entry",  now)
    r.hset(key, "token_left",  new_token)

    # Update counter O(1)
    if is_first:
        r.incr("gate:counter:total_entry")

    # Tulis ke gate:log dengan flag manual
    log_entry = {
        "server_timestamp": now,
        "gate_id":          gate_id,
        "ktp_uid":          uid,
        "status":           "allowed",
        "name":             data.get("name", ""),
        "token_left":       new_token,
        "token_max":        token_max,
        "crc_valid":        True,
        "manual":           True,
        "manual_reason":    reason,
        "rssi":             0,
    }
    r.lpush("gate:log", json.dumps(log_entry))

    # Update stats gate
    r.hincrby(f"gate:stats:{gate_id}", "total_tap", 1)
    r.hset(f"gate:stats:{gate_id}", "last_seen", now)

    return {
        "status":     "allowed",
        "uid":        uid,
        "name":       data.get("name", ""),
        "gate_id":    gate_id,
        "token_left": new_token,
        "token_max":  token_max,
        "reason":     reason,
        "manual":     True,
    }
