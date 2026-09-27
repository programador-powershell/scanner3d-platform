"""Author closed yarns on a folded lace ground from the own photo's bright ridges.

Photographic shadow regions never become large geometric cut-outs. The fine
ground, round yarn section, unseen repeats and scale are interpretations that
require the original photo and four actual 3D views for visual review.
"""
import argparse,hashlib,json,math,shutil,sys
from collections import Counter
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--threads',required=True)
parser.add_argument('--outline',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
graph=json.loads(Path(args.threads).read_text(encoding='utf-8'))
outline=json.loads(Path(args.outline).read_text(encoding='utf-8'))
for key in ['model','editableBlend','sourcePhoto']:
    if sha(parent[key])!=parent[key+'Sha256']:raise ValueError('Changed actual parent evidence: '+key)
if graph['sourcePhotoSha256']!=parent['sourcePhotoSha256'] or graph['sourcePhotoCrop']!=[649,344,727,368]:
    raise ValueError('Require this stage own unchanged photo thread paths.')
if outline['sourcePhotoSha256']!=graph['sourcePhotoSha256']:raise ValueError('Wrong original scallop outline.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve actual checkpoints and their evidence.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    source=Path(parent['editableBlend']).parent/dependency['file']
    if sha(source)!=dependency['sha256']:raise ValueError('Changed intact exterior library.')
    shutil.copyfile(source,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene;scene.frame_set(1)

def raw_hash(obj):
    xyz=np.empty(len(obj.data.vertices)*3,np.float32);obj.data.vertices.foreach_get('co',xyz)
    return hashlib.sha256(xyz.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
before={o.name:raw_hash(o) for o in scene.objects if o.type=='MESH'}
construction=dict(parent['garterBeltGatherConstruction'])
lace=bpy.data.objects[construction['lowerPhotographicLace']]
frill=bpy.data.objects[construction['frills'][1]]
columns=construction['rawColumns'];rim=[v.co.copy() for v in frill.data.vertices[-columns:]]
circumference=sum((rim[(i+1)%columns]-p).length for i,p in enumerate(rim))
repeats=10;tile_width=circumference/repeats
depth=tile_width*graph['height']/graph['width']
# The aspect of the photograph is preserved. Actual body scale is not proven.
outer=next(c['points'] for c in outline['tiles'][0]['contours'] if not c['hole'])
bottom=[]
for x in range(graph['width']):
    near=[y for px,y in outer if abs(px-x)<=1.1]
    bottom.append(max(near)/graph['height'] if near else .8)
bottom=np.clip(np.asarray(bottom),.55,1.)
bottom=(np.roll(bottom,1)+2*bottom+np.roll(bottom,-1))/4

def hem(x):
    p=(x%1)*(len(bottom)-1);a=int(p)
    return float(bottom[a]*(1-(p-a))+bottom[min(a+1,len(bottom)-1)]*(p-a))
def rim_point(u):
    v=(u%1)*columns;a=int(v)
    return rim[a].lerp(rim[(a+1)%columns],v-a)
def folded(u,t):
    theta=u*math.tau;radial=Vector((math.sin(theta),-math.cos(theta),0))
    # Separate coarse scalloped folds from the finer gathers of the attachment.
    gather=.00115*t*math.sin(40*theta+.8*t)
    gather+=.00040*t*math.sin(59*theta+1.1*t)
    return rim_point(u)+Vector((0,0,-depth*t))+radial*gather

def simplify(points,tolerance):
    if len(points)<3:return points
    first,last=np.asarray(points[0]),np.asarray(points[-1]);delta=last-first
    values=np.asarray(points[1:-1]);den=float(delta@delta)
    along=np.clip((values-first)@delta/max(den,1e-20),0,1)
    distances=np.linalg.norm(values-first-along[:,None]*delta,axis=1)
    i=int(np.argmax(distances))+1
    if float(distances[i-1])<=tolerance:return [points[0],points[-1]]
    return simplify(points[:i+1],tolerance)[:-1]+simplify(points[i:],tolerance)
def smooth(points,closed):
    pairs=list(zip(points,points[1:]+([points[0]] if closed else [])))
    result=[] if closed else [points[0]]
    for a,b in pairs:result.extend([a*.75+b*.25,a*.25+b*.75])
    if not closed:result.append(points[-1])
    return result
def subdivide(points,closed,limit=.00075):
    result=[]
    pairs=list(zip(points,points[1:]+([points[0]] if closed else [])))
    for a,b in pairs:
        count=max(1,math.ceil((a-b).length/limit))
        result.extend(a.lerp(b,i/count) for i in range(count))
    if not closed:result.append(points[-1])
    return result

vertices=[];faces=[];uv_faces=[];photo_faces=[];components=[]
def yarn(points,source_uv,radius,closed,label):
    if len(points)<2:raise ValueError('Degenerate yarn path.')
    offset=len(vertices);sides=6
    lengths=[0.]
    for a,b in zip(points,points[1:]):lengths.append(lengths[-1]+(a-b).length)
    total=lengths[-1]+((points[-1]-points[0]).length if closed else 0.)
    for i,p in enumerate(points):
        tangent=(points[(i+1)%len(points)]-points[i-1]) if closed else (
            points[1]-p if i==0 else p-points[i-1] if i==len(points)-1 else points[i+1]-points[i-1])
        tangent.normalize()
        normal=Vector((p.x,p.y,0));normal.normalize()
        normal-=tangent*normal.dot(tangent)
        if normal.length<1e-8:normal=tangent.cross(Vector((0,0,1)))
        normal.normalize();binormal=tangent.cross(normal).normalized()
        for side in range(sides):
            angle=side/sides*math.tau
            vertices.append(p+radius*(normal*math.cos(angle)+binormal*math.sin(angle)))
    for i in range(len(points) if closed else len(points)-1):
        ni=(i+1)%len(points);u0=lengths[i]/total;u1=(lengths[ni]/total if ni else 1.)
        for side in range(sides):
            ns=(side+1)%sides
            faces.append((offset+i*sides+side,offset+i*sides+ns,offset+ni*sides+ns,offset+ni*sides+side))
            uv_faces.append([(u0,side/sides),(u0,(side+1)/sides),(u1,(side+1)/sides),(u1,side/sides)])
            photo_faces.append([source_uv[i],source_uv[i],source_uv[ni],source_uv[ni]])
    if not closed:
        for i,reverse in [(0,True),(len(points)-1,False)]:
            order=list(range(sides));order=order[::-1] if reverse else order
            faces.append(tuple(offset+i*sides+s for s in order))
            uv_faces.append([(.5+.45*math.cos(s/sides*math.tau),.5+.45*math.sin(s/sides*math.tau)) for s in order])
            photo_faces.append([source_uv[i]]*sides)
    components.append({'kind':label,'points':len(points),'closedPath':closed,'radius':radius})

# A true closed sewing header follows every actual rim column.
yarn(rim,[(i/columns,1.) for i in range(columns)],.00010,True,'attachment_header')
for repeat in range(repeats):
    for path in graph['paths']:
        uv=[Vector((x/graph['width'],y/graph['height'])) for x,y in path['points']]
        flat=[Vector((p.x*tile_width,p.y*depth)) for p in uv]
        flat=simplify(flat,.00012)
        flat=smooth(flat,path['closed']);flat=subdivide(flat,path['closed'])
        uv=[(p.x/tile_width,p.y/depth) for p in flat]
        points=[folded((repeat+x)/repeats,y) for x,y in uv]
        yarn(points,[(x,1-y) for x,y in uv],.00015,path['closed'],'photographic_bright_filament')
    # Fine inferred warp and weft cover shaded folds. They are actual yarns,
    # not a plane whose photographic black pixels were deleted as holes.
    nx=max(2,round(tile_width/.0015));ny=max(2,round(depth/.0015))
    for x in (np.arange(nx)+.5)/nx:
        tmax=hem(float(x));count=max(2,math.ceil(depth*tmax/.0009)+1)
        uv=[(float(x),float(t)) for t in np.linspace(0,tmax,count)]
        yarn([folded((repeat+x)/repeats,t) for x,t in uv],[(x,1-t) for x,t in uv],.000055,False,'inferred_fine_ground_warp')
    for t in (np.arange(ny)+.5)/ny:
        samples=np.linspace(0,1,max(3,math.ceil(tile_width/.0009)+1));chains=[];chain=[]
        for x in samples:
            if t<=hem(float(x)):chain.append((float(x),float(t)))
            else:
                if len(chain)>1:chains.append(chain)
                chain=[]
        if len(chain)>1:chains.append(chain)
        for uv in chains:
            yarn([folded((repeat+x)/repeats,t) for x,t in uv],[(x,1-t) for x,t in uv],.000055,False,'inferred_fine_ground_weft')
print('ACTUAL_CLOSED_LACE_YARNS_BUILT',len(vertices),len(components),flush=True)

disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:disabled.append(modifier);modifier.show_viewport=False
followers=[m for m in lace.modifiers if m.type=='SURFACE_DEFORM']
if len(followers)!=1 or not followers[0].is_bound:raise ValueError('Missing actual sewn lace carrier.')
bpy.ops.object.select_all(action='DESELECT');lace.select_set(True);bpy.context.view_layer.objects.active=lace
followers[0].show_viewport=True;bpy.ops.object.surfacedeform_bind(modifier=followers[0].name)
removed_nodes=[m.name for m in lace.modifiers if m.type=='NODES']
for modifier in list(lace.modifiers):
    if modifier.type=='NODES':
        if modifier in disabled:disabled.remove(modifier)
        lace.modifiers.remove(modifier)
materials=list(lace.data.materials)
mesh=bpy.data.meshes.new(lace.name+' / rounded photographed filaments and fine ground')
mesh.from_pydata(vertices,[],faces);mesh.update()
for p in mesh.polygons:p.use_smooth=True
for material in materials:mesh.materials.append(material)
lace.data=mesh
for name,data in [('UVMap',uv_faces),('PhotoLaceUV',photo_faces)]:
    layer=mesh.uv_layers.new(name=name)
    for polygon,coordinates in zip(mesh.polygons,data):
        for loop,coordinate in zip(polygon.loop_indices,coordinates):layer.data[loop].uv=coordinate
mesh.uv_layers.active=mesh.uv_layers['UVMap'];mesh.uv_layers['UVMap'].active_render=True
for key in ['opaqueGeometryApertures','traceHolesPerRepeat','traceRepeats']:
    if key in lace:del lace[key]
lace['actualClosedLaceYarns']=len(components)
lace['photographicThreadPaths']=len(graph['paths']);lace['fineGroundInferred']=True
lace['sourceCrop']=json.dumps(graph['sourcePhotoCrop'])
edge_counts=Counter(tuple(sorted((p.vertices[i],p.vertices[(i+1)%len(p.vertices)])))
    for p in mesh.polygons for i in range(len(p.vertices)))
if any(n!=2 for n in edge_counts.values()):raise ValueError('An actual yarn has an open or nonmanifold edge.')
for modifier in disabled:modifier.show_viewport=True
scene.frame_set(1)
print('ACTUAL_ROUNDED_LACE_BIND_STARTED',len(vertices),flush=True)
bpy.ops.object.surfacedeform_bind(modifier=followers[0].name)
if not followers[0].is_bound:raise ValueError('Actual rounded lace did not bind to its existing carrier.')
changed=[name for name,digest in before.items() if raw_hash(bpy.data.objects[name])!=digest]
if changed!=[lace.name]:raise ValueError('Changed an unrelated raw mesh: '+str(changed))
evaluated=lace.evaluated_get(bpy.context.evaluated_depsgraph_get());result=evaluated.to_mesh();result.calc_loop_triangles()
if not np.isfinite(np.asarray([d.uv[:] for d in result.uv_layers['UVMap'].data])).all():raise ValueError('Invalid evaluated yarn UVs.')
piece=next(dict(p) for p in parent['pieces'] if p['name']==lace.name)
for key in ['actualGeometricApertures','traceRepeats','traceHolesPerRepeat']:piece.pop(key,None)
piece.update(baseVertices=len(mesh.vertices),basePolygons=len(mesh.polygons),evaluatedVertices=len(result.vertices),
    triangles=len(result.loop_triangles),uvMaps=[u.name for u in result.uv_layers],uvFinite=True,
    actualClosedLaceYarns=len(components),surfaceDeformBindings=[{'target':followers[0].target.name,'bound':True}])
evaluated.to_mesh_clear();pieces=[piece if p['name']==lace.name else p for p in parent['pieces']]
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_garter_lace_threads.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for p in pieces:bpy.data.objects[p['name']].select_set(True)
model=out/'foundation_garter_lace_threads.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_animations=False)
thread_record={'mesh':lace.name,'sourceThreadGraph':str(Path(args.threads).resolve()),'sourceThreadGraphSha256':sha(args.threads),
    'sourcePhotoCrop':graph['sourcePhotoCrop'],'repeats':repeats,'actualDepth':depth,'actualTileWidth':tile_width,
    'photoAspectPreserved':True,'photographicBodyScaleVerified':False,'components':components,
    'actualRawVertices':len(mesh.vertices),'actualRawPolygons':len(mesh.polygons),'actualManifoldEdgesVerified':True,
    'allYarnsCappedOrClosed':True,'photographicShadowsUsedAsHoles':False,'fineGroundAndUnseenRepeatsInferred':True,
    'closedYarnDoubleThicknessNodesRemoved':removed_nodes,'actualCarrierBindingVerified':True,
    'attachmentHeaderVertexStart':0,'attachmentHeaderVertexCount':columns*6,'attachmentHeaderRadius':.0001,
    'allOtherActualRawMeshesUnchanged':True,'rigPresent':False,'motionVerified':False,
    'clothCollisionVerified':False,'visualFidelityVerified':False}
construction.pop('denseLaceSurface',None)
construction.update(laceRepeats=repeats,laceDepth=depth,roundedLaceThreads=thread_record,
    lowerLaceMaterial='opaque round needle cotton yarns; photographic lighting excluded')
report={**parent,'method':'own_photo_bright_filaments_with_closed_yarns_and_inferred_fine_ground',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),
    'pieces':pieces,'garterBeltGatherConstruction':construction,'garterLaceThreadRefinement':thread_record,
    'inheritedInternalPieces':len(pieces),'addedInternalPieces':0,'refinedInternalPieces':1,
    'changedExistingRawMeshes':changed,'existingCagesUnchanged':True,'untouchedRawMeshesUnchanged':True,
    'additionalCreditsConsumed':0,'fidelityVerified':False,'rigPresent':False,'motionVerified':False,
    'clothCollisionVerified':False,'allLayersFinished':False,'nextVariantMayStart':False}
if 'garterLaceSurfaceRefinement' in report:
    report['previousLaceSurfaceStep']={**report.pop('garterLaceSurfaceRefinement'),'appliesToParentGeneration':str(Path(args.parent).resolve())}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTUAL_ROUNDED_LACE_CHECKPOINT_SAVED',len(pieces),flush=True)
