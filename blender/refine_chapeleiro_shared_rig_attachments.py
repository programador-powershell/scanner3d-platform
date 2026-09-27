"""Correct actual torso/skirt/sleeve weights without changing any geometry.

Previous exported motion is kept as rejected evidence. The same skeleton and
four actions remain; new visual and collision review is still required.
"""
import argparse,hashlib,json,shutil,struct,sys,time
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from chapeleiro_shared_rig_fields import GarmentFields,attachment_regions,quantized_assign

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent',required=True);parser.add_argument('--output',required=True)
parser.add_argument('--fit-native-hands',action='store_true',help='Infer arm/hand bind from the unchanged whole geometry and native atlas; inherited motions require renewed review.')
parser.add_argument('--finger-guides',help='Measured individual native finger target JSON for the exact parent whole export.')
parser.add_argument('--retarget-motions',help='Directory containing the original Walking, Fast Run and One Hand Sword Combo FBX bones/actions.')
parser.add_argument('--native-surface-weights',help='Measured geodesic surface inference JSON for the exact parent native exterior, without geometry edits.')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);parent_path=Path(args.parent);parent=json.loads(parent_path.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(parent['editableBlend'])!=parent['editableBlendSha256'] or parent['riggedActualPieces']!=230:raise ValueError('Changed actual complete rig checkpoint.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve earlier rig evidence.')
out.mkdir(parents=True);started=time.time()
write=lambda name,value:(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def progress(step,**kwargs):
    value={'step':step,'elapsedSeconds':round(time.time()-started,2),**kwargs};write('progress',value);print('ATTACHMENT_REFINE_PROGRESS',json.dumps(value),flush=True)
for filename in ['alice-vestido-chapeleiro.blend']:
    file=parent_path.parent/filename
    if sha(file)!='ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9':raise ValueError('Changed protected whole library.')
    shutil.copyfile(file,out/filename)
foundation=json.loads((parent_path.parent/'foundation_generation.json').read_text(encoding='utf-8'))
whole_record=json.loads((parent_path.parent/'whole_generation.json').read_text(encoding='utf-8'))
schema=json.loads((parent_path.parent/'shared_rig_bind.json').read_text(encoding='utf-8'))
old_audit=json.loads((parent_path.parent/'skin_audit.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend']);scene=bpy.context.scene;scene.frame_set(1)
rigs=[o for o in scene.objects if o.type=='ARMATURE']
if len(rigs)!=1:raise ValueError('Expected one actual common rig.')
rig=rigs[0]
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None
names={p['name']:p for p in foundation['pieces']}
authored={name:bpy.data.objects['Authoring / '+name] for name in names}
hand_fit=None
if not args.fit_native_hands and parent.get('nativeHandBindFit'):
    inherited_fit=json.loads((parent_path.parent/'native_hand_bind_fit.json').read_text(encoding='utf-8'))
    write('native_hand_bind_fit',inherited_fit)
    for filename in ['native_individual_finger_targets.json','refitted_motion_retarget.json']:
        file=parent_path.parent/filename
        if file.exists():shutil.copyfile(file,out/filename)
if args.fit_native_hands:
    from chapeleiro_native_hand_fit import fit_native_hands
    native_entry=next(p for p in old_audit['pieces'] if p['role']=='whole_native')
    finger_guides=None
    if args.finger_guides:
        finger_guides=json.loads(Path(args.finger_guides).read_text(encoding='utf-8'))
        if finger_guides['modelSha256']!=whole_record['modelSha256'] or finger_guides['parentEditableSha256']!=parent['editableBlendSha256'] or finger_guides['sourcePhotoSha256']!=whole_record['sourcePhotoSha256']:
            raise ValueError('Individual finger guides belong to a different actual model/photo.')
        shutil.copyfile(args.finger_guides,out/'native_individual_finger_targets.json')
    hand_fit=fit_native_hands(rig,bpy.data.objects[native_entry['mesh']],finger_guides);write('native_hand_bind_fit',hand_fit)
    schema['bones']=[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),
        'tail':list(b.tail_local),'matrix':[[v for v in row] for row in b.matrix_local]} for b in rig.data.bones]
    schema['nativeHandBindFit']=hand_fit
elif args.finger_guides:raise ValueError('Individual finger guides require native hand fitting.')
retarget=None
if args.retarget_motions:
    from chapeleiro_refitted_motion_retarget import retarget_refitted_rig
    retarget=retarget_refitted_rig(rig,Path(args.retarget_motions))
    if hand_fit:
        hand_fit['inheritedLocalActionChannelsRequireRetargetAndPoseReview']=False
        hand_fit['retargetRequiresPoseReview']=True
        hand_fit['limitations']=[s for s in hand_fit['limitations'] if not s.startswith('Original local action channels')]
        hand_fit['limitations'].append('Four actions were rebuilt for this bind; full motion and cloth review remain pending.')
        write('native_hand_bind_fit',hand_fit)
    write('refitted_motion_retarget',retarget);schema['refittedMotionRetarget']=retarget
    progress('four_actions_rebuilt_for_current_bind',actualClips=[m['clip'] for m in retarget['motionAudit']])
regions=attachment_regions(foundation['pieces'],authored)
fields=GarmentFields(rig,schema['clothFamilies'],schema['pieceFamilies'],regions)
previews=[bpy.data.objects[p['mesh']] for p in old_audit['pieces']]
collection=previews[0].users_collection[0];collection.hide_viewport=True
def mesh_hash(mesh):
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    loops=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('vertex_index',loops)
    counts=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('loop_total',counts)
    return hashlib.sha256(xyz.tobytes()+loops.tobytes()+counts.tobytes()).hexdigest()
before={obj:mesh_hash(obj.data) for obj in scene.objects if obj.type=='MESH'}
skin_audit=[]
for index,(obj,entry) in enumerate(zip(previews,old_audit['pieces'])):
    if entry['role']=='whole_native' and args.native_surface_weights:
        from chapeleiro_native_surface_weights import assign_native_surface_weights
        audit=assign_native_surface_weights(obj,rig,args.native_surface_weights,parent,whole_record)
        inference=json.loads(Path(args.native_surface_weights).read_text(encoding='utf-8'))
        shutil.copyfile(inference['weightsFile'],out/'native_surface_weights.npz')
        inference['originalInferenceSha256']=sha(args.native_surface_weights)
        inference['weightsFile']=str((out/'native_surface_weights.npz').resolve())
        write('native_surface_weight_inference',inference)
    else:audit=quantized_assign(obj,rig,fields,entry['role'],entry['mesh'])
    skin_audit.append(audit)
    family=schema['pieceFamilies'].get(obj.name);region=regions.get(obj.name,{})
    if family or region.get('kind')=='torso':
        allowed={'Hips','Spine','Spine1','Spine2','Neck'}
        if family:allowed.update(b.name for b in rig.data.bones if b.name.startswith(family+'_'))
        if set(audit['boneGroups'])-allowed:raise ValueError('Arm/leg contamination remains in an actual torso/skirt attachment.')
    if index%25==0:progress('actual_piece_weights_refined',completed=index+1,total=len(previews))
cage_audit=[]
for entry in old_audit['authoringCages']:
    obj=bpy.data.objects[entry['mesh']];receiver=entry['receiver']
    preserved={g.name:[(v.index,m.weight) for v in obj.data.vertices for m in v.groups if m.group==g.index]
        for g in obj.vertex_groups if g.name in entry['authoredFields']}
    audit=quantized_assign(obj,rig,fields,names[receiver]['role'],receiver,True,True)
    for name,values in preserved.items():
        group=obj.vertex_groups[name]
        actual=[(v.index,m.weight) for v in obj.data.vertices for m in v.groups if m.group==group.index]
        if actual!=values:raise ValueError('Changed actual cloth pin/stiffness/pressure field.')
    audit.update(authoredFields=entry['authoredFields'],modifierOrder=[m.type for m in obj.modifiers],receiver=receiver,
        actualClothFieldWeightsUnchanged=True);cage_audit.append(audit)
if any(mesh_hash(obj.data)!=digest for obj,digest in before.items()):raise ValueError('Geometry changed during weight refinement.')
collection.hide_viewport=False;scene.frame_set(1);bpy.context.view_layer.update()
schema['pieceRegions']=regions;schema['attachmentFieldRefinement']='torso-only corset/waist anchors, actual cava roots, native hands/legs excluded from skirt field'
schema['bloomerLegAttachment']={'method':'existing separate leg-opening trims follow their own thigh; continuous body keeps v084 weights',
    'existingTrimNamePrefixes':['01 / left bloomers /','01 / right bloomers /'],
    'measuredActualTrimZBounds':[.39512595534324646,.42955002188682556],
    'continuousCrotchFieldUnchangedFromV084':True,'originalHipBlendZ':[.45,.52],
    'measuredActualV084ModelSha256':'2d5997151d87fa67d740ff273316e6980895e31899439f5a01f6afc590b98fe0',
    'sewnJunctionMotionVerified':False,
    'motionVerified':False,'clothCollisionVerified':False}
write('shared_rig_bind',schema);write('skin_audit',{'pieces':skin_audit,'authoringCages':cage_audit,'actualRawGeometryUnchanged':True,
    'actualClothFieldWeightsUnchanged':True,'torsoSkirtArmContaminationAbsent':True})
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_shared_rig_attachment_refinement.blend';bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
progress('full_refined_local_checkpoint_saved',bytes=editable.stat().st_size,sha256=sha(editable))
exports={}
for label,objects,source_record in [('foundation',previews[:-1],foundation),('whole',previews[-1:],whole_record)]:
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for obj in objects:obj.select_set(True)
    file=out/(label+'_shared_rig_study.glb');bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,
        export_yup=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False)
    content=file.read_bytes();size=struct.unpack_from('<I',content,12)[0];document=json.loads(content[20:20+size])
    actual_nodes=[n for n in document.get('nodes',[]) if 'mesh' in n and 'skin' in n]
    clip_names=[a.get('name','') for a in document.get('animations',[])]
    if len(actual_nodes)!=len(objects) or len(document.get('skins',[]))!=1:raise ValueError('Actual shared skin lost on export.')
    if not all(any(name.startswith(label+' /') for name in clip_names) for label in ['Walk','Run','Jump','Attack']):raise ValueError('Lost actual action.')
    exports[label]={'model':str(file.resolve()),'modelSha256':sha(file),'bytes':file.stat().st_size,
        'actualSkinnedNodes':len(actual_nodes),'actualSkins':len(document['skins']),'actualClips':clip_names,
        'sourcePhoto':source_record['sourcePhoto'],'sourcePhotoSha256':source_record['sourcePhotoSha256']}
    updated=dict(source_record);updated.update(exports[label],editableBlend=str(editable.resolve()),editableBlendSha256=sha(editable),
        parentRigModelSha256=source_record['modelSha256'],method='shared_rig_attachment_field_refinement_without_geometry_cuts',
        status='generated_awaiting_visual_review',fidelityVerified=False,motionVerified=False,clothCollisionVerified=False,
        allLayersFinished=False,nextVariantMayStart=False,additionalCreditsConsumed=0)
    if label=='foundation':updated['pieces']=[dict(p,rigPresent=True,motionVerified=False) for p in updated['pieces']]
    if retarget:
        updated['motionAudit']=retarget['motionAudit'];updated['retargetStatus']='rebuilt from original source orientations and current fitted bind; pose and cloth review pending'
        updated['inheritedActionsRequireRetargetReview']=False;updated['retargetRequiresPoseReview']=True
    write(label+'_generation',updated);progress('actual_refined_glb_exported',family=label,**exports[label])
result=dict(parent);result.update(parentGeneration=str(parent_path.resolve()),parentGenerationSha256=sha(parent_path),
    method='same_230_piece_shared_rig_with_sewn_torso_and_cava_attachment_field_refinement',
    editableBlend=str(editable.resolve()),editableBlendSha256=sha(editable),editableBytes=editable.stat().st_size,exports=exports,
    scriptSha256=sha(__file__),fieldScriptSha256=sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
    actualGeometryUnchanged=True,actualClothFieldWeightsUnchanged=True,torsoSkirtArmContaminationAbsent=True,
    publicationStatus='local_only_pending_new_visual_motion_review')
result['nativeArmComponentScriptSha256']=sha(Path(__file__).with_name('chapeleiro_whole_arm_components.py'))
result['nativeArmMembershipClassificationVerified']=False
if not args.fit_native_hands and parent.get('nativeHandBindFit'):
    result['nativeHandFitInheritedFrom']=str(parent_path.resolve())
if hand_fit:
    result.pop('nativeHandFitInheritedFrom',None)
    result['nativeHandBindFit']=True;result['inheritedActionsRequireRetargetReview']=True
    result['handFitScriptSha256']=sha(Path(__file__).with_name('chapeleiro_native_hand_fit.py'))
    result['motionAudit']=[dict(m,previousRetarget=m.get('retarget'),
        retarget='inherited local channels in a refitted arm/hand bind; experimental deformation probe',motionVerified=False)
        for m in result['motionAudit']]
if args.finger_guides:result['nativeIndividualFingerGuideSha256']=sha(args.finger_guides)
if retarget:
    result['motionAudit']=retarget['motionAudit'];result['inheritedActionsRequireRetargetReview']=False
    result['retargetRequiresPoseReview']=True;result['motionRetargetScriptSha256']=sha(Path(__file__).with_name('chapeleiro_refitted_motion_retarget.py'))
if args.native_surface_weights:
    result['nativeSurfaceWeightInferenceSha256']=sha(out/'native_surface_weight_inference.json')
    result['nativeSurfaceWeightScriptSha256']=sha(Path(__file__).with_name('chapeleiro_native_surface_weights.py'))
    result['nativeSurfaceOwnershipVerified']=False
    result['method']='same_230_piece_shared_rig_with_intact_native_geodesic_surface_weight_refinement'
write('generation',result);progress('complete_local_attachment_refinement',actualPieces=len(previews))
