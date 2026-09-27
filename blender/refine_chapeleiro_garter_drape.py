"""Sculpt the own-photo cup volume and move existing sewn details with it.

Refine the actual cup quads; preserve both rims and all unrelated garments.
Transfer each sewn detail through the actual old cup triangles. This is an
editable rest-shape refinement, not a rig or a cloth-motion approval.
"""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed parent evidence: '+field)
if parent['sourcePhotoSha256']!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Require the unchanged own foundation photo.')
out=Path(args.output)
if out.exists():raise ValueError('Preserve prior modeling and visual checkpoints.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    path=Path(parent['editableBlend']).parent/dependency['file']
    if sha(path)!=dependency['sha256']:raise ValueError('The intact exterior library changed.')
    shutil.copyfile(path,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene
scene.frame_set(1)
objects=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]
def raw_hash(obj):
    values=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',values)
    return hashlib.sha256(values.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
before={o.name:raw_hash(o) for o in scene.objects if o.type=='MESH'}
disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            disabled.append(modifier);modifier.show_viewport=False

def select(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True);bpy.context.view_layer.objects.active=obj
def bind(obj,unbind=False):
    select(obj)
    for modifier in obj.modifiers:
        if modifier.type=='SURFACE_DEFORM':
            modifier.show_viewport=True
            if unbind:
                if modifier.is_bound:bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
            else:
                if modifier.is_bound:raise ValueError('A modified attachment must bind from its new rest shape.')
                bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
                if not modifier.is_bound:raise ValueError('The sculpted detail attachment failed: '+obj.name)

def relief(u,t):
    # Leave the photographed narrow facing and the entire pointed hem fixed.
    angle=u*math.tau
    front=max(0.,math.cos(angle))
    # The facing has a fixed physical height even where the pointed hem
    # changes the local fabric length. Leave clearance below its entire rim.
    start=.0065/(.027+.018*front**4)+.015
    s=(t-start)/(.93-start)
    if not 0<s<1:return Vector()
    envelope=math.sin(math.pi*s)**1.35
    dome=.0078*envelope*front**1.65
    # Shallow diagonal tension folds concentrate beside, rather than across,
    # the center seam. The hidden rear remains unchanged and explicitly inferred.
    lateral=abs(math.sin(angle))
    tension=.00055*envelope*front**1.3*lateral*math.sin(14*angle+19*t+.3*math.sin(5*angle))
    shoulder=.0016*envelope*math.sin(angle)*front
    return Vector((shoulder,-dome,0))+Vector((math.sin(angle),-math.cos(angle),0))*tension

allowed=set();drapes=[];webs=[];construction={p['mesh']:dict(p) for p in parent['garterCupConstruction']}
for label in ['left','right']:
    cup=bpy.data.objects[f'01 / {label} garter / pointed thigh reinforcement']
    stock=cup.parent
    target=bpy.data.objects[stock['skinCage']]
    for modifier in target.modifiers:
        modifier.show_viewport=True
        if modifier.type=='TRIANGULATE':modifier.quad_method='FIXED'
    old=[v.co.copy() for v in cup.data.vertices]
    if len(old)!=96*15:raise ValueError('Unexpected parent cup topology.')
    cup.data.calc_loop_triangles()
    triangles=[tuple(t.vertices) for t in cup.data.loop_triangles]
    tree=BVHTree.FromPolygons(old,triangles,all_triangles=True)
    params=[Vector((i%96/96,i//96/14,0)) for i in range(len(old))]
    family=[o for o in objects if o.parent==cup and
            (o.get('garterOwnPhotoDetail') or 'cup front stitch' in o.name)]
    for obj in [cup]+family:bind(obj,True)
    # Add vertical samples within the existing quad bands without changing
    # the original rim vertices or the continuous seam around either opening.
    refined=[];rows=42
    for row in range(rows+1):
        t=row/rows
        band=min(13,int(t*14));fraction=t*14-band
        for column in range(96):
            position=old[band*96+column].lerp(old[(band+1)*96+column],fraction)
            refined.append(position+relief(column/96,t))
    if any(refined[c]!=old[c] or refined[rows*96+c]!=old[14*96+c] for c in range(96)):
        raise ValueError('The original cup seams moved.')
    faces=[(r*96+c,(r+1)*96+c,(r+1)*96+(c+1)%96,r*96+(c+1)%96)
           for r in range(rows) for c in range(96)]
    material_slots=list(cup.data.materials)
    mesh=bpy.data.meshes.new(cup.name+' / sculpted quad fabric')
    mesh.from_pydata(refined,[],faces);mesh.update()
    for polygon in mesh.polygons:polygon.use_smooth=True
    for material in material_slots:mesh.materials.append(material)
    cup.data=mesh
    # A suspension web crosses the front dome. Fit its actual thin surface
    # outside the sculpted cup, keeping its belt and clasp endpoints intact.
    mesh.calc_loop_triangles()
    cup_tree=BVHTree.FromPolygons([v.co.copy() for v in mesh.vertices],
        [tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
    web=bpy.data.objects[f'01 / {label} garter / front suspension web']
    web_cage=bpy.data.objects[web['skinCage']]
    if web.data!=web_cage.data:raise ValueError('The real web lost its shared skin midsurface.')
    web_old=[v.co.copy() for v in web.data.vertices]
    if len(web_old)!=50:raise ValueError('Unexpected parent suspension web topology.')
    web.data.calc_loop_triangles()
    web_triangles=[tuple(t.vertices) for t in web.data.loop_triangles]
    web_tree=BVHTree.FromPolygons(web_old,web_triangles,all_triangles=True)
    web_params=[Vector((i%2,i//2/24,0)) for i in range(50)]
    hardware=[o for o in objects if o.parent==web]
    for obj in [web]+hardware:bind(obj,True)
    # Sample across the width as well as along the web: straight chords
    # between only two edges can enter the convex cup at face centers.
    web_rows=56;web_columns=5;web_points=[];sampled_contacts=0
    for row in range(web_rows+1):
        index=row/web_rows*24;band=min(23,int(index));fraction=index-band
        left_edge=web_old[band*2].lerp(web_old[(band+1)*2],fraction)
        right_edge=web_old[band*2+1].lerp(web_old[(band+1)*2+1],fraction)
        for column in range(web_columns):
            point=left_edge.lerp(right_edge,column/(web_columns-1))
            hit,normal,face,distance=cup_tree.ray_cast(Vector((point.x,-.20,point.z)),Vector((0,1,0)),.4)
            if hit is not None:
                point.y=min(point.y,hit.y-.0010);sampled_contacts+=1
            web_points.append(point)
    if [web_points[0],web_points[web_columns-1],web_points[-web_columns],web_points[-1]]!=[web_old[0],web_old[1],web_old[-2],web_old[-1]]:
        raise ValueError('The belt or clasp endpoints moved.')
    web_mesh=bpy.data.meshes.new(web.name+' / fitted front dome midsurface')
    web_mesh.from_pydata(web_points,[],[(web_columns*r+c,web_columns*(r+1)+c,
        web_columns*(r+1)+c+1,web_columns*r+c+1)
        for r in range(web_rows) for c in range(web_columns-1)])
    web_mesh.update()
    for polygon in web_mesh.polygons:polygon.use_smooth=True
    for material in web.data.materials:web_mesh.materials.append(material)
    web.data=web_cage.data=web_mesh
    def sample_web(u,t):
        index=min(web_rows,max(0.,t*web_rows));row=min(web_rows-1,int(index))
        width=min(web_columns-1,max(0.,u*(web_columns-1)))
        column=min(web_columns-2,int(width));fraction=width-column
        a=web_points[row*web_columns+column].lerp(web_points[row*web_columns+column+1],fraction)
        b=web_points[(row+1)*web_columns+column].lerp(web_points[(row+1)*web_columns+column+1],fraction)
        return a.lerp(b,index-row)
    for obj in hardware:
        values=[]
        for vertex in obj.data.vertices:
            point=vertex.co.copy();hit,normal,index,distance=web_tree.find_nearest(point)
            a,b,c=web_triangles[index]
            uv=barycentric_transform(hit,web_old[a],web_old[b],web_old[c],
                                     web_params[a],web_params[b],web_params[c])
            values.append(point+sample_web(uv.x,uv.y)-hit)
        obj.data.vertices.foreach_set('co',np.asarray([p[:] for p in values],np.float32).ravel());obj.data.update()
        allowed.add(obj.name)
    for modifier in web_cage.modifiers:
        modifier.show_viewport=True
        if modifier.type=='TRIANGULATE':modifier.quad_method='FIXED'
    for obj in [web]+hardware:bind(obj)
    allowed.update([web.name,web_cage.name])
    webs.append({'mesh':web.name,'cup':cup.name,'skinCage':web_cage.name,'rawVertices':len(web_points),
        'rawRows':web_rows+1,'rawColumns':web_columns,'frontCrossSectionSampled':True,
        'cupRaySamples':sampled_contacts,'minimumAuthoredClearance':.0010,
        'beltAndClaspEndpointsPreserved':True,'hardwareTransferredThroughActualWeb':True,
        'rigPresent':False,'motionVerified':False,'collisionVerified':False})
    print('ACTUAL_GARTER_WEB_FITTED',json.dumps(webs[-1]),flush=True)
    transferred=[]
    for obj in family:
        values=[];maximum=0.
        for vertex in obj.data.vertices:
            point=vertex.co.copy()
            hit,normal,index,distance=tree.find_nearest(point)
            if hit is None:raise ValueError('The real cup has no nearest surface for its sewn detail.')
            a,b,c=triangles[index]
            pa,pb,pc=[p.copy() for p in [params[a],params[b],params[c]]]
            # The cyclic seam spans u=0/1. Unwrap that triangle locally before
            # transferring its barycentric parameter, keeping the back seam continuous.
            if max(pa.x,pb.x,pc.x)-min(pa.x,pb.x,pc.x)>.5:
                for p in [pa,pb,pc]:
                    if p.x<.5:p.x+=1
            uv=barycentric_transform(hit,old[a],old[b],old[c],pa,pb,pc)
            delta=relief(uv.x,uv.y)
            values.append(point+delta);maximum=max(maximum,delta.length)
        obj.data.vertices.foreach_set('co',np.asarray([p[:] for p in values],np.float32).ravel())
        obj.data.update()
        transferred.append({'mesh':obj.name,'maximumSewnDetailDisplacement':maximum,
                            'sampledActualOldCupTriangles':True})
        if maximum>1e-8:allowed.add(obj.name)
    for obj in [cup]+family:bind(obj)
    allowed.add(cup.name)
    cup['garterDrapeSculptedFromOwnPhoto']=True
    cup['originalCupRimsPreserved']=True
    rim_hash=lambda pts:hashlib.sha256(np.asarray([p[:] for p in pts],np.float32).tobytes()).hexdigest()
    facing_unchanged=all(p['maximumSewnDetailDisplacement']<1e-8 for p in transferred
                         if 'top facing' in p['mesh'])
    if not facing_unchanged:raise ValueError('The photographed top facing must stay fixed.')
    entry={'mesh':cup.name,'rawColumns':96,'rawRows':rows+1,'rawVertices':len(refined),
        'originalTopRimSha256':rim_hash(old[:96]),'originalHemRimSha256':rim_hash(old[-96:]),
        'topAndPointedHemPreserved':True,'topFacingUnchanged':facing_unchanged,
        'originalTopFacingRawHashes':{obj.name:before[obj.name] for obj in family if 'top facing' in obj.name},
        'maximumFrontRelief':max(relief(c/96,r/rows).length for r in range(rows+1) for c in range(96)),
        'existingSewnDetailsTransferred':transferred,'rearReliefAdded':False,
        'measuredBodyFitVerified':False,'rigPresent':False,'motionVerified':False}
    drapes.append(entry)
    construction[cup.name]['rawVertices']=len(refined)
    construction[cup.name]['maximumRawDisplacement']=entry['maximumFrontRelief']
    print('ACTUAL_GARTER_DRAPE_SCULPTED',json.dumps(entry),flush=True)
for modifier in disabled:modifier.show_viewport=True
scene.frame_set(1)
changed=[name for name,digest in before.items() if raw_hash(bpy.data.objects[name])!=digest]
if set(changed)-allowed:raise ValueError('An unrelated raw garment changed: '+str(set(changed)-allowed))
pieces=[];deps=bpy.context.evaluated_depsgraph_get()
for obj in objects:
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv or not np.isfinite(np.asarray([d.uv[:] for d in uv.data])).all():raise ValueError('The sculpted garment UVs failed: '+obj.name)
    piece={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),'basePolygons':len(obj.data.polygons),
        'evaluatedVertices':len(mesh.vertices),'triangles':len(mesh.loop_triangles),'uvMaps':[u.name for u in mesh.uv_layers],
        'uvFinite':True,'parent':obj.parent.name if obj.parent else None,
        'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
        'rigPresent':False,'fidelityVerified':False}
    if obj.get('opaqueGeometryApertures'):piece.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):piece['actualThreadLoops']=obj['actualThreadLoops']
    if obj.get('actualSewingDashes'):piece['actualSewingDashes']=obj['actualSewingDashes']
    pieces.append(piece);evaluated.to_mesh_clear()
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_garter_drape.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
model=out/'foundation_garter_drape.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,
                         export_yup=True,export_animations=False)
report={**parent,'method':'own_photo_garter_front_dome_and_diagonal_seam_tension_folds',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),'pieces':pieces,
    'garterCupConstruction':list(construction.values()),'garterCupDrapeConstruction':drapes,
    'garterFrontWebConstruction':webs,
    'garterDetailMeshes':[o.name for o in objects if o.get('garterOwnPhotoDetail')],
    'inheritedInternalPieces':len(objects),'addedInternalPieces':0,'refinedInternalPieces':len(changed),
    'changedExistingRawMeshes':changed,'untouchedRawMeshesUnchanged':True,'existingCagesUnchanged':False,
    'completeExteriorVerticesUnchanged':True,'allLayersFinished':False,'rigPresent':False,'fidelityVerified':False,
    'motionVerified':False,'clothCollisionVerified':False,'additionalCreditsConsumed':0,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('GARTER_DRAPE_CHECKPOINT_SAVED',json.dumps({'pieces':len(pieces),'changedRawMeshes':len(changed),
    'triangles':sum(p['triangles'] for p in pieces),'completeExteriorUnchanged':True}),flush=True)
