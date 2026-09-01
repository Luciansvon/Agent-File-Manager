# Folder Vision project structure blueprint

Blueprint ini adalah peta kerja repo, bukan alasan untuk memindahkan source yang sudah memakai path canonical.

## Struktur canonical

```text
FolderVisionAI-FileID/
├── AGENTS.md                         aturan kerja aktif
├── README.md                         overview dan quickstart publik
├── CHANGELOG.md                      catatan release upstream/product
├── CONTRIBUTING.md                   kontribusi umum
├── SECURITY.md                       kebijakan keamanan root
├── platforms/
│   └── windows/                      app WinUI, Core, engine Rust, installer, tests
├── shared/
│   ├── docs/                         pusat dokumentasi aktif dan arsip bukti
│   │   ├── README.md                 documentation hub
│   │   ├── FOLDER_VISION_ARCHITECTURE.md  authority Windows terbaru
│   │   ├── ARCHITECTURE.md           kontrak lintas-platform FileID
│   │   ├── STATE.md                  kondisi terverifikasi, terbaru di atas
│   │   ├── NEXT.md                   pekerjaan dan acceptance gate
│   │   ├── WORKLOG.md                riwayat pekerjaan aktual
│   │   ├── DECISIONS.md              keputusan append-only
│   │   ├── BUGS.md                   bug terbuka/belum direproduksi
│   │   ├── ERROR_SOLUTIONS.md        root cause dan solusi terverifikasi
│   │   ├── TESTING.md / TEST.md      panduan dan checklist test
│   │   ├── RUNTIME.md                proses, startup, log, storage runtime
│   │   ├── SECURITY.md / PRIVACY.md  guard keamanan dan privacy boundary
│   │   ├── MODELS.md                 model, lisensi, hash, dan download policy
│   │   ├── SHIP.md                   release readiness
│   │   ├── GRAVITY_HANDOFF.md        handoff kerja Windows MVP
│   │   ├── assets/                   logo, icon, visual reference
│   │   └── audit-*/                 bukti audit historis, tidak dicampur status aktif
│   ├── ipc-schema/                   schema dan README IPC
│   ├── models/                       asset/manifest model yang memang source-controlled
│   └── security/                     material security yang memang source-controlled
└── generated/runtime data             tetap di luar repo atau di-ignore
```

## Konvensi file

| Jenis | Lokasi | Aturan |
|---|---|---|
| Aturan agent | `AGENTS.md` | Jangan duplikasi ke dokumen status. |
| Arsitektur | `shared/docs/*ARCHITECTURE*.md` | Satu authority per scope; Windows terbaru adalah `FOLDER_VISION_ARCHITECTURE.md`. |
| Worklog | `shared/docs/WORKLOG.md` | Kronologis, bukti aktual, terbaru di atas. |
| Error selesai | `shared/docs/ERROR_SOLUTIONS.md` | Hanya setelah root cause dan solusi punya bukti. |
| Bug terbuka | `shared/docs/BUGS.md` | Jangan disamarkan sebagai solusi. |
| Status | `shared/docs/STATE.md` | Apa yang benar-benar bekerja sekarang. |
| Rencana | `shared/docs/NEXT.md` | Apa yang belum dikerjakan/dibuktikan. |
| Keputusan | `shared/docs/DECISIONS.md` | Append-only, tulis alternatif dan alasan. |
| Handoff | `shared/docs/GRAVITY_HANDOFF.md` | Snapshot siap dilanjutkan agent lain. |
| Audit historis | `shared/docs/audit-*` atau `AUDIT-*` | Simpan sebagai evidence, jangan jadikan status aktif otomatis. |

## Yang sengaja tidak dilakukan

- Tidak membuat `docs/` kedua di root.
- Tidak memindahkan `shared/docs` ke lokasi lain karena banyak link dan tooling FileID mengandalkannya.
- Tidak mencampur database, model weights, log runtime, `bin/obj`, dan Rust `target` ke folder dokumentasi.
- Tidak menghapus audit lama atau source hanya demi tampilan folder yang lebih pendek.
- Tidak membuat salinan `STATE`, `NEXT`, atau arsitektur di CatatToko/Morrow; struktur mereka hanya dijadikan referensi pola.

## Definition of tidy

Repo dianggap rapi jika agent baru bisa:

1. menemukan authority arsitektur dalam satu klik dari `shared/docs/README.md`;
2. membedakan fakta terverifikasi (`STATE`/`WORKLOG`) dari rencana (`NEXT`) dan bug terbuka (`BUGS`);
3. menemukan root cause (`ERROR_SOLUTIONS`) tanpa membaca seluruh audit historis;
4. melanjutkan kerja dari `GRAVITY_HANDOFF.md` tanpa menebak status runtime;
5. tidak mengunduh, menghapus, atau memproses data library hanya karena membaca dokumentasi.
