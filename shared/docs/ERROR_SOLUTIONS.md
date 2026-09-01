# Folder Vision Error Solutions

Catatan insiden dan bug yang sudah dianalisis. Masalah yang belum selesai tetap dicatat di [`BUGS.md`](BUGS.md) dan [`NEXT.md`](NEXT.md), bukan dipindahkan ke sini hanya karena ada dugaan solusi.

## Format

- ID stabil: `ERR-FV-NNN`.
- Tulis gejala, root cause, solusi, bukti aktual, dan status.
- Bedakan `Fixed + runtime verified`, `Fixed in source`, `Open`, dan `Mitigation`.
- Jangan menulis bahwa model, build, GUI, atau hardware sudah tervalidasi jika hanya lolos inspeksi source.

---

## ERR-FV-001 — OneDrive online-only file ikut ter-hydrate saat indexing

Status: `Fixed + runtime verified`

### Gejala

Windows menampilkan notifikasi Automatic file downloads ketika FileID sedang indexing. Ini berisiko menghabiskan kuota dan ruang disk.

### Root cause

Placeholder OneDrive online-only diperlakukan seperti file lokal yang boleh dibuka oleh parser, thumbnail, atau vision worker.

### Solusi

- Deteksi atribut cloud-only sebelum content access.
- Simpan/teruskan status `metadata_only`.
- Skip parser, OCR, thumbnail, embedding, dan VLM untuk placeholder.
- Jangan memanggil operasi yang dapat menghidrate file secara implisit.

### Bukti

Smoke test memakai kandidat offline OneDrive: `totalFiles=0`, atribut `Offline` tetap ada, dan tidak ada content yang dibuka.

---

## ERR-FV-002 — Full clean build/test terhenti karena dependency locked tidak tersedia offline

Status: `Open / Blocked by local artifact availability`

### Gejala

Targeted binary yang sudah tersedia dapat dijalankan, tetapi resolusi clean Rust/NuGet tidak selalu dapat menyelesaikan semua dependency saat jaringan/download tidak diizinkan.

### Root cause

Cache lokal tidak memiliki seluruh artifact yang dikunci; blocker Rust yang tercatat adalah `async-channel` dan `anyhow 1.0.104`, sementara full WinUI test membutuhkan locked NuGet assets.

### Solusi aman

- Jangan menjalankan restore otomatis pada koneksi metered.
- Dengan approval eksplisit, restore hanya artifact yang sudah dikunci.
- Setelah restore, jalankan full engine test dan full WinUI test; catat hasilnya di `STATE.md`.
- Jangan menghapus database, model, atau source untuk mengatasi blocker build.

### Bukti/batasan

Core publish dan App Debug build sudah berhasil pada artifact yang tersedia. Full clean reproducibility belum dianggap selesai.

---

## ERR-FV-003 — Checkbox rename membuat UI blank/hitam pada library besar

Status: `Fixed in source; GUI retest remains a gate`

### Gejala

Saat checkbox rename disentuh pada daftar besar, layar dapat berhenti merespons atau tampak hitam.

### Root cause

Preview rename materializes terlalu banyak proposal sekaligus dan interaksi checkbox ikut membebani UI thread.

### Solusi

- Batasi materialisasi proposal ke page/batch review.
- Memoize suggestion yang sudah dihitung.
- Virtualize/paginate daftar dan jangan render seluruh library.
- Proposal low-confidence atau redundant tetap tidak terpilih.

### Batasan

Source sudah memuat bounded review path. Retest GUI pada library besar tetap perlu dicatat sebagai bukti terpisah; source inspection bukan pengganti GUI acceptance.

---

## ERR-FV-004 — File yang dihapus masih muncul sebagai hasil search

Status: `Fixed + runtime verified`

### Gejala

File sudah dihapus di filesystem, tetapi row index masih aktif.

### Root cause

Watcher delete/rename belum mengirim tombstone untuk path yang tepat; index baru terkoreksi saat full reconciliation.

### Solusi

- Tambahkan `markPathDeleted` pada IPC.
- Tombstone path/descendant yang tepat dari event watcher.
- Exclude lifecycle `tombstone` dari active search.

### Bukti

Runtime delete smoke: file aktif sebelum penghapusan, file fisik hilang, lalu row database berubah menjadi `tombstone` dalam batas waktu smoke.

---

## ERR-FV-005 — AI rename menghasilkan nama generik atau tidak sesuai konteks

Status: `Fixed + runtime verified for local Qwen path`

### Gejala

Nama hasil vision terlalu generik, redundan dengan nama lama, atau berisiko menghilangkan extension.

### Root cause

Proposal diterima tanpa quality gate yang memeriksa confidence, konteks, redundansi, dan suffix file.

### Solusi

- Gunakan satu structured local Qwen call untuk caption, tags, dan proposal.
- Tolak nama generik, tidak pasti, atau redundant.
- Pertahankan extension dari filesystem.
- Tampilkan alasan/confidence dan minta approval checkbox sebelum mutasi.

### Bukti

Local Qwen image smoke menyimpan deskripsi dan proposal contextual; Rename + Move + Undo smoke mempertahankan extension dan berhasil di-undo.

---

## ERR-FV-006 — UI membuka engine kedua ketika background engine sudah hidup

Status: `Fixed + runtime smoke verified; reboot gate pending`

### Gejala

UI dan background startup dapat meluncurkan dua proses engine yang menulis database yang sama.

### Root cause

UI sebelumnya memiliki ownership engine sendiri, sementara Core/startup juga dapat aktif.

### Solusi

- Core menjadi satu-satunya owner dan respawner `FileIDEngine`.
- UI hanya memakai current-user named pipe.
- Startup tetap hidden dan tidak mengunduh model/package.

### Bukti/batasan

Smoke runtime menunjukkan satu Core + satu engine dan shortcut mengarah ke app yang ter-stage. Login/reboot acceptance tetap perlu dibuktikan terpisah.

---

## ERR-FV-007 — Generated Rust incremental cache menghabiskan disk

Status: `Mitigation`

### Gejala

Folder target build dapat tumbuh beberapa gigabyte dan membuat ruang kosong virtual disk terlihat habis.

### Solusi aman

- Bedakan source/database/model dari generated build cache.
- Ukur dan pastikan path target tepat sebelum cleanup.
- Hapus hanya cache generated yang sudah diverifikasi, bukan `AppData`, database, model, OneDrive, atau seluruh workspace.
- Build ulang saat diperlukan; cache akan dibuat kembali.

### Aturan

Jangan menjalankan recursive delete pada path yang belum diverifikasi. Penghematan disk bukan alasan untuk menghapus data library atau artifact model secara membabi buta.

---

## Template insiden baru

```markdown
## ERR-FV-NNN — Judul singkat

Status: `Open` | `Fixed in source` | `Fixed + runtime verified` | `Mitigation`

### Gejala

...

### Root cause

...

### Solusi

...

### Bukti verifikasi aktual

- `command` / runtime / GUI / hardware: ...

### Batasan

...
```
