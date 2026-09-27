"""Integrate a verified computed atlas into the intact authoring character.

Only the reviewed garment polygons get copied materials with a new albedo UV.
Original anatomy/hair materials and their old UV remain intact, as do all
geometry, weights, bones, actions and procedural interior garment authoring.
"""
import argparse,hashlib,json,shutil,struct,sys
from pathlib import Path
import bpy
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--texture',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
t=read(a.texture);assert sha(t['textureFile'])==t['textureSha256']
assert t['conflictingUvOverlapTexels']==0
assert sha(t['uvGeneration'])==t['uvGenerationSha256']
g=read(t['uvGeneration']);assert sha(g['editableBlend'])==g['editableBlendSha256']
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
geometry=np.load(g['projectionGeometry']);selected=set(geometry['polygon_indices'][geometry['selected_triangle_indices']].tolist())
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
whole=bpy.data.objects[g['nativeWholeObject']];mesh=whole.data
coordinates=np.array([v.co[:] for v in mesh.vertices],np.float32)
assert np.array_equal(coordinates,geometry['vertices'])
original_uv=np.array([loop.uv[:] for loop in mesh.uv_layers[g['originalUvLayer']].data],np.float32)
original_materials=list(mesh.materials)
material_indices=np.array([p.material_index for p in mesh.polygons],np.int32)
polygons_before=np.array([tuple(p.vertices) for p in mesh.polygons],np.int32)
scope_selected=set(selected)
protected_skin_slots={index for index,material in enumerate(original_materials) if 'exposed skin' in material.name.lower()}
centers=geometry['world_points'][geometry['triangles']].mean(1)
x,y,z=centers.T
arm_center=.102+(.693-z)*.49
bare_arm=((z>.535)&(z<.698)&(np.abs(np.abs(x)-arm_center)<.03)&(np.abs(y)<.06))
protected_skin_polygons={p.index for p in mesh.polygons if p.material_index in protected_skin_slots}
protected_arm_polygons=set(geometry['polygon_indices'][bare_arm].tolist())
selected-=protected_skin_polygons|protected_arm_polygons
assert selected

def weights_hash():
    h=hashlib.sha256()
    for group in whole.vertex_groups:h.update(group.name.encode('utf-8')+b'\0')
    for vertex in mesh.vertices:
        for group in vertex.groups:h.update(struct.pack('<IIf',vertex.index,group.group,group.weight))
    return h.hexdigest()

assert weights_hash()==g['weightHash']
image=bpy.data.images.load(t['textureFile'],check_existing=False)
image.name='Chapeleiro / visibility-projected dress albedo / 4K / first pass'
image.colorspace_settings.name='sRGB';image.pack()
materials=[];material_mapping={}
used_source_slots={int(material_indices[index]) for index in selected}
for index,source in enumerate(original_materials):
    if index not in used_source_slots:continue
    material=source.copy();material.name=source.name+' / dress UV 4K first pass'
    nodes=material.node_tree.nodes;links=material.node_tree.links
    old_uv=nodes.new('ShaderNodeUVMap');old_uv.uv_map=g['originalUvLayer']
    old_uv.label='Preserve original normal and roughness UV'
    for node in list(nodes):
        if node.type=='TEX_IMAGE' and not node.inputs['Vector'].is_linked:
            links.new(old_uv.outputs['UV'],node.inputs['Vector'])
        if node.type=='NORMAL_MAP':node.uv_map=g['originalUvLayer']
    dress_uv=nodes.new('ShaderNodeUVMap');dress_uv.uv_map=g['newUvLayer']
    dress_uv.label='Dedicated reviewed garment UV 4096 x 4096'
    texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.interpolation='Linear'
    texture.label='Visible-face garment projection; original atlas fallback'
    bsdf=next(node for node in nodes if node.type=='BSDF_PRINCIPLED')
    links.new(dress_uv.outputs['UV'],texture.inputs['Vector'])
    links.new(texture.outputs['Color'],bsdf.inputs['Base Color'])
    material_mapping[index]=len(mesh.materials)
    mesh.materials.append(material);materials.append(material)
for polygon in mesh.polygons:
    if polygon.index in selected:polygon.material_index=material_mapping[int(material_indices[polygon.index])]
assert np.array_equal(coordinates,np.array([v.co[:] for v in mesh.vertices],np.float32))
assert np.array_equal(polygons_before,np.array([tuple(p.vertices) for p in mesh.polygons],np.int32))
assert np.array_equal(original_uv,np.array([l.uv[:] for l in mesh.uv_layers[g['originalUvLayer']].data],np.float32))
assert weights_hash()==g['weightHash']
assert all(p.material_index==int(material_indices[p.index]) for p in mesh.polygons if p.index not in selected)
mesh.uv_layers.active=mesh.uv_layers[g['originalUvLayer']]
blend=out/'chapeleiro_full_dress_uv4k_first_pass.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
report=dict(parentGeneration=t['uvGeneration'],parentEditableSha256=g['editableBlendSha256'],
    editableBlend=str(blend),editableBlendSha256=sha(blend),editableBytes=blend.stat().st_size,
    textureManifest=a.texture,textureManifestSha256=sha(a.texture),
    textureFile=t['textureFile'],textureSha256=t['textureSha256'],textureResolution=t['resolution'],
    nativeWholeObject=whole.name,dressUvLayer=g['newUvLayer'],originalUvLayer=g['originalUvLayer'],
    originalMaterials=[m.name for m in original_materials],newGarmentMaterials=[m.name for m in materials],
    modifiedMaterialPolygons=len(selected),geometryUnchanged=True,originalUvUnchanged=True,
    scopePolygonsExcludedForSkinProtection=len(scope_selected-selected),
    originalSkinMaterialSlotsPreserved=sorted(protected_skin_slots),
    allOriginalSkinMaterialFacesPreserved=True,bareArmRegionMaterialsPreserved=True,
    weightsUnchanged=True,weightHash=g['weightHash'],allInteriorAuthoringPreserved=True,
    allRigAndActionsPreserved=True,protectedAnatomyAndHairMaterialsUnchanged=True,
    sourceUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],
    firstProjectionPassIntegrated=True,comparisonRendersPending=True,fullDressCoverageApproved=False,
    characterFidelityVerified=False,clothMotionVerified=False,newGlbOrFbxExported=False,published=False,
    additionalTripoCreditsConsumed=0,scriptSha256=sha(__file__))
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_material_integration.py')
print('FULL_CHARACTER_DRESS_TEXTURE_INTEGRATED',json.dumps(report),flush=True)
