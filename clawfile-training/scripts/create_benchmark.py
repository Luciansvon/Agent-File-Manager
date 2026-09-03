# -*- coding: utf-8 -*-
"""
Pemisahan Soal Ujian Terkunci (Frozen Benchmark) vs Data Latih
Menghasilkan:
- clawfile-training/benchmarks/frozen_test_benchmark.jsonl (20% beku)
- clawfile-training/data_versions/dataset_train_v1.jsonl (80% latih)
"""

import os
import json
import random

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
MASTER_JSONL = os.path.join(BASE_DIR, "data_versions", "dataset_v1_master.jsonl")
BENCHMARK_JSONL = os.path.join(BASE_DIR, "benchmarks", "frozen_test_benchmark.jsonl")
TRAIN_JSONL = os.path.join(BASE_DIR, "data_versions", "dataset_train_v1.jsonl")

def main():
    print(">>> MEMULAI PEMBENTUKAN FROZEN BENCHMARK (SOAL UJIAN BEKU)...")
    random.seed(42) # Deterministic seed
    
    by_category = {
        "VISION": [],
        "DOCUMENT": [],
        "FILE_MANAGEMENT": [],
        "CONVERSATION": []
    }
    
    with open(MASTER_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            cat = item.get("task_category", "CONVERSATION")
            by_category[cat].append(item)
            
    benchmark_samples = []
    train_samples = []
    
    # 20% stratified split
    for cat, items in by_category.items():
        random.shuffle(items)
        n_bench = max(1, int(len(items) * 0.20))
        bench_part = items[:n_bench]
        train_part = items[n_bench:]
        
        benchmark_samples.extend(bench_part)
        train_samples.extend(train_part)
        print(f" - Kategori {cat}: {len(items)} total -> {len(bench_part)} Ujian Beku, {len(train_part)} Bahan Latih")
        
    # Verifikasi Ketiadaan Kebocoran Data (Zero-Leakage Verification)
    bench_ids = {s["id"] for s in benchmark_samples}
    train_ids = {s["id"] for s in train_samples}
    leakage = bench_ids.intersection(train_ids)
    
    if leakage:
        raise ValueError(f"CRITICAL ERROR: Data leakage detected! Overlapping IDs: {leakage}")
        
    print(f"\n>>> VERIFIKASI LEAKAGE: 100% AMAN! (0 overlap antara Ujian dan Latih)")
    
    os.makedirs(os.path.dirname(BENCHMARK_JSONL), exist_ok=True)
    with open(BENCHMARK_JSONL, "w", encoding="utf-8") as f:
        for s in benchmark_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            
    with open(TRAIN_JSONL, "w", encoding="utf-8") as f:
        for s in train_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            
    print(f"Soal Ujian Beku tersimpan: {BENCHMARK_JSONL} ({len(benchmark_samples)} sampel)")
    print(f"Bahan Latih v1 tersimpan: {TRAIN_JSONL} ({len(train_samples)} sampel)")
    print("=" * 60)

if __name__ == "__main__":
    main()
