#!/usr/bin/env python3
"""
apply_materials_to_layers.py
Aplica automaticamente os materiais do preset "Dark Romantic Victorian Gothic"
nas camadas do costume_layers.json dentro do Blender.

Uso (dentro do Blender ou via headless):
blender --background --python apply_materials_to_layers.py -- \
  --costume_layers /caminho/costume_layers.json \
  --materials_preset /caminho/dark_romantic_victorian_gothic_materials.json \
  --apply_to_scene
"""

import bpy
import json
import argparse
import os
from mathutils import Color

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_or_get_material(name, mat_data):
    """Cria ou atualiza um material Blender a partir dos dados do preset"""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name=name)
    
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Limpa nodes existentes
    for node in nodes:
        nodes.remove(node)
    
    # Cria nodes principais
    output = nodes.new(type='ShaderNodeOutputMaterial')
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    
    # Posicionamento
    output.location = (400, 0)
    principled.location = (0, 0)
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    # Aplica propriedades do preset
    principled.inputs['Base Color'].default_value = (
        int(mat_data.get('base_color', '#FFFFFF')[1:3], 16) / 255,
        int(mat_data.get('base_color', '#FFFFFF')[3:5], 16) / 255,
        int(mat_data.get('base_color', '#FFFFFF')[5:7], 16) / 255,
        1.0
    )
    
    if 'roughness' in mat_data:
        principled.inputs['Roughness'].default_value = mat_data['roughness']
    if 'metallic' in mat_data:
        principled.inputs['Metallic'].default_value = mat_data['metallic']
    if 'sheen' in mat_data:
        principled.inputs['Sheen'].default_value = mat_data['sheen']
    if 'clearcoat' in mat_data:
        principled.inputs['Clearcoat'].default_value = mat_data['clearcoat']
    if 'transmission' in mat_data:
        principled.inputs['Transmission'].default_value = mat_data['transmission']
    if 'ior' in mat_data:
        principled.inputs['IOR'].default_value = mat_data['ior']
    
    # Normal map (se existir textura)
    if mat_data.get('normal_strength'):
        normal_node = nodes.new(type='ShaderNodeNormalMap')
        normal_node.location = (-300, -200)
        normal_node.inputs['Strength'].default_value = mat_data['normal_strength']
        # Aqui você pode conectar uma imagem de normal map se tiver o caminho
    
    print(f"[Material] Aplicado: {name}")
    return mat

def apply_materials_to_layers(costume_layers_path, materials_preset_path):
    costume = load_json(costume_layers_path)
    materials_preset = load_json(materials_preset_path)
    
    materials_data = materials_preset.get("materials", {})
    
    for layer in costume.get("layers", []):
        layer_id = layer["id"]
        material_id = layer.get("material_id")
        
        if not material_id or material_id not in materials_data:
            print(f"[Warning] Material '{material_id}' não encontrado para layer {layer_id}")
            continue
        
        mat_data = materials_data[material_id]
        mat_name = f"Mat_{layer_id}"
        
        # Cria/atualiza o material
        mat = create_or_get_material(mat_name, mat_data)
        
        # Aplica em todos os objetos que correspondem à layer
        for obj in bpy.data.objects:
            if layer_id.lower() in obj.name.lower() or layer["name"].lower() in obj.name.lower():
                if obj.type == 'MESH':
                    # Remove materiais antigos
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    print(f"[Apply] Material '{mat_name}' aplicado em: {obj.name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--costume_layers', required=True)
    parser.add_argument('--materials_preset', required=True)
    parser.add_argument('--apply_to_scene', action='store_true')
    args = parser.parse_args()
    
    if args.apply_to_scene:
        apply_materials_to_layers(args.costume_layers, args.materials_preset)
        print("[Success] Materiais aplicados automaticamente nas layers!")
    else:
        print("Use --apply_to_scene para aplicar os materiais")

if __name__ == "__main__":
    main()