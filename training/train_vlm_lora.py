# training/train_vlm_lora.py
# Versão aprimorada para auto-aprendizado contínuo
# Usa Unsloth + Qwen3-VL + DPO
# Aprende com aprovações, reprovações e sugestões do usuário

import json
import os
from unsloth import FastVisionModel
from datasets import load_dataset
from trl import DPOTrainer, DPOConfig

DATASET_PATH = "../data/dpo_dataset.jsonl"
OUTPUT_DIR = "./lora_checkpoints"
MODEL_NAME = "Qwen/Qwen2.5-VL-7B-Instruct"   # ou Qwen3-VL quando disponível

def load_dpo_dataset():
    """Carrega o dataset gerado pelas aprovações/reprovações do usuário"""
    examples = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            
            # Cria pares de preferência (chosen = aprovado, rejected = reprovado)
            prompt = f"Analise esta camada do personagem 3D: {data.get('stage')}. Foto de referência e render anexados."
            
            if data.get("label") == "approved":
                examples.append({
                    "prompt": prompt,
                    "chosen": f"Aprovado. Nota: {data.get('note', '')}",
                    "rejected": "Precisa melhorar"
                })
            elif data.get("label") == "rejected":
                examples.append({
                    "prompt": prompt,
                    "chosen": "Precisa melhorar",
                    "rejected": f"Reprovado. Sugestão: {data.get('note', '')}"
                })
    return examples

def train():
    print("Carregando dataset DPO...")
    raw_data = load_dpo_dataset()
    
    if len(raw_data) < 10:
        print("Poucos dados ainda. Continue aprovando/reprovando para melhorar o modelo.")
        return

    dataset = load_dataset("json", data_files={"train": DATASET_PATH}, split="train")

    print("Carregando modelo Qwen-VL com Unsloth...")
    model, tokenizer = FastVisionModel.from_pretrained(
        MODEL_NAME,
        load_in_4bit=True,
        use_gradient_checkpointing=True,
    )

    model = FastVisionModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj"],
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=42,
    )

    training_args = DPOConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=5e-5,
        num_train_epochs=1,
        logging_steps=10,
        save_strategy="epoch",
        optim="adamw_8bit",
        report_to="none",
    )

    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    print("Iniciando fine-tuning com DPO...")
    trainer.train()

    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"Modelo salvo em: {OUTPUT_DIR}")
    print("O VLM agora está mais alinhado com suas preferências!")

if __name__ == "__main__":
    train()