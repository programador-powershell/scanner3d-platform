"""
Fine-tuning da VLM avaliadora (seção 7.8) — Unsloth + Qwen2.5-VL-7B 4-bit.
Hardware alvo: RTX 4060 8GB (config do diretor, mantida verbatim).

Pré-requisitos (uma vez):
  pip install unsloth "trl>=0.9" transformers accelerate bitsandbytes

Fluxo:
  1) python training/prepare_dataset.py      # gera training/dataset.json
  2) python training/train_vlm_unsloth.py    # treina LoRA -> ./qwen3d
  3) merge + serve (vLLM) e aponte VLM_URL para o servidor:
       set VLM_URL=http://localhost:8000/v1/chat/completions
"""
import json
import os

from unsloth import FastVisionModel
import torch

# RTX 4060 8GB
max_seq_length = 512

model, tokenizer = FastVisionModel.from_pretrained(
    model_name="unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
    max_seq_length=max_seq_length,
)

model = FastVisionModel.get_peft_model(
    model,

    # IMPORTANTE:
    # treinar visão e linguagem juntos
    finetune_vision_layers=True,
    finetune_language_layers=True,

    # mantém capacidade de raciocínio
    finetune_attention_modules=True,
    finetune_mlp_modules=True,

    # RTX 4060 8GB
    r=8,
    lora_alpha=16,
    lora_dropout=0,
    bias="none",

    use_rslora=False,
    random_state=3407,

    target_modules="all-linear",

    modules_to_save=[
        "lm_head",
        "embed_tokens",
    ],
)

from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./qwen3d",

    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,

    num_train_epochs=3,

    learning_rate=2e-4,

    fp16=True,
    bf16=False,

    logging_steps=10,

    save_steps=100,
    save_total_limit=2,

    optim="adamw_8bit",

    gradient_checkpointing=True,

    report_to="none",
)

# ---------------------------------------------------------------
# Dataset: pares (foto+render -> veredito JSON) dos 9 portões
# ---------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "dataset.json")
if not os.path.exists(DATASET):
    raise SystemExit("Rode antes: python training/prepare_dataset.py")
with open(DATASET, encoding="utf-8") as f:
    train_dataset = json.load(f)
print(f"dataset: {len(train_dataset)} exemplos")

# Campos extras que o SFTTrainer espera para datasets de visão pré-formatados
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

stats = trainer.train()
print(stats)

# salva o adapter LoRA (e tokenizer) em ./qwen3d
model.save_pretrained("./qwen3d")
tokenizer.save_pretrained("./qwen3d")
print("LoRA salvo em ./qwen3d")

# opcional: merge 16-bit para servir no vLLM (precisa de ~16GB de disco)
#   model.save_pretrained_merged("./qwen3d-merged", tokenizer, save_method="merged_16bit")
#   vllm serve ./qwen3d-merged --port 8000
#   set VLM_URL=http://localhost:8000/v1/chat/completions
