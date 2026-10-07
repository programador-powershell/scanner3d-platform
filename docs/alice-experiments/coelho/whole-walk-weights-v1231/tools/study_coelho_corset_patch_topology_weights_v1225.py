"""Local mesh-edge diffusion study; no Blender source edit or publication."""
from pathlib import Path
import json,numpy as np,heapq,hashlib,collections,time
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'shoulder_topology_weight_STUDY_v1225';D.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));start=time.time()
c=read(R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json');assert c['version']=='v1216' and c['nextPartOrMovementAllowedAfterWholeCheckpoint']
M=np.load(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/character_weights_v1146.npz');G=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1083.npz');ex=np.load(O/'whole_skin_export_source_character_v1202.npz');walk=np.load(O/'whole_skin_walk_world_matrices_v1204.npz');pkg=read(O/'package_skin_export_v1203.json')
P=M['positions'].astype(np.float64);names=M['boneNames'];raw=np.load(O/'remaining_walk_regions_REVIEW_v1221/actual_weights_walk_frame31_v1221.npz');W=raw['weights'].astype(np.float64);assert W.shape==M['weights'].shape;groups=M['physicalSurfaceGroup'];_,first=np.unique(groups,return_index=True);GP=P[first];GW=W[first];roots=G['indexedComponents'];roles=M['physicalRole'];tri=ex['triangles'];edges=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1),axis=0);rest=np.linalg.norm(P[edges[:,0]]-P[edges[:,1]],axis=1)
selectedRoots=np.asarray([75839]);bad=read(O/'remaining_walk_regions_REVIEW_v1221/audit.json')['all42Frames'][30]['edges'];seedVertices=np.unique([v for e in bad for v in e['vertices'] if roots[v] in selectedRoots]);seedGroups=np.unique(groups[seedVertices]);assert len(seedVertices)>0
# Include the observed peak corset frame27, rather than relying only on frame31.
boneIndexSeed={n:i for i,n in enumerate(pkg['boneNames'])};js=np.argsort(W,axis=1)[:,-4:];idsSeed=np.asarray([boneIndexSeed[str(n)] for n in names])[js];restSeed=np.asarray([b['matrixWorld'] for b in pkg['bones']]);deltaSeed=(walk['worldPose'][26]@np.linalg.inv(restSeed))[idsSeed];q27=np.sum(np.einsum('nvij,nj->nvi',deltaSeed,np.column_stack([P,np.ones(len(P))]))[:,:,:3]*np.take_along_axis(W,js,axis=1)[:,:,None],axis=1);bad27=(rest>1e-5)&(rest<.03)&(np.linalg.norm(q27[edges[:,0]]-q27[edges[:,1]],axis=1)>.12);v27=np.unique(edges[bad27]);seedVertices=np.unique(np.concatenate([seedVertices,v27[np.isin(roots[v27],selectedRoots)]]));seedGroups=np.unique(groups[seedVertices]);assert len(seedVertices)==5
eligibleVertex=np.isin(roots,selectedRoots)&np.isin(roles,[0,2,3])&~M['boots']&~M['positiveHand']&~M['negativeHand']
eligible=np.zeros(len(first),bool);eligible[groups[eligibleVertex]]=True;assert eligible[seedGroups].all()
graphEdges=np.unique(np.sort(groups[edges],axis=1),axis=0);graphEdges=graphEdges[graphEdges[:,0]!=graphEdges[:,1]];edgeLength=np.linalg.norm(GP[graphEdges[:,0]]-GP[graphEdges[:,1]],axis=1)
localEdges=graphEdges[eligible[graphEdges].all(1)];localLength=np.linalg.norm(GP[localEdges[:,0]]-GP[localEdges[:,1]],axis=1);adj=collections.defaultdict(list)
for (a,b),length in zip(localEdges,localLength):adj[int(a)].append((int(b),max(float(length),1e-5)));adj[int(b)].append((int(a),max(float(length),1e-5)))
distance=np.full(len(first),np.inf);distance[seedGroups]=0;heap=[(0.,int(g)) for g in seedGroups];heapq.heapify(heap)
while heap:
    length,g=heapq.heappop(heap)
    if length!=distance[g] or length>.080:continue
    for n,edge in adj[g]:
        proposed=length+edge
        if proposed<distance[n] and proposed<=.080:distance[n]=proposed;heapq.heappush(heap,(proposed,n))
selected=distance<.080;ids=np.flatnonzero(selected)
domain=dict(version='v1225',sourceNotEdited=True,seedVertices=seedVertices.tolist(),seedPhysicalGroups=len(seedGroups),eligiblePhysicalGroups=int(eligible.sum()),selectedPhysicalGroups=len(ids),root38212Vertices=int((roots==38212).sum()),root38212Bounds=P[roots==38212].min(0).tolist()+P[roots==38212].max(0).tolist(),selectedVertexIDs=np.flatnonzero(selected[groups]).tolist(),selectedBounds=GP[ids].min(0).tolist()+GP[ids].max(0).tolist(),selectedOriginalBoneTotals={str(n):float(w) for n,w in zip(names,GW[ids].sum(0)) if w>0},surfaceIsVisuallyIdentifiedCorset=True)
(D/'domain_diagnostic_v1225.json').write_text(json.dumps(domain,indent=2),encoding='utf-8');print('SHOULDER_DOMAIN_DIAGNOSTIC',json.dumps({k:domain[k] for k in ['seedPhysicalGroups','eligiblePhysicalGroups','selectedPhysicalGroups','root38212Vertices','root38212Bounds','selectedBounds']}),flush=True)
review=read(O/'corset_patch_weight_review_v1225.json');assert review['acceptedForLimitedTopologyWeightContinuityStudy'] and review['allTwentyActualImagesInspected'];assert 50<len(ids)<500
# Neighbours follow actual triangle topology. Touching unrelated surfaces create no edge.
pair=graphEdges[selected[graphEdges].any(1)];lens=np.linalg.norm(GP[pair[:,0]]-GP[pair[:,1]],axis=1);edgeWeight=1/np.maximum(lens,.002);row=np.concatenate([pair[:,0],pair[:,1]]);col=np.concatenate([pair[:,1],pair[:,0]]);ew=np.concatenate([edgeWeight,edgeWeight]);keep=selected[row];row,col,ew=row[keep],col[keep],ew[keep];den=np.bincount(row,weights=ew,minlength=len(first));assert (den[ids]>0).all()
smooth=GW.copy()
for step in range(120):
    acc=np.zeros((len(first),W.shape[1]),np.float64);np.add.at(acc,row,ew[:,None]*smooth[col]);smooth[ids]=acc[ids]/den[ids,None]
# Compact falloff preserves every weight outside the topology-selected region.
t=np.clip((distance[ids]-.015)/.065,0,1);alpha=1-t*t*(3-2*t);newG=GW.copy();newG[ids]=GW[ids]*(1-alpha[:,None])+smooth[ids]*alpha[:,None]
for g in ids:
    largest=np.argsort(newG[g])[-4:];mask=np.ones(W.shape[1],bool);mask[largest]=False;newG[g,mask]=0;newG[g]/=newG[g].sum()
new=W.copy();new[selected[groups]]=newG[groups[selected[groups]]]
assert np.isfinite(new).all() and np.abs(new.sum(1)-1).max()<1e-5 and (new>0).sum(1).max()<=4
assert np.abs(new-new[first[groups]]).max()<1e-7
changed=np.any(np.abs(new-W)>1e-7,axis=1);assert not (changed&(M['boots']|M['positiveHand']|M['negativeHand'])).any()
assert np.array_equal(new[~selected[groups]],W[~selected[groups]])
boneIndex={n:i for i,n in enumerate(pkg['boneNames'])};indices=np.asarray([boneIndex[str(n)] for n in names]);nativeRest=np.asarray([b['matrixWorld'] for b in pkg['bones']]);inverseRest=np.linalg.inv(nativeRest);HP=np.column_stack([P,np.ones(len(P))])
def pose(weights,world):
    J=np.argsort(weights,axis=1)[:,-4:];vW=np.take_along_axis(weights,J,axis=1);deltas=(world@inverseRest)[indices[J]];Q=np.einsum('nvij,nj->nvi',deltas,HP);return np.sum(Q[:,:,:3]*vW[:,:,None],axis=1)
def stats(Q):
    length=np.linalg.norm(Q[edges[:,0]]-Q[edges[:,1]],axis=1);bad=(rest>1e-5)&(rest<.03)&(length>.12);return dict(allBad=int(bad.sum()),localBad=int((bad&selected[groups[edges]].any(1)).sum()),bootsBad=int((bad&M['boots'][edges].all(1)).sum()),forearmBad=int((bad&M['forearm'][edges].all(1)).sum()),sleeveBad=int((bad&M['sleeve'][edges].all(1)).sum()),samePhysicalSeamMaxM=float(np.linalg.norm(Q-Q[first[groups]],axis=1).max()))
records=[]
for i,f in enumerate(walk['frames']):
    world=walk['worldPose'][i];baseline=pose(W,world);candidate=pose(new,world)
    if int(f)==31:
        true=raw['positions'];error=float(np.linalg.norm(baseline-true,axis=1).max());assert error<2e-6,error
        np.savez_compressed(D/'frame31_topology_comparison_v1225.npz',baseline=baseline.astype(np.float32),candidate=candidate.astype(np.float32),positions=P.astype(np.float32),changed=changed,edges=edges)
    records.append(dict(frame=int(f),baseline=stats(baseline),candidate=stats(candidate)))
    print('TOPOLOGY_SHOULDER_STUDY',int(f),records[-1]['baseline']['allBad'],records[-1]['candidate']['allBad'],flush=True)
np.savez_compressed(D/'character_weights_v1225.npz',weights=new.astype(np.float32),positions=P.astype(np.float32),boneNames=names,changed=changed,physicalSurfaceGroup=groups,topologyDistance=distance[groups].astype(np.float32))
assert sum(r['baseline']['allBad'] for r in records)==read(O/'remaining_walk_regions_REVIEW_v1221/audit.json')['totalBadEdgeOccurrences']
report=dict(version='v1225',readonlyStudySourceAndExportsNotEdited=True,currentWholeGitCheckpoint=c['GitHubCheckpoint']['sourceCommit'],sourceBlend=read(O/'left_patch_weights_whole_CANDIDATE_v1200/manifest.json')['blend'],previousWhole1200OutsideDomainPreserved=True,sameActualOriginalWalk1204Reference=True,baselineFrame31ReproducedMaxM=error,selectedTopologyGroups=len(ids),changedVertices=int(changed.sum()),changedUVRootCounts={str(k):int(v) for k,v in zip(*np.unique(roots[changed],return_counts=True))},changedPhysicalRoleCounts={str(k):int(v) for k,v in zip(*np.unique(roles[changed],return_counts=True))},actualMeshEdgeGraphOnly=True,geodesicRadiusM=.080,smoothIterations=120,outsideDomainWeightsExactlyPreserved=True,geometryUVNormalsMaterialsNotEdited=True,all42Frames=records,visualReviewRequired=True,noWholeBlendOrNewExportsSaved=True,acceptedForProduction=False,productionComplete=False,elapsedSeconds=time.time()-start)
(D/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('SHOULDER_TOPOLOGY_STUDY_COMPLETE_NOT_NATIVE_OR_VISUAL_APPROVAL',flush=True)
