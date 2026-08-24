"""
routes/websocket.py — WebSocket endpoint dan background broadcast task.

Arsitektur:
- Client browser connect ke /ws
- Background task (broadcast_loop) jalan setiap 1 detik,
  kirim snapshot stats + anomali + network ke semua client
- Kalau ada tap baru (via Redis Pub/Sub di receiver.py),
  receiver langsung publish — dashboard langsung update tanpa polling

Kenapa WebSocket dan bukan polling dari browser:
- Latency lebih rendah (server push, bukan client pull)
- Lebih efisien — hanya kirim data saat ada perubahan (jika pakai pubsub)
  atau minimal 1x/detik (saat pakai polling loop seperti sekarang)
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services import gate_service
from backend.services.redis_service import r
from backend.services.websocket_manager import manager

# Import AnomalyDetector dari lokasi lama (raspi/anomaly.py)
# yang sudah kita fix agar state-nya di Redis
import sys, os
_BASE = os.path.join(os.path.dirname(__file__), "../..")
sys.path.insert(0, os.path.join(_BASE, "receiver"))  # anomaly.py
sys.path.insert(0, _BASE)  # predictor.py
from anomaly import AnomalyDetector
from predictor import DensityPredictor

detector  = AnomalyDetector(r)
predictor = DensityPredictor(r)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Tetap terima pesan dari client (untuk future: kirim command dari browser)
            await asyncio.wait_for(ws.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        manager.disconnect(ws)


async def broadcast_loop():
    """
    Background task: broadcast snapshot ke semua client setiap 1 detik.

    Mengirim satu payload gabungan (stats + anomali + network + prediksi)
    supaya browser tidak perlu buka banyak koneksi terpisah.
    Dijalankan sekali saat startup via app lifespan di main.py.
    """
    while True:
        try:
            if manager.active:
                payload = {
                    "type":      "snapshot",
                    "stats":     gate_service.get_stats(),
                    "analytics": gate_service.get_analytics(),
                    "anomaly":   detector.get_summary(),
                    "network":   gate_service.get_network(),
                    "forecast":  predictor.get_forecast(),
                    "log":       [
                        json.loads(e)
                        for e in r.lrange("gate:log", 0, 49)
                    ],
                }
                await manager.broadcast(payload)
        except Exception as e:
            # Jangan crash background task karena satu error
            print(f"[broadcast_loop] error: {e}")
        await asyncio.sleep(1)
