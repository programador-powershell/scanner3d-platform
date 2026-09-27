"""Measure five actual reimported garment surfaces and render the shared study.

Matches original midsurface points to verified rest vertices in the actual GLB,
then checks all recorded poses against the fitted response. The six full-model
renders include both motion angles and rest. Presence of a rig is not approval.
"""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True)
p.add_argument('--fit',required=True)
p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g,fit=read(a.generation),read(a.fit);entry=g['exports']['foundation'];seed=read(fit['seedReport'])
assert sha(entry['model'])==entry['modelSha256']
assert sha(entry['sourcePhoto'])==entry['sourcePhotoSha256']==fit['sourcePhotoSha256']
assert sha(fit['dataFile'])==fit['dataSha256'] and sha(seed['dataFile'])==seed['dataSha256']
data=np.load(fit['dataFile']);s=np.load(seed['dataFile']);names=data['bone_names'].tolist()
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=entry['model'])
scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
assert set(names)==set(rig.data.bones.keys()) and len(names)==209
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(meshes)==229
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='REST';bpy.context.view_layer.update()

def coords(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
 matrix=np.asarray(ev.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
 ev.to_mesh_clear();return points

receivers=[];rest_rows=[]
for part in seed['parts']:
 obj=bpy.data.objects[part['actualWeightedPreview']];rest=coords(obj)
 tree=KDTree(len(rest))
 for i,point in enumerate(rest):tree.insert(Vector(point),i)
 tree.balance()
 original=s['rest_points'][part['start']:part['start']+part['vertices']]
 matches=[tree.find(Vector(point)) for point in original]
 indices=np.asarray([match[1] for match in matches]);error=max(match[2] for match in matches)
 assert error<2e-6,(part['key'],error)
 receivers.append((obj,indices));rest_rows.append({'key':part['key'],'actualImportedVertices':len(rest),
                                               'originalMidsurfaceVerticesMatched':len(indices),'restMaximumMatchErrorMeters':error})
bounds=np.asarray([point for obj in meshes for point in [coords(obj).min(0),coords(obj).max(0)]])
rig.data.pose_position='POSE';action=next(act for act in bpy.data.actions if act.name==g['sewnClothStudyClip'])
rig.animation_data.action=action
if action.slots:rig.animation_data.action_slot=action.slots[0]
first,last=action.frame_range
bind={n:rig.data.bones[n].matrix_local.inverted() for n in names}
world=np.asarray(rig.matrix_world);inverse=np.linalg.inv(world)
rows=[];history=[];joint_history=[]
for index,expected in enumerate(data['rig_deformations']):
 frame=first+(last-first)*index/(len(data['rig_deformations'])-1)
 scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
 actual=np.asarray([world@np.asarray(rig.pose.bones[n].matrix@bind[n])@inverse for n in names])
 matrix_error=float(np.max(np.abs(actual-expected)));assert matrix_error<2e-5,(index,matrix_error)
 xyz=np.concatenate([coords(obj)[ids] for obj,ids in receivers]);assert np.isfinite(xyz).all()
 fitted_error=np.linalg.norm(xyz-data['fitted_points'][index],axis=1)
 assert fitted_error.max()<2e-5,(index,float(fitted_error.max()))
 residual=np.linalg.norm(xyz-data['actual_solver_points'][index],axis=1)
 parts=[]
 for part in seed['parts']:
  lo,hi=part['start'],part['start']+part['vertices']
  parts.append({'key':part['key'],'actualExportVsFitMaximumMeters':float(fitted_error[lo:hi].max()),
                'actualExportVsSolverMaximumMeters':float(residual[lo:hi].max()),
                'actualExportVsSolverP95Meters':float(np.percentile(residual[lo:hi],95))})
 rows.append({'sourcePhysicsFrame':index+1,'actualImportedFrame':frame,'actualJointMatrixMaximumError':matrix_error,
              'actualExportVsFitMaximumMeters':float(fitted_error.max()),'parts':parts})
 history.append(xyz);joint_history.append(actual)
 print('ACTUAL_EXPORTED_FIVE_GARMENT_POSES',index+1,matrix_error,float(fitted_error.max()),flush=True)
raw=out/'actual_exported_five_garment_frames.npz'
np.savez_compressed(raw,points=np.asarray(history),actual_joint_deformations=np.asarray(joint_history),bone_names=data['bone_names'])
record={'modelSha256':entry['modelSha256'],'sourcePhotoSha256':entry['sourcePhotoSha256'],'fitDataSha256':fit['dataSha256'],
        'clip':action.name,'actualRestCorrespondence':rest_rows,'frames':rows,'dataFile':str(raw),'dataSha256':sha(raw),
        'scriptSha256':sha(__file__),'actualFiveGarmentSurfacesMeasured':True,
        'allLayersFinished':False,'motionVerified':False,'clothCollisionVerified':False,'fidelityVerified':False}
(out/'actual_pose_measurements.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12
scene.render.resolution_x,scene.render.resolution_y=620,820;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Actual exported two-anagua study review');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.35,.35,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
lo,hi=bounds.min(0),bounds.max(0);center=Vector((lo+hi)/2)
span=max(float((hi-lo)[2]),float(math.hypot(*(hi-lo)[:2]))*820/620)*1.22
cam=bpy.data.cameras.new('Fixed actual full foundation camera');camera=bpy.data.objects.new(cam.name,cam)
scene.collection.objects.link(camera);scene.camera=camera;cam.type='ORTHO';cam.ortho_scale=span;cam.clip_start=.001
for name,direction,energy in [('Key',(1,-2,2),25),('Fill',(-2,-1,1),15),('Back',(0,2,1),25)]:
 light=bpy.data.lights.new(name,'AREA');light.energy=energy*span**2;light.size=span*1.5
 obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=center+Vector(direction).normalized()*span*2
 obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
renders=[]
for source_frame,view in [(1,'front'),(1,'back'),(20,'front'),(29,'threequarter'),(29,'profile'),(29,'back')]:
 frame=rows[source_frame-1]['actualImportedFrame'];scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
 direction={'front':Vector((0,-1,0)),'back':Vector((0,1,0)),'profile':Vector((1,0,0)),
            'threequarter':Vector((.65,-1,.12)).normalized()}[view]
 camera.location=center+direction*span*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
 file=out/f'foundation_{source_frame:02d}_{view}.png';scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
 renders.append({'sourcePhysicsFrame':source_frame,'actualImportedFrame':frame,'view':view,'scope':'foundation',
                 'file':str(file),'sha256':sha(file),'cameraPosition':list(camera.location),'visibleSkinnedMeshes':229})
 (out/'progress.json').write_text(json.dumps({'completed':False,'renders':renders})+'\n')
 print('ACTUAL_EXPORTED_SEWN_CLOTH_RENDERED',source_frame,view,flush=True)
comparison={**record,'sourcePhoto':entry['sourcePhoto'],'renders':renders,'actualSkeletons':1,'actualSkinnedMeshes':229,
            'modelUnchanged':sha(entry['model'])==entry['modelSha256'],'finalFbxExported':False,
            'limitation':'Reimported fitted study, not the physical trajectory itself. Residuals, body and layer contacts, all actions, other layers and photo fidelity remain unapproved.'}
(out/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_review.py')
print('ACTUAL_EXPORTED_SEWN_CLOTH_REVIEW_SAVED',flush=True)
