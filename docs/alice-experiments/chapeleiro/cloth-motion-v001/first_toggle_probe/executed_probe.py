"""Run the real existing ivory solver against animated stocking/bloomer surfaces.

This isolated physical study does not bake secondary bones into either GLB.
Original meshes, rig and parent checkpoint are preserved. All-layer collision
and anatomy are explicitly outside this initial solver probe's approval scope.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(args.generation)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(path);assert sha(r['editableBlend'])==r['editableBlendSha256']
out=Path(args.output);assert not out.exists();out.mkdir(parents=True);started=time.time()
bpy.ops.wm.open_mainfile(filepath=r['editableBlend']);scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1;rig=rigs[0]
audit=read(path.parent/'skin_audit.json');entry=next(a for a in audit['authoringCages'] if a['receiver']=='01 / long ivory gathered petticoat')
cage=bpy.data.objects[entry['mesh']];receiver=bpy.data.objects['Authoring / '+entry['receiver']]
collider_names=['01 / left stocking / fitted leg ankle and closed toe','01 / right stocking / fitted leg ankle and closed toe',
 '01 / bloomers / continuous waist and sewn crotch']
colliders=[bpy.data.objects[n] for n in collider_names]
for collection in bpy.data.collections:collection.hide_viewport=False
for obj in scene.objects:
 obj.hide_viewport=obj not in [rig,cage,receiver,*colliders]
 obj.hide_render=obj not in [receiver,*colliders]
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=None;rig.data.pose_position='POSE'
action=next(a for a in bpy.data.actions if a.name.startswith('Run / current fitted'))
first,last=action.frame_range;warmup=12;cycles=2
track=rig.animation_data.nla_tracks.new();track.name='Local physical probe / Run with first-pose warmup'
strip=track.strips.new(action.name,warmup+1,action);strip.repeat=cycles;strip.extrapolation='HOLD'
end=int(warmup+1+(last-first)*cycles);scene.frame_start=1;scene.frame_end=end
for obj in colliders:
 m=obj.modifiers.new('Actual animated underlayer collision / local solver study','COLLISION')
 obj.collision.thickness_outer=.0008;obj.collision.thickness_inner=.0008;obj.collision.cloth_friction=5
cloth=next(m for m in cage.modifiers if m.type=='CLOTH');cloth.point_cache.frame_start=1;cloth.point_cache.frame_end=end
assert cloth.settings.vertex_group_mass=='pinned'
def coords(obj):
 evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
 xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
 matrix=np.asarray(evaluated.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
 evaluated.to_mesh_clear();return points
original=np.array([cage.matrix_world@v.co for v in cage.data.vertices],np.float32)
edge_indices=np.empty(len(cage.data.edges)*2,np.int32);cage.data.edges.foreach_get('vertices',edge_indices);edges=edge_indices.reshape(-1,2)
lengths=np.linalg.norm(original[edges[:,0]]-original[edges[:,1]],axis=1);valid=lengths>1e-6
snapshots=[];rows=[]
for frame in range(1,end+1):
 scene.frame_set(frame);bpy.context.view_layer.update();points=coords(cage)
 assert points.shape==original.shape and np.isfinite(points).all()
 # Actual animated skin target with Cloth bypassed, preserving solver cache.
 cloth.show_viewport=False;bpy.context.view_layer.update();target=coords(cage)
 cloth.show_viewport=True;bpy.context.view_layer.update()
 ratios=np.linalg.norm(points[edges[:,0]]-points[edges[:,1]],axis=1)[valid]/lengths[valid]
 delta=np.linalg.norm(points-target,axis=1)
 rows.append({'frame':frame,'maximumEdgeStretch':float(ratios.max()),'edgeStretch95Percentile':float(np.percentile(ratios,95)),
  'maximumActualSolverOffsetFromAnimatedSkin':float(delta.max()),'solverOffset95Percentile':float(np.percentile(delta,95)),
  'bounds':[points.min(0).tolist(),points.max(0).tolist()]})
 snapshots.append(points)
 if frame%5==0:print('ACTUAL_IVORY_SOLVER_FRAME',frame,end,round(time.time()-started,2),flush=True)
file=out/'actual_cloth_frames.npz';np.savez_compressed(file,points=np.asarray(snapshots),rest_points=original,edges=edges)
report={'parentEditableSha256':r['editableBlendSha256'],'parentWholeModelSha256':r['exports']['whole']['modelSha256'],
 'sourcePhotoSha256':r['exports']['foundation']['sourcePhotoSha256'],'clothCage':cage.name,'receiver':receiver.name,
 'actualColliderSurfaces':collider_names,'collisionSurfaceScope':'existing animated stockings and bloomers, not a complete hidden anatomical body or all layers',
 'actualSolver':'Blender CLOTH on the existing authored midsurface','solverSettingsUnchanged':True,
 'actualWarmupFrames':warmup,'sourceAction':action.name,'sourceActionFrameRange':[first,last],'cycles':cycles,
 'frames':rows,'dataFile':str(file),'dataSha256':sha(file),'scriptSha256':sha(__file__),
 'geometryChanged':False,'parentEditableUnchanged':sha(r['editableBlend'])==r['editableBlendSha256'],
 'exportedPreviewReceivesSolverMotion':False,'secondaryBoneResponseBaked':False,'allLayersFinished':False,
 'clothCollisionVerified':False,'motionVerified':False,'fidelityVerified':False}
(out/'actual_solver_motion.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('ACTUAL_IVORY_SOLVER_PROBE_SAVED',end,flush=True)
