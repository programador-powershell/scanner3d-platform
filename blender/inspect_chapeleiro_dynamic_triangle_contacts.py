"""Measure actual nonadjacent edge/face crossings in recorded garment poses."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
from collections import Counter
import numpy as np
from mathutils import Vector,geometry
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--probe',required=True)
p.add_argument('--output',required=True)
p.add_argument('--frames',type=int,nargs='+',default=[1,20,29])
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads(Path(a.probe).read_text(encoding='utf-8'))
assert sha(r['dataFile'])==r['dataSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
d=np.load(r['dataFile']);faces=d['simulation_faces']
triangles=np.concatenate([faces[:,[0,1,2]],faces[:,[0,2,3]]])
owners=np.empty(len(faces),np.int32);start=0
for index,part in enumerate(r['parts']):
    owners[start:start+part['faces']]=index;start+=part['faces']
assert start==len(faces)
triangle_owners=np.r_[owners,owners]
seams={tuple(sorted(pair)) for pair in d['physical_seam_pairs']}
rows=[];arrays={}
for frame in a.frames:
    points=d['actual_simulation_points'][frame-1]
    tree=BVHTree.FromPolygons(points.tolist(),triangles.tolist(),all_triangles=True)
    vectors=[Vector(point) for point in points]
    pairs=[];crossings=[];broad=unresolved=0
    for i,j in tree.overlap(tree):
        if i>=j or set(triangles[i])&set(triangles[j]):continue
        # Direct sewing neighbours are the same seam; this check excludes
        # their intended contact, not other collisions between the garments.
        if any(tuple(sorted((u,v))) in seams for u in triangles[i] for v in triangles[j]):continue
        broad+=1
        t1,t2=[vectors[k] for k in triangles[i]],[vectors[k] for k in triangles[j]]
        hit_point=None
        for edges,surface in [(t1,t2),(t2,t1)]:
            for k in range(3):
                origin,end=edges[k],edges[(k+1)%3];direction=end-origin
                if direction.length_squared<1e-16:continue
                hit=geometry.intersect_ray_tri(*surface,direction,origin,True)
                if hit is None:continue
                fraction=(hit-origin).dot(direction)/direction.length_squared
                if 1e-5<fraction<1-1e-5:hit_point=hit;break
            if hit_point is not None:break
        if hit_point is None:unresolved+=1;continue
        pairs.append((i,j));crossings.append(tuple(hit_point))
    totals=Counter(tuple(sorted((r['parts'][triangle_owners[i]]['key'],r['parts'][triangle_owners[j]]['key']))) for i,j in pairs)
    rows.append({'frame':frame,'nonAdjacentBroadPhasePairs':broad,'properEdgeFaceCrossings':len(pairs),
                 'unresolvedBroadPhasePairs':unresolved,
                 'crossingsByPiecePair':[{'pieces':list(keys),'trianglePairs':count} for keys,count in sorted(totals.items())]})
    arrays[f'frame_{frame:02d}_triangle_pairs']=np.asarray(pairs,np.int32).reshape(-1,2)
    arrays[f'frame_{frame:02d}_crossing_points']=np.asarray(crossings,np.float32).reshape(-1,3)
    print('ACTUAL_TRIANGLE_CONTACT_FRAME',frame,len(pairs),flush=True)
data=out/'actual_triangle_crossings.npz'
np.savez_compressed(data,actual_triangles=triangles,**arrays)
report={'sourcePhysicalDataSha256':r['dataSha256'],'sourcePhotoSha256':r['sourcePhotoSha256'],
        'actualPhysicalVertices':len(d['simulation_rest_points']),'actualPhysicalTriangles':len(triangles),
        'frames':rows,'dataFile':str(data),'dataSha256':sha(data),'scriptSha256':sha(__file__),
        'sourceTrajectoryUnchanged':sha(r['dataFile'])==r['dataSha256'],
        'clothCollisionVerified':False,'fidelityVerified':False,
        'limitation':'Only proper interior edge/face crossings in the selected recorded poses. Coplanar/endpoint pairs, thickness and continuous-time contact are not approved.'}
(out/'triangle_contact_inspection.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
shutil.copyfile(__file__,out/'executed_inspection.py')
print(json.dumps(rows))
