# -*- coding: utf-8 -*-
"""
Inspeksi Lingkungan Hardware & Perangkat Lunak Resmi ClawFile-Agent
Menghasilkan: clawfile-training/environment.json
"""

import json
import os
import platform
import psutil
import torch
import transformers
import peft

BASE_DIR = r"C:\Users\shint\Documents\FolderVisionAI-FileID\clawfile-training"
ENV_PATH = os.path.join(BASE_DIR, "environment.json")

def inspect_environment():
    gpu_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else "None"
    vram_mb = round(torch.cuda.get_device_properties(0).total_memory / (1024**2)) if gpu_available else 0
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    
    env_data = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "gpu": gpu_name,
        "vram_mb": vram_mb,
        "ram_gb": ram_gb,
        "cuda": torch.version.cuda if gpu_available else "None",
        "pytorch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "quantization_support": {
            "load_in_4bit": True,
            "bitsandbytes": True
        },
        "safety_constraints": {
            "max_vram_limit_mb": 3072, # 3.0 GB VRAM limit for RTX 3050 4GB
            "max_steps_per_run": 100,
            "max_retries": 1
        }
    }
    
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        json.dump(env_data, f, indent=2)
        
    print("Environment successfully written to:", ENV_PATH)
    print(json.dumps(env_data, indent=2))
    return env_data

if __name__ == "__main__":
    inspect_environment()
