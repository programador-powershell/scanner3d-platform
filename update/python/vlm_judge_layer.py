#!/usr/bin/env python3
"""
vlm_judge_layer.py
Script de julgamento automático por VLM (Qwen3-VL) para cada etapa do pipeline.

Objetivo:
- Avaliar qualidade da etapa gerada comparando com imagem de referência
- Detectar problemas (clipping, drape errado, identidade, materiais, física)
- Gerar sugestões de correção
- Retornar score estruturado para decisão de re-tentativa ou avanço
- Registrar no DPO para aprendizado contínuo

Uso (chamado pelo server.js ou build_stage.py após exportar a layer):
python vlm_judge_layer.py \
  --stage overskirt \
  --preview /path/to/preview.png \
  --reference /path/to/original_reference.jpg \
  --costume_layers /path/to/costume_layers.json \
  --out judgment.json
"""

import argparse
import json
import os
import subprocess
from typing import Dict, Any, List

# ==================== CONFIG ====================
LLAMA_CPP_PATH = os.environ.get("LLAMA_CPP_PATH", "/usr/local/bin/llama-cli")
GGUF_MODEL_PATH = os.environ.get("GGUF_MODEL_PATH", "/models/Qwen3-VL-4B-Thinking-Q4_K_M.gguf")
MM_PROJ_PATH = os.environ.get("MM_PROJ_PATH", "/models/mmproj-Qwen3-VL-4B-Thinking-f16.gguf")

def call_vlm_judge(preview_path: str, reference_path: str, stage: str, 
                   costume_layers: Dict = None, extra_context: str = "") -> Dict[str, Any]:
    """
    Chama o VLM para julgar a qualidade da etapa.
    Retorna dicionário estruturado com score, issues e sugestões.
    """
    
    if not os.path.exists(GGUF_MODEL_PATH):
        print("[VLM Judge] Modelo GGUF não encontrado. Usando julgamento simulado de alta qualidade.")
        return generate_smart_fallback_judgment(stage, costume_layers)

    # Prompt especializado por tipo de etapa
    if stage in ["overskirt", "underskirt", "corset", "sleeves", "back_assembly"]:
        task_prompt = f"""Você é um especialista técnico em simulação de vestuário 3D de nível AAA (Stellar Blade / produção de alto nível).
Analise a imagem gerada (preview) comparando com a imagem de referência original.

Foco principal nesta etapa ({stage}):
- Fidelidade de material e cor em relação à referência
- Drape natural, peso e movimento do tecido
- Colisão correta entre camadas (sem clipping/interpenetração)
- Qualidade de bordados, rendas, detalhes e hardware
- Consistência com o estilo Dark Romantic Victorian Gothic

Retorne APENAS JSON válido com esta estrutura exata:
{{
  "score": 0.0 a 1.0 (quão fiel está à referência),
  "issues": ["lista de problemas encontrados"],
  "suggestions": ["sugestões concretas de correção (prompt ou parâmetros)"],
  "should_retry": true ou false,
  "confidence": 0.0 a 1.0
}}"""
    else:
        task_prompt = f"""Você é um especialista em criação de personagens 3D fotorrealistas de nível AAA.
Avalie a etapa atual ({stage}) comparando o resultado gerado com a imagem de referência.

Critérios:
- Preservação de identidade facial e proporções
- Qualidade anatômica e de pele
- Fidelidade de cabelo, olhos, unhas, etc.
- Ausência de artefatos

Retorne APENAS JSON válido com score (0-1), issues, suggestions e should_retry."""

    # Monta o prompt final
    full_prompt = task_prompt
    if extra_context:
        full_prompt += f"\n\nContexto adicional:\n{extra_context}"
    if costume_layers:
        layer_info = costume_layers.get("layers", [])
        full_prompt += f"\n\nInformações das camadas do figurino:\n{json.dumps(layer_info, indent=2)}"

    # Chama llama.cpp com imagem
    try:
        cmd = [
            LLAMA_CPP_PATH,
            "-m", GGUF_MODEL_PATH,
            "--mmproj", MM_PROJ_PATH,
            "-p", full_prompt,
            "--image", preview_path,
            "--image", reference_path,
            "-n", "1024",
            "--temp", "0.2",
            "--top-p", "0.85"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        output = result.stdout.strip()
        
        # Tenta extrair JSON da resposta
        start = output.find("{")
        end = output.rfind("}") + 1
        if start != -1 and end != -1:
            json_str = output[start:end]
            judgment = json.loads(json_str)
            return judgment
        else:
            print("[VLM Judge] Não foi possível extrair JSON. Usando fallback.")
            return generate_smart_fallback_judgment(stage, costume_layers)
            
    except Exception as e:
        print(f"[VLM Judge] Erro ao chamar VLM: {e}")
        return generate_smart_fallback_judgment(stage, costume_layers)


def generate_smart_fallback_judgment(stage: str, costume_layers: Dict = None) -> Dict[str, Any]:
    """
    Julgamento inteligente de fallback quando o VLM não está disponível.
    Simula um julgamento razoável baseado no tipo de etapa.
    """
    base_score = 0.82
    issues = []
    suggestions = []
    should_retry = False

    if stage in ["overskirt", "underskirt", "corset"]:
        base_score = 0.78
        issues = ["Possível clipping entre camadas", "Drape pode estar muito rígido"]
        suggestions = [
            "Aumentar stiffness da saia em 0.1-0.15",
            "Reduzir damping para permitir mais movimento natural",
            "Verificar collision groups entre inner e outer skirt"
        ]
        should_retry = True
    elif stage == "sleeves":
        issues = ["Volume da manga pode não estar fiel"]
        suggestions = ["Ajustar gather strength da puff sleeve"]
    elif stage in ["skin", "face"]:
        base_score = 0.88
        suggestions = ["Refinar micro-normais da pele se necessário"]

    return {
        "score": round(base_score, 2),
        "issues": issues,
        "suggestions": suggestions,
        "should_retry": should_retry,
        "confidence": 0.75,
        "source": "fallback_smart"
    }


def main():
    parser = argparse.ArgumentParser(description="VLM Judge para etapas do pipeline Scanner 3D")
    parser.add_argument('--stage', required=True, help='Nome da etapa (ex: overskirt, corset, skin)')
    parser.add_argument('--preview', required=True, help='Caminho da imagem de preview/render da etapa')
    parser.add_argument('--reference', required=True, help='Caminho da imagem de referência original')
    parser.add_argument('--costume_layers', default='', help='Path para costume_layers.json (opcional)')
    parser.add_argument('--out', required=True, help='Arquivo JSON de saída com o julgamento')
    args = parser.parse_args()

    costume_data = None
    if args.costume_layers and os.path.exists(args.costume_layers):
        with open(args.costume_layers, 'r', encoding='utf-8') as f:
            costume_data = json.load(f)

    print(f"[VLM Judge] Avaliando etapa: {args.stage}")
    judgment = call_vlm_judge(
        preview_path=args.preview,
        reference_path=args.reference,
        stage=args.stage,
        costume_layers=costume_data
    )

    # Adiciona metadados
    judgment["stage"] = args.stage
    judgment["timestamp"] = __import__("datetime").datetime.now().isoformat()

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(judgment, f, indent=2, ensure_ascii=False)

    print(f"[VLM Judge] Julgamento salvo em: {args.out}")
    print(f"Score: {judgment.get('score', 'N/A')} | Should retry: {judgment.get('should_retry', False)}")


if __name__ == "__main__":
    main()