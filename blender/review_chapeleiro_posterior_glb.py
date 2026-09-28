"""Reimport the actual complete checkpoint and review its back with hair hidden/restored."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix
p=argparse.ArgumentParser();p.add_argument('--export',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
e=json.loads(Path(a.export).read_text())
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
assert sha(e['model'])==e['modelSha256']
bpy.ops.wm.open_mainfile(filepath=e['sourceBlend']);s=bpy.context.scene
existing=set(bpy.data.objects)
for o in s.objects:
    if o.type not in ['CAMERA','LIGHT']:o.hide_render=True
bpy.ops.import_scene.gltf(filepath=e['model'])
added=[o for o in bpy.data.objects if o not in existing]
hair=[o for o in added if o.get('aliceRole')=='hair'];assert len(hair)==1
rigs=[o for o in added if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0]
if rig.animation_data:
    rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
s.frame_set(1);bpy.context.view_layer.update()
custom_shapes={bone.custom_shape for bone in rig.pose.bones if bone.custom_shape}
for shape in custom_shapes:shape.hide_render=True
meshes=[o for o in added if o.type=='MESH' and o not in custom_shapes];print('IMPORTED_MESH_COUNT',len(meshes),'declared',e['meshCount'],'bone widgets',len(custom_shapes),flush=True)
(out/'import_inventory.json').write_text(json.dumps([dict(name=o.name,type=o.type) for o in added],indent=2))
assert len(meshes)==e['meshCount']
report=dict(model=e['model'],modelSha256=e['modelSha256'],actualImportedMeshes=len(meshes),actualImportedBones=len(rig.data.bones),hairObjects=[o.name for o in hair],completeCharacter=True,defaultHairVisible=True,renders=[],physicsApproved=False,finalFidelityApproved=False)
bodice=next(o for o in meshes if 'finished posterior bodice' in o.name)
motion=[]
for track in rig.animation_data.nla_tracks:
    if not track.strips:continue
    track.mute=False;strip=track.strips[0];samples=[]
    for frame in np.linspace(strip.frame_start,strip.frame_end,3):
        s.frame_set(int(frame),subframe=float(frame)%1);dg=bpy.context.evaluated_depsgraph_get();ev=bodice.evaluated_get(dg);mesh=ev.to_mesh()
        points=np.array([ev.matrix_world@v.co for v in mesh.vertices],np.float32);assert np.isfinite(points).all();samples.append(points);ev.to_mesh_clear()
    motion.append(dict(track=track.name,sampledFrames=3,maximumVertexDisplacement=float(max(np.linalg.norm(p-samples[0],axis=1).max() for p in samples)),finite=True))
    track.mute=True
report['motionChecks']=motion
report['motionCheckScope']='Finite evaluated posterior vertices at three samples per imported track; not a collision or cloth-quality approval.'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
s.frame_set(1);bpy.context.view_layer.update()
cam=s.camera;s.render.resolution_x=s.render.resolution_y=900;s.cycles.samples=24;s.cycles.use_denoising=True
for name,target,span,d,show in [
    ('back_hair_hidden',(0,.025,.733),.26,(0,1,0),False),
    ('back_oblique_hair_hidden',(0,.025,.733),.26,(-.55,1,0),False),
    ('back_hair_restored',(0,.025,.73),.48,(0,1,0),True),
    ('complete_hair_restored',(0,0,.5),1.1,(0,-1,0),True)]:
    for o in hair:o.hide_render=not show
    target=Vector(target);cam.data.ortho_scale=span;cam.location=target+Vector(d).normalized()*1.2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    s.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    report['renders'].append(dict(name=name,file=s.render.filepath,sha256=sha(s.render.filepath)))
    (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
assert sha(e['model'])==e['modelSha256'];print('ACTUAL_POSTERIOR_GLB_REVIEW',json.dumps(report),flush=True)
