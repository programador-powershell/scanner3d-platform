"""Read-only diagnosis of remaining real Walk distortions after local1191 weights."""
from pathlib import Path
import json, collections, time
import numpy as np
R=Path('F:/Alice/SharedProduction'); O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'; D=O/'remaining_walk_regions_REVIEW_v1196';D.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
M=np.load(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/character_weights_v1146.npz');G=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1083.npz');ex=np.load(O/'whole_skin_export_source_character_v1148.npz');walk=np.load(O/'whole_skin_walk_world_matrices_v1170.npz');pkg=read(O/'package_skin_export_v1150.json');N=np.load(O/'shoulder_topology_weight_STUDY_v1189/character_weights_v1189.npz')
names=M['boneNames'];nameIndex={str(n):i for i,n in enumerate(names)};W=np.zeros(M['weights'].shape,np.float32)
for i in range(ex['joints'].shape[1]):
    verts=np.flatnonzero(ex['joints'][:,i]>=0)
    col=np.asarray([nameIndex[pkg['boneNames'][int(j)]] for j in ex['joints'][verts,i]])
    W[verts,col]=ex['weights'][verts,i]
changed=N['changed'];W[changed]=N['weights'][changed]
P=M['positions'].astype(np.float64);tri=ex['triangles'];edges=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1),axis=0);rest=np.linalg.norm(P[edges[:,0]]-P[edges[:,1]],axis=1);short=(rest>1e-5)&(rest<.03);roots=G['indexedComponents'];roles=M['physicalRole'];groups=M['physicalSurfaceGroup']
boneIndex={n:i for i,n in enumerate(pkg['boneNames'])};indices=np.asarray([boneIndex[str(n)] for n in names]);inverseRest=np.linalg.inv(np.asarray([b['matrixWorld'] for b in pkg['bones']]));HP=np.column_stack([P,np.ones(len(P))]);J=np.argsort(W,axis=1)[:,-4:];vW=np.take_along_axis(W,J,axis=1);records=[];allVertices=[];allEdges=[]
for i,f in enumerate(walk['frames']):
    deltas=(walk['worldPose'][i]@inverseRest)[indices[J]];Q=np.sum(np.einsum('nvij,nj->nvi',deltas,HP)[:,:,:3]*vW[:,:,None],axis=1);length=np.linalg.norm(Q[edges[:,0]]-Q[edges[:,1]],axis=1);bad=short&(length>.12);be=edges[bad];vs=np.unique(be);allVertices.extend(vs.tolist());allEdges.extend(np.flatnonzero(bad).tolist())
    counts={str(k):int(v) for k,v in zip(*np.unique(roots[vs],return_counts=True))};rec=dict(frame=int(f),badEdges=int(bad.sum()),affectedVertices=len(vs),uvRoots=counts)
    if int(f) in [18,31]:
        rec['edges']=[dict(vertices=e.tolist(),uvRoots=roots[e].tolist(),roles=roles[e].tolist(),restM=float(r),posedM=float(l),restPositions=P[e].tolist(),weights=[{str(n):float(w) for n,w in zip(names,W[v]) if w>0} for v in e]) for e,r,l in zip(be,rest[bad],length[bad])]
        np.savez_compressed(D/f'actual_weights_walk_frame{int(f)}_v1196.npz',positions=Q.astype(np.float32),badEdges=be,weights=W)
    records.append(rec)
vs=np.unique(allVertices);uv=np.unique(roots[vs]);domains=[]
for root in uv:
    allIDs=np.flatnonzero(roots==root);affected=vs[roots[vs]==root]
    domains.append(dict(uvRoot=int(root),totalVertices=len(allIDs),badEdgeVertices=len(affected),boundsMin=P[allIDs].min(0).tolist(),boundsMax=P[allIDs].max(0).tolist(),roleCounts={str(k):int(v) for k,v in zip(*np.unique(roles[allIDs],return_counts=True))},dominantBoneTotals={str(n):float(w) for n,w in zip(names,W[allIDs].sum(0)) if w>.01}))
report=dict(version='v1196',nativeCandidate='local_patch_weights_whole_CANDIDATE_v1191',authoritativeOutsideWeightsFromRaw1148=True,localPatch1189NotGlobalZero=True,all42Frames=records,totalBadEdgeOccurrences=sum(x['badEdges'] for x in records),maximumBadEdgesInOneFrame=max(x['badEdges'] for x in records),uniqueBadEdges=len(set(allEdges)),uniqueAffectedVertices=len(vs),domains=domains,noSourceOrExportEdited=True,productionComplete=False)
(D/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ['totalBadEdgeOccurrences','maximumBadEdgesInOneFrame','uniqueBadEdges','uniqueAffectedVertices','domains']},indent=2))
