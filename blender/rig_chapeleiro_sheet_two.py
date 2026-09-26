"""Bind the actual new Tripo sheet-2 garment to one fitted motion skeleton.

FBXs supply only bones and motions. Their character meshes are discarded.
World-orientation retargeting handles the scan's A-pose instead of applying a
T-pose arm delta twice. Secondary keys are a deformation study, not cloth physics.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--motions', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
record = json.loads(Path(args.generation).read_text(encoding='utf-8'))
if (record.get('studioModelId') != '32254621-cdf9-43bd-8297-54446796d892'
        or record.get('reusedGeometry') is not False
        or record.get('method') != 'own_layer_2_cuff_lace_tab_and_filigree_refinement_of_new_Tripo'):
    raise ValueError('Requires the detailed layer reconstructed around the new authorized Tripo scan.')
for field in ['model', 'editableBlend', 'sourcePhoto']:
    if sha(record[field]) != record[field + 'Sha256']:
        raise ValueError('Changed parent geometry or original layer photograph.')
out = Path(args.output)
if out.exists():
    raise ValueError('Keep prior checkpoints: choose a new directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
garments = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(garments) != 40:
    raise ValueError('All forty actual sheet-2 components must be present.')
for obj in garments:
    if not obj.get('rig_role'):
        raise ValueError('Every component requires its actual attachment role.')
    bpy.context.view_layer.objects.active = obj
    # Apply thickness before skinning so the lining receives the same weights.
    for modifier in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)

motion_root = Path(args.motions)
sources, source_records = {}, []
for label, filename in [('Walk', 'Walking.fbx'), ('Run', 'Fast Run.fbx'),
                        ('Attack', 'One Hand Sword Combo.fbx')]:
    before = set(bpy.data.objects)
    file = motion_root / filename
    bpy.ops.import_scene.fbx(filepath=str(file))
    imported = set(bpy.data.objects) - before
    source = next(o for o in imported if o.type == 'ARMATURE')
    if not source.animation_data or not source.animation_data.action:
        raise ValueError('Supplied FBX has no motion.')
    source_records.append({'motion': label, 'file': str(file.resolve()), 'sha256': sha(file),
                           'sourceFps': bpy.context.scene.render.fps / bpy.context.scene.render.fps_base})
    source.name = 'Source skeleton only / ' + label
    for obj in imported:
        if obj is not source:
            bpy.data.objects.remove(obj, do_unlink=True)
    sources[label] = source

source = sources['Walk']
source_names = {b.name.split(':')[-1]: b.name for b in source.data.bones}
if any(set(b.name.split(':')[-1] for b in s.data.bones) != set(source_names) for s in sources.values()):
    raise ValueError('Motion skeleton names are incompatible; explicit remapping is required.')
source_rest = {name: source.matrix_world @ source.data.bones[full].matrix_local
               for name, full in source_names.items()}
scale = .685
offset = Vector((0, .002, 0))
heads = {name: source.matrix_world @ source.data.bones[full].head_local * scale + offset
         for name, full in source_names.items()}
tails = {name: source.matrix_world @ source.data.bones[full].tail_local * scale + offset
         for name, full in source_names.items()}
# Fit the shoulder/elbow/wrist chain to the actual A-pose and measured puff.
for side, sign in [('Left', 1), ('Right', -1)]:
    arm = Vector((sign * .076, .018, .780))
    elbow = Vector((sign * .131, .014, .652))
    wrist = Vector((sign * .180, .010, .535))
    old_wrist = heads[side + 'Hand'].copy()
    rotation = Vector((sign, 0, 0)).rotation_difference((wrist - elbow).normalized())
    for name in source_names:
        if name.startswith(side + 'Hand'):
            heads[name] = wrist + rotation @ (heads[name] - old_wrist)
            tails[name] = wrist + rotation @ (tails[name] - old_wrist)
    heads[side + 'Shoulder'].y = .018
    tails[side + 'Shoulder'] = arm
    heads[side + 'Arm'], tails[side + 'Arm'] = arm, elbow
    heads[side + 'ForeArm'], tails[side + 'ForeArm'] = elbow, wrist

data = bpy.data.armatures.new('Alice shared fitted bind skeleton / new Chapeleiro')
rig = bpy.data.objects.new('Alice / Chapeleiro shared rig', data)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for name in source_names:
    bone = data.edit_bones.new(name)
    bone.head, bone.tail = heads[name], tails[name]
    bone.align_roll(source_rest[name].to_3x3().col[2])
for name, full in source_names.items():
    original = source.data.bones[full]
    if original.parent:
        data.edit_bones[name].parent = data.edit_bones[original.parent.name.split(':')[-1]]

secondary = {}
for index, (theta, upper, lower) in enumerate([(-1, .630, .609), (-.53, .628, .602),
                                               (0, .624, .586), (.53, .628, .602), (1, .630, .609)]):
    name = 'DressTab_' + str(index)
    bone = data.edit_bones.new(name)
    bone.head = (-.002 + .063 * math.sin(theta), .002 - .067 * math.cos(theta), upper)
    bone.tail = bone.head + Vector((.004 * math.sin(theta), -.003 * math.cos(theta), lower - upper))
    bone.parent = data.edit_bones['Spine']
    secondary[name] = {'role': 'tasset_' + str(index), 'amplitudeDegrees': 4, 'phase': index * .37}
for side, sign, label in [('Left', 1, 'L'), ('Right', -1, 'R')]:
    for kind, length, y in [('CuffLace', .035, .019), ('Ribbon', .0115, -.014)]:
        name = kind + '_' + label
        bone = data.edit_bones.new(name)
        bone.head = (sign * .104, y, .733 if kind == 'Ribbon' else .731)
        bone.tail = bone.head + Vector((sign * .003, 0, -length))
        bone.parent = data.edit_bones[side + 'Arm']
        secondary[name] = {'role': ('lace_' if kind == 'CuffLace' else 'ribbon_') + label,
                            'amplitudeDegrees': 2 if kind == 'CuffLace' else 5,
                            'phase': .4 if label == 'L' else 1.5}
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True
rig['bind_geometry_sha256'] = record['modelSha256']
rig['source_studio_id'] = record['studioModelId']
rig['cloth_physics_verified'] = False
bind = {b.name: b.matrix_local.copy() for b in data.bones}
ordered = sorted(data.bones, key=lambda b: len(b.parent_recursive))

def clamp(value):
    return max(0.0, min(1.0, value))

def smooth(value):
    value = clamp(value)
    return value * value * (3 - 2 * value)

torso_names = ['Hips', 'Spine', 'Spine1', 'Spine2']
centers = [data.bones[n].head_local.z for n in torso_names]

def torso_weights(p):
    if p.z <= centers[0]:
        return {'Hips': 1.0}
    for index in range(3):
        if centers[index] <= p.z <= centers[index + 1]:
            t = smooth((p.z - centers[index]) / (centers[index + 1] - centers[index]))
            return {torso_names[index]: 1 - t, torso_names[index + 1]: t}
    return {'Spine2': 1.0}

def weight(p, role):
    if role == 'torso':
        return torso_weights(p)
    if role.startswith(('sleeve_', 'cuff_', 'lace_', 'ribbon_')):
        label = role[-1]
        side = 'Left' if label == 'L' else 'Right'
        arm = side + 'Arm'
        if role.startswith('sleeve_'):
            direction = tails[arm] - heads[arm]
            t = (p - heads[arm]).dot(direction) / direction.length_squared
            attachment = (1 - smooth((t - .1) / .22)) * clamp((.093 - abs(p.x)) / .022) * .75
            return {arm: 1 - attachment, side + 'Shoulder': attachment * .65, 'Spine2': attachment * .35}
        if role.startswith('cuff_'):
            return {arm: 1.0}
        secondary_name = ('CuffLace_' if role.startswith('lace_') else 'Ribbon_') + label
        length = .035 if role.startswith('lace_') else .0115
        t = smooth((data.bones[secondary_name].head_local.z - p.z) / length)
        return {arm: 1 - t, secondary_name: t}
    if role.startswith('tasset_'):
        index = int(role.split('_')[1])
        name = 'DressTab_' + str(index)
        bone = data.bones[name]
        t = smooth((bone.head_local.z - p.z) / (bone.head_local.z - bone.tail_local.z))
        result = {n: v * (1 - t) for n, v in torso_weights(p).items()}
        result[name] = t
        return result
    raise ValueError('Unknown attachment role: ' + role)

skin_audit = []
for obj in garments:
    role = obj['rig_role']
    transform = obj.matrix_world.copy()
    obj.parent = rig
    obj.matrix_world = transform
    groups = {}
    max_error = 0.0
    for vertex in obj.data.vertices:
        values = weight(transform @ vertex.co, role)
        total = sum(values.values())
        if not total > 0:
            raise ValueError('Unweighted vertex in ' + obj.name)
        for name, value in values.items():
            if value <= 1e-8:
                continue
            if name not in groups:
                groups[name] = obj.vertex_groups.new(name=name)
            groups[name].add([vertex.index], value / total, 'REPLACE')
        max_error = max(max_error, abs(sum(g.weight for g in vertex.groups) - 1))
    modifier = obj.modifiers.new('Every actual component / same Alice rig', 'ARMATURE')
    modifier.object = rig
    modifier.use_deform_preserve_volume = False  # glTF uses linear blend skinning.
    obj['rig_pending'] = False
    obj['motion_verified'] = False
    skin_audit.append({'mesh': obj.name, 'role': role, 'vertices': len(obj.data.vertices),
                       'unweightedVertices': sum(not v.groups for v in obj.data.vertices),
                       'boneGroups': list(groups), 'maxNormalizationError': max_error})
if any(a['unweightedVertices'] or a['maxNormalizationError'] > 1e-5 for a in skin_audit):
    raise ValueError('The full thickness and all decorations must have normalized skin weights.')

rig.animation_data_create()
for bone in rig.pose.bones:
    bone.rotation_mode = 'QUATERNION'
actions, retarget_audit = [], []

def assign_global_pose(matrices, frame):
    for bone in ordered:
        arguments = {}
        if bone.parent:
            arguments.update(parent_matrix=matrices[bone.parent.name],
                             parent_matrix_local=bind[bone.parent.name])
        pose = rig.pose.bones[bone.name]
        pose.matrix_basis = bone.convert_local_to_pose(
            matrices[bone.name], bind[bone.name], invert=True, **arguments)
        pose.keyframe_insert('location', frame=frame)
        pose.keyframe_insert('rotation_quaternion', frame=frame)
        pose.keyframe_insert('scale', frame=frame)

for label, source in sources.items():
    source_action = source.animation_data.action
    first, last = source_action.frame_range
    fps = next(s['sourceFps'] for s in source_records if s['motion'] == label)
    source_map = {b.name.split(':')[-1]: b for b in source.pose.bones}
    action = bpy.data.actions.new(label + ' / supplied motion retargeted to new Chapeleiro')
    action.use_fake_user = True
    rig.animation_data.action = action
    count = max(2, round((last - first) / fps * 30) + 1)
    for index in range(count):
        source_frame = first + (last - first) * index / (count - 1)
        bpy.context.scene.frame_set(math.floor(source_frame), subframe=source_frame % 1)
        bpy.context.view_layer.update()
        matrices = {}
        for bone in ordered:
            if bone.name in source_names:
                source_matrix = source.matrix_world @ source_map[bone.name].matrix
                rotation = source_matrix.to_quaternion().normalized().to_matrix()
                if bone.parent:
                    local_head = bind[bone.parent.name].inverted() @ bone.head_local
                    head = matrices[bone.parent.name] @ local_head
                else:
                    original = source.matrix_world @ source_map[bone.name].bone.head_local
                    delta = (source_matrix.to_translation() - original) * scale
                    head = bone.head_local + Vector((0, 0, delta.z))
                matrix = rotation.to_4x4()
                matrix.translation = head
            else:
                matrix = matrices[bone.parent.name] @ bind[bone.parent.name].inverted() @ bind[bone.name]
                secondary_rule = secondary[bone.name]
                amplitude = secondary_rule['amplitudeDegrees'] * (1.5 if label == 'Run' else 1)
                angle = math.radians(amplitude) * math.sin(index * math.tau * 2 / count + secondary_rule['phase'])
                matrix = matrix @ Matrix.Rotation(angle, 4, 'X')
            matrices[bone.name] = matrix
        assign_global_pose(matrices, index + 1)
    actions.append(action)
    retarget_audit.append({'clip': action.name, 'frames': count, 'fps': 30,
                           'sourceFrameRange': [first, last], 'rootMotion': 'horizontal translation removed; vertical motion and turning retained',
                           'armRetarget': 'absolute world orientation into the fitted A-pose bind skeleton',
                           'visibleQualityVerified': False, 'clothCollisionVerified': False})
    print('RETARGETED_CLIP', label, count, flush=True)

# No supplied jumping file was used. This new, explicitly named probe includes
# takeoff, flight and landing to expose skin failures. It is not approved gameplay.
jump = bpy.data.actions.new('Jump / authored deformation probe')
jump.use_fake_user = True
rig.animation_data.action = jump
for frame, lift, crouch, lean in [(1, 0, 0, 0), (9, -.045, 1, 9), (15, .02, .25, 3),
                                 (25, .145, .4, -3), (34, .06, .2, 2),
                                 (41, -.035, .8, 8), (53, 0, 0, 0)]:
    matrices = {}
    for bone in ordered:
        local = bind[bone.parent.name].inverted() @ bind[bone.name] if bone.parent else bind[bone.name].copy()
        if bone.parent:
            matrix = matrices[bone.parent.name] @ local
        else:
            matrix = local.copy()
            matrix.translation.z += lift
        angle = 0
        if bone.name in ['LeftUpLeg', 'RightUpLeg']:
            angle = -38 * crouch
        elif bone.name in ['LeftLeg', 'RightLeg']:
            angle = 65 * crouch
        elif bone.name in ['LeftFoot', 'RightFoot']:
            angle = -27 * crouch
        elif bone.name == 'Spine1':
            angle = lean
        elif bone.name in secondary:
            angle = math.sin(frame * .18 + secondary[bone.name]['phase']) * secondary[bone.name]['amplitudeDegrees']
        if angle:
            matrix = matrix @ Matrix.Rotation(math.radians(angle), 4, 'X')
        matrices[bone.name] = matrix
    assign_global_pose(matrices, frame)
actions.append(jump)
retarget_audit.append({'clip': jump.name, 'frames': 53, 'fps': 30, 'source': 'locally authored deformation probe',
                       'visibleQualityVerified': False, 'clothCollisionVerified': False,
                       'limitation': 'Jump timing and combat transitions require gameplay work.'})
for source in sources.values():
    bpy.data.objects.remove(source, do_unlink=True)
rig.animation_data.action = None
for bone in rig.pose.bones:
    bone.matrix_basis = Matrix.Identity(4)
for action in actions:
    track = rig.animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, 1, action)
    if action.slots:
        strip.action_slot = action.slots[0]
    track.mute = True
scene = bpy.context.scene
scene.render.fps = 30
scene.render.fps_base = 1
scene.frame_set(1)
bpy.context.view_layer.update()
blend = out / 'chapeleiro_sheet_two_shared_rig.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT')
for obj in garments + [rig]:
    obj.select_set(True)
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_yup=True, export_animations=True, export_animation_mode='NLA_TRACKS')
# Inspect the actual exported document rather than infer clips from Blender data.
import struct
content = model.read_bytes()
json_size, json_type = struct.unpack_from('<II', content, 12)
document = json.loads(content[20:20 + json_size])
clip_names = [a.get('name') for a in document.get('animations', [])]
if not all(any(n.startswith(label + ' /') for n in clip_names) for label in ['Walk', 'Run', 'Jump', 'Attack']):
    raise ValueError('A required clip was lost during actual GLB export.')
skinned_nodes = [n for n in document.get('nodes', []) if 'mesh' in n and 'skin' in n]
if len(skinned_nodes) != len(garments):
    raise ValueError('An actual exported component has no skin.')
schema = {'sourceGeometrySha256': record['modelSha256'], 'sourcePhotoSha256': record['sourcePhotoSha256'],
          'sourceStudioId': record['studioModelId'], 'scaleFromSuppliedSkeleton': scale,
          'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else None,
                     'head': list(b.head_local), 'tail': list(b.tail_local),
                     'matrix': [list(row) for row in b.matrix_local]} for b in ordered],
          'secondaryBones': secondary, 'fidelityVerified': False, 'motionVerified': False,
          'clothCollisionVerified': False}
(out / 'shared_rig_bind.json').write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding='utf-8')
record.update(model=str(model.resolve()), modelSha256=sha(model),
              editableBlend=str(blend.resolve()), editableBlendSha256=sha(blend),
              geometryParentSha256=record['modelSha256'], rigScriptSha256=sha(__file__),
              rigSources=source_records, rigPresent=True, riggedComponents=len(garments),
              rigStatus='all_sheet_2_components_skinned_pending_visual_motion_review',
              skinAudit=skin_audit, motionAudit=retarget_audit,
              exportAudit={'skinnedNodes': len(skinned_nodes), 'clips': clip_names,
                           'jointCount': len(document['skins'][0]['joints']),
                           'allRequiredClipsPresent': True},
              method='new_Tripo_sheet_2_components_on_shared_A_pose_motion_rig',
              status='generated_awaiting_visual_review', countsAsFinishedLayer=False,
              motionVerified=False, fidelityVerified=False, clothCollisionVerified=False,
              localWorkStatus='shared_rig_and_four_clips_exported_pending_deformation_review',
              additionalCreditsConsumed=0,
              limitations=['The actual forty sheet-2 components are skinned; other clothing layers are pending.',
                           'Shoulder boundaries, side projection and isolated reinforcements need refinement.',
                           'Secondary keys and the jump are authored deformation probes, not cloth simulation.',
                           'Body and inter-layer cloth collisions and Soulslike gameplay are not approved.'])
for component in record['componentAudit']:
    component['rigged'] = True
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('SHARED_SHEET_2_RIG_CREATED', json.dumps(record['exportAudit']), flush=True)
