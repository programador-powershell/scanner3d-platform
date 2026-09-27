"""Inspect physical holes and probe cloth-carrier translation without saving edits."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
record=json.loads(Path(args.generation).read_text(encoding='utf-8'))
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if digest(record['editableBlend'])!=record['editableBlendSha256']:
    raise ValueError('Editable checkpoint changed.')
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
for dependency in record.get('editableLibraryDependencies',[]):
    libraries=[library for library in bpy.data.libraries
               if Path(bpy.path.abspath(library.filepath)).name==dependency['file']]
    if len(libraries)!=1 or digest(bpy.path.abspath(libraries[0].filepath))!=dependency['sha256']:
        raise ValueError('The intact master library must reopen at its relative Git path.')
    meshes=[mesh for mesh in bpy.data.meshes if mesh.library==libraries[0]]
    if not meshes or any(not len(mesh.vertices) for mesh in meshes):
        raise ValueError('The linked exterior did not reopen as actual geometry.')
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
petticoat_partition=[]
for entry in record.get('petticoatSimulationCages',[]):
    cage=bpy.data.objects[entry['name']]
    visible=objects[entry['visibleFabric']]
    binding_error=None
    evaluated_displacement_probe=None
    point_followers=[m for m in visible.modifiers if m.type=='NODES' and m.node_group
                     and m.node_group.get('sameTopologySimulationTarget')==cage.name]
    surface_binding=any(m.type=='SURFACE_DEFORM' and m.target==cage and m.is_bound
                        for m in visible.modifiers)
    if point_followers:
        if len(point_followers)!=1 or list(visible.modifiers).index(point_followers[0])!=0:
            raise ValueError('The solved point positions must precede thickness and UV operations.')
        group=point_followers[0].node_group
        info=[n for n in group.nodes if n.bl_idname=='GeometryNodeObjectInfo']
        sample=[n for n in group.nodes if n.bl_idname=='GeometryNodeSampleIndex']
        if (len(info)!=1 or info[0].inputs['Object'].default_value!=cage
                or info[0].transform_space!='RELATIVE' or len(sample)!=1
                or sample[0].data_type!='FLOAT_VECTOR' or sample[0].domain!='POINT'):
            raise ValueError('Incorrect actual simulation point sampling graph.')
        downstream=list(visible.modifiers)[1:]
        flags=[m.show_viewport for m in downstream]
        perturbation=None
        try:
            for m in downstream:m.show_viewport=False
            source_points,target_points=coords(visible),coords(cage)
            if source_points.shape!=target_points.shape:
                raise ValueError('The actual solved point order changed.')
            binding_error=float(np.linalg.norm(source_points-target_points,axis=1).max())
            if not np.isfinite(source_points).all() or binding_error>1e-6:
                raise ValueError('Visible fabric does not sample actual solved positions.')
            # Deform only the evaluated target, without editing the shared raw
            # mesh. This distinguishes a working point follower from a pass-
            # through graph that happens to agree in the static rest shape.
            perturbation=cage.modifiers.new('Read-only evaluated carrier displacement probe','DISPLACE')
            perturbation.direction='NORMAL';perturbation.strength=.0015;perturbation.mid_level=0
            moved_source,moved_target=coords(visible),coords(cage)
            displacement=np.linalg.norm(moved_target-target_points,axis=1)
            error=float(np.linalg.norm(moved_source-moved_target,axis=1).max())
            if not np.isfinite(moved_source).all() or displacement.max()<.0005 or error>1e-6:
                raise ValueError('Visible petticoat did not follow the evaluated carrier deformation.')
            evaluated_displacement_probe={'maximumCarrierDisplacement':float(displacement.max()),
                'maximumFollowingError':error,'rawMeshEdited':False,'clothSimulationVerified':False}
        finally:
            if perturbation:cage.modifiers.remove(perturbation)
            for m,flag in zip(downstream,flags):m.show_viewport=flag
            bpy.context.view_layer.update()
    if (not cage.hide_render or cage.data!=visible.data
            or sum(m.type=='CLOTH' for m in cage.modifiers)!=1
            or any(m.type in {'NODES','SOLIDIFY'} for m in cage.modifiers)
            or any(m.type=='CLOTH' for m in visible.modifiers)
            or not any(m.type=='TRIANGULATE' and m.quad_method=='FIXED' for m in cage.modifiers)
            or not (surface_binding or binding_error is not None)):
        raise ValueError('A petticoat needs a single thin solver and an actual visible binding.')
    evaluated=visible.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv:raise ValueError('Actual petticoat UVs are missing.')
    data=np.asarray([v.uv[:] for v in uv.data])
    indices=np.asarray([t.loops[:] for t in mesh.loop_triangles])
    a,b,c=data[indices[:,0]],data[indices[:,1]],data[indices[:,2]]
    ab,ac=b-a,c-a
    fraction=float(np.mean(np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5>1e-12))
    evaluated.to_mesh_clear()
    if not np.isfinite(data).all() or fraction<.95:raise ValueError('Degenerate petticoat UV evaluation.')
    result={'visibleFabric':visible.name,'simulationCage':cage.name,'singleThinSolver':True,
            'fixedBindingTargetDiagonals':True,'uvNonDegenerateTriangleFraction':fraction,
            'dynamicSimulationVerified':False}
    if binding_error is not None:
        result.update(followMethod='same_topology_point_index',maximumSolvedPositionError=binding_error,
                      evaluatedCarrierDisplacementProbe=evaluated_displacement_probe)
    else:result['followMethod']='surface_deform'
    if visible.get('role')=='foundation_petticoat_cascade':
        columns=int(visible['cascadeColumns'])
        root=np.asarray([(visible.matrix_world @ v.co)[:] for v in visible.data.vertices[:columns]])
        main=bpy.data.objects['01 / long ivory gathered petticoat']
        seam=np.asarray([(main.matrix_world @ v.co)[:] for v in main.data.vertices[:192]])
        gap=float(distance_to_seam(root,seam).max())
        group=cage.vertex_groups['pinned']
        pin_rows=json.loads(visible['actualGatherPinRows'])
        expected=list(range(columns))+[r*columns for r in pin_rows]
        if gap>1e-6 or any(group.weight(i)<.999 for i in expected):
            raise ValueError('A gathered panel has a detached waist or missing drawstring pins.')
        if not any(m.type=='SURFACE_DEFORM' and m.target.name==main['simulationCage'] and m.is_bound
                   for m in cage.modifiers):raise ValueError('The gathered panel has no actual thin waist carrier.')
        result.update(maximumWaistRootGap=gap,measuredRootVertices=columns,
                      actualPinnedGatherStations=len(pin_rows),actualWaistAndGatherPinsVerified=True)
    petticoat_partition.append(result)
if petticoat_partition:print('PETTICOAT_THIN_SOLVERS_AND_SEAMS_VERIFIED',json.dumps(petticoat_partition),flush=True)
apertures=[]
trace=json.loads(Path(record['laceTrace']).read_text(encoding='utf-8'))
if record.get('additionalLaceTrace'):
    extra=json.loads(Path(record['additionalLaceTrace']).read_text(encoding='utf-8'))
    if extra['sourcePhotoSha256']!=record['sourcePhotoSha256']:
        raise ValueError('The lower lace belongs to another photo.')
    trace['tiles']+=extra['tiles']
for dependency in record.get('additionalLaceTraces',[]):
    if digest(dependency['file'])!=dependency['sha256']:
        raise ValueError('Changed additional photographic lace trace.')
    extra=json.loads(Path(dependency['file']).read_text(encoding='utf-8'))
    if extra['sourcePhotoSha256']!=record['sourcePhotoSha256']:
        raise ValueError('The corset lace belongs to another original photo.')
    trace['tiles']+=extra['tiles']
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
lower_construction=[]
stocking_anatomy=[]
bloomers=[o for o in objects.values() if o.get('role')=='foundation_bloomers']
if bloomers:
    if len(bloomers)!=1:
        raise ValueError('Expected one connected bloomer garment.')
    obj=bloomers[0]
    topology=holes(obj.data)
    boundary=boundary_loops(obj.data)
    if topology['components']!=1 or topology['eulerCharacteristic']!=-1 or len(boundary)!=3:
        raise ValueError('The bloomers must have one waist and two leg openings with a real shared crotch.')
    lower_construction.append({'mesh':obj.name,**topology,'boundaryLoops':len(boundary),
                                'connectedCrotchVerified':True,'motionVerified':False})
    stocks=[o for o in objects.values() if o.get('role')=='foundation_stocking']
    if len(stocks)!=2:
        raise ValueError('Both actual stocking legs and feet are required.')
    for obj in stocks:
        topology=holes(obj.data)
        boundary=boundary_loops(obj.data)
        if (topology['components']!=1 or topology['eulerCharacteristic']!=1 or len(boundary)!=1
                or obj.data.polygons[0].normal.x<=0):
            raise ValueError('The stocking foot must be closed with outward faces and one thigh opening.')
        lower_construction.append({'mesh':obj.name,**topology,'boundaryLoops':len(boundary),
                                    'closedToeVerified':True,'outwardLegFacesVerified':True,'motionVerified':False})
        if record.get('stockingAnatomyConstruction'):
            raw=np.asarray([v.co[:] for v in obj.data.vertices])
            if raw.shape!=(4289,3) or not np.isfinite(raw).all():
                raise ValueError('The refined stocking lost its connected ring topology.')
            obj.data.calc_loop_triangles()
            triangles=np.asarray([t.vertices[:] for t in obj.data.loop_triangles])
            area=np.linalg.norm(np.cross(raw[triangles[:,1]]-raw[triangles[:,0]],
                                        raw[triangles[:,2]]-raw[triangles[:,0]]),axis=1)*.5
            if float(area.min())<=1e-12:
                raise ValueError('The refined foot contains collapsed triangles.')
            rings=raw[:-1].reshape(67,64,3)
            foot=rings[30:].reshape(-1,3)
            centers=rings.mean(axis=1)
            stocking_anatomy.append({'mesh':obj.name,'measuredFromActualCage':True,
                'connectedFootVerified':True,'minimumTriangleArea':float(area.min()),
                'footBounds':{'min':foot.min(axis=0).tolist(),'max':foot.max(axis=0).tolist()},
                'measuredCenterline':centers[::6].tolist(),
                'ballSectionWidth':float(np.ptp(rings[54,:,0])),
                'closedToeVerified':True,'rigPresent':False,'bootContainmentVerified':False,
                'fidelityVerified':False,'clothCollisionVerified':False})
    for entry in record.get('additionalSimulationCages',[])+record.get('additionalSkinCages',[]):
        cage=bpy.data.objects[entry['name']]
        visible=objects[entry['visibleFabric']]
        expected_cloth=1 if 'simulationVerified' in entry else 0
        if (not cage.hide_render or cage.data!=visible.data
                or sum(m.type=='CLOTH' for m in cage.modifiers)!=expected_cloth
                or any(m.type=='CLOTH' for m in visible.modifiers)
                or not any(m.type=='SURFACE_DEFORM' and m.target==cage and m.is_bound for m in visible.modifiers)):
            raise ValueError('A lower fabric has a duplicated or disconnected carrier.')
        lower_construction.append({'mesh':visible.name,'carrier':cage.name,
                                    'actualClothSolvers':expected_cloth,'bindingVerified':True,
                                    'rigPresent':False,'motionVerified':False})
    print('FOUNDATION_LOWER_CONSTRUCTION_VERIFIED',json.dumps(lower_construction),flush=True)
garter_belt=[]
if record.get('garterBeltGatherConstruction'):
    entry=record['garterBeltGatherConstruction']
    belt=objects[entry['mesh']];cage=bpy.data.objects[entry['simulationCage']]
    columns=entry['rawColumns'];rows=entry['rawRows']
    if (len(belt.data.vertices)!=columns*rows or cage.data!=belt.data or not cage.hide_render
            or sum(m.type=='CLOTH' for m in cage.modifiers)!=1
            or any(m.type=='CLOTH' for m in belt.modifiers)):
        raise ValueError('The refined belt must retain one actual shared thin cloth solver.')
    if columns%entry['originalRootColumns']:raise ValueError('The original belt-ring samples must remain identifiable.')
    stride=columns//entry['originalRootColumns']
    rim=np.asarray([v.co[:] for v in belt.data.vertices[-columns:][::stride]],np.float32)
    if hashlib.sha256(rim.tobytes()).hexdigest()!=entry['originalStrapRootRingSha256']:
        raise ValueError('The original suspension-root ring changed.')
    pin=cage.vertex_groups['pinned']
    if {g.name for g in cage.vertex_groups}!=set(entry['originalClothGroupSchema']):
        raise ValueError('The new belt midsurface lost an actual Cloth group definition.')
    if next(m for m in cage.modifiers if m.type=='CLOTH').settings.vertex_group_mass!='pinned':
        raise ValueError('The actual thin belt solver no longer reads its restored pin field.')
    if entry['originalClothGroupSchema'].get('pressure')==entry['originalRootColumns']*9:
        pressure=cage.vertex_groups['pressure']
        if any(pressure.weight(i)<.999 for i in range(columns*rows)):
            raise ValueError('The original constant pressure field was not resampled onto the actual new mesh.')
    if any(pin.weight(i)<.999 for i in range(columns)):
        raise ValueError('The narrower elastic casing lost its actual waist pins.')
    gaps=[]
    for edge,name in enumerate(entry['frills']):
        frill=objects[name]
        root=np.asarray([v.co[:] for v in frill.data.vertices[:columns]])
        reference=np.asarray([v.co[:] for v in (belt.data.vertices[:columns] if edge==0 else belt.data.vertices[-columns:])])
        gap=float(np.linalg.norm(root-reference,axis=1).max())
        if gap>1e-6:raise ValueError('The real gathered belt frill has a detached seam.')
        gaps.append({'mesh':name,'maximumRawSeamGap':gap})
    # Test points along the real lace edges, not only their endpoints. A long
    # chord can have perfectly attached vertices while bridging a folded rim.
    lace=objects[entry['lowerPhotographicLace']]
    lower_frill=objects[entry['frills'][1]]
    lace_points=np.asarray([v.co[:] for v in lace.data.vertices])
    top_vertices={loop.vertex_index for loop,datum in zip(lace.data.loops,lace.data.uv_layers['PhotoLaceUV'].data)
                  if abs(datum.uv.y-1.)<1e-6}
    header_edges=[(a,b) for edge in lace.data.edges for a,b in [edge.vertices]
                  if a in top_vertices and b in top_vertices]
    if not header_edges:raise ValueError('The own-photo lace has no actual header edges.')
    header_samples=np.asarray([lace_points[a]*(1-t)+lace_points[b]*t
                               for a,b in header_edges for t in (0.,.25,.5,.75,1.)])
    frill_rim=np.asarray([v.co[:] for v in lower_frill.data.vertices[-columns:]])
    header_distances=np.concatenate([distance_to_seam(batch,frill_rim) for batch in
        np.array_split(header_samples,max(1,len(header_samples)//1024+1))])
    lace_header={'mesh':lace.name,'actualHeaderEdges':len(header_edges),'actualHeaderEdgeSamples':len(header_samples),
                 'sampleFractions':[0.,.25,.5,.75,1.],'maximumRawHeaderEdgeGap':float(header_distances.max()),
                 'measuredFromActualRawEdges':True,'maximumAllowedRawHeaderEdgeGap':.00025}
    if lace_header['maximumRawHeaderEdgeGap']>.00025:
        raise ValueError('The own-photo lace bridges or detaches from its actual curved frill: '+str(lace_header))
    uv_quality=[]
    for name in [belt.name,*entry['frills'],entry['lowerPhotographicLace'],
                 '01 / garter belt / looped lace edge 0',*entry['actualElasticSeamMeshes']]:
        obj=objects[name];evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
        uv=mesh.uv_layers.get('UVMap')
        if not uv:raise ValueError('The actual belt piece has no evaluated UVMap: '+name)
        values=np.asarray([d.uv[:] for d in uv.data]);indices=np.asarray([t.loops[:] for t in mesh.loop_triangles])
        a,b,c=values[indices[:,0]],values[indices[:,1]],values[indices[:,2]]
        ab,ac=b-a,c-a;fraction=float(np.mean(np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5>1e-12))
        evaluated.to_mesh_clear()
        if not np.isfinite(values).all() or fraction<.95:raise ValueError('Degenerate evaluated belt UVs: '+name)
        uv_quality.append({'mesh':name,'uvNonDegenerateTriangleFraction':fraction})
    threads=[]
    for name in entry['actualElasticSeamMeshes']:
        obj=objects[name];topology=holes(obj.data)
        if topology['components']!=1 or topology['eulerCharacteristic']!=0 or boundary_loops(obj.data):
            raise ValueError('A real continuous elastic stitch has an open seam.')
        threads.append({'mesh':name,'actualClosedThreadLoopVerified':True})
    garter_belt.append({'mesh':belt.name,'simulationCage':cage.name,'measuredFromActualMeshes':True,
        'singleThinClothSolver':True,'originalStrapRootRingVerified':True,'actualWaistPinsVerified':True,
        'actualClothGroupSchemaVerified':True,'actualPressureFieldVerified':True,
        'rawColumns':columns,'rawRows':rows,'frillSeams':gaps,'evaluatedUvQuality':uv_quality,
        'actualElasticSeamMeshes':threads,'lowerPhotographicLace':entry['lowerPhotographicLace'],
        'actualLaceHeaderSeam':lace_header,
        'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False})
    print('FOUNDATION_GARTER_BELT_CONSTRUCTION_VERIFIED',json.dumps(garter_belt),flush=True)

garter_drapes=[]
for entry in record.get('garterCupDrapeConstruction',[]):
    cup=objects[entry['mesh']]
    columns=entry['rawColumns']
    rim_hash=lambda pts:hashlib.sha256(np.asarray([v.co[:] for v in pts],np.float32).tobytes()).hexdigest()
    if (len(cup.data.vertices)!=columns*entry['rawRows']
            or rim_hash(cup.data.vertices[:columns])!=entry['originalTopRimSha256']
            or rim_hash(cup.data.vertices[-columns:])!=entry['originalHemRimSha256']):
        raise ValueError('A sculpted garter cup lost its original rim geometry.')
    for name,expected in entry['originalTopFacingRawHashes'].items():
        obj=objects[name]
        values=np.empty(len(obj.data.vertices)*3,np.float32)
        obj.data.vertices.foreach_get('co',values)
        actual=hashlib.sha256(values.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()
        if actual!=expected:raise ValueError('The original garter facing geometry changed: '+name)
    cup.data.calc_loop_triangles()
    values=np.asarray([v.co[:] for v in cup.data.vertices])
    triangles=np.asarray([t.vertices[:] for t in cup.data.loop_triangles])
    a,b,c=values[triangles[:,0]],values[triangles[:,1]],values[triangles[:,2]]
    areas=np.linalg.norm(np.cross(b-a,c-a),axis=1)*.5
    if not np.isfinite(values).all() or areas.min()<=1e-12:
        raise ValueError('The sculpted cup has collapsed actual fabric triangles.')
    garter_drapes.append({'mesh':cup.name,'measuredFromActualCage':True,
        'originalTopAndHemVerified':True,'originalTopFacingVerified':True,
        'rawVertices':len(values),'minimumTriangleArea':float(areas.min()),
        'rigPresent':False,'motionVerified':False})
garter_webs=[]
for entry in record.get('garterFrontWebConstruction',[]):
    cup=objects[entry['cup']]
    web=objects[entry['mesh']]
    deps=bpy.context.evaluated_depsgraph_get()
    evaluated=cup.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    points=[evaluated.matrix_world @ v.co for v in mesh.vertices]
    tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
    evaluated.to_mesh_clear()
    evaluated=web.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    vertices=[evaluated.matrix_world @ v.co for v in mesh.vertices]
    samples=vertices+[sum((vertices[i] for i in triangle.vertices),Vector())/3 for triangle in mesh.loop_triangles]
    evaluated.to_mesh_clear()
    clearances=[]
    for point in samples:
        hit,normal,index,distance=tree.ray_cast(Vector((point.x,-.20,point.z)),Vector((0,1,0)),.4)
        if hit is not None:clearances.append(float(hit.y-point.y))
    if len(clearances)<15 or min(clearances)<.00015:
        raise ValueError('The evaluated suspension web intersects its sculpted cup: '+web.name+' '+str(min(clearances,default=0.)))
    garter_webs.append({'mesh':web.name,'cup':cup.name,'measuredFromEvaluatedGeometry':True,
        'actualSampledClearances':len(clearances),'minimumMeasuredFrontClearance':min(clearances),
        'verticesAndTriangleCentroidsSampled':True,'restSeparationVerified':True,
        'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False})
garter_details=[]
if record.get('garterCupConstruction'):
    details=[o for o in objects.values() if o.get('garterOwnPhotoDetail')]
    cups=[objects[p['mesh']] for p in record['garterCupConstruction']]
    for obj in cups+details:
        cup=obj if obj in cups else obj.parent
        if cup not in cups:
            raise ValueError('The garter detail has no actual cup carrier.')
        stocking=cup.parent
        target=bpy.data.objects[stocking['skinCage']]
        if not any(m.type=='SURFACE_DEFORM' and m.target==target and m.is_bound for m in obj.modifiers):
            raise ValueError('An actual garter detail is not bound to its stocking carrier.')
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles()
        uv=mesh.uv_layers.get('UVMap')
        if not uv:
            raise ValueError('A refined garter piece has no evaluated UVs.')
        values=np.asarray([d.uv[:] for d in uv.data])
        loops=np.asarray([t.loops[:] for t in mesh.loop_triangles])
        a,b,c=values[loops[:,0]],values[loops[:,1]],values[loops[:,2]]
        ab,ac=b-a,c-a
        fraction=float(np.mean(np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5>1e-12))
        evaluated.to_mesh_clear()
        if not np.isfinite(values).all() or fraction<.95:
            raise ValueError('Excessive collapsed UV triangles in an actual garter detail: '+obj.name)
        topology=holes(obj.data)
        if obj in cups and (topology['components']!=1 or len(boundary_loops(obj.data))!=2):
            raise ValueError('A refined cup lost its continuous open garment topology.')
        if obj.get('actualSewingDashes') and (topology['components']!=obj['actualSewingDashes']
                or topology['eulerCharacteristic']!=2*obj['actualSewingDashes']):
            raise ValueError('The visible sewing dashes are not actual closed thread geometry.')
        garter_details.append({'mesh':obj.name,'cup':cup.name,'actualSkinCarrier':target.name,
            'bindingVerified':True,'measuredFromActualMesh':True,
            'uvNonDegenerateTriangleFraction':fraction,'rawTopology':topology,
            'actualSewingDashes':int(obj.get('actualSewingDashes',0)),
            'rigPresent':False,'motionVerified':False})
    expected_details=set(record.get('garterDetailMeshes',[]))
    if ((expected_details and {o.name for o in details}!=expected_details)
            or (not expected_details and len(details)!=record['addedInternalPieces'])):
        raise ValueError('A newly authored garter piece escaped the actual detail audit.')
    print('FOUNDATION_GARTER_DETAILS_VERIFIED',len(garter_details),flush=True)
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
        'petticoatSolverPartitionAudit':petticoat_partition,
        'actualLowerConstructionAudit':lower_construction,
        'actualStockingAnatomyAudit':stocking_anatomy,
        'actualGarterDetailAudit':garter_details,
        'actualGarterDrapeAudit':garter_drapes,
        'actualGarterWebContactAudit':garter_webs,
        'actualGarterBeltAudit':garter_belt,
        'actualInternalObjects':len(objects),'attachmentRoots':[o.name for o in roots],
        'verifiedFollowers':len(covered),'allActualFollowersCovered':True,
        'savedModelUnchanged':True,'rigPresent':False,'motionVerified':False,
        'clothCollisionVerified':False,'limitation':'Frame-1 attachment probe only; no gameplay or dynamic simulation approval.'}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_ATTACHMENT_AUDIT',json.dumps({'actualInternalObjects':len(objects),
      'verifiedFollowers':len(covered),'allActualFollowersCovered':True}),flush=True)
