"""Actual front-corner411 geometry comparison against whole377 under identical constant materials."""
import bpy,json,hashlib,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';start=time.time()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'apron_ornament_front_corner_authoring_audit_v411.json');assert read(O/'apron_ornament_component_audit_v412.json')['totalInwardComponents']==0;contact=read(O/'apron_ornament_triangle_contact_audit_v413.json');assert contact['totalWholeSurfaceSATTrianglePairs']==contact['totalSelfSATTrianglePairs']==contact['totalBetweenOrnamentsSATTrianglePairs']==0;source=R/a['path'];assert sha(source)==a['sha256'];scene=bpy.context.scene;scene.cycles.samples=48;cam=scene.camera
gold=bpy.data.materials.new('DIAGNOSTIC_Gold414');blue=bpy.data.materials.new('DIAGNOSTIC_Blue414')
for mat,col,metal,rough in [(gold,(.60,.335,.115,1),1,.25),(blue,(.012,.048,.095,1),.45,.18)]:
 mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=col;bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough;bs.inputs['Coat Weight'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.5
names={r['object'] for r in a['newObjects']};wanted=names|{'Alice.Coelho.WholeCheckpoint377.'+r for r in ['apron','chain','cord','lace']}
for ob in scene.objects:
 if ob.type in {'MESH','CURVE'}:ob.hide_render=ob.name not in wanted
for name in names:bpy.data.objects[name].data.materials[0]=gold;bpy.data.objects[name].data.materials[1]=blue
views=read(O/'apron_ornament_full_reference_render_audit_v271.json')['renders'];fixed=read(O/'apron_ornament_fixed_detail_render_audit_v277.json')['renders'][0];records=[]
for view in views:
 if view['view']=='inner_left_detail':view=fixed
 cam.location=view['cameraLocation'];cam.rotation_euler=(Vector(view['cameraTarget'])-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=view['orthoScale'];scene.render.resolution_x,scene.render.resolution_y=view['resolution'];scene.render.resolution_percentage=100
 out=E/('apron_ornaments_'+view['view']+'_compact_blue_review_v414.png');scene.render.filepath=str(out);bpy.ops.render.render(write_still=True);records.append(dict(view,path=out.relative_to(R).as_posix(),sha256=sha(out),blueMetallic=.45,blueRoughness=.18));print('COMPACT414_RENDERED',view['view'],flush=True)
view=fixed;baselineNames={'Alice.Coelho.WholeCheckpoint377.ornament_'+row['id'] for row in a['newObjects']};wantedBaseline=baselineNames|{'Alice.Coelho.WholeCheckpoint377.'+r for r in ['apron','chain','cord','lace']}
for ob in scene.objects:
 if ob.type in {'MESH','CURVE'}:ob.hide_render=ob.name not in wantedBaseline
for name in baselineNames:bpy.data.objects[name].data.materials[0]=gold;bpy.data.objects[name].data.materials[1]=blue
cam.location=view['cameraLocation'];cam.rotation_euler=(Vector(view['cameraTarget'])-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=view['orthoScale'];scene.render.resolution_x,scene.render.resolution_y=view['resolution'];out=E/'apron_ornaments_inner_left_detail_source377_same_material_v414.png';scene.render.filepath=str(out);bpy.ops.render.render(write_still=True);records.append(dict(view,path=out.relative_to(R).as_posix(),sha256=sha(out),blueMetallic=.45,blueRoughness=.18,comparisonBaseline=True,sourceWhole='v377',sameCamerasLightsAndConstantMaterials=True))
assert sha(source)==a['sha256'];(O/'apron_ornament_compact_reference_review_v414.json').write_text(json.dumps(dict(version='v414',sourceCandidate='v411',sourceSHA256=a['sha256'],records=records,allViewsSameCameraAsPrior271And277=True,onlyNewCastGeometryBeforeAfterSameConstantMaterialsAndLight=True,source377BaselineUsesItsExisting370Ornaments=True,portableOpaqueMixedBlueHypothesis=True,opticalGemstoneRefractionNotModeled=True,readOnlyNoSaveOrExport=True,ownUVPBRNotBaked=True,requiresActualReferenceAndImageInspection=True,productionComplete=False,elapsedSeconds=time.time()-start),indent=2),encoding='utf-8');print('COMPACT414_MULTIVIEW_TERMINAL_ACTUAL_REVIEW_REQUIRED',flush=True)
