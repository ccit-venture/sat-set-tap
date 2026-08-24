# Kebijakan Keamanan — Sat Set Tap

## Laporkan Kerentanan

Jika kamu menemukan kerentanan keamanan pada Sat Set Tap, **jangan** membuka
issue publik. Kirim laporan langsung ke maintainer agar bisa diperbaiki sebelum
diungkap.

**Kontak keamanan:** **Hudya** (Industrial Lecturer CCIT-FTUI) —
**mhudyaramadhana@gmail.com**

Sertakan dalam laporan:

- Deskripsi kerentanan dan potensi dampaknya
- Langkah reproduksi (sebaiknya minimal, tanpa data sensitif)
- Versi/branch yang terpengaruh (firmware, receiver, backend)
- (Opsional) usulan perbaikan

## Proses Penanganan

1. Maintainer menerima laporan dan mengonfirmasi dalam **48 jam**.
2. Kerentanan divalidasi dan kerentanan serupa diperiksa.
3. Perbaikan dikembangkan secara privat bila diperlukan.
4. Setelah diperbaiki, maintainer mengumumkan rilis/perbaikan dan mengkredit
   pelapor (jika diinginkan).

## Area yang Perlu Diperhatikan

- **Packet LoRa** — validasi CRC-16 dan ukuran packet (12 byte / 24 hex)
- **Redis** — auth password wajib; bind hanya ke jaringan internal/Tailscale
- **Dashboard** — jangan expose ke internet publik tanpa autentikasi tambahan
- **Token peserta** — kuota `token_left` per UID, revoke bila mencurigakan

## Rujukan

- [docs/security.md](docs/security.md) — detail langkah keamanan yang diterapkan