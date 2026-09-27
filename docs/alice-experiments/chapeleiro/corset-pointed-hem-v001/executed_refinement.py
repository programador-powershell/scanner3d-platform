"""Refine the authored interior corset's displayed front hem toward its own photo.

Preserve the complete source, all UVs, skin weights, actions and protected whole
dress. This local prototype changes existing skinned interior meshes only.
The original hidden procedural authoring cages remain available unchanged;
propagating the approved shape into their bindings is a separate pending step.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g = json.loads(Path(a.generation).read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
photo = g['exports']['foundation']['sourcePhoto']
assert sha(photo) == g['exports']['foundation']['sourcePhotoSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
frame_before = scene.frame_current
action_before = rig.animation_data.action
tracks_before = [t.mute for t in rig.animation_data.nla_tracks]
pose_before = [p.matrix_basis.copy() for p in rig.pose.bones]
for t in rig.animation_data.nla_tracks: t.mute = True
rig.animation_data.action = None
for pbone in rig.pose.bones: pbone.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()

def geometry_hash(obj):
    mesh = obj.data
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    loops = np.empty(len(mesh.loops), np.int32)
    mesh.vertices.foreach_get('co', xyz)
    mesh.loops.foreach_get('vertex_index', loops)
    return hashlib.sha256(xyz.tobytes() + loops.tobytes()).hexdigest()

def surface_hash(obj):
    mesh = obj.data
    digest = hashlib.sha256()
    for layer in mesh.uv_layers:
        xy = np.empty(len(layer.data) * 2, np.float32)
        layer.data.foreach_get('uv', xy)
        digest.update(layer.name.encode()); digest.update(xy.tobytes())
    groups = [[(group.group, group.weight) for group in vertex.groups] for vertex in mesh.vertices]
    digest.update(json.dumps(groups).encode())
    digest.update(json.dumps([group.name for group in obj.vertex_groups]).encode())
    digest.update(json.dumps([m.name if m else None for m in mesh.materials]).encode())
    return digest.hexdigest()

def action_hash():
    rows = []
    for action in bpy.data.actions:
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        curves.append([curve.data_path, curve.array_index,
                                       [(list(k.co), list(k.handle_left), list(k.handle_right), k.interpolation)
                                        for k in curve.keyframe_points]])
        rows.append([action.name, curves])
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

before = {o.name: geometry_hash(o) for o in scene.objects if o.type == 'MESH'}
actions_before = action_hash()
source = bpy.data.objects['Authoring / 01 / ivory fitted boned corset / pointed front']
assert len(source.data.vertices) == 3200
rim = np.array([source.matrix_world @ v.co for v in source.data.vertices[-128:]])
front = rim[rim[:, 1] <= 1e-6]
order = np.argsort(front[:, 0]); front = front[order]
assert np.all(np.diff(front[:, 0]) > 0)
extent = float(np.max(np.abs(front[:, 0])))
tip = float(front[np.argmin(np.abs(front[:, 0])), 2])
side = float((front[0, 2] + front[-1, 2]) / 2)
assert .075 < extent < .085 and .59 < tip < .60 and .62 < side < .63
modified = []
for obj in scene.objects:
    if obj.type != 'MESH' or not obj.name.startswith('01 / '): continue
    if not any(x in obj.name.lower() for x in ['corset', 'busk', 'rear eyelet']): continue
    assert any(m.type == 'ARMATURE' and m.object == rig for m in obj.modifiers)
    world = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
    x = np.clip(world[:, 0], -extent, extent)
    old_hem = np.interp(x, front[:, 0], front[:, 2])
    new_hem = tip + (side - tip) * np.abs(x) / extent
    # Use the assembled foundation's pointed front as the shape reference.
    # The isolated corset drawing on the same sheet has different upper fit;
    # unseen depth and tailoring dimensions remain modeled estimates.
    taper = np.clip((.665 - world[:, 2]) / (.665 - old_hem), 0, 1) ** 2
    delta = (new_hem - old_hem) * taper * (world[:, 1] < -.0005)
    if float(np.max(np.abs(delta))) < 1e-8: continue
    surface_before = surface_hash(obj)
    obj.data = obj.data.copy()
    changed_world = world.copy(); changed_world[:, 2] += delta
    inv = np.array(obj.matrix_world.inverted())
    local = changed_world @ inv[:3, :3].T + inv[:3, 3]
    obj.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
    custom_normals_cleared = obj.data.has_custom_normals
    if custom_normals_cleared:
        obj.data.normals_split_custom_set([(0., 0., 0.)] * len(obj.data.loops))
    obj.data.update()
    assert surface_hash(obj) == surface_before
    modified.append({'name': obj.name, 'maximumVerticalChangeMeters': float(np.max(np.abs(delta))),
                     'uvSkinWeightsAndMaterialSlotsExactlyPreserved': True,
                     'obsoleteCustomNormalsCleared': custom_normals_cleared,
                     'geometryBeforeSha256': before[obj.name], 'geometryAfterSha256': geometry_hash(obj)})
names = {r['name'] for r in modified}
assert '01 / ivory fitted boned corset / pointed front' in names
assert all(geometry_hash(bpy.data.objects[n]) == value for n, value in before.items() if n not in names)
assert action_hash() == actions_before
for track, mute in zip(rig.animation_data.nla_tracks, tracks_before): track.mute = mute
rig.animation_data.action = action_before
for bone, basis in zip(rig.pose.bones, pose_before): bone.matrix_basis = basis
scene.frame_set(frame_before)
blend = out / 'chapeleiro_corset_pointed_hem_study.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
record = {
    'method': 'Local pointed front hem refinement of existing authored skinned corset and its trim',
    'parentGeneration': str(Path(a.generation).resolve()), 'parentGenerationSha256': sha(a.generation),
    'editableBlend': str(blend), 'editableBlendSha256': sha(blend), 'editableBytes': blend.stat().st_size,
    'exports': {'foundation': {'sourcePhoto': photo, 'sourcePhotoSha256': sha(photo)}},
    'referenceChoice': 'Pointed front of assembled foundation on the full own-stage sheet; isolated drawings inform construction details.',
    'modifiedSkinnedPieces': modified, 'otherMeshesIncludingHiddenAuthoringAndWholeExteriorUnchanged': True,
    'allActionsExact': True, 'actionDataSha256': actions_before, 'sharedBones': len(rig.data.bones),
    'fullAuthoringRetained': True, 'hiddenProceduralAuthoringShapePropagationPending': True,
    'scriptSha256': sha(__file__), 'sourceCheckpointUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
    'newGlbExported': False, 'finalFbxExported': False, 'fidelityVerified': False,
    'motionVerified': False, 'clothCollisionVerified': False, 'allLayersFinished': False,
    'additionalTripoCreditsConsumed': 0,
}
(out / 'generation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_refinement.py')
print('POINTED_CORSET_HEM_STUDY_SAVED', len(modified), blend.stat().st_size, flush=True)
