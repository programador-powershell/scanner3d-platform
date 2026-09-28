"""Reimport the whole experimental GLB and inspect actual UV-mapped fibers."""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

p=argparse.ArgumentParser()
p.add_argument('--export',required=True)
p.add_argument('--output',required=True)
p.add_argument('--hair-only',action='store_true')
p.add_argument('--views',default='front,left,back,right')
p.add_argument('--hair-roughness',type=float)
p.add_argument('--hair-specular',type=float)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
e=json.loads(Path(a.export).read_text(encoding='utf-8'))
def sha(file):
    h=hashlib.sha256()
    with open(file,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
assert sha(e['model'])==e['modelSha256']
bpy.ops.wm.open_mainfile(filepath=e['sourceBlend'])
s=bpy.context.scene
old=set(bpy.data.objects)
for obj in s.objects:
    if obj.type not in ('CAMERA','LIGHT'):obj.hide_render=True
bpy.ops.import_scene.gltf(filepath=e['model'])
added=[o for o in bpy.data.objects if o not in old]
hair=[o for o in added if o.get('aliceRole')=='hair']
assert len(hair)==e['hairRibbonMeshCount']
if a.hair_roughness is not None or a.hair_specular is not None:
    assert a.hair_roughness is None or 0<=a.hair_roughness<=1
    assert a.hair_specular is None or 0<=a.hair_specular<=1
    for material in {m for obj in hair for m in obj.data.materials if m}:
        bs=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
        if bs:
            if a.hair_roughness is not None:bs.inputs['Roughness'].default_value=a.hair_roughness
            if a.hair_specular is not None and 'Specular IOR Level' in bs.inputs:
                bs.inputs['Specular IOR Level'].default_value=a.hair_specular
if a.hair_only:
    for obj in added:
        if obj.type=='MESH' and obj not in hair:obj.hide_render=True
rig=next(o for o in added if o.type=='ARMATURE')
if rig.animation_data:
    rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for bone in rig.pose.bones:
    if bone.custom_shape:bone.custom_shape.hide_render=True
s.frame_set(1)
bpy.context.view_layer.update()
s.render.resolution_x=s.render.resolution_y=768
s.cycles.samples=24
s.cycles.use_denoising=True
cam=s.camera
cam.data.ortho_scale=.4
target=Vector((0,.025,.808))
directions={'front':(0,-1,0),'left':(-1,0,0),'back':(0,1,0),'right':(1,0,0)}
for view in a.views.split(','):
    direction=directions[view]
    cam.location=target+Vector(direction)*1.2
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    s.render.filepath=str(out/(view+'.png'))
    bpy.ops.render.render(write_still=True)
(out/'review.json').write_text(json.dumps(dict(export=a.export,
    modelSha256=e['modelSha256'],hairObjects=len(hair),
    characterReimported=True,hairOnly=a.hair_only,hairRoughness=a.hair_roughness,
    hairSpecular=a.hair_specular,visibilityProjectionApproved=False,
    styleFidelityApproved=False),indent=2)+'\n',encoding='utf-8')
