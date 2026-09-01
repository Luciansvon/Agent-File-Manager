# Folder Vision documentation hub

Dokumen aktif project ini berada di `shared/docs`. FileID sudah memakai path ini sebagai kontrak lintas-platform, jadi dokumentasi tidak dipindah ke root `docs/` agar link lama dan tooling tetap aman.

## Urutan baca

| Kebutuhan | Dokumen |
|---|---|
| Aturan kerja repo | [`AGENTS.md`](../../AGENTS.md) |
| Arsitektur Windows terbaru | [`FOLDER_VISION_ARCHITECTURE.md`](FOLDER_VISION_ARCHITECTURE.md) |
| Arsitektur FileID lintas-platform | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Kondisi yang benar-benar sudah terbukti | [`STATE.md`](STATE.md) |
| Pekerjaan berikutnya dan acceptance gate | [`NEXT.md`](NEXT.md) |
| Riwayat pekerjaan per sesi | [`WORKLOG.md`](WORKLOG.md) |
| Keputusan non-obvious dan alasannya | [`DECISIONS.md`](DECISIONS.md) |
| Bug yang masih terbuka | [`BUGS.md`](BUGS.md) |
| Error yang sudah dianalisis dan solusinya | [`ERROR_SOLUTIONS.md`](ERROR_SOLUTIONS.md) |
| Cara menjalankan test dan smoke test | [`TESTING.md`](TESTING.md) dan [`TEST.md`](TEST.md) |
| Runtime, keamanan, dan privasi | [`RUNTIME.md`](RUNTIME.md), [`SECURITY.md`](SECURITY.md), [`PRIVACY.md`](PRIVACY.md) |
| Model, lisensi, dan aturan download | [`MODELS.md`](MODELS.md) |
| Release gate | [`SHIP.md`](SHIP.md) dan [`WINDOWS_SIGNING.md`](WINDOWS_SIGNING.md) |
| Handoff ke agent berikutnya | [`GRAVITY_HANDOFF.md`](GRAVITY_HANDOFF.md) |
| Bahasa visual UI | [`VISUAL-LANGUAGE.md`](VISUAL-LANGUAGE.md) |

## Aturan status

- `STATE.md` hanya menyatakan sesuatu sebagai selesai jika ada bukti build, test, runtime, atau GUI yang disebutkan.
- `NEXT.md` adalah daftar pekerjaan/pembuktian yang belum selesai; isi di sana bukan fitur yang sudah tersedia.
- `WORKLOG.md` mencatat apa yang dikerjakan, file yang terdampak, dan validasi aktual.
- `DECISIONS.md` append-only untuk keputusan arsitektur, model, dependency, privasi, dan trade-off yang tidak obvious.
- `BUGS.md` menampung masalah yang masih terbuka atau belum direproduksi.
- `ERROR_SOLUTIONS.md` menampung root cause, solusi, bukti, dan status perbaikan. Jangan memindahkan bug terbuka ke sini tanpa bukti.

Gunakan status berikut secara konsisten:

| Status | Arti |
|---|---|
| `Selesai + terverifikasi` | Source, build/test, atau runtime yang relevan sudah dibuktikan. |
| `Source-wired` | Jalur kode sudah ada, tetapi bukti runtime/GUI/hardware belum lengkap. |
| `Pending` | Direncanakan, belum dikerjakan atau belum dibuktikan. |
| `Blocked` | Tidak bisa dilanjutkan karena blocker eksternal yang disebutkan jelas. |
| `Deferred` | Sengaja ditunda berdasarkan scope/keputusan, bukan terlupakan. |

## Riwayat dan artefak besar

- `audit-*`, `AUDIT-*`, `LOCKSTEP-*`, dan laporan campaign adalah arsip bukti; jangan dicampur dengan status aktif.
- Asset visual tetap di `assets/`.
- Output build, cache model, database lokal, dan log runtime bukan dokumentasi repo; simpan di lokasi runtime yang sudah ditentukan.
- Jika menambah dokumen baru, masukkan link-nya ke hub ini dan pilih satu sumber kebenaran. Jangan membuat salinan `STATE`, `NEXT`, atau arsitektur di folder lain.

## Titik mulai agent baru

1. Baca `AGENTS.md`.
2. Baca `STATE.md` bagian paling atas.
3. Baca `NEXT.md` bagian paling atas.
4. Baca `GRAVITY_HANDOFF.md` jika melanjutkan pekerjaan Windows MVP.
5. Setelah bekerja, update `WORKLOG.md`; sinkronkan `STATE`, `NEXT`, `DECISIONS`, atau `ERROR_SOLUTIONS` sesuai jenis perubahan.
