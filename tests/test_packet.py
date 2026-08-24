"""Unit test v3 — packet 12 bytes (24 char hex)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "raspi", "receiver"))
from packet import parse_hex_packet, build_hex_packet, crc16, Command

def test(name, fn):
    try:
        fn()
        print(f"  ✓  {name}")
    except Exception as e:
        print(f"  ✗  {name} — {type(e).__name__}: {e}")

print("=== Packet v3 Tests ===\n")

# Build lalu parse
print("[ Build & Parse ]")

def t_roundtrip():
    h = build_hex_packet(Command.TAP_REQUEST, 1, "12AB34CD", timestamp=30)
    p = parse_hex_packet(h)
    assert p.command == Command.TAP_REQUEST
    assert p.gate_id == 1
    assert p.ktp_uid == "12AB34CD"
    assert p.timestamp == 30
    assert p.is_crc_valid

def t_length():
    h = build_hex_packet(Command.TAP_REQUEST, 1, "12AB34CD")
    assert len(h) == 24, f"len={len(h)}"

def t_gate_max():
    h = build_hex_packet(Command.TAP_REQUEST, 255, "AABBCCDD")
    p = parse_hex_packet(h)
    assert p.gate_id == 255

def t_hop_count():
    h = build_hex_packet(Command.TAP_REQUEST, 1, "12AB34CD", hop_count=3, timestamp=30)
    p = parse_hex_packet(h)
    assert p.hop_count == 3, f"hop={p.hop_count}"
    assert p.timestamp == 30

def t_all_commands():
    for cmd in Command:
        h = build_hex_packet(cmd, 1, "12AB34CD")
        p = parse_hex_packet(h)
        assert p.command == cmd

def t_crc_valid():
    h = build_hex_packet(Command.TAP_REQUEST, 2, "DEADBEEF", timestamp=100)
    p = parse_hex_packet(h)
    assert p.is_crc_valid

test("Roundtrip build→parse", t_roundtrip)
test("Panjang hex 24 char", t_length)
test("Gate ID max 255", t_gate_max)
test("Hop count & timestamp", t_hop_count)
test("Semua command codes", t_all_commands)
test("CRC valid setelah build", t_crc_valid)

print("\n[ Validasi Error ]")

def t_wrong_length():
    try:
        parse_hex_packet("0101AABB")
        assert False
    except ValueError:
        pass

def t_less_than_24():
    try:
        parse_hex_packet("0101" + "AABBCCDD" + "0300" + "001E" + "1234"[:8])
        assert False
    except ValueError:
        pass

def t_bad_crc():
    h = build_hex_packet(Command.TAP_REQUEST, 1, "12AB34CD")
    # Korupsi byte terakhir
    corrupted = h[:-2] + "FF"
    try:
        parse_hex_packet(corrupted)
        assert False, "Harus raise CRC error"
    except ValueError as e:
        assert "CRC" in str(e)

def t_bad_command():
    # Build 12-byte packet dengan command invalid (0xFF)
    # build_hex_packet tidak memvalidasi command, parse-lah yang harus menolak.
    from packet import build_hex_packet, parse_hex_packet
    h = build_hex_packet(0xFF, 1, "12AB34CD")
    assert len(h) == 24
    try:
        parse_hex_packet(h)
        assert False
    except ValueError as e:
        assert "Command" in str(e), f"msg={e}"

def t_uid_wrong_length():
    try:
        build_hex_packet(Command.TAP_REQUEST, 1, "ABCD")  # 4 char, bukan 8
        assert False
    except ValueError:
        pass

def t_gate_zero():
    try:
        build_hex_packet(Command.TAP_REQUEST, 0, "12AB34CD")
        assert False
    except ValueError:
        pass

test("Reject hex != 24 char", t_wrong_length)
test("Reject CRC corrupt",   t_bad_crc)
test("Reject command invalid",t_bad_command)
test("Reject UID < 8 char",  t_uid_wrong_length)
test("Reject gate_id = 0",   t_gate_zero)

print("\n[ Packet Size ]")
def t_size():
    h = build_hex_packet(Command.TAP_REQUEST, 1, "12AB34CD")
    raw = bytes.fromhex(h)
    assert len(raw) == 12, f"Harus 12 bytes, dapat {len(raw)}"
    print(f"       → {len(raw)} bytes raw  |  {len(h)} chars hex string")
    assert len(h) == 24, f"Harus 24 chars, dapat {len(h)}"

test("12 bytes raw / 24 chars hex", t_size)

print("\n=== Done ===")
