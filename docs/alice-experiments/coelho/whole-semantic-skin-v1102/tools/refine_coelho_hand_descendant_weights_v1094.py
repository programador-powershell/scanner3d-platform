import bpy,json,numpy as np,sys
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'semantic_skin_binding_CANDIDATE_v1090';W=O/'semantic_skin_binding_CANDIDATE_v1094';W.mkdir(exist_ok=True);sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha,array_hash
source=json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'));assert Path(bpy.data.filepath).resolve()==Path(source['blend']).resolve();assert sha(Path(source['blend']))==source['blendSHA256'];ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=ob.modifiers[0].object;labels=np.load(O/'character_exact_position_component_labels_v1081.npy');selected=np.isin(labels,[12729,4977,3852]);P=np.asarray([ob.matrix_world@v.co for v in ob.data.vertices]);assert selected.sum()==2447
def signature():return dict(positions=array_hash(ob.data.vertices,'co',3),loops=array_hash(ob.data.loops,'vertex_index',1,np.int32),uv={u.name:array_hash(u.data,'uv',2) for u in ob.data.uv_layers},normals=array_hash(ob.data.corner_normals,'vector',3),materials=[m.name for m in ob.data.materials])
before=signature();names=[n.name for n in ob.vertex_groups if n.name=='RightHand' or (n.name.startswith('RightHand') and n.name[-1] in '123')];assert len(names)==16;A=np.asarray([rig.matrix_world@rig.data.bones[n].head_local for n in names]);B=np.asarray([rig.matrix_world@rig.data.bones[n].tail_local for n in names]);V=B-A;Q=P[selected];t=np.clip(np.sum((Q[:,None,:]-A)*V,axis=2)/np.maximum(np.sum(V*V,axis=1),1e-20),0,1);distance=np.linalg.norm(Q[:,None,:]-(A+t[:,:,None]*V),axis=2);nearest=np.argsort(distance,axis=1)[:,:4];weights=1/np.maximum(np.take_along_axis(distance,nearest,axis=1),.005)**4;weights/=weights.sum(1)[:,None];ids=np.flatnonzero(selected)
oldProtected=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1089.npz')['protect'];assert not oldProtected[selected].any()
for group in ob.vertex_groups:group.remove(ids.tolist())
for j,name in enumerate(names):
 group=ob.vertex_groups[name]
 for slot in range(4):
  for k in np.flatnonzero(nearest[:,slot]==j):group.add([int(ids[k])],float(weights[k,slot]),'REPLACE')
assert signature()==before;out=W/'alice_coelho_complete_semantic_hand_skin_CANDIDATE_v1094.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True,relative_remap=True,check_existing=False);report=dict(source,version='v1094',blend=str(out),blendSHA256=sha(out),sourceBlendSHA256=source['blendSHA256'],handCorrection={'actualTopologyRoots':[12729,4977,3852],'vertices':2447,'allowedBones':names,'excludedHipsAndTorsoFromActualHand':True,'digitWeightsStillRequireFingerGestureReview':True},characterGeometryUVNormalsMaterialsExactlyPreserved=True,visualApprovalPending=True,acceptedForPublication=False,productionComplete=False,renders=[])
# All hand influences inherit the same forearm motion; no hand vertex can stay attached to pelvis.
for pose in rig.pose.bones:pose.matrix_basis.identity()
s=bpy.context.scene;s.render.resolution_x=900;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.cycles.samples=16;s.cycles.use_denoising=True;s.render.threads_mode='FIXED';s.render.threads=6
from mathutils import Vector
cam=s.camera;target=Vector((0,0,.88));cam.location=target+Vector((0,-4,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.04
for label,boneName,angle in [('neutral','RightForeArm',0),('right_elbow_20deg','RightForeArm',-.34906585),('left_elbow_20deg','LeftForeArm',.34906585)]:
 for pose in rig.pose.bones:pose.matrix_basis.identity()
 pose=rig.pose.bones[boneName];pose.rotation_mode='XYZ';pose.rotation_euler.z=angle;bpy.context.view_layer.update();s.render.filepath=str(W/f'whole_semantic_skin_{label}_v1094.png');bpy.ops.render.render(write_still=True);report['renders'].append(dict(view=label,path=s.render.filepath,sha256=sha(Path(s.render.filepath)),manualPoseNotGameplay=True))
assert signature()==before;assert sha(Path(source['blend']))==source['blendSHA256'];(W/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('ACTUAL_HAND_DESCENDANT_WEIGHTS_FIXED_LOCALLY',flush=True)
