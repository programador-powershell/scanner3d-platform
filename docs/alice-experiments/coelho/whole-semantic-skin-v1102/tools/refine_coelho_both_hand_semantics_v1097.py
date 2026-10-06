import bpy,json,numpy as np,sys
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'semantic_skin_binding_CANDIDATE_v1094';W=O/'semantic_skin_binding_CANDIDATE_v1097';W.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash
source=json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'));assert Path(bpy.data.filepath).resolve()==Path(source['blend']).resolve();assert sha(Path(source['blend']))==source['blendSHA256'];ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=ob.modifiers[0].object;selected=np.load(O/'semantic_weight_masks_v1082/positive_hand_semantic_mask_v1096.npz')['hand'];P=np.asarray([ob.matrix_world@v.co for v in ob.data.vertices]);assert selected.sum()==2477
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),loops=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();names=[n.name for n in ob.vertex_groups if n.name=='LeftHand' or (n.name.startswith('LeftHand') and n.name[-1] in '123')];assert len(names)==16;A=np.asarray([rig.matrix_world@rig.data.bones[n].head_local for n in names]);B=np.asarray([rig.matrix_world@rig.data.bones[n].tail_local for n in names]);V=B-A;Q=P[selected];t=np.clip(np.sum((Q[:,None,:]-A)*V,axis=2)/np.maximum(np.sum(V*V,axis=1),1e-20),0,1);distance=np.linalg.norm(Q[:,None,:]-(A+t[:,:,None]*V),axis=2);nearest=np.argsort(distance,axis=1)[:,:4];weights=1/np.maximum(np.take_along_axis(distance,nearest,axis=1),.005)**4;weights/=weights.sum(1)[:,None];ids=np.flatnonzero(selected)
for group in ob.vertex_groups:group.remove(ids.tolist())
for j,name in enumerate(names):
 group=ob.vertex_groups[name]
 for slot in range(4):
  for k in np.flatnonzero(nearest[:,slot]==j):group.add([int(ids[k])],float(weights[k,slot]),'REPLACE')
negative=np.isin(np.load(O/'character_exact_position_component_labels_v1081.npy'),[12729,4977,3852]);allHands=negative|selected;protect=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1089.npz')['protect'].copy();protect|=(P[:,2]>.4)&(P[:,2]<.966)&~allHands
allNames=[g.name for g in ob.vertex_groups];weightsAll=np.zeros((len(P),len(allNames)))
for v in ob.data.vertices:
 for g in v.groups:weightsAll[v.index,g.group]=g.weight
old=weightsAll.copy()
for j,name in enumerate(allNames):
 if name.startswith(('LeftShoulder','LeftArm','LeftForeArm','LeftHand','RightShoulder','RightArm','RightForeArm','RightHand')):weightsAll[protect,j]=0
zero=weightsAll.sum(1)<1e-12;weightsAll[zero,allNames.index('Hips')]=1;weightsAll/=weightsAll.sum(1)[:,None];ids=np.flatnonzero(protect).tolist()
for group in ob.vertex_groups:group.remove(ids)
for j,group in enumerate(ob.vertex_groups):
 for i in np.flatnonzero(protect&(weightsAll[:,j]>0)):group.add([int(i)],float(weightsAll[i,j]),'REPLACE')
assert not protect[allHands].any();assert signature()==before;np.savez_compressed(W/'semantic_body_hand_garment_masks_v1097.npz',positiveHand=selected,negativeHand=negative,protectedGarment=protect,positions=P.astype(np.float32))
for pose in rig.pose.bones:pose.matrix_basis.identity()
out=W/'alice_coelho_complete_both_hand_semantic_skin_CANDIDATE_v1097.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False);report=dict(source,version='v1097',blend=str(out),blendSHA256=sha(out),sourceBlendSHA256=source['blendSHA256'],bothActualHandsBoundOnlyToOwnHandAndDigitBones=True,positiveHandVertices=2477,negativeHandVertices=2447,protectedGarmentVertices=int(protect.sum()),extraGarmentWeightVerticesChanged=int(np.any(np.abs(old-weightsAll)>1e-7,axis=1)[protect].sum()),underWristGarmentRule='0.4m<Z<0.966m, actual hand surfaces excluded; anatomical hidden body not reconstructed',characterGeometryUVNormalsMaterialsExactlyPreserved=True,visualApprovalPending=True,acceptedForPublication=False,productionComplete=False,renders=[])
s=bpy.context.scene;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;s.render.threads_mode='FIXED';s.render.threads=6;cam=s.camera;target=Vector((0,0,.88));cam.location=target+Vector((0,-4,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.04
for label,boneName,angle in [('neutral','RightForeArm',0),('right_elbow_20deg','RightForeArm',-.34906585),('left_elbow_20deg','LeftForeArm',.34906585)]:
 for pose in rig.pose.bones:pose.matrix_basis.identity()
 pose=rig.pose.bones[boneName];pose.rotation_mode='XYZ';pose.rotation_euler.z=angle;bpy.context.view_layer.update();s.render.filepath=str(W/f'whole_semantic_skin_{label}_v1097.png');bpy.ops.render.render(write_still=True);report['renders'].append(dict(view=label,path=s.render.filepath,sha256=sha(Path(s.render.filepath)),manualPoseNotGameplay=True))
# Actual individual finger motion test on the corrected positive hand, using a world-space curl axis.
for pose in rig.pose.bones:pose.matrix_basis.identity()
bone=rig.data.bones['LeftHandIndex2'];world=rig.matrix_world@bone.matrix_local;direction=(rig.matrix_world@bone.tail_local-rig.matrix_world@bone.head_local).normalized();axis=direction.cross(Vector((0,-1,0))).normalized();localAxis=(world.to_3x3().inverted()@axis).normalized();pose=rig.pose.bones['LeftHandIndex2'];pose.rotation_mode='QUATERNION';pose.rotation_quaternion=Quaternion(localAxis,.523598776);bpy.context.view_layer.update();target=Vector((.34,-.045,.84));cam.location=target+Vector((.25,-2,.04));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.33;s.render.resolution_x=s.render.resolution_y=900;s.render.filepath=str(W/'left_index_finger_curl_close_v1097.png');bpy.ops.render.render(write_still=True);report['renders'].append(dict(view='left_index_finger_curl_30deg_close',path=s.render.filepath,sha256=sha(Path(s.render.filepath)),manualPoseNotGameplay=True,worldCurlAxis=list(axis),localCurlAxis=list(localAxis)))
assert signature()==before;assert sha(Path(source['blend']))==source['blendSHA256'];(W/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('BOTH_HAND_SEMANTIC_BINDING_AND_GARMENT_PROTECTION_DONE',flush=True)
