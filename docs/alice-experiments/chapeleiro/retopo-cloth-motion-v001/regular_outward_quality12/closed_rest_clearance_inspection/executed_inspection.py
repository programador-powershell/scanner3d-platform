"""Test rest carrier vertices against closed actual underlayer proxy volumes."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g, r = read(path), read(a.probe)
assert sha(g['editableBlend']) == g['editableBlendSha256'] == r['parentEditableSha256']
assert sha(r['dataFile']) == r['dataSha256']
assert not out.exists()
out.mkdir(parents=True)
data = np.load(r['dataFile'])
carrier, faces = data['simulation_rest_points'], data['simulation_faces']
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
proxies, proxy_rows = closed_thin_underlayer_proxies(scene, read(path.parent / 'skin_audit.json'), names, rig)
for collection in bpy.data.collections: collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, *proxies]
    if obj in [rig, *proxies]: obj.hide_set(False)
bpy.context.view_layer.update()
directions = [Vector((.837, .324, .439)).normalized(), Vector((-.413, .823, .388)).normalized()]

def inside(tree, point, direction):
    count, origin = 0, Vector(point)
    for i in range(32):
        location, normal, index, distance = tree.ray_cast(origin, direction, 2.)
        if location is None: return count % 2 == 1
        count += 1
        origin = location + direction * 1e-6
    raise ValueError('Unexpected repeated proxy ray intersections.')

rows, arrays = [], {}
for obj, row in zip(proxies, proxy_rows):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    points = np.asarray([tuple(ev.matrix_world @ v.co) for v in mesh.vertices], np.float32)
    triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles], np.int32)
    tree = BVHTree.FromPolygons([Vector(v) for v in points], triangles.tolist(), all_triangles=True, epsilon=0.)
    ev.to_mesh_clear()
    xyz = points[triangles]
    volume = float(np.sum(np.sum(xyz[:, 0] * np.cross(xyz[:, 1], xyz[:, 2]), axis=1)) / 6)
    assert volume > 0
    masks, distances = [], []
    for point in carrier:
        distances.append(tree.find_nearest(Vector(point))[3])
        masks.append([inside(tree, point, direction) for direction in directions])
    masks, distances = np.asarray(masks, bool), np.asarray(distances, np.float32)
    disagreement = masks[:, 0] != masks[:, 1]
    assert not np.any(disagreement & (distances > 1e-5))
    inside_mask = masks[:, 0] & masks[:, 1] & (distances > 1e-5)
    parts, start = [], 0
    for part in r['parts']:
        ids = np.unique(faces[start:start + part['faces']])
        start += part['faces']
        parts.append({'key': part['key'], 'restPhysicalVertices': len(ids),
                      'verticesInsideClosedProxy': int(np.count_nonzero(inside_mask[ids])),
                      'maximumInsideDistanceMeters': float(distances[ids][inside_mask[ids]].max()) if np.any(inside_mask[ids]) else 0.})
    rows.append({**row, 'actualSignedVolumeCubicMeters': volume,
                 'twoRayDirectionsAgreeAwayFromBoundary': True,
                 'verticesInsideClosedProxy': int(np.count_nonzero(inside_mask)),
                 'maximumInsideDistanceMeters': float(distances[inside_mask].max()) if inside_mask.any() else 0.,
                 'parts': parts})
    arrays[obj.name + '_inside'] = inside_mask
    arrays[obj.name + '_distances'] = distances
datafile = out / 'actual_rest_inside_masks.npz'
np.savez_compressed(datafile, **arrays)
report = {'sourcePhysicalDataSha256': r['dataSha256'], 'sourcePhotoSha256': r['sourcePhotoSha256'],
          'actualClosedProxyRestInspection': rows, 'rawInsideMasksFile': str(datafile), 'rawInsideMasksSha256': sha(datafile),
          'scriptSha256': sha(__file__), 'closedProxyHelperSha256': sha(Path(__file__).with_name('chapeleiro_closed_underlayer_proxies.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'noVisualSourceOrPhysicalTrajectoryChanged': True,
          'notAnAllActionOrFidelityApproval': True,
          'limitation': 'Underlayer caps define independent collision-test volumes only. The visible stockings and bloomers remain open at their original cuffs and waist.'}
(out / 'rest_clearance_inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_inspection.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_closed_underlayer_proxies.py'), out / 'executed_closed_proxy_helper.py')
print(json.dumps({'closedRestVolumes': rows}, indent=2))
