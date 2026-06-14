"""
train_vlm_unsloth.py - Atualizado (junho 2026)
Suporta tanto SFT quanto DPO usando feedback humano (aprovações/reprovações).

Fluxo recomendado:
1. Rode o servidor normalmente (ele gera dpo_dataset.jsonl automaticamente)
2. Quando quiser treinar: python training/train_vlm_unsloth.py
3. O script detecta automaticamente se existe dpo_dataset.jsonl e usa DPO
"""

import json
import os
from unsloth import FastVisionModel
from transformers import TrainingArguments

# ==================== CONFIGURAÇÕES ====================
max_seq_length = 512
HERE = os.path.dirname(os.path.abspath(__file__))

DPO_DATASET = os.path.join(HERE, "..", "data", "dpo_dataset.jsonl")
SFT_DATASET = os.path.join(HERE, "dataset.json")

OUTPUT_DIR = "./qwen3d"

# ==================== CARREGAMENTO DO MODELO ====================
model, tokenizer = FastVisionModel.from_pretrained(
    model_name="unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
    max_seq_length=max_seq_length,
)

model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=True,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=16,                    # Aumentei um pouco para melhor aprendizado
    lora_alpha=16,
    lora_dropout=0.05,
    bias="none",
    use_rslora=False,
    random_state=3407,
    target_modules="all-linear",
    modules_to_save=["lm_head", "embed_tokens"],
)

# ==================== DETECÇÃO DO TIPO DE DATASET ====================
use_dpo = os.path.exists(DPO_DATASET) and os.path.getsize(DPO_DATASET) > 100

if use_dpo:
    print(">>> Usando DPO com dados de aprovações/reprovações do usuário")
    from trl import DPOTrainer, DPOConfig
    from datasets import load_dataset

    train_dataset = load_dataset("json", data_files=DPO_DATASET, split="train")

    training_args = DPOConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=2,
        learning_rate=5e-5,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        optim="adamw_8bit",
        gradient_checkpointing=True,
        report_to="none",
        beta=0.1,                    # Parâmetro importante do DPO
    )

    FastVisionModel.for_training(model)

    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        tokenizer=tokenizer,
    )

else:
    print(">>> Usando SFT (dataset.json tradicional)")
    if not os.path.exists(SFT_DATASET):
        raise SystemExit("Arquivo dataset.json não encontrado. Rode prepare_dataset.py primeiro.")

    with open(SFT_DATASET, encoding="utf-8") as f:
        train_dataset = json.load(f)

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        num_train_epochs=3,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        optim="adamw_8bit",
        gradient_checkpointing=True,
        report_to="none",
    )

    training_args.remove_unused_columns = False
    training_args.dataset_text_field = ""
    training_args.dataset_kwargs = {"skip_prepare_dataset": True}

    from unsloth.trainer import UnslothVisionDataCollator
    from trl import SFTTrainer

    FastVisionModel.for_training(model)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer),
        train_dataset=train_dataset,
        args=training_args,
    )

# ==================== TREINAMENTO ====================
print(f"Iniciando treinamento com {len(train_dataset)} exemplos...")
stats = trainer.train()
print(stats)

# Salva o LoRA
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"\n✅ Modelo salvo em: {OUTPUT_DIR}")

print("\nDica: Depois do treinamento, você pode fazer merge para 16-bit e servir com vLLM.")