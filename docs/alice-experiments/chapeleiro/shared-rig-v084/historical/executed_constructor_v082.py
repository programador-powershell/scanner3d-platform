"""Preserve the whole Tripo scan and skin every current foundation piece.

This creates a local deformation study, not an approved garment or collision
result. Source FBXs supply bones/actions only. Procedural authoring geometry and
the protected linked exterior remain available beside evaluated skin previews.
"""
import argparse,hashlib,json,math,shutil,struct,sys,time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from chapeleiro_shared_rig_fields import GarmentFields,quantized_assign,solve_leg

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--motions',required=True)
parser.add_argument('--whole-photo',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.generation).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed actual parent: '+field)
if parent.get('rigPresent') or len(parent['pieces'])!=229:raise ValueError('Requires the actual unskinned 229-piece foundation.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve prior checkpoints; choose a fresh output directory.')
out.mkdir(parents=True)
started=time.time()

def receipt(name,record):
    (out/(name+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
def progress(step,**data):
    record={'step':step,'elapsedSeconds':round(time.time()-started,2),**data}
    receipt('progress',record);print('SHARED_FOUNDATION_PROGRESS',json.dumps(record),flush=True)
def geometry_hash(mesh):
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    loops=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('vertex_index',loops)
    counts=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('loop_total',counts)
    return hashlib.sha256(xyz.tobytes()+loops.tobytes()+counts.tobytes()).hexdigest()

for dependency in parent.get('editableLibraryDependencies',[]):
    file=Path(parent['editableBlend']).parent/dependency['file']
    if sha(file)!=dependency['sha256']:raise ValueError('Changed protected whole library.')
    shutil.copyfile(file,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene;scene.frame_set(1)
pieces={p['name']:dict(p) for p in parent['pieces']}
actual={name:bpy.data.objects[name] for name in pieces}
whole=next(o for o in scene.objects if o.type=='MESH' and o.data.library)
whole_hash=geometry_hash(whole.data)
if whole_hash!='10d6825fa75b34de11fbd71b7b61f69c71ec14589fb1cd035d36a6c07c5d7ece':
    raise ValueError('Requires the intact native whole geometry, without garment extraction.')
original_geometry={o.name:geometry_hash(o.data) for o in scene.objects if o.type=='MESH'}
original_objects=list(scene.objects)
original_names={obj:obj.name for obj in original_objects}

# Freeze the evaluated rest surfaces, including the existing BCB thickness/UV.
# Authoring originals remain independent and editable; previews are not new cuts.
frozen=[];depsgraph=bpy.context.evaluated_depsgraph_get()
for name,obj in actual.items():
    evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=depsgraph)
    snapshot=mesh.copy();evaluated.to_mesh_clear()
    frozen.append((name,pieces[name]['role'],snapshot,obj.matrix_world.copy(),obj))
frozen.append(('Chapeleiro / intact whole exterior / skin study','whole_native',whole.data.copy(),whole.matrix_world.copy(),whole))
progress('actual_rest_surfaces_preserved',foundationPieces=len(actual),wholeVertices=len(whole.data.vertices))

sources={};source_records=[]
for label,filename in [('Walk','Walking.fbx'),('Run','Fast Run.fbx'),('Attack','One Hand Sword Combo.fbx')]:
    file=Path(args.motions)/filename;before=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(file));imported=set(bpy.data.objects)-before
    rigs=[o for o in imported if o.type=='ARMATURE']
    if len(rigs)!=1:raise ValueError('Expected exactly one supplied motion skeleton.')
    source=rigs[0]
    if not source.animation_data or not source.animation_data.action:raise ValueError('Missing supplied motion.')
    removed_meshes=sum(o.type=='MESH' for o in imported)
    for obj in imported:
        if obj!=source:bpy.data.objects.remove(obj,do_unlink=True)
    source.name='Source bones only / '+label;sources[label]=source
    source_records.append({'motion':label,'file':str(file.resolve()),'sha256':sha(file),
        'sourceFps':scene.render.fps/scene.render.fps_base,'discardedForeignMeshObjects':removed_meshes,
        'foreignCharacterGeometryUsed':False})
template=sources['Walk'];source_names={b.name.split(':')[-1]:b.name for b in template.data.bones}
if any({b.name.split(':')[-1] for b in s.data.bones}!=set(source_names) for s in sources.values()):
    raise ValueError('Source motions require incompatible bone remapping.')
scale=.685;offset=Vector((0,.002,0))
source_rest={n:template.matrix_world@template.data.bones[f].matrix_local for n,f in source_names.items()}
heads={n:(template.matrix_world@template.data.bones[f].head_local)*scale+offset for n,f in source_names.items()}
tails={n:(template.matrix_world@template.data.bones[f].tail_local)*scale+offset for n,f in source_names.items()}
lower_fit=[]
for side,sign in [('Left',1),('Right',-1)]:
    # Actual authored ring centers, not a nominal central humanoid footprint.
    stocking=next(o for n,o in actual.items() if n.startswith('01 / '+side.lower()+' stocking /') and pieces[n]['role']=='foundation_stocking')
    if len(stocking.data.vertices)!=4289:raise ValueError('Unexpected actual stocking loft.')
    rings=[sum((stocking.matrix_world@v.co for v in stocking.data.vertices[i*64:(i+1)*64]),Vector())/64 for i in range(67)]
    knee_z=heads[side+'Leg'].z
    indices=sorted(range(30),key=lambda i:abs(rings[i].z-knee_z))[:2];a,b=sorted(indices,key=lambda i:rings[i].z)
    knee=rings[a].lerp(rings[b],(knee_z-rings[a].z)/(rings[b].z-rings[a].z))
    ankle=rings[29].copy();toe=rings[53].copy();tip=rings[61].copy()
    old_toe=heads[side+'Toe_End'].copy();old_tail=tails[side+'Toe_End'].copy()
    heads[side+'Leg']=knee;tails[side+'UpLeg']=knee
    heads[side+'Foot']=ankle;tails[side+'Leg']=ankle
    heads[side+'ToeBase']=toe;tails[side+'Foot']=toe
    tails[side+'ToeBase']=tip;heads[side+'Toe_End']=tip
    tails[side+'Toe_End']=tip+(old_tail-old_toe).normalized()*.012
    lower_fit.append({'side':side,'actualStocking':stocking.name,'sourceRows':{'ankle':29,'toeBase':53,'toeTip':61},
        'knee':list(knee),'ankle':list(ankle),'toeBase':list(toe),'toeTip':list(tip),'bootContainmentVerified':False})
    arm=Vector((sign*.076,.018,.780));elbow=Vector((sign*.131,.014,.652));wrist=Vector((sign*.180,.010,.535))
    old_wrist=heads[side+'Hand'].copy();rotation=Vector((sign,0,0)).rotation_difference((wrist-elbow).normalized())
    for name in source_names:
        if name.startswith(side+'Hand'):
            heads[name]=wrist+rotation@(heads[name]-old_wrist);tails[name]=wrist+rotation@(tails[name]-old_wrist)
    heads[side+'Shoulder'].y=.018;tails[side+'Shoulder']=arm
    heads[side+'Arm'],tails[side+'Arm']=arm,elbow
    heads[side+'ForeArm'],tails[side+'ForeArm']=elbow,wrist

# Piece membership comes from the actual sewn parent graph. Every decoration
# below a petticoat uses the same field, including names without "petticoat".
families={}
for name,piece in pieces.items():
    current=name;seen=set()
    while current and current not in seen:
        seen.add(current)
        if current=='01 / black petticoat continuous waist support':families[name]='BlackCloth';break
        if current=='01 / long ivory gathered petticoat':families[name]='IvoryCloth';break
        current=pieces.get(current,{}).get('parent')
cloth_families={}
for family in ['IvoryCloth','BlackCloth','ExteriorCloth']:
    members=[row for row in frozen if families.get(row[0])==family] if family!='ExteriorCloth' else [frozen[-1]]
    points=np.asarray([tuple(matrix@v.co) for _,_,mesh,matrix,_ in members for v in mesh.vertices])
    if family=='ExteriorCloth':points=points[(points[:,2]>.24)&(points[:,2]<.64)&(np.abs(points[:,0])<.23)]
    hi=float(points[:,2].max());lo=float(points[:,2].min());levels=list(np.linspace(hi,lo,4))
    radii=[]
    for z in levels:
        band=points[np.abs(points[:,2]-z)<max(.02,(hi-lo)/8)]
        if not len(band):raise ValueError('Missing actual garment section for cloth bind.')
        radii.append([float(np.quantile(np.abs(band[:,0]),.95)),float(np.quantile(np.abs(band[:,1]-.002),.95))])
    cloth_families[family]={'sectors':12,'levels':levels,'radii':radii,'response':'unbaked; parent motion only','collisionVerified':False}

data=bpy.data.armatures.new('Chapeleiro / fitted common anatomical and garment bones')
rig=bpy.data.objects.new('Alice Chapeleiro / shared rig study',data);scene.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for name in source_names:
    bone=data.edit_bones.new(name);bone.head=heads[name];bone.tail=tails[name]
    bone.align_roll(source_rest[name].to_3x3().col[2])
for name,full in source_names.items():
    original=template.data.bones[full]
    if original.parent:data.edit_bones[name].parent=data.edit_bones[original.parent.name.split(':')[-1]]
for family,rule in cloth_families.items():
    for sector in range(rule['sectors']):
        theta=sector*math.tau/rule['sectors']
        points=[Vector((rx*math.sin(theta),.002-ry*math.cos(theta),z)) for z,(rx,ry) in zip(rule['levels'],rule['radii'])]
        for level in range(3):
            bone=data.edit_bones.new(f'{family}_{sector:02d}_{level}');bone.head=points[level];bone.tail=points[level+1]
            bone.parent=data.edit_bones[f'{family}_{sector:02d}_{level-1}'] if level else data.edit_bones['Hips']
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
fields=GarmentFields(rig,cloth_families,families)
preview_collection=bpy.data.collections.new('Actual skin previews / full evaluated surfaces');scene.collection.children.link(preview_collection)
preview=[];skin_audit=[]
for index,(name,role,mesh,world,original) in enumerate(frozen):
    if role!='whole_native':original.name='Authoring / '+name
    obj=bpy.data.objects.new(name,mesh);preview_collection.objects.link(obj);obj.matrix_world=world
    skin_audit.append(quantized_assign(obj,rig,fields,role,name))
    modifier=obj.modifiers.new('Common Chapeleiro rig / actual weighted skin','ARMATURE');modifier.object=rig
    modifier.use_deform_preserve_volume=False
    obj.parent=rig;obj.matrix_world=world;obj['role']=role;obj['rig_study']=True;obj['motion_verified']=False
    preview.append(obj)
    if index%20==0:progress('actual_piece_weights_created',completed=index+1,total=len(frozen),mesh=name)

# Bind actual midsurface carriers before Cloth, while preserving all authored
# pin/stiffness/shrink/pressure group definitions and the original seam topology.
cage_audit=[]
for obj in original_objects:
    if obj.type!='MESH' or not ('midsurface' in obj.name):continue
    old_name=original_names[obj]
    receiver=next((name for name,original in actual.items() if any(m.type=='SURFACE_DEFORM' and m.target==obj for m in original.modifiers)),None)
    if not receiver:
        receiver=next((name for name in actual if old_name.startswith(name+' /')),None)
    if not receiver:raise ValueError('No real authoring garment receiver for cage: '+obj.name)
    schema=[(g.name,g.lock_weight) for g in obj.vertex_groups]
    obj.data=obj.data.copy()
    # Blender may remove definitions on a mesh datablock replacement.
    if not len(obj.vertex_groups):
        for group,locked in schema:obj.vertex_groups.new(name=group).lock_weight=locked
    if [(g.name,g.lock_weight) for g in obj.vertex_groups]!=schema:raise ValueError('Changed cloth field definitions.')
    result=quantized_assign(obj,rig,fields,pieces[receiver]['role'],receiver,True)
    modifier=obj.modifiers.new('Skin before physical garment solver','ARMATURE');modifier.object=rig
    with bpy.context.temp_override(object=obj,active_object=obj):bpy.ops.object.modifier_move_to_index(modifier=modifier.name,index=0)
    result.update(authoredFields=[name for name,_ in schema],modifierOrder=[m.type for m in obj.modifiers],receiver=receiver)
    cage_audit.append(result)
authoring=bpy.data.collections.new('Preserved procedural BCB authoring / cloth unverified');scene.collection.children.link(authoring)
for obj in original_objects:
    for collection in list(obj.users_collection):collection.objects.unlink(obj)
    authoring.objects.link(obj)
authoring.hide_render=True;authoring.hide_viewport=True
for obj in original_objects:
    if obj.type=='MESH' and geometry_hash(obj.data)!=original_geometry[original_names[obj]]:
        raise ValueError('An actual raw authoring mesh was changed during rigging.')
progress('all_actual_components_skinned',previewPieces=len(preview),authoringCages=len(cage_audit),bones=len(data.bones))
receipt('skin_audit',{'pieces':skin_audit,'authoringCages':cage_audit,'allActualRawAuthoringGeometryUnchanged':True})

bind={b.name:b.matrix_local.copy() for b in data.bones};ordered=sorted(data.bones,key=lambda b:len(b.parent_recursive))
rig.animation_data_create()
for bone in rig.pose.bones:bone.rotation_mode='QUATERNION'
actions=[];motion_audit=[]
preview_collection.hide_viewport=True
def assign_global_pose(matrices,frame):
    for bone in ordered:
        arguments={}
        if bone.parent:arguments.update(parent_matrix=matrices[bone.parent.name],parent_matrix_local=bind[bone.parent.name])
        pose=rig.pose.bones[bone.name]
        pose.matrix_basis=bone.convert_local_to_pose(matrices[bone.name],bind[bone.name],invert=True,**arguments)
        for path in ['location','rotation_quaternion','scale']:pose.keyframe_insert(path,frame=frame)

for label,source in sources.items():
    first,last=source.animation_data.action.frame_range;fps=next(r['sourceFps'] for r in source_records if r['motion']==label)
    source_map={b.name.split(':')[-1]:b for b in source.pose.bones}
    action=bpy.data.actions.new(label+' / shared Chapeleiro deformation study');action.use_fake_user=True
    rig.animation_data.action=action;count=max(2,round((last-first)/fps*30)+1)
    for index in range(count):
        frame=first+(last-first)*index/(count-1);scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update();matrices={}
        for bone in ordered:
            if bone.name in source_names:
                source_matrix=source.matrix_world@source_map[bone.name].matrix
                matrix=source_matrix.to_quaternion().normalized().to_matrix().to_4x4()
                if bone.parent:head=matrices[bone.parent.name]@(bind[bone.parent.name].inverted()@bone.head_local)
                else:
                    delta=(source_matrix.to_translation()-source_rest[bone.name].to_translation())*scale
                    head=bone.head_local+Vector((0,0,delta.z))
                matrix.translation=head
            else:matrix=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name]
            matrices[bone.name]=matrix
        assign_global_pose(matrices,index+1)
    actions.append(action);motion_audit.append({'clip':action.name,'frames':count,'fps':30,'sourceFrameRange':[first,last],
        'source':label,'retarget':'absolute source world orientation into the fitted bind; horizontal root travel removed',
        'motionVerified':False,'clothCollisionVerified':False})
    progress('supplied_motion_retargeted',clip=label,frames=count)

# A new authored jump uses two-bone IK at planted crouch/landing keys. Actual
# surface/floor contacts and in-between interpolation still need motion review.
jump=bpy.data.actions.new('Jump / planted-key IK deformation study');jump.use_fake_user=True;rig.animation_data.action=jump
jump_keys=[(1,0,0,0),(9,-.045,0,9),(15,.02,.020,3),(25,.145,.195,-3),(34,.06,.09,2),(41,-.035,0,8),(53,0,0,0)]
ik_audit=[]
for frame,lift,ankle_lift,lean in jump_keys:
    matrices={}
    for bone in ordered:
        matrix=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name] if bone.parent else bind[bone.name].copy()
        if not bone.parent:matrix.translation.z+=lift
        if bone.name=='Spine1':matrix=matrix@Matrix.Rotation(math.radians(lean),4,'X')
        matrices[bone.name]=matrix
    for side in ['Left','Right']:
        up=side+'UpLeg';leg=side+'Leg';foot=side+'Foot';toe=side+'ToeBase'
        hip=matrices[up].translation.copy();ankle=heads[foot]+Vector((0,0,ankle_lift))
        knee=solve_leg(hip,ankle,(tails[up]-heads[up]).length,(tails[leg]-heads[leg]).length)
        for name,start,end in [(up,hip,knee),(leg,knee,ankle)]:
            rotation=(tails[name]-heads[name]).normalized().rotation_difference((end-start).normalized())
            matrix=rotation.to_matrix().to_4x4()@bind[name];matrix.translation=start;matrices[name]=matrix
        matrices[foot]=bind[foot].copy();matrices[foot].translation=ankle
        for bone in ordered:
            if bone.name!=foot and any(parent.name==foot for parent in bone.parent_recursive):
                matrices[bone.name]=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name]
        ik_audit.append({'frame':frame,'side':side,'hip':list(hip),'knee':list(knee),'ankle':list(ankle),'plantedKey':ankle_lift==0,
            'surfaceContactVerified':False})
    assign_global_pose(matrices,frame)
actions.append(jump);motion_audit.append({'clip':jump.name,'frames':53,'fps':30,'source':'locally authored two-bone IK probe',
    'plantedKeys':[1,9,41,53],'surfaceContactVerified':False,'motionVerified':False,'clothCollisionVerified':False})
for source in sources.values():bpy.data.objects.remove(source,do_unlink=True)
preview_collection.hide_viewport=False
rig.animation_data.action=None
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for action in actions:
    track=rig.animation_data.nla_tracks.new();track.name=action.name;strip=track.strips.new(action.name,1,action)
    if action.slots:strip.action_slot=action.slots[0]
    track.mute=True
scene.render.fps=30;scene.render.fps_base=1;scene.frame_set(1);bpy.context.view_layer.update()
schema={'sourceFoundationSha256':parent['modelSha256'],'sourceWholeGeometrySha256':whole_hash,
    'lowerActualRingFit':lower_fit,'upperArmFit':'initial A-pose guide; actual photo/mesh fit remains unverified',
    'bones':[{'name':b.name,'parent':b.parent.name if b.parent else None,'head':list(b.head_local),'tail':list(b.tail_local),
        'matrix':[list(row) for row in b.matrix_local]} for b in ordered],
    'clothFamilies':cloth_families,'pieceFamilies':families,'jumpKeyIK':ik_audit,
    'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
receipt('shared_rig_bind',schema);receipt('motion_sources',source_records)
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_shared_rig_full_checkpoint.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
progress('full_local_editable_saved',file=str(editable),bytes=editable.stat().st_size,sha256=sha(editable))

exports={}
for label,objects,photo in [('foundation',preview[:-1],parent['sourcePhoto']),('whole',preview[-1:],args.whole_photo)]:
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for obj in objects:obj.select_set(True)
    model=out/(label+'_shared_rig_study.glb')
    bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,
        export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False)
    content=model.read_bytes();size,kind=struct.unpack_from('<II',content,12);document=json.loads(content[20:20+size])
    skin_nodes=[n for n in document.get('nodes',[]) if 'mesh' in n and 'skin' in n]
    clip_names=[a.get('name','') for a in document.get('animations',[])]
    if len(skin_nodes)!=len(objects):raise ValueError('An actual exported component lost its skin.')
    if not all(any(name.startswith(clip+' /') for name in clip_names) for clip in ['Walk','Run','Jump','Attack']):
        raise ValueError('An actual required motion clip was lost on export.')
    exports[label]={'model':str(model.resolve()),'modelSha256':sha(model),'bytes':model.stat().st_size,'actualSkinnedNodes':len(skin_nodes),
        'actualSkins':len(document.get('skins',[])),'actualClips':clip_names,'sourcePhoto':str(Path(photo).resolve()),'sourcePhotoSha256':sha(photo)}
    progress('actual_skinned_glb_exported',family=label,**exports[label])
    review_record=dict(parent) if label=='foundation' else {'variant':'alice_chapeleiro','reusedGeometry':False,'pieces':[]}
    review_record.update(exports[label],modelUpAxis='Y',status='generated_awaiting_visual_review',rigPresent=True,
        method='shared_rig_deformation_study_preserving_intact_whole_and_actual_foundation',
        editableBlend=str(editable.resolve()),editableBlendSha256=sha(editable),motionVerified=False,
        allLayersFinished=False,fidelityVerified=False,clothCollisionVerified=False,additionalCreditsConsumed=0,
        limitations=['Skin and clips are present; visible deformation, body fit and physical collisions are not approved.',
            'Secondary cloth bones follow the parent pose; no physical secondary animation is baked.',
            'The preserved authoring originals retain procedural BCB graphs; their cloth motion remains unverified.'])
    receipt(label+'_generation',review_record)
result={'method':'actual_230_component_common_rig_local_deformation_study','parentGeneration':str(Path(args.generation).resolve()),
    'parentGenerationSha256':sha(args.generation),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'editableBytes':editable.stat().st_size,'exports':exports,'riggedActualPieces':len(preview),'sharedArmatures':1,
    'bones':len(data.bones),'sourceWholeGeometrySha256':whole_hash,'sourceWholeUncut':True,
    'actualAuthoringGeometryUnchanged':True,'authoringCages':len(cage_audit),'motionAudit':motion_audit,
    'scriptSha256':sha(__file__),'fieldScriptSha256':sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
    'additionalCreditsConsumed':0,'allLayersFinished':False,'fidelityVerified':False,'motionVerified':False,
    'clothCollisionVerified':False,'finalFbxExported':False,'nextVariantMayStart':False,
    'publicationStatus':'local_only_pending_actual_visual_motion_and_collision_review'}
receipt('generation',result);progress('complete_local_rig_study',actualPieces=len(preview),exports=exports)
