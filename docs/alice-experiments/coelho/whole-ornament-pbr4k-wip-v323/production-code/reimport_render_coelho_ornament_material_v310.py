"""Actual LOCAL material-format reimport and fixed-camera review, no publication."""
import bpy,numpy as np,json,hashlib,time,sys
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';sys.path.insert(0,str(R/'Tools/PythonDeps/mesh_repair'));from scipy.spatial import cKDTree
start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v301.json');export=read(O/'apron_ornament_material_format_payload_v308.json');assert export['sourceSHA256']==a['sha256'];source=R/a['path'];assert sha(source)==a['sha256'];original=[bpy.data.objects[r['object']] for r in a['newObjects']];scene=bpy.context.scene;cam=scene.camera;view=read(O/'apron_ornament_fixed_detail_render_audit_v277.json')['renders'][0];cam.location=view['cameraLocation'];cam.rotation_euler=(Vector(view['cameraTarget'])-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=view['orthoScale'];scene.cycles.samples=48;scene.render.resolution_x,scene.render.resolution_y=view['resolution'];scene.render.resolution_percentage=100;background={'Alice.Coelho.WholeCheckpoint181.'+x for x in ['apron','chain','cord','lace']}
def corners(ob):
    m=ob.data;P=np.asarray([ob.matrix_world@v.co for v in m.vertices],np.float64);uv=np.asarray([x.uv[:] for x in m.uv_layers.active.data],np.float64);ids=np.asarray([x.vertex_index for x in m.loops]);return np.column_stack((P[ids],uv))
reference={ob.name:corners(ob) for ob in original}
def render(label,objects):
    wanted={ob.name for ob in objects}|background
    for ob in scene.objects:
        if ob.type in {'MESH','CURVE'}:ob.hide_render=ob.name not in wanted
    out=E/('apron_ornament_material_'+label+'_reimport_v310.png');scene.render.filepath=str(out);bpy.ops.render.render(write_still=True);return dict(label=label,path=out.relative_to(R).as_posix(),sha256=sha(out),cameraLocation=view['cameraLocation'],cameraTarget=view['cameraTarget'],orthoScale=view['orthoScale'],resolution=view['resolution'])
renders=[render('source301',original)];formats=[]
for kind in ['glb','fbx']:
    file=R/export['files'][kind]['path'];assert sha(file)==export['files'][kind]['sha256'];old=set(bpy.data.objects)
    if kind=='glb':bpy.ops.import_scene.gltf(filepath=str(file))
    else:bpy.ops.import_scene.fbx(filepath=str(file),use_anim=False)
    added=[ob for ob in bpy.data.objects if ob not in old];meshes=[ob for ob in added if ob.type=='MESH'];assert len(meshes)==5;qa=[]
    for ob in meshes:
        matches=[name for name in reference if ob.name.startswith(name)];assert len(matches)==1,(ob.name,matches);name=matches[0];src=reference[name];got=corners(ob);forward=cKDTree(src).query(got,k=1)[0];reverse=cKDTree(got).query(src,k=1)[0];assert max(forward.max(),reverse.max())<4e-7,(kind,name,forward.max(),reverse.max());images=[]
        for mat in ob.data.materials:
            assert mat and mat.use_nodes;nodes=[n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
            for n in nodes:images.append(dict(material=mat.name,image=n.image.name,size=list(n.image.size),colorSpace=n.image.colorspace_settings.name))
            assert len(nodes)>=3,(kind,mat.name,len(nodes));assert all(list(n.image.size)==[4096,4096] for n in nodes)
        qa.append(dict(object=name,importedObject=ob.name,sourceCorners=len(src),importedCorners=len(got),maxPositionUVJointDistance=float(max(forward.max(),reverse.max())),bothWaySurfaceCornerCorrespondencePassed=True,images=images))
    renders.append(render(kind,meshes));formats.append(dict(format=kind,fileSHA256=sha(file),objects=qa))
    for ob in added:bpy.data.objects.remove(ob,do_unlink=True)
assert sha(source)==a['sha256'];report=dict(version='v310',sourceCandidate='v301',sourceSHA256=a['sha256'],diagnosticLocalOnlyNoWholeCharacterPublication=True,formats=formats,renders=renders,geometryAndUVJointCornerCorrespondencePassed=True,images4KBoundAfterBothActualReimports=True,requiresActualAppearanceInspection=True,rigPhysicsNotProven=True,notPublished=True,productionComplete=False,elapsedSeconds=time.time()-start);(O/'apron_ornament_material_actual_reimport_audit_v310.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENT_MATERIAL310_REIMPORT_TERMINAL_ACTUAL_IMAGE_REVIEW_REQUIRED',flush=True)
