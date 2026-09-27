"""Simulate the actual authored Black support and sewn flounces locally.

Use the additional measured Ivory action as the animated collision context.
No exterior cut, foreign geometry, model export or saved master modification.
Cloth-to-cloth response and all-layer fidelity remain under review.
"""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--ivory-collider', choices=['include', 'exclude'], default='include')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
path, out = Path(a.generation), Path(a.output)
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
g, schema, audit = read(path), read(path.parent / 'shared_rig_bind.json'), read(path.parent / 'skin_audit.json')
assert sha(g['editableBlend']) == g['editableBlendSha256'] and g['ivoryResponseBaked']
assert not out.exists()
out.mkdir(parents=True)
start = time.time()
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_shared_rig_fields import GarmentFields, quantized_assign
from chapeleiro_cloth_colliders import thin_underlayer_colliders
fields = GarmentFields(rig, schema['clothFamilies'], schema['pieceFamilies'], schema.get('pieceRegions'))
visible_names = ['01 / black petticoat continuous waist support'] + ['01 / black gathered flounce ' + str(i) for i in range(1, 4)]
sources = [bpy.data.objects['Authoring / ' + n] for n in visible_names]
clones, cloths, source_rows = [], [], []
for i, source in enumerate(sources):
    clone = source.copy()
    clone.data = source.data.copy()
    clone.name = 'Local physical Black family / ' + visible_names[i]
    scene.collection.objects.link(clone)
    for modifier in list(clone.modifiers):
        if modifier.type == 'NODES': clone.modifiers.remove(modifier)
    cloth = next(m for m in clone.modifiers if m.type == 'CLOTH')
    cloth.show_viewport = False  # Construction only, before the sequential cache.
    cloths.append(cloth)
    clones.append(clone)
    source_rows.append({'source': source.name, 'visibleGarment': visible_names[i],
                        'vertices': len(source.data.vertices), 'faces': len(source.data.polygons),
                        'independentMeshCopy': clone.data is not source.data,
                        'originalPhotoSha256': source['originalLayerPhotoSha256']})
main = clones[0]
assigned = quantized_assign(main, rig, fields, 'internal_petticoat', visible_names[0], preserve_other_groups=True)
arm = main.modifiers.new('Existing common BlackCloth field / local solver', 'ARMATURE')
arm.object = rig
bpy.ops.object.select_all(action='DESELECT')
main.select_set(True)
bpy.context.view_layer.objects.active = main
while list(main.modifiers).index(arm) > 0: bpy.ops.object.modifier_move_up(modifier=arm.name)
main.modifiers.new('Triangulate after local Black solver', 'TRIANGULATE')
for clone in clones[1:]:
    world = clone.matrix_world.copy()
    clone.parent = main
    clone.matrix_parent_inverse = main.matrix_world.inverted()
    clone.matrix_world = world
    mod = next(m for m in clone.modifiers if m.type == 'SURFACE_DEFORM')
    bpy.ops.object.select_all(action='DESELECT')
    clone.select_set(True)
    bpy.context.view_layer.objects.active = clone
    if mod.is_bound: bpy.ops.object.surfacedeform_bind(modifier=mod.name)
    mod.target = main
    bpy.ops.object.surfacedeform_bind(modifier=mod.name)
    assert mod.is_bound
    clone.modifiers.new('Triangulate after sewn Black flounce solver', 'TRIANGULATE')
    next(m for m in clone.modifiers if m.type == 'CLOTH').settings.use_dynamic_mesh = True

collider_names = ['01 / left stocking / fitted leg ankle and closed toe',
                  '01 / right stocking / fitted leg ankle and closed toe',
                  '01 / bloomers / continuous waist and sewn crotch']
if a.ivory_collider == 'include': collider_names.append('01 / long ivory gathered petticoat')
colliders, collider_rows = thin_underlayer_colliders(scene, audit, collider_names, rig)
targets = []
for clone in clones:
    target = clone.copy()
    target.name = 'Measurement only / Black solver input / ' + clone.name
    scene.collection.objects.link(target)
    target.modifiers.remove(next(m for m in target.modifiers if m.type == 'CLOTH'))
    assert target.data is clone.data
    targets.append(target)
for collection in bpy.data.collections: collection.hide_viewport = False
active = {rig, *clones, *targets, *colliders}
for obj in scene.objects:
    obj.hide_viewport = obj not in active
    obj.hide_render = True
    if obj in active: obj.hide_set(False)
for track in rig.animation_data.nla_tracks: track.mute = True
action = bpy.data.actions[g['ivoryStudyClip']]
rig.animation_data.action = action
rig.data.pose_position = 'POSE'
scene.frame_start, scene.frame_end = 1, 29
for obj in colliders:
    obj.modifiers.new('Actual animated collision surface / Black study', 'COLLISION')
    obj.collision.thickness_outer = .0008
    obj.collision.thickness_inner = .0008
    obj.collision.cloth_friction = 5
for cloth in cloths:
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, 29
    cloth.show_viewport = True
    assert cloth.settings.vertex_group_mass == 'pinned'

def coords(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    m = np.asarray(evaluated.matrix_world)
    result = xyz.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    evaluated.to_mesh_clear()
    return result

keys = ['support', 'tier1', 'tier2', 'tier3']
rest, edges, lengths, pins, snapshots, inputs = {}, {}, {}, {}, {}, {}
for key, obj in zip(keys, clones):
    rest[key] = np.array([obj.matrix_world @ v.co for v in obj.data.vertices], np.float32)
    raw = np.empty(len(obj.data.edges) * 2, np.int32)
    obj.data.edges.foreach_get('vertices', raw)
    edges[key] = raw.reshape(-1, 2)
    lengths[key] = np.linalg.norm(rest[key][edges[key][:, 0]] - rest[key][edges[key][:, 1]], axis=1)
    index = obj.vertex_groups['pinned'].index
    pins[key] = np.array([next((w.weight for w in v.groups if w.group == index), 0.) for v in obj.data.vertices], np.float32)
    snapshots[key], inputs[key] = [], []
rows, rig_poses = [], []
names = [b.name for b in rig.data.bones]
inverse = [b.matrix_local.inverted() for b in rig.data.bones]
for frame in range(1, 30):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    pieces = []
    for key, obj, target, cloth in zip(keys, clones, targets, cloths):
        points, skin = coords(obj), coords(target)
        assert points.shape == skin.shape == rest[key].shape and np.isfinite(points).all()
        assert cloth.show_viewport
        valid = lengths[key] > 1e-6
        stretch = np.linalg.norm(points[edges[key][:, 0]] - points[edges[key][:, 1]], axis=1)[valid] / lengths[key][valid]
        error = np.linalg.norm(points - skin, axis=1)
        pieces.append({'key': key, 'maximumEdgeStretch': float(stretch.max()),
                       'edgeStretch95Percentile': float(np.percentile(stretch, 95)),
                       'maximumFullyPinnedInputError': float(error[pins[key] > .999].max()),
                       'cacheInfo': cloth.point_cache.info, 'cacheOutdated': bool(cloth.point_cache.is_outdated),
                       'bounds': [points.min(0).tolist(), points.max(0).tolist()]})
        snapshots[key].append(points)
        inputs[key].append(skin)
    rows.append({'frame': frame, 'pieces': pieces})
    rig_poses.append([np.asarray(rig.pose.bones[n].matrix @ inv) for n, inv in zip(names, inverse)])
    if frame % 5 == 0:
        print('ACTUAL_BLACK_FAMILY_SOLVER_FRAME', frame, 29, round(time.time() - start, 2), flush=True)
        (out / 'progress.json').write_text(json.dumps({'completed': False, 'lastActualFrame': frame, 'plannedFrames': 29, 'frames': rows}) + '\n', encoding='utf-8', newline='\n')
data = out / 'actual_black_family_cloth_frames.npz'
arrays = {'rig_deformations': np.asarray(rig_poses), 'bone_names': np.asarray(names)}
for key in keys:
    arrays.update({key + '_points': np.asarray(snapshots[key]), key + '_inputs': np.asarray(inputs[key]),
                   key + '_rest_points': rest[key], key + '_edges': edges[key], key + '_pin_weights': pins[key]})
np.savez_compressed(data, **arrays)
report = {'parentEditableSha256': g['editableBlendSha256'], 'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'],
          'actualSolver': 'Blender CLOTH on independent copies of existing photo-authored Black support and three sewn flounces',
          'sources': source_rows, 'assignedCommonRigField': assigned,
          'actualColliderSources': collider_rows, 'includeMeasuredIvoryCollider': a.ivory_collider == 'include',
          'sourceAction': action.name, 'sourceAnimationFrames': 29,
          'actualModifierOrders': [[m.type for m in o.modifiers] for o in clones],
          'clothNeverBypassedDuringSequence': True, 'frames': rows,
          'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'fieldHelperSha256': sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
          'colliderHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_colliders.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'localBlackResponseBaked': False, 'modelExported': False, 'finalFbxExported': False,
          'allLayersFinished': False, 'fidelityVerified': False, 'clothCollisionVerified': False, 'motionVerified': False,
          'limitation': 'Animated Ivory collision surface is the existing approximate rig response. Mutual cloth response, all poses and signed contact remain unapproved.',
          'elapsedSeconds': time.time() - start}
(out / 'actual_black_family_solver_motion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_probe.py')
print('ACTUAL_BLACK_FAMILY_SOLVER_SAVED', 29, flush=True)
