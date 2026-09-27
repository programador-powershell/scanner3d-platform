"""Measure recorded cloth vertices against the actual animated closed proxies.

This is a vertex penetration diagnostic, not a continuous collision test or a
fidelity approval. It never reruns the cloth solver or alters the source model.
"""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
p.add_argument('--points-field', choices=['actual_simulation_points', 'actual_simulation_skin_targets', 'points', 'actual_skin_targets'], default='actual_simulation_points')
p.add_argument('--minimum-pin-weight', type=float)
p.add_argument('--fixed-body-triangles',action='store_true')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g, r = read(path), read(a.probe)
assert sha(g['editableBlend']) == g['editableBlendSha256'] == r['parentEditableSha256']
assert sha(r['dataFile']) == r['dataSha256']
assert sha(g['exports']['foundation']['sourcePhoto']) == r['sourcePhotoSha256']
assert not out.exists()
out.mkdir(parents=True)
started = time.time()
data = np.load(r['dataFile'])
assert a.points_field in data.files
fine_points = a.points_field in ['points', 'actual_skin_targets']
point_count = len(data['rest_points'] if fine_points else data['simulation_rest_points'])
pin_values = data['pin_weights'] if fine_points else data['simulation_pin_weights']
assert data[a.points_field].shape[1] == point_count and len(pin_values) == point_count
query_ids = (np.arange(point_count) if a.minimum_pin_weight is None
             else np.flatnonzero(pin_values >= a.minimum_pin_weight))
assert len(query_ids) > 0
query_index = np.full(point_count, -1, np.int32)
query_index[query_ids] = np.arange(len(query_ids))
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_closed_underlayer_proxies import closed_thin_underlayer_proxies
names = ['01 / left stocking / fitted leg ankle and closed toe', '01 / right stocking / fitted leg ankle and closed toe',
         '01 / bloomers / continuous waist and sewn crotch']
reference_root = Path(g.get('authoringReferenceRoot', path.parent))
proxies, proxy_rows = closed_thin_underlayer_proxies(scene, read(reference_root / 'skin_audit.json'), names, rig,
                                                 triangulate_before_deformation=a.fixed_body_triangles)
for collection in bpy.data.collections: collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, *proxies]
    if obj in [rig, *proxies]: obj.hide_set(False)
bone_names = data['bone_names'].tolist()
assert bone_names == [b.name for b in rig.data.bones]
bind = {b.name: b.matrix_local.copy() for b in rig.data.bones}
directions = [Vector((.837, .324, .439)).normalized(), Vector((-.413, .823, .388)).normalized()]
part_indices, start = [], 0
for part in r['parts']:
    indices = (np.arange(part['start'], part['start'] + part['vertices']) if fine_points
               else np.unique(data['simulation_faces'][start:start + part['faces']]))
    part_indices.append(query_index[indices][query_index[indices] >= 0])
    start += part['faces']

def inside(tree, point, direction):
    count, origin = 0, Vector(point)
    for i in range(64):
        location, normal, index, distance = tree.ray_cast(origin, direction, 2.)
        if location is None: return count % 2 == 1
        count += 1
        origin = location + direction * 1e-6
    raise ValueError('Unexpected repeated proxy ray intersections.')

rows, masks, distances, agreements = [], [], [], []
proxy_points, proxy_triangles = [[] for _ in proxies], [[] for _ in proxies]
for frame, all_points in enumerate(data[a.points_field], 1):
    carrier = all_points[query_ids]
    desired = {n: Matrix(data['rig_deformations'][frame - 1, i].tolist()) @ bind[n] for i, n in enumerate(bone_names)}
    for bone in rig.data.bones:
        parent = {'parent_matrix': desired[bone.parent.name], 'parent_matrix_local': bind[bone.parent.name]} if bone.parent else {}
        rig.pose.bones[bone.name].matrix_basis = bone.convert_local_to_pose(desired[bone.name], bind[bone.name], invert=True, **parent)
    bpy.context.view_layer.update()
    matrix_error = float(np.abs(np.array([np.asarray(rig.pose.bones[n].matrix @ bind[n].inverted()) for n in bone_names]) - data['rig_deformations'][frame - 1]).max())
    assert matrix_error < 1e-5
    frame_rows, frame_masks, frame_distances, frame_agreements = [], [], [], []
    for index, (obj, row) in enumerate(zip(proxies, proxy_rows)):
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        points = np.asarray([tuple(ev.matrix_world @ v.co) for v in mesh.vertices], np.float32)
        triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles], np.int32)
        if a.fixed_body_triangles and proxy_triangles[index]:
            assert np.array_equal(triangles,proxy_triangles[index][0]), 'Body calculation faces changed during pose'
        tree = BVHTree.FromPolygons([Vector(v) for v in points], triangles.tolist(), all_triangles=True, epsilon=0.)
        ev.to_mesh_clear()
        proxy_points[index].append(points)
        proxy_triangles[index].append(triangles)
        xyz = points[triangles]
        volume = float(np.sum(np.sum(xyz[:, 0] * np.cross(xyz[:, 1], xyz[:, 2]), axis=1)) / 6)
        assert volume > 0
        tests, near = [], []
        for point in carrier:
            near.append(tree.find_nearest(Vector(point))[3])
            tests.append([inside(tree, point, direction) for direction in directions])
        tests, near = np.asarray(tests, bool), np.asarray(near, np.float32)
        agree = tests[:, 0] == tests[:, 1]
        # Rigged garments can fold and intersect themselves. Preserve ambiguous
        # queries instead of silently treating one ray as a reliable volume.
        certain = agree & tests[:, 0] & (near > 1e-5)
        components = []
        for part, ids in zip(r['parts'], part_indices):
            components.append({'key': part['key'], 'verticesTested': len(ids),
                               'certainInsideVertices': int(certain[ids].sum()),
                               'maximumCertainPenetrationMeters': float(near[ids][certain[ids]].max()) if certain[ids].any() else 0.,
                               'ambiguousRayQueries': int((~agree[ids] & (near[ids] > 1e-5)).sum())})
        frame_rows.append({'proxyIndex': index, 'signedVolumeCubicMeters': volume,
                           'certainInsideVertices': int(certain.sum()),
                           'maximumCertainPenetrationMeters': float(near[certain].max()) if certain.any() else 0.,
                           'ambiguousRayQueries': int((~agree & (near > 1e-5)).sum()), 'parts': components})
        frame_masks.append(certain)
        frame_distances.append(near)
        frame_agreements.append(agree)
    rows.append({'frame': frame, 'recordedRigMatrixMaximumError': matrix_error, 'proxies': frame_rows})
    masks.append(frame_masks); distances.append(frame_distances); agreements.append(frame_agreements)
    print('ACTUAL_DYNAMIC_CLEARANCE', frame, len(data['actual_simulation_points']), round(time.time() - started, 2), flush=True)
arrays = {'queried_point_vertex_indices': query_ids, 'certain_inside_masks': np.asarray(masks), 'nearest_distances': np.asarray(distances),
          'two_ray_agreements': np.asarray(agreements)}
if not fine_points: arrays['queried_simulation_vertex_indices'] = query_ids
for index in range(len(proxies)):
    arrays[f'proxy_{index}_animated_world_points'] = np.asarray(proxy_points[index])
    arrays[f'proxy_{index}_animated_triangles'] = np.asarray(proxy_triangles[index])
datafile = out / 'actual_dynamic_clearance.npz'
np.savez_compressed(datafile, **arrays)
report = {'sourcePhysicalDataSha256': r['dataSha256'], 'sourcePhotoSha256': r['sourcePhotoSha256'],
          'actualBodyTrianglesFrozenBeforeDeformation':a.fixed_body_triangles,
          'actualQueriedPointField': a.points_field, 'actualQueriedSurface': 'original_fine_garment_detail' if fine_points else 'coarse_physical_calculator',
          'minimumPinWeight': a.minimum_pin_weight, 'actualVerticesQueriedPerProxyAndFrame': len(query_ids),
          'actualClosedProxies': proxy_rows, 'frames': rows,
          'dataFile': str(datafile), 'dataSha256': sha(datafile), 'scriptSha256': sha(__file__),
          'closedProxyHelperSha256': sha(Path(__file__).with_name('chapeleiro_closed_underlayer_proxies.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'parentGlbUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'noVisualSourceOrPhysicalTrajectoryChanged': True,
          'motionVerified': False, 'clothCollisionVerified': False, 'fidelityVerified': False,
          'limitation': 'Recorded vertex queries only; edges/faces crossing and continuous-time contacts are not tested. Proxy caps close garment boundaries for the diagnostic, not the visible garments.',
          'elapsedSeconds': time.time() - started}
(out / 'dynamic_clearance_inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_inspection.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_closed_underlayer_proxies.py'), out / 'executed_closed_proxy_helper.py')
print('ACTUAL_DYNAMIC_CLEARANCE_SAVED', flush=True)
