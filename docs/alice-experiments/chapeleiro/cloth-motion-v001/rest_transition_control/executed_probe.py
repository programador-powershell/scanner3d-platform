"""Measure an uninterrupted Cloth cache using a separate Armature-only target.

This is a physical study of the existing ivory midsurface. It preserves the
source edit, exports no final FBX, and does not approve all-layer collisions.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--clip', choices=['Walk', 'Run', 'Jump', 'Attack'], default='Run')
p.add_argument('--motion-cycles', dest='cycles', type=int, default=1)
p.add_argument('--warmup', type=int, default=12)
p.add_argument('--collision-scope', choices=['actual_underlayers', 'none', 'stockings_only', 'bloomers_only'], default='actual_underlayers')
p.add_argument('--entry-mode', choices=['held_first', 'rest_transition'], default='held_first')
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert args.cycles > 0 and args.warmup > 0
path = Path(args.generation)
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
r = read(path)
assert sha(r['editableBlend']) == r['editableBlendSha256']
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
started = time.time()
bpy.ops.wm.open_mainfile(filepath=r['editableBlend'])
scene = bpy.context.scene
rigs = [o for o in scene.objects if o.type == 'ARMATURE']
assert len(rigs) == 1
rig = rigs[0]
audit = read(path.parent / 'skin_audit.json')
entry = next(a for a in audit['authoringCages'] if a['receiver'] == '01 / long ivory gathered petticoat')
cage = bpy.data.objects[entry['mesh']]
receiver = bpy.data.objects['Authoring / ' + entry['receiver']]
collider_candidates = ['01 / left stocking / fitted leg ankle and closed toe',
                  '01 / right stocking / fitted leg ankle and closed toe',
                  '01 / bloomers / continuous waist and sewn crotch']
collider_names = (collider_candidates if args.collision_scope == 'actual_underlayers' else
                  collider_candidates[:2] if args.collision_scope == 'stockings_only' else
                  collider_candidates[2:] if args.collision_scope == 'bloomers_only' else [])
colliders = [bpy.data.objects[n] for n in collider_names]
assert [m.type for m in cage.modifiers] == ['ARMATURE', 'CLOTH', 'TRIANGULATE']
cloth = next(m for m in cage.modifiers if m.type == 'CLOTH')
# Copy only the original target object. Shared mesh data and copied skin groups
# preserve the same rest vertices and weights; the duplicate has no Cloth.
target = cage.copy()
target.name = 'Measurement only / identical ivory Armature target'
scene.collection.objects.link(target)
target.modifiers.remove(next(m for m in target.modifiers if m.type == 'CLOTH'))
assert target.data is cage.data
assert [m.type for m in target.modifiers] == ['ARMATURE', 'TRIANGULATE']
for collection in bpy.data.collections:
    collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, cage, target, *colliders]
    obj.hide_render = obj not in [receiver, *colliders]
target.hide_render = True
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
action = next(a for a in bpy.data.actions if a.name.startswith(args.clip + ' / current fitted'))
first, last = action.frame_range
entry_script_sha = None
initial_rest_error = None
if args.entry_mode == 'rest_transition':
    helper = Path(__file__).with_name('chapeleiro_cloth_motion_entry.py')
    sys.path.insert(0, str(helper.parent))
    from chapeleiro_cloth_motion_entry import rest_transition_action
    # Build the local entry action before the measured sequential cache begins.
    cloth.show_viewport = False
    local_action, end, initial_rest_error = rest_transition_action(rig, action, args.warmup, args.cycles)
    cloth.show_viewport = True
    entry_script_sha = sha(helper)
else:
    track = rig.animation_data.nla_tracks.new()
    track.name = 'Uninterrupted local physical study / ' + args.clip
    strip = track.strips.new(action.name, args.warmup + 1, action)
    strip.repeat = args.cycles
    strip.extrapolation = 'HOLD'
    end = int(args.warmup + 1 + (last - first) * args.cycles)
scene.frame_start = 1
scene.frame_end = end
for obj in colliders:
    obj.modifiers.new('Actual animated underlayer collision / local study', 'COLLISION')
    obj.collision.thickness_outer = .0008
    obj.collision.thickness_inner = .0008
    obj.collision.cloth_friction = 5
cloth.point_cache.frame_start = 1
cloth.point_cache.frame_end = end
assert cloth.settings.vertex_group_mass == 'pinned'
setting_keys = ['quality', 'mass', 'time_scale', 'air_damping', 'tension_stiffness',
                'compression_stiffness', 'shear_stiffness', 'bending_stiffness',
                'tension_damping', 'compression_damping', 'shear_damping', 'bending_damping',
                'pin_stiffness', 'vertex_group_mass', 'use_dynamic_mesh', 'use_pressure',
                'uniform_pressure_force', 'shrink_min', 'shrink_max', 'vertex_group_shrink']
actual_settings = {k: getattr(cloth.settings, k) for k in setting_keys if hasattr(cloth.settings, k)}
pin_group = cage.vertex_groups['pinned'].index
pins = np.array([next((g.weight for g in v.groups if g.group == pin_group), 0.0)
                 for v in cage.data.vertices], np.float32)
fully_pinned = pins > .999

def coords(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    matrix = np.asarray(evaluated.matrix_world)
    result = xyz.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    evaluated.to_mesh_clear()
    return result

original = np.array([cage.matrix_world @ v.co for v in cage.data.vertices], np.float32)
raw_edges = np.empty(len(cage.data.edges) * 2, np.int32)
cage.data.edges.foreach_get('vertices', raw_edges)
edges = raw_edges.reshape(-1, 2)
lengths = np.linalg.norm(original[edges[:, 0]] - original[edges[:, 1]], axis=1)
valid = lengths > 1e-6
snapshots, skin_targets, rig_poses, rows = [], [], [], []
names = [b.name for b in rig.data.bones]
bind_inverse = [b.matrix_local.inverted() for b in rig.data.bones]
for frame in range(1, end + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    points = coords(cage)
    skin = coords(target)
    assert cloth.show_viewport and points.shape == skin.shape == original.shape
    assert np.isfinite(points).all() and np.isfinite(skin).all()
    ratios = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)[valid] / lengths[valid]
    delta = np.linalg.norm(points - skin, axis=1)
    rows.append({'frame': frame, 'maximumEdgeStretch': float(ratios.max()),
                 'edgeStretch95Percentile': float(np.percentile(ratios, 95)),
                 'maximumActualSolverOffsetFromAnimatedSkin': float(delta.max()),
                 'solverOffset95Percentile': float(np.percentile(delta, 95)),
                 'maximumFullyPinnedTargetError': float(delta[fully_pinned].max()),
                 'cacheOutdated': bool(cloth.point_cache.is_outdated),
                 'cacheInfo': cloth.point_cache.info,
                 'bounds': [points.min(0).tolist(), points.max(0).tolist()]})
    snapshots.append(points)
    skin_targets.append(skin)
    rig_poses.append([np.asarray(rig.pose.bones[n].matrix @ inv) for n, inv in zip(names, bind_inverse)])
    if frame % 5 == 0:
        print('CONTINUOUS_IVORY_SOLVER_FRAME', frame, end, round(time.time() - started, 2), flush=True)
        (out / 'progress.json').write_text(json.dumps({'completed': False, 'lastActualFrame': frame,
            'plannedFrames': end, 'actualSolverSettings': actual_settings, 'actualFrames': rows,
            'clothNeverBypassedDuringSequence': True, 'scriptSha256': sha(__file__)}, indent=2) + '\n',
            encoding='utf-8', newline='\n')
data = out / 'actual_continuous_cloth_frames.npz'
np.savez_compressed(data, points=np.asarray(snapshots), actual_skin_targets=np.asarray(skin_targets),
                    rest_points=original, edges=edges, pin_weights=pins,
                    rig_deformations=np.asarray(rig_poses), bone_names=np.asarray(names))
report = {'parentEditableSha256': r['editableBlendSha256'],
          'parentWholeModelSha256': r['exports']['whole']['modelSha256'],
          'sourcePhotoSha256': r['exports']['foundation']['sourcePhotoSha256'],
          'clothCage': cage.name, 'receiver': receiver.name,
          'actualColliderSurfaces': collider_names,
          'collisionScope': args.collision_scope,
          'collisionControlsOnly': args.collision_scope != 'actual_underlayers',
          'entryMode': args.entry_mode, 'entryScriptSha256': entry_script_sha,
          'initialRestLocalTransformMaximumError': initial_rest_error,
          'collisionSurfaceScope': 'existing animated stockings and bloomers; hidden anatomy and other layers pending',
          'actualSolver': 'Blender CLOTH on the existing authored midsurface',
          'solverSettingsUnchanged': True, 'clothNeverBypassedDuringSequence': True,
          'actualSolverSettings': actual_settings,
          'targetMeasurement': 'separate identical mesh and skin groups with Armature only; no solver mutation',
          'actualWarmupFrames': args.warmup, 'sourceAction': action.name,
          'sourceActionFrameRange': [first, last], 'cycles': args.cycles,
          'frames': rows, 'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'geometryChanged': False, 'parentEditableUnchanged': sha(r['editableBlend']) == r['editableBlendSha256'],
          'exportedPreviewReceivesSolverMotion': False, 'secondaryBoneResponseBaked': False,
          'allLayersFinished': False, 'clothCollisionVerified': False,
          'motionVerified': False, 'fidelityVerified': False}
(out / 'actual_continuous_solver_motion.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print('CONTINUOUS_IVORY_SOLVER_SAVED', end, flush=True)
