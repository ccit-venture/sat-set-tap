# Contributing — Sat Set Tap

Terima kasih sudah ingin berkontribusi! 🎉

Project ini adalah sistem manajemen akses event berbasis IoT (ESP32 + LoRa +
Raspberry Pi). Sebelum mulai, baca dulu **[AGENTS.md](AGENTS.md)** — berisi
konvensi struktur folder, format packet, dan hal-hal yang sering salah dipahami.

Daftar isi:
1. [Cara Fork & Clone](#cara-fork--clone)
2. [Buat Branch](#buat-branch)
3. [Menjalankan Test](#menjalankan-test)
4. [Gaya Commit Message](#gaya-commit-message)
5. [Membuat Pull Request](#membuat-pull-request)
6. [Aturan Dokumentasi](#aturan-dokumentasi)
7. [Laporkan Bug / Usulkan Fitur](#laporkan-bug--usulkan-fitur)

---

## Cara Fork & Clone

1. Klik tombol **Fork** di kanan atas halaman repo
   `github.com/ccit-venture/sat-set-tap`.

2. Clone hasil fork ke lokal:

```bash
git clone https://github.com/<username-kamu>/sat-set-tap.git
cd sat-set-tap
```

3. Tambahkan repo asli sebagai `upstream` (untuk sinkronisasi):

```bash
git remote add upstream https://github.com/ccit-venture/sat-set-tap.git
```

Pastikan remote sudah benar:

```bash
git remote -v
# origin   → repo fork kamu
# upstream → ccit-venture/sat-set-tap
```

4. Sinkronkan branch `master` kamu dengan upstream:

```bash
git checkout master
git pull upstream master
```

> Selalu `pull upstream master` sebelum mulai bekerja supaya tidak bentrok saat
> review.

---

## Buat Branch

Gunakan nama branch yang deskriptif dan mengikuti pola:

| Jenis | Contoh nama branch |
|-------|--------------------|
| Fitur baru | `feature/nfc-self-registration` |
| Perbaikan bug | `fix/receiver-crc-error` |
| Dokumentasi | `docs/jelaskan-alur-tap` |
| Refactor | `refactor/consolidate-mock-redis` |
| Test / CI | `test/ci-python-compile` |

```bash
git checkout -b feature/nama-fitur
```

Kerjakan perubahan di branch ini, lalu commit.

---

## Menjalankan Test

**Wajib** menjalankan test yang bisa berjalan tanpa Redis sebelum submit PR:

```bash
# Unit test packet — dari root repo (tanpa Redis)
python3 tests/test_packet.py

# Benchmark pipeline — mock Redis, tanpa server (tanpa Redis)
python3 tests/pipeline_benchmark.py --gates 2 --uids 20 --duration 3
```

Test yang butuh Redis (jalankan jika kamu punya RPi/Redis aktif):

```bash
python3 tests/test_raspi.py
python3 tests/stress_test.py --gates 2 --uids 50 --duration 10
```

CI otomatis juga menjalankan compile-check + `test_packet.py` di setiap push/PR.

---

## Gaya Commit Message

Ikuti gaya repo saat ini (Conventional-ish short subject):

```
<tipe>: <deskripsi singkat>
```

Tipe yang dipakai:

- `feat:` — fitur baru
- `fix:` — perbaikan bug
- `refactor:` — perubahan struktur tanpa mengubah perilaku
- `docs:` — dokumentasi (README, docs/, AGENTS.md)
- `test:` — test / benchmark / CI

Contoh:

```bash
git add raspi/receiver/packet.py tests/test_packet.py
git commit -m "fix: validasi hop count saat parse packet"
```

> Satu commit sedapat mungkin mewakili satu perubahan logis. Jangan commit
> perubahan yang tidak saling berhubungan.

---

## Membuat Pull Request

1. Push branch kamu ke fork:

```bash
git push origin feature/nama-fitur
```

2. Di GitHub, buka halaman repo asli → tombol **Compare & pull request**.

3. Isi template PR yang otomatis muncul. Lengkapi:
   - Deskripsi perubahan
   - Issue yang di-fix (`closes #<nomor>`)
   - Checklist (pastikan test lulus)

4. Setelah submit, CI akan berjalan otomatis. Pastikan semua job hijau.

5. Maintainer akan me-review. Perbaiki masukan dengan menambahkan commit baru
   pada branch yang sama (bukan force-push ke branch yang sudah di-review).

---

## Aturan Dokumentasi

- README hanya berisi ringkasan proyek & quick start.
- Detail teknis ditaruh di `docs/` yang modular (lihat tabel dokumentasi di README).
- **Semua diagram alur memakai Mermaid** (`` ```mermaid ``), bukan simbol panah teks `->`.
- Tambahkan link balik `## Lihat Juga` saat membuat file markdown baru di `docs/`.
- Update README tabel dokumentasi jika menambah/mengubah file di `docs/`.

Struktur proyek:

```
firmware/   → kode Arduino/ESP32 (C++)
raspi/      → server Raspberry Pi (Python), modul di raspi/receiver/ & raspi/backend/
tests/      → unit test & benchmark
docs/       → dokumentasi modular
.github/    → template issue/PR & CI
```

**Perhatikan:** jangan menaruh modul di root `raspi/` — semua modul receiver
berada di `raspi/receiver/` (anomaly.py, predictor.py, dll sudah dipindah ke sana).

---

## Laporkan Bug / Usulkan Fitur

Gunakan template issue yang sudah disediakan:

- 🐛 [Laporan Bug](.github/ISSUE_TEMPLATE/bug_report.md)
- ✨ [Permintaan Fitur](.github/ISSUE_TEMPLATE/feature_request.md)

Untuk masalah keamanan, JANGAN buka issue publik — ikuti petunjuk di
[SECURITY.md](SECURITY.md).