"""Skin the NEW photo-modeled corset and its details to supplied motion bones.

Only skeleton/actions are used from FBXs. Their character geometry is discarded.
This verifies initial movement of one component, not all garment layers or cloth physics.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector, Quaternion

parser=argparse.ArgumentParser()
parser.add_argument('--generation',required=True)
parser.add_argument('--motions',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source_manifest=Path(args.generation);generation=json.loads(source_manifest.read_text(encoding='utf-8'))
if generation.get('reusedGeometry') is not False or generation['method']!='new_blender_surface_from_stage_photo':
    raise ValueError('This study requires the new photo-modeled corset, not an old Alice mesh.')
sha=lambda file:hashlib.sha256(Path(file).read_bytes()).hexdigest()
if sha(generation['model'])!=generation['modelSha256']:raise ValueError('Fresh geometry has changed.')
if sha(generation['editableBlend'])!=generation['editableBlendSha256']:raise ValueError('Editable geometry has changed.')
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
if (out/'generation.json').exists():raise ValueError('Existing rig study: choose a new version directory.')
bpy.ops.wm.open_mainfile(filepath=generation['editableBlend'])
garments=[o for o in bpy.context.scene.objects if o.type in {'MESH','CURVE'}]
bpy.ops.object.select_all(action='DESELECT')
for obj in garments:obj.select_set(True)
bpy.context.view_layer.objects.active=garments[0]
bpy.ops.object.convert(target='MESH')
garments=[o for o in bpy.context.scene.objects if o.type=='MESH']
motion_root=Path(args.motions)
sources={'Walk':'Walking.fbx','Run':'Fast Run.fbx','Attack':'One Hand Sword Combo.fbx'}
rig=None;actions=[];rig_sources=[]
for label,name in sources.items():
    before=set(bpy.data.objects);prior_actions=set(bpy.data.actions)
    file=motion_root/name;bpy.ops.import_scene.fbx(filepath=str(file))
    imported=set(bpy.data.objects)-before
    skeleton=next(o for o in imported if o.type=='ARMATURE')
    action=skeleton.animation_data.action if skeleton.animation_data else None
    if not action:raise ValueError(f'No actual motion in {name}')
    action.name=f'{label} / supplied motion';action.use_fake_user=True
    if rig is None:
        rig=skeleton;rig.name='Alice compatible motion rig / initial corset study'
        rig.animation_data_clear();rig.scale*=1.26
    else:
        if set(b.name for b in skeleton.data.bones)!=set(b.name for b in rig.data.bones):
            raise ValueError(f'{name} needs retargeting: different bone names.')
        # Compatibility is checked against actual rest matrices; bone names alone are insufficient.
        for bone in rig.data.bones:
            other=skeleton.data.bones[bone.name]
            if (bone.head_local-other.head_local).length>.02 or (bone.tail_local-other.tail_local).length>.02:
                raise ValueError(f'{name} needs retargeting: incompatible rest skeleton.')
    actions.append(action);rig_sources.append({'action':label,'file':str(file.resolve()),'sha256':sha(file)})
    for obj in imported:
        if obj is not rig:bpy.data.objects.remove(obj,do_unlink=True)
rig.data.pose_position='REST';bpy.context.view_layer.update()
names=[next(b.name for b in rig.data.bones if b.name.split(':')[-1]==name) for name in ['Hips','Spine','Spine1','Spine2']]
centers=[(rig.matrix_world@rig.data.bones[name].head_local).z for name in names]
skin_audit=[]
for obj in garments:
    world=obj.matrix_world.copy();obj.parent=rig;obj.matrix_world=world
    groups=[obj.vertex_groups.new(name=name) for name in names]
    for vertex in obj.data.vertices:
        z=(obj.matrix_world@vertex.co).z
        pairs=sorted([(abs(z-center),i) for i,center in enumerate(centers)])[:2]
        if z<=centers[0]:weights=[(0,1.0)]
        elif z>=centers[-1]:weights=[(3,1.0)]
        else:
            distance_total=sum(d for d,_ in pairs)
            weights=[(i,1-d/distance_total) for d,i in pairs] if distance_total else [(pairs[0][1],1.0)]
        for i,value in weights:groups[i].add([vertex.index],value,'REPLACE')
    armature=obj.modifiers.new('Skin to shared motion skeleton','ARMATURE');armature.object=rig
    errors=[abs(sum(g.weight for g in v.groups)-1) for v in obj.data.vertices]
    if max(errors,default=0)>1e-5:raise ValueError('Unnormalized skin weights.')
    skin_audit.append({'mesh':obj.name,'vertices':len(obj.data.vertices),'unweighted':sum(not v.groups for v in obj.data.vertices),
                       'maxNormalizationError':max(errors,default=0)})
rig.data.pose_position='POSE';rig.animation_data_create()
# A new authored jump probe, explicitly separate from supplied production motions.
jump=bpy.data.actions.new('Jump / authored deformation probe');rig.animation_data.action=jump
for bone in rig.pose.bones:bone.rotation_mode='QUATERNION'
keyframes=[(1,0,0),(10,-.18,1),(18,.20,.35),(30,.70,.25),(42,.30,.2),(50,-.12,.7),(64,0,0)]
def rotation_global(bone,axis,angle):
    frame=(rig.matrix_world@bone.bone.matrix_local).to_quaternion()
    return frame.inverted()@Quaternion(Vector(axis),math.radians(angle))@frame
for frame,lift,crouch in keyframes:
    for bone in rig.pose.bones:
        bone.location=(0,0,0);bone.rotation_quaternion=(1,0,0,0)
    hips=rig.pose.bones[names[0]];hips.location.y=lift/rig.matrix_world.to_scale().y
    for side in ['Left','Right']:
        for part,angle in [('UpLeg',-50*crouch),('Leg',85*crouch),('Foot',-35*crouch)]:
            b=next(b for b in rig.pose.bones if b.name.split(':')[-1]==side+part)
            b.rotation_quaternion=rotation_global(b,(1,0,0),angle)
        b=next(b for b in rig.pose.bones if b.name.split(':')[-1]==side+'Arm')
        b.rotation_quaternion=rotation_global(b,(0,1,0),75 if side=='Left' else -75)
    for bone in rig.pose.bones:
        bone.keyframe_insert('location',frame=frame);bone.keyframe_insert('rotation_quaternion',frame=frame)
jump.use_fake_user=True;actions.append(jump)
motion_audit=[]
for action in actions:
    rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    samples=[]
    for frame in sorted({int(action.frame_range[0]),int(sum(action.frame_range)/2),int(action.frame_range[1])}):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        obj=garments[0];evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
        point=evaluated.matrix_world@mesh.vertices[len(mesh.vertices)//2].co;evaluated.to_mesh_clear()
        if not all(math.isfinite(v) for v in point):raise ValueError('Invalid deformation coordinate.')
        samples.append({'frame':frame,'sampleVertexWorld':list(point)})
    displacement=max((Vector(a['sampleVertexWorld'])-Vector(b['sampleVertexWorld'])).length for a in samples for b in samples)
    if displacement<1e-4:raise ValueError(f'{action.name} does not move the skinned garment.')
    motion_audit.append({'clip':action.name,'samples':samples,'sampleDisplacementMetres':displacement,
                         'visibleQualityVerified':False,'clothPhysicsVerified':False})
rig.animation_data.action=None
for bone in rig.pose.bones:bone.location=(0,0,0);bone.rotation_quaternion=(1,0,0,0)
for action in actions:
    track=rig.animation_data.nla_tracks.new();track.name=action.name
    strip=track.strips.new(action.name,1,action)
    if action.slots:strip.action_slot=action.slots[0]
    track.mute=True
bpy.context.scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'corset_rigged_study.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'model.glb'),export_format='GLB',export_yup=True,
                          export_animations=True,export_animation_mode='NLA_TRACKS')
record={**generation,'model':str((out/'model.glb').resolve()),'modelSha256':sha(out/'model.glb'),
        'editableBlend':str((out/'corset_rigged_study.blend').resolve()),
        'editableBlendSha256':sha(out/'corset_rigged_study.blend'),
        'method':'new_photo_modeled_corset_with_supplied_motion_rig','geometryParentSha256':generation['modelSha256'],
        'rigSources':rig_sources,'riggedComponents':len(garments),'skinAudit':skin_audit,'motionAudit':motion_audit,
        'rigStatus':'initial_skinning_verified_numerically','motionVerified':False,'clothPhysicsVerified':False,
        'pendingComponents':generation['pendingComponents'],
        'limitations':generation['limitations']+['Only the corset component is skinned; all other layers remain pending.',
           'Jump is a new deformation probe requiring visual and gameplay refinement, not a finished Soulslike jump.',
           'No body/cloth or inter-layer collision simulation has been approved.']}
(out/'generation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print('FRESH_CORSET_RIG_MOTION_STUDY_SAVED',out)
