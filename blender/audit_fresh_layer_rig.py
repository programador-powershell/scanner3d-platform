"""Audit every new garment component; numerical motion is not visual approval.

Run inside Blender against the editable file recorded by the reconstruction.
The report never approves cloth collisions or artistic fidelity automatically.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--blend', required=True)
parser.add_argument('--layer', required=True)
parser.add_argument('--role', choices=['fitted', 'loose'], required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
generation = json.loads(Path(args.generation).read_text(encoding='utf-8'))
digest = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
if generation.get('reusedGeometry') is not False:
    raise ValueError('Only newly constructed geometry may be audited.')
if digest(generation['sourcePhoto']) != generation['sourcePhotoSha256']:
    raise ValueError('The original layer photograph changed.')
if digest(generation['model']) != generation['modelSha256']:
    raise ValueError('The generated model changed.')
if Path(args.blend).resolve() != Path(generation['editableBlend']).resolve() or digest(args.blend) != generation['editableBlendSha256']:
    raise ValueError('The editable file is not the recorded fresh model.')
bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
bone_shapes = {bone.custom_shape for obj in bpy.context.scene.objects if obj.type == 'ARMATURE'
               for bone in obj.pose.bones if bone.custom_shape}
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj not in bone_shapes]
if not meshes:
    raise ValueError('No garment geometry to audit.')
rigs = {modifier.object for obj in meshes for modifier in obj.modifiers
        if modifier.type == 'ARMATURE' and modifier.object}
components = []
for obj in meshes:
    armatures = [m for m in obj.modifiers if m.type == 'ARMATURE' and m.object]
    rig = armatures[0].object if len(armatures) == 1 else None
    bone_groups = {g.index for g in obj.vertex_groups if rig and g.name in rig.data.bones}
    sums = [sum(g.weight for g in vertex.groups if g.group in bone_groups)
            for vertex in obj.data.vertices]
    cloth = [m for m in obj.modifiers if m.type == 'CLOTH']
    components.append({
        'mesh': obj.name, 'layer': args.layer, 'role': args.role,
        'rig': rig.name if rig else None, 'vertices': len(sums),
        'unweightedVertices': sum(value < 1e-6 for value in sums),
        'maxWeightError': max((abs(value - 1) for value in sums), default=1),
        'clothModifiers': [{
            'name': m.name, 'pinGroup': m.settings.vertex_group_mass,
            'collisionsEnabled': m.collision_settings.use_collision,
            'selfCollisionEnabled': m.collision_settings.use_self_collision,
            'baked': m.point_cache.is_baked,
        } for m in cloth],
        'clothSimulationConfigured': bool(cloth),
    })

motions = []
if len(rigs) == 1:
    rig = next(iter(rigs))
    rig.data.pose_position = 'POSE'
    rig.animation_data_create()
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    root = next(bone for bone in rig.pose.bones if bone.parent is None)
    for required in ['Walk', 'Run', 'Jump', 'Attack']:
        matches = [action for action in bpy.data.actions if action.name.startswith(required + ' /')]
        clip = {'requiredMotion': required, 'found': len(matches) == 1,
                'visibleQualityVerified': False, 'collisionVerified': False}
        if len(matches) == 1:
            action = matches[0]
            rig.animation_data.action = action
            if action.slots:
                rig.animation_data.action_slot = action.slots[0]
            first, last = action.frame_range
            frames = sorted({round(first + (last - first) * i / 6) for i in range(7)})
            samples = {obj.name: [] for obj in meshes}
            for frame in frames:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()
                root_inverse = (rig.matrix_world @ root.matrix).inverted()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                for obj in meshes:
                    evaluated = obj.evaluated_get(depsgraph)
                    mesh = evaluated.to_mesh()
                    indices = sorted({round((len(mesh.vertices) - 1) * i / 15) for i in range(16)})
                    points = [root_inverse @ evaluated.matrix_world @ mesh.vertices[i].co for i in indices]
                    if not all(math.isfinite(value) for point in points for value in point):
                        raise ValueError(f'Invalid evaluated geometry: {obj.name}, {required}, {frame}')
                    samples[obj.name].append(points)
                    evaluated.to_mesh_clear()
            clip.update(name=action.name, frames=frames,
                        componentDeformation=[{
                            'mesh': name,
                            'maxRootRelativeDisplacementMetres': max(
                                ((point - initial).length for pose in poses[1:]
                                 for point, initial in zip(pose, poses[0])), default=0),
                        } for name, poses in samples.items()])
        motions.append(clip)

colliders = [obj.name for obj in bpy.context.scene.objects
             if any(m.type == 'COLLISION' for m in obj.modifiers)]
report = {
    'layer': args.layer, 'role': args.role,
    'sourcePhotoSha256': generation['sourcePhotoSha256'],
    'modelSha256': generation['modelSha256'], 'blendSha256': digest(args.blend),
    'components': components, 'sharedRigCount': len(rigs), 'motions': motions,
    'colliders': colliders,
    'allComponentsSkinned': len(rigs) == 1 and all(
        c['rig'] and c['unweightedVertices'] == 0 and c['maxWeightError'] < 1e-5
        for c in components),
    'allRequiredClipsPresent': len(motions) == 4 and all(c['found'] for c in motions),
    'clothFollowingVerified': False, 'bodyCollisionVerified': False,
    'interLayerCollisionVerified': False, 'fidelityVerified': False,
    'readyForGameplay': False,
    'limitations': [
        'This audit covers only the named layer and components actually in this file.',
        'Seven sampled poses and sixteen vertices per component do not prove full deformation quality.',
        'Root-relative displacement excludes character translation; rigid fittings may correctly remain stationary.',
        'Cloth settings and existing colliders do not prove collision-free simulation.',
        'Loose skirts, linings, aprons, sleeves and accessories require visual motion and collision tests.',
    ],
}
Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: report[key] for key in ['layer', 'allComponentsSkinned',
      'allRequiredClipsPresent', 'readyForGameplay']}))
