# Pull Request

## Deskripsi

Jelaskan secara singkat apa yang diubah dan mengapa. Sertakan konteks yang cukup
supaya reviewer memahami tanpa harus menebak.

## Issue Terkait

- Fixes #`<nomor-issue>` (jika ada)
- Closes #`<nomor-issue>` (jika ada)

Jika tidak berkaitan dengan issue, tulis **Tidak ada** dan jelaskan alasannya.

## Tipe Perubahan

Pilih salah satu (hapus yang tidak relevan):

- [ ] 🐛 Bug fix
- [ ] ✨ Fitur baru
- [ ] 📝 Dokumentasi
- [ ] ♻️ Refactor (tidak mengubah perilaku)
- [ ] 🧪 Test / Benchmark
- [ ] 🔧 Konfigurasi / CI / Infra

## Checklist

Sebelum submit, pastikan semua poin berikut terpenuhi:

- [ ] ✅ `python3 tests/test_packet.py` lulus (tanpa Redis)
- [ ] ✅ `python3 tests/pipeline_benchmark.py --gates 2 --uids 20 --duration 3` jalan (tanpa Redis)
- [ ] ✅ Python dapat di-compile tanpa error (`python3 -m py_compile`)
- [ ] 📝 Dokumentasi diperbarui jika ada perubahan struktur/modul
- [ ] 📄 Tidak ada file duplikat di root `raspi/` (semua modul di `raspi/receiver/` atau `raspi/backend/`)
- [ ] ⚙️ Jika mengubah `raspi/setup/*.service` — path `WorkingDirectory`/`EnvironmentFile` sinkron di kedua service & `setup_raspi.sh`
- [ ] 🧹 Tidak ada perubahan yang tidak disengaja di file lain

## Screenshot (opsional)

Untuk perubahan UI/dashboard, lampirkan screenshot:
- Sebelum:
- Sesudah:

## Catatan Tambahan

Hal-hal lain yang perlu diketahui reviewer (misal: dependensi baru, cara test manual, trade-off):