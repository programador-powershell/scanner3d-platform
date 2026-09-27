"""Fit reviewed sleeve UV charts into unused 4K space without moving existing UVs."""
import argparse,hashlib,json,shutil
from pathlib import Path
import cv2,numpy as np,xatlas
from scipy.ndimage import binary_dilation
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--approval',required=True);p.add_argument('--uv-generation',required=True);p.add_argument('--character-generation',required=True)
p.add_argument('--projection',required=True);p.add_argument('--output',required=True)
a=p.parse_args();read=lambda s:json.loads(Path(s).read_text());sha=lambda s:hashlib.sha256(Path(s).read_bytes()).hexdigest()
approval=read(a.approval);assert approval['safeForLocalSleeveProjection'];assert sha(approval['scopeFile'])==approval['scopeSha256']
scope=read(approval['scopeFile']);assert sha(scope['dataFile'])==scope['dataSha256']
g=read(a.uv_generation);character=read(a.character_generation);projection=read(a.projection)
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256'];assert sha(character['editableBlend'])==character['editableBlendSha256']
assert sha(projection['triangleOwners'])==projection['triangleOwnersSha256']
d=np.load(g['projectionGeometry']);s=np.load(scope['dataFile']);added=s['local_added_triangles'];selected=s['triangle_indices'];retained=np.setdiff1d(selected,added)
assert len(retained)==character['modifiedMaterialPolygons']
owner=np.load(projection['triangleOwners']);reserved=np.isin(owner,retained)
reserved=binary_dilation(reserved,iterations=5)
points,faces,loops=d['world_points'],d['triangles'],d['triangle_loops'];uv=d['dress_uv'].copy()
old_uv_tri=uv[loops[retained]];e1,e2=old_uv_tri[:,1]-old_uv_tri[:,0],old_uv_tri[:,2]-old_uv_tri[:,0]
uv_area=np.abs(e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]).sum()/2
old_world=points[faces[retained]];world_area=np.linalg.norm(np.cross(old_world[:,1]-old_world[:,0],old_world[:,2]-old_world[:,0]),axis=1).sum()/2
density=float(np.sqrt(uv_area*4096**2/world_area))
native,local=np.unique(faces[added],return_inverse=True);local=local.reshape(-1,3).astype(np.uint32)
atlas=xatlas.Atlas();atlas.add_mesh(points[native].astype(np.float32),local)
pack=xatlas.PackOptions();pack.texels_per_unit=density;pack.padding=4;pack.bilinear=True
chart_options=xatlas.ChartOptions();chart_options.max_iterations=2
atlas.generate(chart_options=chart_options,pack_options=pack)
mapping,indices,coordinates=atlas[0];assert np.array_equal(mapping[indices],local);assert atlas.atlas_count==1
# xatlas duplicates chart vertices. Connectivity in these UV indices therefore
# recovers each chart, without needing unavailable chart-introspection APIs.
u=indices[:,[0,1,2]].ravel();v=indices[:,[1,2,0]].ravel()
graph=coo_matrix((np.ones(len(u),np.uint8),(u,v)),shape=(len(coordinates),len(coordinates))).tocsr()
count,labels=connected_components(graph,directed=False)
face_labels=labels[indices[:,0]];assert np.all(labels[indices]==face_labels[:,None])
pixel_coordinates=coordinates*np.array([atlas.width,atlas.height])
charts=[]
for label in np.unique(face_labels):
    face_ids=np.flatnonzero(face_labels==label);corners=pixel_coordinates[indices[face_ids]].copy()
    corners-=corners.min(axis=(0,1));bounds=np.ceil(corners.max(axis=(0,1))).astype(int)
    charts.append((int((bounds+10).prod()),face_ids,corners,bounds))
placements=[];padding=5;pending=list(charts);split_count=0
while pending:
    pending.sort(key=lambda row:row[0])
    _,face_ids,corners,bounds=pending.pop()
    found=None
    integral=cv2.integral(reserved.astype(np.uint8),sdepth=cv2.CV_32S)
    for rotate in (False,True):
        local_corners=corners if not rotate else corners[...,::-1]
        size=(bounds if not rotate else bounds[::-1])+padding*2+1;w,h=map(int,size)
        if w>4096 or h>4096:continue
        # Evaluate padded rectangle positions every four pixels. Texture texel
        # owners and their existing gutters stay reserved during every placement.
        sums=integral[h:,w:][::4,::4]-integral[:-h,w:][::4,::4]-integral[h:,:-w][::4,::4]+integral[:-h,:-w][::4,::4]
        positions=np.argwhere(sums==0)
        if len(positions):
            yy,xx=positions[0]*4;found=(int(xx),int(yy),w,h,local_corners,rotate);break
    if found is None:
        assert len(face_ids)>1, f'No safe unused rectangle for one sleeve triangle with bounds {bounds.tolist()}'
        # Add only UV seams. Subdivide an oversized chart spatially, preserving
        # every triangle's parameterization and texel density in both children.
        axis=int(np.argmax(bounds));order=np.argsort(corners.mean(1)[:,axis]);half=len(order)//2
        for subset in (order[:half],order[half:]):
            child=corners[subset].copy();child-=child.min(axis=(0,1));child_bounds=np.ceil(child.max(axis=(0,1))).astype(int)
            pending.append((int((child_bounds+10).prod()),face_ids[subset],child,child_bounds))
        split_count+=1
        continue
    xx,yy,w,h,local_corners,rotate=found;reserved[yy:yy+h,xx:xx+w]=True
    # Occupancy is in image coordinates (top down), whereas Blender UV is bottom up.
    image_uv=(local_corners+[xx+padding,yy+padding])/4096
    uv[loops[added[face_ids]]]=image_uv*[1,-1]+[0,1]
    placements.append(dict(triangles=added[face_ids].tolist(),pixelOrigin=[xx,yy],pixelBounds=[w,h],rotated=rotate))
assert np.array_equal(uv[loops[retained]],d['dress_uv'][loops[retained]])
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
data=out/'projection_uv_geometry.npz'
np.savez_compressed(data,world_points=points,vertices=d['vertices'],triangles=faces,triangle_loops=loops,polygon_indices=d['polygon_indices'],original_uv=d['original_uv'],dress_uv=uv,selected_triangle_indices=selected,visible_camera_masks=s['visible_camera_masks'],incremental_triangle_indices=added,retained_triangle_indices=retained)
report=dict(g);report.update(dict(parentCharacterGeneration=a.character_generation,parentCharacterGenerationSha256=sha(a.character_generation),editableBlend=character['editableBlend'],editableBlendSha256=character['editableBlendSha256'],editableBytes=character['editableBytes'],
    localApproval=a.approval,localApprovalSha256=sha(a.approval),sourceScopeFile=approval['scopeFile'],sourceScopeSha256=approval['scopeSha256'],projectionGeometry=str(data),projectionGeometrySha256=sha(data),
    selectedTriangles=len(selected),selectedPolygons=len(selected),incrementalTriangles=len(added),retainedTriangles=len(retained),retainedUvCoordinatesUnchanged=True,localChartCount=len(charts),placements=placements,texelsPerWorldUnit=density,
    layoutAppliedToEditableBlend=False,materialIntegrationPending=True,fullDressCoverageApproved=False,characterFidelityVerified=False,published=False,scriptSha256=sha(__file__)))
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_local_uv_packing.py')
print('LOCAL_SLEEVE_UV_PACKED',json.dumps(dict(triangles=len(added),charts=len(placements),additionalUvSeams=split_count,texelsPerWorldUnit=density,existingUvMoved=False)),flush=True)
