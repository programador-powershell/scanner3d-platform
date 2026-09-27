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
    audit=quantized_assign(obj,rig,fields,entry['role'],entry['mesh']);skin_audit.append(audit)
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
schema['bloomerLegAttachment']={'method':'continuous lateral thigh split with original vertical hip blend',
    'centralHalfWidthAtCuffs':.003,'centralHalfWidthTowardWaist':.021,'widthTransitionZ':[.45,.52],
    'originalHipBlendZ':[.45,.52],'measuredBodyCentralClearanceBelowZ045':.003720698179677129,
    'measuredActualV084ModelSha256':'2d5997151d87fa67d740ff273316e6980895e31899439f5a01f6afc590b98fe0',
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
    write(label+'_generation',updated);progress('actual_refined_glb_exported',family=label,**exports[label])
result=dict(parent);result.update(parentGeneration=str(parent_path.resolve()),parentGenerationSha256=sha(parent_path),
    method='same_230_piece_shared_rig_with_sewn_torso_and_cava_attachment_field_refinement',
    editableBlend=str(editable.resolve()),editableBlendSha256=sha(editable),editableBytes=editable.stat().st_size,exports=exports,
    scriptSha256=sha(__file__),fieldScriptSha256=sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
    actualGeometryUnchanged=True,actualClothFieldWeightsUnchanged=True,torsoSkirtArmContaminationAbsent=True,
    publicationStatus='local_only_pending_new_visual_motion_review')
write('generation',result);progress('complete_local_attachment_refinement',actualPieces=len(previews))
