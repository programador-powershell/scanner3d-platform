"""Rebuild source motion in the current fitted Chapeleiro skeleton.

FBXs contribute bones/actions only. Absolute source orientations use current
bind joint locations and lengths. A new jump preserves the authored planted-key
IK probe. Accurate key matrices do not approve motion, contact or cloth physics.
"""
import hashlib,math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector
from chapeleiro_shared_rig_fields import solve_leg

SOURCES=[('Walk','Walking.fbx','f1ab7f6314e92972d08c1136cbb30515d333b3c17d0ee71f261a0fbf528f80e0'),
    ('Run','Fast Run.fbx','cef54fa8bed0fdeef15b01c512f234350444f816a0483ba5ee568466fb951301'),
    ('Attack','One Hand Sword Combo.fbx','0979a14715012ec4a642889b1cd4a1fe55790432a5812330623f8ab2017837d3')]

def retarget_refitted_rig(rig,directory):
    scene=bpy.context.scene
    existing=[t for t in rig.animation_data.nla_tracks if t.strips]
    if len(existing)!=4 or len(rig.data.bones)!=173:raise ValueError('Unexpected current common rig/actions.')
    original_objects=set(bpy.data.objects);original_hide={o:o.hide_viewport for o in original_objects}
    for obj in original_objects:
        if obj!=rig:obj.hide_viewport=True
    old_actions={s.action for t in existing for s in t.strips};rig.animation_data.action=None
    for track in list(rig.animation_data.nla_tracks):rig.animation_data.nla_tracks.remove(track)
    for action in old_actions:
        action.use_fake_user=False
        if action.users:raise ValueError('Existing rig action has another authored user.')
        bpy.data.actions.remove(action)
    ordered=sorted(rig.data.bones,key=lambda b:len(b.parent_recursive))
    bind={b.name:b.matrix_local.copy() for b in ordered}
    heads={b.name:b.head_local.copy() for b in ordered};tails={b.name:b.tail_local.copy() for b in ordered}
    for bone in rig.pose.bones:bone.rotation_mode='QUATERNION';bone.matrix_basis=Matrix.Identity(4)
    sources={};receipts=[]
    for label,filename,expected in SOURCES:
        file=Path(directory)/filename
        if hashlib.sha256(file.read_bytes()).hexdigest()!=expected:raise ValueError('Changed original source motion: '+filename)
        before=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(file));imported=set(bpy.data.objects)-before
        skeletons=[o for o in imported if o.type=='ARMATURE']
        if len(skeletons)!=1 or not skeletons[0].animation_data or not skeletons[0].animation_data.action:
            raise ValueError('Missing unique original source skeleton/action.')
        source=skeletons[0];discarded=sum(o.type=='MESH' for o in imported)
        for obj in imported:
            if obj!=source:bpy.data.objects.remove(obj,do_unlink=True)
        source.name='Source bones only / current bind / '+label;sources[label]=source
        receipts.append({'motion':label,'file':str(file.resolve()),'sha256':expected,
            'sourceFps':scene.render.fps/scene.render.fps_base,'discardedForeignMeshObjects':discarded,
            'foreignCharacterGeometryUsed':False})
    source_names={b.name.split(':')[-1] for b in sources['Walk'].data.bones}
    if len(source_names)!=65 or not source_names.issubset(bind):raise ValueError('Original motion mapping changed.')
    if any({b.name.split(':')[-1] for b in s.data.bones}!=source_names for s in sources.values()):
        raise ValueError('Source motions have different actual bone maps.')
    root_names=[b.name for b in ordered if b.parent is None]
    if root_names!=['Hips']:raise ValueError('Changed current common skeleton root.')
    template=sources['Walk'];source_rest={b.name.split(':')[-1]:template.matrix_world@b.matrix_local for b in template.data.bones}
    scene.render.fps=30;scene.render.fps_base=1
    actions=[];audit=[]

    def assign(matrices,frame,previous):
        for bone in ordered:
            arguments={}
            if bone.parent:arguments.update(parent_matrix=matrices[bone.parent.name],parent_matrix_local=bind[bone.parent.name])
            pose=rig.pose.bones[bone.name]
            pose.matrix_basis=bone.convert_local_to_pose(matrices[bone.name],bind[bone.name],invert=True,**arguments)
            q=pose.rotation_quaternion.copy()
            if bone.name in previous and q.dot(previous[bone.name])<0:q.negate();pose.rotation_quaternion=q
            previous[bone.name]=q.copy()
            for path in ['location','rotation_quaternion','scale']:pose.keyframe_insert(path,frame=frame)

    def verify_samples(action,samples):
        rig.animation_data.action=action
        if action.slots:rig.animation_data.action_slot=action.slots[0]
        maximum=0.
        for frame,matrices in samples:
            scene.frame_set(frame);bpy.context.view_layer.update()
            maximum=max(maximum,max(float(np.max(np.abs(np.asarray(rig.pose.bones[name].matrix)-np.asarray(matrix)))) for name,matrix in matrices.items()))
        if maximum>2e-5:raise ValueError('Baked current-bind poses disagree with the intended actual matrices: '+str(maximum))
        return {'actualKeysChecked':len(samples),'actualBonesPerKey':len(ordered),'maximumMatrixAbsoluteError':maximum,
            'scope':'baked key matrices only; intermediate poses, anatomy, foot contact and cloth remain unverified'}

    for label,source in sources.items():
        first,last=source.animation_data.action.frame_range
        fps=next(r['sourceFps'] for r in receipts if r['motion']==label)
        source_map={b.name.split(':')[-1]:b for b in source.pose.bones}
        action=bpy.data.actions.new(label+' / current fitted Chapeleiro motion study');action.use_fake_user=True
        rig.animation_data.action=action;count=max(2,round((last-first)/fps*30)+1);samples=[];previous={}
        for index in range(count):
            frame=first+(last-first)*index/(count-1);scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update();matrices={}
            for bone in ordered:
                if bone.name in source_names:
                    source_matrix=source.matrix_world@source_map[bone.name].matrix
                    matrix=source_matrix.to_quaternion().normalized().to_matrix().to_4x4()
                    if bone.parent:head=matrices[bone.parent.name]@(bind[bone.parent.name].inverted()@bone.head_local)
                    else:
                        delta=(source_matrix.translation-source_rest[bone.name].translation)*.685
                        head=bone.head_local+Vector((0,0,delta.z))
                    matrix.translation=head
                else:matrix=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name]
                matrices[bone.name]=matrix
            assign(matrices,index+1,previous);samples.append((index+1,{n:m.copy() for n,m in matrices.items()}))
        checks=verify_samples(action,samples);actions.append(action)
        audit.append({'clip':action.name,'frames':count,'fps':30,'sourceFrameRange':[first,last],'source':label,
            'retarget':'original source world orientations with current fitted bind joint positions and lengths; horizontal root travel removed',
            'bakedKeyMatrixAudit':checks,'motionVerified':False,'clothCollisionVerified':False})
        print('CURRENT_BIND_MOTION_REBUILT',label,count,checks['maximumMatrixAbsoluteError'],flush=True)
    jump=bpy.data.actions.new('Jump / current fitted planted-key IK motion study');jump.use_fake_user=True
    rig.animation_data.action=jump;samples=[];previous={};ik=[]
    for frame,lift,ankle_lift,lean in [(1,0,0,0),(9,-.045,0,9),(15,.02,.020,3),(25,.145,.195,-3),(34,.06,.09,2),(41,-.035,0,8),(53,0,0,0)]:
        matrices={}
        for bone in ordered:
            matrix=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name] if bone.parent else bind[bone.name].copy()
            if not bone.parent:matrix.translation.z+=lift
            if bone.name=='Spine1':matrix=matrix@Matrix.Rotation(math.radians(lean),4,'X')
            matrices[bone.name]=matrix
        for side in ['Left','Right']:
            up=side+'UpLeg';leg=side+'Leg';foot=side+'Foot'
            hip=matrices[up].translation.copy();ankle=heads[foot]+Vector((0,0,ankle_lift))
            knee=solve_leg(hip,ankle,(tails[up]-heads[up]).length,(tails[leg]-heads[leg]).length)
            for name,start,end in [(up,hip,knee),(leg,knee,ankle)]:
                rotation=(tails[name]-heads[name]).normalized().rotation_difference((end-start).normalized())
                matrix=rotation.to_matrix().to_4x4()@bind[name];matrix.translation=start;matrices[name]=matrix
            matrices[foot]=bind[foot].copy();matrices[foot].translation=ankle
            for bone in ordered:
                if bone.name!=foot and any(parent.name==foot for parent in bone.parent_recursive):
                    matrices[bone.name]=matrices[bone.parent.name]@bind[bone.parent.name].inverted()@bind[bone.name]
            ik.append({'frame':frame,'side':side,'hip':list(hip),'knee':list(knee),'ankle':list(ankle),
                'plantedKey':ankle_lift==0,'surfaceContactVerified':False})
        assign(matrices,frame,previous);samples.append((frame,{n:m.copy() for n,m in matrices.items()}))
    checks=verify_samples(jump,samples);actions.append(jump)
    audit.append({'clip':jump.name,'frames':53,'fps':30,'source':'locally rebuilt planted-key IK probe in the current fitted bind',
        'plantedKeys':[1,9,41,53],'bakedKeyMatrixAudit':checks,'surfaceContactVerified':False,
        'motionVerified':False,'clothCollisionVerified':False})
    for source in sources.values():bpy.data.objects.remove(source,do_unlink=True)
    if {o for o in bpy.data.objects if o.type=='ARMATURE'}!={rig}:raise ValueError('Foreign source skeleton remained after retarget.')
    rig.animation_data.action=None
    for pose in rig.pose.bones:pose.matrix_basis=Matrix.Identity(4)
    for action in actions:
        track=rig.animation_data.nla_tracks.new();track.name=action.name;strip=track.strips.new(action.name,1,action)
        if action.slots:strip.action_slot=action.slots[0]
        track.mute=True
    for obj,value in original_hide.items():obj.hide_viewport=value
    scene.frame_set(1);bpy.context.view_layer.update()
    return {'method':'rebuild all four actions for the current fitted common bind',
        'motionAudit':audit,'actualOriginalMotionSources':receipts,'jumpKeyIK':ik,
        'sourceSkeletonsRemoved':True,'foreignCharacterGeometryUsed':False,'commonSkeletonTopologyPreserved':True,
        'inheritedLocalChannelsUsed':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
