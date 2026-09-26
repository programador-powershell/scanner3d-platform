"""Inspect physical holes and probe cloth-carrier translation without saving edits."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
record=json.loads(Path(args.generation).read_text(encoding='utf-8'))
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if digest(record['editableBlend'])!=record['editableBlendSha256']:
    raise ValueError('Editable checkpoint changed.')
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
scene=bpy.context.scene
scene.frame_set(1)
def coords(obj):
    bpy.context.view_layer.update()
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    vertices=np.asarray([evaluated.matrix_world@v.co for v in mesh.vertices])
    evaluated.to_mesh_clear()
    return vertices
def holes(mesh):
    parent=list(range(len(mesh.vertices)))
    def find(v):
        while parent[v]!=v:
            parent[v]=parent[parent[v]]
            v=parent[v]
        return v
    for e in mesh.edges:
        a,b=map(find,e.vertices)
        parent[a]=b
    components=len({find(i) for i in range(len(parent))})
    euler=len(mesh.vertices)-len(mesh.edges)+len(mesh.polygons)
    return {'components':components,'eulerCharacteristic':euler,
            'openSurfaceHoles':components-euler}
objects={o.name:o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')}
apertures=[]
trace=json.loads(Path(record['laceTrace']).read_text(encoding='utf-8'))
for obj in objects.values():
    if obj.get('opaqueGeometryApertures'):
        result=holes(obj.data)
        result.update(mesh=obj.name,minimumExpected=obj['traceHolesPerRepeat']*obj['traceRepeats']*.5,
                      textureAlphaHolesUsed=False)
        if result['openSurfaceHoles']<result['minimumExpected']:
            raise ValueError('Tracing did not produce the expected actual apertures: '+str(result))
        tile=next(t for t in trace['tiles'] if t['name'] in obj.name)
        mask=bpy.data.images.load(tile['mask'],check_existing=True)
        pixels=np.empty(len(mask.pixels),dtype=np.float32)
        mask.pixels.foreach_get(pixels)
        pixels=pixels.reshape(tile['height'],tile['width'],4)
        uv=obj.data.uv_layers['PhotoLaceUV']
        hits=[]
        for poly in obj.data.polygons:
            coordinate=np.mean([uv.data[i].uv[:] for i in poly.loop_indices],axis=0)
            x=int(round(float(coordinate[0])*(tile['width']-1)))
            y=int(round(float(coordinate[1])*(tile['height']-1)))
            hits.append(pixels[max(0,min(tile['height']-1,y)),max(0,min(tile['width']-1,x)),0]>.5)
        result['surfaceCentroidsOnPhotoThreadMask']=float(np.mean(hits))
        if result['surfaceCentroidsOnPhotoThreadMask']<.8:
            raise ValueError('Lace texture UV does not align with traced material: '+str(result))
        apertures.append(result)
        print('FOUNDATION_APERTURES_VERIFIED',json.dumps(result),flush=True)
probes=[]
for name in ['01 / long ivory gathered petticoat','01 / black petticoat continuous waist support',
             '01 / ivory fitted boned corset / pointed front']:
    support=objects[name]
    followers=[o for o in objects.values() if o.get('actualClothCarrier')==name]
    follower_names={o.name for o in followers}
    followers += [o for o in objects.values() if o.get('carrier') in follower_names]
    before={o.name:coords(o) for o in followers}
    location=support.location.copy()
    support.location.x+=.006
    bpy.context.view_layer.update()
    for obj in followers:
        after=coords(obj)
        delta=after-before[obj.name]
        error=np.linalg.norm(delta-np.asarray([.006,0,0]),axis=1)
        probes.append({'support':name,'follower':obj.name,'measuredVertices':len(delta),
                       'medianDelta':np.median(delta,axis=0).tolist(),
                       'p95TranslationError':float(np.percentile(error,95)),
                       'maximumTranslationError':float(error.max()),
                       'frame':1,'clothAnimationVerified':False})
        if np.percentile(error,95)>.001:
            raise ValueError('Carrier did not follow the test translation: '+str(probes[-1]))
    print('FOUNDATION_CARRIER_TRANSLATION_VERIFIED',name,len(followers),flush=True)
    support.location=location
    bpy.context.view_layer.update()
if digest(record['editableBlend'])!=record['editableBlendSha256']:
    raise ValueError('Read-only audit unexpectedly changed the checkpoint file.')
report={'stage':'alice_chapeleiro_stage_01','editableBlendSha256':record['editableBlendSha256'],
        'actualApertureAudit':apertures,'carrierTranslationProbe':probes,
        'savedModelUnchanged':True,'rigPresent':False,'motionVerified':False,
        'clothCollisionVerified':False,'limitation':'Frame-1 attachment probe only; no gameplay or dynamic simulation approval.'}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_ATTACHMENT_AUDIT',json.dumps(report),flush=True)
