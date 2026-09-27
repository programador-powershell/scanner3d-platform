"""Check non-adjacent rest triangles on the actual independent cloth carrier."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from collections import Counter
import bpy
import numpy as np
from mathutils import Vector, geometry
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
r = json.loads(Path(a.probe).read_text(encoding='utf-8'))
assert sha(r['dataFile']) == r['dataSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
data = np.load(r['dataFile'])
points, faces = data['simulation_rest_points'], data['simulation_faces']
mesh = bpy.data.meshes.new('Actual carrier rest intersection diagnostic')
mesh.from_pydata(points.tolist(), [], faces.tolist())
mesh.update(); mesh.calc_loop_triangles()
triangles = np.asarray([tuple(t.vertices) for t in mesh.loop_triangles], np.int32)
polygon_indices = np.asarray([t.polygon_index for t in mesh.loop_triangles], np.int32)
owners, start = np.empty(len(faces), np.int32), 0
for index, part in enumerate(r['parts']):
    owners[start:start + part['faces']] = index; start += part['faces']
edge_faces = Counter(tuple(sorted((face[i], face[(i + 1) % 4]))) for face in faces for i in range(4))
tree = BVHTree.FromPolygons([Vector(p) for p in points], triangles.tolist(), all_triangles=True, epsilon=0.)
vectors = [Vector(p) for p in points]
pairs, points_of_crossing, broad_phase, ambiguous = [], [], 0, 0
for first, second in tree.overlap(tree):
    if first >= second or set(triangles[first]) & set(triangles[second]): continue
    broad_phase += 1
    t1, t2 = [vectors[i] for i in triangles[first]], [vectors[i] for i in triangles[second]]
    crossing = None
    # Endpoints and coplanar overlaps remain explicitly outside this narrow
    # test. Interior edge/face crossings demonstrate a proper intersection.
    for edges, surface in [(t1, t2), (t2, t1)]:
        for i in range(3):
            origin, end = edges[i], edges[(i + 1) % 3]
            direction = end - origin
            hit = geometry.intersect_ray_tri(*surface, direction, origin, True)
            if hit is None: continue
            t = (hit - origin).dot(direction) / direction.length_squared
            if 1e-5 < t < 1 - 1e-5:
                crossing = hit; break
        if crossing is not None: break
    if crossing is not None:
        pairs.append((first, second)); points_of_crossing.append(tuple(crossing))
    else: ambiguous += 1
pairs = np.asarray(pairs, np.int32).reshape(-1, 2)
totals = Counter(tuple(sorted((r['parts'][owners[polygon_indices[i]]]['key'], r['parts'][owners[polygon_indices[j]]]['key']))) for i, j in pairs)
file = out / 'actual_rest_triangle_crossings.npz'
np.savez_compressed(file, actual_rest_points=points, actual_rest_triangles=triangles,
                    actual_polygon_indices=polygon_indices, actual_triangle_pairs=pairs,
                    actual_crossing_points=np.asarray(points_of_crossing, np.float32).reshape(-1, 3))
report = {'sourcePhysicalDataSha256': r['dataSha256'], 'sourcePhotoSha256': r['sourcePhotoSha256'],
          'actualRestVertices': len(points), 'actualRestQuads': len(faces), 'actualRestTriangles': len(triangles),
          'actualBoundaryEdges': sum(n == 1 for n in edge_faces.values()),
          'actualEdgesWithMoreThanTwoFaces': sum(n > 2 for n in edge_faces.values()),
          'nonAdjacentBroadPhasePairs': broad_phase, 'properRestEdgeFaceCrossings': len(pairs),
          'unresolvedBroadPhasePairs': ambiguous,
          'crossingsByPiecePair': [{'pieces': list(keys), 'trianglePairs': count} for keys, count in sorted(totals.items())],
          'dataFile': str(file), 'dataSha256': sha(file), 'scriptSha256': sha(__file__),
          'noModelOrTrajectoryChanged': True, 'clothCollisionVerified': False, 'fidelityVerified': False,
          'limitation': 'Only non-adjacent interior segment/triangle intersections at rest. Coplanar/endpoint pairs and clearance below cloth thickness require separate checks.'}
(out / 'rest_intersection_inspection.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_inspection.py')
print(json.dumps(report, indent=2), flush=True)
