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
VLM_JUDGMENTS_IN = os.path.join(ROOT, "data", "vlm_judgments.jsonl")  # new hybrid data for better "saber o que é cada coisa"
DATASET_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset.json")

STAGE_NAMES = {
    "skeleton": "Esqueleto", "muscles": "Músculos",
    "garment": "Tecido", "skin": "Pele", "nails": "Unhas",
    "face": "Rosto", "eyes": "Olhos", "hair": "Cabelo",
}

# Improved to teach the VLM "o que é cada coisa" (semantics of gates, spatial elements, layers, proportions)
# with more rigorous, descriptive prompts per gate + hybrid spatial context.
JUDGE_PROMPT = (
    "Você é diretor de arte AAA nível Stellar Blade. A primeira imagem é a foto 2D de referência enviada; "
    "a segunda é o render 3D atual do portão {stage}. "
    "SEMPRE faça aferição direta e rigorosa contra a foto enviada (posições, proporções, camadas, localização exata de elementos via verificação espacial precisa).\n"
    "Descrição do que é o portão {stage}:\n"
    "  - Esqueleto: ossos reais (crânio, vértebras, costelas, pelve, clavículas, falanges), rig com IK, proporções anatômicas, sem palito.\n"
    "  - Músculos: volumes volumétricos instanciados (deltoides, peitorais, bíceps, quadríceps etc) que seguem exatamente a silhueta e massas do corpo na foto de referência, servindo de barreira física real para o tecido (não inferidos, não genéricos), definição de bordas anatômicas visíveis, proporções que casam com o tipo físico da pessoa na foto (ombros/quadril/cintura da imagem).\n"
    "  - Tecido: camadas independentes (corset/chemise como base estruturada na cintura, underskirt com tiers de volume e renda, overskirt com drape assimétrico e apron, mangas puff, back bow, legwear), física real (gravidade, vento, lift), sem fusão/clip entre layers ou com corpo, materiais e bordados fiéis.\n"
    "  - Pele: PBR com poros/micro-normais, SSS translucidez, albedo exato da foto, sem aspecto de cera.\n"
    "  - Unhas: forma anatômica, cutícula, lúnula, specular correto nas extremidades.\n"
    "  - Rosto: topologia com edge loops para animação FACS, identidade facial exata (proporções, linhas de expressão).\n"
    "  - Olhos: íris posicionada, córnea com refração/umidade, lacrimal, profundidade vs face.\n"
    "  - Cabelo: fios individuais (strands/curves), volume, integração com couro cabeludo/rosto, cor e silhueta da foto.\n"
    "Avalie com rigor:\n"
    "1) O resultado é 100% humano (não placeholder, não cartoon, não cilindro)?\n"
    "2) A anatomia do portão {stage} bate com referências humanas reais e verificação espacial (posições/camadas/proporções da foto enviada)?\n"
    "3) A identidade e estética preservam a foto (rosto/proporções/pele/cabelo/roupa exata)?\n"
    "Se verificação espacial indicar falhas (posições erradas, camadas sobrepostas, proporções incorretas), force pass=false e liste como defects.\n"
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
    stage = STAGE_NAMES.get(rec.get("stage", ""), rec.get("stage", ""))
    ref = url_to_local(rec.get("source", "")) or url_to_local(rec.get("image", ""))
    render = url_to_local(rec.get("snapshot", "")) or url_to_local(rec.get("preview_image", ""))
    if not ref or not render:
        return None

    # Support direct DPO format (chosen/rejected) or old label/vlm
    if "chosen" in rec and "rejected" in rec:
        # DPO style from review or judgments
        prompt = rec.get("prompt", f"Analise o portão {stage} vs a foto original enviada.")
        return {
            "messages": [
                {"role": "user", "content": [{"type": "image", "image": ref}, {"type": "image", "image": render}, {"type": "text", "text": prompt}] },
                {"role": "assistant", "content": rec["chosen"] or "approved"}
            ]
        }  # For DPO, the dataset prep will turn into chosen/rejected pairs later if needed; here we prioritize the pair

    if rec.get("label") not in ("approved", "rejected", "vlm_pass", "vlm_reject"):
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
    examples = []
    # Original finetune
    if os.path.exists(DATASET_IN):
        with open(DATASET_IN, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                ex = to_example(rec)
                if ex:
                    examples.append(ex)
    # New: vlm_judgments with hybrid (LocateAnything spatial + Qwen) for teaching "o que é cada coisa"
    # Creates richer SFT/DPO examples that explicitly train on spatial verification vs aesthetic, per-gate semantics.
    if os.path.exists(VLM_JUDGMENTS_IN):
        with open(VLM_JUDGMENTS_IN, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("type") != "vlm_judgment_pro_build":
                        continue
                    stage = STAGE_NAMES.get(rec.get("stage", ""), rec.get("stage", ""))
                    ref = url_to_local(rec.get("ref_images", [None])[0] if rec.get("ref_images") else None) or rec.get("ref_images", [None])[0]
                    render = url_to_local(rec.get("preview_image")) or rec.get("preview_image")
                    if not ref or not render:
                        continue
                    hybrid = rec.get("verdict", {}).get("hybrid", {})
                    spatial = hybrid.get("spatial", {})
                    qwen = hybrid.get("qwen_verdict", rec.get("verdict", {}))
                    approved = qwen.get("pass", False) and spatial.get("avg_spatial_score", 0) >= 0.85
                    # Enrich prompt with hybrid spatial + semantics so VLM learns precise "o que é" (layers positions, proportions, what a corset "is" spatially)
                    spatial_note = f" Spatial verification (LocateAnything vs sent photo): score={spatial.get('avg_spatial_score',0.7)}. Issues: {spatial.get('issues', [])}. "
                    enriched_prompt = JUDGE_PROMPT.format(stage=stage) + spatial_note + " Use this to judge if spatial precision + overall quality match the reference photo exactly."
                    verdict = {
                        "pass": approved,
                        "score": qwen.get("score", 0.92 if approved else 0.35),
                        "defects": qwen.get("defects", []) + spatial.get("issues", []),
                        "suggested_prompt_fix": qwen.get("suggested_prompt_fix", "") or spatial.get("recommendation", ""),
                    }
                    examples.append({
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image", "image": ref},
                                    {"type": "image", "image": render},
                                    {"type": "text", "text": enriched_prompt},
                                ],
                            },
                            {
                                "role": "assistant",
                                "content": [{"type": "text", "text": json.dumps(verdict, ensure_ascii=False)}],
                            },
                        ]
                    })
                except Exception:
                    continue
    if not os.path.exists(DATASET_IN) and not os.path.exists(VLM_JUDGMENTS_IN):
        print(f"ERRO: Nenhum dataset de decisões (finetune ou vlm_judgments) encontrado. Gere no pipeline primeiro.")
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
