"""Independent whole-source comparison across all 42 frames of the same linked Walk STUDY."""
import bpy,sys,json,numpy as np
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'walk_continuity_independent_REVIEW_v1147';D.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash,audit_link
cur=json.loads((R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json').read_text(encoding='utf-8-sig'));candidate=json.loads((O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/manifest.json').read_text(encoding='utf-8-sig'));assert candidate['allFourSameCameraRendersComplete'] and len(candidate['renders'])==4
for im in candidate['renders']:assert sha(R/im['path'])==im['sha256']
N=np.load(O/'distinct_stocking_cloth_weights_CANDIDATE_v1146/character_weights_v1146.npz');P=N['positions'].astype(np.float64);inv=N['physicalSurfaceGroup'];_,first=np.unique(inv,return_index=True);native=np.load(O/'whole_skin_export_source_character_v1099.npz');tri=native['triangles'];edges=np.unique(np.sort(np.concatenate([tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]]]),axis=1),axis=0);restLen=np.linalg.norm(P[edges[:,1]]-P[edges[:,0]],axis=1);valid=restLen>1e-5;classes={key:N[key][edges].all(1)&valid for key in ['forearm','sleeve','boots']};classes['all']=valid;classes['bootBoundary']=N['boots'][edges].sum(1)==1
def sig(ob):return dict(positions=array_hash(ob.data.vertices,'co',3),indices=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
def evaluate(label,path,expectedHash):
 assert sha(path)==expectedHash
 if Path(bpy.data.filepath).resolve()!=path.resolve():bpy.ops.wm.open_mainfile(filepath=str(path))
 ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=bpy.data.objects['Alice.Shared.Rig'];assert sig(ob)==candidate['sourceGeometrySignature'];link=audit_link(R/'SharedBase/Development/alice_shared_base.blend');actions={s.action.name:s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action};action=next(a for n,a in actions.items() if n.startswith('Walk /'));assert action.library
 for t in rig.animation_data.nla_tracks:t.mute=True
 rig.animation_data.action=action
 if len(action.slots):rig.animation_data.action_slot=action.slots[0]
 for pb in rig.pose.bones:pb.matrix_basis.identity()
 records=[];allWorst={}
 for f in range(1,43):
  bpy.context.scene.frame_set(f);bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();co=np.empty(len(m.vertices)*3,np.float32);m.vertices.foreach_get('co',co);Q=co.reshape(-1,3).astype(np.float64);mat=np.asarray(ev.matrix_world);Q=Q@mat[:3,:3].T+mat[:3,3];ev.to_mesh_clear();assert len(Q)==len(P) and np.isfinite(Q).all();seam=float(np.linalg.norm(Q-Q[first[inv]],axis=1).max());length=np.linalg.norm(Q[edges[:,1]]-Q[edges[:,0]],axis=1);ratio=length/np.maximum(restLen,1e-5);rows={}
  for key,mask in classes.items():
   ids=np.flatnonzero(mask);bad=ids[(restLen[ids]<.03)&(length[ids]>.12)];rows[key]=dict(edges=len(ids),maxStretchRatio=float(ratio[ids].max()) if len(ids) else 0,p99StretchRatio=float(np.percentile(ratio[ids],99)) if len(ids) else 0,shortRestEdgesExpandedBeyond12cm=len(bad),maxLengthGrowthM=float((length-restLen)[ids].max()) if len(ids) else 0)
   worst=ids[np.argsort((length-restLen)[ids])[-10:]][::-1];allWorst[f'{key}_frame{f}']=[dict(vertexIDs=edges[i].tolist(),restLengthM=float(restLen[i]),posedLengthM=float(length[i]),restPoints=P[edges[i]].tolist(),posedPoints=Q[edges[i]].tolist()) for i in worst]
  records.append(dict(frame=f,exactPositionUVSeamMaxSeparationM=seam,edgeStatistics=rows))
  if label=='candidate':assert seam<2e-6,(f,seam)
  if f==11:np.savez_compressed(D/f'{label}_whole_frame11_v1147.npz',positions=Q.astype(np.float32),edges=edges)
  print('WALK_EDGE_AUDIT',label,f,'seam',seam,'bootBad',rows['boots']['shortRestEdgesExpandedBeyond12cm'],'armBad',rows['forearm']['shortRestEdgesExpandedBeyond12cm'],flush=True)
 assert sig(ob)==candidate['sourceGeometrySignature'];assert sha(path)==expectedHash
 (D/f'{label}_worst_edges_v1147.json').write_text(json.dumps(allWorst,indent=2),encoding='utf-8')
 return dict(sourceSHA256=expectedHash,sourceUnchanged=True,sharedLibraryUnchanged=True,linkedCommonAction=action.name,frames=records,maxSeamSeparationM=max(r['exactPositionUVSeamMaxSeparationM'] for r in records))
baseline=evaluate('baseline',R/cur['currentBlend'],cur['files']['blend']['sha256']);changed=evaluate('candidate',Path(candidate['blend']),candidate['blendSHA256'])
report=dict(version='v1147',kind='independent_reopen_same_action_all_frames_weight_continuity_review',baseline=baseline,candidate=changed,geometryAllUVNormalsMaterialsExactlyPreserved=True,seamDefinition='exact rest position within same reviewed physical surface role; touching garment versus stocking may legitimately separate',canonicalBaseNotPromoted=True,noBlendOrExportSaved=True,visualApprovalRequired=True,rigComplete=False,gameplayApproved=False,productionComplete=False,additionalTripoCredits=0,VercelUsed=False);(D/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ALL_42_FRAMES_BASELINE_AND_CANDIDATE_AUDITED_NOT_GAMEPLAY_APPROVAL',flush=True)
