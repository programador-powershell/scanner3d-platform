"""Export the whole Chapeleiro with disconnected, Head-rigged individual fiber ribbons."""
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--draco',action='store_true',help='Measure whole-character geometry compression for future individual-fiber checkpoint')
p.add_argument('--draco-generic-bits',type=int,default=0,help='Generic attribute quantization bits; 0 preserves exact fiber and guide IDs')
p.add_argument('--image-format',choices=['AUTO','WEBP','JPEG'],default='AUTO')
p.add_argument('--image-quality',type=int,default=100)
p.add_argument('--fiber-count',type=int,default=-1,help='Bounded full-character export probe; -1 means every fiber')
p.add_argument('--fiber-width-scale',type=float,default=1.0,help='Non-destructive ribbon-width study; 1 preserves source radius')
p.add_argument('--fiber-tone-variation',action='store_true',help='Use stable dark per-fiber fallback tone instead of one uniform fallback')
p.add_argument('--individual-reflection-tones',action='store_true',help='Export two stable PBR tones for individual black hair strands')
p.add_argument('--hair-roughness',type=float,default=.42,help='Base roughness of unprojected dark fibers')
p.add_argument('--hair-specular',type=float,default=.5,help='Specular IOR level of unprojected dark fibers')
p.add_argument('--samples',type=int,default=24)
p.add_argument('--chunk-size',type=int,default=2048)
p.add_argument('--projection-atlas',help='Local UV projection probe; requires --alignment')
p.add_argument('--alignment',help='Four-view 2D registration report')
p.add_argument('--hair-mask',help='Conservative 4K source-image hair-only mask')
p.add_argument('--depth-gate-mm',type=float,default=0,help='Screen-space self-occlusion gate on painted fiber faces; 0 disables')
p.add_argument('--body-occlusion',action='store_true',help='Reject projected hair hidden behind the remaining body, dress or hat mesh')
p.add_argument('--strict-projection',action='store_true',help='Require endpoints and interior UV samples to remain in hair-only paint')
p.add_argument('--flow-angle-deg',type=float,default=0,help='Reject painted segments whose UV tangent differs from local painted strand flow; 0 disables')
p.add_argument('--flow-coherence-min',type=float,default=.6,help='Minimum 2D structure-tensor coherence for flow-gated paint')
p.add_argument('--guide-family-source',help='NPZ containing the original guide_families for paint-family audit')
p.add_argument('--unpainted-guide-families',default='',help='Comma-separated interior guide families kept on the dark fallback material')
p.add_argument('--audit-roi',help='Optional painted-guide tally in one render view: view:x0:y0:x1:y1 at 768px')
p.add_argument('--runtime-hair-attributes',action='store_true',help='Export per-fiber identity and root-to-tip factor for verified runtime deformation')
p.add_argument('--include-rear-braid',action='store_true',help='Include separately authored individual rear braid fibers in the complete character')
p.add_argument('--audit-only',action='store_true',help='Measure UV gates on the full character without writing a GLB')
p.add_argument('--audit-force-view',choices=['front','left','right','back'],help='Diagnostic only: assign all sampled segments to one view')
p.add_argument('--audit-alternate-views',action='store_true',help='Diagnostic only: test all other views for rejected segments; never changes exported UVs')
p.add_argument('--audit-hair-bvh',action='store_true',help='Diagnostic only: compare center depth map with actual sampled ribbon ray hits')
p.add_argument('--audit-hair-bvh-gate',action='store_true',help='Diagnostic only: use near ribbon hit instead of center depth gate for sampled fibers')
p.add_argument('--audit-hair-bvh-mesh',action='store_true',help='Diagnostic only: construct BVH through a vectorized Blender mesh')
p.add_argument('--audit-bvh-full-hair',action='store_true',help='Diagnostic only: test sampled fibers against the full 101424-fiber ribbon BVH')
p.add_argument('--audit-select-visible-view',action='store_true',help='Diagnostic only: select an eligible UV view using the full hair BVH before painting sampled ribbons')
p.add_argument('--audit-hair-three-samples',action='store_true',help='Diagnostic only: require 20%, 50%, and 80% of each ribbon segment to be frontmost')
p.add_argument('--audit-render-preview',action='store_true',help='Diagnostic only: render the complete dressed authoring scene with sampled UV ribbons over original hair')
p.add_argument('--audit-preview-hide-source-hair',action='store_true',help='Diagnostic render only: hide original authored hair to inspect the sampled projected ribbons')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
assert 0<=a.draco_generic_bits<=30
assert not a.audit_force_view or a.audit_only
assert not a.audit_alternate_views or a.audit_only
assert not a.audit_hair_bvh or (a.audit_only and a.projection_atlas and a.depth_gate_mm and ((a.fiber_count==-1 and a.audit_hair_bvh_mesh) or 0<a.fiber_count<=10000))
assert not a.audit_hair_bvh_gate or a.audit_hair_bvh
assert not a.audit_hair_bvh_mesh or a.audit_hair_bvh
assert not a.audit_bvh_full_hair or (a.audit_only and a.audit_hair_bvh and a.audit_hair_bvh_mesh and
                                     (a.fiber_count==-1 or 0<a.fiber_count<=10000))
assert not a.audit_select_visible_view or (a.audit_bvh_full_hair and a.audit_hair_bvh_gate and not a.audit_force_view)
assert not a.audit_hair_three_samples or (a.audit_only and a.audit_bvh_full_hair and a.audit_hair_bvh_gate)
assert not a.audit_render_preview or (a.audit_only and a.projection_atlas and
                                      (a.fiber_count==-1 or 0<a.fiber_count<=10000))
assert not a.audit_preview_hide_source_hair or a.audit_render_preview
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
assert not a.include_rear_braid or (a.fiber_count==-1 and not a.projection_atlas and not a.audit_only and 'rearBraidStrandStudy' in g)
source_metadata=g
while 'posteriorBodice' not in source_metadata:
    assert 'parentGeneration' in source_metadata, 'Posterior bodice metadata missing from generation ancestry'
    source_metadata=json.loads(Path(source_metadata['parentGeneration']).read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
whole=bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
rig=next(m.object for m in whole.modifiers if m.type=='ARMATURE')
mask=whole.data.attributes['alice_original_hair_review_mask'];hair_faces={i for i,v in enumerate(mask.data) if v.value}
original_faces=len(whole.data.polygons);original_vertices=len(whole.data.vertices)
whole.name='Alice / complete body and dress / individual hair checkpoint'
for mod in list(whole.modifiers):
    if mod.type!='ARMATURE':whole.modifiers.remove(mod)
bm=bmesh.new();bm.from_mesh(whole.data);bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[face for i,face in enumerate(bm.faces) if i in hair_faces],context='FACES')
isolated=[v for v in bm.verts if not v.link_faces]
if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
bm.to_mesh(whole.data);bm.free();whole.data.update()
assert len(whole.data.polygons)+len(hair_faces)==original_faces

source_hair=next(o for o in bpy.context.scene.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
C=len(source_hair.data.curves);N=len(source_hair.data.points)//C
assert 8<=a.samples<=N and a.chunk_size>0 and (a.fiber_count==-1 or 1<=a.fiber_count<=C)
assert .15<=a.fiber_width_scale<=1.5
assert 0<=a.hair_roughness<=1 and 0<=a.hair_specular<=1
assert not (a.individual_reflection_tones and a.projection_atlas)
v=np.empty(len(source_hair.data.points)*3,np.float32);source_hair.data.attributes['position'].data.foreach_get('vector',v);v=v.reshape(C,N,3)
r=np.empty(len(source_hair.data.points),np.float32);source_hair.data.attributes['radius'].data.foreach_get('value',r);r=r.reshape(C,N)
selected_fiber_ids=np.arange(C) if a.fiber_count==-1 else np.linspace(0,C-1,a.fiber_count,dtype=int)
guide_ids=np.empty(C,np.int32)
source_hair.data.attributes['guide_id'].data.foreach_get('value',guide_ids)
guide_families=np.full(int(guide_ids.max())+1,'added',dtype='<U32')
if a.guide_family_source:
    original_families=np.load(a.guide_family_source)['guide_families']
    assert len(original_families)<=len(guide_families)
    guide_families[:len(original_families)]=original_families
    family_count_keys=('newLowerGuides','newProfileGuides','interiorGuidesAdded','newFrontUndercoatGuides')
    family_metadata=g
    while not all(key in family_metadata for key in family_count_keys):
        assert 'parentGeneration' in family_metadata, 'Guide-family additions missing from generation ancestry'
        family_metadata=json.loads(Path(family_metadata['parentGeneration']).read_text(encoding='utf-8'))
    additions=[('lower_locks',family_metadata['newLowerGuides']),
               ('profile_locks',family_metadata['newProfileGuides']),
               ('interior_back_waves',family_metadata['interiorGuidesAdded']),
               ('front_undercoat',family_metadata['newFrontUndercoatGuides'])]
    offset=len(original_families)
    for family,count in additions:
        guide_families[offset:offset+count]=family
        offset+=count
    assert offset==len(guide_families),(offset,len(guide_families))
unpainted_families={x.strip() for x in a.unpainted_guide_families.split(',') if x.strip()}
assert not unpainted_families or a.guide_family_source
audit_roi=None
if a.audit_roi:
    parts=a.audit_roi.split(':')
    assert len(parts)==5 and parts[0] in ('front','back','left','right')
    audit_roi=(parts[0],tuple(map(int,parts[1:])))
    assert 0<=audit_roi[1][0]<audit_roi[1][2]<=768 and 0<=audit_roi[1][1]<audit_roi[1][3]<=768
sample=np.linspace(0,N-1,a.samples).round().astype(int)
mat=bpy.data.materials.new('Alice / individual dark hair ribbons / checkpoint');mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.025,.020,.019,1);bs.inputs['Roughness'].default_value=a.hair_roughness
if 'Specular IOR Level' in bs.inputs:bs.inputs['Specular IOR Level'].default_value=a.hair_specular
mat.use_backface_culling=False
fallback_mat=mat
assert bool(a.projection_atlas)==bool(a.alignment)
assert not a.hair_mask or a.projection_atlas
assert not a.body_occlusion or a.projection_atlas
assert 0<=a.flow_angle_deg<=90 and (not a.flow_angle_deg or a.projection_atlas)
assert 0<=a.flow_coherence_min<=1
assert 0<=a.depth_gate_mm<=20 and (not a.depth_gate_mm or a.projection_atlas)
projection=None
fallback_palette=[fallback_mat]
if a.individual_reflection_tones:
    dark=fallback_mat.copy();dark.name='Alice / black individual fiber base / PBR'
    dark_bs=dark.node_tree.nodes.get('Principled BSDF')
    dark_bs.inputs['Base Color'].default_value=(.012,.010,.013,1)
    dark_bs.inputs['Roughness'].default_value=.46
    if 'Specular IOR Level' in dark_bs.inputs:dark_bs.inputs['Specular IOR Level'].default_value=.65
    light=fallback_mat.copy();light.name='Alice / individual fiber reflected tone / PBR'
    light_bs=light.node_tree.nodes.get('Principled BSDF')
    light_bs.inputs['Base Color'].default_value=(.022,.019,.019,1)
    light_bs.inputs['Roughness'].default_value=.38
    if 'Specular IOR Level' in light_bs.inputs:light_bs.inputs['Specular IOR Level'].default_value=.65
    fallback_palette=[dark,light]
if a.projection_atlas:
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    info=json.loads(Path(a.alignment).read_text(encoding='utf-8'))
    assert info['allViewsProjectionApproved'] is False
    by_view={row['renderView']:row for row in info['views']}
    assert set(by_view)=={'front','back','left','right'}
    assert all(row['status'] in ('estimated','provisional_from_opposite_profile') for row in by_view.values())
    atlas=bpy.data.images.load(a.projection_atlas,check_existing=False)
    assert tuple(atlas.size)==(4096,4096)
    import cv2
    atlas_pixels=cv2.imread(a.projection_atlas,cv2.IMREAD_UNCHANGED)
    assert atlas_pixels.shape[:2]==(4096,4096)
    flow_x=flow_y=flow_coherence=None
    if a.flow_angle_deg:
        flow_x=np.empty((4096,4096),np.float16)
        flow_y=np.empty((4096,4096),np.float16)
        flow_coherence=np.empty((4096,4096),np.float16)
        for y0 in (0,2048):
            for x0 in (0,2048):
                tile=atlas_pixels[y0:y0+2048,x0:x0+2048,:3]
                gray=cv2.cvtColor(tile,cv2.COLOR_BGR2GRAY).astype(np.float32)
                gx=cv2.Sobel(gray,cv2.CV_32F,1,0,ksize=3)
                gy=cv2.Sobel(gray,cv2.CV_32F,0,1,ksize=3)
                jxx=cv2.GaussianBlur(gx*gx,(0,0),3)
                jyy=cv2.GaussianBlur(gy*gy,(0,0),3)
                jxy=cv2.GaussianBlur(gx*gy,(0,0),3)
                angle=.5*np.arctan2(2*jxy,jxx-jyy)
                flow_x[y0:y0+2048,x0:x0+2048]=(-np.sin(angle)).astype(np.float16)
                flow_y[y0:y0+2048,x0:x0+2048]=np.cos(angle).astype(np.float16)
                flow_coherence[y0:y0+2048,x0:x0+2048]=(np.sqrt((jxx-jyy)**2+4*jxy*jxy)/(jxx+jyy+1e-6)).astype(np.float16)
        del tile,gray,gx,gy,jxx,jyy,jxy,angle
    hair_mask_pixels=cv2.imread(a.hair_mask,cv2.IMREAD_GRAYSCALE) if a.hair_mask else None
    assert hair_mask_pixels is None or hair_mask_pixels.shape==(4096,4096)
    fallback_mat=mat.copy();fallback_mat.name='Alice / unpainted dark fiber / occluded or nonhair image pixels'
    fallback_palette=[fallback_mat]
    fallback_bs=fallback_mat.node_tree.nodes.get('Principled BSDF')
    fallback_bs.inputs['Roughness'].default_value=.68
    if 'Specular IOR Level' in fallback_bs.inputs:
        fallback_bs.inputs['Specular IOR Level'].default_value=.12
    if a.fiber_tone_variation:
        fallback_palette=[]
        for i,level in enumerate((.013,.019,.025,.033,.043,.057)):
            variant=fallback_mat.copy()
            variant.name=f'Alice / dark individual fiber tone {i}'
            variant_bs=variant.node_tree.nodes.get('Principled BSDF')
            variant_bs.inputs['Base Color'].default_value=(level,level*.81,level*.77,1)
            variant_bs.inputs['Roughness'].default_value=(.73,.71,.68,.66,.63,.60)[i]
            fallback_palette.append(variant)
    mat.name='Alice / visible fiber painting / guarded UV probe'
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas
    mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value=.58
    if 'Specular IOR Level' in bs.inputs:bs.inputs['Specular IOR Level'].default_value=.15
    cameras={}
    center=Vector((0,.025,.808))
    for view,direction in [('front',(0,-1,0)),('back',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
        cam=bpy.context.scene.camera.copy();cam.data=bpy.context.scene.camera.data.copy()
        cam.location=center+Vector(direction)*1.2
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        # Copies are not linked to the depsgraph. Set the transform explicitly;
        # otherwise matrix_world can retain the source scene camera's pose.
        cam.matrix_world=Matrix.Translation(cam.location)@cam.rotation_euler.to_matrix().to_4x4()
        cam.data.type='ORTHO';cam.data.ortho_scale=.4
        cameras[view]=cam
    tiles={'front':(0,0),'right':(2048,0),'back':(0,2048),'left':(2048,2048)}
    projection=dict(atlas=a.projection_atlas,alignment=a.alignment,hairMask=a.hair_mask,
                    flowAngleDeg=a.flow_angle_deg,flowCoherenceMin=a.flow_coherence_min,
                    depthGateMm=a.depth_gate_mm,validLoopPoints=0,clampedLoopPoints=0,
                    imageHairFaces=0,imageRejectedFaces=0,depthRejectedFaces=0,
                    bodyOccludedFaces=0,bodyRaycasts=0,strictRejectedFaces=0,
                    flowRejectedFaces=0)
    projection['excludedGuideFamilies']=sorted(unpainted_families)
    projection['depthGateMode']='sampledRibbonBvhDiagnostic' if a.audit_hair_bvh_gate else 'centerDepthMap'
    projection['byView']={view:dict(selected=0,maskPassed=0,strictPassed=0,
                                    flowPassed=0,depthPassed=0,painted=0,
                                    rejected=0,bodyOccluded=0)
                          for view in cameras}
    if a.audit_only:
        projection['maskColorAudit']={view:dict(valid=0,hairMask=0,colorFilter=0,
                                               alpha=0,allPassed=0) for view in cameras}
        front_projection_points=[]
    if a.audit_alternate_views:
        stages=('valid','mask','strict','flow','depth','body','family')
        projection['alternateViewAudit']={
            'primaryRejected':0,'anyAlternatePassed':0,'nonePassed':0,
            'alternatePassedByView':{view:0 for view in cameras},
            'candidateStagePasses':{stage:0 for stage in stages},
            'rejectedSegmentWithAnyStagePass':{stage:0 for stage in stages},
            'scope':('Diagnostic filter pass with full source-hair ribbon midpoint BVH; still not complete face visibility.'
                     if a.audit_bvh_full_hair and a.audit_hair_bvh_gate else
                     'Diagnostic filter pass only; center-depth and body ray do not prove full ribbon visibility.')}
    if a.audit_select_visible_view:
        projection['visibleViewSelection']={'primaryPassed':0,'reassigned':0,'noEligible':0,
                                            'selectedByView':{view:0 for view in cameras},
                                            'scope':'Sampled midpoint selection using full source-hair BVH; not a whole-face visibility proof.'}
    view_index={view:index for index,view in enumerate(cameras)}
    flow_guide_reject=np.zeros((len(cameras),int(guide_ids.max())+1),np.int32)
    painted_guide_counts=np.zeros_like(flow_guide_reject)
    family_painted={view:{} for view in cameras}
    family_gate={view:{} for view in cameras}
    roi_painted_guides=np.zeros(int(guide_ids.max())+1,np.int32)
    transforms={view:np.array(cam.matrix_world.inverted()@source_hair.matrix_world,dtype=np.float32)
                for view,cam in cameras.items()}
    depth_maps={}
    body_bvh=None
    if a.body_occlusion:
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        world_vertices=[whole.matrix_world@vert.co for vert in whole.data.vertices]
        polygons=[tuple(poly.vertices) for poly in whole.data.polygons]
        body_bvh=BVHTree.FromPolygons(world_vertices,polygons,all_triangles=False,epsilon=0.0)
        toward_camera={view:(cam.location-center).normalized() for view,cam in cameras.items()}
        del world_vertices,polygons
    if a.depth_gate_mm:
        centers=((v[:,sample[:-1]]+v[:,sample[1:]])*.5).reshape(-1,3)
        for view,transform in transforms.items():
            local=centers@transform[:3,:3].T+transform[:3,3]
            ix=np.floor((.5+local[:,0]/.4)*768).astype(np.int32)
            iy=np.floor((.5-local[:,1]/.4)*768).astype(np.int32)
            distance=-local[:,2]
            inside=(ix>=0)&(ix<768)&(iy>=0)&(iy<768)&(distance>0)
            grid=np.full(768*768,np.inf,np.float32)
            np.minimum.at(grid,iy[inside]*768+ix[inside],distance[inside])
            depth_maps[view]=grid.reshape(768,768)
        del centers,local,ix,iy,distance,inside,grid
    def depth_visible(point,view):
        transform=transforms[view]
        local=transform[:3,:3]@point+transform[:3,3]
        ix=int(np.floor((.5+local[0]/.4)*768))
        iy=int(np.floor((.5-local[1]/.4)*768))
        if not (0<=ix<768 and 0<=iy<768):return False
        nearest=depth_maps[view][iy,ix]
        return bool(np.isfinite(nearest) and -local[2]<=nearest+a.depth_gate_mm*.001)
    def body_visible(point,view):
        world_point=source_hair.matrix_world@Vector(point)
        toward=toward_camera[view]
        hit=body_bvh.ray_cast(world_point+toward*1.2,-toward,1.198)
        return hit[0] is None
    def project_path(path,view):
        row=by_view[view]
        transform=transforms[view]
        local=path@transform[:3,:3].T+transform[:3,3]
        px=(.5+local[:,0]/.4)*768
        py=(.5-local[:,1]/.4)*768
        m=np.asarray(row['matrixRenderToPaint'],np.float32)
        sx=m[0,0]*px+m[0,1]*py+m[0,2]
        sy=m[1,0]*px+m[1,1]*py+m[1,2]
        valid=(sx>=0)&(sx<1254)&(sy>=0)&(sy<1254)
        sx=np.clip(sx,1,1253);sy=np.clip(sy,1,1253)
        tx,ty=tiles[row['paintView']]
        return np.stack(((tx+sx*2048/1254)/4096,
                         1-(ty+sy*2048/1254)/4096),axis=1),valid

    def safe_hair_uv(coordinate,strict=False):
        px=int(np.clip(coordinate[0]*4095,0,4095));py=int(np.clip((1-coordinate[1])*4095,0,4095))
        pixel=atlas_pixels[py,px]
        blue,green,red=(int(pixel[0]),int(pixel[1]),int(pixel[2]))
        bright=max(red,green,blue)
        if strict:
            color_ok=7<=bright<=105 and green<=red*.98+2 and blue<=red*1.10+4
        else:
            color_ok=7<=bright<=105 and green<=red*1.16+4 and blue<=red*1.3+5
        return bool(color_ok and (len(pixel)<4 or int(pixel[3])>127)
                    and (hair_mask_pixels is None or hair_mask_pixels[py,px]>127))
    def flow_matches(coordinate,delta):
        length=float(np.linalg.norm(delta))
        if length<1e-7:return False
        px=int(np.clip(coordinate[0]*4095,0,4095))
        py=int(np.clip((1-coordinate[1])*4095,0,4095))
        if float(flow_coherence[py,px])<a.flow_coherence_min:return False
        dx=float(delta[0])/length;dy=-float(delta[1])/length
        match=abs(dx*float(flow_x[py,px])+dy*float(flow_y[py,px]))
        return match>=np.cos(np.deg2rad(a.flow_angle_deg))
    if a.audit_hair_bvh:
        from mathutils.bvhtree import BVHTree
        bvh_fiber_ids=np.arange(C,dtype=np.int32) if a.audit_bvh_full_hair else selected_fiber_ids
        if a.audit_hair_bvh_mesh:
            hair_paths=v[bvh_fiber_ids][:,sample,:]
            hair_radii=r[bvh_fiber_ids][:,sample]
            hair_tangents=np.gradient(hair_paths,axis=1)
            hair_tangents/=np.maximum(np.linalg.norm(hair_tangents,axis=2,keepdims=True),1e-9)
            hair_radials=hair_paths-np.array([0,.012,.82],np.float32);hair_radials[:,:,2]=0
            hair_radials/=np.maximum(np.linalg.norm(hair_radials,axis=2,keepdims=True),1e-9)
            hair_sides=np.cross(hair_tangents,hair_radials)
            hair_sides/=np.maximum(np.linalg.norm(hair_sides,axis=2,keepdims=True),1e-9)
            hair_widths=np.maximum(hair_radii*a.fiber_width_scale,.000012)
            ribbon_vertices=np.stack((hair_paths-hair_sides*hair_widths[:,:,None],
                                      hair_paths+hair_sides*hair_widths[:,:,None]),axis=2).reshape(-1,3)
            hair_matrix=np.array(source_hair.matrix_world,dtype=np.float32)
            ribbon_vertices=ribbon_vertices@hair_matrix[:3,:3].T+hair_matrix[:3,3]
            fiber_bases=np.arange(len(bvh_fiber_ids),dtype=np.int32)[:,None,None]*(a.samples*2)
            segment_bases=np.arange(a.samples-1,dtype=np.int32)[None,:,None]*2
            ribbon_faces=(fiber_bases+segment_bases+np.array([0,1,3,2],np.int32)).reshape(-1,4)
            mesh=bpy.data.meshes.new('Alice ribbon BVH audit only')
            mesh.vertices.add(len(ribbon_vertices));mesh.vertices.foreach_set('co',ribbon_vertices.ravel())
            mesh.loops.add(ribbon_faces.size);mesh.loops.foreach_set('vertex_index',ribbon_faces.ravel())
            mesh.polygons.add(len(ribbon_faces))
            mesh.polygons.foreach_set('loop_start',np.arange(len(ribbon_faces),dtype=np.int32)*4)
            mesh.polygons.foreach_set('loop_total',np.full(len(ribbon_faces),4,np.int32))
            mesh.update()
            bvh_object=bpy.data.objects.new('Alice ribbon BVH audit only',mesh)
            bpy.context.collection.objects.link(bvh_object)
            hair_bvh=BVHTree.FromObject(bvh_object,bpy.context.evaluated_depsgraph_get())
            bpy.data.objects.remove(bvh_object,do_unlink=True)
            bpy.data.meshes.remove(mesh)
            del hair_paths,hair_radii,hair_tangents,hair_radials,hair_sides,hair_widths,hair_matrix
        else:
            ribbon_vertices=[];ribbon_faces=[]
            for hair_fid in bvh_fiber_ids:
                hair_path=v[hair_fid,sample];hair_radius=r[hair_fid,sample]
                hair_tangent=np.gradient(hair_path,axis=0)
                hair_tangent/=np.maximum(np.linalg.norm(hair_tangent,axis=1,keepdims=True),1e-9)
                hair_radial=hair_path-np.array([0,.012,.82],np.float32);hair_radial[:,2]=0
                hair_radial/=np.maximum(np.linalg.norm(hair_radial,axis=1,keepdims=True),1e-9)
                hair_side=np.cross(hair_tangent,hair_radial)
                hair_side/=np.maximum(np.linalg.norm(hair_side,axis=1,keepdims=True),1e-9)
                first_ribbon=len(ribbon_vertices)
                for hair_i in range(a.samples):
                    width=max(float(hair_radius[hair_i])*a.fiber_width_scale,.000012)
                    ribbon_vertices.extend((source_hair.matrix_world@Vector(hair_path[hair_i]-hair_side[hair_i]*width),
                                            source_hair.matrix_world@Vector(hair_path[hair_i]+hair_side[hair_i]*width)))
                ribbon_faces.extend((first_ribbon+2*j,first_ribbon+2*j+1,
                                     first_ribbon+2*j+3,first_ribbon+2*j+2)
                                    for j in range(a.samples-1))
            hair_bvh=BVHTree.FromPolygons(ribbon_vertices,ribbon_faces,all_triangles=False,epsilon=0.0)
        hair_toward={view:(cam.location-center).normalized() for view,cam in cameras.items()}
        projection['hairBvhAudit']={key:0 for key in ('tested','noHit','nearHit','farHit',
            'depthPassNearHit','depthPassFarHit','depthPassNoHit','depthRejectNearHit',
            'depthRejectFarHit','depthRejectNoHit','hitWithin0p1mm','depthRejectHitWithin0p1mm',
            'hitWithin0p25mm','depthRejectHitWithin0p25mm','hitWithin0p5mm',
            'depthRejectHitWithin0p5mm')}
        projection['hairBvhAudit']['scope']='Selected sampled ribbons only, midpoint ray, 1.5 mm near-hit tolerance; diagnostic, not a paint gate.'
        projection['hairBvhAudit']['bvhFiberCount']=int(len(bvh_fiber_ids))
        projection['hairBvhAudit']['threePointRejected']=0
        if a.audit_bvh_full_hair:
            projection['hairBvhAudit']['scope']='Full source-hair ribbon BVH against sampled candidate midpoints; diagnostic, not a complete face-visibility proof.'
        del ribbon_vertices,ribbon_faces
    probe=np.array([[0,.025,.808]],np.float32)
    for view,cam in cameras.items():
        reference=world_to_camera_view(bpy.context.scene,cam,source_hair.matrix_world@Vector(probe[0]))
        local=probe@transforms[view][:3,:3].T+transforms[view][:3,3]
        assert abs(reference.x-(.5+local[0,0]/.4))<1e-4
        assert abs(reference.y-(.5+local[0,1]/.4))<1e-4
    def hair_segment_visible(path,view,index):
        toward=hair_toward[view]
        for fraction in ((.2,.5,.8) if a.audit_hair_three_samples else (.5,)):
            point=path[index]*(1-fraction)+path[index+1]*fraction
            world_point=source_hair.matrix_world@Vector(point)
            hit=hair_bvh.ray_cast(world_point+toward*1.2,-toward,1.201)
            if hit[0] is None or (hit[0]-world_point).length>.0001:return False
        return True
    def eligible_visible_view(projected_path,curve_path,view,index,midpoint,family):
        uv_path,valid=projected_path[view]
        if not (valid[index] and valid[index+1]):return False
        uv0=np.asarray(uv_path[index]);uv1=np.asarray(uv_path[index+1]);middle=(uv0+uv1)*.5
        if not safe_hair_uv(middle):return False
        if a.strict_projection and not (
            np.linalg.norm((uv1-uv0)*4096)<=85 and
            all(safe_hair_uv(uv0*(1-t)+uv1*t,True) for t in (0,.25,.5,.75,1))):return False
        if a.flow_angle_deg and not flow_matches(middle,uv1-uv0):return False
        if not hair_segment_visible(curve_path,view,index):return False
        if a.body_occlusion and not body_visible(midpoint,view):return False
        return family not in unpainted_families
hair_chunks=[]
for chunk_start in range(0,len(selected_fiber_ids),a.chunk_size):
    fibers=selected_fiber_ids[chunk_start:chunk_start+a.chunk_size]
    verts=[];faces=[];uv=[];face_materials=[];fiber_ids=[];fiber_factors=[];fiber_guide_ids=[]
    for fid in fibers:
        tone_hash=(int(fid)*2654435761 & 0xffffffff)
        tone_index=int(tone_hash/4294967296.0>=.94) if a.individual_reflection_tones else int(tone_hash%len(fallback_palette))
        path=v[fid,sample];radius=r[fid,sample]
        tangent=np.gradient(path,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1,keepdims=True),1e-9)
        radial=path-np.array([0,.012,.82],np.float32);radial[:,2]=0
        radial/=np.maximum(np.linalg.norm(radial,axis=1,keepdims=True),1e-9)
        side=np.cross(tangent,radial);side/=np.maximum(np.linalg.norm(side,axis=1,keepdims=True),1e-9)
        first=len(verts)
        for i in range(a.samples):
            width=max(float(radius[i])*a.fiber_width_scale,.000012)
            verts.extend([tuple(path[i]-side[i]*width),tuple(path[i]+side[i]*width)])
            if a.runtime_hair_attributes:
                fiber_ids.extend([float(fid),float(fid)])
                fiber_factors.extend([i/(a.samples-1)]*2)
                fiber_guide_ids.extend([float(guide_ids[fid]),float(guide_ids[fid])])
        if projection:
            projected={view:project_path(path,view) for view in cameras}
        for i in range(a.samples-1):
            faces.append((first+2*i,first+2*i+1,first+2*i+3,first+2*i+2))
            if projection:
                midpoint=(path[i]+path[i+1])*.5
                radial=midpoint-np.array([0,.006,.864],np.float32)
                view=a.audit_force_view or (('left' if radial[0]<0 else 'right') if abs(radial[0])>abs(radial[1]) else ('front' if radial[1]<0 else 'back'))
                if a.audit_select_visible_view:
                    selection=projection['visibleViewSelection']
                    family=str(guide_families[guide_ids[fid]])
                    if eligible_visible_view(projected,path,view,i,midpoint,family):
                        selection['primaryPassed']+=1
                    else:
                        replacement=next((other for other in cameras if other!=view and
                                          eligible_visible_view(projected,path,other,i,midpoint,family)),None)
                        if replacement is None:selection['noEligible']+=1
                        else:view=replacement;selection['reassigned']+=1
                    selection['selectedByView'][view]+=1
                projection['byView'][view]['selected']+=1
                family=str(guide_families[guide_ids[fid]])
                gate=family_gate[view].setdefault(family,dict(selected=0,maskPassed=0,strictPassed=0,
                                                              flowPassed=0,depthPassed=0,painted=0))
                gate['selected']+=1
                uv_path,valid=projected[view]
                a0=tuple(uv_path[i]);a1=tuple(uv_path[i+1])
                projection['validLoopPoints']+=int(valid[i])+int(valid[i+1])
                projection['clampedLoopPoints']+=2-int(valid[i])-int(valid[i+1])
                uv.extend([a0,a0,a1,a1])
                uv0=np.asarray(a0);uv1=np.asarray(a1)
                middle=(uv0+uv1)*.5
                if a.audit_only and valid[i] and valid[i+1]:
                    mask_audit=projection['maskColorAudit'][view]
                    mask_audit['valid']+=1
                    audit_px=int(np.clip(middle[0]*4095,0,4095))
                    audit_py=int(np.clip((1-middle[1])*4095,0,4095))
                    audit_pixel=atlas_pixels[audit_py,audit_px]
                    audit_blue,audit_green,audit_red=(int(audit_pixel[0]),int(audit_pixel[1]),int(audit_pixel[2]))
                    audit_bright=max(audit_red,audit_green,audit_blue)
                    audit_color=7<=audit_bright<=105 and audit_green<=audit_red*1.16+4 and audit_blue<=audit_red*1.3+5
                    audit_alpha=len(audit_pixel)<4 or int(audit_pixel[3])>127
                    audit_mask=hair_mask_pixels is None or hair_mask_pixels[audit_py,audit_px]>127
                    mask_audit['colorFilter']+=int(audit_color)
                    mask_audit['alpha']+=int(audit_alpha)
                    mask_audit['hairMask']+=int(audit_mask)
                    mask_audit['allPassed']+=int(audit_color and audit_alpha and audit_mask)
                    if view=='front':
                        hair_visible=None
                        if a.audit_bvh_full_hair:
                            world_midpoint=source_hair.matrix_world@Vector(midpoint)
                            toward=hair_toward[view]
                            diagnostic_hit=hair_bvh.ray_cast(world_midpoint+toward*1.2,-toward,1.201)
                            hair_visible=bool(diagnostic_hit[0] is not None and
                                              (diagnostic_hit[0]-world_midpoint).length<=.0001)
                        body_clear=body_visible(midpoint,view) if a.body_occlusion else None
                        front_projection_points.append((int(fid),i,audit_px,audit_py,
                                                        int(audit_mask),int(audit_color),int(audit_alpha),
                                                        int(guide_ids[fid]),str(guide_families[guide_ids[fid]]),
                                                        hair_visible,body_clear))
                image_hair=bool(valid[i] and valid[i+1] and safe_hair_uv(middle))
                projection['byView'][view]['maskPassed']+=int(image_hair)
                gate['maskPassed']+=int(image_hair)
                if image_hair and a.strict_projection:
                    image_hair=bool(np.linalg.norm((uv1-uv0)*4096)<=85 and
                                    all(safe_hair_uv(uv0*(1-t)+uv1*t,True)
                                        for t in (0,.25,.5,.75,1)))
                    projection['strictRejectedFaces']+=int(not image_hair)
                projection['byView'][view]['strictPassed']+=int(image_hair)
                gate['strictPassed']+=int(image_hair)
                if image_hair and a.flow_angle_deg and not flow_matches(middle,uv1-uv0):
                    image_hair=False
                    projection['flowRejectedFaces']+=1
                    flow_guide_reject[view_index[view],guide_ids[fid]]+=1
                projection['byView'][view]['flowPassed']+=int(image_hair)
                gate['flowPassed']+=int(image_hair)
                bvh_gate_visible=None
                if image_hair and a.audit_hair_bvh:
                    bvh_audit=projection['hairBvhAudit'];bvh_audit['tested']+=1
                    world_midpoint=source_hair.matrix_world@Vector(midpoint)
                    toward=hair_toward[view]
                    hit=hair_bvh.ray_cast(world_midpoint+toward*1.2,-toward,1.201)
                    if hit[0] is None:category='NoHit'
                    elif (hit[0]-world_midpoint).length<=.0015:category='NearHit'
                    else:category='FarHit'
                    bvh_audit[category[0].lower()+category[1:]]+=1
                    depth_category='depthPass' if depth_visible(midpoint,view) else 'depthReject'
                    bvh_audit[depth_category+category]+=1
                    if hit[0] is not None:
                        hit_gap=(hit[0]-world_midpoint).length
                        bvh_gate_visible=hit_gap<=.0001
                        if bvh_gate_visible and a.audit_hair_three_samples:
                            bvh_gate_visible=hair_segment_visible(path,view,i)
                            bvh_audit['threePointRejected']+=int(not bvh_gate_visible)
                        for threshold,label in ((.0001,'0p1mm'),(.00025,'0p25mm'),(.0005,'0p5mm')):
                            if hit_gap<=threshold:
                                bvh_audit['hitWithin'+label]+=1
                                if depth_category=='depthReject':bvh_audit['depthRejectHitWithin'+label]+=1
                depth_gate_visible=bvh_gate_visible if a.audit_hair_bvh_gate else depth_visible(midpoint,view) if image_hair and a.depth_gate_mm else True
                if image_hair and a.depth_gate_mm and not depth_gate_visible:
                    image_hair=False
                    projection['depthRejectedFaces']+=1
                projection['byView'][view]['depthPassed']+=int(image_hair)
                gate['depthPassed']+=int(image_hair)
                if image_hair and a.body_occlusion:
                    projection['bodyRaycasts']+=1
                    if not body_visible(midpoint,view):
                        image_hair=False
                        projection['bodyOccludedFaces']+=1
                        projection['byView'][view]['bodyOccluded']+=1
                if image_hair and guide_families[guide_ids[fid]] in unpainted_families:
                    image_hair=False
                    projection['familyExcludedFaces']=projection.get('familyExcludedFaces',0)+1
                if a.audit_alternate_views and not image_hair:
                    alternative=projection['alternateViewAudit']
                    alternative['primaryRejected']+=1
                    passed=[]
                    any_stages=set()
                    for other in cameras:
                        if other==view:continue
                        other_path,other_valid=projected[other]
                        if not (other_valid[i] and other_valid[i+1]):continue
                        alternative['candidateStagePasses']['valid']+=1;any_stages.add('valid')
                        other_uv0=np.asarray(other_path[i]);other_uv1=np.asarray(other_path[i+1])
                        other_mid=(other_uv0+other_uv1)*.5
                        if not safe_hair_uv(other_mid):continue
                        alternative['candidateStagePasses']['mask']+=1;any_stages.add('mask')
                        if a.strict_projection and not (
                            np.linalg.norm((other_uv1-other_uv0)*4096)<=85 and
                            all(safe_hair_uv(other_uv0*(1-t)+other_uv1*t,True)
                                for t in (0,.25,.5,.75,1))):continue
                        alternative['candidateStagePasses']['strict']+=1;any_stages.add('strict')
                        if a.flow_angle_deg and not flow_matches(other_mid,other_uv1-other_uv0):continue
                        alternative['candidateStagePasses']['flow']+=1;any_stages.add('flow')
                        if a.depth_gate_mm and a.audit_hair_bvh_gate:
                            if not hair_segment_visible(path,other,i):continue
                        elif a.depth_gate_mm and not depth_visible(midpoint,other):continue
                        alternative['candidateStagePasses']['depth']+=1;any_stages.add('depth')
                        if a.body_occlusion and not body_visible(midpoint,other):continue
                        alternative['candidateStagePasses']['body']+=1;any_stages.add('body')
                        if guide_families[guide_ids[fid]] in unpainted_families:continue
                        alternative['candidateStagePasses']['family']+=1;any_stages.add('family')
                        passed.append(other)
                    for stage in any_stages:alternative['rejectedSegmentWithAnyStagePass'][stage]+=1
                    if passed:
                        alternative['anyAlternatePassed']+=1
                        for other in passed:alternative['alternatePassedByView'][other]+=1
                    else:
                        alternative['nonePassed']+=1
                face_materials.append(len(fallback_palette) if image_hair else tone_index)
                projection['imageHairFaces']+=int(image_hair)
                projection['imageRejectedFaces']+=int(not image_hair)
                coverage=projection.setdefault('segmentCoverageDiagnostic',dict(
                    selectedRawCenterlineLengthM=0.,paintedRawCenterlineLengthM=0.,
                    selectedRibbonAreaProxyM2=0.,paintedRibbonAreaProxyM2=0.,
                    scope='Length-weighted sampled segment and width-times-length proxy; not visible-pixel coverage or full-face occlusion proof.'))
                segment_length=float(np.linalg.norm(path[i+1]-path[i]))
                ribbon_area_proxy=segment_length*(max(float(radius[i])*a.fiber_width_scale,.000012)+
                    max(float(radius[i+1])*a.fiber_width_scale,.000012))
                coverage['selectedRawCenterlineLengthM']+=segment_length
                coverage['selectedRibbonAreaProxyM2']+=ribbon_area_proxy
                if image_hair:
                    coverage['paintedRawCenterlineLengthM']+=segment_length
                    coverage['paintedRibbonAreaProxyM2']+=ribbon_area_proxy
                projection['byView'][view]['painted' if image_hair else 'rejected']+=1
                gate['painted']+=int(image_hair)
                if image_hair:
                    painted_guide_counts[view_index[view],guide_ids[fid]]+=1
                    family=str(guide_families[guide_ids[fid]])
                    family_painted[view][family]=family_painted[view].get(family,0)+1
                    if audit_roi and view==audit_roi[0]:
                        local=transforms[view][:3,:3]@midpoint+transforms[view][:3,3]
                        sx=(.5+local[0]/.4)*768;sy=(.5-local[1]/.4)*768
                        x0,y0,x1,y1=audit_roi[1]
                        if x0<=sx<x1 and y0<=sy<y1:roi_painted_guides[guide_ids[fid]]+=1
            else:
                t0=i/(a.samples-1);t1=(i+1)/(a.samples-1)
                uv.extend([(0,t0),(1,t0),(1,t1),(0,t1)])
                if a.individual_reflection_tones:face_materials.append(tone_index)
    mesh=bpy.data.meshes.new('Alice separated fiber ribbons '+str(chunk_start//a.chunk_size));mesh.from_pydata(verts,[],faces);mesh.update()
    layer=mesh.uv_layers.new(name='Hair UV')
    for loop,coordinate in zip(layer.data,uv):loop.uv=coordinate
    if a.runtime_hair_attributes:
        assert len(fiber_ids)==len(fiber_factors)==len(fiber_guide_ids)==len(mesh.vertices)
        mesh.attributes.new('_FIBER_ID','FLOAT','POINT').data.foreach_set('value',fiber_ids)
        mesh.attributes.new('_FIBER_T','FLOAT','POINT').data.foreach_set('value',fiber_factors)
        mesh.attributes.new('_GUIDE_ID','FLOAT','POINT').data.foreach_set('value',fiber_guide_ids)
    if projection:
        for fallback in fallback_palette:mesh.materials.append(fallback)
        mesh.materials.append(mat)
        mesh.polygons.foreach_set('material_index',face_materials)
        checked=bad=0
        for polygon in mesh.polygons:
            if polygon.material_index!=len(fallback_palette):continue
            checked+=1
            for loop_index in polygon.loop_indices:
                if not safe_hair_uv(layer.data[loop_index].uv,a.strict_projection):
                    bad+=1;break
        projection['postMeshPaintedFaces']=projection.get('postMeshPaintedFaces',0)+checked
        projection['postMeshPaintedFacesOutsideMask']=projection.get('postMeshPaintedFacesOutsideMask',0)+bad
        print('POST_MESH_PAINT_AUDIT',checked,bad,flush=True)
        if chunk_start==0:
            samples=[]
            for polygon in mesh.polygons:
                if polygon.material_index!=len(fallback_palette):continue
                point=source_hair.matrix_world@polygon.center
                coordinate=layer.data[polygon.loop_indices[0]].uv
                samples.append(dict(center=[round(float(x),6) for x in point],uv=[round(float(x),6) for x in coordinate]))
                if len(samples)==20:break
            (out/'preexport_painted_samples.json').write_text(json.dumps(samples,indent=2))
    elif a.individual_reflection_tones:
        for tone in fallback_palette:mesh.materials.append(tone)
        mesh.polygons.foreach_set('material_index',face_materials)
    else:mesh.materials.append(mat)
    obj=bpy.data.objects.new('Alice / individual hair fibers / '+str(chunk_start//a.chunk_size),mesh)
    bpy.context.scene.collection.objects.link(obj);obj.parent=rig
    # Raw curve positions are in the character's rest coordinates. Reusing the
    # evaluated hair object's Head transform also skins that pose a second time.
    obj.matrix_world=Matrix.Identity(4)
    group=obj.vertex_groups.new(name='Head');group.add(list(range(len(mesh.vertices))),1.0,'REPLACE')
    modifier=obj.modifiers.new('Alice Head skin','ARMATURE');modifier.object=rig
    obj['aliceRole']='hair';obj['hairFiberCount']=len(fibers);obj['hairRepresentation']='separate mesh ribbon per source fiber; static Head skin, runtime dynamics pending'
    hair_chunks.append(obj)
    print('HAIR_RIBBON_CHUNK',len(hair_chunks),len(fibers),flush=True)
    del verts,faces,uv
rear_braid_fibers=0
if a.include_rear_braid:
    braid=bpy.data.objects['Chapeleiro / rear braid individual fibers / study']
    rear_braid_fibers=len(braid.data.curves)
    assert rear_braid_fibers==g['rearBraidStrandStudy']['newFiberCount']==1500
    braid_points=len(braid.data.points)//rear_braid_fibers
    braid_v=np.empty(len(braid.data.points)*3,np.float32)
    braid.data.attributes['position'].data.foreach_get('vector',braid_v)
    braid_v=braid_v.reshape(rear_braid_fibers,braid_points,3)
    braid_r=np.empty(len(braid.data.points),np.float32)
    braid.data.attributes['radius'].data.foreach_get('value',braid_r)
    braid_r=braid_r.reshape(rear_braid_fibers,braid_points)
    braid_side=np.empty(rear_braid_fibers,np.int32)
    braid_tress=np.empty(rear_braid_fibers,np.int32)
    braid.data.attributes['alice_braid_side'].data.foreach_get('value',braid_side)
    braid.data.attributes['alice_braid_tress'].data.foreach_get('value',braid_tress)
    assert set(braid_side)=={-1,1} and set(braid_tress)=={0,1,2}
    braid_sample=np.linspace(0,braid_points-1,a.samples).round().astype(int)
    braid_mat=fallback_mat.copy();braid_mat.name='Alice / rear braid dark fibers / PBR'
    braid_bs=braid_mat.node_tree.nodes.get('Principled BSDF')
    braid_bs.inputs['Base Color'].default_value=(.034,.027,.023,1)
    braid_bs.inputs['Roughness'].default_value=.45
    if 'Specular IOR Level' in braid_bs.inputs:braid_bs.inputs['Specular IOR Level'].default_value=.32
    for chunk_start in range(0,rear_braid_fibers,a.chunk_size):
        fibers=range(chunk_start,min(chunk_start+a.chunk_size,rear_braid_fibers))
        verts=[];faces=[];uv=[];fiber_ids=[];fiber_factors=[];fiber_guide_ids=[]
        for fid in fibers:
            path=braid_v[fid,braid_sample];radius=braid_r[fid,braid_sample]
            tangent=np.gradient(path,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1,keepdims=True),1e-9)
            radial=path-np.array([0,.012,.82],np.float32);radial[:,2]=0
            radial/=np.maximum(np.linalg.norm(radial,axis=1,keepdims=True),1e-9)
            side=np.cross(tangent,radial);side/=np.maximum(np.linalg.norm(side,axis=1,keepdims=True),1e-9)
            first=len(verts)
            virtual_guide=2112+(0 if braid_side[fid]==-1 else 3)+int(braid_tress[fid])
            for i in range(a.samples):
                width=max(float(radius[i])*a.fiber_width_scale,.000012)
                verts.extend([tuple(path[i]-side[i]*width),tuple(path[i]+side[i]*width)])
                if a.runtime_hair_attributes:
                    fiber_ids.extend([float(C+fid)]*2)
                    fiber_factors.extend([i/(a.samples-1)]*2)
                    fiber_guide_ids.extend([float(virtual_guide)]*2)
            for i in range(a.samples-1):
                faces.append((first+2*i,first+2*i+1,first+2*i+3,first+2*i+2))
                t0=i/(a.samples-1);t1=(i+1)/(a.samples-1)
                uv.extend([(0,t0),(1,t0),(1,t1),(0,t1)])
        mesh=bpy.data.meshes.new('Alice rear braid individual ribbons '+str(chunk_start//a.chunk_size))
        mesh.from_pydata(verts,[],faces);mesh.update()
        layer=mesh.uv_layers.new(name='Braid Hair UV')
        for loop,coordinate in zip(layer.data,uv):loop.uv=coordinate
        if a.runtime_hair_attributes:
            mesh.attributes.new('_FIBER_ID','FLOAT','POINT').data.foreach_set('value',fiber_ids)
            mesh.attributes.new('_FIBER_T','FLOAT','POINT').data.foreach_set('value',fiber_factors)
            mesh.attributes.new('_GUIDE_ID','FLOAT','POINT').data.foreach_set('value',fiber_guide_ids)
        mesh.materials.append(braid_mat)
        obj=bpy.data.objects.new('Alice / rear braid individual hair fibers / '+str(chunk_start//a.chunk_size),mesh)
        bpy.context.scene.collection.objects.link(obj);obj.parent=rig;obj.matrix_world=Matrix.Identity(4)
        group=obj.vertex_groups.new(name='Head');group.add(list(range(len(mesh.vertices))),1.0,'REPLACE')
        modifier=obj.modifiers.new('Alice Head skin','ARMATURE');modifier.object=rig
        obj['aliceRole']='hair';obj['hairFiberCount']=len(fibers)
        obj['hairRepresentation']='separate rear braid ribbon per fiber; static Head skin, independent dynamics pending'
        hair_chunks.append(obj)
        print('BRAID_RIBBON_CHUNK',len(hair_chunks),len(fibers),flush=True)
if projection and a.flow_angle_deg:
    projection['flowRejectedTopGuidesByView']={
        view:[dict(guideId=int(gid),rejectedSegments=int(flow_guide_reject[view_index[view],gid]))
              for gid in np.argsort(flow_guide_reject[view_index[view]])[-20:][::-1]
              if flow_guide_reject[view_index[view],gid]>0]
        for view in cameras}
if projection:
    projection['paintedByFamilyByView']=family_painted
    projection['gateByFamilyByView']=family_gate
    if audit_roi:
        projection['auditRoi']=dict(view=audit_roi[0],bounds=audit_roi[1],
                                    paintedSegments=int(roi_painted_guides.sum()),
                                    paintedByFamily={str(family):int(roi_painted_guides[guide_families==family].sum())
                                                     for family in np.unique(guide_families)
                                                     if roi_painted_guides[guide_families==family].sum()>0},
                                    topGuides=[dict(guideId=int(gid),family=str(guide_families[gid]),
                                                    paintedSegments=int(roi_painted_guides[gid]))
                                               for gid in np.argsort(roi_painted_guides)[-30:][::-1]
                                               if roi_painted_guides[gid]>0])
    projection['paintedTopGuidesByView']={
        view:[dict(guideId=int(gid),paintedSegments=int(painted_guide_counts[view_index[view],gid]))
              for gid in np.argsort(painted_guide_counts[view_index[view]])[-20:][::-1]
              if painted_guide_counts[view_index[view],gid]>0]
        for view in cameras}
    if painted_guide_counts.shape[1]==2112:
        projection['paintedGuideRanges']={
            view:dict(initialSourceFlow=int(painted_guide_counts[view_index[view],:1326].sum()),
                      interiorBackWaves=int(painted_guide_counts[view_index[view],1326:1992].sum()),
                      frontUndercoat=int(painted_guide_counts[view_index[view],1992:].sum()))
            for view in cameras}
if a.audit_only:
    if projection:
        (out/'front_projection_points.json').write_text(json.dumps(front_projection_points),encoding='utf-8')
    if a.audit_render_preview:
        scene=bpy.context.scene
        if a.audit_preview_hide_source_hair:
            source_hair.hide_render=True
        scene.render.resolution_x=scene.render.resolution_y=768
        scene.cycles.samples=16
        scene.cycles.use_denoising=True
        preview_camera=scene.camera
        preview_camera.data.type='ORTHO'
        preview_camera.data.ortho_scale=.4
        for name,direction in [('front',(0,-1,0)),('left',(-1,0,0)),
                               ('back',(0,1,0)),('right',(1,0,0))]:
            target=Vector((0,.025,.808))
            preview_camera.location=target+Vector(direction)*1.2
            preview_camera.rotation_euler=(target-preview_camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(out/('uv_preview_'+name+'.png'))
            bpy.ops.render.render(write_still=True)
        projection['previewScope']=('Complete dressed authoring scene with sampled projected ribbons; original authored hair hidden only in these renders.'
                                    if a.audit_preview_hide_source_hair else
                                    'Complete dressed authoring scene with sampled projected ribbons and the original hair; diagnostic only.')
    report=dict(sourceGeneration=a.generation,sourceBlendSha256=g['editableBlendSha256'],
                fiberCount=len(selected_fiber_ids),projection=projection)
    (out/'projection_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(__file__,out/'executed_audit.py')
    print('HAIR_PROJECTION_AUDIT',json.dumps(report),flush=True)
    sys.exit(0)
selected=[whole,rig]+hair_chunks+[bpy.data.objects[name] for name in source_metadata['posteriorBodice']['objects']]
selected += [bpy.data.objects[source_metadata['posteriorBodice']['underlyingSkinObject']],bpy.data.objects['Chapeleiro / reconstructed closed head interior / review'],bpy.data.objects['Chapeleiro / reconstructed neck interior / review']]
assert not any(o.get('alice_collision_proxy') for o in selected)
if rig.animation_data:rig.animation_data.action=None
rig.data.pose_position='POSE'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for track in list(rig.animation_data.nla_tracks):
    if track.name.split(' /')[0] in ('Walk','Run','Jump','Attack'):track.mute=False
    else:rig.animation_data.nla_tracks.remove(track)
for col in bpy.data.collections:col.hide_render=col.hide_viewport=False
for obj in bpy.context.scene.objects:
    obj.hide_render=obj not in selected;obj.hide_viewport=obj not in selected;obj.hide_set(obj not in selected);obj.select_set(obj in selected)
bpy.context.view_layer.objects.active=rig;bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
unweighted={}
for obj in selected:
    if obj.type=='MESH' and any(m.type=='ARMATURE' for m in obj.modifiers):
        empty=[v.index for v in obj.data.vertices if not any(w.weight>1e-8 for w in v.groups)]
        if empty:unweighted[obj.name]=len(empty)
assert not unweighted,unweighted
model=out/'alice_chapeleiro_complete_individual_hair_checkpoint.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,export_extras=True,export_attributes=a.runtime_hair_attributes,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_all_influences=True,export_draco_mesh_compression_enable=a.draco,export_draco_mesh_compression_level=6,export_draco_generic_quantization=a.draco_generic_bits,export_image_format=a.image_format,export_image_quality=a.image_quality)
with model.open('rb') as f:
    magic,version,total=struct.unpack('<4sII',f.read(12));length,kind=struct.unpack('<II',f.read(8));data=json.loads(f.read(length))
assert magic==b'glTF' and total==model.stat().st_size
names=[x['name'] for x in data['animations']];assert len(names)==4
assert {name.split(' /')[0] for name in names}=={'Walk','Run','Jump','Attack'}
assert sum(n.get('extras',{}).get('hairFiberCount',0) for n in data['nodes'])==len(selected_fiber_ids)+rear_braid_fibers
assert any('finished posterior bodice' in n.get('name','') for n in data['nodes'])
report=dict(sourceGeneration=a.generation,sourceBlend=g['editableBlend'],sourceBlendSha256=g['editableBlendSha256'],sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],model=str(model),modelSha256=sha(model),modelBytes=model.stat().st_size,wholeCharacterWithDress=True,sourceFaceCount=original_faces,sourceVertices=original_vertices,sourceHairFacesExcluded=len(hair_faces),originalTripoHairIncluded=False,hairRepresentation='One disconnected mesh ribbon per source fiber; Head skin only; independent wind dynamics remain Blender authoring',exportedFiberCount=len(selected_fiber_ids)+rear_braid_fibers,sourceFiberCount=C,addedRearBraidFiberCount=rear_braid_fibers,fiberSamples=a.samples,fiberWidthScale=a.fiber_width_scale,fiberToneVariation=a.fiber_tone_variation,hairRoughness=a.hair_roughness,hairSpecular=a.hair_specular,hairRibbonMeshCount=len(hair_chunks),meshCount=len(data['meshes']),skinCount=len(data['skins']),animations=names,posteriorBodiceObjects=source_metadata['posteriorBodice']['objects'],collisionProxiesExcluded=True,allRiggedVerticesWeighted=True,characterFinished=False,physicsApproved=False,published=False,dracoEnabled=a.draco,imageFormat=a.image_format,imageQuality=a.image_quality)
report['hairProjectionProbe']=projection
report['runtimeHairAttributes']=['_FIBER_ID','_FIBER_T','_GUIDE_ID'] if a.runtime_hair_attributes else []
report['individualReflectionTones']=dict(enabled=a.individual_reflection_tones,
    highlightThreshold=.94 if a.individual_reflection_tones else None,
    materialNames=[item.name for item in fallback_palette] if a.individual_reflection_tones else [])
report['dracoGenericQuantizationBits']=a.draco_generic_bits if a.draco else None
if projection:
    report['hairProjectionProbe']['visibleFaceOcclusionValidated']=False
    report['hairProjectionProbe']['selfOcclusionDepthGateApplied']=bool(a.depth_gate_mm)
    report['hairProjectionProbe']['bodyOcclusionApplied']=a.body_occlusion
    report['hairProjectionProbe']['strictProjection']=a.strict_projection
    report['hairProjectionProbe']['depthGateScope']=('Hair segment-center screen depth, with a first-hit ray against the preserved whole exterior mesh; separate accessories and subpixel ribbon coverage remain unverified.' if a.body_occlusion else 'Hair segment-center screen depth only; body, hat and subpixel ribbon coverage remain unverified.') if a.depth_gate_mm else None
    report['hairProjectionProbe']['rightViewRegistrationValidated']=False
    report['hairProjectionProbe']['uvFidelityApproved']=False
(out/'export.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_export.py')
print('WHOLE_INDIVIDUAL_HAIR_CHECKPOINT_EXPORTED',json.dumps({k:v for k,v in report.items() if k!='posteriorBodiceObjects'}),flush=True)
