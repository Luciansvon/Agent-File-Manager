# -*- coding: utf-8 -*-
"""
Skrip Pembersih Model Lama (exp_001 s/d exp_014)
==============================================
Menghapus berkas .gguf dan lora_output dari eksperimen lama yang sudah tidak terpakai
agar ruang penyimpanan disk laptop kembali lega.

Catatan Keamanan:
- Base model ('empero-ai/Qwen3.8-2B-Distill') TIDAK DIHAPUS.
- Eksperimen terbaru ('exp_015') TIDAK DIHAPUS.
- Log training_metrics.json dan training_log.jsonl TETAP DIPERTANAKAN untuk riwayat audit.
"""

import os
import shutil

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
EXP_BASE = os.path.join(BASE_DIR, "experiments")

freed_bytes = 0
deleted_files = 0

for i in range(1, 15):
    exp_name = f"exp_{i:03d}"
    exp_dir = os.path.join(EXP_BASE, exp_name)
    if not os.path.isdir(exp_dir):
        continue

    # Walk and remove .gguf and .safetensors
    for root, dirs, files in os.walk(exp_dir, topdown=False):
        for f in files:
            if f.endswith(".gguf") or f.endswith(".safetensors") or f.endswith(".bin"):
                fpath = os.path.join(root, f)
                try:
                    size = os.path.getsize(fpath)
                    os.remove(fpath)
                    freed_bytes += size
                    deleted_files += 1
                    print(f"[Cleaned] {exp_name}/{f} ({round(size / (1024*1024), 1)} MB)")
                except Exception as e:
                    print(f"[Warning] Gagal menghapus {fpath}: {e}")

        # Remove lora_output directory if empty or contains left-over checkpoint folders
        for d in dirs:
            if d == "lora_output" or d.startswith("checkpoint"):
                dpath = os.path.join(root, d)
                try:
                    shutil.rmtree(dpath, ignore_errors=True)
                    print(f"[Cleaned Dir] {exp_name}/{d}")
                except Exception:
                    pass

freed_gb = round(freed_bytes / (1024 * 1024 * 1024), 2)
print("=" * 60)
print(f">>> PEMBERSIHAN SELESAI!")
print(f"Total Berkas Dihapus : {deleted_files} berkas")
print(f"Ruang Disk Dibebaskan: {freed_gb} GB")
print("=" * 60)
