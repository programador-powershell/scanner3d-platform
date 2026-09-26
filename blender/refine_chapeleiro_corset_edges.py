"""Add the own-photo corset frills, geometric hem lace and rear ribbons.

Preserve all prior cages and the whole exterior. The inclined photographed
lace header is mapped to the actual pointed rim, retaining its raw photo UVs.
"""
import argparse,ast,hashlib,json,math,shutil,sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--lace',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
trace=json.loads(Path(args.lace).read_text(encoding='utf-8'))
if (sha(parent['editableBlend'])!=parent['editableBlendSha256']
        or sha(parent['sourcePhoto'])!=parent['sourcePhotoSha256']
        or trace['sourcePhotoSha256']!=parent['sourcePhotoSha256']):
    raise ValueError('The same unmodified foundation photo and editable source are required.')
out=Path(args.output)
if out.exists(): raise ValueError('Use a new refinement directory.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    library=Path(parent['editableBlend']).parent/dependency['file']
    if sha(library)!=dependency['sha256']: raise ValueError('Changed intact master library.')
    shutil.copyfile(library,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene
def cage_hash(obj):
    co=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',co)
    return hashlib.sha256(co.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
existing={o.name:cage_hash(o) for o in scene.objects if o.type=='MESH'}
inherited=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]
corset=bpy.data.objects['01 / ivory fitted boned corset / pointed front']
disabled=[]
for obj in scene.objects:
    if obj.type=='MESH' and obj!=corset:
        for modifier in obj.modifiers:
            if modifier.show_viewport:
                disabled.append(modifier)
                modifier.show_viewport=False
scene.frame_set(1)
ivory=bpy.data.materials['Foundation / warm ivory cotton']
brass=bpy.data.materials['Foundation / aged brass eyelets and busk']
post=bpy.data.node_groups[parent['proceduralNodeAsset']]
new,temporarily_disabled,physics_carriers,lace_materials=[],[],{},{}
def own_functions(file,names):
    tree=ast.parse(file.read_text(encoding='utf-8'))
    body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in body}!=set(names): raise ValueError('Changed own helper interface.')
    exec(compile(ast.Module(body=body,type_ignores=[]),str(file),'exec'),globals())
helper=Path(__file__).with_name('refine_chapeleiro_foundation_blouse.py')
lace_helper=Path(__file__).with_name('refine_chapeleiro_foundation_cloth.py')
own_functions(helper,['mesh_object','parent_to','post_modifier','surface_follow','sleeve_faces','tube','sewn_eyelets'])
own_functions(lace_helper,['image_array','lace_material','flat_trace'])
n=128
if len(corset.data.vertices)!=n*25: raise ValueError('Unexpected actual corset rim topology.')
roots={0:[v.co.copy() for v in corset.data.vertices[:n]],
       1:[v.co.copy() for v in corset.data.vertices[-n:]]}
frills={}
for edge,direction in [(0,1),(1,-1)]:
    root=roots[edge]
    points=[]
    for row in range(9):
        t=row/8
        for c,p in enumerate(root):
            theta=c/n*math.tau
            radial=Vector((math.sin(theta),-math.cos(theta),0))
            phase=39*theta+.5*math.sin(7*theta)
            wave=math.cos(phase)
            points.append(p+radial*(.0005+t*(.0023+.0015*wave))
                          +Vector((0,0,direction*t*(.0045+.0007*wave))))
    frill=mesh_object('01 / corset / '+('upper gathered frill' if edge==0 else 'lower pointed gathered frill'),
                     points,[face if direction==1 else face[::-1] for face in sleeve_faces(n,8)],
                     'foundation_corset_trim')
    surface_follow(frill,corset)
    post_modifier(frill,-.0002)
    frills[edge]=(frill,points[-n:])
    print('CORSET_ACTUAL_RIM_FRILL_BUILT',frill.name,flush=True)
top,ring=frills[0]
sewn_eyelets('01 / corset / upper needle lace edging',ring,72,.0023,
             Vector((0,0,1)),top,corset)
new[-1]['role']='foundation_corset_trim'

carrier,ring=frills[1]
tile=trace['tiles'][0]
base,polygons=flat_trace(tile)
verts,faces,uv_faces=[],[],[]
repeats=14
def sample_ring(u):
    index=(u%1)*n
    i=int(index)
    return ring[i].lerp(ring[(i+1)%n],index-i)
for repeat in range(repeats):
    offset=len(verts)
    for p in base:
        seam=tile['attachmentSeamPixels'][0]+(tile['attachmentSeamPixels'][1]-tile['attachmentSeamPixels'][0])*p.x
        depth=((1-p.y)*(tile['height']-1)-seam)/tile['laceDepthPixels']
        verts.append(sample_ring((repeat+p.x)/repeats)+Vector((0,0,-.0075*depth)))
    faces.extend(tuple(offset+i for i in poly) for poly in polygons)
    uv_faces.extend([[(base[i].x,base[i].y) for i in poly] for poly in polygons])
lace=mesh_object('01 / corset / corset hem scalloped floral lace',verts,faces,
                 'internal_photographic_lace',lace_material(tile))
uv=lace.data.uv_layers.new(name='PhotoLaceUV')
for poly,coords in zip(lace.data.polygons,uv_faces):
    for index,coordinate in zip(poly.loop_indices,coords): uv.data[index].uv=coordinate
surface_follow(lace,carrier,corset)
post_modifier(lace,-.00015)
lace['opaqueGeometryApertures']=True
lace['traceHolesPerRepeat']=tile['retainedHoles']
lace['traceRepeats']=repeats
lace['carrier']=carrier.name
lace['inclinedPhotoSeamMappedToActualPointedRim']=True

# Tie the fabric below the actual last eyelets. The former constant Y crossed
# the flared rear panel and concealed the lower tails in the rendered model.
def rear_profile(obj, columns):
    points=[obj.matrix_world @ obj.data.vertices[i].co
            for i in range(columns//2,len(obj.data.vertices),columns)]
    return sorted([(p.z,p.y) for p in points])

rear_profiles=[rear_profile(corset,n),
               rear_profile(bpy.data.objects['01 / long ivory gathered petticoat'],192)]

def rear_envelope_y(z):
    values=[]
    for profile in rear_profiles:
        if z<=profile[0][0]: values.append(profile[0][1]); continue
        if z>=profile[-1][0]: values.append(profile[-1][1]); continue
        for (az,ay),(bz,by) in zip(profile,profile[1:]):
            if az<=z<=bz:
                values.append(ay+(by-ay)*(z-az)/(bz-az)); break
    return max(values)

last_eyelets=[bpy.data.objects[f'01 / rear eyelet 7 side {side}'] for side in [-1,1]]
tie_z=sum((obj.matrix_world @ v.co).z for obj in last_eyelets for v in obj.data.vertices)
tie_z/=sum(len(obj.data.vertices) for obj in last_eyelets)
tie_z-=.003
center=Vector((0,rear_envelope_y(tie_z)+.004,tie_z))
for side in [-1,1]:
    points=[]
    for row in range(25):
        t=row/24
        p=center+Vector((side*(.001+.019*math.sin(math.pi*t)),
                         .002+.005*math.sin(math.pi*t)**2,.0045*math.sin(math.tau*t)))
        tangent=Vector((side*.019*math.pi*math.cos(math.pi*t),0,
                        .0045*math.tau*math.cos(math.tau*t))).normalized()
        width=Vector((-tangent.z,0,tangent.x)).normalized()
        for c in range(5):
            w=c/4-.5
            points.append(p+width*.0065*w+Vector((0,.0008*math.cos(math.pi*w*2)*math.sin(math.pi*t),0)))
    faces=[(r*5+c,r*5+c+1,(r+1)*5+c+1,(r+1)*5+c) for r in range(24) for c in range(4)]
    bow=mesh_object(f'01 / corset / rear ribbon bow wing {side}',points,faces,'foundation_corset_ribbon')
    surface_follow(bow,corset)
    post_modifier(bow,-.0003)
    points=[]
    for row in range(33):
        t=row/32
        z=center.z-.060*t
        p=Vector((side*(.003+.005*t+.0015*math.sin(math.pi*t)),
                  rear_envelope_y(z)+.004+.002*math.sin(t*math.pi*.8),z))
        for c in range(5):
            w=c/4-.5
            points.append(p+Vector((.0075*w,.00065*math.sin(math.pi*w*2)*math.sin(math.pi*t),
                                    -.0015*abs(w)*t**6)))
    tail=mesh_object(f'01 / corset / rear hanging ribbon tail {side}',points,
                     [(r*5+c,r*5+c+1,(r+1)*5+c+1,(r+1)*5+c) for r in range(32) for c in range(4)],
                     'foundation_corset_ribbon')
    surface_follow(tail,corset)
    post_modifier(tail,-.0003)
path=[center+Vector((math.cos(k/24*math.tau)*.003, .004,math.sin(k/24*math.tau)*.002)) for k in range(25)]
knot=tube('01 / corset / rear ribbon sewn knot',path,.0014,role='foundation_corset_ribbon')
surface_follow(knot,corset)
for modifier in disabled+temporarily_disabled: modifier.show_viewport=True
scene.frame_set(1)
if any(cage_hash(bpy.data.objects[name])!=value for name,value in existing.items()):
    raise ValueError('A prior actual cage or the complete exterior changed.')
deps=bpy.context.evaluated_depsgraph_get()
pieces=[]
for obj in inherited+new:
    evaluated=obj.evaluated_get(deps)
    mesh=evaluated.to_mesh()
    mesh.calc_loop_triangles()
    if not mesh.uv_layers.get('UVMap'): raise ValueError('Missing actual post-thickness UV: '+obj.name)
    entry={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),
           'basePolygons':len(obj.data.polygons),'evaluatedVertices':len(mesh.vertices),
           'triangles':len(mesh.loop_triangles),'uvMaps':[l.name for l in mesh.uv_layers],
           'uvFinite':bool(np.isfinite(np.asarray([d.uv[:] for d in mesh.uv_layers['UVMap'].data])).all()),
           'parent':obj.parent.name if obj.parent else None,
           'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
           'rigPresent':False,'fidelityVerified':False}
    if not entry['uvFinite']: raise ValueError('Non-finite corset UVs.')
    if obj.get('opaqueGeometryApertures'):
        entry.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'): entry['actualThreadLoops']=obj['actualThreadLoops']
    pieces.append(entry)
    evaluated.to_mesh_clear()
for library in bpy.data.libraries:
    library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_corset_edges.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited+new: obj.select_set(True)
model=out/'foundation_corset_edges.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,
                          export_apply=True,export_yup=True,export_animations=False)
report={**parent,'method':'own_photo_corset_frills_inclined_seam_lace_and_rear_fabric_ribbons',
        'model':str(model.resolve()),'modelSha256':sha(model),
        'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
        'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),
        'pieces':pieces,'inheritedInternalPieces':len(inherited),'addedInternalPieces':len(new),
        'existingCagesUnchanged':True,'completeExteriorVerticesUnchanged':True,
        'additionalLaceTraces':parent.get('additionalLaceTraces',[])+[{'file':str(Path(args.lace).resolve()),'sha256':sha(args.lace)}],
        'ownCorsetHelperSources':[{'file':str(helper.resolve()),'sha256':sha(helper)},
                                 {'file':str(lace_helper.resolve()),'sha256':sha(lace_helper)}],
        'corsetEdgesCompared':False,'corsetRibbonFitVerified':False,
        'ribbonConstruction':{'tieBelowLastActualEyeletRow':True,'tiePosition':list(center),
                              'rearEnvelopeFromActualCorsetAndPetticoat':True,
                              'staticSurfaceClearance':.004,'dynamicCollisionsVerified':False},
        'allLayersFinished':False,'fidelityVerified':False,'rigPresent':False,'motionVerified':False,
        'clothCollisionVerified':False,'additionalCreditsConsumed':0}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('CORSET_RIM_REFINEMENT_SAVED',json.dumps({'newPieces':len(new),'totalPieces':len(pieces),
        'triangles':sum(p['triangles'] for p in pieces),'priorCagesUnchanged':True}),flush=True)
