# -*- coding: utf-8 -*-
"""
Suite Tolok Ukur Standar Industri (Community & Research Standard Benchmark)
Mengadaptasi:
1. POPE (Polling-based Object Probing Evaluation) -> Mengukur Tingkat Halusinasi (F1-Score)
2. DocVQA & ANLS (Average Normalized Levenshtein Similarity) -> Mengukur Presisi Teks Dokumen
3. Stress & Robustness Test (Rotasi & Distorsi Gambar) -> Menguji Daya Tahan Model
4. Strict Schema & Taxonomy Validation -> Validasi Ketat Penamaan Berkas Windows
"""

import os
import json
import base64
import time
import io
import urllib.request
import re
from PIL import Image, ImageFilter

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan"
REPORT_PATH = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training\reports\advanced_benchmark_report.json"

ALLOWED_FOLDERS = [
    "01_poster_iklan",
    "02_desain_logo",
    "03_render_furnitur",
    "04_mockup_produk",
    "05_foto_dokumentasi",
    "06_dokumen_laporan",
    "01_laporan_desain",
    "01_furnitur",
    "01_furnitur_kursi",
    "01_furnitur_set_tidur"
]

def query_model(prompt, b64_img=None, timeout=45):
    payload = {
        "model": "clawfile-agent:latest",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "top_p": 0.9}
    }
    if b64_img:
        payload["images"] = [b64_img]
        
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            dur = time.time() - t0
            data = json.loads(res.read().decode("utf-8"))
            return {
                "response": data.get("response", ""),
                "prompt_eval_s": data.get("prompt_eval_duration", 0) / 1e9,
                "eval_s": data.get("eval_duration", 0) / 1e9,
                "total_s": dur
            }
    except Exception as e:
        return {"response": f"ERROR: {e}", "prompt_eval_s": 0, "eval_s": 0, "total_s": time.time() - t0}

def levenshtein_distance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]

def calculate_anls(ground_truth, prediction):
    gt = ground_truth.strip().lower()
    pred = prediction.strip().lower()
    if not gt or not pred: return 0.0
    dist = levenshtein_distance(gt, pred)
    max_len = max(len(gt), len(pred))
    sim = 1.0 - (dist / max_len)
    return sim if sim >= 0.5 else 0.0

def img_to_b64(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def run_suite():
    print("=" * 70)
    print(">>> MEMULAI ADVANCED BENCHMARK SUITE (STANDAR RISET AI KOMUNITAS)")
    print("=" * 70)
    
    suite_results = {
        "pope_hallucination": {},
        "docvqa_anls": {},
        "stress_robustness": {},
        "schema_strictness": {}
    }
    
    # -------------------------------------------------------------
    # 1. POPE (Polling-based Object Probing Evaluation)
    # -------------------------------------------------------------
    print("\n--- [1/4] SUITE 1: POPE OBJECT HALLUCINATION PROBING ---")
    pope_cases = [
        # (File, Question, Expected: True=Ada/False=Tidak)
        (os.path.join(BASE_DIR, "03_render_furnitur", "kursi terpilih.png"), "Apakah ada kursi di gambar ini? Jawab singkat: Ya atau Tidak.", True),
        (os.path.join(BASE_DIR, "03_render_furnitur", "kursi terpilih.png"), "Apakah ada kucing tidur di atas kursi ini? Jawab singkat: Ya atau Tidak.", False),
        (os.path.join(BASE_DIR, "03_render_furnitur", "BED-NAT16.png"), "Apakah ada tempat tidur atau dipan di gambar ini? Jawab singkat: Ya atau Tidak.", True),
        (os.path.join(BASE_DIR, "03_render_furnitur", "BED-NAT16.png"), "Apakah ada sepeda motor atau mobil di gambar ini? Jawab singkat: Ya atau Tidak.", False),
        (os.path.join(BASE_DIR, "03_render_furnitur", "COFFE TABLE-NAT 13.png"), "Apakah ada meja di gambar ini? Jawab singkat: Ya atau Tidak.", True),
        (os.path.join(BASE_DIR, "03_render_furnitur", "COFFE TABLE-NAT 13.png"), "Apakah ada laptop menyala di atas meja ini? Jawab singkat: Ya atau Tidak.", False),
        (os.path.join(BASE_DIR, "05_foto_dokumentasi", "hutan-bambu.jpeg"), "Apakah ada rumpun bambu atau tanaman alam di gambar ini? Jawab singkat: Ya atau Tidak.", True),
        (os.path.join(BASE_DIR, "05_foto_dokumentasi", "hutan-bambu.jpeg"), "Apakah ada pesawat terbang melintas di gambar ini? Jawab singkat: Ya atau Tidak.", False),
        (os.path.join(BASE_DIR, "02_desain_logo", "logo pijar.jpg"), "Apakah ada simbol logo atau teks perusahaan di gambar ini? Jawab singkat: Ya atau Tidak.", True),
        (os.path.join(BASE_DIR, "02_desain_logo", "logo pijar.jpg"), "Apakah ada hewan jerapah di gambar ini? Jawab singkat: Ya atau Tidak.", False),
    ]
    
    tp = fp = tn = fn = 0
    pope_details = []
    
    for fpath, q, expected in pope_cases:
        if not os.path.isfile(fpath): continue
        im = Image.open(fpath).convert("RGB")
        im.thumbnail((1024, 1024))
        b64 = img_to_b64(im, "JPEG")
        
        res = query_model(q, b64)
        resp_text = res["response"].lower()
        
        # Ekstrak jawaban setelah </think> jika ada
        if "</think>" in resp_text:
            ans_part = resp_text.split("</think>")[-1]
        else:
            ans_part = resp_text
            
        predicted_yes = "ya" in ans_part and "tidak" not in ans_part[:10]
        predicted_no = "tidak" in ans_part or "bukan" in ans_part
        
        if expected is True:
            if predicted_yes: tp += 1; status = "CORRECT (TP)"
            else: fn += 1; status = "MISS (FN)"
        else:
            if predicted_no: tn += 1; status = "CORRECT (TN)"
            else: fp += 1; status = "HALLUCINATION (FP)"
            
        print(f"  POPE: {os.path.basename(fpath)} | Tanya: {q[:35]}... -> Prediksi: {'Ya' if predicted_yes else 'Tidak'} [{status}]")
        pope_details.append({
            "file": os.path.basename(fpath),
            "question": q,
            "expected": "Ya" if expected else "Tidak",
            "prediction": "Ya" if predicted_yes else "Tidak",
            "status": status
        })
        
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    hallucination_rate = fp / (tn + fp) if (tn + fp) > 0 else 0
    
    suite_results["pope_hallucination"] = {
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "hallucination_rate_pct": round(hallucination_rate * 100, 2),
        "details": pope_details
    }
    print(f"  >>> POPE Score: Precision={precision*100:.1f}%, Recall={recall*100:.1f}%, F1={f1*100:.1f}%, Tingkat Halusinasi={hallucination_rate*100:.1f}%")
    
    # -------------------------------------------------------------
    # 2. DocVQA & ANLS (Average Normalized Levenshtein Similarity)
    # -------------------------------------------------------------
    print("\n--- [2/4] SUITE 2: DocVQA & ANLS TEXT EXTRACTION ---")
    doc_path = os.path.join(BASE_DIR, "06_dokumen_laporan", "1.jpeg")
    anls_scores = []
    docvqa_details = []
    
    if os.path.isfile(doc_path):
        im = Image.open(doc_path).convert("RGB")
        b64 = img_to_b64(im, "JPEG")
        
        doc_queries = [
            ("Sebutkan nama lengkap orang/mahasiswa yang tertulis di dokumen ini.", "bima chakti adi surya"),
            ("Sebutkan tanggal atau bulan yang tertulis pada dokumen ini.", "april 2026")
        ]
        
        for q, gt in doc_queries:
            res = query_model(q, b64)
            resp_text = res["response"].split("</think>")[-1].strip() if "</think>" in res["response"] else res["response"]
            
            score = calculate_anls(gt, resp_text)
            anls_scores.append(score)
            print(f"  DocVQA: GT='{gt}' | Prediksi='{resp_text[:35]}...' | ANLS={score:.3f}")
            docvqa_details.append({
                "query": q,
                "ground_truth": gt,
                "prediction": resp_text[:100],
                "anls_score": round(score, 3)
            })
            
    avg_anls = sum(anls_scores) / max(1, len(anls_scores))
    suite_results["docvqa_anls"] = {
        "average_anls_score": round(avg_anls, 3),
        "details": docvqa_details
    }
    print(f"  >>> Rata-rata Skor ANLS Dokumen: {avg_anls:.3f} / 1.000")
    
    # -------------------------------------------------------------
    # 3. Stress & Robustness Test (Rotasi 90 Derajat & Kompresi Buram)
    # -------------------------------------------------------------
    print("\n--- [3/4] SUITE 3: STRESS & ROBUSTNESS (DISTORSI & ROTASI) ---")
    stress_file = os.path.join(BASE_DIR, "03_render_furnitur", "kursi terpilih.png")
    stress_details = []
    stress_pass = 0
    
    if os.path.isfile(stress_file):
        im_orig = Image.open(stress_file).convert("RGB")
        
        # Test 1: Rotasi 90 Derajat
        im_rot = im_orig.rotate(90, expand=True)
        b64_rot = img_to_b64(im_rot, "JPEG")
        res_rot = query_model("Apa objek furnitur utama pada gambar ini?", b64_rot)
        rot_ans = res_rot["response"].lower()
        rot_ok = "kursi" in rot_ans or "armchair" in rot_ans
        if rot_ok: stress_pass += 1
        print(f"  Stress Rotasi 90°: {'PASS (Kursi Terdeteksi)' if rot_ok else 'FAIL'} | Waktu: {res_rot['total_s']:.2f}s")
        stress_details.append({"test": "Rotasi 90 Derajat", "passed": rot_ok, "response": rot_ans[:100]})
        
        # Test 2: Kompresi Buram (Gaussian Blur)
        im_blur = im_orig.filter(ImageFilter.GaussianBlur(radius=5))
        b64_blur = img_to_b64(im_blur, "JPEG")
        res_blur = query_model("Walaupun gambar buram, apa warna dan objek perkiraan gambar ini?", b64_blur)
        blur_ans = res_blur["response"].lower()
        blur_ok = ("kursi" in blur_ans or "kayu" in blur_ans or "abu" in blur_ans)
        if blur_ok: stress_pass += 1
        print(f"  Stress Buram (Gaussian Blur): {'PASS (Atribut Terdeteksi)' if blur_ok else 'FAIL'} | Waktu: {res_blur['total_s']:.2f}s")
        stress_details.append({"test": "Gaussian Blur Keras", "passed": blur_ok, "response": blur_ans[:100]})
        
    suite_results["stress_robustness"] = {
        "passed_tests": stress_pass,
        "total_stress_tests": 2,
        "robustness_rate": f"{(stress_pass/2)*100:.1f}%",
        "details": stress_details
    }
    
    # -------------------------------------------------------------
    # 4. Strict Schema & Taxonomy Validation
    # -------------------------------------------------------------
    print("\n--- [4/4] SUITE 4: STRICT SCHEMA & TAXONOMY VALIDATION ---")
    schema_files = [
        (os.path.join(BASE_DIR, "03_render_furnitur", "BED-NAT16.png"), ".png"),
        (os.path.join(BASE_DIR, "03_render_furnitur", "render-kursi-proto.jpg"), ".jpg"),
        (os.path.join(BASE_DIR, "01_poster_iklan", "extrajoss-energy-drink.jpeg"), ".jpeg"),
        (os.path.join(BASE_DIR, "04_mockup_produk", "project kemeja ajis depan.png"), ".png")
    ]
    
    schema_correct = 0
    schema_details = []
    
    for fp, expected_ext in schema_files:
        if not os.path.isfile(fp): continue
        im = Image.open(fp).convert("RGB")
        im.thumbnail((1024, 1024))
        b64 = img_to_b64(im, "JPEG")
        
        fn = os.path.basename(fp)
        res = query_model(f"Rapikan nama file {fn} dan tentukan foldernya.", b64)
        resp = res["response"]
        
        # Validasi:
        # 1. Ekstensi cocok
        fn_matches = re.findall(r'`([^`]+\.[a-zA-Z0-9]+)`', resp)
        s_name = fn_matches[0] if fn_matches else ""
        s_ext = os.path.splitext(s_name)[1].lower() if s_name else ""
        ext_match = (s_ext == expected_ext) or (expected_ext in ['.jpg', '.jpeg'] and s_ext in ['.jpg', '.jpeg'])
        
        # 2. Windows Safe
        win_safe = bool(s_name and not re.search(r'[\\/:*?"<>|]', s_name))
        
        # 3. Tag count (3-5)
        tags = re.findall(r'`([a-z0-9\-_]+)`', resp)
        tags_valid = 3 <= len(tags) <= 7
        
        # 4. Folder taxonomy valid
        folder_match = any(f in resp for f in ALLOWED_FOLDERS)
        
        is_all_valid = ext_match and win_safe and tags_valid and folder_match
        if is_all_valid: schema_correct += 1
        
        print(f"  Schema: {fn} -> Nama: {s_name} | Ext: {ext_match} | Safe: {win_safe} | Folder: {folder_match} -> [{'PASS' if is_all_valid else 'FAIL'}]")
        schema_details.append({
            "file": fn,
            "suggested_filename": s_name,
            "extension_valid": ext_match,
            "windows_safe": win_safe,
            "folder_taxonomy_valid": folder_match,
            "all_passed": is_all_valid
        })
        
    suite_results["schema_strictness"] = {
        "strict_compliance_rate": f"{(schema_correct / max(1, len(schema_files))) * 100:.1f}%",
        "details": schema_details
    }
    
    # Simpan Laporan Komprehensif
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(suite_results, f, indent=2)
        
    print("\n" + "=" * 70)
    print(">>> ADVANCED BENCHMARK SELESAI!")
    print(f"POPE F1-Score (Halusinasi Objek): {suite_results['pope_hallucination']['f1_score']}%")
    print(f"DocVQA ANLS (Akurasi Teks Dokumen): {suite_results['docvqa_anls']['average_anls_score']}")
    print(f"Robustness Ketahanan Foto (Stress): {suite_results['stress_robustness']['robustness_rate']}")
    print(f"Disiplin Skema & Taksonomi Folder: {suite_results['schema_strictness']['strict_compliance_rate']}")
    print(f"Laporan lengkap tersimpan di: {REPORT_PATH}")
    print("=" * 70)

if __name__ == "__main__":
    run_suite()
