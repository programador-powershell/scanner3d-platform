"""Local whole-character candidate: continuous anatomical weights, geometry/UV untouched."""
import bpy,json,sys,numpy as np
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'walk_weight_continuity_CANDIDATE_v1131';D.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash,audit_link
claim=json.loads((R/'Coordination/Claims/alice_coelho.json').read_text(encoding='utf-8-sig'));assert claim['owner']=='root_coelho_refinement_20261003' and claim['nonce']=='f88f8d53fab24a619579580190e6207a'
current=json.loads((R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json').read_text(encoding='utf-8-sig'));src=R/current['currentBlend'];assert Path(bpy.data.filepath).resolve()==src.resolve();assert sha(src)==current['files']['blend']['sha256']
lib=audit_link(R/'SharedBase/Development/alice_shared_base.blend');ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=bpy.data.objects['Alice.Shared.Rig'];M=np.load(O/'walk_weight_regions_REVIEW_v1130/anatomical_semantic_masks_v1130.npz');P=np.asarray([ob.matrix_world@v.co for v in ob.data.vertices]);assert np.array_equal(P.astype(np.float32),M['positions'])
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),indices=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();names=[g.name for g in ob.vertex_groups];old=np.zeros((len(P),len(names)),np.float64)
for v in ob.data.vertices:
 for g in v.groups:old[v.index,g.group]=g.weight
new=old.copy();originalMasks=np.load(O/'semantic_skin_binding_CANDIDATE_v1097/semantic_body_hand_garment_masks_v1097.npz');groups=M['uniquePositionGroup'];u,first=np.unique(groups,return_index=True)
# Propagate correct own-hand weights ONLY to coincident UV seam counterparts.
for key in ['positiveHand','negativeHand']:
 for gid in np.unique(groups[M[key]&~originalMasks[key]]):
  ids=np.flatnonzero(groups==gid);good=ids[originalMasks[key][ids]];assert len(good)>0;new[ids]=old[good[0]]
def segment_weights(mask,boneNames):
 ids=np.flatnonzero(mask)
 if not len(ids):return
 A=np.asarray([rig.matrix_world@rig.data.bones[n].head_local for n in boneNames]);B=np.asarray([rig.matrix_world@rig.data.bones[n].tail_local for n in boneNames]);V=B-A;Q=P[ids]
 t=np.clip(np.sum((Q[:,None,:]-A)*V,axis=2)/np.maximum(np.sum(V*V,axis=1),1e-20),0,1);distance=np.linalg.norm(Q[:,None,:]-(A+t[:,:,None]*V),axis=2);w=1/np.maximum(distance,.008)**4;w/=w.sum(1)[:,None];new[ids]=0
 for j,n in enumerate(boneNames):new[ids,names.index(n)]=w[:,j]
for side,sign in [('Left',1),('Right',-1)]:
 sideMask=P[:,0]*sign>0
 segment_weights(M['forearm']&sideMask,[side+'Arm',side+'ForeArm',side+'Hand'])
 segment_weights(M['sleeve']&sideMask,['Spine2',side+'Shoulder',side+'Arm'])
 ids=np.flatnonzero(M['boots']&sideMask);t=np.clip((P[ids,2]-.126)/.060,0,1);leg=t*t*(3-2*t);new[ids]=0;new[ids,names.index(side+'Leg')]=leg;new[ids,names.index(side+'Foot')]=1-leg
# All EXACT-position duplicates must be identical in weight, never welded geometrically.
duplicateError=np.abs(new-new[first[groups]]).max();assert duplicateError<1e-7,duplicateError
changed=np.any(np.abs(new-old)>1e-7,axis=1);ids=np.flatnonzero(changed);assert np.isfinite(new).all() and np.min(new)>=0 and np.max(np.abs(new.sum(1)-1))<1e-5 and (new>0).sum(1).max()<=4
for group in ob.vertex_groups:group.remove(ids.tolist())
for j,group in enumerate(ob.vertex_groups):
 for i in np.flatnonzero(changed&(new[:,j]>0)):group.add([int(i)],float(new[i,j]),'REPLACE')
assert signature()==before
for pose in rig.pose.bones:pose.matrix_basis.identity()
out=D/'alice_coelho_complete_walk_weight_continuity_CANDIDATE_v1131.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False)
np.savez_compressed(D/'character_weights_v1131.npz',positions=P.astype(np.float32),weights=new.astype(np.float32),boneNames=np.asarray(names),positiveHand=M['positiveHand'],negativeHand=M['negativeHand'],forearm=M['forearm'],sleeve=M['sleeve'],boots=M['boots'],uniquePositionGroup=groups)
manifest=dict(version='v1131',kind='whole_character_anatomical_weight_continuity_CANDIDATE',wholeCharacterWithDress=True,blend=str(out),blendSHA256=sha(out),bytes=out.stat().st_size,sourceBlend=str(src),sourceSHA256=current['files']['blend']['sha256'],sharedLibrary=lib,sourceGeometrySignature=before,positionsTopologyAllUVNormalsMaterialsExactlyPreserved=True,originalAuthoringPreserved=True,changedWeightVertices=int(changed.sum()),exactPositionUVSeamWeightMaxError=float(duplicateError),maskVertices={k:int(M[k].sum()) for k in ['positiveHand','negativeHand','forearm','sleeve','boots']},bootWeightMethod='Own foot/leg smoothstep ankle .126-.186m, no pelvis; full anatomical UV components incl. seam duplicates.',armWeightMethod='Own Arm/ForeArm/Hand inverse segment distance without abrupt distance cutoff; puff sleeve Spine2/Shoulder/Arm.',canonicalBaseNotPromoted=True,anatomical168cmApproved=False,individualHairComplete=False,clothPhysicsApproved=False,rigComplete=False,gameplayMotionApproved=False,productionComplete=False,acceptedForPublication=False,additionalTripoCredits=0,VercelUsed=False,renders=[])
(D/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print('WHOLE_WEIGHT_CANDIDATE_SAVED_RENDER_REVIEW_PENDING',flush=True)
# Same linked Walk study, same cameras as rejected v1126; do not save this posed state.
actions={s.action.name:s.action for t in rig.animation_data.nla_tracks for s in t.strips if s.action};action=next(a for n,a in actions.items() if n.startswith('Walk /'));assert action.library
for t in rig.animation_data.nla_tracks:t.mute=True
rig.animation_data.action=action
if len(action.slots):rig.animation_data.action_slot=action.slots[0]
s=bpy.context.scene;s.render.threads_mode='FIXED';s.render.threads=6;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;cam=s.camera;target=Vector((0,0,.88));cam.data.ortho_scale=2.04
for frame,view,direction in [(1,'front_start',(0,-4,0)),(11,'front_quarter',(0,-4,0)),(31,'front_threequarter',(0,-4,0)),(11,'profile_quarter',(-4,0,0))]:
 s.frame_set(frame);bpy.context.view_layer.update();cam.location=target+Vector(direction);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();p=D/f'whole_walk_{view}_frame{frame}_v1131.png';assert not p.exists();s.render.filepath=str(p);bpy.ops.render.render(write_still=True);manifest['renders'].append(dict(frame=frame,view=view,path=p.relative_to(R).as_posix(),sha256=sha(p)))
assert signature()==before and sha(src)==current['files']['blend']['sha256'] and sha(R/'SharedBase/Development/alice_shared_base.blend')==lib['librarySHA256'];manifest['sourceAndLibraryUnchanged']=True;manifest['allFourSameCameraRendersComplete']=True;(D/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print('WHOLE_WEIGHT_CANDIDATE_RENDER_COMPLETE_REQUIRES_VISUAL_REVIEW',flush=True)
