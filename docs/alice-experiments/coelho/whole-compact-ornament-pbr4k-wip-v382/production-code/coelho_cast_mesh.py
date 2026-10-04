import bpy,bmesh,numpy as np,math

def topology(ob):
    m=ob.data;m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],float);T=np.asarray([t.vertices[:] for t in m.loop_triangles]);center=P.mean(0);Q=P-center
    volume=float(np.einsum('ij,ij->i',Q[T[:,0]],np.cross(Q[T[:,1]],Q[T[:,2]])).sum()/6)
    bm=bmesh.new();bm.from_mesh(m);boundary=sum(e.is_boundary for e in bm.edges);nonmanifold=sum(not e.is_manifold for e in bm.edges);unseen=set(bm.verts);components=0
    while unseen:
        stack=[unseen.pop()];components+=1
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                w=e.other_vert(v)
                if w in unseen:unseen.remove(w);stack.append(w)
    bm.free();areas=np.linalg.norm(np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]]),axis=1)/2
    return dict(vertices=len(P),polygons=len(m.polygons),triangles=len(T),connectedComponents=components,boundaryEdges=boundary,nonManifoldEdges=nonmanifold,zeroAreaTriangles=int(np.sum(areas<1e-16)),signedVolumeM3=volume)

def object_from_mesh(name,points,faces,col,origin):
    m=bpy.data.meshes.new(name+'.Mesh');m.from_pydata((np.asarray(points)-origin).tolist(),[],faces);m.update();ob=bpy.data.objects.new(name,m);col.objects.link(ob);ob.location=origin;ob.hide_render=True
    bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
    if topology(ob)['signedVolumeM3']<0:
        bm=bmesh.new();bm.from_mesh(m);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free()
    return ob

def unit(v):return np.asarray(v,float)/np.linalg.norm(v)

def tube(path,radius,closed=False,sides=8):
    path=np.asarray(path,float);P=[];F=[];normal=unit(np.cross(path-path.mean(0),np.roll(path,-1,axis=0)-path.mean(0)).sum(0)) if closed else None
    for j,p in enumerate(path):
        t=unit(path[(j+1)%len(path)]-path[(j-1)%len(path)] if closed else path[min(j+1,len(path)-1)]-path[max(j-1,0)])
        axis=normal if closed else np.array([0,1,0],float)
        if abs(axis@t)>.95:axis=np.array([1,0,0],float)
        axis=unit(axis-t*(axis@t));cross=unit(np.cross(t,axis))
        P.extend(p+radius*(axis*np.cos(a)+cross*np.sin(a)) for a in np.arange(sides)*2*np.pi/sides)
    for j in range(len(path) if closed else len(path)-1):
        for k in range(sides):F.append((j*sides+k,j*sides+(k+1)%sides,((j+1)%len(path))*sides+(k+1)%sides,((j+1)%len(path))*sides+k))
    if not closed:F.extend([tuple(reversed(range(sides))),tuple((len(path)-1)*sides+k for k in range(sides))])
    return np.asarray(P),F

def hollow_cap(root,sides=40):
    # Closed radial cross-section: thin bell walls, hollow interior, narrow
    # collar that intersects the rigid gold adapter. Threads start under it.
    profile=[(.00040,.001),(.00100,.001),(.00120,.0008),(.00260,.0003),(.00270,.0002),(.00285,0),(.00300,-.0028),(.00300,-.003),(.00260,-.003),(.00245,-.0015),(.00235,.0002),(.00040,.0008)]
    P=[];F=[]
    for radius,z in profile:P.extend(np.asarray(root)+[radius*np.cos(a),radius*np.sin(a),z] for a in np.arange(sides)*2*np.pi/sides)
    for j in range(len(profile)):
        for k in range(sides):F.append((j*sides+k,j*sides+(k+1)%sides,((j+1)%len(profile))*sides+(k+1)%sides,((j+1)%len(profile))*sides+k))
    return np.asarray(P),F

def tidy_boolean_result(ob,tolerance=1e-8):
    """Clean only a new boolean result, at a measured 10-nanometer scale.

    No source mesh edits, hole filling or relaxed validity predicates.
    """
    before=np.asarray([v.co[:] for v in ob.data.vertices],float);qaBefore=topology(ob)
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance)
    bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=tolerance)
    bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()
    after=np.asarray([v.co[:] for v in ob.data.vertices],float);nearest=0.
    for k in range(0,len(before),256):nearest=max(nearest,float(np.linalg.norm(before[k:k+256,None]-after[None],axis=2).min(1).max()))
    assert nearest<2*tolerance,'Cleanup moved or discarded vertices beyond the reviewed microscopic bound'
    return dict(before=qaBefore,after=topology(ob),duplicateAndDegenerateCleanupToleranceM=tolerance,maximumRemovedVertexDistanceToSurvivingVertexM=nearest,noHoleFilling=True,noSourceMeshEdited=True)
