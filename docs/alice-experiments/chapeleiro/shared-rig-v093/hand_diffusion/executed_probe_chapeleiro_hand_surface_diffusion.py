"""Probe actual palm-weight continuity on the unchanged current native surface."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix

root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/native_surface_measurement_v092')
out=root/'hand_surface_diffusion_v001';assert not out.exists();out.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(root/'measurement.json');a=np.load(root/'native_surface_weights.npz');assert sha(root/'native_surface_weights.npz')==r['dataSha256']
p=a['points'];edges=a['edges'];old=a['weights'];names=[b['name'] for b in r['bones']]
_,aliases=np.unique(np.round(p,7),axis=0,return_inverse=True);count=int(aliases.max())+1
counts=np.bincount(aliases,minlength=count);pairs=np.unique(np.sort(aliases[edges],axis=1),axis=0)
pairs=pairs[pairs[:,0]!=pairs[:,1]]
alias_p=np.stack([np.bincount(aliases,weights=p[:,i],minlength=count)/counts for i in range(3)],axis=1)
rest_lengths=np.linalg.norm(p[edges[:,0]]-p[edges[:,1]],axis=1);valid=rest_lengths>1e-5
selected=np.zeros(len(p),bool);hand_masks={};graphs={};initial={};anchors={};columns={}
for side,sign in [('Left',1),('Right',-1)]:
 cols=[i for i,n in enumerate(names) if n.startswith(side+'Hand')]
 mask=(old[:,cols].sum(1)>.995)&(p[:,0]*sign>.12)&(p[:,2]<.535)&(p[:,2]>.415)
 hand_masks[side]=mask;selected|=mask;columns[side]=cols
 ids=np.unique(aliases[mask]);local=np.full(count,-1,np.int32);local[ids]=np.arange(len(ids));n=len(ids)
 q=pairs[np.all(local[pairs]>=0,axis=1)];q=local[q]
 lengths=np.linalg.norm(alias_p[ids[q[:,0]]]-alias_p[ids[q[:,1]]],axis=1)
 values=1/np.maximum(lengths,.0002)
 graph=coo_matrix((np.r_[values,values],(np.r_[q[:,0],q[:,1]],np.r_[q[:,1],q[:,0]])),shape=(n,n)).tocsr()
 degrees=np.asarray(graph.sum(1)).ravel();graph=graph.multiply(1/np.maximum(degrees,1e-12)[:,None]).tocsr()
 w=np.stack([np.bincount(aliases,weights=old[:,i],minlength=count)[ids]/counts[ids] for i in cols],axis=1)
 boundary=np.unique(pairs[np.any(local[pairs]<0,axis=1)&np.any(local[pairs]>=0,axis=1)])
 anchor=np.isin(ids,boundary)|(degrees==0)
 # Preserve actual measured distal tips; no synthetic importer bone tails.
 for bone in r['bones']:
  if bone['name'].startswith(side+'Hand') and bone['name'].endswith('3'):
   anchor|=np.linalg.norm(alias_p[ids]-np.asarray(bone['tail']),axis=1)<.0025
 initial[side]=(ids,local,w);graphs[side]=graph;anchors[side]=anchor

def quantize(weights):
 keep=np.argpartition(weights,-4,axis=1)[:,-4:];sparse=np.zeros_like(weights)
 np.put_along_axis(sparse,keep,np.take_along_axis(weights,keep,axis=1),axis=1)
 sparse/=sparse.sum(1)[:,None];units=np.rint(sparse*65536).astype(np.int32)
 units[np.arange(len(units)),units.argmax(1)]+=65536-units.sum(1)
 result=units.astype(np.float32)/65536;assert np.all(result.sum(1)==1) and np.all((result>0).sum(1)<=4)
 return result
def posed(weights,matrices):
 result=np.zeros_like(p)
 for i in range(len(names)):
  indices=np.flatnonzero(weights[:,i]>0)
  if len(indices):result[indices]+=(p[indices]@matrices[i,:3,:3].T+matrices[i,:3,3])*weights[indices,i,None]
 return result

reports=[]
for steps in [8,24,48]:
 new=old.copy()
 for side in ['Left','Right']:
  ids,local,w=initial[side];field=w.copy()
  for step in range(steps):
   field=.4*field+.6*(graphs[side]@field);field[anchors[side]]=w[anchors[side]]
  idx=np.flatnonzero(hand_masks[side]);new[np.ix_(idx,columns[side])]=field[local[aliases[idx]]]
 new[selected]=quantize(new[selected]);assert np.array_equal(new[~selected],old[~selected])
 rows=[]
 for i,pose in enumerate(r['poses']):
  before=a['actual_posed_points'][i];after=posed(new,a['bone_deformations'][i])
  br=np.linalg.norm(before[edges[:,0]]-before[edges[:,1]],axis=1)/np.maximum(rest_lengths,1e-10)
  ar=np.linalg.norm(after[edges[:,0]]-after[edges[:,1]],axis=1)/np.maximum(rest_lengths,1e-10)
  hand_edges=valid&np.any(selected[edges],axis=1)
  rows.append({'pose':pose,'beforeWholeMaximum':float(br[valid].max()),'candidateWholeMaximum':float(ar[valid].max()),
   'beforeHandMaximum':float(br[hand_edges].max()),'candidateHandMaximum':float(ar[hand_edges].max()),
   'beforeHandEdgesAbove10':int((br[hand_edges]>10).sum()),'candidateHandEdgesAbove10':int((ar[hand_edges]>10).sum())})
 file=out/f'steps_{steps:02d}.npz';np.savez_compressed(file,weights=new,preserved_vertices=~selected)
 report={'steps':steps,'weightsFile':str(file),'weightsSha256':sha(file),'changedVertices':int(np.any(new!=old,axis=1).sum()),
  'selectedHandVertices':int(selected.sum()),'handAliases':{side:len(initial[side][0]) for side in initial},
  'fixedAnchorAliases':{side:int(anchors[side].sum()) for side in anchors},'nativePoseEstimates':rows,
  'parentEditableSha256':r['parentEditableSha256'],'parentWholeModelSha256':r['parentWholeModelSha256'],
  'sourcePhotoSha256':r['sourcePhotoSha256'],'rawGeometrySha256':r['rawGeometrySha256'],'boneNames':names,
  'measurementDataSha256':r['dataSha256'],'scriptSha256':sha(__file__),
  'method':'weighted original-surface palm/finger diffusion with actual distal tip and wrist boundary anchors; no geometry edits',
  'candidateNativeEstimateOnly':True,'newActualExportEvidence':False,'anatomicalRegionsVerified':False,
  'geometryChanged':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
 (out/f'steps_{steps:02d}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');reports.append(report)
 print(json.dumps({'steps':steps,'changedVertices':report['changedVertices'],'poses':rows},indent=2),flush=True)
(out/'probes.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8',newline='\n')
