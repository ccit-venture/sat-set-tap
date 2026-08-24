"""
config.py — Satu-satunya tempat konfigurasi dibaca.

Semua modul lain import dari sini, bukan baca os.getenv() sendiri-sendiri.
Nilai dibaca dari environment variable (yang di-load dari file .env oleh
python-dotenv saat startup di main.py).

Kenapa dipisah ke file ini:
- Kalau ada perubahan nama env var, cukup ubah di sini — tidak perlu
  cari-cari di seluruh codebase.
- Mudah di-mock saat testing tanpa perlu patch os.environ di banyak tempat.
"""

import os

REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASS     = os.getenv("REDIS_PASS", "")

SERIAL_PORT    = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
TOKEN_DEFAULT  = int(os.getenv("TOKEN_DEFAULT", "3"))
