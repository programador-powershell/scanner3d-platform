"""Refine the actual stockings' foot volume and fit their rest stance to Alice.

The original complete scan supplies measurements, never extracted geometry.
Photo 1 supplies the stocking design. Keep all other raw garment meshes and
the complete exterior unchanged, preserving the existing cascade construction.
"""
import argparse, hashlib, json, math, shutil, sys
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
for field in ['model','editableBlend','sourcePhoto','lowerBoneMeasurements']:
    if sha(parent[field])!=parent[field+'Sha256']:raise ValueError('Changed parent evidence: '+field)
if parent['sourcePhotoSha256']!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('The stockings require their unchanged original foundation photo.')
out=Path(args.output)
if out.exists():raise ValueError('Use a new complete modeling checkpoint.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies',[]):
    source=Path(parent['editableBlend']).parent/dependency['file']
    if sha(source)!=dependency['sha256']:raise ValueError('The intact master library changed.')
    shutil.copyfile(source,out/dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene
scene.frame_set(1)

def cage_hash(obj):
    values=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',values)
    return hashlib.sha256(values.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()

objects=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]
before={o.name:cage_hash(o) for o in scene.objects if o.type=='MESH'}
disabled=[]
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            disabled.append(modifier);modifier.show_viewport=False
whole=next(o for o in scene.objects if o.type=='MESH' and o.data.library)
scan=np.asarray([(whole.matrix_world @ v.co)[:] for v in whole.data.vertices])
measurements=json.loads(Path(parent['lowerBoneMeasurements']).read_text(encoding='utf-8'))
allowed=set()
fits=[]

def interpolation(z,knots):
    """Monotone Hermite centerline, without independent flattened zigzags."""
    pairs=sorted(knots)
    if z<=pairs[0][0]:return pairs[0][1]
    if z>=pairs[-1][0]:return pairs[-1][1]
    widths=np.diff([p[0] for p in pairs])
    slopes=np.diff([p[1] for p in pairs])/widths
    derivatives=[float(slopes[0])]
    for i in range(1,len(pairs)-1):
        left,right=slopes[i-1],slopes[i]
        if left*right<=0:derivatives.append(0.)
        else:
            w1=2*widths[i]+widths[i-1];w2=widths[i]+2*widths[i-1]
            derivatives.append(float((w1+w2)/(w1/left+w2/right)))
    derivatives.append(0.)
    for i,((a,x),(b,y)) in enumerate(zip(pairs,pairs[1:])):
        if a<=z<=b:
            t=(z-a)/(b-a)
            return (2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*(b-a)*derivatives[i]+(-2*t**3+3*t*t)*y+(t**3-t*t)*(b-a)*derivatives[i+1]

for side,label in [(1,'left'),(-1,'right')]:
    obj=bpy.data.objects[f'01 / {label} stocking / fitted leg ankle and closed toe']
    cage=bpy.data.objects[obj['skinCage']]
    if cage.data!=obj.data or len(obj.data.vertices)!=4289:raise ValueError('Unexpected actual stocking loft.')
    raw=np.asarray([v.co[:] for v in obj.data.vertices])
    upper_center=raw[:64].mean(axis=0)
    foot=scan[(scan[:,2]<.09)&(scan[:,0]*side>0)]
    if len(foot)<100:raise ValueError('The actual preserved scan has no usable boot guide.')
    def boot_center(z):
        # Above the boot shaft, the same height intersects the skirt. Restrict
        # the measurement to the boot corridor; never crop the actual master.
        mask=(np.abs(scan[:,2]-z)<.012)&(scan[:,0]*side>.035)&(scan[:,0]*side<.13)
        mask&=(scan[:,1]>-.04)&(scan[:,1]<.05)
        points=scan[mask]
        if len(points)<20:raise ValueError('Missing actual boot cross-section.')
        # Robust lateral center from the measured outer envelope, not a body mesh.
        return float((np.quantile(points[:,0],.05)+np.quantile(points[:,0],.95))*.5)
    heel_center=boot_center(.077)
    calf_center=boot_center(.16)
    upper_boot_center=boot_center(.235)
    foot_center=float((np.quantile(foot[:,0],.05)+np.quantile(foot[:,0],.95))*.5)
    knee_center=float(upper_center[0])+(upper_boot_center-float(upper_center[0]))*(.40-.31)/(.40-.235)
    x_knots=[(.039,foot_center),(.077,heel_center),(.16,calf_center),
             (.235,upper_boot_center),(.31,knee_center),(.40,float(upper_center[0]))]
    dx_knots=[(z,x-float(upper_center[0])) for z,x in x_knots]
    front=float(foot[:,1].min())+.004
    heel_back=float(foot[:,1].max())-.004
    fore=foot[(foot[:,1]<-.025)&(foot[:,2]<.045)]
    toe_width=float((np.quantile(fore[:,0],.95)-np.quantile(fore[:,0],.05))*.95)
    toe_width=max(.032,min(.048,toe_width))
    ankle=Vector(measurements['bones'][label.title()+'Foot']['head'])
    refined=raw.copy()
    for row in range(30):
        for c in range(64):
            i=row*64+c
            refined[i,0]+=interpolation(raw[i,2],dx_knots)
    def bezier(points,t):
        a,b,c,d=[np.asarray(p,dtype=float) for p in points]
        value=(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
        derivative=3*(1-t)**2*(b-a)+6*(1-t)*t*(c-b)+3*t*t*(d-c)
        return value,derivative
    # A continuous quarter-turn gives the heel and instep a smooth silhouette.
    # Cross-sections retain the same connected quad topology and UV layout.
    heel_path=[(ankle.y,.077),(ankle.y,.047),(.012,.021),(-.013,.019)]
    fore_path=[(-.013,.019),(-.030,.019),(front+.022,.019),(front+.011,.019)]
    for row in range(30,67):
        if row<=48:
            t=(row-30)/18
            yz,tangent_yz=bezier(heel_path,t)
            rx=.0148+(.0215-.0148)*(t*t*(3-2*t))
            ry=.020+(.013-.020)*(t*t*(3-2*t))
        elif row<=60:
            t=(row-48)/12
            yz,tangent_yz=bezier(fore_path,t)
            rx=.0215+(toe_width*.5-.0215)*(t*t*(3-2*t))
            ry=.013+(.012-.013)*(t*t*(3-2*t))
        else:
            t=(row-60)/6
            yz=np.asarray([front+.011*(1-math.sin(math.pi*t*.5)),.019])
            tangent_yz=np.asarray([-1.,0.])
            rx=max(.0008,toe_width*.5*math.cos(math.pi*t*.5))
            ry=max(.0008,.012*math.cos(math.pi*t*.5))
        center=Vector((interpolation(float(yz[1]),x_knots),float(yz[0]),float(yz[1])))
        tangent=Vector((0,float(tangent_yz[0]),float(tangent_yz[1]))).normalized()
        other=tangent.cross(Vector((1,0,0))).normalized()
        for c in range(64):
            theta=c/64*math.tau
            wrinkle=.00045*math.exp(-((center.z-.062)/.014)**2)*math.sin(46*center.z/.10+.45*math.cos(theta*3))
            p=center+Vector((1,0,0))*(rx+wrinkle)*math.cos(theta)+other*(ry+wrinkle)*math.sin(theta)
            medial=max(0,-side*math.cos(theta))
            arch=.003*math.exp(-((p.y+.024)/.017)**2)*medial*max(0,-math.sin(theta))**2
            p.z=max(p.z,.005+arch)
            refined[row*64+c]=p[:]
    refined[-1]=[interpolation(.019,x_knots),front,.019]
    high=raw[:,2]>=.40
    if not np.array_equal(refined[high],raw[high]):raise ValueError('The existing high-thigh seam moved.')
    if not np.isfinite(refined).all():raise ValueError('Non-finite foot positions.')
    # Reconstruct all real upper-leg trims in the fitted rest position. Their
    # high-thigh roots remain unchanged, so the garter cups stay sewn in place.
    for trim in objects:
        if trim.parent==obj and trim.get('role')=='foundation_stocking_trim':
            values=np.asarray([v.co[:] for v in trim.data.vertices])
            values[:,0]+=[interpolation(float(z),dx_knots) for z in values[:,2]]
            trim.data.vertices.foreach_set('co',values.astype(np.float32).ravel());trim.data.update()
            allowed.add(trim.name)
    # Unbind before changing target geometry/triangulation; rebuild every actual
    # attachment to this stocking carrier in the new rest shape.
    bindings=[]
    for follower in scene.objects:
        for modifier in follower.modifiers:
            if modifier.type=='SURFACE_DEFORM' and modifier.target==cage:
                bindings.append((follower,modifier))
                bpy.ops.object.select_all(action='DESELECT');follower.select_set(True)
                bpy.context.view_layer.objects.active=follower
                modifier.show_viewport=True
                if modifier.is_bound:bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    obj.data.vertices.foreach_set('co',refined.astype(np.float32).ravel());obj.data.update()
    for modifier in cage.modifiers:
        modifier.show_viewport=True
        if modifier.type=='TRIANGULATE':modifier.quad_method='FIXED'
    for follower,modifier in bindings:
        bpy.ops.object.select_all(action='DESELECT');follower.select_set(True)
        bpy.context.view_layer.objects.active=follower
        bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
        if not modifier.is_bound:raise ValueError('Actual fitted stocking attachment failed: '+follower.name)
    allowed.update([obj.name,cage.name])
    obj['footRefinedFromOwnPhoto']=True
    obj['nativeScanRestStanceMeasured']=True
    fits.append({'mesh':obj.name,'skinCage':cage.name,'rawVertices':len(refined),
        'bootRegionVerticesMeasured':len(foot),'measuredBootBounds':{'min':foot.min(axis=0).tolist(),'max':foot.max(axis=0).tolist()},
        'restCenterlineTargets':x_knots,'toeWidth':toe_width,'toeFrontY':front,'heelRearGuideY':heel_back,
        'bootGuideExcludesSkirt':True,'heelInstepContinuousBezier':True,
        'originalUpperThighPreserved':True,'closedTopologyPreserved':True,
        'heelAndArchInferredFromPhoto':True,'bootContainmentVerified':False,'rigPresent':False})
    print('ACTUAL_STOCKING_ANATOMY_REFINED',json.dumps(fits[-1]),flush=True)

for modifier in disabled:modifier.show_viewport=True
scene.frame_set(1)
changed=[name for name,digest in before.items() if cage_hash(bpy.data.objects[name])!=digest]
if set(changed)-allowed:raise ValueError('An unrelated garment or the complete exterior changed.')
pieces=[];deps=bpy.context.evaluated_depsgraph_get()
for obj in objects:
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv or not np.isfinite(np.asarray([d.uv[:] for d in uv.data])).all():raise ValueError('Actual refined garment UVs failed.')
    piece={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),'basePolygons':len(obj.data.polygons),
        'evaluatedVertices':len(mesh.vertices),'triangles':len(mesh.loop_triangles),'uvMaps':[u.name for u in mesh.uv_layers],
        'uvFinite':True,'parent':obj.parent.name if obj.parent else None,
        'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
        'rigPresent':False,'fidelityVerified':False}
    if obj.get('opaqueGeometryApertures'):piece.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):piece['actualThreadLoops']=obj['actualThreadLoops']
    pieces.append(piece);evaluated.to_mesh_clear()
for library in bpy.data.libraries:library.filepath='//'+Path(bpy.path.abspath(library.filepath)).name
editable=out/'chapeleiro_foundation_stocking_anatomy.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
model=out/'foundation_stocking_anatomy.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_apply=True,
                         export_yup=True,export_animations=False)
report={**parent,'method':'own_photo_stocking_rounded_toes_heel_arch_and_native_scan_rest_stance',
    'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
    'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),'pieces':pieces,
    'existingCagesUnchanged':False,'untouchedRawMeshesUnchanged':True,'changedExistingRawMeshes':changed,
    'stockingAnatomyConstruction':fits,'inheritedInternalPieces':len(objects),'addedInternalPieces':0,'refinedInternalPieces':2,
    'completeExteriorVerticesUnchanged':True,'allLayersFinished':False,'rigPresent':False,'fidelityVerified':False,
    'motionVerified':False,'clothCollisionVerified':False,'additionalCreditsConsumed':0,'nextVariantMayStart':False}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('STOCKING_ANATOMY_CHECKPOINT_SAVED',json.dumps({'pieces':len(pieces),'changedRawMeshes':changed,
    'triangles':sum(p['triangles'] for p in pieces),'exteriorUnchanged':True}),flush=True)
