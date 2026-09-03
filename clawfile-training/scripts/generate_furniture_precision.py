# -*- coding: utf-8 -*-
"""
Generator Data Latih Khusus Presisi Furnitur & Pengawetan Ekstensi Berkas
Mengatasi:
1. Perubahan ekstensi ilegal (.png jadi .jpeg) -> Wajib pertahankan ekstensi asli.
2. Kalimat ganda/berulang -> Buat jawaban padat dan cepat.
3. Terminologi furnitur profesional (Dipan, Nakas, Credenza, Meja Kopi, Kursi Lengan).
"""

import json
import os

OUTPUT_FILE = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training\hard_examples\furniture_precision_samples.jsonl"

samples = [
    {
        "id": "furn_001",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Tolong periksa gambar BED-NAT16.png ini. Jelaskan jenis furnitur, material kayu, fungsi, dan usulkan nama file yang rapi beserta foldernya."
            },
            {
                "role": "assistant",
                "content": "<think>\nGambar menampilkan dipan tempat tidur (bed frame) model king/queen dengan sandaran kepala empuk berlapis kain krem dan rangka kayu solid warna cokelat natural. Ekstensi file adalah .png, wajib dipertahankan.\n</think>\n\n**Ringkasan Visual:** Dipan tempat tidur kayu solid minimalis dengan sandaran empuk kain krem bertekstur halus.\n**Jenis Furnitur:** Dipan Tempat Tidur (Bed Frame).\n**Material & Warna:** Rangka kayu jati/mahoni cokelat natural dengan lapisan kain sandaran krem.\n**Usulan Nama File:** `dipan-tempat-tidur-sandaran-krem-kayu-natural.png`\n**Label Pencarian (5 Tag):** `furnitur-kamar`, `dipan-tempat-tidur`, `bed-frame`, `kayu-natural`, `desain-minimalis`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Pindahkan ke folder 03_render_furnitur untuk katalog produk kamar tidur."
            }
        ]
    },
    {
        "id": "furn_002",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Ini ada file COFFE TABLE-NAT 13.png. Tolong beri analisis visual dan nama file baru."
            },
            {
                "role": "assistant",
                "content": "<think>\nObjek adalah meja kopi (coffee table) kayu solid dengan empat kaki melengkung elegan dan rak bawah terbuka. Ekstensi asli adalah .png, wajib dipertahankan.\n</think>\n\n**Ringkasan Visual:** Meja kopi kayu solid berkaki melengkung dengan rak penyimpanan terbuka di bawah permukaan meja.\n**Jenis Furnitur:** Meja Kopi (Coffee Table).\n**Material & Warna:** Kayu jati cokelat tua dengan finishing doff/matte.\n**Usulan Nama File:** `meja-kopi-kaki-lengkung-rak-terbuka-jati.png`\n**Label Pencarian (5 Tag):** `meja-kopi`, `coffee-table`, `kayu-jati`, `ruang-tamu`, `finishing-doff`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Simpan ke folder 03_render_furnitur sebagai arsip desain meja."
            }
        ]
    },
    {
        "id": "furn_003",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Analisis file kursi terpilih.png untuk katalog arsip kantor."
            },
            {
                "role": "assistant",
                "content": "<think>\nKursi santai berlengan (armchair) modern dengan bantalan kain abu-abu dan rangka kayu solid finishing natural. Ekstensi asli .png tidak boleh diubah.\n</think>\n\n**Ringkasan Visual:** Kursi santai berlengan (armchair) dengan bantalan busa kain abu-abu terang dan rangka kayu jati kokoh.\n**Jenis Furnitur:** Kursi Santai Berlengan (Armchair).\n**Material & Warna:** Kayu jati warna cokelat hangat dan kain pelapis abu-abu cerah.\n**Usulan Nama File:** `kursi-santai-armchair-kain-abu-rangka-jati.png`\n**Label Pencarian (5 Tag):** `kursi-santai`, `armchair`, `furnitur-kayu`, `kain-abu-abu`, `desain-skandinavia`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Pindahkan ke folder 03_render_furnitur."
            }
        ]
    },
    {
        "id": "furn_004",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "File pijar-laci-kayu.png ini isinya apa? Rapikan namanya."
            },
            {
                "role": "assistant",
                "content": "<think>\nSideboard atau nakas kabinet serbaguna dengan laci kayu dan pintu penyimpanan. Ekstensi .png harus dipertahankan.\n</think>\n\n**Ringkasan Visual:** Kabinet serbaguna (sideboard/credenza) dengan laci tengah dan panel pintu kayu minimalis.\n**Jenis Furnitur:** Kabinet Bufet / Sideboard.\n**Material & Warna:** Kayu olahan solid dengan serat kayu cokelat madu alami.\n**Usulan Nama File:** `kabinet-sideboard-laci-kayu-cokelat-madu.png`\n**Label Pencarian (5 Tag):** `kabinet-kayu`, `sideboard`, `credenza`, `laci-kayu`, `penyimpanan-ruang-tamu`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Masukkan ke folder 03_render_furnitur."
            }
        ]
    },
    {
        "id": "furn_005",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Periksa berkas tabel-kayu-kaca-geometris.jpeg ini. Berikan usulan nama dan foldernya."
            },
            {
                "role": "assistant",
                "content": "<think>\nDetail sambungan konstruksi kayu (joinery) meja dengan sambungan mortise-tenon atau dovetail presisi. Ekstensi asli .jpeg harus dipertahankan.\n</think>\n\n**Ringkasan Visual:** Foto makro detail sambungan konstruksi kayu meja modern dengan perpaduan kayu muda dan gelap.\n**Jenis Furnitur:** Detail Konstruksi / Sambungan Kayu (Joinery Detail).\n**Material & Warna:** Kayu oak terang dan aksen walnut gelap dengan sambungan presisi.\n**Usulan Nama File:** `detail-sambungan-konstruksi-kaki-meja-presisi.jpeg`\n**Label Pencarian (5 Tag):** `detail-sambungan`, `konstruksi-kayu`, `joinery`, `meja-modern`, `kayu-oak`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Pindahkan ke folder 03_render_furnitur untuk dokumentasi teknik produksi."
            }
        ]
    },
    {
        "id": "furn_006",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Tolong cek foto render-kursi-dan-meja-proto.png ini, mau dibuat katalog."
            },
            {
                "role": "assistant",
                "content": "<think>\nSatu set meja makan atau meja kerja beserta kursi kayu prototipe. Ekstensi .png harus dipertahankan.\n</think>\n\n**Ringkasan Visual:** Render set furnitur meja kerja minimalis bersama kursi ergonomis berdesain modern.\n**Jenis Furnitur:** Set Meja dan Kursi Prototipe.\n**Material & Warna:** Kayu sungkai warna cerah dengan finishing doff halus.\n**Usulan Nama File:** `set-render-prototipe-meja-dan-kursi-sungkai.png`\n**Label Pencarian (5 Tag):** `set-furnitur`, `meja-kerja`, `kursi-prototipe`, `kayu-sungkai`, `render-3d`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Simpan ke folder 03_render_furnitur sebagai referensi set produk."
            }
        ]
    },
    {
        "id": "furn_007",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Ini berkas lemari-mulfung-render.png tolong diorganisir."
            },
            {
                "role": "assistant",
                "content": "<think>\nLemari multifungsi berukuran tinggi dengan sekat rak buku, gantungan pakaian, dan laci bawah. Ekstensi .png wajib dipertahankan.\n</think>\n\n**Ringkasan Visual:** Lemari kabinet multifungsi dengan kombinasi pintu tertutup, rak display terbuka, dan laci bawah.\n**Jenis Furnitur:** Lemari Multifungsi (Multipurpose Wardrobe).\n**Material & Warna:** Kayu solid finishing cokelat natural dengan pegangan logam hitam.\n**Usulan Nama File:** `lemari-multifungsi-rak-terbuka-laci-bawah.png`\n**Label Pencarian (5 Tag):** `lemari-pakaian`, `lemari-multifungsi`, `rak-display`, `penyimpanan-kamar`, `furnitur-modern`\n**Rekomendasi Folder:** `03_render_furnitur`\n**Tindakan Sistem:** Pindahkan ke folder 03_render_furnitur."
            }
        ]
    },
    {
        "id": "furn_008",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Rapikan nama file mockup polo tampak belakang kerah.png."
            },
            {
                "role": "assistant",
                "content": "<think>\nMockup pakaian kaos polo sudut pandang belakang dengan fokus pada kerah dan jahitan. Ekstensi .png harus dipertahankan.\n</think>\n\n**Ringkasan Visual:** Mockup produk kaos polo dilihat dari sudut belakang dengan detail kerah dan jahitan punggung.\n**Jenis Produk:** Mockup Kaos Polo.\n**Warna & Detail:** Warna dasar kain dengan garis aksen pada bagian kerah.\n**Usulan Nama File:** `mockup-kaos-polo-tampak-belakang-detail-kerah.png`\n**Label Pencarian (5 Tag):** `mockup-produk`, `kaos-polo`, `tampak-belakang`, `detail-kerah`, `desain-fashion`\n**Rekomendasi Folder:** `04_mockup_produk`\n**Tindakan Sistem:** Simpan ke folder 04_mockup_produk untuk arsip merchandise."
            }
        ]
    },
    {
        "id": "furn_009",
        "task_category": "VISION",
        "messages": [
            {
                "role": "user",
                "content": "Tolong cek logo pijar.jpg ini buat arsip branding."
            },
            {
                "role": "assistant",
                "content": "<think>\nLogo perusahaan PT Pijar Sukma dengan simbol grafis dan tipografi merek. Ekstensi .jpg wajib dipertahankan.\n</think>\n\n**Ringkasan Visual:** Logo resmi PT Pijar Sukma menampilkan simbol grafis modern dengan tipografi teks perusahaan.\n**Jenis Aset:** Identitas Merek / Logo Perusahaan.\n**Warna:** Kombinasi warna korporat resmi dengan latar bersih.\n**Usulan Nama File:** `logo-resmi-perusahaan-pt-pijar-sukma.jpg`\n**Label Pencarian (5 Tag):** `logo-perusahaan`, `identitas-merek`, `pijar-sukma`, `branding`, `aset-vektor`\n**Rekomendasi Folder:** `02_desain_logo`\n**Tindakan Sistem:** Pindahkan ke folder 02_desain_logo untuk aset identitas visual."
            }
        ]
    },
    {
        "id": "furn_010",
        "task_category": "CONVERSATION",
        "messages": [
            {
                "role": "user",
                "content": "Bagusan kayu jati atau kayu sungkai ya buat bikin nakas kamar tidur minimalis?"
            },
            {
                "role": "assistant",
                "content": "<think>\nPertanyaan diskusi santai desain furnitur antara jati vs sungkai. Tidak perlu format sortir file.\n</think>\n\nPilihan yang menarik, Bima! Keduanya punya karakter kuat tergantung konsep kamar tidur yang ingin kamu capai:\n\n1. **Kayu Jati:**\n   - **Karakter:** Seratnya sangat tegas, warnanya cokelat keemasan atau hangat, dan sangat kokoh serta tahan rayap alami.\n   - **Kesan:** Memberikan nuansa mewah, hangat, abadi (*timeless*), dan cocok untuk gaya modern-natural atau klasik elegan.\n\n2. **Kayu Sungkai:**\n   - **Karakter:** Warnanya jauh lebih terang (putih kekuningan) dengan alur serat yang lurus dan rapi. Mudah dibentuk dan menyerap warna finishing terang dengan baik.\n   - **Kesan:** Sangat cocok untuk konsep **Skandinavia (*Japandi*)** atau minimalis modern yang butuh suasana ruangan terang, lapang, dan bersih.\n\n**Rekomendasi:** Kalau kamu mengincar gaya kamar minimalis ala Jepang/Nordik yang terang, **Sungkai** jadi pilihan favorit. Tapi kalau ingin kesan mewah dan awet puluhan tahun, **Jati** tetap juaranya!"
            }
        ]
    }
]

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Berhasil menulis {len(samples)} sampel furnitur & preservasi ekstensi ke: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
