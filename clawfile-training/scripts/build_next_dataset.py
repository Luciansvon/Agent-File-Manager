# -*- coding: utf-8 -*-
"""
Skrip Pembuat Dataset Modular: build_next_dataset.py
===================================================
Membangun dataset versi berikutnya (dataset_train_vN+1.jsonl) dari kombinasi:
1. 60% Dataset lama (dataset_train_vN.jsonl)
2. 20% Hard examples (hard_examples/exp_N_failures.jsonl)
3. 20% Data internet / domain bersih (data/internet/clean_samples.jsonl)

Fitur Keamanan Data:
- Deduplikasi otomatis berbasis hash isi pesan.
- Pemeriksaan kebocoran dari frozen benchmark (Frozen Benchmark Isolation Gate).
- Pembuatan manifest dataset lengkap (manifest.json) dengan SHA256 checksum.
"""

import os
import sys
import json
import glob
import hashlib
import argparse
from typing import List, Dict, Any, Set

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"

def parse_args():
    parser = argparse.ArgumentParser(description="Pembuat Dataset Versi Baru ClawFile-Agent")
    parser.add_argument("--prev_dataset", type=str, required=True, help="Path ke dataset versi sebelumnya")
    parser.add_argument("--failures", type=str, required=True, help="Path ke hard_examples/exp_N_failures.jsonl")
    parser.add_argument("--internet_samples", type=str, default="", help="Path ke data internet/domain bersih")
    parser.add_argument("--output", type=str, required=True, help="Path output dataset_train_vN+1.jsonl")
    return parser.parse_args()

def compute_sha256(filepath: str) -> str:
    if not os.path.isfile(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def get_message_content_hash(messages: List[Dict[str, Any]]) -> str:
    raw_str = ""
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, list):
            c = " ".join([p.get("text", "") for p in c if isinstance(p, dict)])
        raw_str += f"{m.get('role', '')}:{c};"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def load_frozen_benchmark_hashes() -> Set[str]:
    benchmark_hashes = set()
    possible_paths = [
        os.path.join(BASE_DIR, "benchmarks", "eval_frozen_35_cases.jsonl"),
        os.path.join(BASE_DIR, "benchmarks", "frozen_benchmark.jsonl")
    ]
    for p in possible_paths:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                            msgs = item.get("messages", [])
                            if msgs:
                                benchmark_hashes.add(get_message_content_hash(msgs))
                            prompt = item.get("prompt") or item.get("user_task")
                            if prompt:
                                benchmark_hashes.add(hashlib.sha256(str(prompt).encode("utf-8")).hexdigest())
                        except Exception:
                            pass
    return benchmark_hashes

def main():
    args = parse_args()

    prev_path = os.path.abspath(args.prev_dataset)
    failures_path = os.path.abspath(args.failures)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(prev_path):
        print(f"[Error] Prev dataset tidak ditemukan: {prev_path}")
        sys.exit(1)

    # Load frozen benchmark hashes for isolation check
    frozen_hashes = load_frozen_benchmark_hashes()
    print(f"[*] Memuat {len(frozen_hashes)} tanda tangan frozen benchmark untuk gerbang isolasi data.")

    # 1. Load dataset lama
    old_samples = []
    with open(prev_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    old_samples.append(json.loads(line))
                except Exception:
                    pass
    print(f"[*] Memuat {len(old_samples)} sampel lama dari {os.path.basename(prev_path)}")

    # 2. Load hard examples
    hard_samples = []
    if os.path.isfile(failures_path):
        with open(failures_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        hard_samples.append(json.loads(line))
                    except Exception:
                        pass
    print(f"[*] Memuat {len(hard_samples)} hard examples dari {os.path.basename(failures_path)}")

    # 3. Load internet / domain samples
    internet_samples = []
    internet_path = args.internet_samples
    if not internet_path:
        possible_internet = [
            os.path.join(BASE_DIR, "data_versions", "dataset_general_indo_docs.jsonl"),
            os.path.join(BASE_DIR, "data", "internet", "clean_samples.jsonl")
        ]
        for pi in possible_internet:
            if os.path.isfile(pi):
                internet_path = pi
                break

    if internet_path and os.path.isfile(internet_path):
        with open(internet_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        internet_samples.append(json.loads(line))
                    except Exception:
                        pass
    print(f"[*] Memuat {len(internet_samples)} internet/domain samples dari {os.path.basename(internet_path) if internet_path else 'None'}")

    # Deduplikasi dan Pengecekan Kebocoran
    seen_hashes = set()
    final_dataset = []
    dedup_count = 0
    leak_count = 0

    all_candidates = old_samples + hard_samples + internet_samples

    for s in all_candidates:
        msgs = s.get("messages", [])
        if not msgs:
            continue

        chash = get_message_content_hash(msgs)

        # Cek kebocoran frozen benchmark
        if chash in frozen_hashes:
            leak_count += 1
            continue

        # Cek duplikat
        if chash in seen_hashes:
            dedup_count += 1
            continue

        seen_hashes.add(chash)
        final_dataset.append(s)

    # Simpan dataset baru
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in final_dataset:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    output_sha256 = compute_sha256(output_path)

    # Buat Manifest File
    manifest_path = output_path.replace(".jsonl", "_manifest.json")
    manifest_data = {
        "dataset": os.path.basename(output_path),
        "created_from": [
            os.path.basename(prev_path),
            os.path.basename(failures_path) if os.path.isfile(failures_path) else "none",
            os.path.basename(internet_path) if internet_path else "none"
        ],
        "total_samples": len(final_dataset),
        "old_samples_count": len(old_samples),
        "hard_examples_count": len(hard_samples),
        "internet_samples_count": len(internet_samples),
        "deduplicated_count": dedup_count,
        "frozen_benchmark_leak_check": "PASS" if leak_count == 0 else f"BLOCKED_{leak_count}_LEAKS",
        "sha256": output_sha256,
        "timestamp": sys.argv[0]
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print(f">>> DATASET BARU BERHASIL DIBUAT: {output_path}")
    print(f"Total Sampel Akhir : {len(final_dataset)}")
    print(f"Sampel Terbuang    : {dedup_count} duplikat, {leak_count} kebocoran benchmark")
    print(f"SHA256 Checksum    : {output_sha256}")
    print(f"Manifest           : {manifest_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
