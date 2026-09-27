"""Render candidate weight ownership on the actual intact native surface."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True);parser.add_argument('--inference',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=json.loads(Path(args.generation).read_text(encoding='utf-8'));inference=json.loads(Path(args.inference).read_text(encoding='utf-8'))
assert sha(g['editableBlend'])==g['editableBlendSha256']==inference['parentEditableSha256']
assert sha(inference['weightsFile'])==inference['weightsSha256']
assert sha(g['exports']['whole']['sourcePhoto'])==inference['sourcePhotoSha256']
out=Path(args.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);scene=bpy.context.scene
audit=json.loads((Path(args.generation).parent/'skin_audit.json').read_text(encoding='utf-8'))
obj=bpy.data.objects[next(p['mesh'] for p in audit['pieces'] if p['role']=='whole_native')]
for other in scene.objects:other.hide_render=other!=obj
rig=next(o for o in scene.objects if o.type=='ARMATURE');rig.data.pose_position='REST'
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None
weights=np.load(inference['weightsFile'])['weights'];names=inference['boneNames']
assert weights.shape==(len(obj.data.vertices),173)
palette={'Head':(.15,.40,.95),'Torso':(.85,.78,.60),'Cloth':(.10,.70,.34),
    'LeftArm':(1,.55,.08),'RightArm':(.95,.15,.1),'LeftLeg':(.7,.25,.9),'RightLeg':(.30,.7,.95)}
color=np.zeros((len(weights),3),np.float32)
for i,name in enumerate(names):
    owner='Head' if name=='Head' else 'Torso'
    if name.startswith('ExteriorCloth_'):owner='Cloth'
    for side in ['Left','Right']:
        if name.startswith((side+'Shoulder',side+'Arm',side+'ForeArm',side+'Hand')):owner=side+'Arm'
        if name.startswith((side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase')):owner=side+'Leg'
    color+=weights[:,i,None]*np.array(palette[owner])
rgba=np.ones((len(weights),4),np.float32);rgba[:,:3]=color
attribute=obj.data.color_attributes.new(name='Measured candidate rig ownership',type='FLOAT_COLOR',domain='POINT')
attribute.data.foreach_set('color',rgba.ravel())
material=bpy.data.materials.new('Candidate ownership diagnostic only');material.use_nodes=True
principled=material.node_tree.nodes.get('Principled BSDF');principled.inputs['Roughness'].default_value=.75
node=material.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name=attribute.name
material.node_tree.links.new(node.outputs['Color'],principled.inputs['Base Color'])
obj.data.materials.clear();obj.data.materials.append(material)
for face in obj.data.polygons:face.material_index=0
xyz=[obj.matrix_world@v.co for v in obj.data.vertices]
low=Vector(tuple(min(p[i] for p in xyz) for i in range(3)));high=Vector(tuple(max(p[i] for p in xyz) for i in range(3)))
center=(low+high)/2;span=(high-low).z*1.14
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12
scene.render.resolution_x=520;scene.render.resolution_y=760;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Ownership inspection world');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.5,.5,.5,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
data=bpy.data.cameras.new('Actual intact candidate ownership camera');camera=bpy.data.objects.new(data.name,data)
scene.collection.objects.link(camera);scene.camera=camera;data.type='ORTHO';data.ortho_scale=span;data.clip_start=.001
for i,direction in enumerate([Vector((1,-1,1)),Vector((-1,-.5,.3)),Vector((0,1,.7))]):
    data=bpy.data.lights.new('Ownership light '+str(i),'AREA');data.energy=15;data.size=span
    light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light);light.location=center+direction.normalized()*span*2
    light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,direction in [('front',Vector((0,-1,0))),('back',Vector((0,1,0))),('threequarter',Vector((.65,-1,.15)).normalized())]:
    camera.location=center+direction*span*2;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    file=out/(name+'.png');scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
    views[name]={'file':str(file),'sha256':sha(file)}
report={'parentEditableSha256':g['editableBlendSha256'],'parentWholeModelSha256':inference['parentWholeModelSha256'],
    'sourcePhoto':g['exports']['whole']['sourcePhoto'],'sourcePhotoSha256':inference['sourcePhotoSha256'],
    'candidateWeightsSha256':inference['weightsSha256'],'scope':'candidate bone-weight ownership on actual native rest geometry only',
    'palette':palette,'renders':views,'scriptSha256':sha(__file__),'sourceEditableUnchanged':sha(g['editableBlend'])==g['editableBlendSha256'],
    'actualCharacterGeometryChanged':False,'candidateWeightsOnly':True,'materialsChangedInMemoryOnly':True,
    'anatomicalRegionsVerified':False,'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
    'limitation':'Diagnostic colors show bone influence, not final materials, a new garment layer, skinning approval or cloth physics.'}
(out/'comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ACTUAL_NATIVE_CANDIDATE_OWNERSHIP_RENDERED',flush=True)
