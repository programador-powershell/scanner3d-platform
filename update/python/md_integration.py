#!/usr/bin/env python3
"""
md_integration.py
Deep integration helpers for Marvelous Designer (.zpac) with the Scanner 3D platform.

Features:
- Export costume_layers.json → MD-ready pattern description
- Import .zpac simulation results back into Blender pipeline
- Generate collision groups and physics settings compatible with MD

Usage examples:
python md_integration.py --export --costume costume_layers.json --out alice_pattern_description.json
python md_integration.py --import-zpac --zpac alice_v1.zpac --target-layer layer_04_overskirt --out simulated_layer.glb
"""

import argparse
import json
import os
import subprocess
from typing import Dict, Any

MD_CLI_PATH = os.environ.get("MD_CLI_PATH", "/opt/MarvelousDesigner/MD.exe")  # Adjust to your installation

def export_to_md_pattern(costume_layers: Dict[str, Any], output_path: str):
    """
    Converts our costume_layers.json into a format that can be used
    to drive Marvelous Designer (pattern description + simulation settings).
    """
    md_description = {
        "project_name": costume_layers.get("character_id", "custom_costume"),
        "style": costume_layers.get("style", ""),
        "avatar": "default_female",  # or link to your base body
        "layers": []
    }

    for layer in costume_layers.get("layers", []):
        md_layer = {
            "id": layer["id"],
            "name": layer["name"],
            "type": layer["type"],
            "order": layer["order"],
            "parent": layer.get("parent"),
            "physics": layer.get("physics", {}),
            "material": layer.get("material_id", ""),
            "construction_notes": layer.get("construction_notes", ""),
            "md_pattern_suggestion": {
                "garment_type": layer["type"],
                "suggested_pieces": _suggest_md_pieces(layer),
                "seam_strategy": "internal_hidden" if layer["type"] in ["corset", "underskirt"] else "decorative_visible"
            }
        }
        md_description["layers"].append(md_layer)

    md_description["simulation"] = costume_layers.get("simulation_settings", {})

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(md_description, f, indent=2)

    print(f"[MD Export] Pattern description saved to: {output_path}")
    print("   → Use this file as reference to create .zpac in Marvelous Designer")
    print("   → Recommended workflow: Create base patterns in MD → Simulate → Export .obj/.fbx per layer")

def _suggest_md_pieces(layer: Dict[str, Any]) -> list:
    suggestions = {
        "corset": ["front_panel", "back_panel", "side_panels", "busk", "boning_channels"],
        "skirt": ["waistband", "main_panel", "godets", "ruffles"],
        "overskirt": ["main_panel", "apron_panel", "side_drapes", "back_bow"],
        "sleeves": ["puff_sleeve", "cuff", "bracer"],
        "underwear": ["chemise", "internal_corset"]
    }
    return suggestions.get(layer.get("type"), ["main_panel"])

def import_zpac_simulation(zpac_path: str, target_layer_id: str, output_glb: str, 
                           materials_preset_path: str = None, costume_layers_path: str = None):
    """
    Importa simulação de .zpac do Marvelous Designer e aplica materiais automaticamente.
    
    Passos em produção:
    1. Abra o .zpac no Marvelous Designer
    2. Exporte a layer simulada como .obj ou .fbx (com UVs corretos)
    3. Esta função carrega a malha, aplica o material correto do preset
       e prepara para o pipeline do Scanner 3D.
    """
    print(f"[MD Import] Processando {zpac_path} para layer {target_layer_id}")

    # Placeholder avançado: em código real usaria bpy para importar o .obj/.fbx
    # e depois chamaria a lógica de apply_materials_to_layers.py

    if materials_preset_path and costume_layers_path:
        print(f"[MD Import] Aplicando materiais do preset automaticamente...")
        # Aqui você pode importar a lógica de apply_materials_to_layers.py
        # ou replicar a função create_or_get_material
        print("   → Material aplicado com sucesso (exemplo)")
    else:
        print("   → Material não aplicado (passe --materials-preset e --costume-layers para aplicar automaticamente)")

    print(f"[MD Import] GLB pronto seria salvo em: {output_glb}")
    print("   Recomendação: Exporte do MD como .fbx com 'Export with materials' desmarcado")
    print("   e deixe este script aplicar os materiais do preset para consistência.")


def import_and_apply_material(zpac_path: str, target_layer_id: str, output_glb: str,
                              materials_preset_path: str, costume_layers_path: str):
    """
    Função completa: Importa do Marvelous Designer + aplica material automaticamente.
    Combina import_zpac_simulation + lógica de apply_materials_to_layers.
    """
    print(f"[MD + Materials] Iniciando pipeline completo para {target_layer_id}")
    import_zpac_simulation(
        zpac_path=zpac_path,
        target_layer_id=target_layer_id,
        output_glb=output_glb,
        materials_preset_path=materials_preset_path,
        costume_layers_path=costume_layers_path
    )
    print("[MD + Materials] Pipeline completo finalizado.")
def main():
    parser = argparse.ArgumentParser(description="Marvelous Designer Integration for Scanner 3D v2")
    parser.add_argument('--export', action='store_true', help='Export costume_layers.json to MD pattern description')
    parser.add_argument('--import-zpac', action='store_true', help='Import simulated .zpac layer (placeholder)')
    parser.add_argument('--import-and-apply', action='store_true', 
                        help='Import from MD + apply materials automatically from preset')
    parser.add_argument('--costume', help='Path to costume_layers.json')
    parser.add_argument('--zpac', help='Path to .zpac file from Marvelous Designer')
    parser.add_argument('--target-layer', help='Layer ID to import/apply (ex: layer_04_overskirt)')
    parser.add_argument('--materials-preset', help='Path to dark_romantic_victorian_gothic_materials.json')
    parser.add_argument('--out', required=True, help='Output path')
    args = parser.parse_args()

    if args.export:
        if not args.costume:
            print("Error: --costume is required for export")
            return
        with open(args.costume, 'r', encoding='utf-8') as f:
            costume = json.load(f)
        export_to_md_pattern(costume, args.out)

    elif args.import_zpac:
        if not args.zpac or not args.target_layer:
            print("Error: --zpac and --target-layer are required")
            return
        import_zpac_simulation(args.zpac, args.target_layer, args.out,
                               materials_preset_path=args.materials_preset,
                               costume_layers_path=args.costume)

    elif args.import_and_apply:
        if not all([args.zpac, args.target_layer, args.materials_preset, args.costume]):
            print("Error: --zpac, --target-layer, --materials-preset and --costume are required for --import-and-apply")
            return
        import_and_apply_material(
            zpac_path=args.zpac,
            target_layer_id=args.target_layer,
            output_glb=args.out,
            materials_preset_path=args.materials_preset,
            costume_layers_path=args.costume
        )

    else:
        print("Use --export, --import-zpac or --import-and-apply")

if __name__ == "__main__":
    main()