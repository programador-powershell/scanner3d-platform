"""Refine the own-photo gathered belt and construct its photographed lace.

Preserve the strap root ring and all unrelated clothing, including the intact
native exterior. One thin cloth cage carries the casing, frills and sewn trims.
This authors an editable rest shape, not rig or gameplay collision approval.
"""
import argparse,ast,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,delaunay_2d_cdt

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--lace',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
trace=json.loads(Path(args.lace).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed parent evidence: '+field)
if (parent['sourcePhotoSha256']!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4'
        or trace['sourcePhotoSha256']!=parent['sourcePhotoSha256'] or trace['section']!='garter'):
    raise ValueError('Require the unchanged own foundation photo and its garter trace.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve previous construction and visual checkpoints.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    source=Path(parent['editableBlend']).parent/dependency['file']
    if sha(source)!=dependency['sha256']:raise ValueError('The intact master library changed.')
    shutil.copyfile(source,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene;scene.frame_set(1)
inherited=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]

def raw_hash(obj):
    values=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',values)
    return hashlib.sha256(values.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
before={o.name:(o,raw_hash(o)) for o in scene.objects if o.type=='MESH'}
disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:disabled.append(modifier);modifier.show_viewport=False

belt=bpy.data.objects['01 / garter belt / gathered waist casing']
cage=bpy.data.objects[belt['simulationCage']]
if belt.data!=cage.data:raise ValueError('The real casing lost its shared cloth midsurface.')
old=[v.co.copy() for v in belt.data.vertices]
if len(old)!=128*9:raise ValueError('Unexpected parent belt topology.')
group_fields={group.name:np.asarray([next((g.weight for g in vertex.groups if g.group==group.index),0.)
    for vertex in cage.data.vertices]) for group in cage.vertex_groups}
if 'pinned' not in group_fields:raise ValueError('The actual parent cloth casing has no pin field.')
frills=[bpy.data.objects[f'01 / garter belt / ruffled edge {i}'] for i in [0,1]]
loops=[bpy.data.objects[f'01 / garter belt / looped lace edge {i}'] for i in [0,1]]
allowed={belt,cage,*frills,*loops}
new=[];temporarily_disabled=[];physics_carriers={belt.name:cage}
ivory=bpy.data.materials['Foundation / warm ivory cotton']
post=bpy.data.node_groups[parent['proceduralNodeAsset']]
lace_materials={}

def helpers(filename,names):
    body=[node for node in ast.parse(filename.read_text(encoding='utf-8')).body
          if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in body}!=set(names):raise ValueError('Changed own bounded construction helpers.')
    exec(compile(ast.Module(body=body,type_ignores=[]),str(filename),'exec'),globals())
helpers(Path(__file__).with_name('refine_chapeleiro_foundation_blouse.py'),
        ['mesh_object','parent_to','post_modifier','surface_follow','sleeve_faces'])
helpers(Path(__file__).with_name('refine_chapeleiro_foundation_cloth.py'),
        ['image_array','lace_material','flat_trace'])

def bind(obj,unbind=False):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    for modifier in obj.modifiers:
        if modifier.type=='SURFACE_DEFORM':
            modifier.show_viewport=True
            if unbind:
                if modifier.is_bound:bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
            else:
                if modifier.is_bound:raise ValueError('Rebind the changed rest surface explicitly.')
                print('GARTER_BELT_BIND_START',obj.name,flush=True)
                bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
                if not modifier.is_bound:raise ValueError('The actual belt attachment did not bind: '+obj.name)
                print('GARTER_BELT_BIND_OK',obj.name,flush=True)
for obj in [belt]+frills+loops:bind(obj,True)

columns=512;rows=24
def ring_sample(points,u):
    index=(u%1)*len(points);a=int(index)
    return points[a].lerp(points[(a+1)%len(points)],index-a)
original_root=old[-128:]
def casing_point(u,t):
    theta=u*math.tau
    point=ring_sample(original_root,u)
    if t==1:return point
    point.z+=.008*(1-t)
    phase=61*theta+.65*math.sin(3*theta+.7)+.24*math.sin(7*theta-1.2)
    amplitude=.00075*(.72+.23*math.sin(5*theta+.4)+.12*math.sin(11*theta))
    gather=amplitude*(.35+.65*math.sin(math.pi*t)**.7)*math.cos(phase+.25*t)
    gather+=.00019*math.sin(113*theta+1.8*t)*math.sin(math.pi*t)
    gather*=min(1.,(1-t)/.13)
    return point+Vector((math.sin(theta),-math.cos(theta)*.72,0))*gather

def mesh_replace(obj,points,faces):
    materials=list(obj.data.materials)
    mesh=bpy.data.meshes.new(obj.name+' / own photo refined fabric')
    mesh.from_pydata(points,[],faces);mesh.update()
    for face in mesh.polygons:face.use_smooth=True
    for material in materials:mesh.materials.append(material)
    obj.data=mesh
    return mesh

points=[casing_point(c/columns,r/rows) for r in range(rows+1) for c in range(columns)]
if any(points[rows*columns+4*c]!=original_root[c] for c in range(128)):
    raise ValueError('The original strap-root ring moved.')
cage.data=mesh_replace(belt,points,[face[::-1] for face in sleeve_faces(columns,rows)])
# Blender 5.2 stores these group definitions with mesh data. Replacing the
# midsurface clears them: restore every actual Cloth field on the new mesh.
for name,field in group_fields.items():
    group=cage.vertex_groups.get(name) or cage.vertex_groups.new(name=name)
    if name=='pinned':continue
    for r in range(rows+1):
        v=r/rows*8;row=min(7,int(v));blend=v-row
        for c in range(columns):
            u=c/columns*128;column=int(u);fraction=u-column
            a=field[row*128+column]*(1-fraction)+field[row*128+(column+1)%128]*fraction
            b=field[(row+1)*128+column]*(1-fraction)+field[(row+1)*128+(column+1)%128]*fraction
            weight=float(a*(1-blend)+b*blend)
            if weight>0:group.add([r*columns+c],weight,'REPLACE')
pin=cage.vertex_groups['pinned']
pin.add(list(range(columns)),1.,'REPLACE');pin.add(list(range(columns,2*columns)),.7,'REPLACE')
if sum(m.type=='CLOTH' for m in cage.modifiers)!=1:raise ValueError('Require one real thin casing solver.')
for modifier in cage.modifiers:
    modifier.show_viewport=True
    if modifier.type=='TRIANGULATE':modifier.quad_method='FIXED'
bind(belt)
frill_points=[];frill_rows=12
for edge,frill in enumerate(frills):
    old_frill=[v.co.copy() for v in frill.data.vertices]
    if len(old_frill)!=128*7:raise ValueError('Unexpected parent belt frill topology.')
    frill.data.calc_loop_triangles()
    old_triangles=[tuple(t.vertices) for t in frill.data.loop_triangles]
    old_tree=BVHTree.FromPolygons(old_frill,old_triangles,all_triangles=True)
    old_params=[Vector((i%128/128,i//128/6,0)) for i in range(len(old_frill))]
    direction=1 if edge==0 else -1
    root=points[:columns] if edge==0 else points[-columns:]
    values=[]
    for row in range(frill_rows+1):
        t=row/frill_rows
        for c,p in enumerate(root):
            theta=c/columns*math.tau
            phase=59*theta+.7*math.sin(3*theta+.4)+.3*math.sin(7*theta+edge)
            amplitude=.74+.17*math.sin(5*theta+.8)+.10*math.cos(9*theta+edge)
            pleat=amplitude*(math.cos(phase+.7*t)+.22*math.cos(2*phase-.5*t))
            secondary=.00035*t*math.sin(107*theta+2*t)
            length=.0095 if edge==0 else .0053
            radial=Vector((math.sin(theta),-math.cos(theta),0))
            values.append(p+radial*t*(.0037+.0019*pleat+secondary)
                +Vector((0,0,direction*(length*t+.00125*t*pleat))))
    mesh_replace(frill,values,[face if direction==1 else face[::-1]
                             for face in sleeve_faces(columns,frill_rows)])
    frill_points.append(values)
    if edge==0:
        def sampled(u,t):
            x=(u%1)*columns;c=int(x);v=min(frill_rows,max(0.,t*frill_rows));r=min(frill_rows-1,int(v))
            a=values[r*columns+c].lerp(values[r*columns+(c+1)%columns],x-c)
            b=values[(r+1)*columns+c].lerp(values[(r+1)*columns+(c+1)%columns],x-c)
            return a.lerp(b,v-r)
        transferred=[]
        for vertex in loops[0].data.vertices:
            p=vertex.co.copy();hit,normal,index,distance=old_tree.find_nearest(p)
            a,b,c=old_triangles[index];pa,pb,pc=[old_params[i].copy() for i in [a,b,c]]
            if max(pa.x,pb.x,pc.x)-min(pa.x,pb.x,pc.x)>.5:
                for parameter in [pa,pb,pc]:
                    if parameter.x<.5:parameter.x+=1
            uv=barycentric_transform(hit,old_frill[a],old_frill[b],old_frill[c],pa,pb,pc)
            transferred.append(p+sampled(uv.x,uv.y)-hit)
        loops[0].data.vertices.foreach_set('co',np.asarray([p[:] for p in transferred],np.float32).ravel())
        loops[0].data.update()
        uv=loops[0].data.uv_layers['UVMap']
        for face in loops[0].data.polygons:
            if len(face.vertices)==6:
                for loop in face.loop_indices:
                    angle=loops[0].data.loops[loop].vertex_index%6/6*math.tau
                    uv.data[loop].uv=(.5+.45*math.cos(angle),.5+.45*math.sin(angle))
    bind(frill)

# Replace the old lower loop-only trim with this belt's own photographed
# openwork. New 3D apertures follow its actual gathered rim, retaining photo UVs.
tile=trace['tiles'][0];base,polygons=flat_trace(tile);repeats=5;lace_depth=.0105
lace_vertices=[];lace_faces=[];lace_uv=[]
rim=frill_points[1][-columns:]
for repeat in range(repeats):
    offset=len(lace_vertices)
    for p in base:
        u=(repeat+p.x)/repeats;point=ring_sample(rim,u)
        theta=u*math.tau;t=1-p.y
        lace_vertices.append(point+Vector((0,0,-lace_depth*t))
            +Vector((math.sin(theta),-math.cos(theta),0))*(.00055*t*math.sin(59*theta+.8*t)))
    lace_faces.extend(tuple(offset+i for i in poly) for poly in polygons)
    lace_uv.extend([[(base[i].x,base[i].y) for i in poly] for poly in polygons])
lace=loops[1];lace.name='01 / garter belt / garter belt hem photographic lace'
mesh_replace(lace,lace_vertices,lace_faces)
lace.data.materials.clear()
needle_cotton=ivory.copy();needle_cotton.name='Photo 1 / garter belt needle cotton / scene lighting'
lace.data.materials.append(needle_cotton)
uv=lace.data.uv_layers.new(name='PhotoLaceUV')
for face,coordinates in zip(lace.data.polygons,lace_uv):
    for loop,coordinate in zip(face.loop_indices,coordinates):uv.data[loop].uv=coordinate
if 'actualThreadLoops' in lace:del lace['actualThreadLoops']
lace['opaqueGeometryApertures']=True;lace['traceHolesPerRepeat']=tile['retainedHoles']
lace['traceRepeats']=repeats;lace['carrier']=frills[1].name
lace['sourceCrop']=json.dumps(tile['sourcePhotoCrop'])
post_modifier(lace,-.00015);bind(lace);bind(loops[0])

# Two continuous narrow stitches bound to the same actual thin casing.
for name,t in [('upper',.14),('lower',.86)]:
    values=[];faces=[];uv_faces=[];sides=6
    for c in range(columns):
        theta=c/columns*math.tau;radial=Vector((math.sin(theta),-math.cos(theta),0))
        center=casing_point(c/columns,t)+radial*.00028
        for side in range(sides):
            angle=side/sides*math.tau
            values.append(center+.00014*(radial*math.cos(angle)+Vector((0,0,math.sin(angle)))))
    for c in range(columns):
        for side in range(sides):
            faces.append((c*sides+side,((c+1)%columns)*sides+side,
                ((c+1)%columns)*sides+(side+1)%sides,c*sides+(side+1)%sides))
            uv_faces.append([(c/columns,side/sides),((c+1)/columns,side/sides),
                ((c+1)/columns,(side+1)/sides),(c/columns,(side+1)/sides)])
    obj=mesh_object('01 / garter belt / elastic casing '+name+' stitch',values,faces,'foundation_garter_trim')
    uv=obj.data.uv_layers.new(name='UVMap')
    for face,coordinates in zip(obj.data.polygons,uv_faces):
        for loop,coordinate in zip(face.loop_indices,coordinates):uv.data[loop].uv=coordinate
    surface_follow(obj,belt,cage)

for modifier in disabled+temporarily_disabled:modifier.show_viewport=True
scene.frame_set(1)
changed=[obj.name for old_name,(obj,digest) in before.items() if raw_hash(obj)!=digest]
if any(obj not in allowed for obj,digest in before.values() if raw_hash(obj)!=digest):
    raise ValueError('An unrelated raw garment or the native exterior changed.')
pieces=[];deps=bpy.context.evaluated_depsgraph_get()
for obj in inherited+new:
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv or not np.isfinite(np.asarray([d.uv[:] for d in uv.data])).all():
        raise ValueError('The actual belt construction has invalid evaluated UVs: '+obj.name)
    entry={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),'basePolygons':len(obj.data.polygons),
        'evaluatedVertices':len(mesh.vertices),'triangles':len(mesh.loop_triangles),'uvMaps':[u.name for u in mesh.uv_layers],
        'uvFinite':True,'parent':obj.parent.name if obj.parent else None,
        'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
        'rigPresent':False,'fidelityVerified':False}
    if obj.get('opaqueGeometryApertures'):entry.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):entry['actualThreadLoops']=obj['actualThreadLoops']
    if obj.get('actualSewingDashes'):entry['actualSewingDashes']=obj['actualSewingDashes']
    pieces.append(entry);evaluated.to_mesh_clear()
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_garter_belt.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited+new:obj.select_set(True)
model=out/'foundation_garter_belt.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,
                         export_yup=True,export_animations=False)
rim_hash=hashlib.sha256(np.asarray([p[:] for p in original_root],np.float32).tobytes()).hexdigest()
construction={'mesh':belt.name,'simulationCage':cage.name,'rawColumns':columns,'rawRows':rows+1,
    'casingHeight':.008,'originalRootColumns':128,'originalStrapRootRingSha256':rim_hash,
    'originalStrapRootRingPreserved':True,'frills':[o.name for o in frills],
    'frillRows':frill_rows+1,'lowerPhotographicLace':lace.name,'ownSourceCrop':tile['sourcePhotoCrop'],
    'photoHolesPerRepeat':tile['retainedHoles'],'laceRepeats':repeats,'laceDepth':lace_depth,
    'actualElasticSeamMeshes':[o.name for o in new],'singleThinClothSolver':True,
    'originalClothGroupSchema':{name:int(np.count_nonzero(field)) for name,field in group_fields.items()},
    'clothGroupFieldsRebuiltForNewMidsurface':True,'photographicBodyScaleVerified':False,
    'lowerLaceMaterial':'cotton weave; photograph contours and UV retained without baked photographic lighting',
    'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False}
report={**parent,'method':'own_photo_narrow_garter_casing_irregular_gathers_and_photographic_openwork',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),'pieces':pieces,
    'garterBeltGatherConstruction':construction,
    'additionalLaceTraces':parent.get('additionalLaceTraces',[])+[{'file':str(Path(args.lace).resolve()),'sha256':sha(args.lace)}],
    'inheritedInternalPieces':len(inherited),'addedInternalPieces':len(new),'refinedInternalPieces':len(changed),
    'changedExistingRawMeshes':changed,'untouchedRawMeshesUnchanged':True,'existingCagesUnchanged':False,
    'completeExteriorVerticesUnchanged':True,'allLayersFinished':False,'rigPresent':False,'fidelityVerified':False,
    'motionVerified':False,'clothCollisionVerified':False,'additionalCreditsConsumed':0,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('GARTER_BELT_CHECKPOINT_SAVED',json.dumps({'pieces':len(pieces),'refinedRawMeshes':changed,
    'triangles':sum(p['triangles'] for p in pieces),'completeExteriorUnchanged':True}),flush=True)
