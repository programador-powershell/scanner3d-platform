"""Author the foundation photo's gathered side fabric, tapes and drawstring ties.

Keep the complete exterior and all prior raw garment meshes unchanged. Move
the long petticoat's existing solver onto one thin carrier, and give each new
side panel a single thin solver before Bystedt thickness and UV evaluation.
This is an inferred modeling checkpoint, not rig or gameplay approval.
"""
import argparse, ast, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed parent evidence: '+field)
if parent['sourcePhotoSha256']!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Only the original foundation photo is valid.')
out=Path(args.output)
if out.exists():raise ValueError('Use a new modeling checkpoint directory.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    source=Path(parent['editableBlend']).parent/dependency['file']
    if sha(source)!=dependency['sha256']:raise ValueError('The intact master library changed.')
    shutil.copyfile(source,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene

def cage_hash(obj):
    data=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',data)
    return hashlib.sha256(data.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()

existing={o.name:cage_hash(o) for o in scene.objects if o.type=='MESH'}
inherited=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]
disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            disabled.append(modifier)
            modifier.show_viewport=False
scene.frame_set(1)
ivory=bpy.data.materials['Foundation / warm ivory cotton']
brass=bpy.data.materials['Foundation / aged brass eyelets and busk']
post=bpy.data.node_groups[parent['proceduralNodeAsset']]
main=bpy.data.objects['01 / long ivory gathered petticoat']
if len(main.data.vertices)!=192*37:raise ValueError('Unexpected actual petticoat topology.')
new,temporarily_disabled,physics_carriers=[],[],{}
helper=Path(__file__).with_name('refine_chapeleiro_foundation_blouse.py')
tree=ast.parse(helper.read_text(encoding='utf-8'))
names={'mesh_object','parent_to','post_modifier','surface_follow','tube','cloth','sleeve_faces'}
body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
if {n.name for n in body}!=names:raise ValueError('Changed own helper interface.')
exec(compile(ast.Module(body=body,type_ignores=[]),str(helper),'exec'),globals())
import BystedtsClothBuilder as BCB
from BystedtsClothBuilder import simulation
if not hasattr(bpy.types.Scene,'BCB_props'):BCB.register()
scene.BCB_props.use_triangulate=False
scene.BCB_props.simulation_frames=48
scene.BCB_props.sim_quality=12
scene.BCB_props.collision_quality=5
scene.BCB_props.collision_distance=.0005

def point_index_follow(obj,cage):
    # These two surfaces share exactly the same vertex order. Sampling the
    # solved point positions avoids an unnecessary interpolation/self-bind.
    evaluated=cage.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    if len(mesh.vertices)!=len(obj.data.vertices):
        raise ValueError('A point follower requires identical actual point counts.')
    evaluated.to_mesh_clear()
    group=bpy.data.node_groups.new(obj.name+' / solved point positions','GeometryNodeTree')
    group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes,links=group.nodes,group.links
    source=nodes.new('NodeGroupInput');output=nodes.new('NodeGroupOutput')
    info=nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE'
    info.inputs['Object'].default_value=cage
    info.inputs['As Instance'].default_value=False
    position=nodes.new('GeometryNodeInputPosition');index=nodes.new('GeometryNodeInputIndex')
    sample=nodes.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT'
    sample.clamp=False
    setter=nodes.new('GeometryNodeSetPosition')
    links.new(info.outputs['Geometry'],sample.inputs['Geometry'])
    links.new(position.outputs['Position'],sample.inputs['Value'])
    links.new(index.outputs['Index'],sample.inputs['Index'])
    links.new(source.outputs['Geometry'],setter.inputs['Geometry'])
    links.new(sample.outputs['Value'],setter.inputs['Position'])
    links.new(setter.outputs['Geometry'],output.inputs['Geometry'])
    follower=obj.modifiers.new('Visible petticoat samples its solved point positions','NODES')
    follower.node_group=group
    group['sameTopologySimulationTarget']=cage.name
    while list(obj.modifiers).index(follower)>0:bpy.ops.object.modifier_move_up(modifier=follower.name)
    return follower

def single_thin_solver(obj):
    solver=next(m for m in obj.modifiers if m.type=='CLOTH')
    # The copy retains the actual pin groups and any sewn attachment before Cloth.
    cage=obj.copy();cage.data=obj.data
    cage.name=obj.name+' / petticoat simulation midsurface'
    scene.collection.objects.link(cage)
    cage.hide_render=True;cage.display_type='WIRE'
    cage['constructedNewInternalLayer']=False
    cage['isPetticoatSimulationCage']=True
    cage['visibleFabric']=obj.name
    for modifier in list(cage.modifiers):
        if modifier.type=='NODES':cage.modifiers.remove(modifier)
        else:modifier.show_viewport=True
    triangulate=cage.modifiers.new('Stable evaluated thin target / fixed diagonals','TRIANGULATE')
    triangulate.quad_method='FIXED'
    # Both target and solver are thin; the evaluated solid output is never the target.
    for modifier in list(obj.modifiers):
        if modifier.type in {'CLOTH','SURFACE_DEFORM'}:obj.modifiers.remove(modifier)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
    if obj==main:
        # Keep the original main fabric's already verified deformation behavior.
        follower=obj.modifiers.new('Visible petticoat follows its single thin solver','SURFACE_DEFORM')
        follower.target=cage
        while list(obj.modifiers).index(follower)>0:bpy.ops.object.modifier_move_up(modifier=follower.name)
        bpy.ops.object.surfacedeform_bind(modifier=follower.name)
        bound=follower.is_bound
    else:
        follower=point_index_follow(obj,cage)
        bound=True
    if not bound:
        evaluated=cage.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
        coordinates=np.asarray([v.co[:] for v in mesh.vertices])
        triangles=np.asarray([t.vertices[:] for t in mesh.loop_triangles])
        points=coordinates[triangles]
        areas=np.linalg.norm(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]),axis=1)*.5
        diagnostic={'target':cage.name,'vertices':len(coordinates),'polygons':len(mesh.polygons),
                    'minimumTriangleArea':float(areas.min()),'degenerateTriangles':int(np.sum(areas<1e-12)),
                    'finiteCoordinates':bool(np.isfinite(coordinates).all()),
                    'modifierTypes':[m.type for m in cage.modifiers]}
        np.save(out/'failed_target_coordinates.npy',coordinates)
        np.save(out/'failed_target_triangles.npy',triangles)
        evaluated.to_mesh_clear()
        (out/'failed_target_diagnostic.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf-8')
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'failed_target_debug.blend'),compress=True)
        print('ACTUAL_INVALID_BIND_TARGET_DIAGNOSTIC',json.dumps(diagnostic),flush=True)
        raise ValueError('Thin fabric binding failed: '+obj.name)
    obj['simulationCage']=cage.name
    obj['simulationFollowMethod']='surface_deform' if obj==main else 'same_topology_point_index'
    physics_carriers[obj.name]=cage
    print('PETTICOAT_SINGLE_THIN_SOLVER',obj.name,cage.name,flush=True)
    return cage

main_cage=single_thin_solver(main)
next(m for m in main_cage.modifiers if m.type=='CLOTH').point_cache.frame_end=48

def base_position(u,t):
    # Bilinear sampling of actual authored cloth, with a short hem extension.
    column=(u%1)*192;i=int(column);fraction=column-i
    row=t*36;r=max(0,min(35,int(row)));v=row-r
    a=main.data.vertices[r*192+i].co.lerp(main.data.vertices[r*192+(i+1)%192].co,fraction)
    b=main.data.vertices[(r+1)*192+i].co.lerp(main.data.vertices[(r+1)*192+(i+1)%192].co,fraction)
    return a.lerp(b,v)

rows,columns=96,33
panel_cages=[]
pin_rows=[round(t*rows) for t in [.08,.23,.38,.53,.68,.83]]
for side in [-1,1]:
    label='left' if side<0 else 'right'
    def panel_position(c,t):
        inner=.198-.073*t
        u=side*(inner+(.476-inner)*c)
        p=base_position(u,t*1.10)
        theta=u*math.tau
        radial=Vector((math.sin(theta),-math.cos(theta),0))
        edge=math.sin(math.pi*c)**.65
        envelope=math.sin(math.pi*min(1,t))**.38
        # Narrow folded ridges and diagonal cloth creases, rather than broad
        # inflated lobes. The front drawstring edge gathers more than the back.
        phase=math.tau*(6.5*t-.65*c+.15*c*c+.04*math.sin(math.tau*t*1.1))
        ridge=(.5+.5*math.cos(phase))**6
        fine=.0015*math.cos(math.tau*(8*c+1.1*t+.25*math.sin(math.tau*t)))*edge*envelope
        outward=(.0012+.0045*ridge*(.3+.7*edge)+fine)*min(1,t/.08)
        vertical=-.007*math.sin(phase)*(.2+.8*(1-c))*envelope
        return p+radial*outward+Vector((0,0,vertical))
    points=[panel_position(c/(columns-1),r/rows) for r in range(rows+1) for c in range(columns)]
    faces=[]
    for r in range(rows):
        for c in range(columns-1):
            a=r*columns+c;b=a+1
            faces.append((a,a+columns,b+columns,b) if side>0 else (a,b,b+columns,a+columns))
    panel=mesh_object(f'01 / {label} petticoat / gathered side cascade panel',points,faces,'foundation_petticoat_cascade')
    # Attach to the actual thin main carrier before its own single Cloth solver.
    surface_follow(panel,main,main_cage)
    cloth(panel,{1.:list(range(columns))+[r*columns for r in pin_rows],
                 .65:list(range(columns,columns*2))})
    cloth_mod=next(m for m in panel.modifiers if m.type=='CLOTH')
    cloth_mod.settings.bending_stiffness=.25
    cloth_mod.collision_settings.distance_min=.0005
    cloth_mod.collision_settings.self_distance_min=.0004
    cloth_mod.point_cache.frame_end=48
    cage=single_thin_solver(panel)
    post_modifier(panel,-.00035)
    panel_cages.append(cage)
    panel['cascadeRows']=rows;panel['cascadeColumns']=columns
    panel['actualGatherPinRows']=json.dumps(pin_rows)
    panel['waistRootSampledFromActualPetticoat']=True
    panel['frontEdgeHeldAtActualDrawstringStations']=True

    edge=[points[r*columns] for r in range(rows+1)]
    tape_points=[]
    for r,p in enumerate(edge):
        transverse=(points[r*columns+1]-p).normalized()
        radial=Vector((p.x,p.y,0)).normalized()
        for c in range(3):tape_points.append(p+transverse*.0034*(c/2-.5)+radial*.0007)
    tape_faces=[(r*3+c,r*3+c+1,(r+1)*3+c+1,(r+1)*3+c) for r in range(rows) for c in range(2)]
    tape=mesh_object(f'01 / {label} petticoat / sewn drawstring casing tape',tape_points,tape_faces,'foundation_petticoat_detail')
    surface_follow(tape,panel,cage);post_modifier(tape,-.0002)
    hem=[points[rows*columns+c] for c in range(columns)]
    binding=tube(f'01 / {label} petticoat / rolled cascade lower hem',hem,.0006,role='foundation_petticoat_detail')
    surface_follow(binding,panel,cage)
    cord_material=ivory.copy();cord_material.name=f'Photo 1 / {label} petticoat aged drawcord'
    shader=cord_material.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value=(.17,.11,.061,1)
    shader.inputs['Roughness'].default_value=.7
    cord=tube(f'01 / {label} petticoat / continuous gathering drawcord',
              [p+Vector((p.x,p.y,0)).normalized()*.0011 for p in edge],.00042,
              material=cord_material,role='foundation_petticoat_detail')
    surface_follow(cord,panel,cage)
    for index,r in enumerate(pin_rows):
        p=edge[r];radial=Vector((p.x,p.y,0)).normalized()
        across=Vector((-radial.y,radial.x,0))
        center=p+radial*.0011
        ring=[center+across*(.00125*math.cos(k/16*math.tau))
                    +Vector((0,0,.0016*math.sin(k/16*math.tau))) for k in range(17)]
        eyelet=tube(f'01 / {label} petticoat / drawstring brass eyelet {index}',ring,.00027,
                    material=brass,role='foundation_petticoat_detail')
        surface_follow(eyelet,panel,cage)
    center=panel_position(0,.70)
    radial=Vector((center.x,center.y,0)).normalized()
    transverse=Vector((-radial.y,radial.x,0))
    center+=radial*.0035
    for wing in [-1,1]:
        verts=[]
        for r in range(25):
            t=r/24
            p=center+transverse*(wing*.010*math.sin(math.pi*t))+radial*(.002*math.sin(math.pi*t))
            p.z+=.0025*math.sin(math.tau*t)
            tangent=transverse*(wing*.010*math.pi*math.cos(math.pi*t))+Vector((0,0,.0025*math.tau*math.cos(math.tau*t)))
            width=radial.cross(tangent.normalized()).normalized()
            for c in range(5):verts.append(p+width*.0048*(c/4-.5))
        ribbon_faces=[(r*5+c,r*5+c+1,(r+1)*5+c+1,(r+1)*5+c) for r in range(24) for c in range(4)]
        bow=mesh_object(f'01 / {label} petticoat / gathered tie bow wing {wing}',verts,ribbon_faces,'foundation_petticoat_ribbon')
        surface_follow(bow,panel,cage);post_modifier(bow,-.00025)
        verts=[]
        for r in range(49):
            t=r/48
            p=panel_position(0,.70+.35*t)+radial*(.0035+.0015*math.sin(math.pi*t))
            p+=transverse*(wing*(.002+.003*t))
            for c in range(5):
                w=c/4-.5
                verts.append(p+transverse*(.0048*w)+radial*(.0005*math.sin(w*math.tau)*math.sin(math.pi*t)))
        tail=mesh_object(f'01 / {label} petticoat / hanging gathered tie ribbon {wing}',verts,
            [(r*5+c,r*5+c+1,(r+1)*5+c+1,(r+1)*5+c) for r in range(48) for c in range(4)],'foundation_petticoat_ribbon')
        surface_follow(tail,panel,cage);post_modifier(tail,-.00025)
    knot=tube(f'01 / {label} petticoat / gathered tie sewn knot',
        [center+transverse*(.002*math.cos(k/20*math.tau))+Vector((0,0,.0014*math.sin(k/20*math.tau))) for k in range(21)],
        .00085,role='foundation_petticoat_ribbon')
    surface_follow(knot,panel,cage)
    print('OWN_PHOTO_SIDE_CASCADE_AUTHORED',label,len(points),len(pin_rows),flush=True)

for modifier in disabled+temporarily_disabled:
    # The main solver was moved to its thin copy; removed RNA is invalid.
    try:modifier.show_viewport=True
    except ReferenceError:pass
scene.frame_set(1)
if any(cage_hash(bpy.data.objects[name])!=value for name,value in existing.items()):
    raise ValueError('An inherited raw mesh or the intact exterior changed.')

deps=bpy.context.evaluated_depsgraph_get()
pieces=[]
for obj in inherited+new:
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv:raise ValueError('Missing actual UV evaluation: '+obj.name)
    values=np.asarray([d.uv[:] for d in uv.data])
    if not np.isfinite(values).all():raise ValueError('Non-finite actual garment UVs.')
    piece={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),
           'basePolygons':len(obj.data.polygons),'evaluatedVertices':len(mesh.vertices),
           'triangles':len(mesh.loop_triangles),'uvMaps':[l.name for l in mesh.uv_layers],
           'uvFinite':True,'parent':obj.parent.name if obj.parent else None,
           'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
           'rigPresent':False,'fidelityVerified':False}
    if obj.get('opaqueGeometryApertures'):
        piece.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):piece['actualThreadLoops']=obj['actualThreadLoops']
    pieces.append(piece);evaluated.to_mesh_clear()
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_petticoat_cascades.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited+new:obj.select_set(True)
model=out/'foundation_petticoat_cascades.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,
                         export_apply=True,export_yup=True,export_animations=False)
report={**parent,'method':'own_photo_gathered_side_cascades_with_sewn_drawstring_tapes_and_thin_cloth_carriers',
        'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),
        'editableBlendSha256':sha(editable),'parentGeneration':str(Path(args.parent).resolve()),
        'parentGenerationSha256':sha(args.parent),'pieces':pieces,'inheritedInternalPieces':len(inherited),
        'addedInternalPieces':len(new),'existingCagesUnchanged':True,'completeExteriorVerticesUnchanged':True,
        'petticoatSimulationCages':[{'name':o.name,'visibleFabric':o['visibleFabric'],'rigPresent':False}
                                    for o in [main_cage,*panel_cages]],
        'cascadeConstruction':{'sourceCrop':[35,380,635,825],'surfacesInferredFromOwnPhoto':True,
            'sidePanels':2,'gatherStationsPerSide':len(pin_rows),'waistRootSampledFromActualPetticoat':True,
            'unseenBackInferred':True,'fixedBindingTargetDiagonals':True,'dynamicSimulationVerified':False},
        'ownHelperSource':{'file':str(helper.resolve()),'sha256':sha(helper)},
        'allLayersFinished':False,'fidelityVerified':False,'rigPresent':False,'motionVerified':False,
        'clothCollisionVerified':False,'additionalCreditsConsumed':0,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('OWN_PHOTO_PETTICOAT_CASCADES_SAVED',json.dumps({'newPieces':len(new),'totalPieces':len(pieces),
      'triangles':sum(p['triangles'] for p in pieces),'priorRawMeshesUnchanged':True}),flush=True)
