"""
routes/stats.py — Endpoint data statistik dan analytics.

Setiap route handler di sini sengaja dibuat tipis:
hanya terima request, panggil service, return hasil.
Tidak ada logic di sini.
"""

from fastapi import APIRouter
from backend.services import gate_service
from backend.services.redis_service import r
from backend.services.websocket_manager import manager
import json

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def api_stats():
    return gate_service.get_stats()


@router.get("/analytics")
def api_analytics():
    return gate_service.get_analytics()


@router.get("/loadbalance")
def api_loadbalance():
    return gate_service.get_load_balance()


@router.get("/network")
def api_network():
    return gate_service.get_network()


@router.get("/log")
def api_log(limit: int = 100):
    return [json.loads(e) for e in r.lrange("gate:log", 0, limit - 1)]
