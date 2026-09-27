"""Measure rest-carrier winding and clearance against actual thin underlayers."""
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
assert sha(r['dataFile']) == r['dataSha256'] and sha(g['editableBlend']) == g['editableBlendSha256']
assert not out.exists()
out.mkdir(parents=True)
data = np.load(r['dataFile'])
vertices, faces = data['simulation_rest_points'], data['simulation_faces']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_cloth_colliders import thin_underlayer_colliders
names = ['01 / left stocking / fitted leg ankle and closed toe', '01 / right stocking / fitted leg ankle and closed toe',
         '01 / bloomers / continuous waist and sewn crotch']
colliders, source_rows = thin_underlayer_colliders(scene, read(path.parent / 'skin_audit.json'), names, rig)
for collection in bpy.data.collections: collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, *colliders]
    if obj in [rig, *colliders]: obj.hide_set(False)
bpy.context.view_layer.update()

def winding(points, polygons):
    triangles = np.concatenate([np.asarray(polygons)[:, [0, 1, 2]], np.asarray(polygons)[:, [0, 2, 3]]]) if np.asarray(polygons).shape[1] == 4 else np.asarray(polygons)
    xyz = points[triangles]
    normal = np.cross(xyz[:, 1] - xyz[:, 0], xyz[:, 2] - xyz[:, 0])
    center = xyz.mean(1)
    radial = center - points.mean(0)
    radial[:, 2] = 0
    sign = np.sum(normal * radial, axis=1)
    signed_volume = float(np.sum(np.sum(xyz[:, 0] * np.cross(xyz[:, 1], xyz[:, 2]), axis=1)) / 6)
    counts = {}
    for tri in triangles:
        for i in range(3):
            pair = tuple(sorted((int(tri[i]), int(tri[(i+1) % 3]))))
            counts[pair] = counts.get(pair, 0) + 1
    return {'radialOutwardFacingTrianglesFraction': float(np.mean(sign > 0)),
            'radialInwardFacingTrianglesFraction': float(np.mean(sign < 0)),
            'signedVolumeCubicMeters': signed_volume, 'boundaryEdges': sum(n == 1 for n in counts.values()),
            'nonmanifoldEdges': sum(n > 2 for n in counts.values()),
            'limitation': 'Radial signs use the object centroid and are descriptive on curved limbs; signed volume is definitive for closed consistent surfaces only.'}

parts, face_start = [], 0
trees = {}
for part in r['parts']:
    subset = faces[face_start:face_start + part['faces']]
    face_start += part['faces']
    ids, local = np.unique(subset, return_inverse=True)
    local_faces = local.reshape(subset.shape)
    parts.append({'key': part['key'], **winding(vertices[ids], local_faces)})
    trees[part['key']] = BVHTree.FromPolygons([Vector(v) for v in vertices[ids]], local_faces.tolist(), all_triangles=False, epsilon=0.)
collider_reports = []
for obj, row in zip(colliders, source_rows):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    points = np.asarray([tuple(ev.matrix_world @ v.co) for v in mesh.vertices], np.float32)
    triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles], np.int32)
    tree = BVHTree.FromPolygons([Vector(v) for v in points], triangles.tolist(), all_triangles=True, epsilon=0.)
    ev.to_mesh_clear()
    distances, signed = [], []
    for point in vertices:
        nearest, normal, index, distance = tree.find_nearest(Vector(point))
        assert nearest is not None
        distances.append(distance)
        signed.append((Vector(point) - nearest).dot(normal))
    distances, signed = np.asarray(distances), np.asarray(signed)
    collider_reports.append({'source': row, 'vertices': len(points), 'triangles': len(triangles),
                             **winding(points, triangles),
                             'carrierPointsWithinTwoMillimeters': int(np.count_nonzero(distances < .002)),
                             'carrierPointsBehindGeometricNormalByOneMillimeter': int(np.count_nonzero(signed < -.001)),
                             'nearestDistance05PercentileMeters': float(np.percentile(distances, 5)),
                             'minimumDistanceMeters': float(distances.min())})
near_layers = []
for first, second in [('ivory', 'support'), ('tier1', 'support'), ('tier2', 'support'), ('tier3', 'support')]:
    part = next(p for p in r['parts'] if p['key'] == first)
    subset_start = sum(p['faces'] for p in r['parts'][:r['parts'].index(part)])
    ids = np.unique(faces[subset_start:subset_start + part['faces']])
    distances = [trees[second].find_nearest(Vector(vertices[i]))[3] for i in ids]
    near_layers.append({'first': first, 'second': second, 'testedPhysicalVertices': len(ids),
                        'physicalVerticesWithinTwoMillimeters': int(np.count_nonzero(np.asarray(distances) < .002)),
                        'distance05PercentileMeters': float(np.percentile(distances, 5)),
                        'limitation': 'Welded seam vertices are included; proximity alone is not a triangle-intersection or penetration test.'})
report = {'sourcePhysicalDataSha256': r['dataSha256'], 'sourcePhotoSha256': r['sourcePhotoSha256'],
          'actualRestMeshWinding': parts, 'actualThinColliders': collider_reports,
          'actualRestInterlayerProximity': near_layers, 'scriptSha256': sha(__file__),
          'colliderHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_colliders.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'noMeshOrSimulationWasSavedOrModified': True, 'notAContactOrFidelityApproval': True}
(out / 'rest_contact_inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_inspection.py')
print(json.dumps({'carriers': parts, 'colliders': [{k: v for k,v in row.items() if k != 'source'} for row in collider_reports],
                  'interlayers': near_layers}, indent=2))
