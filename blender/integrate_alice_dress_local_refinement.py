"""Apply the incremental UV/albedo improvement to the entire intact character."""
import argparse,hashlib,json,shutil,struct,sys
from pathlib import Path
import bpy,numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--texture',required=True);p.add_argument('--uv-check',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);read=lambda s:json.loads(Path(s).read_text());sha=lambda s:hashlib.sha256(Path(s).read_bytes()).hexdigest()
t=read(a.texture);g=read(t['uvGeneration']);parent=read(g['parentCharacterGeneration']);check=read(a.uv_check)
assert t['conflictingUvOverlapTexels']==0 and check['safeToProject'] and check['harmfulUvOverlapTexels']==0
assert Path(check['uvGeneration']).resolve()==Path(t['uvGeneration']).resolve()
assert sha(t['textureFile'])==t['textureSha256'];assert sha(t['uvGeneration'])==t['uvGenerationSha256']
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256'];assert sha(parent['editableBlend'])==parent['editableBlendSha256']
d=np.load(g['projectionGeometry']);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend']);whole=bpy.data.objects[parent['nativeWholeObject']];mesh=whole.data
vertices=np.array([v.co[:] for v in mesh.vertices],np.float32)
assert np.array_equal(vertices,d['vertices'])
polygons=np.array([p.vertices[:] for p in mesh.polygons],np.int32)
old_uv=np.array([l.uv[:] for l in mesh.uv_layers[parent['originalUvLayer']].data],np.float32)
old_dress_uv=np.array([l.uv[:] for l in mesh.uv_layers[parent['dressUvLayer']].data],np.float32)
assert np.array_equal(old_uv,d['original_uv'])
assert np.array_equal(old_dress_uv[d['triangle_loops'][d['retained_triangle_indices']]],d['dress_uv'][d['triangle_loops'][d['retained_triangle_indices']]])
materials=np.array([p.material_index for p in mesh.polygons],np.int32)
slots={i for i,m in enumerate(mesh.materials) if m.name in parent['newGarmentMaterials']};assert len(slots)==1
slot=next(iter(slots));selected=set(d['polygon_indices'][d['selected_triangle_indices']].tolist())
assert all(materials[i]==0 for i in d['polygon_indices'][d['incremental_triangle_indices']])
assert {p.index for p in mesh.polygons if p.material_index==slot}==set(d['polygon_indices'][d['retained_triangle_indices']].tolist())
actions=[(q.name,q.session_uid) for q in bpy.data.actions]
def weight_hash():
    h=hashlib.sha256()
    for group in whole.vertex_groups:h.update(group.name.encode()+b'\0')
    for vertex in mesh.vertices:
        for group in vertex.groups:h.update(struct.pack('<IIf',vertex.index,group.group,group.weight))
    return h.hexdigest()
def rig_hash():
    h=hashlib.sha256()
    for rig in sorted((o for o in bpy.data.objects if o.type=='ARMATURE'),key=lambda o:o.name):
        for bone in rig.data.bones:
            h.update((bone.name+'|'+(bone.parent.name if bone.parent else '')).encode());h.update(np.array(bone.matrix_local,np.float32).tobytes())
    return h.hexdigest()
assert weight_hash()==g['weightHash'];before_rig=rig_hash();assert before_rig==g['rigHash']
material=mesh.materials[slot]
node=next(n for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'visibility-projected dress albedo' in n.image.name)
assert node.image.packed_file and hashlib.sha256(node.image.packed_file.data).hexdigest()==parent['textureSha256']
image=bpy.data.images.load(t['textureFile'],check_existing=False);image.name='Chapeleiro / visibility-projected dress albedo / 4K / refined sleeves'
image.colorspace_settings.name='sRGB';image.pack();node.image=image
mesh.uv_layers[parent['dressUvLayer']].data.foreach_set('uv',d['dress_uv'].ravel())
for polygon in mesh.polygons:
    if polygon.index in selected:polygon.material_index=slot
assert np.array_equal(vertices,np.array([v.co[:] for v in mesh.vertices],np.float32))
assert np.array_equal(polygons,np.array([p.vertices[:] for p in mesh.polygons],np.int32))
assert np.array_equal(old_uv,np.array([l.uv[:] for l in mesh.uv_layers[parent['originalUvLayer']].data],np.float32))
assert all(p.material_index==int(materials[p.index]) for p in mesh.polygons if p.index not in selected)
assert weight_hash()==g['weightHash'] and rig_hash()==before_rig and actions==[(q.name,q.session_uid) for q in bpy.data.actions]
assert mesh.uv_layers[parent['originalUvLayer']].active_render
blend=out/'chapeleiro_full_dress_uv4k_refined_sleeves.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
report=dict(parent);report.update(dict(parentGeneration=g['parentCharacterGeneration'],parentGenerationSha256=sha(g['parentCharacterGeneration']),editableBlend=str(blend),editableBlendSha256=sha(blend),editableBytes=blend.stat().st_size,
    uvGeneration=t['uvGeneration'],uvGenerationSha256=t['uvGenerationSha256'],uvCollisionCheck=a.uv_check,uvCollisionCheckSha256=sha(a.uv_check),
    textureManifest=a.texture,textureManifestSha256=sha(a.texture),textureFile=t['textureFile'],textureSha256=t['textureSha256'],modifiedMaterialPolygons=len(selected),
    localSleevePolygonsAdded=len(d['incremental_triangle_indices']),retainedUvCoordinatesUnchanged=True,originalUvUnchanged=True,geometryUnchanged=True,weightHash=g['weightHash'],weightsUnchanged=True,rigHash=before_rig,allRigAndActionsPreserved=True,allInteriorAuthoringPreserved=True,
    originalSkinAndBareArmMaterialsPreserved=True,protectedAnatomyAndHairMaterialsUnchanged=True,comparisonRendersPending=True,fullDressCoverageApproved=False,characterFidelityVerified=False,clothMotionVerified=False,
    newGlbOrFbxExported=False,published=False,additionalTripoCreditsConsumed=0,sourceUnchanged=sha(parent['editableBlend'])==parent['editableBlendSha256'],scriptSha256=sha(__file__)))
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_local_refinement.py')
print('FULL_CHARACTER_LOCAL_DRESS_REFINEMENT_INTEGRATED',json.dumps({k:report[k] for k in ('editableBlend','editableBlendSha256','editableBytes','localSleevePolygonsAdded','modifiedMaterialPolygons')}),flush=True)
