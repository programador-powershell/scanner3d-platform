"""Package the computed 3D UV texels losslessly, adding UV filtering gutters."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--projection',required=True);p.add_argument('--output',required=True)
a=p.parse_args();read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
g=read(a.projection);assert sha(g['atlasData'])==g['atlasDataSha256']
assert sha(g['triangleOwners'])==g['triangleOwnersSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
atlas=np.load(g['atlasData']);owners=np.load(g['triangleOwners'])
assert atlas.shape==(4096,4096,4)
distance,nearest=distance_transform_edt(owners<0,return_indices=True)
padding=(owners<0)&(distance<=4)
atlas[padding]=atlas[nearest[0][padding],nearest[1][padding]]
target=out/'chapeleiro_dress_albedo_4k_first_pass.png'
Image.fromarray(atlas).save(target,compress_level=6)
with Image.open(target) as image:assert image.size==(4096,4096) and image.mode=='RGBA'
report=dict(projectionFile=a.projection,projectionSha256=sha(a.projection),
    uvGeneration=g['uvGeneration'],uvGenerationSha256=g['uvGenerationSha256'],
    textureFile=str(target),textureSha256=sha(target),textureBytes=target.stat().st_size,
    resolution=[4096,4096],mode='RGBA',colorSpace='sRGB',paddingTexels=int(padding.sum()),
    paddingDistancePixels=4,computedTexelsPackagedLosslessly=True,
    conflictingUvOverlapTexels=g['conflictingUvOverlapTexels'],
    projectedTexels=g['projectedTexels'],originalColorFallbackTexels=g['originalColorFallbackTexels'],
    fullCharacterMaterialIntegrationPending=True,comparisonRendersPending=True,
    fullDressCoverageApproved=False,characterFidelityVerified=False,published=False,
    newGlbOrFbxExported=False)
(out/'texture.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
