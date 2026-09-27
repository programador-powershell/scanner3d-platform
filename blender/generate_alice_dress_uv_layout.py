"""Generate dense garment-only UV coordinates without replacing mesh vertices.

xatlas receives a temporary indexed surface. Its duplicated UV vertices map
back to the original polygon loops; the complete character geometry and weights
are never replaced by this temporary parameterization mesh.
"""
import argparse,hashlib,importlib.metadata,json,shutil,time
from pathlib import Path
import numpy as np
import xatlas
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
a=p.parse_args();g=json.loads(Path(a.generation).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(g['projectionGeometry'])==g['projectionGeometrySha256']
geometry=np.load(g['projectionGeometry'])
selected=geometry['selected_triangle_indices'];faces=geometry['triangles'][selected]
native_indices,local_indices=np.unique(faces,return_inverse=True)
local_faces=local_indices.reshape(-1,3).astype(np.uint32)
points=geometry['world_points'][native_indices].astype(np.float32)
atlas=xatlas.Atlas();atlas.add_mesh(points,local_faces)
charts=xatlas.ChartOptions();charts.max_iterations=2
pack=xatlas.PackOptions();pack.resolution=4096;pack.padding=4;pack.bilinear=True
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
print('XATLAS_GARMENT_LAYOUT_START',len(points),len(faces),flush=True)
start=time.time();atlas.generate(chart_options=charts,pack_options=pack)
mapping,indices,coordinates=atlas[0]
assert np.array_equal(mapping[indices],local_faces)
assert atlas.atlas_count==1
loop_uv=geometry['original_uv'].copy()
loop_uv[geometry['triangle_loops'][selected]]=coordinates[indices]
tri_uv=coordinates[indices]
e1,e2=tri_uv[:,1]-tri_uv[:,0],tri_uv[:,2]-tri_uv[:,0]
uv_area=float(np.abs(e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]).sum()/2)
assert np.isfinite(tri_uv).all() and uv_area>.20
target=out/'dense_dress_uv_coordinates.npz'
np.savez_compressed(target,dress_uv=loop_uv,selected_triangle_indices=selected,
    original_vertices=geometry['vertices'],original_triangles=geometry['triangles'],
    original_triangle_loops=geometry['triangle_loops'])
report=dict(uvGeneration=a.generation,uvGenerationSha256=sha(a.generation),
    coordinateFile=str(target),coordinateFileSha256=sha(target),uvArea=uv_area,
    atlasUtilization=float(atlas.utilization),nativePackingDimensions=[atlas.width,atlas.height],
    targetTextureDimensions=[4096,4096],paddingPixels=4,bilinearPadding=True,
    charts=atlas.chart_count,xatlasVersion=importlib.metadata.version('xatlas'),
    duplicatedVerticesUsedOnlyForUvMapping=True,nativeVertexMappingExact=True,
    elapsedSeconds=time.time()-start,modelNotEdited=True,newGlbOrFbxExported=False,published=False,
    scriptSha256=sha(__file__))
(out/'layout.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,out/'executed_uv_layout_generation.py')
print('XATLAS_GARMENT_LAYOUT_COMPLETE',json.dumps(report),flush=True)
