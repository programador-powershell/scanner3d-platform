"""Give each existing black flounce and its lace independent shared-rig controls.

Append child joints with the existing bind transforms and remap six actual skin
previews. Original geometry, UV, materials, normalized weights, old joints and
five actions remain unchanged. Child joints reproduce their old parent exactly
until a separately measured response is baked; no paid rig or new scan is used.
"""
import argparse,hashlib,json,shutil,sys
from collections import defaultdict
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True)
p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(a.generation);assert sha(g['editableBlend'])==g['editableBlendSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
old_names=[b.name for b in rig.data.bones];assert len(old_names)==173
old_binds={b.name:np.asarray(b.matrix_local).copy() for b in rig.data.bones}
old_heads={b.name:b.head_local.copy() for b in rig.data.bones}
old_tails={b.name:b.tail_local.copy() for b in rig.data.bones}
old_parents={b.name:b.parent.name if b.parent else None for b in rig.data.bones}
reference=Path(g.get('authoringReferenceRoot',Path(a.generation).parent))
audit=read(reference/'skin_audit.json')
previews=[bpy.data.objects[row['mesh']] for row in audit['pieces']]
assert len(previews)==230

def geometry_hash(obj):
 mesh=obj.data;h=hashlib.sha256()
 for attr,prop,width,dtype in [(mesh.vertices,'co',3,np.float32),(mesh.loops,'vertex_index',1,np.int32),(mesh.polygons,'loop_total',1,np.int32)]:
  x=np.empty(len(attr)*width,dtype);attr.foreach_get(prop,x);h.update(x.tobytes())
 for layer in mesh.uv_layers:
  x=np.empty(len(layer.data)*2,np.float32);layer.data.foreach_get('uv',x);h.update(layer.name.encode());h.update(x.tobytes())
 h.update(json.dumps([m.name if m else None for m in mesh.materials]).encode())
 return h.hexdigest()
def weight_rows(obj):
 names={g.index:g.name for g in obj.vertex_groups}
 return [[(names[w.group],w.weight) for w in v.groups] for v in obj.data.vertices]
def curve_hash(action):
 values=[(fc.data_path,fc.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points])
         for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
 return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
geometry_before={o.name:geometry_hash(o) for o in scene.objects if o.type=='MESH'}
actions={strip.action for track in rig.animation_data.nla_tracks for strip in track.strips}
action_hashes={act.name:curve_hash(act) for act in actions};assert len(actions)==5
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None
for pose in rig.pose.bones:pose.matrix_basis=Matrix.Identity(4)
scene.frame_set(1)
collection_states={c:c.hide_viewport for c in bpy.data.collections}
object_states={o:o.hide_viewport for o in scene.objects}
modifier_states=[(m,m.show_viewport) for o in scene.objects if o not in {rig,*previews} for m in o.modifiers]
for c in bpy.data.collections:c.hide_viewport=False
for o in scene.objects:o.hide_viewport=o not in {rig,*previews}
for m,state in modifier_states:m.show_viewport=False
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
mapping={}
for tier in range(1,4):
 for sector in range(12):
  old=f'BlackCloth_{sector:02d}_2';name=f'BlackFlounce{tier}_{sector:02d}'
  bone=rig.data.edit_bones.new(name)
  bone.head=old_heads[old];bone.tail=old_tails[old]
  bone.parent=rig.data.edit_bones[old];bone.use_connect=False;mapping[name]=old
bpy.ops.object.mode_set(mode='OBJECT')
assert len(rig.data.bones)==209
assert all(np.array_equal(np.asarray(rig.data.bones[n].matrix_local),m) for n,m in old_binds.items())
assert {n:rig.data.bones[n].parent.name if rig.data.bones[n].parent else None for n in old_names}==old_parents
new_bind_errors={n:float(np.max(np.abs(np.asarray(rig.data.bones[n].matrix_local)-old_binds[parent]))) for n,parent in mapping.items()}
new_endpoint_errors={n:max((rig.data.bones[n].head_local-old_heads[parent]).length,(rig.data.bones[n].tail_local-old_tails[parent]).length) for n,parent in mapping.items()}
assert max(new_endpoint_errors.values())<1e-6
# A child's rest roll can differ from its parent's. Skin deformation cancels
# the child's own inverse bind; test that actual motion below, not axis copies.
rows=[]
edited_names={f'01 / black gathered flounce {tier}' for tier in range(1,4)}|{f'01 / black floral lace tier {tier} / real apertures' for tier in range(1,4)}
other_weights={obj.name:hashlib.sha256(json.dumps(weight_rows(obj)).encode()).hexdigest() for obj in previews if obj.name not in edited_names}
for tier in range(1,4):
 for name in [f'01 / black gathered flounce {tier}',f'01 / black floral lace tier {tier} / real apertures']:
  obj=bpy.data.objects[name];before=weight_rows(obj);batches=defaultdict(list)
  remap={old:new for new,old in mapping.items() if new.startswith(f'BlackFlounce{tier}_')}
  for index,weights in enumerate(before):
   assert all(n in remap and w>0 for n,w in weights)
   for old,weight in weights:batches[(remap[old],weight)].append(index)
  for old in remap:
   group=obj.vertex_groups.get(old)
   if group:group.remove(list(range(len(obj.data.vertices))))
  for (new,weight),ids in batches.items():
   group=obj.vertex_groups.get(new) or obj.vertex_groups.new(name=new);group.add(ids,weight,'REPLACE')
  after=weight_rows(obj)
  assert [sorted(vertex) for vertex in after]==[sorted((remap[n],w) for n,w in vertex) for vertex in before]
  assert max(abs(sum(w for n,w in vertex)-1) for vertex in after)<1e-7
  rows.append({'object':name,'vertices':len(after),'actualRemappedJointNames':sorted(remap.values()),
               'maximumInfluences':max(map(len,after)),'normalizedWeightValuesPreservedExactly':True})
assert {obj.name:hashlib.sha256(json.dumps(weight_rows(obj)).encode()).hexdigest() for obj in previews if obj.name not in edited_names}==other_weights
assert {o.name:geometry_hash(o) for o in scene.objects if o.type=='MESH'}==geometry_before
checks=[]
for act in sorted(actions,key=lambda act:act.name):
 rig.animation_data.action=act
 if act.slots:rig.animation_data.action_slot=act.slots[0]
 first,last=act.frame_range
 for frame in [first,(first+last)*.5,last]:
  scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update()
  error=max(float(np.max(np.abs(np.asarray(rig.pose.bones[n].matrix@rig.data.bones[n].matrix_local.inverted())-
                              np.asarray(rig.pose.bones[parent].matrix@rig.data.bones[parent].matrix_local.inverted())))) for n,parent in mapping.items())
  assert error<1e-6
  checks.append({'action':act.name,'frame':frame,'actualChildParentSkinDeformationMaximumError':error})
assert {act.name:curve_hash(act) for act in actions}==action_hashes
rig.animation_data.action=None
for pose in rig.pose.bones:pose.matrix_basis=Matrix.Identity(4)
scene.frame_set(1);bpy.context.view_layer.update()
for m,state in modifier_states:m.show_viewport=state
for o,state in object_states.items():o.hide_viewport=state
for c,state in collection_states.items():c.hide_viewport=state
file=out/'chapeleiro_shared_rig_independent_flounces.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False,relative_remap=True)
assert sha(g['editableBlend'])==g['editableBlendSha256']
report={'parentGeneration':str(Path(a.generation).resolve()),'parentEditableSha256':g['editableBlendSha256'],
        'editableBlend':str(file),'editableBlendSha256':sha(file),'editableBytes':file.stat().st_size,
        'sourcePhotoSha256':g['exports']['foundation']['sourcePhotoSha256'],'actualOriginalJointNames':old_names,
        'actualAdditionalJointParents':mapping,'actualSharedBones':209,'actualEditedSkinPreviews':rows,
        'actualNewRestAxisDifferenceFromParent':new_bind_errors,'actualNewHeadTailCopyMaximumErrors':new_endpoint_errors,
        'allActualMeshGeometryUvAndMaterialsPreserved':True,'other224SkinPreviewWeightsPreservedExactly':True,
        'old173JointBindMatricesAndParentsPreservedExactly':True,'allFiveOriginalActionCurvesPreservedExactly':True,
        'actualOriginalActionHashes':action_hashes,'actualExistingMotionChildParentChecks':checks,
        'fullAuthoringPreservedWithoutTrimming':True,'actualPackedImages':sum(bool(i.packed_file) for i in bpy.data.images),
        'scriptSha256':sha(__file__),'responseFitted':False,'responseBaked':False,'modelExported':False,
        'allLayersFinished':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,'finalFbxExported':False,
        'limitation':'The three flounces and lace now have independent controls but still inherit the previous motion until a response is measured and baked. Physics and fidelity are not approved.'}
(out/'independent_flounce_rig.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
result={**g,'parentGeneration':str(Path(a.generation).resolve()),'editableBlend':str(file),'editableBlendSha256':sha(file),
        'editableBytes':file.stat().st_size,'authoringReferenceRoot':str(reference),'independentFlounceRig':str(out/'independent_flounce_rig.json'),
        'method':'Original shared rig plus independent child controls for all three black flounces and their lace',
        'actualSharedBones':209,'exportsInheritedForReferenceOnly':True,'modelExportedInThisRefinement':False,
        'allLayersFinished':False,'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
        'finalFbxExported':False,'nextVariantMayStart':False,'additionalCreditsConsumed':0,'publicationStatus':'local_authoring_not_exported'}
(out/'generation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_independent_flounce_rig.py')
print('ACTUAL_INDEPENDENT_FLOUNCE_RIG_SAVED',file.stat().st_size,209,flush=True)
