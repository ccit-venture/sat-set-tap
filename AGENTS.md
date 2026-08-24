# AGENTS.md — Panduan untuk AI & Developer

Panduan kerja pada repositori **Sat Set Tap**. Baca ini sebelum mengubah kode agar
tidak merusak struktur, path import, atau konvensi yang sudah ada.

## Ringkasan Proyek

Sistem manajemen akses event berbasis IoT. Peserta **tap e-KTP** di gate (ESP32 +
PN532 + LoRa), packet dikirim lewat **LoRa mesh** ke **Raspberry Pi** (server)
yang memproses dengan **Redis** dan menampilkan dashboard via **FastAPI +
WebSocket**.

Arsitektur tiga lapis:
1. **firmware/** — sketch Arduino/ESP32 (C++)
2. **raspi/** — server Raspberry Pi (Python)
3. **docs/** — dokumentasi & diagram wiring

## Struktur Penting (`raspi/`)

Repo ini **monorepo** — akar repo berisi `firmware/`, `raspi/`, `tests/`, `docs/`.
Semua kode server berada di dalam `raspi/`. **PENTING:** modul diimpor relatif
dari dalam `raspi/`, dan banyak yang memakai `sys.path.insert` ke `raspi/receiver/`.

```
raspi/
├── backend/                # FastAPI (API + WebSocket + static frontend)
│   ├── main.py             # entry point: jalankan dengan `python3 -m backend.main`
│   ├── config.py           # baca env (.env) — satu-satunya tempat config
│   ├── .env.example        # template → copy ke .env
│   ├── routes/             # route HTTP/WS (stats, participants, events, anomaly, websocket)
│   └── services/           # business logic (gate_service, redis_service, websocket_manager)
├── frontend/               # dashboard web statis (index.html, data.html, style.css, app.js)
├── receiver/               # CORE — processing packet
│   ├── receiver.py         # baca serial + dispatcher
│   ├── packet.py           # packet 12 byte (24 hex): builder & parser + CRC-16
│   ├── packet_size.py      # validasi ukuran packet
│   ├── redis_handler.py    # semua operasi Redis (store_tap, import_uids, dll)
│   ├── anomaly.py          # deteksi anomali (AI statistical)
│   ├── predictor.py        # prediksi kepadatan gate (SMA)
│   ├── lora_receiver.py    # (opsional) receiver LoRa langsung tanpa serial
│   └── registration_station.py # CLI registrasi peserta H-1
├── setup/                  # systemd service + setup_raspi.sh
├── simulate_event.py       # simulasi event via virtual serial (socat)
└── requirements.txt
```

## Dokumentasi Modular (`docs/`)

Pengetahuan dipisah ke beberapa markdown — **jangan** menaruh seluruh detail teknis
di `README.md`. README hanya berisi ringkasan proyek & quick start (dengan diagram
**Mermaid**, bukan panah teks).

| File | Isi |
|------|-----|
| `docs/architecture.md` | Topologi, alur data (sequence diagram), komponen server |
| `docs/hardware.md` | Komponen hardware per node |
| `docs/wiring.md` | Diagram wiring + gambar di `docs/wiring/` |
| `docs/packet-format.md` | Format packet 12 byte / 24 hex + CRC-16 |
| `docs/deployment.md` | Setup RPi, Redis AOF, systemd service, `.env` |
| `docs/dashboard.md` | Fitur Ops View & Data View |
| `docs/security.md` | Keamanan & deteksi anomali |
| `docs/roadmap.md` | Pengembangan lanjutan (NFC self-registration) |

Aturan:
- Semua diagram alur memakai **Mermaid** (` ```mermaid `), bukan simbol `->`.
- Tambahkan dokumen baru dengan link balik (`## Lihat Juga`) di bagian bawah.
- Update tabel dokumentasi di `README.md` saat menambah/mengubah file di `docs/`.

## Cara Menjalankan

Setup deployment di RPi (asumsi: clone di `/home/pi/sat-set-tap`, user `pi`):

```bash
# Backend (dashboard) — dari dalam raspi/
cd raspi
python3 -m backend.main          # atau: uvicorn backend.main:app --port 8080

# Receiver (baca serial ESP32 gateway) — dari dalam raspi/
python3 receiver/receiver.py --serial /dev/ttyUSB0 --redis-pass <pass>
python3 receiver/receiver.py --mock            # tanpa hardware

# Simulasi event penuh (butuh socat)
python3 simulate_event.py --auto --uids 100 --gates 2 --duration 10 --redis-pass <pass>
```

Install sekali di RPi: `bash raspi/setup/setup_raspi.sh` (contoh, sesuaikan path).

## Konfigurasi (.env)

Salin `raspi/backend/.env.example` menjadi `raspi/backend/.env`. Variabel yang
dibaca `backend/config.py`:
`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASS`, `SERIAL_PORT`, `DASHBOARD_PORT`, `TOKEN_DEFAULT`.

## Format Packet (kritis!)

Packet **12 byte = 24 char hex**. Jangan "perbaiki" jadi 10 byte — itu versi lama.

| Byte | Field | Ukuran |
|------|-------|--------|
| 0 | Command | 1B (1=TAP_REQ, 2=RESP_OK, 3=RESP_DENY, 4=PING, 5=LOCKDOWN, 6=UNLOCK, 7=HEARTBEAT) |
| 1 | Gate ID | 1B |
| 2–5 | KTP UID | 4B |
| 6 | Hop Count | 1B (mulai 3) |
| 7 | Reserved | 1B |
| 8–9 | Timestamp | 2B big-endian |
| 10–11 | CRC-16 | 2B big-endian (CCITT-FALSE, byte 0–9) |

## Konvensi Penting

- **`build_hex_packet(command, gate_id, ktp_uid, hop_count=3, timestamp=None)`**
  — argumen ke-4 adalah `hop_count`, **bukan timestamp**. Gunakan keyword
  `timestamp=...` bila perlu menetapkan timestamp.
- **`redis_handler.py` memakai `hset(key, mapping={...})`** (Redis ≥ 4). Setiap
  mock/stub Redis (misal `MockRedisConnection` di benchmark) **harus mendukung
  bentuk `mapping=`** ini, bukan hanya `hset(key, field, value)`.
- `backend/` dan `receiver/` sering saling import via `sys.path.insert` ke
  `raspi/receiver/`. Jangan memindahkan file `anomaly.py`/`predictor.py` ke lokasi
  lain tanpa memperbarui semua `sys.path` di `backend/routes/*.py`.
- Frontend di-serve oleh backend (`app.mount("/", StaticFiles(...))`) — jangan
  jalankan frontend terpisah.

## Menjalankan Test

```bash
# Unit test packet (tidak butuh Redis) — dari root repo
python3 tests/test_packet.py

# Benchmark pipeline (mock Redis, tidak butuh server) — dari root repo
python3 tests/pipeline_benchmark.py --gates 2 --uids 20 --duration 3

# Test koneksi RPi + Redis (butuh Redis jalan)
python3 tests/test_raspi.py

# Stress test (butuh Redis jalan)
python3 tests/stress_test.py --gates 2 --uids 50 --duration 10
```

`test_packet.py` dan `pipeline_benchmark.py` bisa jalan tanpa Redis.
`stress_test.py` dan `test_raspi.py` butuh server Redis aktif.

## Hal yang Sering Salah

- Mengira packet = 10 byte (itu versi lama). Sekarang **12 byte / 24 hex**.
- Menaruh file di root `raspi/` yang seharusnya di `raspi/receiver/` (sejarah: ada
  `anomaly.py`, `predictor.py` lama di root — sudah dipindah, jangan dibuat lagi).
- Service systemd menunjuk `WorkingDirectory=/home/pi/sat-set-tap/raspi` — path
  berubah harus sinkron di kedua `.service` dan `setup_raspi.sh`.
