# -*- coding: utf-8 -*-
r"""
ClawFile Red Team Full Pipeline Runner (Fase C & F Master Orchestrator)
======================================================================
Menjalankan seluruh alur audit keamanan dalam satu perintah tunggal:
1. Menyiapkan dan memvalidasi Mock Filesystem Sandbox v2.
2. Mengeksekusi Adversarial Red Team Suite v2 (7 Kategori Serangan).
3. Meng-generate seluruh laporan mutakhir (00_EXECUTIVE_SUMMARY s/d 08_INTEGRITY_AUDIT).
4. Melakukan verifikasi independen (verify_metrics.py) dengan gerbang keluar 0 mismatch.

Penggunaan:
  python scripts/run_full_redteam_pipeline.py [--dry-run] [--model <nama>] [--seed <n>]
"""

import os
import sys
import time
import argparse
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

def run_step(cmd_list: list, step_name: str) -> bool:
    print("\n" + "=" * 80)
    print(f"[TAHAP EKSEKUSI] {step_name}")
    print(f"[Perintah] {' '.join(cmd_list)}")
    print("=" * 80)

    t0 = time.time()
    proc = subprocess.run(cmd_list, cwd=BASE_DIR)
    dur = time.time() - t0

    if proc.returncode == 0:
        print(f"\n[+] {step_name} SELESAI DENGAN SUKSES ({dur:.2f} detik)")
        return True
    else:
        print(f"\n[!] {step_name} GAGAL dengan kode keluar {proc.returncode} ({dur:.2f} detik)")
        return False

def main():
    parser = argparse.ArgumentParser(description="ClawFile Full Red Team Pipeline Runner")
    parser.add_argument("--dry-run", action="store_true", help="Jalankan dalam mode simulasi cepat")
    parser.add_argument("--model", type=str, default="clawfile-agent:latest", help="Model target Ollama")
    parser.add_argument("--seed", type=int, default=42, help="Seed deterministik")
    parser.add_argument("--report-dir", type=str, default=None, help="Custom output directory")
    args = parser.parse_args()

    python_bin = sys.executable
    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    report_dir = args.report_dir or os.path.join(BASE_DIR, "reports", f"redteam_{timestamp}")

    print("=" * 80)
    print("        CLAWFILE MASTER RED TEAM PIPELINE RUNNER (FASE C & F)")
    print("=" * 80)
    print(f"[*] Target Model : {args.model}")
    print(f"[*] Mode Dry-Run : {args.dry_run}")
    print(f"[*] Report Dir   : {report_dir}")
    print("=" * 80)

    # 1. Uji Validasi Mock Filesystem Sandbox v2
    cmd_sandbox = [python_bin, os.path.join(SCRIPTS_DIR, "test_mock_filesystem_sandbox_v2.py")]
    if not run_step(cmd_sandbox, "1. Validasi Integritas Sandbox v2"):
        sys.exit(1)

    # 2. Eksekusi Adversarial Red Team Suite v2
    cmd_suite = [
        python_bin, os.path.join(SCRIPTS_DIR, "adversarial_redteam_suite.py"),
        "--model", args.model,
        "--seed", str(args.seed),
        "--report-dir", report_dir
    ]
    if args.dry_run:
        cmd_suite.append("--dry-run")

    if not run_step(cmd_suite, "2. Eksekusi Adversarial Red Team Suite v2"):
        sys.exit(1)

    # 3. Generate Laporan Lengkap
    cmd_report = [
        python_bin, os.path.join(SCRIPTS_DIR, "generate_report.py"),
        "--report-dir", report_dir
    ]
    if not run_step(cmd_report, "3. Otomasi Pembuatan Laporan Red Team (Fase F)"):
        sys.exit(1)

    # 4. Verifikasi Metrik Independen (0 Mismatch Gate)
    cmd_verify = [
        python_bin, os.path.join(SCRIPTS_DIR, "verify_metrics.py"),
        "--report-dir", report_dir
    ]
    if not run_step(cmd_verify, "4. Verifikasi Independen & Audit Data Honesty"):
        sys.exit(1)

    print("\n" + "=" * 80)
    print(">>> SELURUH PIPELINE FASE C & F BERHASIL DISELESAIKAN DENGAN SEMPURNA!")
    print(f">>> Direktori Bukti & Laporan: {report_dir}")
    print("=" * 80)

if __name__ == "__main__":
    main()
