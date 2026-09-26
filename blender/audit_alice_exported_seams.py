"""Measure actual exported sleeve joins and stretch at every exported sample time.

This is a skin/deformation audit. It never approves artistic fidelity or cloth
collisions and does not infer success from settings or Blender vertex groups.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
generation = json.loads(Path(args.generation).read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
if not generation.get('rigPresent') or not generation.get('sleeveConstructionAudit'):
    raise ValueError('Requires the recorded new sleeves and shared rig.')
if sha(generation['model']) != generation['modelSha256'] or sha(generation['sourcePhoto']) != generation['sourcePhotoSha256']:
    raise ValueError('The actual model or original layer photograph changed.')
content = Path(generation['model']).read_bytes()
json_size = struct.unpack_from('<I', content, 12)[0]
doc = json.loads(content[20:20 + json_size])
binary_start = 20 + json_size + 8

def sample_times(animation):
    values = set()
    for accessor_id in {s['input'] for s in animation['samplers']}:
        accessor = doc['accessors'][accessor_id]
        if accessor['type'] != 'SCALAR' or accessor['componentType'] != 5126:
            raise ValueError('Unsupported exported animation timing.')
        view = doc['bufferViews'][accessor['bufferView']]
        offset = binary_start + view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        stride = view.get('byteStride', 4)
        values.update(struct.unpack_from('<f', content, offset + i * stride)[0] for i in range(accessor['count']))
    return sorted(values)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=generation['model'])
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
if len(rigs) != 1:
    raise ValueError('The exported layer does not use one shared skeleton.')
rig = rigs[0]
shapes = {b.custom_shape for b in rig.pose.bones if b.custom_shape}
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in shapes]
body = next(o for o in meshes if o.name.startswith('Corpete /'))
rig.animation_data_create()
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()

def points(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', coords)
    matrix = np.array(evaluated.matrix_world, dtype=np.float64)
    coords = coords.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    evaluated.to_mesh_clear()
    return coords

rest = {o.name: points(o, bpy.context.evaluated_depsgraph_get()) for o in meshes}

def nearest_indices(obj, coordinates):
    cloud = rest[obj.name]
    tree = KDTree(len(cloud))
    for index, point in enumerate(cloud):
        tree.insert(Vector(point), index)
    tree.balance()
    matches = [tree.find(Vector(p)) for p in coordinates]
    error = max(m[2] for m in matches)
    if error > .000002:
        raise ValueError('An exported sewn endpoint changed: ' + obj.name + ' / ' + str(error))
    return np.array([m[1] for m in matches], dtype=np.int32)

seams = []
for sleeve in generation['sleeveConstructionAudit']:
    label = sleeve['sleeve']
    sign = 1 if label == 'L' else -1
    puff = next(o for o in meshes if o.name.startswith('Manga ') and rest[o.name][:, 0].mean() * sign > 0)
    cuff = next(o for o in meshes if o.name.startswith('Punho ' + label + ' / tecido'))
    for kind, coordinates, other in [('root', sleeve['rootRestPoints'], body),
                                     ('cuff', sleeve['cuffRestPoints'], cuff)]:
        seams.append({'label': label + '_' + kind, 'a': puff, 'b': other,
                      'indicesA': nearest_indices(puff, coordinates),
                      'indicesB': nearest_indices(other, coordinates)})
tracked = list({o for seam in seams for o in [seam['a'], seam['b']]})
edge_data = {}
for obj in tracked:
    vertices = rest[obj.name]
    edges = np.empty(len(obj.data.edges) * 2, dtype=np.int32)
    obj.data.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    lengths = np.linalg.norm(vertices[edges[:, 0]] - vertices[edges[:, 1]], axis=1)
    edge_data[obj.name] = (edges, lengths)
rig.data.pose_position = 'POSE'
fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
clips = []
for animation in doc['animations']:
    action = next(a for a in bpy.data.actions if a.name == animation['name'])
    rig.animation_data.action = action
    if action.slots:
        rig.animation_data.action_slot = action.slots[0]
    times = sample_times(animation)
    if abs(action.frame_range[0] - times[0] * fps) > .0001:
        raise ValueError('Imported action timing does not match actual exported samples.')
    maxima = {seam['label']: {'maxGapMetres': 0.0, 'worstTimeSeconds': 0.0} for seam in seams}
    stretch = {obj.name: {'maximumEdgeStretch': 1.0, 'maximum95Percentile': 1.0,
                           'maximumFractionAbove150Percent': 0.0} for obj in tracked}
    for seconds in times:
        frame = seconds * fps
        bpy.context.scene.frame_set(math.floor(frame), subframe=frame % 1)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        poses = {obj.name: points(obj, dg) for obj in tracked}
        if not all(np.isfinite(v).all() for v in poses.values()):
            raise ValueError('Nonfinite evaluated exported skin.')
        for seam in seams:
            distance = np.linalg.norm(poses[seam['a'].name][seam['indicesA']] - poses[seam['b'].name][seam['indicesB']], axis=1)
            gap = float(distance.max(initial=0))
            if gap > maxima[seam['label']]['maxGapMetres']:
                maxima[seam['label']].update(maxGapMetres=gap, worstTimeSeconds=seconds)
        for obj in tracked:
            edges, rest_lengths = edge_data[obj.name]
            lengths = np.linalg.norm(poses[obj.name][edges[:, 0]] - poses[obj.name][edges[:, 1]], axis=1)
            valid = rest_lengths > .00001
            ratios = lengths[valid] / rest_lengths[valid]
            result = stretch[obj.name]
            maximum = float(ratios.max(initial=1))
            if maximum > result['maximumEdgeStretch']:
                index = np.flatnonzero(valid)[int(ratios.argmax())]
                result.update(maximumEdgeStretch=maximum,
                              worstEdge={'indices': edges[index].tolist(), 'timeSeconds': seconds,
                                         'restLengthMetres': float(rest_lengths[index]),
                                         'deformedLengthMetres': float(lengths[index]),
                                         'restPoints': rest[obj.name][edges[index]].tolist(),
                                         'deformedPoints': poses[obj.name][edges[index]].tolist()})
            result['maximum95Percentile'] = max(result['maximum95Percentile'], float(np.percentile(ratios, 95)))
            result['maximumFractionAbove150Percent'] = max(result['maximumFractionAbove150Percent'], float((ratios > 1.5).mean()))
    clips.append({'clip': animation['name'], 'exportedSampleCount': len(times), 'seams': maxima,
                  'edgeStretch': stretch, 'motionVerified': False, 'clothCollisionVerified': False})
    print('EXPORTED_SEAMS_MEASURED', animation['name'].split(' /')[0], len(times),
          'maxGap', max(v['maxGapMetres'] for v in maxima.values()), flush=True)
report = {'modelSha256': generation['modelSha256'], 'sourcePhotoSha256': generation['sourcePhotoSha256'],
          'allExportedSampleTimesChecked': True, 'clips': clips,
          'sewnEndpointContinuityVerified': all(v['maxGapMetres'] < .00001 for c in clips for v in c['seams'].values()),
          'motionVerified': False, 'fidelityVerified': False, 'clothCollisionVerified': False,
          'limitations': ['Only the explicitly named sleeve/cuff joins are checked.',
                          'Exported sample times do not prove all interpolated frames or transitions.',
                          'Endpoint continuity does not prove collision-free or natural cloth simulation.',
                          'Actual deformation, silhouettes, texture and layering still require visual review.']}
Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('EXPORTED_SEAM_AUDIT_SAVED', report['sewnEndpointContinuityVerified'], flush=True)
