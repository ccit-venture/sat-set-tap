# Komponen Hardware

> Daftar komponen yang dibutuhkan per node. Untuk diagram koneksi pin, lihat [wiring.md](wiring.md)
> beserta gambar di [docs/wiring/](wiring/).

---

## Per Gate Node

| Komponen     | Spek             | Fungsi               |
|--------------|------------------|----------------------|
| ESP32 DevKit | Dual-core 240MHz | Mikrokontroler utama |
| LoRa SX1278  | 433MHz · SF9     | Transmisi data       |
| PN532        | I2C · 13.56MHz   | Baca UID e-KTP       |
| Servo SG90   | PWM · GPIO13     | Buka/tutup gate      |
| Antena       | 433MHz · 12dBi   | Jangkauan sinyal     |

Wiring → [docs/wiring.md#1-gate-node](wiring.md#1-gate-node)

---

## Per Relay Node

| Komponen     | Spek         | Fungsi                  |
|--------------|--------------|-------------------------|
| ESP32 DevKit | —            | Mikrokontroler          |
| LoRa SX1278  | 433MHz · SF9 | Terima & forward packet |

Wiring → [docs/wiring.md#3-relay-node](wiring.md#3-relay-node)

---

## Raspberry Pi (Base)

| Komponen       | Keterangan                        |
|----------------|-----------------------------------|
| Raspberry Pi 4 | Server utama                      |
| Redis 6.x      | Database in-memory + AOF persist  |
| Python 3.9     | Runtime receiver & backend        |
| Tailscale      | Remote access VPN                 |

Setup & konfigurasi → [deployment.md](deployment.md)

---

## Registration Station (H-1)

| Komponen    | Keterangan                |
|-------------|---------------------------|
| Arduino Uno | Mikrokontroler            |
| PN532       | I2C (DIP: SW1=ON SW2=OFF) |

Wiring → [docs/wiring.md#4-registration-station-h-1](wiring.md#4-registration-station-h-1)

---

## Persyaratan LoRa (harus sama di semua node)

```cpp
#define LORA_FREQ  433E6
#define LORA_SF    9
#define LORA_BW    125E3
#define LORA_SW    0x12
```

Detail parameter → [packet-format.md#lora-parameters](packet-format.md#lora-parameters)