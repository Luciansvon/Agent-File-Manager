# LAPORAN DATA PROVENANCE & KURASI INTERNET (FASE A)
**Proyek:** FolderVision AI (ClawFile-Agent)  
**Status Kontrak:** `TERPENUHI [PASSED]`  
**Tanggal Audit:** 2026-09-03  
**Auditor:** ClawFile Senior ML Security & Evaluation Auditor  

---

## 1. Ringkasan Eksekutif

Akuisisi data eksternal dari repositori internet publik berlisensi permisif telah diselesaikan dengan sukses. Seluruh berkas sampel nyata telah diunduh, disanitasi dari potensi pelanggaran privasi (PII) dan identitas wajah, dideduplikasi melalui *perceptual hash* (*p-hash*), serta dicatat secara transparan ke dalam manifes provenance.

| Parameter Evaluasi | Target Kontrak | Hasil Aktual | Status |
| :--- | :--- | :--- | :--- |
| **Sumber Lisensi Permisif** | 100% Permisif (CC0/CC-BY/MIT/Apache/PD) | **100.00%** (23/23 berkas) | `PASSED` |
| **Rasio Data Internet pada Dataset v9** | Minimal ≥ 40.0% | **53.49%** (92/172 sampel) | `PASSED` |
| **Pembersihan Wajah & PII (Scrubbing)** | 100% Bersih / Clean | **100.00%** (23/23 berkas) | `PASSED` |
| **Deduplikasi Perceptual Hash (p-hash)** | Hamming Distance < 4 disaring | **Aktif & Berfungsi** (Duplikat disaring) | `PASSED` |
| **Isolasi Brankas Ujian (Frozen Bench)** | 0% Kebocoran (Data Leakage = 0) | **0 Kebocoran** (35 soal tetap beku murni) | `PASSED` |
| **Rantai Fallback Downloader** | Transparan 6 Tingkat | `curl` -> `wget` -> `aria2c` -> `gallery-dl` -> `yt-dlp` -> `requests` | `PASSED` |

---

## 2. Distribusi Sumber & Platform

Total berkas fisik yang berhasil dikurasi: **23 berkas** (13.87 MB).

### A. Rincian per Platform
- **Wikimedia Commons**: 20 berkas (87.0%)
- **Open Document Standards & Test Repositories**: 3 berkas (13.0%)

### B. Rincian per Kategori Berkas
- **furnitur** (Sketsa & Rancangan Perabot Kayu (MET / Public)): 5 berkas (21.7%)
- **teknik** (Gambar Teknik & Blueprint Mesin Paten): 4 berkas (17.4%)
- **faktur** (Faktur & Kuitansi Finansial Resmi): 3 berkas (13.0%)
- **poster** (Poster Iklan & Materi Promosi Vintage CC0): 3 berkas (13.0%)
- **logo** (Emblem & Lambang Simbol Resmi): 3 berkas (13.0%)
- **dokumen_pdf** (Dokumen Standar Digital PDF (W3C / MIT)): 3 berkas (13.0%)
- **formulir** (Formulir Aplikasi & Sertifikat Resmi): 2 berkas (8.7%)

---

## 3. Audit Lisensi & Kepatuhan Legalitas

Semua data yang diakuisisi mematuhi kebijakan lisensi terbuka (*permissive license*) tanpa batasan komersial (*commercial-friendly*) dan tanpa royalti:

- **Public domain**: 12 berkas (52.2%)
- **CC0**: 6 berkas (26.1%)
- **MIT**: 2 berkas (8.7%)
- **CC BY-SA 2.0**: 1 berkas (4.3%)
- **CC BY-SA 4.0**: 1 berkas (4.3%)
- **W3C Document License (Permissive)**: 1 berkas (4.3%)

- **Total Rasio Lisensi Permisif:** **100.00%**
- **Status Pelanggaran Lisensi Non-Komersial / Eksklusif:** **0 (NIL)**

---

## 4. Sanitasi Privasi, Deteksi Wajah, & PII Scrubbing

Untuk mencegah kebocoran informasi pribadi dan privasi pihak ketiga pada data latihan model:
1. **Deteksi Wajah (Face Detection):** Dijalankan menggunakan detektor *OpenCV Haar Cascade* (`haarcascade_frontalface_default.xml`). Setiap kontur wajah manusia otomatis dibaurkan (*Gaussian Blur*) sebelum masuk tahap ekstraksi fitur.
2. **Scrubbing EXIF & Metadata Dokumen:**
   - Berkas citra (JPG, PNG) dibersihkan dari seluruh penanda EXIF personal seperti koordinat GPS kamera, nama pemilik perangkat, dan stempel waktu kamera.
   - Berkas PDF dibersihkan dari metadata penyusun (*Author*, *Producer*, *Creator*).
3. **Status PII:** Seluruh 23 berkas tercatat dengan status `"pii_scrub": "clean"` pada manifes provenance.

---

## 5. Komposisi Dataset Latih `dataset_train_v9_internet.jsonl`

Dataset latih v9 dibangun dari kombinasi kurikulum sampel lokal inti yang bersih dengan sampel hasil kurasi data internet ber-provenance:

- **Total Sampel Latih:** **172 sampel**
- **Sampel Internet Provenance:** **92 sampel** (**53.49%**)
- **Sampel Inti Lokal (v8 non-benchmark):** **80 sampel** (**46.51%**)

### Distribusi Kategori Tugas dalam Dataset v9:
- **VISION**: 72 sampel (41.9%)
- **REAL_TASK**: 23 sampel (13.4%)
- **SECURITY**: 23 sampel (13.4%)
- **GENERAL_LLM**: 23 sampel (13.4%)
- **FILE_MANAGEMENT**: 17 sampel (9.9%)
- **DOCUMENT**: 14 sampel (8.1%)

### Isolasi Brankas Ujian Beku (*Frozen Test Benchmark*):
- Status Kebocoran Data (*Data Leakage*): **PASSED (0 Kebocoran / 100% Bersih)**
- Sebanyak 35 soal tolok ukur di `benchmarks/frozen_test_benchmark.jsonl` tetap 100% steril dan tidak tersentuh proses pelatihan.

---

## 6. Audit Integritas Kriptografis (SHA-256 Checksums)

Seluruh berkas keluaran Fase A diverifikasi dengan *hash* SHA-256 untuk menjamin integritas data (*non-repudiation*):

```
File: configs/sources.yaml
SHA-256: a3101b550b478259c5a89d6aa2d0683ed5262c9c7ce702909781452299fe2fba

File: data/internet/manifest.jsonl
SHA-256: 3f6f9569557c618e282ed3cb474d6bfa702dcd144b8e217c890ed26c20ec84cc

File: data_versions/dataset_train_v9_internet.jsonl
SHA-256: 87630def91c775edd15c7b293680a7f37d6ede62376f8cd409609d13bba7ec97
```

---
*Laporan ini dihasilkan secara otomatis oleh `scripts/generate_data_report.py` pada repositori `clawfile-training`.*
