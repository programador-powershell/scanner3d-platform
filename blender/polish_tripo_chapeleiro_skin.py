"""Locally reduce metallic/glossy skin artifacts while preserving new Tripo geometry."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = json.loads(Path(args.generation).read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
if source.get('variant') != 'alice_chapeleiro' or not source.get('studioModelId') or source.get('reusedGeometry') is not False:
    raise ValueError('Use the newly generated full Chapeleiro model, not rejected geometry.')
if sha(source['editableBlend']) != source['editableBlendSha256'] or sha(source['model']) != source['modelSha256']:
    raise ValueError('Fresh full model or editable import changed.')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Use a new polish directory.')
bpy.ops.wm.open_mainfile(filepath=source['editableBlend'])
audits = []
for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
    mesh = obj.data
    if len(mesh.materials) != 1 or not mesh.uv_layers:
        raise ValueError('Expected the original Tripo material and UV atlas.')
    material = mesh.materials[0]
    shader = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    color_node = next(link.from_node for link in shader.inputs['Base Color'].links if link.from_node.type == 'TEX_IMAGE')
    image = color_node.image
    pixels = np.empty(image.size[0] * image.size[1] * image.channels, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(image.size[1], image.size[0], image.channels)
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', positions)
    positions = positions.reshape(-1, 3)
    world = np.asarray(obj.matrix_world, dtype=np.float32)
    positions = positions @ world[:3, :3].T + world[:3, 3]
    counts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', counts)
    if not np.all(counts == 3):
        raise ValueError('Preserve the original triangular topology for this material-only polish.')
    vertices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', vertices)
    centers = positions[vertices.reshape(-1, 3)].mean(axis=1)
    uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 3, 2)
    # Use one actual loop per face rather than averaging across distant UV seams.
    uv = uv[:, 0, :]
    x = np.clip((uv[:, 0] * (image.size[0] - 1)).astype(np.int32), 0, image.size[0] - 1)
    y = np.clip((uv[:, 1] * (image.size[1] - 1)).astype(np.int32), 0, image.size[1] - 1)
    color = pixels[y, x, :3]
    x, y, z = centers.T
    # Actual scan landmarks checked in the four views: arms below the sleeve
    # cuffs, fingers beyond the gauntlets, and face above the costume neckline.
    arm_center = .102 + (.693 - z) * .49
    arms = (z > .535) & (z < .691) & (np.abs(np.abs(x) - arm_center) < .03) & (np.abs(y) < .06)
    hands = (z > .433) & (z < .527) & (np.abs(x) > .153)
    face = (z > .780) & (z < .906) & (np.abs(x) < .052) & (y < -.005)
    chest = (z > .742 + np.abs(x) * .32) & (z < .796) & (np.abs(x) < .056) & (y < -.018)
    pale_skin = (color.min(axis=1) > .14) & (color[:, 0] > color[:, 1] * 1.025) & (color[:, 0] > color[:, 2] * 1.04) & ((color[:, 0] - color[:, 1]) < .22)
    selected = (arms | hands | face | chest) & pale_skin
    if selected.sum() < 100:
        raise ValueError('Skin material mask failed; keep the original model unchanged.')
    skin = material.copy()
    skin.name = 'Chapeleiro / exposed skin / local PBR polish'
    skin_shader = next(n for n in skin.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    for name, value in [('Metallic', 0), ('Roughness', .65), ('IOR', 1.4)]:
        for link in list(skin_shader.inputs[name].links):
            skin.node_tree.links.remove(link)
        skin_shader.inputs[name].default_value = value
    for node in skin.node_tree.nodes:
        if node.type == 'NORMAL_MAP':
            node.inputs['Strength'].default_value = .12
    mesh.materials.append(skin)
    indices = np.where(selected, 1, 0).astype(np.int32)
    mesh.polygons.foreach_set('material_index', indices)
    audits.append({'mesh': obj.name, 'skinPolygons': int(selected.sum()),
                   'armSkinPolygons': int((selected & arms).sum()),
                   'headSkinPolygons': int((selected & face).sum()),
                   'handSkinPolygons': int((selected & hands).sum()),
                   'chestSkinPolygons': int((selected & chest).sum()),
                   'verticesUnchanged': True, 'uvUnchanged': True,
                   'maskVisuallyVerified': False,
                   'limitations': 'Color/spatial mask needs close visual review; no garment-layer separation or rig created.'})
editable = out / 'chapeleiro_skin_polish.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', export_yup=True)
record = {**source, 'model': str(model), 'modelSha256': sha(model),
          'editableBlend': str(editable), 'editableBlendSha256': sha(editable),
          'geometryParentSha256': source['modelSha256'],
          'originalDownloadedModelSha256': source.get('originalDownloadedModelSha256', source['modelSha256']),
          'method': 'new_Tripo_full_model_local_skin_material_polish',
          'materialAudit': audits, 'status': 'generated_awaiting_visual_review',
          'fidelityVerified': False, 'motionVerified': False, 'completedOutfit': False,
          'additionalCreditsConsumed': 0}
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('LOCAL_SKIN_POLISH_SAVED', json.dumps(audits))
