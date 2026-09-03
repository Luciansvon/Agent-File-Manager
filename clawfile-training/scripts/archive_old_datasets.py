# -*- coding: utf-8 -*-
"""
ClawFile Dataset Archiver (Workflow Pengarsipan Bersih)
======================================================
Tujuan:
Mendeteksi dataset atau berkas sementara yang sudah selesai dipakai / versi lama,
mengompresnya ke format .zip di folder arsip khusus (arsip_dataset/),
dan menjaga folder kerja tetap ringkas, bersih, serta tidak memperlambat sistem/OneDrive.
"""

import os
import sys
import zipfile
import time
import shutil

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID"
TRAIN_DIR = os.path.join(BASE_DIR, "clawfile-training")
DATA_VERSIONS_DIR = os.path.join(TRAIN_DIR, "data_versions")
DATASET_LATIHAN_DIR = os.path.join(BASE_DIR, "dataset_latihan")
ARCHIVE_DIR = os.path.join(TRAIN_DIR, "arsip_dataset")

os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_obsolete_datasets():
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    zip_name = f"arsip_dataset_lama_{timestamp}.zip"
    zip_path = os.path.join(ARCHIVE_DIR, zip_name)
    
    # Berkas yang ditargetkan untuk diarsipkan (versi lama yang sudah dilewati)
    targets_data_versions = [
        "dataset_train_v1.jsonl",
        "dataset_train_v2.jsonl",
        "dataset_v1_master.jsonl"
    ]
    
    archived_files = []
    
    print("=" * 65)
    print(">>> MEMULAI WORKFLOW PENGARSIPAN DATASET LAMA KE .ZIP")
    print(f"Target Arsip: {zip_path}")
    print("=" * 65)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Arsipkan versi lama di data_versions/
        for fname in targets_data_versions:
            fpath = os.path.join(DATA_VERSIONS_DIR, fname)
            if os.path.isfile(fpath):
                arcname = os.path.join("data_versions", fname)
                zf.write(fpath, arcname=arcname)
                archived_files.append((fpath, fname, os.path.getsize(fpath)))
                print(f"  [+] Mengemas ke ZIP: data_versions/{fname} ({os.path.getsize(fpath) / 1024:.1f} KB)")
                
        # 2. Arsipkan dataset lama di dataset_latihan/ (jika ada file versi 1 awal)
        old_ds = os.path.join(DATASET_LATIHAN_DIR, "dataset_clawfile.jsonl")
        if os.path.isfile(old_ds) and os.path.isfile(os.path.join(DATASET_LATIHAN_DIR, "dataset_clawfile_v2.jsonl")):
            arcname = os.path.join("dataset_latihan", "dataset_clawfile.jsonl")
            zf.write(old_ds, arcname=arcname)
            archived_files.append((old_ds, "dataset_clawfile.jsonl", os.path.getsize(old_ds)))
            print(f"  [+] Mengemas ke ZIP: dataset_latihan/dataset_clawfile.jsonl ({os.path.getsize(old_ds) / 1024:.1f} KB)")
            
    if not archived_files:
        print("  [!] Tidak ada berkas lama yang perlu diarsipkan. Folder sudah bersih!")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return
        
    zip_size = os.path.getsize(zip_path) / 1024
    print(f"\n>>> Berhasil membuat arsip .zip: {zip_name} (Ukuran: {zip_size:.1f} KB)")
    
    # Hapus file asli yang sudah masuk ke dalam zip agar menghemat ruang
    print("\n>>> Membersihkan berkas mentah lama dari folder aktif...")
    freed_bytes = 0
    for fpath, fname, fsize in archived_files:
        try:
            os.remove(fpath)
            freed_bytes += fsize
            print(f"  [-] Dihapus dari folder kerja: {fname}")
        except Exception as e:
            print(f"  [!] Gagal menghapus {fname}: {e}")
            
    print(f"\n>>> PENGARSIPAN SELESAI! Total ruang yang dihemat/dirapikan: {freed_bytes / 1024:.1f} KB")
    print(f"Folder arsip aman di: {ARCHIVE_DIR}")
    print("=" * 65)

if __name__ == "__main__":
    archive_obsolete_datasets()
