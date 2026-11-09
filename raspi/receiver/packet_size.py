"""
Analisis ukuran data yang dikirim via LoRa.
Jalankan: python packet_size.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../receiver"))

from packet import Command, build_hex_packet, parse_hex_packet

# Contoh packet
EXAMPLE_UID = "12AB34CD"
packet_hex = build_hex_packet(Command.TAP_REQUEST, 1, EXAMPLE_UID)
packet_bytes = bytes.fromhex(packet_hex)
packet = parse_hex_packet(packet_hex)

print("=" * 50)
print("  ANALISIS UKURAN PACKET LORA")
print("=" * 50)

print("\n[ Format yang dikirim via Serial (hex string) ]")
print(f"  String  : {packet_hex}")
print(f"  Panjang : {len(packet_hex)} karakter")
print(f"  Ukuran  : {len(packet_hex.encode())} bytes  ← ini yang lewat serial ke RPi")

print("\n[ Payload aktual di udara (raw bytes) ]")
print(f"  Bytes   : {packet_bytes.hex(' ').upper()}")
print(f"  Ukuran  : {len(packet_bytes)} bytes  ← ini yang LoRa pancarkan")

print("\n[ Breakdown per field ]")
fields = [
    ("command  ", packet_bytes[0:1], packet.command_label),
    ("gate_id  ", packet_bytes[1:2], "Nomor gate"),
    ("ktp_uid  ", packet_bytes[2:6], "UID RFID e-KTP"),
    ("hop_count", packet_bytes[6:7], "Sisa hop"),
    ("reserved ", packet_bytes[7:8], "Cadangan"),
    ("timestamp", packet_bytes[8:10], "Detik sejak boot"),
    ("crc16    ", packet_bytes[10:12], "CRC-16/CCITT-FALSE"),
]
for name, b, desc in fields:
    print(f"  {name} : {b.hex().upper():16s}  ({len(b)} bytes)  — {desc}")

print("\n[ Perbandingan metode pengiriman ]")
rows = [
    ("Raw bytes (LoRa payload)",  len(packet_bytes),         "Ideal, paling efisien"),
    ("Hex string via Serial",     len(packet_hex.encode()),  "Yang sekarang dipakai ke RPi"),
    ("Teks biasa (nama+uid)",     45,                        "Contoh: 'GATE1 12AB34CD'"),
    ("JSON",                      80,                        "Contoh: {command:TAP_REQ,gate:1,uid:...}"),
]
for label, size, note in rows:
    bar = "█" * size
    print(f"  {label:<30} {size:>3} bytes  {bar}  ({note})")

print("\n[ Konteks LoRa bandwidth ]")
print("  LoRa SF7, BW500kHz  → ~21.9 kbps  max data rate")
print(f"  Teoritis bisa kirim ~{21900 // (12*8)} packet/detik (tanpa duty cycle)")
print("  Duty cycle LoRa Indonesia 1% → praktisnya ~18 packet/menit per node")
print("=" * 50)
