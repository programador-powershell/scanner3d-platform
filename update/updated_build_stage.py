#!/usr/bin/env python3
"""
build_stage.py - Scanner 3D Cognitivo v6
Atualizado para construir camadas complexas de figurinos reais
(Alice Liddell style - corset, multi-tier skirts, overskirt, sleeves, etc.)

Uso:
blender --background --python build_stage.py -- --job <id> --stage <stage> --out <dir> --ref-image <path> [--costume-layers <json>]
"""

import bpy
import sys
import json
import argparse
import os
from mathutils import Vector

# ==================== ARGUMENTOS ====================

parser = argparse.ArgumentParser()
parser.add_argument('--job', required=True)
parser.add_argument('--stage', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--ref-image', default='')
parser.add_argument('--costume-layers', default='')
parser.add_argument('--garment-pattern', default='')
parser.add_argument('--materials-preset', default='')   # NOVO: Preset de materiais

args = parser.parse_args()

JOB_ID = args.job
STAGE = args.stage
OUT_DIR = args.out
REF_IMAGE = args.ref_image
COSTUME_LAYERS_PATH = args.costume_layers
MATERIALS_PRESET_PATH = args.materials_preset

os.makedirs(OUT_DIR, exist_ok=True)

print(f"[build_stage] Job: {JOB_ID} | Stage: {STAGE}")

# ==================== FUNÇÕES AUXILIARES ====================

def hide_all(except_names=None):
    if except_names is None:
        except_names = []
    for obj in bpy.data.objects:
        obj.hide_set(obj.name not in except_names)

def export_gltf(filepath, apply_modifiers=True):
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_apply=apply_modifiers,
        export_yup=True,
        use_visible=True
    )
    print(f"[export] GLB salvo em: {filepath}")

def setup_cloth_physics(obj, layer_data):
    """Adiciona e configura modificador Cloth com propriedades por camada"""
    if obj.type != 'MESH':
        return

    # Remove cloth anterior se existir
    for mod in obj.modifiers:
        if mod.type == 'CLOTH':
            obj.modifiers.remove(mod)

    cloth_mod = obj.modifiers.new(name="ClothSim", type='CLOTH')
    settings = cloth_mod.settings

    physics = layer_data.get('physics', {})
    settings.quality = 8
    settings.mass = physics.get('mass', 0.5)
    settings.stiffness = physics.get('stiffness', 0.7)
    settings.damping = physics.get('damping', 0.4)
    settings.air_damping = 0.15
    settings.bending_stiffness = 0.6
    settings.tension_stiffness = 0.8

    # Collision settings
    coll = cloth_mod.collision_settings
    coll.use_collision = True
    coll.distance_min = 0.005
    coll.friction = 0.3

    print(f"[physics] Cloth configurado para {obj.name} | stiffness={settings.stiffness}")

def add_collision_to_body(body_obj):
    """Adiciona Collision modifier ao corpo para interação com roupa"""
    if body_obj.type != 'MESH':
        return
    for mod in body_obj.modifiers:
        if mod.type == 'COLLISION':
            return
    body_obj.modifiers.new(name="Collision", type='COLLISION')
    body_obj.collision.absorption = 0.1


# ==================== APLICAÇÃO AUTOMÁTICA DE MATERIAIS ====================

def create_material_from_preset(name: str, mat_data: dict):
    """Cria material Blender a partir do preset JSON"""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    for node in list(nodes):
        nodes.remove(node)
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    output.location = (400, 0)
    principled.location = (0, 0)
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    base_color_hex = mat_data.get('base_color', '#FFFFFF')
    r = int(base_color_hex[1:3], 16) / 255
    g = int(base_color_hex[3:5], 16) / 255
    b = int(base_color_hex[5:7], 16) / 255
    principled.inputs['Base Color'].default_value = (r, g, b, 1.0)
    
    if 'roughness' in mat_data:
        principled.inputs['Roughness'].default_value = float(mat_data['roughness'])
    if 'metallic' in mat_data:
        principled.inputs['Metallic'].default_value = float(mat_data['metallic'])
    if 'sheen' in mat_data:
        principled.inputs['Sheen'].default_value = float(mat_data['sheen'])
    if 'clearcoat' in mat_data:
        principled.inputs['Clearcoat'].default_value = float(mat_data['clearcoat'])
    if 'transmission' in mat_data:
        principled.inputs['Transmission'].default_value = float(mat_data['transmission'])
    if 'ior' in mat_data:
        principled.inputs['IOR'].default_value = float(mat_data['ior'])
    
    print(f"[Material] Criado/Aplicado: {name}")
    return mat


def apply_materials_automatically(costume_layers_path: str, materials_preset_path: str):
    """Aplica materiais do preset em todas as layers do figurino"""
    if not costume_layers_path or not materials_preset_path:
        print("[Material] Paths não fornecidos. Pulando aplicação automática.")
        return
    if not os.path.exists(costume_layers_path) or not os.path.exists(materials_preset_path):
        print("[Material] Arquivos de layers ou preset não encontrados.")
        return

    with open(costume_layers_path, 'r', encoding='utf-8') as f:
        costume = json.load(f)
    with open(materials_preset_path, 'r', encoding='utf-8') as f:
        preset = json.load(f)

    materials_data = preset.get("materials", {})

    for layer in costume.get("layers", []):
        material_id = layer.get("material_id")
        if not material_id or material_id not in materials_data:
            continue

        mat_data = materials_data[material_id]
        mat_name = f"Mat_{layer['id']}"
        mat = create_material_from_preset(mat_name, mat_data)

        # Aplica no objeto correspondente
        for obj in bpy.data.objects:
            layer_name_lower = layer['name'].lower()
            if (layer['id'].lower() in obj.name.lower() or 
                layer_name_lower in obj.name.lower() or
                layer.get('type', '') in obj.name.lower()):
                if obj.type == 'MESH' and len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                    print(f"[Material] Aplicado {mat_name} em {obj.name}")


def run_vlm_judge(stage_name: str, preview_image: str, reference_image: str, 
                  costume_layers_path: str, output_judgment: str):
    """Chama o script vlm_judge_layer.py após exportar a layer"""
    import subprocess
    
    if not os.path.exists(preview_image) or not os.path.exists(reference_image):
        print("[VLM Judge] Preview ou referência não encontrada. Pulando julgamento.")
        return None

    cmd = [
        "python3",
        os.path.join(os.path.dirname(__file__), "..", "python", "vlm_judge_layer.py"),
        "--stage", stage_name,
        "--preview", preview_image,
        "--reference", reference_image,
        "--costume_layers", costume_layers_path,
        "--out", output_judgment
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(f"[VLM Judge] Saída: {result.stdout.strip()}")
        
        if os.path.exists(output_judgment):
            with open(output_judgment, 'r') as f:
                judgment = json.load(f)
            print(f"[VLM Judge] Score: {judgment.get('score')} | Retry: {judgment.get('should_retry')}")
            return judgment
    except Exception as e:
        print(f"[VLM Judge] Erro ao executar julgamento: {e}")
    
    return None

# ==================== CARREGAR COSTUME LAYERS ====================

costume_data = None
if COSTUME_LAYERS_PATH and os.path.exists(COSTUME_LAYERS_PATH):
    with open(COSTUME_LAYERS_PATH, 'r') as f:
        costume_data = json.load(f)
    print(f"[costume] {len(costume_data.get('layers', []))} camadas carregadas")

# ==================== ESTÁGIOS ====================

if STAGE == 'skeleton':
    print("[stage] Construindo esqueleto com MPFB2 / Z-Anatomy...")
    # Lógica existente de MPFB2 (mantida e reforçada)
    try:
        import mpfb
        from mpfb.services.humanservice import HumanService
        human = HumanService.create_human()
        # ... (código original de criação do rig)
        armature = bpy.data.objects.get('SkeletonRig_MPFB2') or human
        hide_all(except_names=[armature.name])
        export_gltf(os.path.join(OUT_DIR, 'skeleton.glb'))
    except Exception as e:
        print(f"[warning] MPFB2 não disponível ou erro: {e}")
        # Fallback: cria armature básico
        bpy.ops.object.armature_add()
        export_gltf(os.path.join(OUT_DIR, 'skeleton_fallback.glb'))

elif STAGE in ['inner_base', 'corset', 'underskirt', 'overskirt', 'sleeves', 'back_assembly', 'legwear', 'accessories']:
    print(f"[stage] Construindo camada de figurino: {STAGE}")

    if not costume_data:
        print("[error] costume_layers.json não encontrado. Usando stub.")
        # Cria cubo placeholder
        bpy.ops.mesh.primitive_cube_add(size=0.3, location=(0, 0, 1.0))
        obj = bpy.context.active_object
        obj.name = f"Placeholder_{STAGE}"
        export_gltf(os.path.join(OUT_DIR, f'{STAGE}_placeholder.glb'))
    else:
        # Encontra a layer correspondente
        target_layer = None
        for layer in costume_data.get('layers', []):
            if STAGE in layer.get('id', '') or STAGE in layer.get('name', '').lower():
                target_layer = layer
                break

        if not target_layer:
            print(f"[warning] Layer para stage '{STAGE}' não encontrada no JSON. Criando placeholder.")
            target_layer = {"id": STAGE, "name": STAGE, "physics": {}}

        # === LÓGICA PRINCIPAL DE CONSTRUÇÃO DE CAMADA ===
        # 1. Importar malha base (placeholder ou de GarmentCode/MD)
        #    No futuro: importar .obj/.fbx gerado por GarmentCode ou Marvelous Designer
        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 1.0))
        obj = bpy.context.active_object
        obj.name = target_layer.get('name', STAGE)

        # 2. Aplicar materiais PBR (exemplo simplificado)
        mat = bpy.data.materials.new(name=f"Mat_{STAGE}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs['Base Color'].default_value = (0.15, 0.18, 0.25, 1.0)  # Navy escuro exemplo
        bsdf.inputs['Roughness'].default_value = target_layer.get('material', {}).get('roughness', 0.6)
        obj.data.materials.append(mat)

        # 3. Configurar física Cloth
        setup_cloth_physics(obj, target_layer)

        # 4. Adicionar Collision no corpo (se existir)
        body = bpy.data.objects.get('Body') or bpy.data.objects.get('BaseMesh')
        if body:
            add_collision_to_body(body)

        # 5. Parent para armature (se existir)
        armature = bpy.data.objects.get('SkeletonRig_MPFB2')
        if armature:
            obj.parent = armature
            obj.parent_type = 'ARMATURE'

        # 6. Auto UV Unwrap (NOVO)
        auto_uv_unwrap(obj)

        # 7. Trellis2 Texturing + Upscale/Refino (NOVO)
        if target_layer:
            run_trellis2_texturing(obj, target_layer, OUT_DIR)

        # 8. Exportar
        export_path = os.path.join(OUT_DIR, f'{STAGE}.glb')
        export_gltf(export_path)

        # 7. Aplicar materiais automaticamente
        if MATERIALS_PRESET_PATH and COSTUME_LAYERS_PATH:
            apply_materials_automatically(COSTUME_LAYERS_PATH, MATERIALS_PRESET_PATH)

        # 8. Julgamento automático pelo VLM (NOVO - Self-Correction)
        preview_path = os.path.join(OUT_DIR, f'{STAGE}_preview.png')
        judgment_path = os.path.join(OUT_DIR, f'{STAGE}_judgment.json')
        
        # Gera preview simples (placeholder - em produção usar render mais avançado)
        bpy.ops.render.opengl(write_still=True)
        bpy.data.images['Render Result'].save_render(preview_path)
        
        if REF_IMAGE and os.path.exists(REF_IMAGE):
            run_vlm_judge(
                stage_name=STAGE,
                preview_image=preview_path,
                reference_image=REF_IMAGE,
                costume_layers_path=COSTUME_LAYERS_PATH,
                output_judgment=judgment_path
            )

        print(f"[success] Camada '{STAGE}' construída, materiais aplicados e julgada pelo VLM.")

elif STAGE == 'final_assembly':
    print("[stage] Montagem final de todas as camadas + bake de simulação...")
    # Placeholder de montagem final
    bpy.ops.mesh.primitive_cube_add(size=1.8, location=(0,0,1))
    final = bpy.context.active_object
    final.name = "Alice_Liddell_Final_Assembled"

    # Aplicar materiais em todas as layers
    if MATERIALS_PRESET_PATH and COSTUME_LAYERS_PATH:
        apply_materials_automatically(COSTUME_LAYERS_PATH, MATERIALS_PRESET_PATH)

    # Julgamento VLM do assembly final
    preview_path = os.path.join(OUT_DIR, 'final_preview.png')
    judgment_path = os.path.join(OUT_DIR, 'final_judgment.json')
    bpy.ops.render.opengl(write_still=True)
    bpy.data.images['Render Result'].save_render(preview_path)
    
    if REF_IMAGE and os.path.exists(REF_IMAGE):
        run_vlm_judge(
            stage_name="final_assembly",
            preview_image=preview_path,
            reference_image=REF_IMAGE,
            costume_layers_path=COSTUME_LAYERS_PATH,
            output_judgment=judgment_path
        )

    export_gltf(os.path.join(OUT_DIR, 'character_final.glb'))
    print("[success] Personagem final montado, materiais aplicados e julgado pelo VLM.")

else:
    # Estágios legados (skin, hair, muscles, etc.)
    print(f"[stage] Estágio legado: {STAGE}")
    # ... manter lógica anterior ...

print("[build_stage] Finalizado com sucesso.")