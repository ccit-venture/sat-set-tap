"""
routes/anomaly.py — Endpoint query dan kontrol anomali.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../receiver"))
from anomaly import AnomalyDetector

from fastapi import APIRouter, HTTPException
from backend.services.redis_service import r

router   = APIRouter(prefix="/api/anomaly", tags=["anomaly"])
detector = AnomalyDetector(r)


@router.get("")
def api_anomaly_list():
    """Semua anomali aktif (belum resolve)."""
    return detector.get_active()


@router.get("/summary")
def api_anomaly_summary():
    """Ringkasan anomali: jumlah HIGH, MEDIUM, gate terkunci."""
    return detector.get_summary()


@router.delete("/{anomaly_id}")
def api_anomaly_resolve(anomaly_id: str):
    """
    Tandai anomali sebagai resolved (dismiss manual dari dashboard).
    Tidak otomatis unlock gate — gunakan /api/unlock/{gate_id} untuk itu.
    """
    key = f"gate:anomaly:{anomaly_id}"
    if not r.exists(key):
        raise HTTPException(404, "Anomali tidak ditemukan")
    r.hset(key, "status", "resolved")
    return {"status": "resolved", "id": anomaly_id}
