# -*- coding: utf-8 -*-
"""
Simulasi Pengujian Berjenjang (Mudah -> Sedang -> Sulit) untuk Semua Lini
Model: clawfile-agent:latest
Lini Pengujian:
1. Furnitur & Desain Industri
2. Mockup Produk & Fashion
3. Grafis & Branding / Iklan
4. Dokumen Laporan & Foto Nyata
"""

import os
import json
import base64
import time
import urllib.request
import re

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan"
REPORT_PATH = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training\reports\hierarchical_test_report.json"

TEST_MATRIX = [
    # --- LINI 1: FURNITUR & DESAIN INDUSTRI ---
    {
        "line": "Furnitur & Desain",
        "level": "Mudah",
        "file": os.path.join(BASE_DIR, "03_render_furnitur", "kursi-panjang-front'(3).png"),
        "desc": "Kursi panjang (bench/sofa) sudut pandang depan berlatar bersih"
    },
    {
        "line": "Furnitur & Desain",
        "level": "Sedang",
        "file": os.path.join(BASE_DIR, "03_render_furnitur", "render-kursi-dan-meja-proto.png"),
        "desc": "Set kombinasi meja kerja dan kursi prototipe kayu"
    },
    {
        "line": "Furnitur & Desain",
        "level": "Sulit",
        "file": os.path.join(BASE_DIR, "03_render_furnitur", "tabel-kayu-kaca-geometris.jpeg"),
        "desc": "Detail makro struktur sambungan kayu presisi (joinery)"
    },

    # --- LINI 2: MOCKUP & FASHION ---
    {
        "line": "Mockup & Produk",
        "level": "Mudah",
        "file": os.path.join(BASE_DIR, "04_mockup_produk", "tampak depan polo.png"),
        "desc": "Kaos polo tampak depan sudut lurus"
    },
    {
        "line": "Mockup & Produk",
        "level": "Sedang",
        "file": os.path.join(BASE_DIR, "04_mockup_produk", "project kemeja ajis depan.png"),
        "desc": "Kemeja formal dengan saku dan detail kancing"
    },
    {
        "line": "Mockup & Produk",
        "level": "Sulit",
        "file": os.path.join(BASE_DIR, "04_mockup_produk", "polo tampak belakang kerah.png"),
        "desc": "Detail lipatan kerah dan jahitan punggung belakang"
    },

    # --- LINI 3: GRAFIS & BRANDING ---
    {
        "line": "Grafis & Branding",
        "level": "Mudah",
        "file": os.path.join(BASE_DIR, "02_desain_logo", "logo pijar.jpg"),
        "desc": "Logo korporat PT Pijar Sukma"
    },
    {
        "line": "Grafis & Branding",
        "level": "Sedang",
        "file": os.path.join(BASE_DIR, "01_poster_iklan", "extrajoss-energy-drink.jpeg"),
        "desc": "Poster iklan produk minuman dengan tipografi tebal"
    },
    {
        "line": "Grafis & Branding",
        "level": "Sulit",
        "file": os.path.join(BASE_DIR, "01_poster_iklan", "hari-kemerdekaan-indonesia.png"),
        "desc": "Poster ilustrasi kompleks hari kemerdekaan dengan banyak elemen"
    },

    # --- LINI 4: DOKUMEN & FOTO NYATA ---
    {
        "line": "Dokumen & Nyata",
        "level": "Mudah",
        "file": os.path.join(BASE_DIR, "06_dokumen_laporan", "1.jpeg"),
        "desc": "Pindaian halaman dokumen laporan"
    },
    {
        "line": "Dokumen & Nyata",
        "level": "Sedang",
        "file": os.path.join(BASE_DIR, "05_foto_dokumentasi", "hutan-bambu.jpeg"),
        "desc": "Foto pemandangan alam nyata rumpun bambu"
    },
    {
        "line": "Dokumen & Nyata",
        "level": "Sulit",
        "file": os.path.join(BASE_DIR, "05_foto_dokumentasi", "unduhan-dari-aplikasi-fileidengine-exe.png"),
        "desc": "Tangkapan layar antarmuka aplikasi teknis padat teks"
    }
]

ILLEGAL_WIN_CHARS = re.compile(r'[\\/:*?"<>|]')

def run_test():
    print("=" * 70)
    print(">>> MEMULAI SIMULASI PENGUJIAN BERJENJANG (MUDAH -> SULIT)")
    print("=" * 70)
    
    results = []
    
    for idx, item in enumerate(TEST_MATRIX, 1):
        fp = item["file"]
        fn = os.path.basename(fp)
        orig_ext = os.path.splitext(fn)[1].lower()
        
        print(f"\n[{idx}/12] Lini: {item['line']} | Tingkat: {item['level']} | Berkas: {fn}")
        
        if not os.path.isfile(fp):
            print(f"  [SKIP] Berkas tidak ditemukan: {fp}")
            continue
            
        with open(fp, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            
        prompt = f"Analisis berkas {fn} ini ({item['desc']}). Jelaskan objek/konten visualnya, usulkan nama file yang rapi dan sesuai ekstensinya, berikan 5 label pencarian, dan folder tujuan."
        
        payload = {
            "model": "clawfile-agent:latest",
            "prompt": prompt,
            "images": [b64],
            "stream": False
        }
        
        t0 = time.time()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                dur = time.time() - t0
                raw = json.loads(res.read().decode("utf-8"))
                resp = raw.get("response", "")
                p_eval = raw.get("prompt_eval_duration", 0) / 1e9
                g_eval = raw.get("eval_duration", 0) / 1e9
                
                # Cek Preservasi Ekstensi
                fn_matches = re.findall(r'`([^`]+\.[a-zA-Z0-9]+)`', resp)
                ext_preserved = False
                safe_win_name = False
                suggested_name = fn_matches[0] if fn_matches else "none"
                
                if fn_matches:
                    for f_name in fn_matches:
                        s_ext = os.path.splitext(f_name)[1].lower()
                        if s_ext == orig_ext or (orig_ext in ['.jpg', '.jpeg'] and s_ext in ['.jpg', '.jpeg']):
                            ext_preserved = True
                        if not ILLEGAL_WIN_CHARS.search(f_name):
                            safe_win_name = True
                            
                has_think = "<think>" in resp or "</think>" in resp
                
                test_res = {
                    "index": idx,
                    "line": item["line"],
                    "level": item["level"],
                    "filename": fn,
                    "original_extension": orig_ext,
                    "suggested_filename": suggested_name,
                    "extension_preserved": ext_preserved,
                    "safe_windows_filename": safe_win_name,
                    "has_think": has_think,
                    "time_total_s": round(dur, 2),
                    "time_image_read_s": round(p_eval, 2),
                    "time_generation_s": round(g_eval, 2),
                    "response_snippet": resp[:250].replace("\n", " ") + "..."
                }
                results.append(test_res)
                
                status_icon = "PASS" if ext_preserved and safe_win_name else "WARN"
                print(f"  Status: [{status_icon}] | Baca Foto: {p_eval:.2f}s | Usulan: {suggested_name}")
                
        except Exception as e:
            print(f"  [ERROR] {e}")
            
    # Simpan Laporan
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    summary = {
        "total_tests": len(results),
        "extension_preservation_rate": f"{sum(1 for r in results if r['extension_preserved'])/max(1, len(results))*100:.1f}%",
        "safe_windows_filename_rate": f"{sum(1 for r in results if r['safe_windows_filename'])/max(1, len(results))*100:.1f}%",
        "avg_image_read_time_s": round(sum(r["time_image_read_s"] for r in results) / max(1, len(results)), 2),
        "results": results
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print("\n" + "=" * 70)
    print(">>> SIMULASI PENGUJIAN BERJENJANG SELESAI!")
    print(f"Total Diuji: {len(results)} berkas")
    print(f"Tingkat Keberhasilan Ekstensi: {summary['extension_preservation_rate']}")
    print(f"Nama File Aman Windows: {summary['safe_windows_filename_rate']}")
    print(f"Rata-rata Waktu Baca Gambar: {summary['avg_image_read_time_s']} detik")
    print(f"Laporan lengkap tersimpan di: {REPORT_PATH}")
    print("=" * 70)

if __name__ == "__main__":
    run_test()
