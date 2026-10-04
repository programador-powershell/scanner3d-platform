"""2D grid broadphase plus continuous triangle SAT; coplanar BVH295 is rejected."""
import bpy,numpy as np,json,hashlib,time,itertools
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';start=time.time();epsilon=1e-12
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sat(A,B):
    edges=np.concatenate((np.roll(A,-1,axis=1)-A,np.roll(B,-1,axis=1)-B),axis=1);axes=np.stack((-edges[:,:,1],edges[:,:,0]),axis=2);length=np.linalg.norm(axes,axis=2);assert (length>1e-15).all();axes/=length[:,:,None];pa=np.einsum('nvc,nac->nva',A,axes);pb=np.einsum('nvc,nac->nva',B,axes);return ((np.minimum(pa.max(1),pb.max(1))-np.maximum(pa.min(1),pb.min(1)))>epsilon).all(1)
def broad(T):
    minimum=T.min(1);maximum=T.max(1);lo=np.floor(minimum*128).astype(int);hi=np.floor(maximum*128).astype(int);cells={};encoded=set();N=len(T)
    for i,(lower,upper) in enumerate(zip(lo,hi)):
        for x in range(lower[0],upper[0]+1):
            for y in range(lower[1],upper[1]+1):cells.setdefault((x,y),[]).append(i)
    for indices in cells.values():
        encoded.update(i*N+j for i,j in itertools.combinations(indices,2))
    pairs=np.asarray([(k//N,k%N) for k in sorted(encoded)],np.int32).reshape(-1,2)
    if len(pairs):pairs=pairs[(np.minimum(maximum[pairs[:,0]],maximum[pairs[:,1]])-np.maximum(minimum[pairs[:,0]],minimum[pairs[:,1]])>=0).all(1)]
    return pairs
unit=np.array([[[0,0],[1,0],[0,1]],[[.1,.1],[.2,.1],[.1,.2]],[[2,2],[3,2],[2,3]],[[1,0],[1,1],[0,1]],[[0,0],[1,0],[0,1]]],float);up=broad(unit);actual={(int(i),int(j)) for i,j in up[sat(unit[up[:,0]],unit[up[:,1]])]};assert actual=={(0,1),(0,4),(1,4)},actual
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v417.json');source=R/a['path'];assert hashlib.sha256(source.read_bytes()).hexdigest()==a['sha256'];T=[];records=[]
for row in a['newObjects']:
    ob=bpy.data.objects[row['object']];m=ob.data;m.calc_loop_triangles();uv=np.asarray([x.uv[:] for x in m.uv_layers.active.data],np.float64)
    for t in m.loop_triangles:T.append(uv[list(t.loops)]);records.append(dict(object=ob.name,polygon=t.polygon_index))
T=np.asarray(T);pairs=broad(T);print('UV418_2D_GRID_BROADPAIRS',len(pairs),flush=True);hits=[]
for k in range(0,len(pairs),8192):
    pair=pairs[k:k+8192];hits.extend(pair[sat(T[pair[:,0]],T[pair[:,1]])].tolist())
examples=[dict(triangleA=i,triangleB=j,faceA=records[i],faceB=records[j]) for i,j in hits[:100]];np.savez_compressed(O/'apron_ornament_continuous_uv_overlap_pairs_v418.npz',pairs=np.asarray(hits,np.int32).reshape(-1,2),triangleObjectIndex=np.asarray([next(k for k,r in enumerate(a['newObjects']) if r['object']==x['object']) for x in records],np.int16),trianglePolygonIndex=np.asarray([x['polygon'] for x in records],np.int32));report=dict(version='v418',sourceCandidate='v417',sourceSHA256=a['sha256'],method='Inclusive actual triangle AABB coverage in a 128x128 2D spatial grid, unique pairs, six normalized 2D edge-axis SAT strict positive interval overlap >1e-12 UV.',unitTestsPassed=True,unitTestsCoverContainedIdenticalSeparatedAndSharedEdgeTriangles=True,triangles=len(T),broadphasePairs=len(pairs),continuousUVOverlapPairs=len(hits),examples=examples,positiveAreaOverlapToleranceUV=epsilon,previousCoplanar3DBVH295RejectedAsNonProof=True,sourceUnchanged=True,notIntegrated=True,notPublished=True,productionComplete=False,elapsedSeconds=time.time()-start);assert hashlib.sha256(source.read_bytes()).hexdigest()==a['sha256'];(O/'apron_ornament_continuous_uv_audit_v418.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('UV418_CONTINUOUS_REVIEW',len(hits),flush=True)
