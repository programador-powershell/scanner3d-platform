"""Local body recovery and authored outer/inner cloth ordering constraints.

Virtual caps are only classification volumes; corrections use the original
cloth triangles. Source vertices, polygons, UVs and skin weights are untouched.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

RAYS=[Vector((.837,.324,.439)).normalized(),Vector((-.413,.823,.388)).normalized()]

def ray_inside(tree,point,direction):
    origin=Vector(point);hits=0
    for _ in range(128):
        location,normal,index,distance=tree.ray_cast(origin,direction,10)
        if location is None:return bool(hits%2)
        hits+=1;origin=location+direction*1e-6
    raise ValueError('Unexpected repeated closed-volume ray intersections')

def closed_state(tree,point):
    results=[ray_inside(tree,point,direction) for direction in RAYS]
    return results[0] if results[0]==results[1] else None

def outside_candidate(tree,point,nearest,normal,margin):
    """Keep the nearest verified exterior candidate; never force a blind recovery."""
    nearest=np.asarray(nearest,dtype=np.float64)
    normal=np.asarray(normal,dtype=np.float64)
    delta=np.asarray(point)-nearest
    directions=[normal,-normal]
    if np.linalg.norm(delta)>1e-10:
        directions.extend([delta/np.linalg.norm(delta),-delta/np.linalg.norm(delta)])
    accepted=[]
    for direction in directions:
        for factor in [1.,2.]:
            candidate=nearest+direction*margin*factor
            if closed_state(tree,candidate) is False:
                distance=tree.find_nearest(Vector(candidate))[3]
                if distance>=margin*.75:
                    if factor==1 and np.array_equal(direction,normal):return candidate
                    accepted.append(candidate)
    if not accepted:return None
    return min(accepted,key=lambda candidate:np.linalg.norm(candidate-point))

def barycentric(point,triangle):
    a,b,c=triangle;u,v,w=b-a,c-a,point-a
    uu,uv,vv,wu,wv=np.dot(u,u),np.dot(u,v),np.dot(v,v),np.dot(w,u),np.dot(w,v)
    denominator=uu*vv-uv*uv
    if abs(denominator)<1e-20:return None
    beta=(vv*wu-uv*wv)/denominator;gamma=(uu*wv-uv*wu)/denominator
    weights=np.clip(np.asarray([1-beta-gamma,beta,gamma]),0,1)
    return weights/weights.sum()

def build_layer_volume(positions,grid):
    """Cap only the independent classification copy of the existing inner sheet."""
    rows,around=grid.shape
    local=positions[grid.ravel()]
    index=np.arange(rows*around).reshape(rows,around)
    quads=np.stack([index[:-1],index[1:],np.roll(index[1:],-1,axis=1),
                    np.roll(index[:-1],-1,axis=1)],axis=-1).reshape(-1,4)
    # Current sources use the same outward winding as this parametric grid.
    triangles=np.concatenate([quads[:,[0,1,2]],quads[:,[0,2,3]]])
    caps=[]
    for c in range(around):
        nxt=(c+1)%around
        caps.extend([[int(index[0,c]),int(index[0,nxt]),len(local)],
                     [int(index[-1,nxt]),int(index[-1,c]),len(local)+1]])
    points=np.concatenate([local,local[index[0]].mean(0)[None],local[index[-1]].mean(0)[None]])
    closed=BVHTree.FromPolygons(points.tolist(),np.concatenate([triangles,caps]).tolist(),all_triangles=True)
    surface=BVHTree.FromPolygons(local.tolist(),triangles.tolist(),all_triangles=True)
    return closed,surface,grid.ravel()[triangles],(points.min(0),points.max(0))

def ordered_layer_contact(positions,inverse,inner_grid,outer_ids,margin):
    """Distribute an outer sheet contact to its actual inner triangle by mass."""
    snapshot=positions.copy()
    closed,surface,triangles,(low,high)=build_layer_volume(snapshot,inner_grid)
    ids=outer_ids[np.all((snapshot[outer_ids]>=low-margin)&(snapshot[outer_ids]<=high+margin),axis=1)]
    deltas=np.zeros_like(positions);degrees=np.zeros(len(positions))
    corrections=ambiguous=unresolved=0
    for i in ids:
        nearest,normal,index,distance=surface.find_nearest(Vector(snapshot[i]))
        if nearest is None:continue
        state=closed_state(closed,snapshot[i])
        if state is None:ambiguous+=1;continue
        if not state and distance>=margin:continue
        candidate=outside_candidate(closed,snapshot[i],nearest,normal,margin)
        if candidate is None:unresolved+=1;continue
        triangle=triangles[index]
        if int(i) in triangle:continue
        weights=barycentric(np.asarray(nearest),snapshot[triangle])
        if weights is None:unresolved+=1;continue
        denominator=inverse[i]+np.sum(inverse[triangle]*weights*weights)
        if denominator<=0:unresolved+=1;continue
        delta=(candidate-snapshot[i])/denominator
        deltas[i]+=inverse[i]*delta;degrees[i]+=1
        np.add.at(deltas,triangle,-inverse[triangle,None]*weights[:,None]*delta)
        np.add.at(degrees,triangle,1)
        corrections+=1
    positions+=deltas/np.maximum(degrees,1)[:,None]*.8
    return {'corrections':corrections,'ambiguousQueries':ambiguous,'unresolvedQueries':unresolved}
