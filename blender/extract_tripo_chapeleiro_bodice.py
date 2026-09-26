"""Extract editable bodice/sleeve study from the authorized new full Tripo model.

The outer scan has no hidden garment surfaces. This preserves its geometry and
atlas, and records incomplete cuts rather than pretending they are finished layers.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--stage-plan', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
source = json.loads(Path(args.generation).read_text(encoding='utf-8'))
plan = json.loads(Path(args.stage_plan).read_text(encoding='utf-8'))
stage = next(s for s in plan['stages'] if s['id'] == 'alice_chapeleiro_stage_02')
if source.get('variant') != stage['variant'] or not source.get('studioModelId') or source.get('reusedGeometry') is not False:
    raise ValueError('Requires the authorized newly generated Chapeleiro outfit.')
for file, digest in [(source['model'], source['modelSha256']),
                     (source['editableBlend'], source['editableBlendSha256']),
                     (stage['sourcePhoto'], stage['sourcePhotoSha256'])]:
    if sha(file) != digest:
        raise ValueError('Source geometry or original layer photo changed.')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Choose a new extraction version directory.')
bpy.ops.wm.open_mainfile(filepath=source['editableBlend'])
originals = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(originals) != 1:
    raise ValueError('Expected the original single-mesh Tripo scan.')
original = originals[0]
mesh = original.data
positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
mesh.vertices.foreach_get('co', positions)
positions = positions.reshape(-1, 3)
world = np.asarray(original.matrix_world, dtype=np.float32)
positions = positions @ world[:3, :3].T + world[:3, 3]
indices = np.empty(len(mesh.loops), dtype=np.int32)
counts = np.empty(len(mesh.polygons), dtype=np.int32)
mesh.polygons.foreach_get('loop_total', counts)
if not np.all(counts == 3):
    raise ValueError('Extraction requires the original triangular scan topology.')
mesh.loops.foreach_get('vertex_index', indices)
faces = indices.reshape(-1, 3)
centers = positions[faces].mean(axis=1)
uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
mesh.uv_layers.active.data.foreach_get('uv', uvs)
uvs = uvs.reshape(-1, 3, 2)
material_indices = np.empty(len(mesh.polygons), dtype=np.int32)
mesh.polygons.foreach_get('material_index', material_indices)
base_material = mesh.materials[0]
shader = next(n for n in base_material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
color_image = next(l.from_node.image for l in shader.inputs['Base Color'].links if l.from_node.type == 'TEX_IMAGE')
pixels = np.empty(color_image.size[0] * color_image.size[1] * color_image.channels, dtype=np.float32)
color_image.pixels.foreach_get(pixels)
pixels = pixels.reshape(color_image.size[1], color_image.size[0], color_image.channels)
uv = uvs[:, 0]
u = np.clip((uv[:, 0] * (color_image.size[0] - 1)).astype(np.int32), 0, color_image.size[0] - 1)
v = np.clip((uv[:, 1] * (color_image.size[1] - 1)).astype(np.int32), 0, color_image.size[1] - 1)
color = pixels[v, u, :3]
x, y, z = centers.T
# Bounds are fitted to this actual scan, not a generic replacement mannequin.
# Color removes hair only at the neckline, not dark garment embroidery.
green = (color[:, 1] > color[:, 0] * 1.025) & (color[:, 1] > color[:, 2] * 1.025)
dark_hair = (color.mean(axis=1) < .07) & ~green
body = (np.abs(x) < .073) & (z > .588 + np.abs(x) * .45) & (z < .742 + np.abs(x) * .32)
body &= (y < .045) & ~((z > .706) & dark_hair)
# The top portion behind the character is occluded by hair in the full scan.
body &= (y < .015) | (z < .696)
sleeves = (np.abs(x) > .072) & (np.abs(x) < .143) & (z > .684) & (z < .802) & (np.abs(y) < .068)
sleeves &= ~((z > .738) & dark_hair & (np.abs(x) < .09))
masks = {'Corpete verde / scan exterior': body & ~sleeves,
         'Manga esquerda / scan exterior': sleeves & (x > 0),
         'Manga direita / scan exterior': sleeves & (x < 0)}
objects = []
audit = []
for name, mask in masks.items():
    selected = np.flatnonzero(mask)
    if selected.size < 100:
        raise ValueError('Extraction mask did not identify a real garment region: ' + name)
    vertex_ids, remapped = np.unique(faces[selected], return_inverse=True)
    remapped = remapped.ravel()
    part = bpy.data.meshes.new(name)
    # foreach_set preserves the original scan positions/UVs without re-triangulation.
    part.vertices.add(len(vertex_ids))
    part.vertices.foreach_set('co', positions[vertex_ids].ravel())
    part.loops.add(len(remapped))
    part.loops.foreach_set('vertex_index', remapped.astype(np.int32))
    part.polygons.add(len(selected))
    part.polygons.foreach_set('loop_start', np.arange(len(selected), dtype=np.int32) * 3)
    part.polygons.foreach_set('loop_total', np.full(len(selected), 3, dtype=np.int32))
    for material in mesh.materials:
        part.materials.append(material)
    part.polygons.foreach_set('material_index', material_indices[selected])
    part.polygons.foreach_set('use_smooth', np.ones(len(selected), dtype=np.bool_))
    layer = part.uv_layers.new(name=mesh.uv_layers.active.name)
    layer.data.foreach_set('uv', uvs[selected].ravel())
    part.update(calc_edges=True)
    obj = bpy.data.objects.new(name, part)
    bpy.context.scene.collection.objects.link(obj)
    obj['original_layer_photo_sha256'] = stage['sourcePhotoSha256']
    obj['geometry_parent_sha256'] = source['modelSha256']
    obj['layer_complete'] = False
    objects.append(obj)
    audit.append({'component': name, 'vertices': len(vertex_ids), 'triangles': len(selected),
                  'positionsPreserved': True, 'uvPreserved': True,
                  'boundaryNeedsRefinement': True, 'hiddenSurfacePresent': False,
                  'rigged': False, 'fidelityVerified': False})
bpy.data.objects.remove(original, do_unlink=True)
bpy.context.scene['source_photo_sha256'] = stage['sourcePhotoSha256']
editable = out / 'chapeleiro_bodice_extraction.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', export_yup=True)
record = {**source, 'sourcePhoto': stage['sourcePhoto'], 'sourcePhotoSha256': stage['sourcePhotoSha256'],
          'generationPhoto': source['sourcePhoto'], 'generationPhotoSha256': source['sourcePhotoSha256'],
          'sourceViews': source['sourceViews'], 'model': str(model), 'modelSha256': sha(model),
          'editableBlend': str(editable), 'editableBlendSha256': sha(editable),
          'geometryParentSha256': source['modelSha256'], 'extractionAudit': audit,
          'vertices': sum(item['vertices'] for item in audit),
          'triangles': sum(item['triangles'] for item in audit),
          'materialAudit': [], 'localWorkStatus': 'bodice_and_sleeves_boundary_refinement_in_progress',
          'method': 'authorized_new_Tripo_variant_local_bodice_sleeve_extraction',
          'status': 'generated_awaiting_visual_review', 'fidelityVerified': False,
          'motionVerified': False, 'completedOutfit': False, 'countsAsFinishedLayer': False,
          'additionalCreditsConsumed': 0,
          'limitations': ['Exterior extraction only; back obscured by hair, lining and cut boundaries need reconstruction.',
                          'Local masks require actual front, side, back and threequarter review against sheet 2.',
                          'No rig, cloth simulation or collision approval.']}
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('ACTUAL_BODICE_SLEEVES_EXTRACTED', json.dumps(audit))
