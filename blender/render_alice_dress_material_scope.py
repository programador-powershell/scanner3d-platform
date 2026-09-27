"""Render the actual assigned dress polygons using the direct-color audit settings."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy
from mathutils import Matrix
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);read=lambda s:json.loads(Path(s).read_text());sha=lambda s:hashlib.sha256(Path(s).read_bytes()).hexdigest()
g,b=read(a.generation),read(a.baseline)
assert sha(g['editableBlend'])==g['editableBlendSha256']
assert b['basecolorRenderSettings']['denoising'] is False
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);scene=bpy.context.scene
whole=bpy.data.objects[g['nativeWholeObject']];mesh=whole.data
slots={i for i,m in enumerate(mesh.materials) if m.name in g['newGarmentMaterials']}
selected={p.index for p in mesh.polygons if p.material_index in slots}
assert len(selected)==g['modifiedMaterialPolygons']
rig=next(o for o in scene.objects if o.type=='ARMATURE')
rig.animation_data.action=None
for track in rig.animation_data.nla_tracks:track.mute=True
rig.data.pose_position='REST'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for collection in bpy.data.collections:collection.hide_viewport=collection.hide_render=False
for obj in scene.objects:
    obj.hide_viewport=obj not in (whole,rig);obj.hide_render=obj!=whole;obj.hide_set(obj not in (whole,rig))
    if obj!=whole:
        for modifier in obj.modifiers:modifier.show_viewport=modifier.show_render=False
scene.frame_set(1);bpy.context.view_layer.update()
mesh.materials.clear()
for name,color in [('protected original material',(0,0,0,1)),('actual new garment albedo',(1,1,1,1))]:
    m=bpy.data.materials.new(name);m.use_nodes=True;nodes=m.node_tree.nodes
    emission=nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=color
    m.node_tree.links.new(emission.outputs[0],next(n for n in nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface'])
    mesh.materials.append(m)
for polygon in mesh.polygons:polygon.material_index=int(polygon.index in selected)
data=bpy.data.cameras.new('Actual dress material audit');data.type='ORTHO';data.ortho_scale=b['orthoScale'];data.clip_start=.001
camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera);scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4
scene.cycles.use_denoising=False;scene.cycles.use_adaptive_sampling=False;scene.cycles.seed=0;scene.cycles.use_animated_seed=False
scene.render.resolution_x,scene.render.resolution_y=b['resolution'];scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True;scene.view_settings.view_transform='Standard'
renders=[]
for row in b['renders']:
    if row['kind']!='basecolor':continue
    camera.matrix_world=Matrix(row['cameraWorldMatrix']);scene.render.filepath=str(out/(row['view']+'_dress_mask.png'))
    bpy.ops.render.render(write_still=True)
    renders.append(dict(view=row['view'],file=scene.render.filepath,sha256=sha(scene.render.filepath)))
report=dict(generation=a.generation,sourceBlendSha256=g['editableBlendSha256'],baselineFile=a.baseline,baselineSha256=sha(a.baseline),selectedTriangles=len(selected),renders=renders,
    maskDefinition='White equals the actual integrated garment material, black equals preserved original material; original geometry is intact.',basecolorRenderSettings=b['basecolorRenderSettings'],sourceUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],selectionApproved=False,published=False)
(out/'scope_review.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_material_scope.py')
print('ACTUAL_DRESS_MATERIAL_MASK_COMPLETE',len(selected),flush=True)
