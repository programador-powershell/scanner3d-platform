"""Add an independently unwrapped garment UV to the complete authoring master.

The original UV, geometry, weights, rig, actions and original materials remain
unchanged. Only reviewed visible garment polygons receive the new unwrap.
"""
import argparse, hashlib, json, math, shutil, struct, sys
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True)
p.add_argument('--approval',required=True)
p.add_argument('--paints',required=True)
p.add_argument('--atlas-layout')
p.add_argument('--output',required=True)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
g, approval, paint = read(a.generation), read(a.approval), read(a.paints)
assert approval['safeForConservativeProjection']
assert sha(approval['scopeFile']) == approval['scopeSha256']
scope = read(approval['scopeFile'])
assert scope['sourceBlendSha256'] == g['editableBlendSha256'] == sha(g['editableBlend'])
assert sha(scope['dataFile']) == scope['dataSha256']
assert sha(scope['baselineFile']) == scope['baselineSha256']
baseline = read(scope['baselineFile'])
assert sha(baseline['geometryFile']) == baseline['geometrySha256']
for row in paint['sources']: assert sha(row['image']) == row['sha256']
geometry = np.load(baseline['geometryFile'])
mask = np.load(scope['dataFile'])
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
whole = bpy.data.objects[baseline['nativeWholeObject']]
mesh = whole.data
old_uv = mesh.uv_layers.active
old_uv_name = old_uv.name
assert 'DressUV4K' not in mesh.uv_layers
uv_before = np.array([loop.uv[:] for loop in old_uv.data],np.float32)
assert np.array_equal(uv_before,geometry['uv'])
coordinates_before = np.array([vertex.co[:] for vertex in mesh.vertices],np.float32)
assert np.array_equal(coordinates_before,geometry['vertices'])

def weights_hash():
    h=hashlib.sha256()
    for group in whole.vertex_groups: h.update(group.name.encode('utf-8')+b'\0')
    for vertex in mesh.vertices:
        for group in vertex.groups: h.update(struct.pack('<IIf',vertex.index,group.group,group.weight))
    return h.hexdigest()

def rig_hash():
    h=hashlib.sha256()
    for rig in sorted((o for o in bpy.data.objects if o.type=='ARMATURE'),key=lambda o:o.name):
        for bone in rig.data.bones:
            h.update((bone.name+'|'+(bone.parent.name if bone.parent else '')).encode())
            h.update(np.array(bone.matrix_local,dtype=np.float32).tobytes())
    return h.hexdigest()

weight_before, bones_before = weights_hash(), rig_hash()
actions_before = [(action.name,action.session_uid) for action in bpy.data.actions]
original_selection=[obj for obj in bpy.context.selected_objects]
original_active=bpy.context.view_layer.objects.active
original_select_mode=tuple(bpy.context.tool_settings.mesh_select_mode)
polygon_selection=np.array([polygon.select for polygon in mesh.polygons],bool)
vertex_selection=np.array([vertex.select for vertex in mesh.vertices],bool)
edge_selection=np.array([edge.select for edge in mesh.edges],bool)
states = [(obj,obj.hide_viewport,obj.hide_render,obj.hide_get(),
           [(m,m.show_viewport,m.show_render) for m in obj.modifiers]) for obj in bpy.data.objects]
collections = [(c,c.hide_viewport,c.hide_render) for c in bpy.data.collections]
for c,_,_ in collections: c.hide_viewport=c.hide_render=False
for obj,_,_,_,modifiers in states:
    obj.hide_set(False);obj.hide_viewport=False
    for m,_,_ in modifiers:m.show_viewport=False;m.show_render=False
bpy.ops.object.select_all(action='DESELECT')
whole.select_set(True);bpy.context.view_layer.objects.active=whole
new_uv=mesh.uv_layers.new(name='DressUV4K',do_init=True)
mesh.uv_layers.active=new_uv
selected=set(mask['polygon_indices'].tolist())
if a.atlas_layout:
    layout=read(a.atlas_layout)
    assert sha(layout['coordinateFile'])==layout['coordinateFileSha256']
    atlas_coordinates=np.load(layout['coordinateFile'])
    assert np.array_equal(atlas_coordinates['original_vertices'],geometry['vertices'])
    assert np.array_equal(atlas_coordinates['original_triangles'],geometry['triangles'])
    assert np.array_equal(atlas_coordinates['original_triangle_loops'],geometry['triangle_loops'])
    assert np.array_equal(atlas_coordinates['selected_triangle_indices'],mask['triangle_indices'])
    new_uv.data.foreach_set('uv',atlas_coordinates['dress_uv'].ravel())
else:
    for polygon in mesh.polygons:polygon.select=polygon.index in selected
    for vertex in mesh.vertices:vertex.select=False
    for edge in mesh.edges:edge.select=False
    bpy.context.tool_settings.mesh_select_mode=(False,False,True)
    bpy.ops.object.mode_set(mode='EDIT')
    result=bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.001,
                                  area_weight=0.,correct_aspect=False,scale_to_bounds=True)
    assert 'FINISHED' in result
    bpy.ops.object.mode_set(mode='OBJECT')
mesh=whole.data
# Layer collections can reallocate their backing memory when a layer is added
# and when Edit Mode ends. Reacquire RNA references before reading UV data.
old_uv=mesh.uv_layers[old_uv_name]
new_uv=mesh.uv_layers['DressUV4K']
new_coordinates=np.array([loop.uv[:] for loop in new_uv.data],np.float32)
selected_triangles=mask['triangle_indices']
loops=geometry['triangle_loops'][selected_triangles]
tri_uv=new_coordinates[loops]
e1,e2=tri_uv[:,1]-tri_uv[:,0],tri_uv[:,2]-tri_uv[:,0]
uv_area=float(np.abs(e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]).sum()/2)
assert np.isfinite(tri_uv).all() and uv_area>.05
assert np.array_equal(uv_before,np.array([loop.uv[:] for loop in old_uv.data],np.float32))
assert np.array_equal(coordinates_before,np.array([v.co[:] for v in mesh.vertices],np.float32))
assert weights_hash()==weight_before and rig_hash()==bones_before
assert actions_before==[(action.name,action.session_uid) for action in bpy.data.actions]
np.savez_compressed(out/'projection_uv_geometry.npz',world_points=geometry['world_points'],
    vertices=geometry['vertices'],triangles=geometry['triangles'],triangle_loops=geometry['triangle_loops'],
    polygon_indices=geometry['polygon_indices'],original_uv=geometry['uv'],dress_uv=new_coordinates,
    selected_triangle_indices=selected_triangles,visible_camera_masks=mask['visible_camera_masks'])
baseimage=next(node.image for material in mesh.materials for node in material.node_tree.nodes
               if node.type=='TEX_IMAGE' and node.image and 'basecolor' in node.image.name.lower())
assert baseimage.packed_file
# Preserve encoded original pixels verbatim; avoid changing image colorspace
# or applying a display transform while extracting the albedo source.
(out/'source_basecolor_original.bin').write_bytes(baseimage.packed_file.data)
mesh.uv_layers.active=old_uv
bpy.context.tool_settings.mesh_select_mode=original_select_mode
for polygon,value in zip(mesh.polygons,polygon_selection):polygon.select=bool(value)
for vertex,value in zip(mesh.vertices,vertex_selection):vertex.select=bool(value)
for edge,value in zip(mesh.edges,edge_selection):edge.select=bool(value)
bpy.ops.object.select_all(action='DESELECT')
for obj in original_selection:obj.select_set(True)
bpy.context.view_layer.objects.active=original_active
for c,viewport,render in collections:c.hide_viewport=viewport;c.hide_render=render
for obj,viewport,render,hide,modifiers in states:
    obj.hide_viewport=viewport;obj.hide_render=render;obj.hide_set(hide)
    for m,show_viewport,show_render in modifiers:m.show_viewport=show_viewport;m.show_render=show_render
blend=out/'chapeleiro_full_dress_uv4k_prepared.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
report=dict(parentGeneration=str(Path(a.generation).resolve()),parentEditableSha256=g['editableBlendSha256'],
    atlasLayout=a.atlas_layout,atlasLayoutSha256=sha(a.atlas_layout) if a.atlas_layout else None,
    editableBlend=str(blend),editableBlendSha256=sha(blend),editableBytes=blend.stat().st_size,
    approvalFile=str(Path(a.approval).resolve()),approvalSha256=sha(a.approval),
    sourceScopeFile=approval['scopeFile'],sourceScopeSha256=approval['scopeSha256'],
    paintSources=str(Path(a.paints).resolve()),paintSourcesSha256=sha(a.paints),
    baselineFile=scope['baselineFile'],baselineSha256=scope['baselineSha256'],
    projectionGeometry=str(out/'projection_uv_geometry.npz'),projectionGeometrySha256=sha(out/'projection_uv_geometry.npz'),
    sourceBasecolor=str(out/'source_basecolor_original.bin'),sourceBasecolorSha256=sha(out/'source_basecolor_original.bin'),
    nativeWholeObject=whole.name,newUvLayer='DressUV4K',originalUvLayer=old_uv.name,
    selectedTriangles=len(selected_triangles),selectedPolygons=len(selected),uvArea=uv_area,
    geometryUnchanged=True,originalUvUnchanged=True,weightsUnchanged=True,rigUnchanged=True,
    weightHash=weight_before,rigHash=bones_before,actionCount=len(actions_before),
    allActionsPreserved=True,allInteriorAuthoringPreserved=True,sourceBlendUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],
    textureBakePending=True,fullDressCoverageApproved=False,characterFidelityVerified=False,
    newGlbOrFbxExported=False,published=False,additionalTripoCreditsConsumed=0,scriptSha256=sha(__file__))
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_uv_preparation.py')
print('FULL_CHARACTER_DRESS_UV_PREPARED',json.dumps(report),flush=True)
