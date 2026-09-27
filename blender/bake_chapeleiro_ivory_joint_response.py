"""Bake a measured Ivory response into the existing complete shared rig.

Keep all geometry, UVs, weights, materials, bind joints and four source actions.
Add one separately named physical study action to the foundation export only.
The intact whole GLB is copied unchanged; this does not simulate its exterior.
"""
import argparse, hashlib, json, shutil, struct, sys, time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--parent', required=True)
p.add_argument('--fit', required=True)
p.add_argument('--output', required=True)
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
parent_path = Path(args.parent)
parent, fit = read(parent_path), read(args.fit)
assert sha(parent['editableBlend']) == parent['editableBlendSha256'] == fit['parentEditableSha256']
assert sha(fit['dataFile']) == fit['dataSha256'] and fit['other137BonesUnchanged']
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
start = time.time()
write = lambda name, value: (out / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
master = parent_path.parent / 'alice-vestido-chapeleiro.blend'
assert sha(master) == 'ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9'
shutil.copyfile(master, out / master.name)
for name in ['shared_rig_bind.json', 'skin_audit.json', 'native_hand_bind_fit.json',
             'native_individual_finger_targets.json', 'refitted_motion_retarget.json']:
    shutil.copyfile(parent_path.parent / name, out / name)
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene = bpy.context.scene
rigs = [o for o in scene.objects if o.type == 'ARMATURE']
assert len(rigs) == 1
rig = rigs[0]
names = [b.name for b in rig.data.bones]
data = np.load(fit['dataFile'])
assert names == data['bone_names'].tolist() and len(names) == 173
assert len(data['modified_bone_indices']) == 36
audit = read(out / 'skin_audit.json')
pieces = [bpy.data.objects[x['mesh']] for x in audit['pieces']]
assert len(pieces) == 230
assert all(any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers) for o in pieces)

def mesh_hash(obj):
    mesh = obj.data
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    indices = np.empty(len(mesh.loops), np.int32)
    mesh.loops.foreach_get('vertex_index', indices)
    counts = np.empty(len(mesh.polygons), np.int32)
    mesh.polygons.foreach_get('loop_total', counts)
    digest = hashlib.sha256(xyz.tobytes() + indices.tobytes() + counts.tobytes())
    for layer in mesh.uv_layers:
        uv = np.empty(len(layer.data) * 2, np.float32)
        layer.data.foreach_get('uv', uv)
        digest.update(uv.tobytes())
    digest.update(json.dumps([m.name if m else None for m in mesh.materials]).encode())
    return digest.hexdigest()

def action_hash(action):
    rows = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    rows.append([curve.data_path, curve.array_index,
                                 [[list(k.co), list(k.handle_left), list(k.handle_right), k.interpolation]
                                  for k in curve.keyframe_points]])
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()

before_meshes = {o.name: mesh_hash(o) for o in scene.objects if o.type == 'MESH'}
source_actions = {a.name: action_hash(a) for a in bpy.data.actions
                  if any(a.name.startswith(prefix + ' /') for prefix in ['Walk', 'Run', 'Jump', 'Attack'])}
assert len(source_actions) == 4
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.data.pose_position = 'POSE'
local = bpy.data.actions.new('Corrida com tecido / anágua em refinamento')
rig.animation_data.action = local
bind = {b.name: b.matrix_local.copy() for b in rig.data.bones}
previous, checks = {}, []
for frame, deformations in enumerate(data['rig_deformations'], 1):
    matrices = {name: Matrix(deformations[i].tolist()) @ bind[name] for i, name in enumerate(names)}
    for bone in rig.data.bones:
        arguments = ({'parent_matrix': matrices[bone.parent.name],
                      'parent_matrix_local': bind[bone.parent.name]} if bone.parent else {})
        pose = rig.pose.bones[bone.name]
        pose.rotation_mode = 'QUATERNION'
        pose.matrix_basis = bone.convert_local_to_pose(matrices[bone.name], bind[bone.name], invert=True, **arguments)
        q = pose.rotation_quaternion.copy()
        if bone.name in previous and q.dot(previous[bone.name]) < 0:
            q.negate()
            pose.rotation_quaternion = q
        previous[bone.name] = q.copy()
        for channel in ['location', 'rotation_quaternion', 'scale']:
            pose.keyframe_insert(data_path=channel, frame=frame, group=bone.name)
for layer in local.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = 'LINEAR'
for frame, deformations in enumerate(data['rig_deformations'], 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    actual = np.array([np.asarray(rig.pose.bones[n].matrix @ bind[n].inverted()) for n in names])
    error = float(np.abs(actual - deformations).max())
    assert error < 1e-5
    checks.append({'frame': frame, 'actualBakedJointMatrixMaximumError': error})
assert {n: action_hash(bpy.data.actions[n]) for n in source_actions} == source_actions
assert {o.name: mesh_hash(o) for o in scene.objects if o.type == 'MESH'} == before_meshes
track = rig.animation_data.nla_tracks.new()
track.name = local.name
track.strips.new(local.name, 1, local)
track.mute = True
rig.animation_data.action = None
for bone in rig.pose.bones:
    bone.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()
for library in bpy.data.libraries:
    library.filepath = '//' + Path(bpy.path.abspath(library.filepath)).name
editable = out / 'chapeleiro_shared_rig_ivory_response.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable), compress=True, relative_remap=False)
print('ACTUAL_FULL_IVORY_RESPONSE_EDITABLE_SAVED', editable.stat().st_size, flush=True)
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
for obj in pieces[:-1]:
    obj.select_set(True)
model = out / 'foundation_shared_rig_study.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                         export_yup=True, export_animations=True, export_animation_mode='NLA_TRACKS', export_frame_range=False)
raw = model.read_bytes()
length = struct.unpack_from('<I', raw, 12)[0]
document = json.loads(raw[20:20 + length])
clips = [a.get('name', '') for a in document['animations']]
nodes = [n for n in document['nodes'] if 'mesh' in n and 'skin' in n]
assert len(nodes) == 229 and len(document['skins']) == 1 and len(document['skins'][0]['joints']) == 173
assert len(clips) == 5 and local.name in clips
assert all(any(n.startswith(prefix + ' /') for n in clips) for prefix in ['Walk', 'Run', 'Jump', 'Attack'])
foundation = read(parent_path.parent / 'foundation_generation.json')
foundation.update(model=str(model), modelSha256=sha(model), bytes=model.stat().st_size,
                  editableBlend=str(editable), editableBlendSha256=sha(editable),
                  actualClips=clips, actualSkinnedNodes=229, actualSkins=1,
                  additionalPhysicalStudyClip=local.name, ivoryResponseBaked=True,
                  fidelityVerified=False, motionVerified=False, clothCollisionVerified=False,
                  allLayersFinished=False, nextVariantMayStart=False, additionalCreditsConsumed=0)
write('foundation_generation', foundation)
whole_model = out / 'whole_shared_rig_study.glb'
shutil.copyfile(parent['exports']['whole']['model'], whole_model)
assert sha(whole_model) == parent['exports']['whole']['modelSha256']
whole = read(parent_path.parent / 'whole_generation.json')
whole.update(model=str(whole_model), editableBlend=str(editable), editableBlendSha256=sha(editable),
             wholeResponseUnchangedFromParent=True, ivoryStudyClipNotIncludedInWholeExport=True)
write('whole_generation', whole)
exports = {'foundation': {k: foundation[k] for k in ['model', 'modelSha256', 'bytes', 'actualClips', 'actualSkinnedNodes', 'actualSkins', 'sourcePhoto', 'sourcePhotoSha256']},
           'whole': dict(parent['exports']['whole'], model=str(whole_model))}
result = dict(parent)
result.update(parentGeneration=str(parent_path), parentGenerationSha256=sha(parent_path),
              method='existing shared rig with measured Ivory response study; intact exterior unchanged',
              editableBlend=str(editable), editableBlendSha256=sha(editable), editableBytes=editable.stat().st_size,
              exports=exports, scriptSha256=sha(__file__), actualGeometryUnchanged=True,
              sourceFourActionCurveHashes=source_actions, ivoryFitReport=str(Path(args.fit).resolve()),
              ivoryFitDataSha256=fit['dataSha256'], ivoryResponseBaked=True,
              ivoryStudyClip=local.name, actualBakedJointMatrixChecks=checks,
              wholePhysicsResponseBaked=False, otherLayersPhysicsResponseBaked=False,
              sourcePhotoComparisonAndExportReimportPending=True, allLayersFinished=False,
              fidelityVerified=False, motionVerified=False, clothCollisionVerified=False,
              finalFbxExported=False, nextVariantMayStart=False, additionalCreditsConsumed=0,
              elapsedSeconds=time.time() - start)
write('generation', result)
shutil.copyfile(__file__, out / 'executed_bake.py')
print('ACTUAL_FOUNDATION_IVORY_RESPONSE_EXPORTED', model.stat().st_size, clips, flush=True)
