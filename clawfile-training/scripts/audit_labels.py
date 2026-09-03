# -*- coding: utf-8 -*-
"""
Audit Label & Niat Asli (Ground Truth Intent) Benchmark Beku
"""

import json
import re
import os

BENCH_PATH = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training\benchmarks\frozen_test_benchmark.jsonl"

def main():
    with open(BENCH_PATH, "r", encoding="utf-8") as f:
        bench = [json.loads(l) for l in f if l.strip()]

    fn_pattern = re.compile(r"`([a-zA-Z0-9_\-\.\'\(\)]+\.[a-zA-Z0-9]{2,5})`")

    file_tasks = []
    chat_tasks = []

    for s in bench:
        asst = next((m["content"] for m in s["messages"] if m["role"] == "assistant"), "")
        matches = fn_pattern.findall(asst)
        if matches:
            file_tasks.append((s["id"], s.get("task_category"), matches[0]))
        else:
            chat_tasks.append((s["id"], s.get("task_category"), asst[:60].replace("\n", " ")))

    print(f"TOTAL BENCHMARK: {len(bench)} sampel")
    print(f"1. TUGAS FILE / ORGANISIR (Mengharapkan usulan nama file): {len(file_tasks)} sampel")
    for sid, cat, fn in file_tasks:
        print(f"   [{sid}] (Label: {cat}) -> Target: `{fn}`")

    print(f"\n2. TUGAS OBROLAN / KONSULTASI (DILARANG mengeluarkan format file): {len(chat_tasks)} sampel")
    for sid, cat, snip in chat_tasks:
        print(f"   [{sid}] (Label: {cat}) -> Target: \"{snip}...\"")

if __name__ == "__main__":
    main()
