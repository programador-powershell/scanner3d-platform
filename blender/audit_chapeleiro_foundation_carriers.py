"""Inspect physical holes and probe cloth-carrier translation without saving edits."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
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
    local=np.empty((len(mesh.vertices),3),dtype=np.float32)
    mesh.vertices.foreach_get('co',local.ravel())
    matrix=np.asarray(evaluated.matrix_world)
    vertices=local@matrix[:3,:3].T+matrix[:3,3]
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
def boundary_loops(mesh):
    counts=Counter(tuple(sorted((p.vertices[i],p.vertices[(i+1)%len(p.vertices)])))
                   for p in mesh.polygons for i in range(len(p.vertices)))
    graph=defaultdict(list)
    for (a,b),count in counts.items():
        if count==1:
            graph[a].append(b)
            graph[b].append(a)
    if any(len(neighbors)!=2 for neighbors in graph.values()):
        raise ValueError('A blouse boundary contains an open or branched seam.')
    remaining,loops=set(graph),[]
    while remaining:
        start=min(remaining)
        indices,previous,current=[],None,start
        while current not in indices:
            indices.append(current)
            previous,current=current,next(i for i in graph[current] if i!=previous)
        if current!=start:
            raise ValueError('The blouse seam is not a closed boundary.')
        remaining.difference_update(indices)
        loops.append(np.asarray([mesh.vertices[i].co[:] for i in indices]))
    return loops
def distance_to_seam(points,seam):
    a,b=seam,np.roll(seam,-1,axis=0)
    edges=b-a
    delta=points[:,None,:]-a[None,:,:]
    t=np.clip(np.sum(delta*edges[None,:,:],axis=2)/np.sum(edges*edges,axis=1),0,1)
    return np.min(np.linalg.norm(delta-t[:,:,None]*edges[None,:,:],axis=2),axis=1)
blouse_seams=[]
solver_partition=[]
blouses=[o for o in objects.values() if o.get('role')=='foundation_gathered_blouse']
if blouses:
    if len(blouses)!=1:
        raise ValueError('Expected one actual blouse, not unrelated replacement copies.')
    blouse=blouses[0]
    loops=boundary_loops(blouse.data)
    if len(loops)!=4:
        raise ValueError('The blouse must have a neck, waist and two actual open armholes.')
    armholes=[loop for loop in loops if abs(loop[:,0].mean())>.06]
    if len(armholes)!=2:
        raise ValueError('Actual side armholes are missing.')
    neck=max((loop for loop in loops if abs(loop[:,0].mean())<.06),key=lambda loop:loop[:,2].mean())
    def check_seam(obj,source,name):
        candidates=boundary_loops(obj.data)
        distances=[distance_to_seam(loop,source) for loop in candidates]
        chosen=int(np.argmin([d.max() for d in distances]))
        result={'name':name,'object':obj.name,'measuredRootVertices':len(candidates[chosen]),
                'maximumRootGap':float(distances[chosen].max()),'measuredFromActualCages':True}
        if result['maximumRootGap']>1e-6:
            raise ValueError('The actual sewn blouse root is detached: '+str(result))
        blouse_seams.append(result)
        return candidates[1-chosen] if len(candidates)==2 else None
    sleeves=[o for o in objects.values() if o.get('role')=='foundation_puffed_sleeve']
    if len(sleeves)!=2:
        raise ValueError('Both puff sleeves must be present.')
    for sleeve in sleeves:
        side=1 if np.mean([v.co.x for v in sleeve.data.vertices])>0 else -1
        armhole=next(loop for loop in armholes if np.sign(loop[:,0].mean())==side)
        cuff_seam=check_seam(sleeve,armhole,'armhole')
        cuffs=[o for o in objects.values() if o.parent==sleeve and o.get('role')=='foundation_blouse_cuff']
        if len(cuffs)!=1:
            raise ValueError('A sleeve is missing its sewn cuff.')
        check_seam(cuffs[0],cuff_seam,'cuff')
    neck_frill=next(o for o in objects.values() if o.get('role')=='foundation_neckline_frill')
    check_seam(neck_frill,neck,'neckline')
    print('FOUNDATION_BLOUSE_SEAMS_VERIFIED',json.dumps(blouse_seams),flush=True)
    for entry in record.get('simulationCages',[]):
        cage=bpy.data.objects[entry['name']]
        visible=objects[entry['visibleFabric']]
        if (not cage.hide_render or cage.data!=visible.data
                or sum(m.type=='CLOTH' for m in cage.modifiers)!=1
                or any(m.type=='CLOTH' for m in visible.modifiers)
                or not any(m.type=='SURFACE_DEFORM' and m.target==cage and m.is_bound
                           for m in visible.modifiers)):
            raise ValueError('A blouse fabric has a duplicated or disconnected simulation solver.')
        evaluated=visible.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles()
        uv=mesh.uv_layers.get('UVMap')
        if not uv:
            raise ValueError('The actual blouse receiver has no evaluated UV map.')
        coords_uv=np.asarray([v.uv[:] for v in uv.data])
        indices=np.asarray([t.loops[:] for t in mesh.loop_triangles])
        a,b,c=coords_uv[indices[:,0]],coords_uv[indices[:,1]],coords_uv[indices[:,2]]
        ab,ac=b-a,c-a
        areas=np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5
        fraction=float(np.mean(areas>1e-12))
        evaluated.to_mesh_clear()
        if not np.isfinite(coords_uv).all() or fraction<.95:
            raise ValueError('The blouse UV unwrap contains excessive degenerate triangles.')
        solver_partition.append({'visibleFabric':visible.name,'simulationCage':cage.name,
                                  'singleSolver':True,'uvNonDegenerateTriangleFraction':fraction,
                                  'dynamicSimulationVerified':False})
    if len(solver_partition)!=3:
        raise ValueError('The torso and both sleeves need exactly three simulation carriers.')
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
roots=[o for o in objects.values() if o.parent is None or o.parent.name not in objects]
def descendants(support):
    family={support.name}
    while True:
        extended=family|{o.name for o in objects.values() if o.parent and o.parent.name in family}
        if extended==family:
            break
        family=extended
    return [o for o in objects.values() if o.name in family and o!=support]
for obj in objects.values():
    if obj not in roots:
        carrier=obj.get('actualClothCarrier') or obj.get('carrier')
        if not carrier or obj.parent.name!=carrier:
            raise ValueError('A fabric/detail follower has no actual declared carrier: '+obj.name)
probes=[]
for support in roots:
    name=support.name
    followers=descendants(support)
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
covered={p['follower'] for p in probes}
expected=set(objects)-{o.name for o in roots}
if covered!=expected:
    raise ValueError('The hierarchy probe omitted actual sewn followers.')
report={'stage':'alice_chapeleiro_stage_01','editableBlendSha256':record['editableBlendSha256'],
        'actualApertureAudit':apertures,'carrierTranslationProbe':probes,
        'actualBlouseSeamAudit':blouse_seams,
        'blouseSolverPartitionAudit':solver_partition,
        'actualInternalObjects':len(objects),'attachmentRoots':[o.name for o in roots],
        'verifiedFollowers':len(covered),'allActualFollowersCovered':True,
        'savedModelUnchanged':True,'rigPresent':False,'motionVerified':False,
        'clothCollisionVerified':False,'limitation':'Frame-1 attachment probe only; no gameplay or dynamic simulation approval.'}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_ATTACHMENT_AUDIT',json.dumps({'actualInternalObjects':len(objects),
      'verifiedFollowers':len(covered),'allActualFollowersCovered':True}),flush=True)
