"""Render unchanged actual GLB materials and posed hands, with no diagnostic geometry."""
import argparse,hashlib,json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);r=json.loads(Path(args.generation).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(r['model'])==r['modelSha256'] and sha(r['sourcePhoto'])==r['sourcePhotoSha256']
out=Path(args.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=r['model']);scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1;rig=rigs[0]
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(meshes)==1;obj=meshes[0]
for other in scene.objects:
 if other.type=='MESH' and other not in meshes:other.hide_render=True
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='REST';bpy.context.view_layer.update()
def coords():
 evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
 xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
 matrix=np.asarray(evaluated.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
 evaluated.to_mesh_clear();return points
rest=coords();masks={};centers={}
for side,sign in [('Left',1),('Right',-1)]:
 groups={g.index for g in obj.vertex_groups if g.name.startswith(side+'Hand')}
 total=np.array([sum(g.weight for g in v.groups if g.group in groups) for v in obj.data.vertices])
 mask=(total>.995)&(rest[:,0]*sign>.12)&(rest[:,2]<.535)&(rest[:,2]>.415);assert mask.sum()>100
 masks[side]=mask;centers[side]=Vector(rest[mask].mean(0))
rig.data.pose_position='POSE'
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16
scene.render.resolution_x=560;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Actual hand material review');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.5,.5,.5,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=1
data=bpy.data.cameras.new('Same hand bind camera follows actual exported wrist joint');camera=bpy.data.objects.new(data.name,data)
scene.collection.objects.link(camera);scene.camera=camera;data.type='ORTHO';data.ortho_scale=.14;data.clip_start=.001
lights=[]
for name,direction in [('Key',Vector((.6,-1,1))),('Fill',Vector((-1,-.3,.3)))]:
 d=bpy.data.lights.new(name,'AREA');d.energy=2;d.size=.18;o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);lights.append((o,direction.normalized()))
rows=[]
for motion,fraction in [('Run',.66),('Attack',.18),('Attack',.78)]:
 action=next(a for a in bpy.data.actions if a.name.startswith(motion+' /'));rig.animation_data.action=action
 if action.slots:rig.animation_data.action_slot=action.slots[0]
 first,last=action.frame_range;frame=first+(last-first)*fraction;scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
 points=coords();assert np.isfinite(points).all()
 for side in ['Left','Right']:
  bone=rig.data.bones[side+'Hand'];pose=rig.pose.bones[side+'Hand']
  deform=rig.matrix_world@pose.matrix@bone.matrix_local.inverted()@rig.matrix_world.inverted()
  center=deform@centers[side];direction=(deform.to_3x3()@Vector((.35,-1,.10))).normalized()
  camera.location=center+direction*.5;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  for lamp,offset in lights:
   lamp.location=center+(deform.to_3x3()@offset).normalized()*.3;lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
  file=out/f'{side.lower()}_{motion.lower()}_{fraction:.2f}.png';scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
  rows.append({'side':side,'motion':motion,'fraction':fraction,'frame':frame,'file':str(file),'sha256':sha(file),
   'cameraPosition':list(camera.location),'cameraTarget':list(center),'orthoScale':data.ortho_scale,
   'actualHandVertexBounds':[points[masks[side]].min(0).tolist(),points[masks[side]].max(0).tolist()]})
  print('ACTUAL_HAND_MOTION_RENDERED',side,motion,fraction,flush=True)
report={'modelSha256':r['modelSha256'],'sourcePhoto':r['sourcePhoto'],'sourcePhotoSha256':r['sourcePhotoSha256'],
 'actualImportedSkeletons':1,'actualModelGeometryChanged':False,'actualMaterialChanged':False,'diagnosticObjectsAdded':False,
 'scope':'six actual posed hand close-ups; camera follows actual wrist joint, entire source mesh remains present',
 'renders':rows,'scriptSha256':sha(__file__),'sourceGlbUnchanged':sha(r['model'])==r['modelSha256'],
 'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
(out/'comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
