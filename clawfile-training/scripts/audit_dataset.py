# -*- coding: utf-8 -*-
"""
Audit & Normalisasi Dataset Resmi ClawFile-Agent
Menghasilkan:
- clawfile-training/reports/dataset_audit.json
- clawfile-training/data_versions/dataset_v1_master.jsonl
"""

import os
import json
import hashlib
import re

SOURCES = [
    r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan\dataset_clawfile.jsonl",
    r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan\dataset_clawfile_v2.jsonl",
    r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan\dataset_percakapan_natural_reddit_threads.jsonl"
]

OUTPUT_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
MASTER_JSONL = os.path.join(OUTPUT_DIR, "data_versions", "dataset_v1_master.jsonl")
AUDIT_JSON = os.path.join(OUTPUT_DIR, "reports", "dataset_audit.json")

ILLEGAL_WIN_CHARS = re.compile(r'[\\/:*?"<>|]')

def classify_task(user_text, assistant_text):
    ut = user_text.lower()
    at = assistant_text.lower()
    
    if any(k in ut for k in ["nota", "kuitansi", "laporan", "formulir", "surat", "dokumen", "pdf", "invoice"]):
        return "DOCUMENT"
    elif any(k in ut for k in ["gambar", "foto", "sketsa", "warna", "kursi", "meja", "kayu", "visual"]):
        return "VISION"
    elif any(k in ut for k in ["nama file", "folder", "rapikan", "organisir", "sortir", "rename"]):
        return "FILE_MANAGEMENT"
    else:
        return "CONVERSATION"

def main():
    print(">>> MEMULAI AUDIT & NORMALISASI DATASET...")
    os.makedirs(os.path.join(OUTPUT_DIR, "data_versions"), exist_ok=True)
    os.makedirs(os.path.join(OUTPUT_DIR, "reports"), exist_ok=True)
    
    seen_hashes = set()
    master_samples = []
    
    audit_stats = {
        "total_raw_rows_scanned": 0,
        "unique_samples": 0,
        "duplicates_removed": 0,
        "corrupted_rows": 0,
        "categories": {
            "VISION": 0,
            "DOCUMENT": 0,
            "FILE_MANAGEMENT": 0,
            "CONVERSATION": 0
        },
        "quality_metrics": {
            "valid_json_rate": 1.0,
            "empty_responses": 0,
            "has_think_reasoning": 0,
            "windows_filename_clean": 0,
            "windows_filename_violations": 0
        }
    }
    
    for src in SOURCES:
        if not os.path.isfile(src):
            print(f"Warning: source file not found: {src}")
            continue
            
        with open(src, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                audit_stats["total_raw_rows_scanned"] += 1
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    msgs = item.get("messages", [])
                    raw_user_msg = next((m["content"] for m in msgs if m["role"] == "user"), "")
                    raw_asst_msg = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
                    
                    if isinstance(raw_user_msg, list):
                        user_msg = " ".join(c.get("text", "") for c in raw_user_msg if isinstance(c, dict) and c.get("type") == "text")
                    else:
                        user_msg = str(raw_user_msg)
                        
                    if isinstance(raw_asst_msg, list):
                        asst_msg = " ".join(c.get("text", "") for c in raw_asst_msg if isinstance(c, dict) and c.get("type") == "text")
                    else:
                        asst_msg = str(raw_asst_msg)
                    
                    if not user_msg or not asst_msg:
                        audit_stats["quality_metrics"]["empty_responses"] += 1
                        continue
                        
                    # Hash user content for deduplication
                    u_hash = hashlib.sha256(user_msg.encode("utf-8")).hexdigest()
                    if u_hash in seen_hashes:
                        audit_stats["duplicates_removed"] += 1
                        continue
                    seen_hashes.add(u_hash)
                    
                    # Task classification
                    task_cat = classify_task(user_msg, asst_msg)
                    audit_stats["categories"][task_cat] += 1
                    
                    # Quality validation
                    if "<think>" in asst_msg:
                        audit_stats["quality_metrics"]["has_think_reasoning"] += 1
                        
                    # Check filename safety
                    fn_match = re.search(r'`([^`]+\.[a-zA-Z0-9]+)`', asst_msg)
                    if fn_match:
                        fn = fn_match.group(1)
                        if ILLEGAL_WIN_CHARS.search(fn):
                            audit_stats["quality_metrics"]["windows_filename_violations"] += 1
                        else:
                            audit_stats["quality_metrics"]["windows_filename_clean"] += 1
                            
                    sample = {
                        "id": f"sample_{len(master_samples) + 1:04d}",
                        "task_category": task_cat,
                        "messages": msgs
                    }
                    master_samples.append(sample)
                    
                except Exception as e:
                    audit_stats["corrupted_rows"] += 1
                    print(f"Corrupted row in {src} line {line_no}: {e}")
                    
    audit_stats["unique_samples"] = len(master_samples)
    
    # Save master dataset
    with open(MASTER_JSONL, "w", encoding="utf-8") as f:
        for s in master_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            
    # Save audit report
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit_stats, f, indent=2)
        
    print("\n" + "=" * 60)
    print(">>> AUDIT SELESAI!")
    print(f"Total baris mentah di-scan: {audit_stats['total_raw_rows_scanned']}")
    print(f"Sampel unik berkualitas: {audit_stats['unique_samples']}")
    print(f"Duplikasi dibersihkan: {audit_stats['duplicates_removed']}")
    print("Distribusi Kategori:")
    for k, v in audit_stats["categories"].items():
        pct = (v / audit_stats["unique_samples"]) * 100 if audit_stats["unique_samples"] > 0 else 0
        print(f" - {k}: {v} sampel ({pct:.1f}%)")
    print(f"Dataset master disimpan ke: {MASTER_JSONL}")
    print(f"Laporan audit disimpan ke: {AUDIT_JSON}")
    print("=" * 60)

if __name__ == "__main__":
    main()
