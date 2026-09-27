"""Check repaired 4K UV coverage against actual 3D positions before projection."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--layout',required=True);p.add_argument('--output',required=True)
a=p.parse_args();read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
layout=read(a.layout);assert sha(layout['coordinateFile'])==layout['coordinateFileSha256']
g=read(layout['uvGeneration']);assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
d=np.load(g['projectionGeometry']);r=np.load(layout['coordinateFile'])
faces=d['triangles'];points=d['world_points'];chart=(r['dress_uv'][d['triangle_loops']]*[1,-1]+[0,1])*4096-.5
owners=np.full((4096,4096),-1,np.int32);rows=[];shared=0
for face in d['selected_triangle_indices']:
    face=int(face);triangle=chart[face]
    lower=np.maximum(np.ceil(triangle.min(0)).astype(int),0);upper=np.minimum(np.floor(triangle.max(0)).astype(int),4095)
    if (upper<lower).any():continue
    e1,e2=triangle[1]-triangle[0],triangle[2]-triangle[0];den=e1[0]*e2[1]-e1[1]*e2[0]
    if abs(den)<1e-9:continue
    yy,xx=np.mgrid[lower[1]:upper[1]+1,lower[0]:upper[0]+1];xy=np.c_[xx.ravel(),yy.ravel()]
    delta=xy-triangle[0]
    b1=(delta[:,0]*e2[1]-delta[:,1]*e2[0])/den;b2=(e1[0]*delta[:,1]-e1[1]*delta[:,0])/den
    bary=np.c_[1-b1-b2,b1,b2];inside=(bary>=-1e-7).all(1);xy,bary=xy[inside],bary[inside]
    previous=owners[xy[:,1],xy[:,0]];different=(previous>=0)&(previous!=face)
    if different.any():
        overlap_xy=xy[different];overlap_bary=bary[different];previous=previous[different]
        previous_chart=chart[previous];p1,p2=previous_chart[:,1]-previous_chart[:,0],previous_chart[:,2]-previous_chart[:,0]
        pd=p1[:,0]*p2[:,1]-p1[:,1]*p2[:,0];difference=overlap_xy-previous_chart[:,0]
        c1=(difference[:,0]*p2[:,1]-difference[:,1]*p2[:,0])/pd
        c2=(p1[:,0]*difference[:,1]-p1[:,1]*difference[:,0])/pd
        pb=np.c_[1-c1-c2,c1,c2]
        position=overlap_bary@points[faces[face]];previous_position=np.einsum('ij,ijk->ik',pb,points[faces[previous]])
        gaps=np.linalg.norm(position-previous_position,axis=1)
        for pixel,other,gap in zip(overlap_xy,previous,gaps):
            if gap>1e-6:rows.append(dict(pixel=pixel.tolist(),firstTriangle=int(other),secondTriangle=face,physicalSeparationMeters=float(gap)))
            else:shared+=1
    free=~different;owners[xy[free,1],xy[free,0]]=face
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
report=dict(layoutFile=a.layout,layoutSha256=sha(a.layout),uvGeneration=layout['uvGeneration'],
    occupiedTexels=int((owners>=0).sum()),harmfulUvOverlapTexels=len(rows),coincidentBoundaryTexels=shared,
    rasterResolution=[4096,4096],physicalCoincidenceToleranceMeters=1e-6,overlaps=rows,
    safeToProject=len(rows)==0,geometryAndWeightsNotModified=True)
(out/'layout_raster_check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='overlaps'}))
