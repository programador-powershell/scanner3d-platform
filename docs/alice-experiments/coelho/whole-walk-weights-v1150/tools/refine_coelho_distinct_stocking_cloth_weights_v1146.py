"""Distinguish touching garment/stocking UV shells; preserve all geometry and UVs."""
import bpy,json,sys,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'distinct_stocking_cloth_weights_CANDIDATE_v1146';D.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash,audit_link
src=json.loads((O/'stocking_weight_continuity_CANDIDATE_v1135/manifest.json').read_text(encoding='utf-8-sig'));p=Path(src['blend']);assert Path(bpy.data.filepath).resolve()==p.resolve() and sha(p)==src['blendSHA256'];assert len(src['renders'])==4;link=audit_link(R/'SharedBase/Development/alice_shared_base.blend');ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=bpy.data.objects['Alice.Shared.Rig'];M=np.load(O/'upper_stocking_regions_REVIEW_v1134/anatomical_semantic_masks_v1134.npz');samples=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1083.npz');P=np.asarray([ob.matrix_world@v.co for v in ob.data.vertices]);names=[g.name for g in ob.vertex_groups]
roots=json.loads((O/'walk_weight_regions_REVIEW_v1130/classification.json').read_text(encoding='utf-8-sig'))['bootStockingUVRoots']+json.loads((O/'upper_stocking_regions_REVIEW_v1134/classification.json').read_text(encoding='utf-8-sig'))['newUVRoots'];boots=np.isin(samples['indexedComponents'],roots)|(P[:,2]<.25)
# A common rest position is not sufficient to identify one physical surface. Do not transfer
# stocking weights into the navy dress UV shell (e.g. root95618) merely because they touch.
assert not boots[samples['indexedComponents']==95618].any()
hands=M['positiveHand']|M['negativeHand'];skirt=(P[:,2]<.966)&~boots&~hands&~M['forearm'];assert not (skirt&boots).any()
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),indices=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();assert before==src['sourceGeometrySignature'];old=np.zeros((len(P),len(names)),np.float64)
for v in ob.data.vertices:
 for g in v.groups:old[v.index,g.group]=g.weight
new=old.copy();new[skirt]=0;new[skirt,names.index('Hips')]=1
for side,sign in [('Left',1),('Right',-1)]:
 ids=np.flatnonzero(boots&(P[:,0]*sign>0));t=np.clip((P[ids,2]-.126)/.060,0,1);leg=t*t*(3-2*t);new[ids]=0;new[ids,names.index(side+'Leg')]=leg;new[ids,names.index(side+'Foot')]=1-leg
 ids=ids[P[ids,2]>.30];bn=[side+'UpLeg',side+'Leg'];A=np.asarray([rig.matrix_world@rig.data.bones[n].head_local for n in bn]);B=np.asarray([rig.matrix_world@rig.data.bones[n].tail_local for n in bn]);V=B-A;Q=P[ids];t=np.clip(np.sum((Q[:,None,:]-A)*V,axis=2)/np.maximum(np.sum(V*V,axis=1),1e-20),0,1);distance=np.linalg.norm(Q[:,None,:]-(A+t[:,:,None]*V),axis=2);w=1/np.maximum(distance,.008)**4;w/=w.sum(1)[:,None];ramp=np.clip((P[ids,2]-.30)/.06,0,1);ramp=ramp*ramp*(3-2*ramp);new[ids]*=(1-ramp[:,None])
 for j,n in enumerate(bn):new[ids,names.index(n)]+=ramp*w[:,j]
roles=np.zeros(len(P),np.int32);roles[M['forearm']]=2;roles[M['sleeve']]=3;roles[boots]=4;roles[M['positiveHand']]=1;roles[M['negativeHand']]=5
_,physicalGroup=np.unique(np.column_stack([M['uniquePositionGroup'],roles]),axis=0,return_inverse=True);_,first=np.unique(physicalGroup,return_index=True);seamError=float(np.abs(new-new[first[physicalGroup]]).max());assert seamError<1e-7,seamError
assert np.isfinite(new).all() and np.max(np.abs(new.sum(1)-1))<1e-5 and (new>0).sum(1).max()<=4;changed=np.any(np.abs(new-old)>1e-7,axis=1);ids=np.flatnonzero(changed)
for g in ob.vertex_groups:g.remove(ids.tolist())
for j,g in enumerate(ob.vertex_groups):
 for i in np.flatnonzero(changed&(new[:,j]>0)):g.add([int(i)],float(new[i,j]),'REPLACE')
assert signature()==before
for pb in rig.pose.bones:pb.matrix_basis.identity()
out=D/'alice_coelho_complete_distinct_stocking_cloth_CANDIDATE_v1146.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False);np.savez_compressed(D/'character_weights_v1146.npz',positions=P.astype(np.float32),weights=new.astype(np.float32),boneNames=np.asarray(names),positiveHand=M['positiveHand'],negativeHand=M['negativeHand'],forearm=M['forearm'],sleeve=M['sleeve'],boots=boots,skirt=skirt,uniquePositionGroup=M['uniquePositionGroup'],physicalSurfaceGroup=physicalGroup,physicalRole=roles)
report=dict(src,version='v1146',blend=str(out),bytes=out.stat().st_size,blendSHA256=sha(out),sourceBlend=str(p),sourceSHA256=src['blendSHA256'],changedWeightVertices=int(changed.sum()),stockingVertices=int(boots.sum()),coincidentDressVerticesReleasedFromLegWeight=int((M['boots']&~boots).sum()),skirtProvisionalPelvisVertices=int(skirt.sum()),sourceGeometrySignature=before,geometryUVNormalsMaterialsExactlyPreserved=True,distinctTouchingClothAndStockingSurfacesSeparatedByWeightOnly=True,noWeldCutOrNewAnatomy=True,UVSeamGrouping='exact position plus reviewed anatomical surface role; different touching physical layers may legitimately separate',samePhysicalSurfaceUVSeamWeightMaxError=seamError,allFourSameCameraRendersComplete=False,sourceAndLibraryUnchanged=False,acceptedForPublication=False,gameplayMotionApproved=False,rigComplete=False,productionComplete=False,renders=[]);(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('DISTINCT_STOCKING_CLOTH_WHOLE_CANDIDATE_SAVED_REVIEW_PENDING',flush=True)
actions={s.action.name:s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action};act=next(a for n,a in actions.items() if n.startswith('Walk /'))
for t in rig.animation_data.nla_tracks:t.mute=True
rig.animation_data.action=act
if len(act.slots):rig.animation_data.action_slot=act.slots[0]
s=bpy.context.scene;s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;cam=s.camera
for frame,view,direction in [(1,'front_start',(0,-4,0)),(11,'front_quarter',(0,-4,0)),(31,'front_threequarter',(0,-4,0)),(11,'profile_quarter',(-4,0,0))]:
 s.frame_set(frame);bpy.context.view_layer.update();target=Vector((0,0,.88));cam.data.ortho_scale=2.04;cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();file=D/f'whole_walk_{view}_frame{frame}_v1146.png';assert not file.exists();s.render.filepath=str(file);bpy.ops.render.render(write_still=True);report['renders'].append(dict(frame=frame,view=view,path=file.relative_to(R).as_posix(),sha256=sha(file)))
assert signature()==before and sha(p)==src['blendSHA256'];assert sha(R/'SharedBase/Development/alice_shared_base.blend')==link['librarySHA256'];report['sourceAndLibraryUnchanged']=True;report['allFourSameCameraRendersComplete']=True;(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('DISTINCT_STOCKING_CLOTH_FOUR_WALK_RENDERS_COMPLETE_REQUIRES_VISUAL_REVIEW',flush=True)
