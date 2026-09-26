"""Render actual new inferred geometry for one stage and preserve photo provenance."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

parser=argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--stage-plan', required=True)
parser.add_argument('--stage-id', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--front-axis', choices=['+x','-x','+y','-y'], default='+x')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
generation=json.loads(Path(args.generation).read_text(encoding='utf-8'))
plan=json.loads(Path(args.stage_plan).read_text(encoding='utf-8'))
stage=next(s for s in plan['stages'] if s['id']==args.stage_id)
if generation['status']!='generated_awaiting_visual_review' or generation.get('reusedGeometry') is not False:
    raise ValueError('A successful fresh photo reconstruction is required.')
if generation['sourcePhotoSha256']!=stage['sourcePhotoSha256']:
    raise ValueError('The model belongs to another stage photo; refusing misleading comparison.')
model_path=Path(generation['model'])
if hashlib.sha256(model_path.read_bytes()).hexdigest()!=generation['modelSha256']:
    raise ValueError('Geometry changed since its reconstruction record.')
out=Path(args.output); out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(model_path))
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
bone_shapes={bone.custom_shape for rig in rigs for bone in rig.pose.bones if bone.custom_shape}
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o not in bone_shapes]
for rig in rigs: rig.data.pose_position='REST'
if not meshes:
    raise ValueError('No mesh imported.')
# TripoSR exports Z-up coordinates in GLB; the importer assumes glTF Y-up.
inverse_conversion=Matrix.Rotation(math.radians(-90),4,'X')
for obj in meshes:
    if generation.get('modelUpAxis','Z')=='Z':
        obj.matrix_world=inverse_conversion @ obj.matrix_world
    for polygon in obj.data.polygons: polygon.use_smooth=True
bpy.context.view_layer.update()
points=[]
depsgraph=bpy.context.evaluated_depsgraph_get()
for obj in meshes:
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    points.extend(evaluated.matrix_world@v.co for v in mesh.vertices)
    evaluated.to_mesh_clear()
if not points: raise ValueError('No evaluated garment vertices to frame.')
lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
center=(lo+hi)/2; size=hi-lo
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=16
scene.render.resolution_x=640; scene.render.resolution_y=960; scene.render.resolution_percentage=100
scene.render.film_transparent=True; scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Inspection world'); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(0.35,0.35,0.35,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=0.8
camera_data=bpy.data.cameras.new('Inspection camera'); camera=bpy.data.objects.new('Inspection camera',camera_data)
scene.collection.objects.link(camera); scene.camera=camera; camera_data.type='ORTHO'
span=max(size.z,size.x*1.5,size.y*1.5)*1.14
camera_data.ortho_scale=span; camera_data.clip_start=0.001; camera_data.clip_end=100
front=Vector({'+x':(1,0,0),'-x':(-1,0,0),'+y':(0,1,0),'-y':(0,-1,0)}[args.front_axis])
right=Vector((-front.y,front.x,0))
views={'front':front,'side':right,'back':-front,'threequarter':(front+right*0.65+Vector((0,0,0.15))).normalized()}
for name,direction,energy in [('Key',front+right*.7+Vector((0,0,1)),25),
                              ('Fill',front-right+Vector((0,0,.4)),15),
                              ('Back',-front+Vector((0,0,.6)),25)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=energy*span**2;data.shape='DISK';data.size=span*1.5
    lamp=bpy.data.objects.new(name,data);scene.collection.objects.link(lamp)
    lamp.location=center+direction.normalized()*span*2
    lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
renders={}
for name,direction in views.items():
    camera.location=center+direction*max(size)*4
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    file=out/f'{name}.png'; scene.render.filepath=str(file); bpy.ops.render.render(write_still=True)
    renders[name]={'file':str(file.resolve()),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                   'cameraPosition':list(camera.location),'cameraTarget':list(center),'orthoScale':span}
bpy.ops.wm.save_as_mainfile(filepath=str(out/'editable.blend'))
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes: obj.select_set(True)
for rig in rigs:
    rig.data.pose_position='POSE'
    rig.select_set(True)
display_model=out/'inspection.glb'
bpy.ops.export_scene.gltf(filepath=str(display_model),export_format='GLB',use_selection=True,export_yup=True,export_animation_mode='NLA_TRACKS')
report={'stageId':stage['id'],'sourcePhoto':stage['sourcePhoto'],'sourcePhotoSha256':stage['sourcePhotoSha256'],
        'sourceCrop':generation.get('sourceCrop'),'model':str(model_path),'modelSha256':generation['modelSha256'],
        'renders':renders,'bounds':{'min':list(lo),'max':list(hi)},'frontAxis':args.front_axis,
        'fidelityVerified':False,'status':'awaiting_visual_review','visibleDifferences':None,
        'limitation':'Unseen surfaces are inferred; camera registration and details require review.'}
report['displayModel']={'file':str(display_model.resolve()),'sha256':hashlib.sha256(display_model.read_bytes()).hexdigest()}
(out/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTUAL_STAGE_RENDERS_SAVED',args.stage_id)
