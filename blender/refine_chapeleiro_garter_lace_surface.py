"""Tessellate this belt's own photo lace before wrapping it around the frill.

Long straight header edges previously bridged the curved gathered rim. Refine
the flat contour surface before mapping, preserving its real holes and UVs.
This fixes an actual rest surface, not rig or dynamic cloth approval.
"""
import argparse,ast,hashlib,json,math,shutil,sys
from pathlib import Path
from collections import Counter
import bpy,bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--lace',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--tessellation',choices=['adaptive','constrained_grid'],default='adaptive')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
trace=json.loads(Path(args.lace).read_text(encoding='utf-8'))
for key in ['model','editableBlend','sourcePhoto']:
    if sha(parent[key])!=parent[key+'Sha256']:raise ValueError('Changed actual parent evidence.')
if (trace['sourcePhotoSha256']!=parent['sourcePhotoSha256'] or trace['section']!='garter'
        or trace['sourcePhotoSha256']!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4'):
    raise ValueError('Require this stage own unchanged photo.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve each previous actual checkpoint.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    path=Path(parent['editableBlend']).parent/dependency['file']
    if sha(path)!=dependency['sha256']:raise ValueError('Changed intact exterior library.')
    shutil.copyfile(path,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene;scene.frame_set(1)
def raw_hash(obj):
    values=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',values)
    return hashlib.sha256(values.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
before={o.name:raw_hash(o) for o in scene.objects if o.type=='MESH'}
construction=dict(parent['garterBeltGatherConstruction'])
lace=bpy.data.objects[construction['lowerPhotographicLace']]
frill=bpy.data.objects[construction['frills'][1]]
columns=construction['rawColumns'];rim=[v.co.copy() for v in frill.data.vertices[-columns:]]
repeat_count=construction['laceRepeats'];depth=construction['laceDepth']
tile=trace['tiles'][0]
if tile['sourcePhotoCrop']!=construction['ownSourceCrop']:raise ValueError('Wrong own belt lace trace.')
# Use only the already reviewed constrained contour triangulation helper.
helper_path=Path(__file__).with_name('refine_chapeleiro_foundation_cloth.py')
functions=[n for n in ast.parse(helper_path.read_text(encoding='utf-8')).body
           if isinstance(n,ast.FunctionDef) and n.name=='flat_trace']
if len(functions)!=1:raise ValueError('Changed bounded contour helper.')
exec(compile(ast.Module(body=functions,type_ignores=[]),str(helper_path),'exec'),globals())
base,faces=flat_trace(tile)
# Measure flat distances in the garment's actual circumferential dimensions.
circumference=sum((rim[(i+1)%columns]-p).length for i,p in enumerate(rim))
tile_width=circumference/repeat_count
max_edge=.0006
iterations=[]
grid_receipt={}
if args.tessellation=='constrained_grid':
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from chapeleiro_lace_tessellation import constrained_physical_grid
    base,faces,grid_receipt=constrained_physical_grid(base,faces,tile_width,depth,max_edge)
    before_euler=grid_receipt['templateEulerBefore']
    print('ACTUAL_CONSTRAINED_PHOTO_GRID_BUILT',json.dumps(grid_receipt),flush=True)
else:
    temp=bpy.data.meshes.new('Own garter photo / flat adaptive tessellation')
    temp.from_pydata(base,[],faces);temp.update()
    bm=bmesh.new();bm.from_mesh(temp)
    before_euler=len(bm.verts)-len(bm.edges)+len(bm.faces)
    def physical_edge_length(edge):
        delta=edge.verts[1].co-edge.verts[0].co
        return math.hypot(delta.x*tile_width,delta.y*depth)
    for iteration in range(12):
        long_edges=[e for e in bm.edges if physical_edge_length(e)>max_edge]
        if not long_edges:break
        iterations.append({'iteration':iteration,'splitEdges':len(long_edges)})
        bmesh.ops.subdivide_edges(bm,edges=long_edges,cuts=1,use_grid_fill=True)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
    else:raise ValueError('Flat lace failed to converge to its actual surface edge limit.')
    if len(bm.verts)-len(bm.edges)+len(bm.faces)!=before_euler:
        raise ValueError('Adaptive tessellation changed the real traced holes.')
    bm.to_mesh(temp);bm.free()
    base=[v.co.copy() for v in temp.vertices];faces=[tuple(p.vertices) for p in temp.polygons]
    bpy.data.meshes.remove(temp)
boundary=Counter(tuple(sorted((p[i],p[(i+1)%len(p)]))) for p in faces for i in range(len(p)))
header_edges=[(a,b) for (a,b),count in boundary.items() if count==1
              and abs(base[a].y-1)<1e-6 and abs(base[b].y-1)<1e-6]
if len(header_edges)<columns/repeat_count/2:
    raise ValueError('The real curved lace header has insufficient attachment samples.')
disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:disabled.append(modifier);modifier.show_viewport=False
followers=[m for m in lace.modifiers if m.type=='SURFACE_DEFORM']
if len(followers)!=1 or not followers[0].is_bound:
    raise ValueError('The actual lower lace lost its single sewn carrier.')
bpy.ops.object.select_all(action='DESELECT');lace.select_set(True);bpy.context.view_layer.objects.active=lace
followers[0].show_viewport=True
bpy.ops.object.surfacedeform_bind(modifier=followers[0].name)
def rim_point(u):
    x=(u%1)*columns;c=int(x)
    return rim[c].lerp(rim[(c+1)%columns],x-c)
vertices=[];polygons=[];uv_faces=[]
for repeat in range(repeat_count):
    offset=len(vertices)
    for p in base:
        u=(repeat+p.x)/repeat_count;theta=u*math.tau;t=1-p.y
        vertices.append(rim_point(u)+Vector((0,0,-depth*t))
            +Vector((math.sin(theta),-math.cos(theta),0))*(.00055*t*math.sin(59*theta+.8*t)))
    polygons.extend(tuple(offset+i for i in face) for face in faces)
    uv_faces.extend([[(base[i].x,base[i].y) for i in face] for face in faces])
materials=list(lace.data.materials)
mesh=bpy.data.meshes.new(lace.name+' / photo contour surface dense before wrapping')
mesh.from_pydata(vertices,[],polygons);mesh.update()
for polygon in mesh.polygons:polygon.use_smooth=True
for material in materials:mesh.materials.append(material)
lace.data=mesh
uv=mesh.uv_layers.new(name='PhotoLaceUV')
for face,coordinates in zip(mesh.polygons,uv_faces):
    for loop,coordinate in zip(face.loop_indices,coordinates):uv.data[loop].uv=coordinate
# Carrier geometry and every other sewn garment remain exactly unchanged.
for modifier in disabled:modifier.show_viewport=True
scene.frame_set(1)
print('ACTUAL_DENSE_LACE_BIND_STARTED',len(mesh.vertices),flush=True)
bpy.ops.object.surfacedeform_bind(modifier=followers[0].name)
if not followers[0].is_bound:raise ValueError('The dense lace did not bind to the existing actual carrier.')
changed=[name for name,digest in before.items() if raw_hash(bpy.data.objects[name])!=digest]
if changed!=[lace.name]:raise ValueError('An unrelated raw garment or the native exterior changed: '+str(changed))
evaluated=lace.evaluated_get(bpy.context.evaluated_depsgraph_get());result=evaluated.to_mesh();result.calc_loop_triangles()
layer=result.uv_layers.get('UVMap')
if not layer or not np.isfinite(np.array([d.uv[:] for d in layer.data])).all():
    raise ValueError('The actual dense lace has invalid evaluated UVs.')
piece=next(dict(p) for p in parent['pieces'] if p['name']==lace.name)
piece.update(baseVertices=len(mesh.vertices),basePolygons=len(mesh.polygons),evaluatedVertices=len(result.vertices),
             triangles=len(result.loop_triangles),uvMaps=[u.name for u in result.uv_layers],uvFinite=True,
             surfaceDeformBindings=[{'target':followers[0].target.name,'bound':True}])
evaluated.to_mesh_clear()
pieces=[piece if p['name']==lace.name else p for p in parent['pieces']]
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_garter_lace_surface.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for p in pieces:bpy.data.objects[p['name']].select_set(True)
model=out/'foundation_garter_lace_surface.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,
                         export_yup=True,export_animations=False)
dense={'mesh':lace.name,'flatPhotoTessellatedBeforeWrapping':True,'actualFlatPhysicalMaximumEdge':max_edge,
       'actualFrillCircumference':circumference,'templateVertices':len(base),'templateFaces':len(faces),
       'templateEulerBefore':before_euler,'templateEulerAfter':before_euler,'templateHeaderEdges':len(header_edges),
       'actualRawVertices':len(mesh.vertices),'subdivisionIterations':iterations,'ownPhotoUvPreserved':True,
       'actualCarrierBindingVerified':True,'allOtherActualRawMeshesUnchanged':True,
       'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False,'visualFidelityVerified':False}
if grid_receipt:
    dense.update(grid_receipt,tessellation='constrained_grid',
                 actualFlatPhysicalMaximumEdge=grid_receipt['actualMaximumFlatPhysicalEdge'])
else:dense['tessellation']='adaptive'
construction['denseLaceSurface']=dense
report={**parent,'method':'own_photo_lace_'+args.tessellation+'_then_actual_gathered_frill_wrapping',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),
    'pieces':pieces,'garterBeltGatherConstruction':construction,'garterLaceSurfaceRefinement':dense,
    'inheritedInternalPieces':len(pieces),'addedInternalPieces':0,'refinedInternalPieces':1,
    'changedExistingRawMeshes':changed,'existingCagesUnchanged':True,'untouchedRawMeshesUnchanged':True,
    'additionalCreditsConsumed':0,'fidelityVerified':False,'rigPresent':False,'motionVerified':False,
    'clothCollisionVerified':False,'allLayersFinished':False,'nextVariantMayStart':False}
if 'laceCottonMaterialRefinement' in report:
    report['previousLaceCottonMaterialStep']={**report.pop('laceCottonMaterialRefinement'),
        'appliesToParentGeneration':str(Path(args.parent).resolve())}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACTUAL_DENSE_GARTER_LACE_CHECKPOINT_SAVED',len(pieces),flush=True)
