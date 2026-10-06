"""Refine gauntlet-to-forearm skin weights locally; preserve every original vertex and UV."""
import bpy,json,sys,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'wrist_weight_transition_CANDIDATE_v1133';D.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash,audit_link
src=json.loads((O/'walk_weight_continuity_CANDIDATE_v1131/manifest.json').read_text(encoding='utf-8-sig'));p=Path(src['blend']);assert Path(bpy.data.filepath).resolve()==p.resolve() and sha(p)==src['blendSHA256'];assert src['allFourSameCameraRendersComplete'];link=audit_link(R/'SharedBase/Development/alice_shared_base.blend');ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=bpy.data.objects['Alice.Shared.Rig'];mask=np.load(O/'walk_weight_regions_REVIEW_v1130/anatomical_semantic_masks_v1130.npz');P=np.asarray([ob.matrix_world@v.co for v in ob.data.vertices]);names=[g.name for g in ob.vertex_groups]
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),indices=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();assert before==src['sourceGeometrySignature'];old=np.zeros((len(P),len(names)),np.float64)
for v in ob.data.vertices:
 for g in v.groups:old[v.index,g.group]=g.weight
new=old.copy();both=np.zeros(len(P),bool);records=[]
for side,key in [('Left','positiveHand'),('Right','negativeHand')]:
 selected=mask[key]&(P[:,2]>.910);both|=selected;ids=np.flatnonzero(selected);bn=[side+'ForeArm',side+'Hand'];A=np.asarray([rig.matrix_world@rig.data.bones[n].head_local for n in bn]);B=np.asarray([rig.matrix_world@rig.data.bones[n].tail_local for n in bn]);V=B-A;Q=P[ids];t=np.clip(np.sum((Q[:,None,:]-A)*V,axis=2)/np.maximum(np.sum(V*V,axis=1),1e-20),0,1);distance=np.linalg.norm(Q[:,None,:]-(A+t[:,:,None]*V),axis=2);w=1/np.maximum(distance,.008)**4;w/=w.sum(1)[:,None]
 # Blend smoothly from the unchanged distal glove weights into the proximal wrist chain.
 ramp=np.clip((P[ids,2]-.910)/.020,0,1);ramp=ramp*ramp*(3-2*ramp);new[ids]*=(1-ramp[:,None])
 for j,n in enumerate(bn):new[ids,names.index(n)]+=ramp*w[:,j]
 # Preserve the four-influence export limit without discarding the largest influences.
 for i in ids:
  nn=np.argsort(new[i])[:-4];new[i,nn]=0;new[i]/=new[i].sum()
 records.append(dict(side=side,proximalGloveVertices=len(ids),transitionZ=[.910,.930],distalFingersPreserved=True))
groups=mask['uniquePositionGroup'];_,first=np.unique(groups,return_index=True);assert np.abs(new-new[first[groups]]).max()<1e-7;changed=np.any(np.abs(new-old)>1e-7,axis=1);ids=np.flatnonzero(changed);assert np.max(np.abs(new.sum(1)-1))<1e-5 and (new>0).sum(1).max()<=4
for g in ob.vertex_groups:g.remove(ids.tolist())
for j,g in enumerate(ob.vertex_groups):
 for i in np.flatnonzero(changed&(new[:,j]>0)):g.add([int(i)],float(new[i,j]),'REPLACE')
assert signature()==before
for pb in rig.pose.bones:pb.matrix_basis.identity()
out=D/'alice_coelho_complete_wrist_transition_CANDIDATE_v1133.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False);np.savez_compressed(D/'character_weights_v1133.npz',positions=P.astype(np.float32),weights=new.astype(np.float32),boneNames=np.asarray(names),positiveHand=mask['positiveHand'],negativeHand=mask['negativeHand'],forearm=mask['forearm'],sleeve=mask['sleeve'],boots=mask['boots'],uniquePositionGroup=groups)
report=dict(src,version='v1133',blend=str(out),bytes=out.stat().st_size,blendSHA256=sha(out),sourceBlend=str(p),sourceSHA256=src['blendSHA256'],changedWristVertices=int(changed.sum()),wristTransition=records,sourceGeometrySignature=before,geometryUVNormalsMaterialsExactlyPreserved=True,acceptedForPublication=False,gameplayMotionApproved=False,rigComplete=False,productionComplete=False,renders=[]);(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WRIST_TRANSITION_WHOLE_CANDIDATE_SAVED_REVIEW_PENDING',flush=True)
actions={s.action.name:s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action};act=next(a for n,a in actions.items() if n.startswith('Walk /'))
for t in rig.animation_data.nla_tracks:t.mute=True
rig.animation_data.action=act
if len(act.slots):rig.animation_data.action_slot=act.slots[0]
s=bpy.context.scene;s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;cam=s.camera
for frame,view,direction in [(1,'front_start',(0,-4,0)),(11,'front_quarter',(0,-4,0)),(31,'front_threequarter',(0,-4,0)),(11,'profile_quarter',(-4,0,0))]:
 s.frame_set(frame);bpy.context.view_layer.update();target=Vector((0,0,.88));cam.data.ortho_scale=2.04;cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();file=D/f'whole_walk_{view}_frame{frame}_v1133.png';assert not file.exists();s.render.filepath=str(file);bpy.ops.render.render(write_still=True);report['renders'].append(dict(frame=frame,view=view,path=file.relative_to(R).as_posix(),sha256=sha(file)))
assert signature()==before and sha(p)==src['blendSHA256'];assert sha(R/'SharedBase/Development/alice_shared_base.blend')==link['librarySHA256'];report['sourceAndLibraryUnchanged']=True;report['allFourSameCameraRendersComplete']=True;(D/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WRIST_WALK_FOUR_RENDERS_COMPLETED_REQUIRES_VISUAL_REVIEW',flush=True)
