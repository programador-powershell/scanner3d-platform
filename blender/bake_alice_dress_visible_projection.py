"""Bake generated garment paintings into the new UV with per-texel occlusion.

This runs the actual whole-character BVH, including protected anatomy and hair.
Only the highest-confidence visible source view contributes at each texel;
unseen or low-alpha paint locations keep the original atlas color.
The result is encoded RGBA data for lossless PNG packaging, not a model export.
"""
import argparse,hashlib,json,shutil,sys,time
from pathlib import Path
import numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--cache',required=True)
p.add_argument('--output',required=True)
p.add_argument('--base-projection',help='Reuse the verified existing texels and project only the reviewed local additions')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
g,cache=read(a.generation),read(a.cache)
assert sha(a.generation)==cache['uvGenerationSha256']
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
assert sha(g['baselineFile'])==g['baselineSha256']
baseline=read(g['baselineFile']);views=[r for r in baseline['renders'] if r['kind']=='basecolor']
assert [r['view'] for r in views]==['front','left','right','back']
pixels={}
for row in cache['sources']:
    assert sha(row['dataFile'])==row['dataSha256']
    pixels[row['view']]=np.load(row['dataFile'],mmap_mode='r')
geometry=np.load(g['projectionGeometry'])
points,triangles=geometry['world_points'],geometry['triangles']
loops=geometry['triangle_loops'];uv=geometry['dress_uv']
old_uv=geometry['original_uv'];coverage=geometry['visible_camera_masks']
tree=BVHTree.FromPolygons(points.tolist(),triangles.tolist(),all_triangles=True)
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
resolution=4096
atlas=np.zeros((resolution,resolution,4),np.uint8)
owner=np.full((resolution,resolution),-1,np.int32)
assignments=np.full((resolution,resolution),-2,np.int8)
retained_pixels=None
if a.base_projection:
    previous=read(a.base_projection)
    for key in ['triangleOwners','cameraAssignments']:assert sha(previous[key])==previous[key+'Sha256']
    assert 'incremental_triangle_indices' in geometry and 'previous_dress_atlas' in pixels
    parent=read(g['parentCharacterGeneration'])
    assert next(r for r in cache['sources'] if r['view']=='previous_dress_atlas')['sourceSha256']==parent['textureSha256']
    atlas=pixels['previous_dress_atlas'].copy()
    owner=np.load(previous['triangleOwners']).copy()
    retained_pixels=np.isin(owner,geometry['retained_triangle_indices'])
    owner[~retained_pixels]=-1
    assignments=np.load(previous['cameraAssignments']).copy();assignments[~retained_pixels]=-2
inverse=[np.array(Matrix(row['cameraWorldMatrix']).inverted()) for row in views]
camera_matrices=[Matrix(row['cameraWorldMatrix']) for row in views]
projections=[np.array(row['cameraProjectionMatrix']) for row in views]
forwards=[-(camera.to_3x3()@Vector((0,0,1))) for camera in camera_matrices]

def sample(image,coordinates):
    height,width=image.shape[:2]
    xy=np.clip(coordinates,0,1)*[width-1,height-1]
    xy0=np.floor(xy).astype(np.int32);xy1=np.minimum(xy0+1,[width-1,height-1])
    w=(xy-xy0).astype(np.float32)
    a=image[xy0[:,1],xy0[:,0]].astype(np.float32)
    b=image[xy0[:,1],xy1[:,0]].astype(np.float32)
    c=image[xy1[:,1],xy0[:,0]].astype(np.float32)
    d=image[xy1[:,1],xy1[:,0]].astype(np.float32)
    return ((a*(1-w[:,0,None])+b*w[:,0,None])*(1-w[:,1,None])+
            (c*(1-w[:,0,None])+d*w[:,0,None])*w[:,1,None])

tested=0;occluded=0;low_alpha=0;overlaps=0;shared_edge_texels=0;degenerate=0
selected=geometry['incremental_triangle_indices'] if a.base_projection else geometry['selected_triangle_indices'];start=time.time()
for order,face_index in enumerate(selected):
    face_index=int(face_index)
    native_triangle=triangles[face_index];world_triangle=points[native_triangle]
    chart=uv[loops[face_index]]*[1,-1]+[0,1]
    chart_pixels=chart*resolution-.5
    lower=np.maximum(np.ceil(chart_pixels.min(0)).astype(int),0)
    upper=np.minimum(np.floor(chart_pixels.max(0)).astype(int),resolution-1)
    if (upper<lower).any():continue
    delta0=chart_pixels[1]-chart_pixels[0];delta1=chart_pixels[2]-chart_pixels[0]
    denominator=delta0[0]*delta1[1]-delta0[1]*delta1[0]
    if abs(denominator)<1e-9:degenerate+=1;continue
    yy,xx=np.mgrid[lower[1]:upper[1]+1,lower[0]:upper[0]+1]
    xy=np.c_[xx.ravel(),yy.ravel()]
    difference=xy-chart_pixels[0]
    b1=(difference[:,0]*delta1[1]-difference[:,1]*delta1[0])/denominator
    b2=(delta0[0]*difference[:,1]-delta0[1]*difference[:,0])/denominator
    bary=np.c_[1-b1-b2,b1,b2]
    inside=(bary>=-1e-7).all(1)
    xy,bary=xy[inside],bary[inside]
    if len(xy)==0:continue
    existing=owner[xy[:,1],xy[:,0]]
    overlap=(existing>=0)&(existing!=face_index)
    if overlap.any():
        previous=existing[overlap]
        previous_chart=(uv[loops[previous]]*[1,-1]+[0,1])*resolution-.5
        pe1,pe2=previous_chart[:,1]-previous_chart[:,0],previous_chart[:,2]-previous_chart[:,0]
        pden=pe1[:,0]*pe2[:,1]-pe1[:,1]*pe2[:,0]
        pdiff=xy[overlap]-previous_chart[:,0]
        pb1=(pdiff[:,0]*pe2[:,1]-pdiff[:,1]*pe2[:,0])/pden
        pb2=(pe1[:,0]*pdiff[:,1]-pe1[:,1]*pdiff[:,0])/pden
        previous_bary=np.c_[1-pb1-pb2,pb1,pb2]
        previous_position=np.einsum('ij,ijk->ik',previous_bary,points[triangles[previous]])
        current_position=bary[overlap]@world_triangle
        same_surface=np.linalg.norm(previous_position-current_position,axis=1)<=1e-6
        overlaps+=int((~same_surface).sum())
        shared_edge_texels+=int(same_surface.sum())
    # Never overwrite an overlapping chart silently; the count remains a QA gate.
    xy,bary=xy[~overlap],bary[~overlap]
    if len(xy)==0:continue
    locations=bary@world_triangle
    old_coordinates=bary@old_uv[loops[face_index]]
    old_coordinates=old_coordinates*[1,-1]+[0,1]
    colors=sample(pixels['original'],old_coordinates)
    colors[:,3]=255
    chosen=np.full(len(xy),-1,np.int8)
    normal=np.cross(world_triangle[1]-world_triangle[0],world_triangle[2]-world_triangle[0])
    length=np.linalg.norm(normal)
    if length>1e-12:
        normal/=length
        confidence=np.array([abs(np.dot(normal,np.array(direction))) for direction in forwards])
        confidence[~coverage[:,face_index]]=0
        for camera_index in np.argsort(-confidence):
            if confidence[camera_index]<.08:continue
            local=locations@inverse[camera_index][:3,:3].T+inverse[camera_index][:3,3]
            clip=np.c_[local,np.ones(len(local))]@projections[camera_index].T
            source_uv=clip[:,:2]/clip[:,3,None]*[.5,-.5]+.5
            eligible=(chosen<0)&(source_uv>0).all(1)&(source_uv<1).all(1)
            if not eligible.any():continue
            ids=np.flatnonzero(eligible)
            projected=sample(pixels[views[camera_index]['view']],source_uv[ids])
            opaque=projected[:,3]>=240
            low_alpha+=int((~opaque).sum())
            for sample_index,color in zip(ids[opaque],projected[opaque]):
                origin=camera_matrices[camera_index]@Vector((float(local[sample_index,0]),float(local[sample_index,1]),0))
                location,hit_normal,hit,distance=tree.ray_cast(origin,forwards[camera_index],baseline['orthoScale']*6)
                tested+=1
                if location is not None and (hit==face_index or np.linalg.norm(np.array(location)-locations[sample_index])<1e-6):
                    colors[sample_index,:3]=color[:3]
                    chosen[sample_index]=camera_index
                else:occluded+=1
    atlas[xy[:,1],xy[:,0]]=np.clip(np.rint(colors),0,255).astype(np.uint8)
    owner[xy[:,1],xy[:,0]]=face_index
    assignments[xy[:,1],xy[:,0]]=chosen
    if order%1000==0:
        print('VISIBLE_DRESS_UV_PROGRESS',order,len(selected),'rays',tested,'seconds',round(time.time()-start,1),flush=True)
if retained_pixels is not None:assert np.array_equal(atlas[retained_pixels],pixels['previous_dress_atlas'][retained_pixels])
np.save(out/'dress_albedo_4k_encoded_rgba.npy',atlas)
np.save(out/'dress_projection_camera_assignment.npy',assignments)
np.save(out/'dress_uv_triangle_owner.npy',owner)
counts={view['view']:int((assignments==index).sum()) for index,view in enumerate(views)}
report=dict(uvGeneration=str(Path(a.generation).resolve()),uvGenerationSha256=sha(a.generation),
    cacheFile=str(Path(a.cache).resolve()),cacheSha256=sha(a.cache),resolution=[resolution,resolution],
    sourcePaintResolution=baseline['resolution'],selectedTriangles=len(selected),
    entireAssignedGarmentTriangles=len(geometry['selected_triangle_indices']),incrementalProjection=bool(a.base_projection),
    retainedAssignedTexelsUnchanged=retained_pixels is not None,
    baseProjection=a.base_projection,baseProjectionSha256=sha(a.base_projection) if a.base_projection else None,
    occupiedTexels=int((owner>=0).sum()),projectedTexels=sum(counts.values()),perCameraTexels=counts,
    originalColorFallbackTexels=int((assignments==-1).sum()),
    visibilityRayTests=tested,occludedAttemptsRejected=occluded,lowAlphaPaintAttemptsRejected=low_alpha,
    conflictingUvOverlapTexels=overlaps,sharedBoundaryTexelsProcessedOnce=shared_edge_texels,
    degenerateUvTriangles=degenerate,
    atlasData=str(out/'dress_albedo_4k_encoded_rgba.npy'),atlasDataSha256=sha(out/'dress_albedo_4k_encoded_rgba.npy'),
    cameraAssignments=str(out/'dress_projection_camera_assignment.npy'),
    cameraAssignmentsSha256=sha(out/'dress_projection_camera_assignment.npy'),
    triangleOwners=str(out/'dress_uv_triangle_owner.npy'),triangleOwnersSha256=sha(out/'dress_uv_triangle_owner.npy'),
    wholeCharacterWasTheOcclusionSurface=True,perTexelVisibilityChecked=True,
    strongestVisibleCameraSelected=True,colorSpace='encoded sRGB; no display transform',
    pngPackagingPending=True,fullCharacterMaterialIntegrationPending=True,comparisonRendersPending=True,
    fullDressCoverageApproved=False,characterFidelityVerified=False,published=False,
    newGlbOrFbxExported=False,additionalTripoCreditsConsumed=0,scriptSha256=sha(__file__))
(out/'projection.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(__file__,out/'executed_visible_uv_projection.py')
print('VISIBLE_DRESS_4K_PROJECTION_COMPLETE',json.dumps(report),flush=True)
