"""
Converte data/finetune_dataset.jsonl (decisões dos 9 portões) no formato de
conversa multimodal que o Unsloth/Qwen2.5-VL consome.

Cada decisão vira um exemplo:
  user:      [foto de referência] + [render do portão] + prompt do avaliador
  assistant: JSON {pass, score, defects, suggested_prompt_fix}

aprovado  -> pass=true,  score alto   (positivo)
reprovado -> pass=false, score baixo, note vira defeito (negativo)

Uso:
  python training/prepare_dataset.py
Saída:
  training/dataset.json  (lista de conversas; imagens como caminhos locais)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_IN = os.path.join(ROOT, "data", "finetune_dataset.jsonl")
DATASET_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset.json")

STAGE_NAMES = {
    "skeleton": "Esqueleto", "veins": "Veias", "muscle": "Músculos",
    "garment": "Tecido", "skin": "Pele", "nails": "Unhas",
    "face": "Rosto", "eyes": "Olhos", "hair": "Cabelo",
}

JUDGE_PROMPT = (
    "Você é diretor de arte AAA. A primeira imagem é a foto 2D de referência; "
    "a segunda é o render 3D atual do portão {stage}. Avalie:\n"
    "1) O resultado é 100% humano (não placeholder, não cartoon, não cilindro)?\n"
    "2) A anatomia do portão {stage} bate com referências humanas reais?\n"
    "3) A identidade preserva a foto (rosto/proporções/pele)?\n"
    "Responda APENAS JSON: {{\"pass\": bool, \"score\": 0-1, "
    "\"defects\": [...], \"suggested_prompt_fix\": \"...\"}}"
)


def url_to_local(url: str) -> str | None:
    """Mapeia as URLs internas (/uploads/x, /api/jobs/<id>/artifact/<f>) para arquivos."""
    if not url:
        return None
    if url.startswith("/uploads/"):
        p = os.path.join(ROOT, "data", "uploads", os.path.basename(url))
    elif "/artifact/" in url:
        parts = url.strip("/").split("/")
        # api/jobs/<jobId>/artifact/<file>
        try:
            job_id = parts[parts.index("jobs") + 1]
            fname = parts[-1]
        except (ValueError, IndexError):
            return None
        p = os.path.join(ROOT, "data", "jobs", job_id, fname)
    else:
        return None
    return p if os.path.exists(p) else None


def to_example(rec: dict) -> dict | None:
    if rec.get("label") not in ("approved", "rejected", "vlm_pass", "vlm_reject"):
        return None  # edits de prompt não viram par visão
    stage = STAGE_NAMES.get(rec.get("stage", ""), rec.get("stage", ""))
    ref = url_to_local(rec.get("source", ""))
    render = url_to_local(rec.get("snapshot", ""))
    if not ref or not render:
        return None

    approved = rec["label"] in ("approved", "vlm_pass")
    note = (rec.get("note") or "").strip()
    verdict = {
        "pass": approved,
        "score": 0.92 if approved else 0.35,
        "defects": [] if approved else ([note] if note else ["abordagem reprovada pelo diretor"]),
        "suggested_prompt_fix": "" if approved else (rec.get("suggested_prompt_fix") or note or "gerar outra abordagem"),
    }
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": ref},
                    {"type": "image", "image": render},
                    {"type": "text", "text": JUDGE_PROMPT.format(stage=stage)},
                ],
            },
            {
                "role": "assistant",
                "content": [{"type": "text", "text": json.dumps(verdict, ensure_ascii=False)}],
            },
        ]
    }


def main():
    if not os.path.exists(DATASET_IN):
        print(f"ERRO: {DATASET_IN} não existe. Gere decisões no pipeline primeiro.")
        sys.exit(1)
    examples = []
    skipped = 0
    with open(DATASET_IN, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            ex = to_example(rec)
            if ex:
                examples.append(ex)
            else:
                skipped += 1
    with open(DATASET_OUT, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    approved = sum(1 for e in examples if '"pass": true' in e["messages"][1]["content"][0]["text"])
    print(f"OK: {len(examples)} exemplos ({approved} positivos, {len(examples)-approved} negativos), {skipped} pulados")
    print(f"-> {DATASET_OUT}")


if __name__ == "__main__":
    main()
