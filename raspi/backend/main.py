"""
main.py — Entry point aplikasi Sat Set Tap backend.

Cara jalankan:
    cd raspi/
    python3 -m backend.main

Atau via uvicorn langsung:
    uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload

Struktur:
    backend/
    ├── main.py                  ← file ini
    ├── config.py                ← semua config dari .env
    ├── routes/
    │   ├── stats.py             ← /api/stats, /api/analytics, dst
    │   ├── participants.py      ← /api/register, /api/register/import, dst
    │   ├── events.py            ← /api/flush, /api/lockdown, dst
    │   ├── anomaly.py           ← /api/anomaly
    │   └── websocket.py         ← /ws + background broadcast loop
    └── services/
        ├── redis_service.py     ← koneksi Redis terpusat
        ├── gate_service.py      ← logic stats, analytics, network
        └── websocket_manager.py ← connection manager WebSocket
"""

import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()  # baca .env sebelum apapun diimport

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import DASHBOARD_PORT
from backend.routes import stats, participants, events, anomaly, websocket
from backend.routes.websocket import broadcast_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context: jalankan background task saat startup,
    bersihkan saat shutdown.
    Ini cara FastAPI yang benar untuk startup/shutdown tasks —
    menggantikan pola @app.on_event("startup") yang deprecated.
    """
    task = asyncio.create_task(broadcast_loop())
    print("[main] Background broadcast loop started")
    yield
    task.cancel()
    print("[main] Background broadcast loop stopped")


app = FastAPI(
    title="Sat Set Tap API",
    description="Backend sistem manajemen akses event berbasis IoT",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — izinkan akses dari browser (penting saat frontend dan backend
# dijalankan di port berbeda saat development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan semua router
app.include_router(stats.router)
app.include_router(participants.router)
app.include_router(events.router)
app.include_router(anomaly.router)
app.include_router(websocket.router)

# Serve frontend sebagai static files
# Semua request yang tidak cocok dengan /api/* atau /ws akan dapat index.html
# Ini yang memungkinkan frontend dan backend jalan dari satu server
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=DASHBOARD_PORT,
        reload=False,  # matikan reload di production (RPi)
    )
