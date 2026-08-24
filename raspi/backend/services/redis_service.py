"""
services/redis_service.py — Koneksi Redis terpusat.

Semua service lain import `r` dari sini.
Kenapa: supaya hanya ada SATU koneksi Redis di seluruh aplikasi,
bukan tiap service buat sendiri-sendiri.
"""

import redis
from backend.config import REDIS_HOST, REDIS_PORT, REDIS_PASS

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASS,
    decode_responses=True,
)
