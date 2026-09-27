"""Preserve the good UV layout and give only foldover faces independent space."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--audit',required=True)
p.add_argument('--additional-audit')
p.add_argument('--output',required=True)
a=p.parse_args();read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
g,audit=read(a.generation),read(a.audit)
assert audit['uvGenerationSha256']==sha(a.generation)
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
d=np.load(g['projectionGeometry']);selected=d['selected_triangle_indices'];loops=d['triangle_loops']
bad=sorted({r['secondTriangle'] for r in audit['overlaps'] if r['harmfulOverlap']})
if a.additional_audit:
    extra=read(a.additional_audit)
    assert Path(extra['uvGeneration']).resolve()==Path(a.generation).resolve()
    bad=sorted(set(bad)|{row['secondTriangle'] for row in extra['overlaps']})
assert bad
resolution=4096;padding=4;strip_width=56;good_scale=(resolution-strip_width)/resolution
uv=d['original_uv'].copy();uv[loops[selected]]=d['dress_uv'][loops[selected]]*good_scale
placements=[];cursor=padding
for face in sorted(bad,key=lambda i:-float(np.ptp(d['dress_uv'][loops[i]],axis=0).max())):
    original=d['dress_uv'][loops[face]]*resolution
    local=original-original.min(0)
    if np.ptp(local[:,0])>np.ptp(local[:,1]):local=np.c_[local[:,1],-local[:,0]]
    local-=local.min(0)
    width,height=np.ptp(local,axis=0)
    assert width+padding*2<strip_width
    assert cursor+height+padding<resolution
    position=np.array([resolution-strip_width+padding,cursor])
    uv[loops[face]]=(local+position)/resolution
    placements.append(dict(triangle=int(face),pixelOrigin=position.tolist(),pixelBounds=[float(width),float(height)]))
    cursor+=int(np.ceil(height))+padding*2
tri_uv=uv[loops[selected]];e1,e2=tri_uv[:,1]-tri_uv[:,0],tri_uv[:,2]-tri_uv[:,0]
area=float(np.abs(e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]).sum()/2)
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
target=out/'dense_dress_uv_coordinates.npz'
np.savez_compressed(target,dress_uv=uv,selected_triangle_indices=selected,
    original_vertices=d['vertices'],original_triangles=d['triangles'],original_triangle_loops=loops)
report=dict(uvGeneration=a.generation,uvGenerationSha256=sha(a.generation),
    additionalAudit=a.additional_audit,additionalAuditSha256=sha(a.additional_audit) if a.additional_audit else None,
    collisionAudit=a.audit,collisionAuditSha256=sha(a.audit),
    coordinateFile=str(target),coordinateFileSha256=sha(target),uvArea=area,
    targetTextureDimensions=[resolution,resolution],nativePackingDimensions=[resolution,resolution],
    reservedStripWidthPixels=strip_width,goodLayoutUniformScale=good_scale,
    repairedTrianglePixelShapesPreserved=True,localUvSeamFaces=bad,placements=placements,
    usedStripHeightPixels=cursor,paddingPixels=padding,garmentGeometryNotCut=True,
    geometryAndWeightsNotEdited=True,repairedLayoutNeedsRasterOverlapCheck=True,
    published=False,newGlbOrFbxExported=False,scriptSha256=sha(__file__))
(out/'layout.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,out/'executed_local_uv_strip_placement.py')
print('LOCAL_UV_REPAIR_STRIP_PREPARED',json.dumps({k:v for k,v in report.items() if k not in ['placements','localUvSeamFaces']}),flush=True)
