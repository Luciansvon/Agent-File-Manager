# -*- coding: utf-8 -*-
"""
Master Runner Loop Iteratif Mandiri ClawFile-Agent: run_iterative_loop.py
========================================================================
Mengotomatiskan rantai loop lengkap:
Dataset vN -> Train exp_N -> GGUF/Ollama -> Benchmark RedTeam & Sandbox ->
Analisis Failures -> Build Dataset vN+1 -> Repeat.

Penghentian Otomatis:
- Jika terdeteksi Destructive Loss > 0 (file terhapus/rusak), loop LANGSUNG BERHENTI.
- Setiap iterasi menghasilkan manifest, sha256, serta bukti mentah cases.jsonl.
"""

import os
import sys
import json
import time
import argparse
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

def parse_args():
    parser = argparse.ArgumentParser(description="Master Runner Loop Iteratif Mandiri ClawFile-Agent")
    parser.add_argument("--start_version", type=int, default=8, help="Versi dataset awal (default: 8 untuk v8)")
    parser.add_argument("--start_exp", type=int, default=9, help="Nomor eksperimen awal (default: 9 untuk exp_009)")
    parser.add_argument("--iterations", type=int, default=1, help="Jumlah iterasi loop (default: 1)")
    parser.add_argument("--max_steps", type=int, default=60, help="Jumlah langkah pelatihan per iterasi (default: 60)")
    return parser.parse_args()

def get_python_executable():
    unsloth_py = r"C:\Users\shint\.unsloth\studio\unsloth_studio\Scripts\python.exe"
    if os.path.isfile(unsloth_py):
        return unsloth_py
    return sys.executable

def run_step(cmd_list, allow_fail=False) -> int:
    py_exe = get_python_executable()
    if cmd_list and (cmd_list[0] == sys.executable or cmd_list[0] == "python"):
        cmd_list[0] = py_exe
    print(f"\n[LOOP RUNNER] Eksekusi: {' '.join(cmd_list)}")
    try:
        res = subprocess.run(cmd_list, cwd=BASE_DIR, check=not allow_fail)
        return res.returncode
    except subprocess.CalledProcessError as e:
        print(f"[LOOP RUNNER ERROR] Langkah gagal dengan exit code {e.returncode}")
        if not allow_fail:
            sys.exit(e.returncode)
        return e.returncode
    except Exception as ex:
        print(f"[LOOP RUNNER ERROR] Gagal menjalankan perintah: {ex}")
        if not allow_fail:
            sys.exit(1)
        return 1

def main():
    args = parse_args()
    current_version = args.start_version
    current_exp_num = args.start_exp
    total_iterations = args.iterations

    print("=" * 75)
    print(">>> MEMULAI WORKFLOW MASTER LOOP ITERATIF MANDIRI CLAWFILE-AGENT")
    print(f"Versi Dataset Awal : dataset_train_v{current_version}.jsonl")
    print(f"Eksperimen Awal    : exp_{current_exp_num:03d}")
    print(f"Target Iterasi     : {total_iterations} siklus")
    print(f"Max Steps / Exp    : {args.max_steps} steps")
    print("=" * 75)

    for i in range(total_iterations):
        exp_id = f"exp_{current_exp_num:03d}"
        dataset_path = os.path.join("data_versions", f"dataset_train_v{current_version}.jsonl")
        
        print("\n" + "#" * 75)
        print(f"  SIKLUS ITERASI MANDIRI {i+1} / {total_iterations}")
        print(f"  Eksperimen : {exp_id}")
        print(f"  Dataset    : {dataset_path}")
        print("#" * 75 + "\n")

        # 1. Pelatihan Model exp_N
        train_script = os.path.join(SCRIPTS_DIR, "train_next_exp.py")
        run_step([sys.executable, train_script, "--dataset", dataset_path, "--exp_id", exp_id, "--max_steps", str(args.max_steps)])

        # 2. Benchmark Red Team & Mock Sandbox
        bench_script = os.path.join(SCRIPTS_DIR, "run_benchmark.py")
        run_step([sys.executable, bench_script, "--exp_id", exp_id, "--model", "clawfile-agent:latest"])

        # 3. Analisis Kegagalan & Ekstraksi Hard Examples
        analyze_script = os.path.join(SCRIPTS_DIR, "analyze_failures.py")
        code = run_step([sys.executable, analyze_script, "--exp_id", exp_id], allow_fail=True)
        if code == 2:
            print("\n[BAHAYA MUTLAK] TERDETEKSI DESTRUCTIVE LOSS > 0! LOOP BERHENTI SEKETIKA.")
            break

        # 4. Generate Report
        report_dir = os.path.join("reports", f"{exp_id}_benchmark")
        report_script = os.path.join(SCRIPTS_DIR, "generate_report.py")
        if os.path.isdir(os.path.join(BASE_DIR, report_dir)):
            run_step([sys.executable, report_script, "--report-dir", os.path.join(BASE_DIR, report_dir)], allow_fail=True)

        # 5. Verify Metrics Independent
        verify_script = os.path.join(SCRIPTS_DIR, "verify_metrics.py")
        run_step([sys.executable, verify_script], allow_fail=True)

        # 6. Build Dataset vN+1
        next_version = current_version + 1
        next_dataset_path = os.path.join("data_versions", f"dataset_train_v{next_version}.jsonl")
        failures_path = os.path.join("hard_examples", f"{exp_id}_failures.jsonl")
        build_script = os.path.join(SCRIPTS_DIR, "build_next_dataset.py")

        run_step([
            sys.executable, build_script,
            "--prev_dataset", dataset_path,
            "--failures", failures_path,
            "--output", next_dataset_path
        ])

        # 7. Pembersihan Berkas GGUF/LoRA Eksperimen Lama (Menjaga Disk Tetap Hemat)
        clean_script = os.path.join(SCRIPTS_DIR, "clean_old_experiments.py")
        if os.path.isfile(clean_script):
            run_step([sys.executable, clean_script], allow_fail=True)

        print(f"\n[✓] SIKLUS {i+1} SELESAI! Dataset berikutnya tersimpan di {next_dataset_path}")
        
        current_version = next_version
        current_exp_num += 1

    print("\n" + "=" * 75)
    print(f">>> WORKFLOW MASTER LOOP ITERATIF MANDIRI SELESAI ({total_iterations} ITERASI TERLEWATI)!")
    print("=" * 75)

if __name__ == "__main__":
    main()
