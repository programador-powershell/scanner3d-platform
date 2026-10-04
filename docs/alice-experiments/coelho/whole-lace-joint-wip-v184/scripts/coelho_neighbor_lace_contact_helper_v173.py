"""Actual triangle contacts between distinct geometric lace motifs."""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from coelho_lace_triangle_audit_v091 import sat_intersects
def audit_neighbors(P,triangles,facepath,paths,offsets):
    keys=sorted(set((p['side'],p['motif']) for p in paths)); groupids={k:i for i,k in enumerate(keys)}
    pathgroup=np.asarray([groupids[(p['side'],p['motif'])] for p in paths]); facegroup=pathgroup[facepath]; pointgroup=np.repeat(pathgroup,np.diff(offsets))
    groupfaces=[np.flatnonzero(facegroup==i) for i in range(len(keys))]; groupverts=[np.flatnonzero(pointgroup==i) for i in range(len(keys))]; trees=[]; boxes=[]
    for i in range(len(keys)):
        vi=groupverts[i]; pt=P[vi]; tri=triangles[groupfaces[i]]; local=np.searchsorted(vi,tri)
        trees.append(BVHTree.FromPolygons([Vector(p) for p in pt],[tuple(t) for t in local],all_triangles=True)); boxes.append([pt.min(0),pt.max(0)])
    boxes=np.asarray(boxes); rows=[]; constraints=set()
    def section(pid,ti):
        ids=(triangles[ti]-offsets[pid])//6; count=paths[pid]['pointsCount']
        if paths[pid]['closedCenterline'] and 0 in ids and count-1 in ids: return count-1
        return min(int(ids.min()),count-2)
    for i in range(len(keys)):
        for j in np.flatnonzero(np.all(boxes[i,0]<=boxes[:,1]+1e-9,axis=1)&np.all(boxes[i,1]>=boxes[:,0]-1e-9,axis=1)&(np.arange(len(keys))>i)):
            pairs=trees[i].overlap(trees[j]); count=0; pathpairs=set()
            for k in range(0,len(pairs),4096):
                chunk=np.asarray(pairs[k:k+4096],np.int32); ia=groupfaces[i][chunk[:,0]]; ib=groupfaces[j][chunk[:,1]]; hits=sat_intersects(P[triangles[ia]],P[triangles[ib]])
                count+=int(hits.sum())
                for ta,tb in zip(ia[hits],ib[hits]):
                    a,b=int(facepath[ta]),int(facepath[tb]); pathpairs.add((a,b)); constraints.add((a,section(a,ta),b,section(b,tb)))
            if count: rows.append(dict(motifA=list(keys[i]),motifB=list(keys[j]),SATTrianglePairs=count,pathPairs=[list(x) for x in sorted(pathpairs)]))
    return dict(SATTrianglePairs=sum(x['SATTrianglePairs'] for x in rows),intersectingMotifPairs=len(rows),contacts=rows),sorted(constraints)
