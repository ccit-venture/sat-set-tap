"""
lora_receiver.py — Jalankan di RPi, terima packet dari ESP32 gate via LoRa SX1278.

Setup sebelum jalan:
  1. Enable SPI: sudo raspi-config -> Interface Options -> SPI -> Enable -> reboot
  2. Install library:
       sudo apt install -y python3-spidev python3-rpi.gpio
       git clone https://github.com/rpsreal/pySX127x ~/pySX127x
       cp -r ~/pySX127x/SX127x ~/sat-set-tap/raspi/SX127x

  3. Pastikan parameter LoRa sama dengan ESP32:
       Frekuensi : 433 MHz
       SF        : 9
       BW        : 125 kHz
       Sync word : 0x12

Usage:
  python3 lora_receiver.py
"""

import sys
import os
import time
import logging

# Resolve path relatif ke lokasi file ini, bukan dari mana script dijalankan
_HERE     = os.path.dirname(os.path.abspath(__file__))
_THEGATE  = os.path.abspath(os.path.join(_HERE, ".."))  # satu level ke atas = raspi/

# Tambahkan receiver/ dan raspi/ ke sys.path
sys.path.insert(0, os.path.join(_HERE))           # untuk packet.py & redis_handler.py
sys.path.insert(0, _THEGATE)                      # untuk SX127x/
from packet import parse_hex_packet, Command
from redis_handler import GateRedis

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lora_rx")

# ── Konfigurasi — harus sama persis dengan ESP32 ─────────────
LORA_FREQ     = 433       # MHz — sesuai antena 433 yang dipakai
LORA_SF       = 7         # Spreading Factor
LORA_BW       = 125e3     # Bandwidth
LORA_CR       = 5         # Coding Rate (4/5)
LORA_SYNCWORD = 0x12      # Sync word default LoRa library Arduino

STATUS_ICON = {
    "new":       "✓ MASUK   ",
    "duplicate": "⚠ DUPLIKAT",
}


def handle_packet(raw: bytes, db: GateRedis):
    """Terima raw bytes dari LoRa, parse, simpan ke Redis."""
    try:
        hex_str = raw.decode("ascii", errors="ignore").strip()
    except Exception:
        log.error(f"Gagal decode bytes: {raw}")
        return

    if not hex_str:
        return

    log.debug(f"Raw RX: '{hex_str}'")

    try:
        packet = parse_hex_packet(hex_str)
    except ValueError as e:
        log.error(f"✗ PARSE/CRC ERR | '{hex_str}' | {e}")
        return

    if packet.command != Command.TAP_REQUEST:
        log.debug(f"Skip non-TAP: {packet.command_label}")
        return

    result = db.store_tap(packet)
    icon   = STATUS_ICON.get(result["status"], "?")

    log.info(
        f"{icon} | Gate {packet.gate_id:>3} "
        f"| UID: {packet.ktp_uid} "
        f"| ts: {packet.timestamp} "
        f"| CRC: {'OK' if packet.is_crc_valid else 'FAIL'}"
    )


class GateLoRa:
    """Wrapper tipis untuk pySX127x."""

    def __init__(self):
        # Import di sini agar error message lebih jelas
        try:
            from SX127x.LoRa import LoRa
            from SX127x.board_config import BOARD
        except ImportError:
            log.error("Library SX127x tidak ditemukan!")
            log.error("Jalankan setup:")
            log.error("  git clone https://github.com/rpsreal/pySX127x ~/pySX127x")
            log.error("  cp -r ~/pySX127x/SX127x ~/sat-set-tap/raspi/SX127x")
            sys.exit(1)

        self._LoRa = LoRa
        self._BOARD = BOARD
        self._lora = None
        self._db = None

    def start(self, db: GateRedis):
        self._db = db
        self._BOARD.setup()
        self._BOARD.reset()

        # Buat subclass inline dengan override on_rx_done
        _db_ref   = db
        _handle   = handle_packet
        _LoRa_cls = self._LoRa

        class _Receiver(_LoRa_cls):
            def __init__(self):
                super().__init__(verbose=False)
                self.set_pa_config(pa_select=1)
                self.set_freq(LORA_FREQ)
                self.set_spreading_factor(LORA_SF)
                self.set_bw(6)            # index 6 = 125 kHz (lihat BW enum di SX127x/LoRa.py)
                self.set_coding_rate(LORA_CR)
                self.set_sync_word(LORA_SYNCWORD)
                self.set_rx_crc(True)
                self.set_mode(0x85)        # RXCONT mode

            def on_rx_done(self):
                payload = self.read_payload(nocheck=True)
                _handle(bytes(payload), _db_ref)
                self.set_mode(0x85)        # kembali ke RXCONT

            def on_crc_error(self):
                log.warning("LoRa hardware CRC error — packet dibuang")
                self.set_mode(0x85)

        self._lora = _Receiver()
        log.info(f"LoRa OK — {LORA_FREQ} MHz | SF{LORA_SF} | BW{int(LORA_BW/1e3)}kHz | SW:0x{LORA_SYNCWORD:02X}")
        log.info("Menunggu packet dari gate... (Ctrl+C untuk berhenti)")

        try:
            while True:
                time.sleep(0.05)
        except KeyboardInterrupt:
            log.info("Receiver berhenti.")
        finally:
            self._BOARD.teardown()


def main():
    # Cek SPI
    if not os.path.exists("/dev/spidev0.0"):
        log.error("SPI belum aktif!")
        log.error("Jalankan: sudo raspi-config -> Interface Options -> SPI -> Enable")
        log.error("Lalu: sudo reboot")
        sys.exit(1)

    # Init Redis
    db = GateRedis()
    if not db.ping():
        log.error("Redis tidak jalan! Jalankan: sudo systemctl start redis-server")
        sys.exit(1)
    log.info("Redis OK")

    # Start LoRa receiver
    rx = GateLoRa()
    rx.start(db)


if __name__ == "__main__":
    main()
