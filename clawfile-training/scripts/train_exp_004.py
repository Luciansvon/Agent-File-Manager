# -*- coding: utf-8 -*-
"""
Skrip Pelatihan Mandiri exp_004: Adaptive Continuous Training & Evaluation Loop
Target: Meningkatkan Skor Tolok Ukur ClawFile Eval Stack > 90%
- Memperkuat ketahanan AgentDojo (penolakan prompt injection & sterilisasi nama Windows)
- Menguasai eksekusi langsung (Direct Execution) tanpa alur toolcall berbelit-belit
- Menyelesaikan masalah penanganan duplikasi nama berkas secara sistematis (-2, -revisi)
- VRAM Budget: < 3.0 GB (RTX 3050 Laptop GPU)
- Steps: 60 steps
"""

import os
import sys
import gc
import json
import torch
import shutil
import subprocess

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
DATASET_PATH = os.path.join(BASE_DIR, "data_versions", "dataset_train_v4.jsonl")
EXP_DIR = os.path.join(BASE_DIR, "experiments", "exp_004")
LORA_OUTPUT_DIR = os.path.join(EXP_DIR, "lora_output")
GGUF_OUTPUT_DIR = os.path.join(EXP_DIR, "model_gguf")

os.makedirs(EXP_DIR, exist_ok=True)
os.makedirs(LORA_OUTPUT_DIR, exist_ok=True)
os.makedirs(GGUF_OUTPUT_DIR, exist_ok=True)

MAX_SEQ_LENGTH = 768
MAX_STEPS = 60
BATCH_SIZE = 1
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4

print("=" * 65)
print(">>> MEMULAI PELATIHAN EXP_004: ADAPTIVE TRAINING LOOP")
print("=" * 65)

# 1. Bersihkan VRAM
torch.cuda.empty_cache()
gc.collect()

# 2. Muat Base Model
model_name = "empero-ai/Qwen3.8-2B-Distill"
print(f"Memuat model dasar: {model_name} (4-bit)...")

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

# 3. Terapkan LoRA
print("Menerapkan LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# 4. Muat Dataset Train v4
print(f"Memuat data latih dari: {DATASET_PATH}...")
train_data = []
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            train_data.append(json.loads(line))

formatted_texts = []
for item in train_data:
    messages = item.get("messages", [])
    clean_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = " ".join(text_parts).strip()
        clean_messages.append({"role": role, "content": content})
        
    text = tokenizer.apply_chat_template(clean_messages, tokenize=False, add_generation_prompt=False)
    formatted_texts.append(text)

hf_dataset = Dataset.from_dict({"text": formatted_texts})
print(f"Total sampel latih v4: {len(formatted_texts)}")

# 5. Konfigurasi Training
training_args = TrainingArguments(
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    warmup_steps=5,
    max_steps=MAX_STEPS,
    learning_rate=LEARNING_RATE,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=10,
    optim="paged_adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="linear",
    seed=3407,
    output_dir=os.path.join(EXP_DIR, "checkpoints"),
    save_strategy="no",
    report_to="none"
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=1,
    packing=False,
    args=training_args,
    train_dataset=hf_dataset,
)

# 6. Jalankan Pelatihan
print(f"Mulai pelatihan {MAX_STEPS} langkah...")
train_result = trainer.train()

loss = train_result.training_loss
peak_vram = torch.cuda.max_memory_allocated() / (1024 ** 2)
print(">>> PELATIHAN EXP_004 SELESAI!")
print(f"Final Loss: {loss:.4f} | Peak VRAM: {peak_vram:.1f} MB (Batas Aman: 3072 MB)")

# 7. Simpan LoRA
print("Menyimpan bobot LoRA...")
model.save_pretrained(LORA_OUTPUT_DIR)
tokenizer.save_pretrained(LORA_OUTPUT_DIR)

# 8. Ekspor ke GGUF Q4_K_M
print("Menggabungkan bobot dan mengekspor ke GGUF (Q4_K_M)...")
model.save_pretrained_gguf(
    GGUF_OUTPUT_DIR,
    tokenizer,
    quantization_method="q4_k_m"
)
print(">>> EKSPOR GGUF EXP_004 SELESAI!")

# 9. Bersihkan Berkas Sementara GGUF yang Besar (Pembersihan Disk)
gguf_target_file = None
for f in os.listdir(GGUF_OUTPUT_DIR):
    fp = os.path.join(GGUF_OUTPUT_DIR, f)
    if (f.endswith(".safetensors") or "BF16.gguf" in f) and os.path.isfile(fp):
        try:
            os.remove(fp)
            print(f"Membersihkan berkas sementara: {f}")
        except:
            pass
    elif "q4_k_m" in f.lower() and f.endswith(".gguf"):
        gguf_target_file = fp

# 10. Daftarkan Otomatis ke Ollama
print("\n>>> Memperbarui model di Ollama: clawfile-agent:latest...")
if gguf_target_file and os.path.isfile(gguf_target_file):
    # Buat Modelfile untuk exp_004
    vision_lens = r"C:\Users\shint\Documents\FolderVisionAI-FileID\dataset_latihan\model_clawfile_agent_gguf_gguf\mmproj-Qwen3.8-2B-ClawFile-Agent.gguf"
    modelfile_path = os.path.join(EXP_DIR, "Modelfile")
    
    modelfile_content = f"""FROM "{gguf_target_file}"
FROM "{vision_lens}"
TEMPLATE \"\"\"{{{{- if .Messages }}}}
{{{{- if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{- end }}}}
{{{{- range $i, $_ := .Messages }}}}
{{{{- $last := eq (len (slice $.Messages $i)) 1 -}}}}
{{{{- if eq .Role "user" }}}}<|im_start|>user
{{{{ .Content }}}}<|im_end|>
{{{{ else if eq .Role "assistant" }}}}<|im_start|>assistant
{{{{ .Content }}}}{{{{ if not $last }}}}<|im_end|>
{{{{ end }}}}
{{{{ end }}}}
{{{{- if and (ne .Role "assistant") $last }}}}<|im_start|>assistant
{{{{ end }}}}
{{{{- end }}}}
{{{{- else }}}}
{{{{- if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
{{{{ end }}}}<|im_start|>assistant
{{{{ end }}}}{{{{ .Response }}}}{{{{ if .Response }}}}<|im_end|>{{{{ end }}}}\"\"\"
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.9
SYSTEM \"\"\"Kamu adalah ClawFile-Agent, asisten AI cerdas lokal pengelola dan perapi file untuk Bima.
- Jika Bima menyapa, mengajak ngobrol, curhat, atau bertanya tentang hal umum, desain furnitur, atau kegiatan harian, jawablah dengan ramah, santai, hangat, dan solutif seperti teman diskusi yang cerdas tanpa menyertakan format penamaan file.
- Jika Bima meminta menganalisis file, foto, dokumen, atau merapikan folder, lakukan penalaran teliti dalam blok <think>...</think>, lalu rumuskan usulan nama file yang spesifik, 3-5 label pencarian, dan rekomendasi folder yang rapi.
- Dilarang keras mengeksekusi path traversal, format disk, atau perintah destruktif sistem Windows.\"\"\"
"""
    with open(modelfile_path, "w", encoding="utf-8") as mf:
        mf.write(modelfile_content)
        
    try:
        cmd = ["ollama", "create", "clawfile-agent:latest", "-f", modelfile_path]
        subprocess.run(cmd, check=True)
        print(">>> Model clawfile-agent:latest BERHASIL DIPERBARUI DI OLLAMA DENGAN BOBOT EXP_004!")
    except Exception as e:
        print(f"[Peringatan] Gagal memperbarui Ollama secara langsung: {e}")

# 11. Simpan Metadata Pelatihan
metrics = {
    "experiment_id": "exp_004",
    "train_steps": MAX_STEPS,
    "final_loss": float(loss),
    "peak_vram_mb": float(peak_vram),
    "samples_trained": len(formatted_texts),
    "gguf_model": gguf_target_file
}
with open(os.path.join(EXP_DIR, "training_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print("METADATA EXP_004 BERHASIL DISIMPAN!")
print("=" * 65)
