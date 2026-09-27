"""Infer arm membership on the intact native surface, without editing geometry.

Spatial bone capsules alone steal nearby skirt vertices. Original surface
components supply a common label, including coincident UV seam aliases in a
measurement graph only. Anatomical membership remains subject to visual review.
"""
import numpy as np

def native_arm_components(obj,bones,arm_names):
    mesh=obj.data
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    matrix=np.asarray(obj.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    edges=np.empty(len(mesh.edges)*2,np.int32);mesh.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
    _,aliases=np.unique(np.round(points,7),axis=0,return_inverse=True)
    parent=np.arange(int(aliases.max())+1);rank=np.zeros(len(parent),np.int8)
    def find(index):
        while parent[index]!=index:
            parent[index]=parent[parent[index]];index=parent[index]
        return index
    for a,b in aliases[edges]:
        a,b=find(int(a)),find(int(b))
        if a==b:continue
        if rank[a]<rank[b]:a,b=b,a
        parent[b]=a
        if rank[a]==rank[b]:rank[a]+=1
    roots=np.array([find(int(i)) for i in aliases])
    _,components=np.unique(roots,return_inverse=True);count=int(components.max())+1
    lower=np.full((count,3),np.inf);upper=np.full((count,3),-np.inf)
    np.minimum.at(lower,components,points);np.maximum.at(upper,components,points)
    counts=np.bincount(components,minlength=count);near=np.zeros(len(points),bool)
    for side,sign in [('Left',1),('Right',-1)]:
        indices=np.flatnonzero((points[:,0]*sign>.06)&(points[:,0]*sign<.23)&(points[:,2]>.42)&(points[:,2]<.71))
        p=points[indices];distance=np.full(len(p),np.inf)
        for name in arm_names[side]:
            head,tail=bones[name];h=np.asarray(head);direction=np.asarray(tail)-h
            fraction=np.clip((p-h)@direction/max(np.dot(direction,direction),1e-15),0,1)
            distance=np.minimum(distance,np.linalg.norm(p-h-fraction[:,None]*direction,axis=1))
        near[indices]=distance<.033
    coverage=np.bincount(components,weights=near,minlength=count)/counts
    labels=np.zeros(count,np.int8);rows=[]
    for index in range(count):
        lo,hi=lower[index],upper[index]
        side='Left' if lo[0]+hi[0]>0 else 'Right';sign=1 if side=='Left' else -1
        minimum_x=lo[0] if sign==1 else -hi[0];maximum_x=hi[0] if sign==1 else -lo[0]
        accepted=(coverage[index]>.5 and lo[2]>.42 and hi[2]<.71
            and minimum_x>.06 and maximum_x<.23 and hi[1]-lo[1]<.13)
        if accepted:labels[index]=sign
        if coverage[index]>0:
            rows.append({'component':index,'vertices':int(counts[index]),'armCoverage':float(coverage[index]),
                'bounds':[lo.tolist(),hi.tolist()],'inferredArmClass':bool(accepted),'inferredSide':side if accepted else None})
    result=labels[components]
    if np.any(result[edges[:,0]]!=result[edges[:,1]]):
        raise ValueError('Native arm membership creates a discontinuity on an original edge.')
    return result,{'method':'inferred common arm label per original surface component with coincident UV aliases',
        'actualVertices':len(points),'actualSurfaceComponents':count,'measurementAliasDecimalPlaces':7,
        'leftArmVertices':int((result==1).sum()),'rightArmVertices':int((result==-1).sum()),
        'originalEdgesCrossingArmClass':0,'componentMeasurements':rows,'geometryEdited':False,
        'classificationVerified':False,'limitation':'Bounds and bone proximity infer semantic membership; arm-to-torso and cloth seams still require review.'}
