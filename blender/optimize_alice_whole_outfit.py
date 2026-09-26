"""Make a reversible whole-outfit reduction study; never extract garment faces.

The original Blender master remains immutable. This is a reduction candidate,
not a claim of deformation-ready retopology or finished cloth simulation.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--ratio', type=float, default=.16)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
source = json.loads(Path(args.generation).read_text(encoding='utf-8'))
if source.get('variant') != 'alice_chapeleiro' or source.get('reusedGeometry') is not False:
    raise ValueError('Expected the single new complete Tripo Chapeleiro.')
if source.get('sourcePhotoSha256') != '69e81154d4fe0903f76883a049ea9c3e2e9f16f57e488cf2075a0d7158e8feab':
    raise ValueError('Use the full outfit reference, not a numbered internal layer.')
if not .05 <= args.ratio <= .8:
    raise ValueError('Reduction ratio out of reviewable range.')
for path, expected in [('model', 'modelSha256'), ('editableBlend', 'editableBlendSha256')]:
    if digest(source[path]) != source[expected]:
        raise ValueError(f'Changed source: {path}')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Use a new directory to preserve earlier candidates.')
bpy.ops.wm.open_mainfile(filepath=source['editableBlend'])
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(objects) != 1:
    raise ValueError('Expected the complete single-mesh master, without cut layer studies.')
obj = objects[0]
mesh = obj.data
mesh.calc_loop_triangles()
original_triangles = len(mesh.loop_triangles)
positions = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
mesh.vertices.foreach_get('co', positions)
positions = positions.reshape(-1, 3)
world = np.asarray(obj.matrix_world, dtype=np.float32)
world_positions = positions @ world[:3, :3].T + world[:3, 3]
x, y, z = world_positions.T
# Protect small facial and finger features from uniform collapse. This is a
# density guide only, not anatomical topology or skinning weights.
face = (z > .78) & (z < .91) & (np.abs(x) < .06) & (y < -.002)
hands = (z > .42) & (z < .54) & (np.abs(x) > .15)
neck = (z > .75) & (z < .82) & (np.abs(x) < .055)
group = obj.vertex_groups.new(name='Reduction priority / face hands neckline')
group.add(np.flatnonzero(face | hands | neck).tolist(), 1.0, 'REPLACE')
mod = obj.modifiers.new('Whole outfit reduction / review candidate', 'DECIMATE')
mod.decimate_type = 'COLLAPSE'
mod.ratio = args.ratio
mod.use_collapse_triangulate = True
mod.vertex_group = group.name
mod.vertex_group_factor = 8.0
mod.invert_vertex_group = True
editable = out / 'chapeleiro_whole_reduction.blend'
# Save the editable source with a live modifier; no destructive apply here.
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = obj.evaluated_get(depsgraph)
low = evaluated.to_mesh()
low.calc_loop_triangles()
low_positions = np.empty(len(low.vertices) * 3, dtype=np.float32)
low.vertices.foreach_get('co', low_positions)
low_positions = low_positions.reshape(-1, 3)
low_tri = [tuple(t.vertices) for t in low.loop_triangles]
bvh = BVHTree.FromPolygons(low_positions.tolist(), low_tri, all_triangles=True)
# Sample the high-poly vertices AND face centers so unchanged retained vertices
# alone cannot make a heavily flattened detail report zero error.
step = max(1, len(positions) // 10000)
samples = list(positions[::step])
face_step = max(1, len(mesh.polygons) // 10000)
samples.extend(np.mean(positions[list(p.vertices)], axis=0) for p in list(mesh.polygons)[::face_step])
distances = np.asarray([bvh.find_nearest(p)[3] for p in samples])
uv = np.empty(len(low.loops) * 2, dtype=np.float32)
low.uv_layers.active.data.foreach_get('uv', uv)
audit = {'originalVertices': len(mesh.vertices), 'originalTriangles': original_triangles,
         'reducedVertices': len(low.vertices), 'reducedTriangles': len(low.loop_triangles),
         'ratioRequested': args.ratio, 'ratioActual': len(low.loop_triangles) / original_triangles,
         'wholeOutfitKept': True, 'garmentFaceExtractionUsed': False,
         'sourceUvAtlasPreserved': True, 'uvFinite': bool(np.isfinite(uv).all()),
         'textures': [{'name': i.name, 'size': list(i.size)} for i in bpy.data.images if i.packed_file],
         'sourceBounds': [world_positions.min(axis=0).tolist(), world_positions.max(axis=0).tolist()],
         'candidateBounds': [(low_positions @ world[:3,:3].T + world[:3,3]).min(axis=0).tolist(),
                             (low_positions @ world[:3,:3].T + world[:3,3]).max(axis=0).tolist()],
         'highToLowDistance': {'samples': len(samples), 'p50': float(np.quantile(distances, .5)),
                               'p95': float(np.quantile(distances, .95)), 'p99': float(np.quantile(distances, .99)),
                               'max': float(distances.max()), 'units': 'Blender source units; model height 0.979919'},
         'deformationTopologyApproved': False, 'normalRebakeCompleted': False,
         'limitations': ['Collapse reduction is a first candidate, not anatomical retopology.',
                        'Existing tangent normal map retained for comparison; rebake requires review.',
                        'No rig, internal layers or collision approval implied.']}
evaluated.to_mesh_clear()
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True)
record = {**source, 'method': 'whole_Tripo_outfit_non_destructive_reduction_study',
          'model': str(model), 'modelSha256': digest(model), 'editableBlend': str(editable),
          'editableBlendSha256': digest(editable), 'geometryParentSha256': source['modelSha256'],
          'originalDownloadedModelSha256': source.get('originalDownloadedModelSha256', source.get('geometryParentSha256')),
          'vertices': audit['reducedVertices'], 'triangles': audit['reducedTriangles'],
          'optimizationAudit': audit, 'status': 'generated_awaiting_visual_review',
          'workflow': 'Preserve the complete exterior; optimize and bake locally. Photos describe missing internal layers.',
          'fidelityVerified': False, 'motionVerified': False, 'completedOutfit': False,
          'additionalCreditsConsumed': 0}
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'optimization_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
print('WHOLE_OUTFIT_REDUCTION', json.dumps(audit))
