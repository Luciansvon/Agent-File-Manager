# -*- coding: utf-8 -*-
"""
Pipeline Pelatihan Resmi ClawFile-Agent Eksperimen 002 (exp_002)
- Menggunakan dataset_train_v2 (159 sampel)
- Menekankan preservasi ekstensi berkas, presisi furnitur, dan respon padat/cepat
- Sepenuhnya mematuhi ML Safety Contract: VRAM < 3.0 GB, max_steps 80
- Membersihkan berkas sementara safetensors secara otomatis
"""

import os
import sys
import json
import torch
import shutil
from unsloth import FastLanguageModel, is_bf16_supported
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

torch.cuda.empty_cache()

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
MODEL_DIR = r"C:\Users\shint\.ollama\models\hub\models--empero-ai--Qwen3.8-2B-Distill\snapshots\e37a2dc4acc68ad75a91e07e63168cb04cc06345"
DATASET_JSONL = os.path.join(BASE_DIR, "data_versions", "dataset_train_v2.jsonl")
EXP_DIR = os.path.join(BASE_DIR, "experiments", "exp_002")
ADAPTER_DIR = os.path.join(EXP_DIR, "lora_adapter")
GGUF_DIR = os.path.join(EXP_DIR, "model_gguf")

def load_data(jsonl_path):
    convs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            item = json.loads(line)
            msgs = []
            for m in item["messages"]:
                c = m["content"]
                if isinstance(c, list):
                    text = " ".join(part["text"] for part in c if part.get("type") == "text")
                else:
                    text = str(c)
                msgs.append({"role": m["role"], "content": text})
            convs.append({"messages": msgs})
    return convs

def main():
    print("=" * 65)
    print(">>> MEMULAI PELATIHAN MANDIRI: EXPERIMENT 002 (exp_002)")
    print("=" * 65)
    
    os.makedirs(EXP_DIR, exist_ok=True)
    os.makedirs(ADAPTER_DIR, exist_ok=True)
    os.makedirs(GGUF_DIR, exist_ok=True)
    
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**2) if torch.cuda.is_available() else 0
    print(f"GPU Terdeteksi: {device_name} ({total_vram:.0f} MB VRAM)")
    
    print("\n[1/5] Memuat model mentah Qwen 3.8 2B (4-bit)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = MODEL_DIR,
        max_seq_length = 768,
        load_in_4bit = True,
    )
    
    print("\n[2/5] Mengonfigurasi LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r = 16,
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha = 32,
        lora_dropout = 0,
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 42,
    )
    
    print(f"\n[3/5] Memuat dataset_train_v2 ({DATASET_JSONL})...")
    raw_data = load_data(DATASET_JSONL)
    print(f"Total sampel latih v2: {len(raw_data)} sampel")
    
    formatted_texts = []
    for item in raw_data:
        t = tokenizer.apply_chat_template(item["messages"], tokenize=False, add_generation_prompt=False)
        formatted_texts.append(t)
    train_dataset = Dataset.from_dict({"text": formatted_texts})
    
    print("\n[4/5] Mengatur konfigurasi pelatihan hemat VRAM...")
    training_args = SFTConfig(
        output_dir = EXP_DIR,
        dataset_text_field = "text",
        max_seq_length = 768,
        per_device_train_batch_size = 1,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 75, # Capped according to ML Safety Contract
        learning_rate = 2e-4,
        fp16 = not is_bf16_supported(),
        bf16 = is_bf16_supported(),
        logging_steps = 5,
        optim = "paged_adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "cosine",
        seed = 42,
        report_to = "none",
        save_strategy = "no",
    )
    
    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = train_dataset,
        args = training_args,
    )
    
    print("\n[5/5] Meluncurkan pelatihan...")
    stats = trainer.train()
    
    peak_vram = torch.cuda.max_memory_allocated(0)/(1024**2)
    print("\n" + "=" * 65)
    print(">>> PELATIHAN exp_002 SELESAI!")
    print(f"Langkah Akhir: {stats.global_step}")
    print(f"Loss Akhir: {stats.training_loss:.4f}")
    print(f"Puncak VRAM: {peak_vram:.1f} MB (Batas Aman: 3072 MB)")
    print("=" * 65)
    
    if peak_vram > 3072:
        print("PERINGATAN: Pemakaian VRAM melampaui 3.0 GB!")
    else:
        print("KONFIRMASI: Pemakaian VRAM 100% aman dalam batas kontrak!")
        
    print(f"\nMenyimpan adapter ke: {ADAPTER_DIR}...")
    model.save_pretrained(ADAPTER_DIR)
    tokenizer.save_pretrained(ADAPTER_DIR)
    
    print(f"\nMengekspor model gabungan ke GGUF (Q4_K_M) di: {GGUF_DIR}...")
    model.save_pretrained_gguf(
        GGUF_DIR,
        tokenizer,
        quantization_method = "q4_k_m"
    )
    
    # Auto-clean intermediate safetensors to save SSD space
    intermediate_st = os.path.join(GGUF_DIR, "model.safetensors")
    if os.path.isfile(intermediate_st):
        print(f"Membersihkan berkas sementara {intermediate_st}...")
        os.remove(intermediate_st)
        
    # Catat konfigurasi eksperimen
    config_data = {
        "experiment_id": "exp_002",
        "dataset_version": "dataset_train_v2",
        "total_samples": len(raw_data),
        "steps": stats.global_step,
        "final_loss": round(stats.training_loss, 4),
        "peak_vram_mb": round(peak_vram, 1),
        "quantization": "Q4_K_M",
        "status": "TRAINED_AND_EXPORTED"
    }
    with open(os.path.join(EXP_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
        
    print("\n>>> EKSPERIMEN exp_002 SELESAI DIEKSPOR!")

if __name__ == "__main__":
    main()
