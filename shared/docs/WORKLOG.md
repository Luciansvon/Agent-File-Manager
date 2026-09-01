# Folder Vision Worklog

File ini mencatat pekerjaan yang benar-benar dilakukan, keputusan yang sudah disetujui, bukti verifikasi, dan pekerjaan yang masih terbuka.

Worklog bukan pengganti:

- `AGENTS.md` untuk aturan kerja;
- `FOLDER_VISION_ARCHITECTURE.md` untuk arsitektur Windows terbaru;
- `DECISIONS.md` untuk alasan keputusan non-obvious;
- `BUGS.md` untuk masalah yang masih terbuka;
- `ERROR_SOLUTIONS.md` untuk root cause dan solusi error;
- `NEXT.md` untuk pekerjaan berikutnya.

## Aturan pencatatan

- Tambahkan catatan terbaru di paling atas.
- Jangan menghapus catatan lama hanya karena rencana berubah.
- Bedakan `Selesai + terverifikasi`, `Source-wired`, `Pending`, `Blocked`, dan `Deferred`.
- Jangan mencatat rencana sebagai fitur yang sudah tersedia.
- Cantumkan file atau area yang terdampak.
- Cantumkan command/test/smoke test aktual. Jika tidak dijalankan, tulis `NOT RUN`.
- Perubahan arsitektur wajib disinkronkan ke `DECISIONS.md` dan dokumen arsitektur terkait.
- Bugfix wajib mempunyai entri di `ERROR_SOLUTIONS.md`; bug yang belum selesai tetap berada di `BUGS.md`.

---

## 2026-09-01 — Documentation hub dan struktur project dirapikan

Status: `Selesai + terverifikasi`.

### Yang berubah

- Menambahkan `shared/docs/README.md` sebagai documentation hub dan urutan baca agent.
- Menambahkan `shared/docs/WORKLOG.md` dan `shared/docs/ERROR_SOLUTIONS.md` dengan format yang mengikuti pola CatatToko.
- Menambahkan `PROJECT_FOLDERS_STRUCTURE_BLUEPRINT.md` sebagai peta struktur repo.
- Menambahkan link dokumentasi ke root `README.md`, persistence list `AGENTS.md`, dan aturan kontribusi.

### Keputusan struktur

- `shared/docs` tetap menjadi lokasi canonical karena FileID dan banyak link internal sudah menggunakannya.
- Tidak dibuat `docs/` kedua di root.
- Audit historis, asset visual, source, cache build, database, model, dan log tidak dipindahkan atau dihapus.
- Morrow diperiksa sebagai referensi, tetapi folder `docs` aktifnya kosong selain `archive`; pola dokumentasi operasional yang dipakai berasal dari CatatToko.

### Validasi aktual

- Semua target file dokumentasi ada.
- Link internal dari hub, worklog, error-solutions, dan blueprint dicek dengan `Test-Path`: seluruhnya valid.
- `git diff --check`: tidak menemukan whitespace error.
- Tidak ada command build, restore, model download, atau runtime restart yang dijalankan untuk cleanup ini.

---

## 2026-09-01 — Runtime acceptance untuk background indexing dan aksi file

Status: `Selesai + terverifikasi` untuk smoke test Windows lokal; clean rebuild penuh dan reboot acceptance masih mengikuti gate di `NEXT.md`.

### Yang dibuktikan

- `FileID.App` tersambung ke `FolderVision.Core`; Core menjadi parent persisten untuk `FileIDEngine`.
- File gambar baru yang disalin ke `C:\Users\shint\Downloads` terdeteksi otomatis setelah settle tanpa menekan Scan.
- File diproses sebagai single-file scan, dianalisis oleh `qwen3-vl:2b-instruct` melalui Ollama loopback, lalu caption dan proposal nama tersimpan di database lokal.
- Persistent lexical search menemukan file tersebut dari deskripsi AI tanpa memulai full scan baru.
- Rename + Move + Undo terverifikasi pada corpus terisolasi; extension tetap dipertahankan dan operasi melewati journal.
- File yang dihapus menjadi `tombstone` di index dan keluar dari active search; file fisiknya benar-benar hilang pada smoke test.
- Kandidat OneDrive online-only dilewati tanpa membuka content atau mengubah atribut `Offline`; smoke test menghasilkan `totalFiles=0`.
- Startup registration `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FolderVisionCore` dan shortcut desktop `Folder Vision AI.lnk` tersedia.

### Validasi aktual

- Rust engine debug build: berhasil.
- `FolderVision.Core` Release publish: berhasil dan binary yang distage cocok dengan hasil publish.
- `FileID.App` Debug build: 0 warning, 0 error.
- Isolated Rename + Move + Undo smoke: `Apply 1/1`, `Undo 1/1`.
- Runtime watcher, persistent search, delete tombstone, dan OneDrive no-hydration smoke: berhasil.
- Tidak ada download model, package, atau artifact besar baru pada sesi ini.

Detail binary, database, log, dan batasan acceptance ada di [`GRAVITY_HANDOFF.md`](GRAVITY_HANDOFF.md).

### Yang belum dianggap selesai

- Full clean Rust compile/test dan full WinUI test gate masih menunggu artifact locked yang belum tersedia offline.
- Reboot/login acceptance belum menggantikan smoke test startup registration.
- USN/MFT initial enumeration dan throughput library besar masih perlu dibuktikan di corpus NTFS terisolasi.
- Chat-first search/RAG dan benchmark dense/hybrid belum selesai.

---

## 2026-08-31 — Incremental ingestion, canonical content, dan local vision rename

Status: `Selesai + terverifikasi` pada source dan smoke test yang disebut di `STATE.md`.

- Core mengirim konfigurasi background roots dan pause state melalui IPC typed; engine memakai bounded polling USN dan fallback watcher.
- Watcher melakukan debounce, settle check, skip temporary download names, dan single-file scan.
- SQLite menyimpan lifecycle/tombstone, canonical content, content chunks, dan persistent FTS; content version berubah saat hash content berubah.
- Qwen3-VL 2B menjadi backend rename lokal default dengan JSON terstruktur, quality gate, batch bounded, dan unload setelah batch.
- UI rename hanya mematerialisasi review batch terbatas; checkbox tetap memerlukan approval eksplisit.

Referensi: [`STATE.md`](STATE.md) entri 2026-08-31 dan [`DECISIONS.md`](DECISIONS.md).

---

## 2026-08-30 — Folder Vision M1 foundation dan Core pipe cutover

Status: `Source-wired` lalu dinaikkan ke runtime smoke pada entri 2026-09-01.

- `FolderVision.Core` ditambahkan sebagai host background dengan named pipe current-user, tray, startup registration, dan ownership engine.
- UI tidak lagi menjadi pemilik langsung engine; Core menjaga indexing tetap hidup saat window ditutup.
- Catalog/lifecycle schema, durable processing queue, OneDrive metadata-only state, dan bounded frame handling ditambahkan.
- Scope produk dikembalikan ke organizer foto + dokumen; aksi rename/move tetap preview dan approval-gated.

Referensi: [`STATE.md`](STATE.md) entri 2026-08-30 dan [`FOLDER_VISION_ARCHITECTURE.md`](FOLDER_VISION_ARCHITECTURE.md).

---

## Template entri baru

```markdown
## YYYY-MM-DD — Judul pekerjaan

Status: `Selesai + terverifikasi` | `Source-wired` | `Pending` | `Blocked` | `Deferred`

### Yang berubah

- ...

### File/area terdampak

- `path/to/file`

### Validasi aktual

- `command` — hasil singkat
- GUI/runtime/hardware: ...

### Batasan atau tindak lanjut

- ...
```
