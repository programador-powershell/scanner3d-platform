"""Readonly source poses for independent skinned export motion comparisons."""
import bpy,json,numpy as np,sys
from pathlib import Path
from mathutils import Vector,Quaternion
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'distinct_stocking_cloth_weights_CANDIDATE_v1146';sys.path.insert(0,str(R/'Tools'));from alice_shared_base_lib import sha
report=json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'));assert Path(bpy.data.filepath).resolve()==Path(report['blend']).resolve() and sha(Path(report['blend']))==report['blendSHA256'];ob=bpy.data.objects['Alice.Coelho.SkinStudy1074.character'];rig=ob.modifiers[0].object;linkedWalk=next(st.action for track in rig.animation_data.nla_tracks for st in track.strips if st.action and st.action.name.startswith('Walk /'));assert linkedWalk.library;originalModes={p.name:p.rotation_mode for p in rig.pose.bones};originalActionSettings={n:getattr(rig.animation_data,n) for n in ['action_influence','action_blend_type','action_extrapolation','use_nla']};rig.animation_data_clear();boneNames=[b.name for b in rig.data.bones];rows=[]
for label,name,angle in [('right_elbow','RightForeArm',-.34906585),('left_elbow','LeftForeArm',.34906585),('left_index','LeftHandIndex2',.523598776),('right_index','RightHandIndex2',.523598776)]:
 for p in rig.pose.bones:p.matrix_basis.identity()
 p=rig.pose.bones[name]
 if 'Index' in name:
  bone=rig.data.bones[name];world=rig.matrix_world@bone.matrix_local;direction=(rig.matrix_world@bone.tail_local-rig.matrix_world@bone.head_local).normalized();axis=direction.cross(Vector((0,-1,0))).normalized();localAxis=(world.to_3x3().inverted()@axis).normalized();p.rotation_mode='QUATERNION';p.rotation_quaternion=Quaternion(localAxis,angle)
 else:p.rotation_mode='XYZ';p.rotation_euler.z=angle
 bpy.context.view_layer.update();ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();P=np.asarray([ev.matrix_world@v.co for v in m.vertices],np.float32);ev.to_mesh_clear();worldPose=np.asarray([rig.matrix_world@rig.pose.bones[n].matrix for n in boneNames],np.float64);path=O/f'whole_skin_motion_{label}_v1170.npz';assert not path.exists();np.savez_compressed(path,positions=P,worldPose=worldPose);rows.append(dict(label=label,bone=name,angleRadians=angle,path=path.relative_to(R).as_posix(),sha256=sha(path)))
for p in rig.pose.bones:p.rotation_mode=originalModes[p.name];p.matrix_basis.identity()
rig.animation_data_create();rig.animation_data.action=linkedWalk
for n,value in originalActionSettings.items():setattr(rig.animation_data,n,value)
if len(linkedWalk.slots):rig.animation_data.action_slot=linkedWalk.slots[0]
walkWorld=[]
for frame in range(1,43):
 for p in rig.pose.bones:p.matrix_basis.identity()
 bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();worldPose=np.asarray([rig.matrix_world@rig.pose.bones[n].matrix for n in boneNames],np.float64);walkWorld.append(worldPose)
 if frame not in [1,11,31,42]:continue
 ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();P=np.asarray([ev.matrix_world@v.co for v in m.vertices],np.float32);ev.to_mesh_clear();label='walk_study_frame'+str(frame);path=O/f'whole_skin_motion_{label}_v1170.npz';assert not path.exists();np.savez_compressed(path,positions=P,worldPose=worldPose);rows.append(dict(label=label,commonLinkedAction=linkedWalk.name,frame=frame,path=path.relative_to(R).as_posix(),sha256=sha(path),gameplayApproved=False))
walkPath=O/'whole_skin_walk_world_matrices_v1170.npz';assert not walkPath.exists();np.savez_compressed(walkPath,worldPose=np.asarray(walkWorld),frames=np.arange(1,43),boneNames=np.asarray(boneNames),frameRate=np.asarray(bpy.context.scene.render.fps/bpy.context.scene.render.fps_base))
observed=np.load(O/'whole_skin_motion_walk_study_frame11_v1170.npz')['positions'];original=np.load(O/'walk_continuity_independent_REVIEW_v1147/candidate_whole_frame11_v1147.npz')['positions'];walkError=float(np.linalg.norm(observed-original,axis=1).max());assert walkError<2e-6,('Walk reference differs from independent source evaluation',walkError);assert sha(Path(report['blend']))==report['blendSHA256'];(O/'whole_skin_motion_reference_v1170.json').write_text(json.dumps(dict(version='v1170',sourceBlendSHA256=report['blendSHA256'],boneNames=boneNames,poses=rows,wholeWalkWorldMatrices=dict(path=walkPath.relative_to(R).as_posix(),sha256=sha(walkPath),frames=42,commonLinkedAction=linkedWalk.name),originalBoneRotationModes=originalModes,originalActionSettings=originalActionSettings,walkReferenceMatchesIndependentOriginalSourceFrame11MaxM=walkError,manualBoneModeChangesRestoredBeforeWalk=True,manualAndLinkedWalkStudyDiagnosticPosesOnly=True,gameplayApproved=False,sourceUnchanged=True,productionComplete=False),indent=2),encoding='utf-8');print('EIGHT_NATIVE_DIAGNOSTIC_POSE_REFERENCES_CAPTURED',flush=True)
