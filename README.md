# Sat Set Tap

> Sistem manajemen akses event berbasis IoT — menggantikan QR/gelang dengan tap e-KTP via LoRa mesh network.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Platform](https://img.shields.io/badge/platform-ESP32%20%7C%20RPi-blue)
![Protocol](https://img.shields.io/badge/protocol-LoRa%20433MHz-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Latar Belakang

Sistem gate event konvensional memiliki dua masalah utama:

- **Antrean lambat** — scan QR membutuhkan 3–10 detik per orang
- **Jaringan tidak stabil** — WiFi/4G sering overload di lokasi event ramai

Sat Set Tap menyelesaikan keduanya: e-KTP sebagai token masuk (tap < 1 detik) dan LoRa mesh sebagai infrastruktur jaringan yang bebas internet.

---

## Arsitektur Sistem

```
[Gate Node]              [Relay A]
ESP32 + LoRa   ──LoRa──► ESP32 + LoRa ──LoRa──► [Gateway ESP32]
+ PN532 NFC              [Relay B]                      │
+ Servo SG90   ──LoRa──► ESP32 + LoRa ──LoRa──►   USB Serial
                         (failover)                     │
                                                  [Raspberry Pi]
                                                  receiver/receiver.py
                                                  Redis DB (AOF)
                                                  backend/main.py
                                                        │
                                                  [Browser / Laptop]
                                                  via Tailscale VPN
```

---

## Packet Format

Setiap tap KTP menghasilkan packet **12 bytes (24 char hex)**:

| Byte  | Field     | Ukuran | Keterangan |
|-------|-----------|--------|------------|
| 0     | Command   | 1 byte | `0x01`=TAP_REQ · `0x02`=RESP_OK · `0x03`=RESP_DENY · `0x04`=PING · `0x05`=LOCKDOWN · `0x06`=UNLOCK · `0x07`=HEARTBEAT |
| 1     | Gate ID   | 1 byte | ID gate pengirim (1–255) |
| 2–5   | KTP UID   | 4 byte | UID chip e-KTP dari PN532 |
| 6     | Hop Count | 1 byte | Sisa hop relay (mulai 3, berkurang tiap lompat) |
| 7     | Reserved  | 1 byte | `0x00` |
| 8–9   | Timestamp | 2 byte | Detik sejak boot (0–65535) |
| 10–11 | CRC-16    | 2 byte | Checksum byte 0–9 (CCITT-FALSE) |

Contoh: `0101188235CA0300001EFC93`

---

## Komponen Hardware

### Per Gate Node
| Komponen     | Spek             | Fungsi               |
|--------------|------------------|----------------------|
| ESP32 DevKit | Dual-core 240MHz | Mikrokontroler utama |
| LoRa SX1278  | 433MHz · SF9     | Transmisi data       |
| PN532        | I2C · 13.56MHz   | Baca UID e-KTP       |
| Servo SG90   | PWM · GPIO13     | Buka/tutup gate      |
| Antena       | 433MHz · 12dBi   | Jangkauan sinyal     |

### Per Relay Node
| Komponen     | Spek         | Fungsi                  |
|--------------|--------------|-------------------------|
| ESP32 DevKit | —            | Mikrokontroler          |
| LoRa SX1278  | 433MHz · SF9 | Terima & forward packet |

### Raspberry Pi (Base)
| Komponen       | Keterangan                        |
|----------------|-----------------------------------|
| Raspberry Pi 4 | Server utama                      |
| Redis 6.x      | Database in-memory + AOF persist  |
| Python 3.9     | Runtime receiver & backend        |
| Tailscale      | Remote access VPN                 |

### Registration Station (H-1)
| Komponen    | Keterangan                |
|-------------|---------------------------|
| Arduino Uno | Mikrokontroler            |
| PN532       | I2C (DIP: SW1=ON SW2=OFF) |

---

## Wiring

Lihat [docs/wiring.md](docs/wiring.md) untuk diagram lengkap semua node.

---

## Struktur Repository

```
Sat-Set-Tap/
├── firmware/                    # Kode Arduino/ESP32
│   ├── gate_node/               # Node gate + PN532 + Servo
│   ├── relay_node/              # Node relay failover
│   ├── gateway/                 # Gateway USB Serial ke RPi
│   └── registration_reader/     # Arduino reader H-1
├── raspi/                       # Kode Raspberry Pi
│   ├── backend/                 # FastAPI backend (API + WebSocket)
│   │   ├── main.py              # Entry point — jalankan dengan: python3 -m backend.main
│   │   ├── config.py            # Konfigurasi dari .env
│   │   ├── .env.example         # Template config (copy ke .env)
│   │   ├── routes/              # HTTP & WebSocket route handlers
│   │   │   ├── stats.py         # GET /api/stats, /api/analytics, /api/network
│   │   │   ├── participants.py  # GET/POST/DELETE /api/register
│   │   │   ├── events.py        # DELETE /api/flush, POST /api/lockdown
│   │   │   ├── anomaly.py       # GET /api/anomaly
│   │   │   └── websocket.py     # WS /ws + broadcast loop
│   │   └── services/            # Business logic
│   │       ├── gate_service.py  # Stats, analytics, network, load balance
│   │       ├── redis_service.py # Koneksi Redis terpusat
│   │       └── websocket_manager.py # WebSocket connection manager
│   ├── frontend/                # Dashboard web (static files)
│   │   ├── index.html           # Ops View — monitoring realtime untuk operator gate
│   │   ├── data.html            # Data View — manajemen peserta untuk panitia
│   │   ├── style.css            # Styling (dark/light mode)
│   │   └── app.js               # JavaScript — WebSocket, fetch, render
│   ├── receiver/                # Core packet processing
│   │   ├── receiver.py          # Serial reader + packet dispatcher
│   │   ├── packet.py            # Packet builder & parser
│   │   ├── redis_handler.py     # Redis operations (store_tap, register, dll)
│   │   ├── anomaly.py           # AI Security — deteksi anomali realtime
│   │   ├── lora_receiver.py     # LoRa receiver (pySX127x)
│   │   └── registration_station.py # CLI registrasi peserta H-1
│   ├── setup/                   # Systemd service files
│   │   ├── satset-dashboard.service
│   │   └── satset-receiver.service
│   ├── simulate_event.py        # Simulasi event via virtual serial port
│   └── requirements.txt
├── tests/                       # Unit tests + mock
│   ├── test_packet.py
│   ├── test_raspi.py
│   └── mock/
└── docs/                        # Dokumentasi & diagram
```

---

## Setup & Instalasi

### 1. Raspberry Pi

```bash
# Clone repo
git clone https://github.com/Anwarupee/Sat-Set-Tap.git
cd Sat-Set-Tap

# Install Python dependencies
pip3 install -r raspi/requirements.txt

# Buat file config dari template
cp raspi/backend/.env.example raspi/backend/.env
nano raspi/backend/.env  # isi REDIS_PASS, SERIAL_PORT, dll

# Install systemd services (auto-start saat boot)
sudo cp raspi/setup/satset-dashboard.service /etc/systemd/system/
sudo cp raspi/setup/satset-receiver.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable satset-dashboard satset-receiver
sudo systemctl start  satset-dashboard satset-receiver
```

Akses dashboard: `http://<tailscale-ip>:8080`

### 2. Redis AOF Persistence

Agar data tidak hilang saat RPi mati mendadak:

```bash
sudo nano /etc/redis/redis.conf
```

Ubah:
```
appendonly yes
appendfsync everysec
```

```bash
sudo systemctl restart redis
```

### 3. Firmware ESP32

Buka Arduino IDE, install library:
- `LoRa` by Sandeep Mistry
- `Adafruit PN532`
- `ESP32Servo`

Flash masing-masing sketch:

| Sketch | Target |
|--------|--------|
| `firmware/gate_node/`  | ESP32 di pintu masuk |
| `firmware/relay_node/` | ESP32 relay (ubah `RELAY_ID`) |
| `firmware/gateway/`    | ESP32 yang colok ke RPi |

**Penting:** Pastikan parameter LoRa sama di semua node:
```cpp
#define LORA_FREQ  433E6
#define LORA_SF    9
#define LORA_BW    125E3
#define LORA_SW    0x12
```

### 4. Wiring Gate Node

```
ESP32        LoRa SX1278
GPIO5   ──►  SS/CS
GPIO14  ──►  RST
GPIO2   ──►  DIO0
GPIO18  ──►  SCK
GPIO19  ──►  MISO
GPIO23  ──►  MOSI
3.3V    ──►  VCC   ⚠️ bukan 5V!

ESP32        PN532
GPIO21  ──►  SDA
GPIO22  ──►  SCL

ESP32        Servo SG90
GPIO13  ──►  Signal (kuning)
VIN     ──►  VCC   (merah) — 5V
GND     ──►  GND   (coklat)
```

---

## Cara Pakai

### Hari H-1 — Registrasi Peserta

**Opsi A: Import CSV massal dari Data View**

Buka `http://<IP>:8080/data.html` → tab Peserta → Import CSV.

Format CSV:
```
uid,name,token_max
A1B2C3D4,Budi Santoso,3
E5F6A7B8,Siti Rahayu,3
```

**Opsi B: Registration Station (Arduino + PN532)**

```bash
python3 raspi/receiver/registration_station.py \
  --serial /dev/ttyUSB0 \
  --redis-pass <pass> \
  --tokens 3
```

Tempelkan KTP ke reader → UID tersimpan otomatis.

### Hari H — Event Berlangsung

Receiver dan dashboard jalan otomatis via systemd. Akses:

- **Ops View** — `http://<IP>:8080` — untuk operator gate
- **Data View** — `http://<IP>:8080/data.html` — untuk panitia

### Simulasi Event (Testing)

```bash
# Terminal 1 — virtual serial port
socat -d -d pty,raw,echo=0 pty,raw,echo=0

# Terminal 2 — receiver dengan slave port
python3 raspi/receiver/receiver.py --serial /dev/pts/X --redis-pass <pass>

# Terminal 3 — simulator dengan master port
python3 raspi/simulate_event.py \
  --port /dev/pts/Y \
  --redis-pass <pass> \
  --uids 100 \
  --gates 2 \
  --duration 10
```

---

## Dashboard

### Ops View (`/`)
Untuk **operator gate** — monitoring realtime dari jarak jauh.

| Fitur | Keterangan |
|-------|------------|
| Stats realtime | Terdaftar, sudah masuk, total tap, gate online |
| Security Monitor | 4 jenis anomali: TAILGATING, UNKNOWN_FLOOD, RAPID_CROSS_GATE, GATE_SILENT |
| AI Forecast | Prediksi kepadatan per gate 5 menit ke depan (HIGH/MED/LOW) |
| Network Status | Latency + RSSI signal bars per gate |
| Gate Cards | Status online/offline, total tap, lockdown control |
| Lockdown | Kunci/buka gate dari jarak jauh — auto-lockdown saat anomali HIGH |
| Chart | Frekuensi tap per menit per gate |
| Ticker | 3 event tap terbaru secara realtime |

### Data View (`/data.html`)
Untuk **panitia/admin** — manajemen data dan kontrol penuh.

| Tab | Fitur |
|-----|-------|
| Peserta | Tabel semua UID + search + filter (Semua/Masuk/Belum/Token Habis) |
| Peserta | Import CSV massal, Export peserta, Manual Check-In, Revoke UID |
| Event Log | 1000 entri terakhir + filter status + filter gate + Export log |
| Kontrol | Flush Event (ketik `RESET_LOG`) + Flush Semua (ketik `HAPUS_SEMUA`) |
| Kontrol | Lockdown/Unlock semua gate + status per gate |

---

## Keamanan

- **SSH Key** — password login dinonaktifkan, hanya key-based
- **Redis auth** — password wajib, bind ke Tailscale IP
- **Redis AOF** — persistensi data saat RPi mati mendadak
- **CRC-16** — setiap packet divalidasi, packet corrupt dibuang
- **Tailscale VPN** — akses remote hanya via jaringan privat
- **Token system** — setiap UID punya kuota masuk terbatas
- **AI Anomaly Detection** — 4 jenis anomali realtime dengan state di Redis (shared antar proses)
- **Auto-lockdown** — gate otomatis dikunci saat anomali HIGH terdeteksi
- **Lockdown block** — tap diblock di receiver saat gate sedang lockdown
- **Admin override** — unlock manual oleh admin tidak bisa di-override anomali selama 30 menit

---

## Testing

```bash
# Unit test packet parser
python3 tests/test_packet.py

# Test koneksi RPi (Redis + packet)
python3 tests/test_raspi.py

# Simulasi event realistis (100 UID, 2 gate, 10 menit)
python3 raspi/simulate_event.py --auto --uids 100 --gates 2 --duration 10 --redis-pass <pass>
```

---

## Kontributor

| Nama | Peran |
|------|-------|
| Muhammad Yanuar Andrianto Putra | Network, RPi, Redis, Backend, Dashboard |
| Rezan Dzaky Ambrita | Hardware, ESP32, LoRa, PN532 |

**Pembimbing:** Pak Hudya  
**Institusi:** CEP CCIT-FTUI

---

## Pengembangan Lanjutan

### NFC Self-Registration *(In Progress)*

Peserta dapat mendaftarkan e-KTP mandiri dari HP masing-masing tanpa perlu datang ke booth registrasi H-1.

**Flow:**
```
Panitia share link → peserta buka di Chrome Android →
tap e-KTP ke belakang HP → UID terbaca via Web NFC API →
isi nama → submit → langsung terdaftar di sistem →
tinggal datang hari-H dan tap di gate
```

**Stack:**
- Web NFC API (Chrome Android 89+)
- PWA — tidak perlu install aplikasi
- Endpoint baru: `POST /api/register/nfc`
- Token registrasi untuk validasi peserta yang berhak daftar

**Keunggulan:**
- Tidak ada antrean di booth H-1
- Panitia tidak perlu standby di registration station
- Peserta bisa daftar kapan saja sebelum hari event

**Keterbatasan:**
- iOS tidak support Web NFC (restriksi Apple)
- Hanya bisa di Chrome Android 89+

**Status:** Dalam pengembangan

---

## Lisensi

MIT License — bebas digunakan dengan menyertakan atribusi.

---

<p align="center">
  <sub>Sat Set Tap · Venture Studio CCIT-FTUI</sub>
</p>
