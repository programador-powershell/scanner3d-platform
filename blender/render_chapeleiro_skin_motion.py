"""Render exported GLB poses and measure edge stretch, without approving cloth."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
record = json.loads(Path(args.generation).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
if not record.get('rigPresent') or record.get('studioModelId') != '32254621-cdf9-43bd-8297-54446796d892':
    raise ValueError('Requires the new shared Chapeleiro rig.')
if sha(record['model']) != record['modelSha256'] or sha(record['sourcePhoto']) != record['sourcePhotoSha256']:
    raise ValueError('Changed actual GLB or original layer photograph.')
out = Path(args.output)
if out.exists():
    raise ValueError('Preserve earlier motion evidence: use a new directory.')
out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=record['model'])
rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
if len(rigs) != 1:
    raise ValueError('All components must share one imported skeleton.')
rig = rigs[0]
bone_shapes = {b.custom_shape for b in rig.pose.bones if b.custom_shape}
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o not in bone_shapes]
if len(meshes) != record['riggedComponents']:
    raise ValueError('Exported component count changed.')
rig.animation_data_create()
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()

def evaluated_points(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    values = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', values)
    points = values.reshape(-1, 3)
    matrix = np.array(evaluated.matrix_world, dtype=np.float64)
    points = points @ matrix[:3, :3].T + matrix[:3, 3]
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    evaluated.to_mesh_clear()
    return points, edges

rest = {}
dg = bpy.context.evaluated_depsgraph_get()
for obj in meshes:
    points, edges = evaluated_points(obj, dg)
    lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
    rest[obj.name] = (edges, lengths)
rig.data.pose_position = 'POSE'
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.resolution_x = 520
scene.render.resolution_y = 620
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.world = bpy.data.worlds.new('Actual exported skin inspection')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .35, .35, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
center, span = Vector((0, 0, .710)), .54
front, right = Vector((0, -1, 0)), Vector((1, 0, 0))
camera_data = bpy.data.cameras.new('Fixed motion comparison camera')
camera = bpy.data.objects.new('Fixed motion comparison camera', camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = 'ORTHO'
camera_data.ortho_scale = span
camera_data.clip_start = .001
camera.location = center + (front + right * .50 + Vector((0, 0, .12))).normalized() * 1.8
camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
for name, direction, energy in [('Key', front + right * .7 + Vector((0, 0, 1)), 25),
                                ('Fill', front - right + Vector((0, 0, .4)), 15),
                                ('Back', -front + Vector((0, 0, .6)), 25)]:
    light = bpy.data.lights.new(name, 'AREA')
    light.energy, light.size = energy * span ** 2, span * 1.5
    lamp = bpy.data.objects.new(name, light)
    scene.collection.objects.link(lamp)
    lamp.location = center + direction.normalized() * span * 2
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
clips = []
for label in ['Walk', 'Run', 'Jump', 'Attack']:
    actions = [a for a in bpy.data.actions if a.name.startswith(label + ' /')]
    if len(actions) != 1:
        raise ValueError('The actual imported GLB lacks a unique required clip.')
    action = actions[0]
    rig.animation_data.action = action
    if action.slots:
        rig.animation_data.action_slot = action.slots[0]
    first, last = action.frame_range
    poses = []
    for index, fraction in enumerate([0, .33, .66]):
        frame = first + (last - first) * fraction
        scene.frame_set(math.floor(frame), subframe=frame % 1)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        measurements = []
        for obj in meshes:
            points, edges = evaluated_points(obj, dg)
            rest_edges, rest_lengths = rest[obj.name]
            if not np.array_equal(edges, rest_edges) or not np.isfinite(points).all():
                raise ValueError('Changed topology or invalid evaluated skin coordinates.')
            lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
            valid = rest_lengths > .00001
            ratios = lengths[valid] / rest_lengths[valid]
            measurements.append({'component': obj.name, 'maximumEdgeStretch': float(ratios.max(initial=1)),
                                 'edgeStretch95Percentile': float(np.percentile(ratios, 95)) if ratios.size else 1,
                                 'fractionOfEdgesAbove150Percent': float((ratios > 1.5).mean()) if ratios.size else 0,
                                 'bounds': [points.min(axis=0).tolist(), points.max(axis=0).tolist()]})
        file = out / (label.lower() + '_' + str(index + 1) + '.png')
        scene.render.filepath = str(file)
        bpy.ops.render.render(write_still=True)
        poses.append({'frame': frame, 'render': str(file.resolve()), 'renderSha256': sha(file),
                      'componentMeasurements': measurements})
        print('EXPORTED_SKIN_RENDERED', label, index + 1, flush=True)
    clips.append({'clip': action.name, 'frameRange': [first, last], 'poses': poses,
                  'visibleQualityVerified': False, 'clothCollisionVerified': False})
report = {'modelSha256': record['modelSha256'], 'sourcePhotoSha256': record['sourcePhotoSha256'],
          'sourcePhoto': record['sourcePhoto'], 'exportedMeshCount': len(meshes), 'clips': clips,
          'camera': {'position': list(camera.location), 'target': list(center), 'orthoScale': span},
          'status': 'awaiting_visual_motion_review', 'motionVerified': False,
          'fidelityVerified': False, 'clothCollisionVerified': False,
          'limitations': ['Three sampled poses per clip do not prove all-frame quality.',
                          'Edge stretch flags require inspection; tiny edge ratios can amplify scan irregularities.',
                          'This is the exported sheet-2 garment only; there is no approved body/cloth collision simulation.']}
(out / 'motion_comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('EXPORTED_SKIN_MOTION_EVIDENCE_SAVED', out, flush=True)
