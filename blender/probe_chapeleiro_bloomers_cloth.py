"""Actual static cloth experiment, never a gameplay or fidelity approval.

Solve only the existing bloomers midsurface against explicitly approximate
hidden pelvis/thigh volumes. Export the actual solved fabric and its bound
trims for an isolated own-photo review. Preserve every source mesh cage.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--frames',type=int,default=24)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=json.loads(Path(args.generation).read_text(encoding='utf-8'))
if sha(source['editableBlend'])!=source['editableBlendSha256']:
    raise ValueError('Changed editable source.')
out=Path(args.output)
if out.exists(): raise ValueError('Use a new experiment directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=source['editableBlend'])
scene=bpy.context.scene
scene.frame_start=1
scene.frame_end=args.frames
scene.render.fps=30
scene.frame_set(1)
fabric=bpy.data.objects['01 / bloomers / continuous waist and sewn crotch']
cage=bpy.data.objects[fabric['simulationCage']]
solver=next(m for m in cage.modifiers if m.type=='CLOTH')
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.type=='CLOTH' and modifier!=solver:
            modifier.show_viewport=False
            modifier.show_render=False
def raw_hash(obj):
    coords=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',coords)
    return hashlib.sha256(coords.tobytes()).hexdigest()
original={o.name:raw_hash(o) for o in scene.objects if o.type=='MESH'}
colliders=[]
for name,center,scale in [
    ('inferred pelvis',(0,0,.568),(.069,.044,.049)),
    ('inferred left thigh',(.04535,.002,.466),(.027,.030,.070)),
    ('inferred right thigh',(-.04535,.002,.466),(.027,.030,.070))]:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=center)
    obj=bpy.context.object
    obj.name='STATIC PROBE ONLY / '+name
    obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.hide_render=True
    obj.display_type='WIRE'
    obj.modifiers.new('Approximate static collision volume','COLLISION')
    obj.collision.thickness_outer=.0005
    obj.collision.thickness_inner=.0003
    obj.collision.cloth_friction=5
    colliders.append({'name':obj.name,'center':center,'radii':scale,
                      'bodyFidelityVerified':False,'exported':False})
solver.settings.quality=12
solver.settings.mass=.08
solver.settings.bending_stiffness=.18
solver.collision_settings.use_collision=True
solver.collision_settings.distance_min=.0005
solver.collision_settings.use_self_collision=True
solver.collision_settings.self_distance_min=.0004
solver.point_cache.frame_start=1
solver.point_cache.frame_end=args.frames
def solved_coords():
    evaluated=cage.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    coords=np.empty((len(mesh.vertices),3),np.float32)
    mesh.vertices.foreach_get('co',coords.ravel())
    evaluated.to_mesh_clear()
    if not np.isfinite(coords).all(): raise ValueError('Non-finite cloth solution.')
    return coords
start=solved_coords()
frames=[]
for frame in range(1,args.frames+1):
    tick=time.perf_counter()
    scene.frame_set(frame)
    coords=solved_coords()
    displacement=np.linalg.norm(coords-start,axis=1)
    if float(displacement.max())>.15:
        raise ValueError('Static cloth became unstable; reject this experiment.')
    frames.append({'frame':frame,'p95Displacement':float(np.percentile(displacement,95)),
                   'maxDisplacement':float(displacement.max()),
                   'seconds':time.perf_counter()-tick})
    print('ACTUAL_BLOOMERS_CLOTH_FRAME',json.dumps(frames[-1]),flush=True)
np.save(out/'solved_midsurface.npy',coords)
if any(raw_hash(bpy.data.objects[name])!=value for name,value in original.items()):
    raise ValueError('The experiment changed a source cage.')
pieces=[p for p in source['pieces'] if p['role'].startswith('foundation_bloomers')]
bpy.ops.object.select_all(action='DESELECT')
for piece in pieces: bpy.data.objects[piece['name']].select_set(True)
model=out/'bloomers_static_cloth_probe.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,
                          export_apply=True,export_yup=True,export_animations=False)
report={**source,'method':'actual_static_bloomers_cloth_probe_with_inferred_hidden_colliders',
        'model':str(model.resolve()),'modelSha256':sha(model),'pieces':pieces,
        'sourceGeneration':str(Path(args.generation).resolve()),'sourceGenerationSha256':sha(args.generation),
        'scope':'isolated bloomers experiment; the published foundation remains unchanged',
        'staticClothFrames':frames,'staticColliders':colliders,'allSourceCagesUnchanged':True,
        'solvedMidsurface':{'file':str((out/'solved_midsurface.npy').resolve()),
                            'sha256':sha(out/'solved_midsurface.npy')},
        'settings':{'mass':.08,'quality':12,'bendingStiffness':.18,'collisionDistance':.0005,
                     'selfCollisionDistance':.0004,'fps':30},
        'cacheBaked':False,'fidelityVerified':False,'motionVerified':False,
        'clothCollisionVerified':False,'gameplayVerified':False,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTUAL_BLOOMERS_STATIC_PROBE_EXPORTED',sha(model),flush=True)
