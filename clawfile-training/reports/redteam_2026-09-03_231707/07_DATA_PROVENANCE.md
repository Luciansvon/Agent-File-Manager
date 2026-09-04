# Data Provenance & Isolasi Soal Ujian (Anti-Leakage Guarantee)
Dokumen ini membuktikan asal-usul data uji yang digunakan dalam Red Team Suite v2.

---

## 1. Jaminan Isolasi Mutlak (Immutable Benchmark Isolation)
- **Kontrak Keras Proyek:** `benchmarks/frozen_test_benchmark.jsonl` DILARANG KERAS digunakan untuk data latihan, data tuning, atau adversarial mining.
- Seluruh 24 kasus uji red team dibuat secara independen khusus untuk pengujian ketahanan keamanan dan tidak pernah dicampurkan ke dalam dataset latihan model (`dataset_train_v*.jsonl`).

---

## 2. Inventaris Kasus & SHA-256 Payload

| ID Kasus | Kategori | Subkategori | SHA-256 Payload | Berkas Artefak |
| :--- | :--- | :--- | :--- | :--- |
| IPI-001 | indirect_prompt_injection | pdf_content | `e433a26514f1b376...` | `05_evidence/artifacts/IPI-001_faktur_pembelian.pdf` |
