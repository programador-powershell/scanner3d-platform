"""Render actual GLB joint positions and hierarchy for hand-bind diagnosis."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
parser.add_argument('--side',choices=['Left','Right'],required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
record=json.loads(Path(args.generation).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(record['model'])==record['modelSha256']
assert sha(record['sourcePhoto'])==record['sourcePhotoSha256']=='69e81154d4fe0903f76883a049ea9c3e2e9f16f57e488cf2075a0d7158e8feab'
out=Path(args.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=record['model'])
scene=bpy.context.scene;rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0]
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='REST'
native=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(native)==1
for material in native[0].data.materials:
    if material and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type=='BSDF_PRINCIPLED':node.inputs['Alpha'].default_value=.28

def marker_material(name,color):
    material=bpy.data.materials.new(name);material.use_nodes=True
    node=material.node_tree.nodes.get('Principled BSDF');node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Emission Color'].default_value=(*color,1);node.inputs['Emission Strength'].default_value=1.5
    return material

colors={'Thumb':(.95,.35,.08),'Index':(.1,.65,1),'Middle':(.2,1,.25),'Ring':(.95,.1,.45),'Pinky':(.8,.3,1)}
materials={key:marker_material(key,value) for key,value in colors.items()}
materials['Arm']=marker_material('Palm and forearm',(.95,.85,.3))
names=[b.name for b in rig.data.bones if b.name in [args.side+'Arm',args.side+'ForeArm',args.side+'Hand'] or b.name.startswith(args.side+'Hand')]
joint_positions={name:rig.matrix_world@rig.data.bones[name].head_local for name in names}
connections=[]
for name in names:
    bone=rig.data.bones[name];head=joint_positions[name]
    key=next((k for k in colors if k in name),'Arm');material=materials[key]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,radius=.001,location=head)
    sphere=bpy.context.object;sphere.name='Diagnostic actual joint / '+name;sphere.data.materials.append(material)
    # glTF stores joint nodes, not bone lengths. The importer may synthesize
    # leaf tails; only actual parent/child joint heads represent exported data.
    if bone.parent and bone.parent.name in joint_positions:
        parent=joint_positions[bone.parent.name];direction=head-parent
        if direction.length>1e-8:
            bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.00055,depth=direction.length,location=(parent+head)/2)
            cylinder=bpy.context.object;cylinder.name='Diagnostic joint connection / '+name
            cylinder.rotation_euler=direction.to_track_quat('Z','Y').to_euler();cylinder.data.materials.append(material)
        connections.append({'parent':bone.parent.name,'child':name})

scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16
scene.render.resolution_x=700;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Bind diagnosis lighting');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.5,.5,.5,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
center=Vector((.17 if args.side=='Left' else -.17,-.015,.535));span=.30
data=bpy.data.cameras.new('Actual hand bind camera');camera=bpy.data.objects.new('Actual hand bind camera',data)
scene.collection.objects.link(camera);scene.camera=camera;data.type='ORTHO';data.ortho_scale=span;data.clip_start=.001
for index,direction in enumerate([Vector((0,-1,1)),Vector((1,1,.7))]):
    light=bpy.data.lights.new('Bind inspection '+str(index),'AREA');light.energy=3;light.size=.3
    obj=bpy.data.objects.new(light.name,light);scene.collection.objects.link(obj);obj.location=center+direction.normalized()*.7
    obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,direction in [('front',Vector((0,-1,0))),('side',Vector((1,0,0))),('back',Vector((0,1,0)))]:
    camera.location=center+direction*1.2;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    file=out/(name+'.png');scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
    views[name]={'file':str(file),'sha256':sha(file)}
report={'model':record['model'],'modelSha256':record['modelSha256'],'sourcePhoto':record['sourcePhoto'],
    'sourcePhotoSha256':record['sourcePhotoSha256'],'scope':args.side+' forearm and hand bind diagnostic only',
    'nativeMaterialDiagnosticAlpha':.28,'bonesShown':names,'renders':views,
    'displayedJointPositions':{name:list(point) for name,point in joint_positions.items()},
    'connections':connections,'importerBoneTailsUsed':False,
    'actualModelGeometryChanged':False,'sourceGlbUnchanged':sha(record['model'])==record['modelSha256'],
    'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
    'limitation':'Transparent material and colored actual glTF joint positions/hierarchy are diagnostic overlays; synthetic importer leaf tails are not displayed. Anatomy, poses and cloth still require review.'}
(out/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ACTUAL_NATIVE_HAND_BIND_VIEWS_SAVED',flush=True)
