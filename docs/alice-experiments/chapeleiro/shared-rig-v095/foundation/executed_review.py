"""Inspect and render the actual exported foundation or intact whole skin.

All measurements concern reimported GLB bytes, not Blender rig declarations.
Three poses per action expose failures; they never approve all-frame motion or
cloth physics. The contact sheet always keeps that asset's original photograph.
"""
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--family',choices=['foundation','whole'],required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--rest-views',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
record=json.loads(Path(args.generation).read_text(encoding='utf-8'))
if 'exports' in record:
    record={**record['exports'][args.family], 'rigPresent':record['sharedArmatures']==1}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if not record.get('rigPresent'):raise ValueError('Requires an actual exported rig study.')
for key in ['model','sourcePhoto']:
    if sha(record[key])!=record[key+'Sha256']:raise ValueError('Changed actual evidence: '+key)
expected_photo={'foundation':'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4',
    'whole':'69e81154d4fe0903f76883a049ea9c3e2e9f16f57e488cf2075a0d7158e8feab'}
if record['sourcePhotoSha256']!=expected_photo[args.family]:raise ValueError('Photograph belongs to a different stage.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve previous actual motion evidence.')
out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=record['model'])
scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE']
if len(rigs)!=1:raise ValueError('Every actual component must share one imported skeleton.')
rig=rigs[0];bone_shapes={b.custom_shape for b in rig.pose.bones if b.custom_shape}
meshes=[o for o in scene.objects if o.type=='MESH' and o not in bone_shapes]
if len(meshes)!=record['actualSkinnedNodes']:raise ValueError('Exported actual mesh count changed.')
for obj in meshes:
    modifiers=[m for m in obj.modifiers if m.type=='ARMATURE']
    if len(modifiers)!=1 or modifiers[0].object!=rig:raise ValueError('An exported piece has a different/no skin.')
rig.animation_data_create()
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='REST';bpy.context.view_layer.update()

def coordinates(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    matrix=np.asarray(evaluated.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    edges=np.empty(len(mesh.edges)*2,np.int32);mesh.edges.foreach_get('vertices',edges)
    evaluated.to_mesh_clear();return points,edges.reshape(-1,2)

rest={};rest_audit=[];bounds=[]
bone_names={b.name for b in rig.data.bones}
for obj in meshes:
    points,edges=coordinates(obj);lengths=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1)
    indices={g.index for g in obj.vertex_groups if g.name in bone_names};unweighted=0;max_error=0.;max_influences=0
    for vertex in obj.data.vertices:
        weights=[g.weight for g in vertex.groups if g.group in indices and g.weight>1e-9]
        unweighted+=not bool(weights);max_error=max(max_error,abs(sum(weights)-1));max_influences=max(max_influences,len(weights))
    if unweighted or max_error>1e-5 or max_influences>4:raise ValueError('Invalid skin in the actual exported GLB.')
    if not obj.data.uv_layers or not np.isfinite(points).all():raise ValueError('Lost UVs or invalid exported coordinates.')
    rest[obj.name]=(points,edges,lengths);bounds.extend([points.min(axis=0),points.max(axis=0)])
    rest_audit.append({'mesh':obj.name,'actualVertices':len(points),'boneGroups':[g.name for g in obj.vertex_groups if g.index in indices],
        'unweightedVertices':unweighted,'maximumNormalizationError':max_error,'maximumInfluences':max_influences})
rig.data.pose_position='POSE';poses=[];clips=[]
for label in ['Walk','Run','Jump','Attack']:
    actions=[a for a in bpy.data.actions if a.name.startswith(label+' /')]
    if len(actions)!=1:raise ValueError('A required unique action is missing from the exported GLB.')
    action=actions[0];rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    first,last=action.frame_range
    fractions=[8/52,24/52,40/52] if label=='Jump' else ([.18,.50,.78] if label=='Attack' else [0,.33,.66])
    clip={'clip':action.name,'frameRange':[first,last],'poses':[],'motionVerified':False,'clothCollisionVerified':False}
    for index,fraction in enumerate(fractions):
        frame=first+(last-first)*fraction;scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
        measurements=[]
        for obj in meshes:
            points,edges=coordinates(obj);reference,rest_edges,lengths=rest[obj.name]
            if not np.isfinite(points).all() or not np.array_equal(edges,rest_edges):raise ValueError('Invalid deformation/topology change.')
            posed=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1);valid=lengths>1e-5;ratios=posed[valid]/lengths[valid]
            lo,hi=points.min(axis=0),points.max(axis=0);bounds.extend([lo,hi])
            # Translation of the torso alone is not evidence that limbs deform.
            delta=points-reference;residual=delta-delta.mean(axis=0)
            measurements.append({'mesh':obj.name,'maximumEdgeStretch':float(ratios.max(initial=1)),
                'edgeStretch95Percentile':float(np.percentile(ratios,95)) if ratios.size else 1,
                'edgeFractionAbove150Percent':float((ratios>1.5).mean()) if ratios.size else 0,
                'maximumDeformationAfterTranslation':float(np.linalg.norm(residual,axis=1).max(initial=0)),
                'bounds':[lo.tolist(),hi.tolist()]})
        pose={'frame':frame,'fraction':fraction,'componentMeasurements':measurements};clip['poses'].append(pose)
        poses.append((label,index,action,pose));print('ACTUAL_EXPORT_POSE_MEASURED',args.family,label,index+1,flush=True)
    clips.append(clip)
array=np.asarray(bounds);lo=array.min(axis=0);hi=array.max(axis=0);center=Vector((lo+hi)/2);size=hi-lo
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=12
scene.render.resolution_x=520;scene.render.resolution_y=760;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
scene.world=bpy.data.worlds.new('Actual shared-rig export inspection');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.35,.35,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
front,right=Vector((0,-1,0)),Vector((1,0,0));direction=(front+right*.5+Vector((0,0,.10))).normalized()
span=max(float(size[2]),float(math.hypot(size[0],size[1]))*760/520)*1.14
camera_data=bpy.data.cameras.new('Fixed camera / all sampled motion bounds');camera=bpy.data.objects.new('Motion evidence camera',camera_data)
scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO';camera_data.ortho_scale=span;camera_data.clip_start=.001
camera.location=center+direction*span*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
for name,direction,energy in [('Key',front+right*.7+Vector((0,0,1)),25),('Fill',front-right+Vector((0,0,.4)),15),('Back',-front+Vector((0,0,.6)),25)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=energy*span**2;data.size=span*1.5
    lamp=bpy.data.objects.new(name,data);scene.collection.objects.link(lamp);lamp.location=center+direction.normalized()*span*2
    lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
rest_renders=[]
if args.rest_views:
    rig.animation_data.action=None;rig.data.pose_position='REST';bpy.context.view_layer.update()
    for view,direction in [('front',Vector((0,-1,0))),('side',Vector((1,0,0))),('back',Vector((0,1,0))),('threequarter',Vector((.5,-1,.10)).normalized())]:
        camera.location=center+direction*span*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        file=out/('rest_'+view+'.png');scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
        rest_renders.append({'view':view,'file':str(file.resolve()),'sha256':sha(file),'cameraPosition':list(camera.location)})
        print('ACTUAL_EXPORT_REST_RENDERED',args.family,view,flush=True)
    rig.data.pose_position='POSE'
    camera.location=center+Vector((.5,-1,.10)).normalized()*span*3
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
for label,index,action,pose in poses:
    rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    frame=pose['frame'];scene.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
    file=out/(label.lower()+'_'+str(index+1)+'.png');scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
    pose.update(render=str(file.resolve()),renderSha256=sha(file));print('ACTUAL_EXPORT_POSE_RENDERED',args.family,label,index+1,flush=True)
report={'family':args.family,'model':record['model'],'modelSha256':record['modelSha256'],'sourcePhoto':record['sourcePhoto'],
    'sourcePhotoSha256':record['sourcePhotoSha256'],'actualImportedSkeletons':len(rigs),'actualImportedSkinnedMeshes':len(meshes),
    'restSkinAudit':rest_audit,'clips':clips,'restRenders':rest_renders,'scriptSha256':sha(__file__),'camera':{'position':list(camera.location),'target':list(center),'orthoScale':span},
    'status':'awaiting_visual_motion_review','fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
    'limitations':['Three actual poses per action do not approve all-frame quality or game transitions.',
        'Secondary cloth bones only follow their parent; physical response and body/inter-layer collisions are not baked.',
        'Photographic scale, unseen anatomy, native hair weighting and extreme-pose deformation require refinement.']}
(out/'motion_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copyfile(__file__,out/'executed_review.py')
print('ACTUAL_SHARED_RIG_EXPORT_REVIEW_SAVED',args.family,flush=True)
