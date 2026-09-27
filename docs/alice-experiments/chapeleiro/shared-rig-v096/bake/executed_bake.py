"""Save a complete shared rig checkpoint with a measured two-anagua study clip.

All original meshes, UVs, weights, materials and actions remain available. Only
the experimental cloth NLA slot changes; four locomotion/combat clips and the
protected whole exterior export stay unchanged. This is not a final FBX.
"""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True)
p.add_argument('--fit',required=True)
p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
read=lambda f:json.loads(Path(f).read_text(encoding='utf-8'))
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
g,fit=read(a.generation),read(a.fit)
assert sha(g['editableBlend'])==g['editableBlendSha256']==fit['parentEditableSha256']
assert sha(fit['dataFile'])==fit['dataSha256'] and fit['other101BodyAndExteriorBonesUnchanged']
assert g['exports']['foundation']['sourcePhotoSha256']==fit['sourcePhotoSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
data=np.load(fit['dataFile'])
assert len(data['modified_bone_indices'])==fit['actualClothBonesFitted']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
names=[b.name for b in rig.data.bones]
assert names==data['bone_names'].tolist() and len(names)==fit['actualSharedRigBones']
reference=Path(g.get('authoringReferenceRoot',Path(a.generation).parent))
audit=read(reference/'skin_audit.json')
previews=[bpy.data.objects[row['mesh']] for row in audit['pieces']]
assert len(previews)==230
assert all(any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers) for o in previews)

def mesh_hash(obj):
 mesh=obj.data;digest=hashlib.sha256()
 for attr,prop,width,dtype in [(mesh.vertices,'co',3,np.float32),(mesh.loops,'vertex_index',1,np.int32),(mesh.polygons,'loop_total',1,np.int32)]:
  values=np.empty(len(attr)*width,dtype);attr.foreach_get(prop,values);digest.update(values.tobytes())
 for layer in mesh.uv_layers:
  values=np.empty(len(layer.data)*2,np.float32);layer.data.foreach_get('uv',values);digest.update(layer.name.encode());digest.update(values.tobytes())
 digest.update(json.dumps([m.name if m else None for m in mesh.materials]).encode())
 groups={group.index:group.name for group in obj.vertex_groups}
 digest.update(json.dumps([[(groups[w.group],w.weight) for w in v.groups] for v in mesh.vertices]).encode())
 return digest.hexdigest()

def curve_hash(action):
 curves=[(fc.data_path,fc.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points])
         for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
 return hashlib.sha256(json.dumps(curves,sort_keys=True).encode()).hexdigest()

before_meshes={o.name:mesh_hash(o) for o in scene.objects if o.type=='MESH'}
before_actions={strip.action.name:curve_hash(strip.action) for track in rig.animation_data.nla_tracks for strip in track.strips}
assert len(before_actions)==5
selected={rig,*previews}
collection_visibility={collection:collection.hide_viewport for collection in bpy.data.collections}
object_visibility={obj:obj.hide_viewport for obj in scene.objects}
modifier_visibility=[(modifier,modifier.show_viewport) for obj in scene.objects if obj not in selected for modifier in obj.modifiers]
for collection in bpy.data.collections:collection.hide_viewport=False
for obj in scene.objects:obj.hide_viewport=obj not in selected
for modifier,visible in modifier_visibility:modifier.show_viewport=False
original_tracks=[track for track in rig.animation_data.nla_tracks if any(strip.action.name.startswith('Corrida com tecido /') for strip in track.strips)]
assert len(original_tracks)==1
for strip in original_tracks[0].strips:strip.action.use_fake_user=True
rig.animation_data.nla_tracks.remove(original_tracks[0])
for track in rig.animation_data.nla_tracks:track.mute=True
clip='Corrida com tecido / camadas em refinamento'
assert clip not in bpy.data.actions
local=bpy.data.actions.new(clip);rig.animation_data.action=local
rig.data.pose_position='POSE'
bind={b.name:b.matrix_local.copy() for b in rig.data.bones}
previous={}
for frame,deformations in enumerate(data['rig_deformations'],1):
 desired={n:Matrix(deformations[i].tolist())@bind[n] for i,n in enumerate(names)}
 for bone in rig.data.bones:
  parent={'parent_matrix':desired[bone.parent.name],'parent_matrix_local':bind[bone.parent.name]} if bone.parent else {}
  pose=rig.pose.bones[bone.name];pose.rotation_mode='QUATERNION'
  pose.matrix_basis=bone.convert_local_to_pose(desired[bone.name],bind[bone.name],invert=True,**parent)
  q=pose.rotation_quaternion.copy()
  if bone.name in previous and q.dot(previous[bone.name])<0:q.negate();pose.rotation_quaternion=q
  previous[bone.name]=q.copy()
  for channel in ['location','rotation_quaternion','scale']:pose.keyframe_insert(data_path=channel,frame=frame,group=bone.name)
for layer in local.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    for key in fc.keyframe_points:key.interpolation='LINEAR'
checks=[]
for frame,deformations in enumerate(data['rig_deformations'],1):
 scene.frame_set(frame);bpy.context.view_layer.update()
 actual=np.asarray([np.asarray(rig.pose.bones[n].matrix@bind[n].inverted()) for n in names])
 error=float(np.max(np.abs(actual-deformations)));assert error<1e-5
 checks.append({'frame':frame,'actualBakedJointMatrixMaximumError':error})
assert {name:curve_hash(bpy.data.actions[name]) for name in before_actions}==before_actions
assert {o.name:mesh_hash(o) for o in scene.objects if o.type=='MESH'}==before_meshes
track=rig.animation_data.nla_tracks.new();track.name=clip;track.strips.new(clip,1,local);track.mute=True
rig.animation_data.action=None
for pose in rig.pose.bones:pose.matrix_basis=Matrix.Identity(4)
scene.frame_set(1);bpy.context.view_layer.update()
for modifier,visible in modifier_visibility:modifier.show_viewport=visible
for obj,visible in object_visibility.items():obj.hide_viewport=visible
for collection,visible in collection_visibility.items():collection.hide_viewport=visible
assert all(modifier.show_viewport==visible for modifier,visible in modifier_visibility)
packed_before=sum(bool(image.packed_file) for image in bpy.data.images)
objects_before=len(scene.objects)
editable=out/'chapeleiro_shared_rig_sewn_cloth_study.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),check_existing=False,relative_remap=True)
assert sha(g['editableBlend'])==g['editableBlendSha256']
assert len(scene.objects)==objects_before and sum(bool(image.packed_file) for image in bpy.data.images)==packed_before
report={'parentGeneration':str(Path(a.generation).resolve()),'parentEditableSha256':g['editableBlendSha256'],
        'editableBlend':str(editable),'editableBlendSha256':sha(editable),'editableBytes':editable.stat().st_size,
        'actualAllMeshGeometryUvMaterialsAndWeightsHashes':before_meshes,'actualOriginalActionHashes':before_actions,
        'allOriginalFiveActionsRetainedUnchanged':True,'previousStudyActionRetainedOutsideExportNla':True,
        'actualPackedImages':packed_before,'actualObjects':objects_before,'actualSharedBones':len(names),
        'actualBakedJointMatrixChecks':checks,'studyClip':clip,'actualClothBonesFitted':fit['actualClothBonesFitted'],
        'fitReport':str(Path(a.fit).resolve()),'fitDataSha256':fit['dataSha256'],'scriptSha256':sha(__file__),
        'completeCheckpointSavedWithoutTrimming':True,'modelExported':False,'finalFbxExported':False,
        'unrelatedAuthoringModifiersTemporarilyMutedForRigChecksOnly':True,'allOriginalModifierVisibilityRestoredBeforeSave':True,
        'allLayersFinished':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,
        'limitation':'Only the separately named run study responds to the measured coupled anagua solver. Physical contacts, fitting residuals, photo fidelity, all source actions and other cloth still need refinement.'}
(out/'sewn_cloth_bake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
result={**g,'parentGeneration':str(Path(a.generation).resolve()),'editableBlend':str(editable),'editableBlendSha256':sha(editable),
        'editableBytes':editable.stat().st_size,'authoringReferenceRoot':str(reference),
        'method':'Preserved full shared rig checkpoint with measured Ivory and Black cloth study action',
        'sewnClothBake':str(out/'sewn_cloth_bake.json'),'sewnClothFitReport':str(Path(a.fit).resolve()),
        'sewnClothStudyClip':clip,'ivoryStudyClip':clip,
        'authoringClips':[strip.action.name for track in rig.animation_data.nla_tracks for strip in track.strips],
        'exportsInheritedForReferenceOnly':True,'modelExportedInThisRefinement':False,
        'allLayersFinished':False,'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
        'finalFbxExported':False,'nextVariantMayStart':False,'additionalCreditsConsumed':0,
        'publicationStatus':'local_full_authoring_not_exported'}
(out/'generation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_bake.py')
print('ACTUAL_FULL_SEWN_CLOTH_STUDY_SAVED',editable.stat().st_size,clip,flush=True)
