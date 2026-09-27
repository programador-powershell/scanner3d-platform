"""Decode existing source PNGs verbatim for the 3D UV projector."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--base-texture',help='Previously integrated 4K texture for an incremental local projection')
a=p.parse_args();g=json.loads(Path(a.generation).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(g['sourceBasecolor'])==g['sourceBasecolorSha256']
paint=json.loads(Path(g['paintSources']).read_text())
assert sha(g['paintSources'])==g['paintSourcesSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
rows=[dict(view='original',image=g['sourceBasecolor'],sha256=g['sourceBasecolorSha256'])]+paint['sources']
if a.base_texture:
    previous=json.loads(Path(a.base_texture).read_text())
    rows.append(dict(view='previous_dress_atlas',image=previous['textureFile'],sha256=previous['textureSha256']))
result=[]
for row in rows:
    assert sha(row['image'])==row['sha256']
    with Image.open(row['image']) as image:pixels=np.array(image.convert('RGBA'))
    target=out/(row['view']+'_encoded_rgba.npy');np.save(target,pixels)
    result.append(dict(view=row['view'],source=row['image'],sourceSha256=row['sha256'],
        dataFile=str(target),dataSha256=sha(target),shape=list(pixels.shape),
        alphaMin=int(pixels[:,:,3].min()),alphaMax=int(pixels[:,:,3].max())))
path=out/'pixel_cache.json';path.write_text(json.dumps(dict(uvGeneration=a.generation,
    uvGenerationSha256=sha(a.generation),sources=result,encodedSrgbPreserved=True,
    imagesNotRetouched=True),indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(cache=str(path),sources=result)))
