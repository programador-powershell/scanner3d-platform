"""Inspect the actual reimported whole-character GLB in the original cameras."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--export',required=True);p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);read=lambda q:json.loads(Path(q).read_text());sha=lambda q:hashlib.sha256(Path(q).read_bytes()).hexdigest()
e,b=read(a.export),read(a.baseline);g=read(e['sourceGeneration'])
assert sha(e['model'])==e['modelSha256'];assert sha(b['geometryFile'])==b['geometrySha256']
reference=np.load(b['geometryFile']);reference_points=reference['world_points']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=e['model']);scene=bpy.context.scene
all_meshes=[o for o in scene.objects if o.type=='MESH'];rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
# The Blender glTF importer adds an Icosphere for bone display. It is not a
# mesh from the GLB. Inspect only the actual skinned model and hide helpers.
meshes=[o for o in all_meshes if any(m.type=='ARMATURE' and m.object==rigs[0] for m in o.modifiers)];assert len(meshes)==1
whole,rig=meshes[0],rigs[0];rig.animation_data.action=None
for obj in scene.objects:obj.hide_render=obj!=whole
for track in rig.animation_data.nla_tracks:track.mute=True
rig.data.pose_position='REST'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
scene.frame_set(1);bpy.context.view_layer.update();mesh=whole.data;mesh.calc_loop_triangles()
points=np.array([whole.matrix_world@v.co for v in mesh.vertices]);assert len(mesh.loop_triangles)==len(reference['triangles'])
tree=KDTree(len(reference_points))
for i,point in enumerate(reference_points):tree.insert(point,i)
tree.balance();max_distance=max(tree.find(point)[2] for point in points)
assert max_distance<1e-6
bounds_error=float(max(abs(points.min(0)-reference_points.min(0)).max(),abs(points.max(0)-reference_points.max(0)).max()))
assert bounds_error<1e-6
center=Vector(b['cameraCenter']);span=b['orthoScale']
data=bpy.data.cameras.new('Original whole-character verification camera');data.type='ORTHO';data.ortho_scale=span;data.clip_start=.001
camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.use_denoising=True
scene.render.resolution_x,scene.render.resolution_y=b['resolution'];scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True;scene.view_settings.view_transform='Standard'
world=bpy.data.worlds.new('Neutral Alice roundtrip review');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.2,.2,.2,1);world.node_tree.nodes['Background'].inputs[1].default_value=.65;scene.world=world
for name,direction,energy in [('Key',(1,-2,2),25),('Fill',(-2,-1,1),15),('Back',(0,2,1),25)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=energy*span**2;light.size=span*1.5
    obj=bpy.data.objects.new(name,light);scene.collection.objects.link(obj);obj.location=center+Vector(direction).normalized()*span*2;obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
directions=[('front',(0,-1,0)),('left',(1,0,0)),('right',(-1,0,0)),('back',(0,1,0))];renders=[]
def render(view,direction,kind):
    camera.location=center+Vector(direction)*span*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/(view+'_'+kind+'.png'));bpy.ops.render.render(write_still=True)
    renders.append(dict(view=view,kind=kind,file=scene.render.filepath,sha256=sha(scene.render.filepath),cameraWorldMatrix=np.array(camera.matrix_world).tolist(),cameraProjectionMatrix=np.array(camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=scene.render.resolution_x,y=scene.render.resolution_y)).tolist()))
for view,direction in directions:
    if view in ('front','back'):render(view,direction,'surface')
for index,original in enumerate(list(mesh.materials)):
    material=original.copy();mesh.materials[index]=material;nodes=material.node_tree.nodes;links=material.node_tree.links
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL');emission=nodes.new('ShaderNodeEmission');base=bsdf.inputs['Base Color']
    if base.is_linked:links.new(base.links[0].from_socket,emission.inputs['Color'])
    else:emission.inputs['Color'].default_value=base.default_value
    links.new(emission.outputs[0],output.inputs['Surface'])
scene.cycles.samples=4;scene.cycles.use_denoising=False;scene.cycles.use_adaptive_sampling=False;scene.cycles.seed=0;scene.cycles.use_animated_seed=False
for view,direction in directions:render(view,direction,'basecolor')
report=dict(exportFile=a.export,exportSha256=sha(a.export),model=e['model'],modelSha256=e['modelSha256'],sourceGeneration=e['sourceGeneration'],generation=e['sourceGeneration'],
    resolution=b['resolution'],cameraCenter=b['cameraCenter'],orthoScale=span,garmentReference=b['garmentReference'],garmentReferenceSha256=b['garmentReferenceSha256'],
    actualImportedMeshes=len(meshes),actualImportedSkeletons=len(rigs),actualImportedBones=len(rig.data.bones),actualImportedTriangles=len(mesh.loop_triangles),actualImportedVertices=len(mesh.vertices),
    importedBoneDisplayHelperMeshes=len(all_meshes)-len(meshes),
    originalSurfaceNearestDistanceMaximumMeters=max_distance,originalBoundsMaximumErrorMeters=bounds_error,exportedGeometryPreserved=True,
    basecolorRenderSettings=dict(samples=4,denoising=False,adaptiveSampling=False,seed=0),renders=renders,sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],
    textureVisualReviewPending=True,fullDressCoverageApproved=False,characterFidelityVerified=False,clothMotionVerified=False,fbxFinalExported=False,published=False,scriptSha256=sha(__file__))
(out/'comparison.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_glb_roundtrip_review.py');print('ACTUAL_GLB_ROUNDTRIP_REVIEW_COMPLETE',json.dumps({k:report[k] for k in ('actualImportedMeshes','actualImportedSkeletons','actualImportedBones','actualImportedTriangles','originalSurfaceNearestDistanceMaximumMeters','originalBoundsMaximumErrorMeters')}),flush=True)
