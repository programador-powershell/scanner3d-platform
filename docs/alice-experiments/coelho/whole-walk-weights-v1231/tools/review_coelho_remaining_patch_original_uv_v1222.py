"""Disposable exact-source UV diagnosis, six left torso/sleeve patches and context."""
import bpy,numpy as np,json,hashlib
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'remaining_patch_original_uv_REVIEW_v1222';D.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));a=np.load(O/'whole_skin_export_source_character_v1202.npz');g=np.load(O/'semantic_weight_masks_v1082/hip_garment_protection_mask_v1083.npz');roots=g['indexedComponents'];chosen=[31911,33610,37288,40008,47679,50222,72825,75839,76235,78840,85281,87036];source=read(O/'semantic_weight_masks_v1082/source_manifest.json')['materials'][0]['images']['Base Color'];tex=O/'semantic_weight_masks_v1082'/source['path'];assert hashlib.sha256(tex.read_bytes()).hexdigest()==source['sha256']
current=read(R/'COELHO_CURRENT_WHOLE_SKIN_CHECKPOINT.json');assert current['version']=='v1216' and current['GitHubCheckpoint']['exports']=='v1203'
assert current['GitEvidenceByteIntegrity']['allTrackedFileBytesVerified']
assert hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest()==current['files']['blend']['sha256']
assert any(im.packed_file and hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==source['sha256'] for im in bpy.data.images), 'Actual current packed base color must match original diagnostic image'
for ob in list(bpy.data.objects):bpy.data.objects.remove(ob,do_unlink=True)
mat=bpy.data.materials.new('DIAGNOSTIC_OriginalBaseColor');mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission');im=n.new('ShaderNodeTexImage');im.image=bpy.data.images.load(str(tex));im.image.colorspace_settings.name='sRGB';mat.node_tree.links.new(im.outputs['Color'],em.inputs['Color']);mat.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
cyan=bpy.data.materials.new('DIAGNOSTIC_LeftPatchCyan');cyan.use_nodes=True;cn=cyan.node_tree.nodes;cn.clear();cout=cn.new('ShaderNodeOutputMaterial');cem=cn.new('ShaderNodeEmission');cem.inputs['Color'].default_value=(0,1,1,1);cyan.node_tree.links.new(cem.outputs[0],cout.inputs['Surface'])
camera=bpy.data.cameras.new('DiagnosticCamera');cam=bpy.data.objects.new('DiagnosticCamera',camera);bpy.context.scene.collection.objects.link(cam);s=bpy.context.scene;s.camera=cam;camera.type='ORTHO';s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=8;s.render.threads_mode='FIXED';s.render.threads=4;s.render.resolution_x=s.render.resolution_y=700;s.render.resolution_percentage=100;s.view_settings.view_transform='Standard';renders=[]
def render(mesh,label,center,scale,direction):
    ob=bpy.data.objects.new(label,mesh);s.collection.objects.link(ob);camera.ortho_scale=scale;center=Vector(center);cam.location=center+Vector(direction);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();p=D/f'{label}_v1222.png';assert not p.exists();s.render.filepath=str(p);bpy.ops.render.render(write_still=True);renders.append(dict(label=label,path=p.relative_to(R).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()));bpy.data.objects.remove(ob,do_unlink=True);bpy.data.meshes.remove(mesh)
for root in chosen:
    mask=(roots[a['triangles']]==root).all(1);tri=a['triangles'][mask];ids=np.unique(tri);index=np.full(len(a['positions']),-1,np.int32);index[ids]=np.arange(len(ids));P=a['positions'][ids];mesh=bpy.data.meshes.new(str(root));mesh.from_pydata(P.tolist(),[],index[tri].tolist());mesh.uv_layers.new(name='ExactSourceUV').data.foreach_set('uv',a['loopUV'][a['triangleLoops'][mask]].astype(np.float32).ravel());mesh.materials.append(mat);mesh.update();render(mesh,f'original_uv_root{root}_rest',(P.min(0)+P.max(0))/2,float(np.max(P.max(0)-P.min(0)))*1.4,(1,1,.2))
for label,P in [('rest',a['positions']),('actual_current_walk18',np.load(O/'remaining_walk_regions_REVIEW_v1221/actual_weights_walk_frame18_v1221.npz')['positions'])]:
    mesh=bpy.data.meshes.new(label);mesh.from_pydata(P.tolist(),[],a['triangles'].tolist());mesh.uv_layers.new(name='ExactSourceUV').data.foreach_set('uv',a['loopUV'][a['triangleLoops']].astype(np.float32).ravel());mesh.materials.append(mat);mesh.materials.append(cyan);mask=np.isin(roots[a['triangles']],chosen).all(1)
    for p in mesh.polygons:
        if mask[p.index]:p.material_index=1
    mesh.update()
    for view,direction in [('front',(0,-4,0)),('back',(0,4,0)),('right_profile',(-4,0,0)),('left_profile',(4,0,0))]:
        copy=mesh.copy();render(copy,f'actual_character_remaining_patches_{label}_{view}',(0,.015,1.34),.8,direction)
    bpy.data.meshes.remove(mesh)
report=dict(version='v1222',readOnlyDiagnostic=True,sourceTrianglesAndUVExactlyCurrent1202=True,unlitSourceTextureNotPBRFidelityProof=True,actualCurrent1200AnalyticWalk18FromAuthoritativeWeights1221=True,roots=chosen,renders=renders,noBlendOrExportChanged=True,visualIdentificationPending=True,productionComplete=False)
(D/'audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CURRENT_REMAINING_PATCH_TWENTY_VIEWS_COMPLETE_NO_SOURCE_EDIT',flush=True)
