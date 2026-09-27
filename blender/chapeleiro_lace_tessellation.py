"""Constrain the actual lace boundary and sample its filled flat surface in metres."""
import math
from collections import Counter
import numpy as np
import bmesh
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt


def refine_physical_triangles(points, faces, width, depth, limit=.0012):
    """Split shared edges and choose quad diagonals in real garment dimensions."""
    points=[p.copy() for p in points];faces=list(faces);rounds=[]
    def distance(a,b):
        delta=points[b]-points[a]
        return math.hypot(delta.x*width,delta.y*depth)
    for iteration in range(12):
        edges={tuple(sorted((p[i],p[(i+1)%3]))) for p in faces for i in range(3)}
        long_edges=sorted(e for e in edges if distance(*e)>limit)
        if not long_edges:break
        midpoints={}
        for a,b in long_edges:
            midpoints[(a,b)]=len(points);points.append(points[a].lerp(points[b],.5))
        refined=[]
        for face in faces:
            mids=[midpoints.get(tuple(sorted((face[i],face[(i+1)%3])))) for i in range(3)]
            count=sum(m is not None for m in mids)
            if count==0:refined.append(face)
            elif count==1:
                i=next(i for i,m in enumerate(mids) if m is not None)
                a,b,c=[face[(i+j)%3] for j in range(3)];m=mids[i]
                refined.extend([(a,m,c),(m,b,c)])
            elif count==2:
                missing=next(i for i,m in enumerate(mids) if m is None)
                i=(missing+2)%3
                a,b,c=[face[(i+j)%3] for j in range(3)]
                p,q=mids[i],mids[(i+2)%3]
                refined.append((a,p,q))
                if distance(p,c)<=distance(b,q):refined.extend([(p,b,c),(p,c,q)])
                else:refined.extend([(p,b,q),(b,c,q)])
            else:
                a,b,c=face;p,q,r=mids
                refined.extend([(a,p,r),(b,q,p),(c,r,q),(p,q,r)])
        faces=refined
        rounds.append({'iteration':iteration,'splitSharedEdges':len(long_edges),'vertices':len(points),'faces':len(faces)})
    else:raise ValueError('Physical edge refinement did not converge.')
    edges={tuple(sorted((p[i],p[(i+1)%3]))) for p in faces for i in range(3)}
    return points,faces,{'physicalTriangleRefinementRounds':rounds,
                        'actualMaximumFlatPhysicalEdge':max(distance(*e) for e in edges),
                        'maximumAuthoredFlatPhysicalEdge':limit}


def constrained_physical_grid(base, faces, width, depth, spacing=.0006, grid_phase=.37):
    """Keep every real aperture while avoiding inherited long internal diagonals."""
    if min(width,depth,spacing)<=0:
        raise ValueError('Require positive actual garment dimensions.')
    triangles=np.asarray([[base[i][:2] for i in face] for face in faces],dtype=float)
    tri_a,tri_b,tri_c=triangles[:,0],triangles[:,1],triangles[:,2]
    denominator=(tri_b[:,1]-tri_c[:,1])*(tri_a[:,0]-tri_c[:,0])+(tri_c[:,0]-tri_b[:,0])*(tri_a[:,1]-tri_c[:,1])
    valid=np.abs(denominator)>1e-14
    denominator=np.where(valid,denominator,1.)
    boundary=Counter(tuple(sorted((p[i],p[(i+1)%len(p)])))
                     for p in faces for i in range(len(p)))
    boundary_edges=[edge for edge,count in boundary.items() if count==1]
    if any(count>2 for count in boundary.values()):
        raise ValueError('The original own-photo surface is not manifold.')
    original_euler=len(base)-len(boundary)+len(faces)
    # Retain the exact original photo-domain coordinates for constrained
    # triangulation. Sampling distances still use the actual garment metres.
    vertices=[Vector((p.x,p.y)) for p in base]
    edges=[]
    for a,b in boundary_edges:
        va,vb=vertices[a],vertices[b]
        delta=vb-va
        cuts=max(1,math.ceil(math.hypot(delta.x*width,delta.y*depth)/spacing))
        indices=[a]
        for step in range(1,cuts):
            indices.append(len(vertices));vertices.append(va.lerp(vb,step/cuts))
        indices.append(b)
        edges.extend(zip(indices[:-1],indices[1:]))
    def on_original(x,y):
        px,py=x/width,y/depth
        wa=((tri_b[:,1]-tri_c[:,1])*(px-tri_c[:,0])+(tri_c[:,0]-tri_b[:,0])*(py-tri_c[:,1]))/denominator
        wb=((tri_c[:,1]-tri_a[:,1])*(px-tri_c[:,0])+(tri_a[:,0]-tri_c[:,0])*(py-tri_c[:,1]))/denominator
        return bool(np.any(valid&(wa>=-1e-8)&(wb>=-1e-8)&(1-wa-wb>=-1e-8)))
    interior=0
    for row in range(math.ceil(depth/spacing)):
        y=(row+grid_phase)*spacing
        if y>=depth:continue
        for column in range(math.ceil(width/spacing)):
            x=(column+grid_phase)*spacing
            if x<width and on_original(x,y):
                vertices.append(Vector((x/width,y/depth)));interior+=1
    vertices,_,triangles,*_=delaunay_2d_cdt(vertices,edges,[],0,1e-7,False)
    selected=[]
    for triangle in triangles:
        center=sum((vertices[i] for i in triangle),Vector((0,0)))/3
        if on_original(center.x*width,center.y*depth):selected.append(tuple(triangle))
    used=sorted({i for face in selected for i in face})
    indices={old:new for new,old in enumerate(used)}
    result=[Vector((vertices[i].x,vertices[i].y,0)) for i in used]
    selected=[tuple(indices[i] for i in face) for face in selected]
    # CDT can introduce near-coincident intersection vertices when scaling
    # thin contour features. Use the original trace's same normalized weld
    # tolerance before verifying the actual aperture topology.
    bm=bmesh.new()
    points=[bm.verts.new(p) for p in result]
    for face in selected:bm.faces.new([points[i] for i in face])
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.verts.index_update()
    result=[v.co.copy() for v in bm.verts]
    selected=[tuple(v.index for v in face.verts) for face in bm.faces]
    bm.free()
    result,selected,physical_refinement=refine_physical_triangles(result,selected,width,depth)
    actual_edges=Counter(tuple(sorted((p[i],p[(i+1)%len(p)])))
                         for p in selected for i in range(len(p)))
    euler=len(result)-len(actual_edges)+len(selected)
    if euler!=original_euler or any(count>2 for count in actual_edges.values()):
        original_segments=np.asarray([[base[i][:2] for i in edge] for edge in boundary_edges],float)
        original_start=original_segments[:,0];delta=original_segments[:,1]-original_start
        unexpected=[]
        for (a,b),count in actual_edges.items():
            if count!=1:continue
            center=np.asarray(((result[a]+result[b])*.5)[:2])
            offset=center-original_start
            fraction=np.clip(np.sum(offset*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
            distance=float(np.linalg.norm(offset-fraction[:,None]*delta,axis=1).min())
            if distance>1e-6:unexpected.append({'edge':[a,b],'center':center.tolist(),'normalizedGap':distance})
        raise ValueError('Constrained physical triangulation changed the own-photo surface topology: '
                         +str({'width':width,'before':original_euler,'after':euler,'vertices':len(result),'faces':len(selected),
                               'unexpectedBoundaryEdges':sorted(unexpected,key=lambda p:p['normalizedGap'],reverse=True)[:6]}))
    lengths=[math.hypot((result[a].x-result[b].x)*width,(result[a].y-result[b].y)*depth)
             for a,b in actual_edges]
    return result,selected,{**physical_refinement,'flatPhysicalGridSpacing':spacing,'gridPhase':grid_phase,'interiorSamples':interior,
        'contourCoordinateDomain':'unchanged original normalized photo domain',
        'templateEulerBefore':original_euler,'templateEulerAfter':euler,
        'templateVertices':len(result),'templateFaces':len(selected),
        'actualMaximumFlatPhysicalEdge':max(lengths),
        'normalizedNumericWeldTolerance':.00001,
        'originalInternalDiagonalsRetained':False,'actualBoundaryContoursPreserved':True}
