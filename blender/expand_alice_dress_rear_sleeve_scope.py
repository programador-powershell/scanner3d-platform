"""Review a local rear-sleeve extension while preserving the verified dress scope."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--baseline',required=True);p.add_argument('--scope',required=True)
p.add_argument('--measurement',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);read=lambda q:json.loads(Path(q).read_text());sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
g,b,s,m=[read(q) for q in (a.generation,a.baseline,a.scope,a.measurement)]
assert sha(g['editableBlend'])==g['editableBlendSha256']==b['parentEditableSha256']
for manifest,key,hashkey in [(b,'geometryFile','geometrySha256'),(s,'dataFile','dataSha256'),(m,'dataFile','dataSha256')]:assert sha(manifest[key])==manifest[hashkey]
d=np.load(b['geometryFile']);old=np.load(s['dataFile']);measured=np.load(m['dataFile'])
points,faces=d['world_points'],d['triangles'];centers=points[faces].mean(1)
assert np.array_equal(faces,measured['faces']) and np.max(np.abs(points-measured['points']))<1e-7
rgb=measured['colors'][faces].mean(1)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);scene=bpy.context.scene;whole=bpy.data.objects[b['nativeWholeObject']];mesh=whole.data
slots=np.array([p.material_index for p in mesh.polygons],np.int32)[d['polygon_indices']]
skin_slots={i for i,mat in enumerate(mesh.materials) if 'exposed skin' in mat.name.lower()}
x,y,z=centers.T;arm_center=.102+(.693-z)*.49
bare_arm=(z>.535)&(z<.698)&(np.abs(np.abs(x)-arm_center)<.03)&(np.abs(y)<.06)
protected=np.isin(slots,list(skin_slots))|bare_arm
coverage=old['visible_camera_masks'].copy();coverage[:,protected]=False
previous=coverage.any(0)
# Only the sleeve silhouette away from the central hair curtain is eligible.
# Green textile seeds plus one adjacent face ring recover nearby embroidery;
# the original skin material and anatomical landmarks are always protected.
candidate=(np.abs(x)>.09)&(np.abs(x)<.17)&(z>.69)&(z<.79)&~protected
seed=candidate&(rgb[:,1]>rgb[:,0]*1.04)&(rgb[:,1]>rgb[:,2]*.95)
seed_vertices=np.unique(faces[seed]);candidate &= np.isin(faces,seed_vertices).any(1)
indices=np.flatnonzero(candidate&~previous)
rectangles={'front':[(.325,.224,.396,.315),(.611,.224,.681,.315)],
            'left':[(.452,.229,.563,.317)],'right':[(.434,.229,.548,.317)],
            'back':[(.325,.227,.399,.315),(.613,.227,.681,.315)]}
tree=BVHTree.FromPolygons(points.tolist(),faces.tolist(),all_triangles=True)
views=[r for r in b['renders'] if r['kind']=='basecolor'];added=np.zeros_like(coverage)
for camera_index,row in enumerate(views):
    camera=Matrix(row['cameraWorldMatrix']);inverse=np.array(camera.inverted());projection=np.array(row['cameraProjectionMatrix'])
    local=centers[indices]@inverse[:3,:3].T+inverse[:3,3];clip=np.c_[local,np.ones(len(local))]@projection.T
    screen=clip[:,:2]/clip[:,3,None]*[.5,-.5]+.5;within=np.zeros(len(indices),bool)
    for x0,y0,x1,y1 in rectangles[row['view']]:within|=(screen[:,0]>x0)&(screen[:,0]<x1)&(screen[:,1]>y0)&(screen[:,1]<y1)
    direction=-(camera.to_3x3()@Vector((0,0,1)))
    for j in np.flatnonzero(within):
        face=int(indices[j]);origin=camera@Vector((float(local[j,0]),float(local[j,1]),0))
        location,normal,hit,distance=tree.ray_cast(origin,direction,b['orthoScale']*6)
        if location is not None and (hit==face or np.linalg.norm(np.array(location)-centers[face])<1e-5):added[camera_index,face]=True
coverage|=added;selected=coverage.any(0);assert not selected[protected].any()
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
np.savez_compressed(out/'visible_dress_faces.npz',polygon_indices=d['polygon_indices'][selected],triangle_indices=np.flatnonzero(selected),visible_camera_masks=coverage,candidate_mask=selected,current_vertex_ownership=old['current_vertex_ownership'],local_added_triangles=np.flatnonzero(added.any(0)))
rig=next(obj for obj in scene.objects if obj.type=='ARMATURE');rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
rig.data.pose_position='REST'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for c in bpy.data.collections:c.hide_viewport=c.hide_render=False
for obj in scene.objects:
    obj.hide_viewport=obj not in (whole,rig);obj.hide_render=obj!=whole;obj.hide_set(obj not in (whole,rig))
    if obj!=whole:
        for mod in obj.modifiers:mod.show_viewport=mod.show_render=False
scene.frame_set(1);bpy.context.view_layer.update();mesh.materials.clear()
for name,color in [('protected',(0,0,0,1)),('retained garment',(1,1,1,1)),('local sleeve extension',(1,0,0,1))]:
    mat=bpy.data.materials.new(name);mat.use_nodes=True;nodes=mat.node_tree.nodes;e=nodes.new('ShaderNodeEmission');e.inputs['Color'].default_value=color
    mat.node_tree.links.new(e.outputs[0],next(n for n in nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface']);mesh.materials.append(mat)
previous_polygons=set(d['polygon_indices'][previous].tolist());extra_polygons=set(d['polygon_indices'][added.any(0)].tolist())
for poly in mesh.polygons:poly.material_index=2 if poly.index in extra_polygons else int(poly.index in previous_polygons)
data=bpy.data.cameras.new('Local rear sleeve review');data.type='ORTHO';data.ortho_scale=b['orthoScale'];data.clip_start=.001
camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4;scene.cycles.use_denoising=False;scene.cycles.use_adaptive_sampling=False;scene.cycles.seed=0;scene.cycles.use_animated_seed=False
scene.render.resolution_x,scene.render.resolution_y=b['resolution'];scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True;scene.view_settings.view_transform='Standard'
renders=[]
for row in views:
    camera.matrix_world=Matrix(row['cameraWorldMatrix']);scene.render.filepath=str(out/(row['view']+'_dress_mask.png'));bpy.ops.render.render(write_still=True)
    renders.append(dict(view=row['view'],file=scene.render.filepath,sha256=sha(scene.render.filepath)))
report=dict(sourceGeneration=a.generation,sourceBlendSha256=g['editableBlendSha256'],baselineFile=a.baseline,baselineSha256=sha(a.baseline),baseScope=a.scope,baseScopeSha256=sha(a.scope),
    dataFile=str(out/'visible_dress_faces.npz'),dataSha256=sha(out/'visible_dress_faces.npz'),selectedTriangles=int(selected.sum()),retainedPolygons=int(previous.sum()),localAddedTriangles=int(added.any(0).sum()),perCameraAddedTriangles=added.sum(1).tolist(),perCameraVisibleTriangles=coverage.sum(1).tolist(),
    maskDefinition='White: previously verified material scope. Red: proposed local sleeve addition. Black: protected original surfaces.',cameraRectangles=rectangles,originalSkinAndBareArmFacesProtected=True,renders=renders,selectionApproved=False,fullDressCoverageApproved=False,published=False,sourceUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],scriptSha256=sha(__file__))
(out/'scope_review.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_sleeve_scope.py');print('LOCAL_SLEEVE_SCOPE_COMPLETE',json.dumps({k:report[k] for k in ('selectedTriangles','retainedPolygons','localAddedTriangles','perCameraAddedTriangles')}),flush=True)
