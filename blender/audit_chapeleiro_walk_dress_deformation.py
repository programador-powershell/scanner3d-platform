"""Measure how the intact dressed character deforms during the authored Walk."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
generation = json.loads(Path(args.generation).read_text(encoding='utf-8'))

digest = hashlib.sha256()
with Path(generation['editableBlend']).open('rb') as source:
    for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
        digest.update(block)
assert digest.hexdigest() == generation['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=generation['editableBlend'])
scene = bpy.context.scene
whole = bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
rig = next(mod.object for mod in whole.modifiers if mod.type == 'ARMATURE')
for modifier in whole.modifiers:
    if modifier.type != 'ARMATURE':
        modifier.show_viewport = False
rig.data.pose_position = 'POSE'
rig.animation_data.action = None
tracks = []
for track in rig.animation_data.nla_tracks:
    track.mute = not track.name.startswith('Walk /')
    if not track.mute:
        tracks.append(track.name)
assert len(tracks) == 1
guides = next(obj for obj in scene.objects if obj.type == 'CURVES' and 'dynamics guides' in obj.name)
node = next(node for node in guides.modifiers[0].node_group.nodes if node.bl_idname == 'GeometryNodeGroup')
node.inputs['Mode'].default_value = 'Animation'

mask = whole.data.attributes['alice_original_hair_review_mask']
material_vertices = {}
for polygon in whole.data.polygons:
    if mask.data[polygon.index].value:
        continue
    material_vertices.setdefault(polygon.material_index, set()).update(polygon.vertices)
material_vertices = {index: np.fromiter(sorted(indices), dtype=np.int32)
                     for index, indices in material_vertices.items()}
assert material_vertices

poses = {}
for frame in (1, 21, 42):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = whole.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    assert len(mesh.vertices) == len(whole.data.vertices)
    points = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', points)
    points = points.reshape(-1, 3)
    transform = np.asarray(evaluated.matrix_world, dtype=np.float32)
    poses[frame] = points @ transform[:3, :3].T + transform[:3, 3]
    evaluated.to_mesh_clear()

rows = []
for index, vertices in material_vertices.items():
    first = poses[1][vertices]
    mid = np.linalg.norm(poses[21][vertices] - first, axis=1)
    last = np.linalg.norm(poses[42][vertices] - first, axis=1)
    material = whole.material_slots[index].material if index < len(whole.material_slots) else None
    rows.append(dict(materialIndex=index, materialName=material.name if material else None,
                     vertexCount=len(vertices),
                     walk21MedianDisplacementM=float(np.median(mid)),
                     walk21MaxDisplacementM=float(mid.max()),
                     walk42MedianDisplacementM=float(np.median(last)),
                     walk42MaxDisplacementM=float(last.max())))

# A shared material does not imply that its lace, panels and skirt tiers are
# connected. Inspect each topological island separately instead of using the
# aggregate material displacement as proof that every piece follows the rig.
dress_index = next(index for index, slot in enumerate(whole.material_slots)
                   if slot.material and 'dress UV 4K' in slot.material.name)
parent = np.arange(len(whole.data.vertices), dtype=np.int32)

def root(index):
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index

for polygon in whole.data.polygons:
    if polygon.material_index != dress_index or mask.data[polygon.index].value:
        continue
    anchor = polygon.vertices[0]
    for vertex in polygon.vertices[1:]:
        parent[root(vertex)] = root(anchor)
islands = {}
for vertex in material_vertices[dress_index]:
    islands.setdefault(root(int(vertex)), []).append(int(vertex))
components = []
for vertices in islands.values():
    indices = np.asarray(vertices, np.int32)
    displacement = np.linalg.norm(poses[21][indices] - poses[1][indices], axis=1)
    weighted = sum(any(group.weight > 0 for group in whole.data.vertices[int(vertex)].groups)
                   for vertex in indices)
    components.append(dict(vertexCount=len(indices), weightedVertices=weighted,
                           medianWalk21DisplacementM=float(np.median(displacement)),
                           maxWalk21DisplacementM=float(displacement.max())))
components.sort(key=lambda item: item['vertexCount'], reverse=True)

report = dict(sourceGeneration=args.generation, sourceBlendSha256=digest.hexdigest(),
              actionTrack=tracks[0], frames=[1, 21, 42],
              materialGroups=rows, dressComponentCount=len(components),
              dressComponentsAtLeast100Vertices=[item for item in components if item['vertexCount'] >= 100],
              smallerDressComponentCount=sum(item['vertexCount'] < 100 for item in components),
              unweightedDressComponentCount=sum(item['weightedVertices'] < item['vertexCount'] for item in components),
              lowMotionDressComponentCount=sum(item['maxWalk21DisplacementM'] < .001 for item in components),
              smallestDressComponentMotionM=min(item['maxWalk21DisplacementM'] for item in components),
              scope='Authored kinematic Walk on intact body/dress, excluding original hair faces; no cloth physics or collision claim',
              published=False)
Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print('WALK_DRESS_DEFORMATION', json.dumps(report), flush=True)
