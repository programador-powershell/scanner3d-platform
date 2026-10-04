"""Independent complete dressed source reopens and actual full-view renders."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';start=time.time();a=json.loads((O/'apron_ornament_whole_integration_audit_v421.json').read_text(encoding='utf-8-sig'));source=R/a['path']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)==a['sha256'];scene=bpy.context.scene
for name,expected in a['wholeCopySignatures'].items():
    ob=bpy.data.objects[name];m=ob.data;actual=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([x.uv[:] for x in u.data],np.float32).tobytes()).hexdigest() for u in m.uv_layers],keys={} if not m.shape_keys else {k.name:hashlib.sha256(np.asarray([v.co[:] for v in k.data],np.float32).tobytes()).hexdigest() for k in m.shape_keys.key_blocks},materials=[mat.name for mat in m.materials],matrixWorld=[list(row) for row in ob.matrix_world]);assert actual==expected and not ob.hide_render
assert not bpy.data.libraries
for im in bpy.data.images:
    if im.type=='IMAGE' and im.size[0]:assert im.packed_file
cam=scene.camera;scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;P=np.asarray([v.co[:] for v in bpy.data.objects['Alice.Coelho.WholeCheckpoint421.character'].data.vertices]);target=(P.min(0)+P.max(0))/2;target[1]=0;records=[]
for view,direction in [('front',(0,-4,0)),('threequarter',(2,-4,0)),('back',(0,4,0)),('left_profile',(-4,0,0)),('right_profile',(4,0,0))]:
    cam.location=target+np.asarray(direction);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=2.05;out=E/('whole_coelho_'+view+'_ornament_wip_v422.png');scene.render.filepath=str(out);bpy.ops.render.render(write_still=True);records.append(dict(view=view,path=out.relative_to(R).as_posix(),sha256=sha(out),target=target.tolist(),orthoScale=2.05));print('WHOLE422_RENDERED',view,flush=True)
assert sha(source)==a['sha256'];report=dict(version='v422',sourceCandidate='v421',sourceSHA256=a['sha256'],allTenCompleteMeshSignaturesExactlyVerified=True,independentSavedWholeReopen=True,portablePackedImages=True,records=records,requiresActualImageInspection=True,readOnlyNoSaveOrExport=True,rigged=False,physicsVerified=False,productionComplete=False,elapsedSeconds=time.time()-start);(O/'apron_ornament_whole_reopen_audit_v422.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE422_REOPEN_RENDER_TERMINAL_IMAGE_REVIEW_REQUIRED',flush=True)
