# -*- coding: utf-8 -*-
"""
Skrip Pelatihan Mandiri exp_003: Intent & Conversational Alignment
Target: Mencapai Skor Tolok Ukur > 95% (Mendekati 100%)
- Membedakan dengan tegas kapan harus merapikan file vs kapan harus berdiskusi teori/konsultasi tanpa format file
- VRAM Budget: < 3.0 GB (RTX 3050 Laptop)
- Steps: 65 steps
"""

import os
import sys
import gc
import json
import torch

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
DATASET_PATH = os.path.join(BASE_DIR, "data_versions", "dataset_train_v3.jsonl")
EXP_DIR = os.path.join(BASE_DIR, "experiments", "exp_003")
LORA_OUTPUT_DIR = os.path.join(EXP_DIR, "lora_output")
GGUF_OUTPUT_DIR = os.path.join(EXP_DIR, "model_gguf")

os.makedirs(EXP_DIR, exist_ok=True)
os.makedirs(LORA_OUTPUT_DIR, exist_ok=True)

MAX_SEQ_LENGTH = 768
MAX_STEPS = 65
BATCH_SIZE = 1
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4

print("=" * 65)
print(">>> MEMULAI PELATIHAN EXP_003: INTENT & CONVERSATION ALIGNMENT")
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

# 4. Muat Dataset Train v3
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
print(f"Total sampel latih v3: {len(formatted_texts)}")

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
print(f">>> PELATIHAN EXP_003 SELESAI!")
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
print(">>> EKSPOR GGUF EXP_003 SELESAI!")

# 9. Hapus Berkas Sementara GGUF yang Besar (Pembersihan Disk)
for f in os.listdir(GGUF_OUTPUT_DIR):
    fp = os.path.join(GGUF_OUTPUT_DIR, f)
    if (f.endswith(".safetensors") or "BF16.gguf" in f) and os.path.isfile(fp):
        try:
            os.remove(fp)
            print(f"Membersihkan berkas sementara: {f}")
        except:
            pass

# Simpan metadata
metrics = {
    "experiment_id": "exp_003",
    "train_steps": MAX_STEPS,
    "final_loss": float(loss),
    "peak_vram_mb": float(peak_vram),
    "samples_trained": len(formatted_texts)
}
with open(os.path.join(EXP_DIR, "training_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print("METADATA EXP_003 BERHASIL DISIMPAN!")
