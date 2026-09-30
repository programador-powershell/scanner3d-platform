"""Render reimported whole GLB under the authoring scene's fixed cameras/lights."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--export',required=True);p.add_argument('--output',required=True)
p.add_argument('--views',nargs='+',choices=['front','left','right','back'],default=['front','left','back'])
p.add_argument('--full-body',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
g=json.loads(Path(a.generation).read_text());e=json.loads(Path(a.export).read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(g['editableBlend'])==g['editableBlendSha256'] and sha(e['model'])==e['modelSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);s=bpy.context.scene;s.frame_set(1)
original=set(s.objects)
for o in original:
    if o.type in {'MESH','CURVES','CURVE','ARMATURE'}:o.hide_render=True
bpy.ops.import_scene.gltf(filepath=e['model'])
imported=[o for o in s.objects if o not in original]
for o in imported:o.hide_render=False
hair=[o for o in imported if o.get('hairFiberCount')]
assert len(hair)==e['hairRibbonMeshCount']
assert sum(o['hairFiberCount'] for o in hair)==e['exportedFiberCount']
cam=s.camera;target=Vector((0,.025,.55 if a.full_body else .808));cam.data.ortho_scale=1.3 if a.full_body else .4
s.render.resolution_x=s.render.resolution_y=768;s.cycles.samples=32;s.cycles.use_denoising=True
directions={'front':(0,-1,0),'left':(-1,0,0),'right':(1,0,0),'back':(0,1,0)}
for view in a.views:
    cam.location=target+Vector(directions[view])*(2 if a.full_body else 1.2)
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    s.render.filepath=str(out/(view+'.png'))
    bpy.ops.render.render(write_still=True)
    print('REIMPORTED_WHOLE_GLB_RENDER',view,flush=True)
report={'source':a.generation,'export':a.export,'modelSha256':e['modelSha256'],
        'importedObjects':len(imported),'importedHairChunks':len(hair),
        'importedFiberCount':sum(o['hairFiberCount'] for o in hair),
        'views':a.views,'fullBodyFraming':a.full_body,'sameCameraAndLightsAsAuthoring':True,
        'renderOnlyNoBlendSaved':True,'appearanceApproved':False}
(out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
