"""Audit possible raster overlaps using the actual 3D positions at each texel."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--projection',required=True);p.add_argument('--output',required=True)
a=p.parse_args();read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
projection=read(a.projection);g=read(projection['uvGeneration'])
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
assert sha(projection['triangleOwners'])==projection['triangleOwnersSha256']
d=np.load(g['projectionGeometry']);owners=np.load(projection['triangleOwners'])
faces=d['triangles'];points=d['world_points'];uv=d['dress_uv'][d['triangle_loops']]
chart=(uv*[1,-1]+[0,1])*4096-.5
rows=[]
for face in d['selected_triangle_indices']:
    face=int(face);triangle=chart[face]
    lower=np.maximum(np.ceil(triangle.min(0)).astype(int),0)
    upper=np.minimum(np.floor(triangle.max(0)).astype(int),4095)
    if (upper<lower).any():continue
    e1,e2=triangle[1]-triangle[0],triangle[2]-triangle[0]
    den=e1[0]*e2[1]-e1[1]*e2[0]
    if abs(den)<1e-9:continue
    yy,xx=np.mgrid[lower[1]:upper[1]+1,lower[0]:upper[0]+1]
    xy=np.c_[xx.ravel(),yy.ravel()];delta=xy-triangle[0]
    b1=(delta[:,0]*e2[1]-delta[:,1]*e2[0])/den
    b2=(e1[0]*delta[:,1]-e1[1]*delta[:,0])/den
    bary=np.c_[1-b1-b2,b1,b2]
    inside=(bary>=-1e-7).all(1);xy,bary=xy[inside],bary[inside]
    previous=owners[xy[:,1],xy[:,0]]
    different=(previous>=0)&(previous!=face)
    if not different.any():continue
    xy,bary,previous=xy[different],bary[different],previous[different]
    if not len(xy):continue
    previous_chart=chart[previous]
    p1,p2=previous_chart[:,1]-previous_chart[:,0],previous_chart[:,2]-previous_chart[:,0]
    previous_den=p1[:,0]*p2[:,1]-p1[:,1]*p2[:,0]
    delta=xy-previous_chart[:,0]
    c1=(delta[:,0]*p2[:,1]-delta[:,1]*p2[:,0])/previous_den
    c2=(p1[:,0]*delta[:,1]-p1[:,1]*delta[:,0])/previous_den
    previous_bary=np.c_[1-c1-c2,c1,c2]
    position=bary@points[faces[face]]
    previous_position=np.einsum('ij,ijk->ik',previous_bary,points[faces[previous]])
    distance=np.linalg.norm(position-previous_position,axis=1)
    for pixel,other,gap in zip(xy,previous,distance):
        rows.append(dict(pixel=pixel.tolist(),firstTriangle=int(other),secondTriangle=face,
                         physicalSeparationMeters=float(gap),harmfulOverlap=bool(gap>1e-6)))
assert len(rows)==projection['conflictingUvOverlapTexels']+projection['sharedBoundaryTexelsProcessedOnce']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
report=dict(projectionFile=a.projection,projectionSha256=sha(a.projection),
    uvGeneration=projection['uvGeneration'],uvGenerationSha256=sha(projection['uvGeneration']),
    initiallySuspectedOverlapTexels=projection['conflictingUvOverlapTexels'],allOverlappingTriangleTexels=len(rows),
    coincidentBoundaryTexels=sum(not r['harmfulOverlap'] for r in rows),
    harmfulUvOverlapTexels=sum(r['harmfulOverlap'] for r in rows),
    maximumPhysicalSeparationMeters=max((r['physicalSeparationMeters'] for r in rows),default=0),
    physicalCoincidenceToleranceMeters=1e-6,overlaps=rows,
    originalUvAndMeshNotModified=True)
(out/'uv_collision_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='overlaps'}))
