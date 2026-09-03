# ClawFile-Agent Autonomous ML Training & Evaluation Harness

Direktori kerja resmi untuk eksperimen, evaluasi tolok ukur (*benchmarking*), dan pelatihan model lokal **ClawFile-Agent** (arsitektur multimodal Qwen 3.5 2B).

## Aturan Keamanan Sistem (ML Safety Contract)
1. **Batas Sumber Daya (GPU RTX 3050):** VRAM maksimal 3.0 GB (dari total 4.0 GB), wajib kuantisasi 4-bit (`load_in_4bit=True`), optimasi Paged AdamW 8-bit, gradient accumulation, dan batch size 1.
2. **Batas Langkah (Steps):** Maksimal 60–100 langkah per eksperimen.
3. **Pemisahan Ujian (Frozen Benchmark):** Berkas di `benchmarks/frozen_test_benchmark.jsonl` tidak boleh digunakan untuk latihan.
4. **Validasi Format Output:** Wajib menyertakan penalaran `<think>`, usulan nama berkas tanpa karakter terlarang Windows, dan 3–5 label pencarian.
5. **Persetujuan Pengguna:** Setiap perubahan arsitektur atau pipeline data wajib melalui persetujuan Bima.

## Struktur Direktori
- `data/`: Berkas data mentah dan master gabungan.
- `data_versions/`: Berkas dataset per versi (`dataset_v1.jsonl`, `dataset_train_v1.jsonl`).
- `benchmarks/`: Soal ujian beku untuk evaluasi jujur (`frozen_test_benchmark.jsonl`).
- `hard_examples/`: Sampel yang gagal diidentifikasi untuk perbaikan bertarget.
- `experiments/`: Arsip per eksperimen (`exp_001`, `exp_002`, dst).
- `checkpoints/`: Model hasil latihan terbaik (`best/`) dan pemulihan (`recovery/`).
- `reports/`: Laporan hasil evaluasi dan perbandingan metrik.
- `scripts/`: Skrip Python otomatis untuk inspeksi, audit, ekstraksi, evaluasi, dan orkestrasi.
- `configs/`: Konfigurasi hyperparameter tiap eksperimen.
