import hashlib,json
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
r=json.loads((base/'retopo_ivory_black_cloth_v011/actual_sewn_solver_motion.json').read_text())
c=json.loads((base/'retopo_ivory_black_cloth_v011/dynamic_clearance_inspection/dynamic_clearance_inspection.json').read_text())
d,b=np.load(r['dataFile']),np.load(c['dataFile'])
rows=[]
for j in range(3):
    trees=BVHTree.FromPolygons(b[f'proxy_{j}_animated_world_points'][0].tolist(),b[f'proxy_{j}_animated_triangles'][0].tolist(),all_triangles=True)
    xyz=d['simulation_rest_points']
    points=b[f'proxy_{j}_animated_world_points'][0]
    ids=np.flatnonzero(np.all((xyz>=points.min(0)-.0015)&(xyz<=points.max(0)+.0015),axis=1))
    signed=[]; distances=[]
    for i in ids:
        co,n,index,distance=trees.find_nearest(Vector(xyz[i]))
        signed.append((Vector(xyz[i])-co).dot(n));distances.append(distance)
    signed,distances=np.asarray(signed),np.asarray(distances)
    rejected=(signed<-.0015)&~b['certain_inside_masks'][0,j,ids]&b['two_ray_agreements'][0,j,ids]
    rows.append({'proxyIndex':j,'testedVertices':len(ids),'falseInteriorClassificationsByNearestNormal':int(rejected.sum()),
                 'maximumRejectedDistanceMeters':float(distances[rejected].max()) if rejected.any() else 0,
                 'certainInsideVerticesAtRecordedRest':int(b['certain_inside_masks'][0,j].sum())})
out=base/'xpbd_contact_sign_inspection_v001.json';assert not out.exists()
out.write_text(json.dumps({'sourceClothSha256':r['dataSha256'],'sourceBodyDataSha256':c['dataSha256'],'actualQueries':rows,
                          'notCollisionOrFidelityApproval':True},indent=2)+'\n')
print(json.dumps(rows))
