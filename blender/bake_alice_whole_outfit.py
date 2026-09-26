"""Transfer full-master PBR shading to the complete reduction candidate at 4K.

No photographic cutouts, garment face extraction or new Tripo request. The
master geometry/materials and the previous candidate remain immutable files.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--master', required=True)
parser.add_argument('--candidate', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
master = json.loads(Path(args.master).read_text(encoding='utf-8'))
candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
for record in [master, candidate]:
    for path, expected in [('model', 'modelSha256'), ('editableBlend', 'editableBlendSha256')]:
        if digest(record[path]) != record[expected]:
            raise ValueError('Source identity changed before bake: ' + path)
if master['sourcePhotoSha256'] != candidate['sourcePhotoSha256'] or not candidate['optimizationAudit']['wholeOutfitKept']:
    raise ValueError('Expected complete master and reduction of the same outfit.')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Use a new bake directory.')
bpy.ops.wm.open_mainfile(filepath=master['editableBlend'])
high = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(high) != 1:
    raise ValueError('Expected a single complete high-poly master.')
high = high[0]
high.name = 'Chapeleiro / complete high-poly bake source'
bpy.ops.import_scene.gltf(filepath=candidate['model'])
low = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o != high]
if len(low) != 1:
    raise ValueError('Expected one complete reduction target.')
low = low[0]
low.name = 'Chapeleiro / whole outfit / 4K baked reduction'
for i, mat in enumerate(low.data.materials):
    low.data.materials[i] = mat.copy()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 1
scene.render.bake.use_selected_to_active = True
scene.render.bake.use_cage = False
scene.render.bake.cage_extrusion = .00135
scene.render.bake.max_ray_distance = .003
scene.render.bake.margin = 16
scene.render.bake.use_clear = True
scene.render.bake.normal_space = 'TANGENT'
scene.render.bake.normal_r = 'POS_X'
scene.render.bake.normal_g = 'POS_Y'
scene.render.bake.normal_b = 'POS_Z'
images = {}
texture_records = {}
original_outputs = []
for mat in high.data.materials:
    output = next(n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
    original_outputs.append((mat, output, output.inputs['Surface'].links[0].from_socket))

def target_image(name, color):
    img = bpy.data.images.new('Chapeleiro / baked ' + name + ' / 4K', width=4096, height=4096,
                              alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    for mat in low.data.materials:
        mat.node_tree.nodes.active = None
        node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.name = 'Bake target / ' + name
        node.image = img
        mat.node_tree.nodes.active = node
    return img

def emit_channel(channel):
    for mat, output, original in original_outputs:
        nt = mat.node_tree
        shader = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        emit = nt.nodes.get('Bake / temporary emission') or nt.nodes.new('ShaderNodeEmission')
        emit.name = 'Bake / temporary emission'
        for link in list(emit.inputs['Color'].links):
            nt.links.remove(link)
        source = shader.inputs[channel]
        if source.links:
            nt.links.new(source.links[0].from_socket, emit.inputs['Color'])
        else:
            value = source.default_value
            emit.inputs['Color'].default_value = (*value[:3], 1) if hasattr(value, '__len__') else (value, value, value, 1)
        nt.links.new(emit.outputs['Emission'], output.inputs['Surface'])

def select_pair():
    bpy.ops.object.select_all(action='DESELECT')
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

for name, channel in [('basecolor','Base Color'), ('roughness','Roughness'), ('metallic','Metallic'), ('normal',None)]:
    img = target_image(name, name == 'basecolor')
    if channel:
        emit_channel(channel)
    else:
        for mat, output, original in original_outputs:
            mat.node_tree.links.new(original, output.inputs['Surface'])
    select_pair()
    print('WHOLE_PBR_BAKE_BEGIN ' + name, flush=True)
    bpy.ops.object.bake(type='EMIT' if channel else 'NORMAL')
    file = out / (name + '.png')
    img.filepath_raw = str(file)
    img.file_format = 'PNG'
    img.save()
    img.pack()
    images[name] = img
    texture_records[name] = {'file': str(file), 'sha256': digest(file), 'size': [4096,4096],
                             'colorspace': img.colorspace_settings.name}
    print('WHOLE_PBR_BAKE_SAVED ' + name, flush=True)
for mat, output, original in original_outputs:
    mat.node_tree.links.new(original, output.inputs['Surface'])
    temporary = mat.node_tree.nodes.get('Bake / temporary emission')
    if temporary:
        mat.node_tree.nodes.remove(temporary)
# glTF metallic-roughness: roughness in green and metallic in blue. Values in
# skin regions include the local master's constants, not the Tripo metal mask.
rough = np.empty(4096 * 4096 * 4, dtype=np.float32)
metal = np.empty_like(rough)
images['roughness'].pixels.foreach_get(rough)
images['metallic'].pixels.foreach_get(metal)
packed = np.ones((4096 * 4096, 4), dtype=np.float32)
packed[:,1] = rough.reshape(-1,4)[:,0]
packed[:,2] = metal.reshape(-1,4)[:,0]
rm = bpy.data.images.new('Chapeleiro / baked roughness metallic / 4K', width=4096, height=4096, alpha=False)
rm.colorspace_settings.name = 'Non-Color'
rm.pixels.foreach_set(packed.ravel())
rm.filepath_raw = str(out / 'roughness_metallic.png')
rm.file_format = 'PNG'
rm.save()
rm.pack()
texture_records['roughnessMetallic'] = {'file': rm.filepath_raw, 'sha256': digest(rm.filepath_raw), 'size': [4096,4096]}
del rough, metal, packed
for mat in low.data.materials:
    nt = mat.node_tree
    shader = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    # Remove old imported map nodes after the bake. Retaining duplicate image
    # nodes can make the exporter select a stale sampler/map.
    for node in list(nt.nodes):
        if node.type in ['TEX_IMAGE', 'NORMAL_MAP', 'SEPARATE_COLOR']:
            nt.nodes.remove(node)
    base = nt.nodes.new('ShaderNodeTexImage'); base.image = images['basecolor']
    normal = nt.nodes.new('ShaderNodeTexImage'); normal.image = images['normal']
    normal_map = nt.nodes.new('ShaderNodeNormalMap'); normal_map.inputs['Strength'].default_value = 1
    packed_node = nt.nodes.new('ShaderNodeTexImage'); packed_node.image = rm
    separate = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(base.outputs['Color'], shader.inputs['Base Color'])
    nt.links.new(normal.outputs['Color'], normal_map.inputs['Color'])
    nt.links.new(normal_map.outputs['Normal'], shader.inputs['Normal'])
    nt.links.new(packed_node.outputs['Color'], separate.inputs['Color'])
    nt.links.new(separate.outputs['Green'], shader.inputs['Roughness'])
    nt.links.new(separate.outputs['Blue'], shader.inputs['Metallic'])
high.hide_render = True
high.hide_set(True)
select_pair()
high.select_set(False)
editable = out / 'chapeleiro_whole_baked.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True, export_yup=True)
if model.stat().st_size >= 100 * 1024 * 1024:
    raise ValueError('Baked GLB exceeds GitHub per-file limit; do not publish it.')
low.data.calc_loop_triangles()
record = {**candidate, 'method': 'whole_Tripo_outfit_reduction_with_high_to_low_4K_PBR_bake',
          'model': str(model), 'modelSha256': digest(model), 'editableBlend': str(editable),
          'editableBlendSha256': digest(editable), 'geometryParentSha256': candidate['modelSha256'],
          'bakeMasterSha256': master['modelSha256'], 'bakedTextures': texture_records,
          'triangles': len(low.data.loop_triangles), 'vertices': len(low.data.vertices),
          'optimizationAudit': {**candidate['optimizationAudit'], 'normalRebakeCompleted': True},
          'bakeSettings': {'resolution': 4096, 'marginPixels': 16, 'cageExtrusion': .00135,
                           'maxRayDistance': .003, 'selectedToActive': True, 'normalSpace': 'TANGENT'},
          'status': 'generated_awaiting_visual_review', 'fidelityVerified': False,
          'motionVerified': False, 'completedOutfit': False, 'additionalCreditsConsumed': 0}
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('WHOLE_PBR_BAKE_COMPLETE', model.stat().st_size, flush=True)
