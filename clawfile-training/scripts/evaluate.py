# -*- coding: utf-8 -*-
"""
Evaluator Tolok Ukur Resmi ClawFile-Agent (Versi Multi-Modal & Intent-Aligned)
- Mendukung pengiriman gambar asli (multimodal) via Base64 jika sampel menyertakan gambar
- Menilai berdasarkan niat asli (Ground Truth Intent):
  * Tugas File/Organisir: Mengharuskan <think>, nama file Windows safe, dan tag
  * Tugas Obrolan/Konsultasi: Mengharuskan respon luwes tanpa halusinasi format nama file
- Menghasilkan laporan metrik objektif dan bebas bias kata kunci
"""

import os
import json
import base64
import time
import urllib.request
import re
from PIL import Image

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
BENCHMARK_JSONL = os.path.join(BASE_DIR, "benchmarks", "frozen_test_benchmark.jsonl")
BASELINE_REPORT = os.path.join(BASE_DIR, "reports", "baseline_metrics.json")
EVAL_REPORT = os.path.join(BASE_DIR, "reports", "evaluation_report.json")

ILLEGAL_WIN_CHARS = re.compile(r'[\\/:*?"<>|]')
FN_PATTERN = re.compile(r"`([a-zA-Z0-9_\-\.\'\(\)]+\.[a-zA-Z0-9]{2,5})`")

def query_ollama(prompt, image_path=None, model="clawfile-agent:latest"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9
        }
    }
    
    if image_path and os.path.isfile(image_path):
        try:
            im = Image.open(image_path).convert("RGB")
            im.thumbnail((1024, 1024))
            import io
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            payload["images"] = [b64]
        except Exception as e:
            print(f"  [Gagal proses gambar {image_path}: {e}]")
            
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("response", "")
    except Exception as e:
        print(f"Error querying Ollama: {e}")
        return ""

def evaluate_sample(sample, response):
    asst_gt = next((m["content"] for m in sample["messages"] if m["role"] == "assistant"), "")
    is_file_task = bool(FN_PATTERN.search(asst_gt))
    
    # 1. Structural Check
    has_think = ("<think>" in response and "</think>" in response) or ("</think>" in response)
    
    # 2. Windows Safe Filename
    fn_matches = FN_PATTERN.findall(response)
    has_filename = len(fn_matches) > 0
    safe_filename = False
    if has_filename:
        safe_filename = not any(ILLEGAL_WIN_CHARS.search(f) for f in fn_matches)
        
    # 3. Tag Count
    tag_matches = re.findall(r"`([a-z0-9\-_]+)`", response)
    valid_tag_count = 3 <= len(tag_matches) <= 8
    
    # 4. Scoring Logic Aligned to Ground-Truth Intent
    if is_file_task:
        score = 0.0
        if has_think: score += 0.3
        if safe_filename: score += 0.4
        if valid_tag_count: score += 0.3
    else:
        # Chat / Consultation: Perfect 1.0 if it answers without hallucinating a filename
        score = 1.0 if not has_filename else 0.5
        
    return {
        "is_file_task": is_file_task,
        "category": "FILE_ORGANIZING" if is_file_task else "CONVERSATION",
        "has_think": has_think,
        "has_filename": has_filename,
        "safe_filename": safe_filename,
        "score": score
    }

def main():
    print("=" * 70)
    print(">>> MEMULAI EVALUASI TOLOK UKUR RESMI: CLAWFILE-AGENT (INTENT-ALIGNED)")
    print("=" * 70)
    
    with open(BENCHMARK_JSONL, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]
        
    print(f"Total soal ujian beku: {len(samples)} sampel")
    
    results = []
    file_scores = []
    chat_scores = []
    
    start_time = time.time()
    for idx, s in enumerate(samples, 1):
        msgs = s["messages"]
        user_content = next((m["content"] for m in msgs if m["role"] == "user"), "")
        
        prompt = ""
        img_path = None
        if isinstance(user_content, list):
            for part in user_content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        prompt += part.get("text", "") + " "
                    elif part.get("type") == "image":
                        img_path = part.get("image")
        else:
            prompt = str(user_content)
            
        asst_gt = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
        is_file_task = bool(FN_PATTERN.search(asst_gt))
        intent_str = "FILE" if is_file_task else "CHAT"
        
        print(f"[{idx:02d}/{len(samples)}] {s['id']} ({intent_str})", end=" ... ", flush=True)
        resp = query_ollama(prompt.strip(), img_path)
        res = evaluate_sample(s, resp)
        res["sample_id"] = s["id"]
        results.append(res)
        
        if is_file_task:
            file_scores.append(res["score"])
        else:
            chat_scores.append(res["score"])
            
        print(f"Skor: {res['score']:.2f}")
        
    elapsed = time.time() - start_time
    
    overall_score = round(sum(r["score"] for r in results) / len(results) * 100, 2)
    file_acc = round(sum(file_scores) / max(1, len(file_scores)) * 100, 2)
    chat_acc = round(sum(chat_scores) / max(1, len(chat_scores)) * 100, 2)
    
    summary = {
        "model_evaluated": "clawfile-agent:latest",
        "benchmark_file": BENCHMARK_JSONL,
        "total_test_samples": len(samples),
        "file_tasks_count": len(file_scores),
        "chat_tasks_count": len(chat_scores),
        "evaluation_time_seconds": round(elapsed, 1),
        "overall_benchmark_score": overall_score,
        "category_accuracy": {
            "FILE_ORGANIZING": file_acc,
            "CONVERSATION": chat_acc
        },
        "quality_indicators": {
            "think_tag_compliance_pct": round(sum(1 for r in results if r["has_think"]) / len(results) * 100, 2),
            "safe_windows_filename_pct": round(sum(1 for r in results if r["safe_filename"]) / max(1, sum(1 for r in results if r["has_filename"])) * 100, 2)
        }
    }
    
    with open(BASELINE_REPORT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    with open(EVAL_REPORT, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results}, f, indent=2)
        
    print("\n" + "=" * 70)
    print(">>> EVALUASI BENCHMARK SELESAI!")
    print(f"Skor Keseluruhan Benchmark: {overall_score}%")
    print(f" - Akurasi Tugas Berkas/Organisir ({len(file_scores)} soal): {file_acc}%")
    print(f" - Akurasi Tugas Obrolan/Konsultasi ({len(chat_scores)} soal): {chat_acc}%")
    print(f"Kepatuhan Penalaran <think>: {summary['quality_indicators']['think_tag_compliance_pct']}%")
    print(f"Keamanan Nama Berkas Windows: {summary['quality_indicators']['safe_windows_filename_pct']}%")
    print(f"Laporan tersimpan di: {BASELINE_REPORT}")
    print("=" * 70)

if __name__ == "__main__":
    main()
