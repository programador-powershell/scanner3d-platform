"""Compare bright filament ridges with the unchanged own-photo crop.

Requires numpy, Pillow, scipy and scikit-image. These are diagnostic candidates,
not approved fabric, invented replacement reference photos or 3D models.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import gaussian_filter
from skimage.filters import meijering,sato,frangi,apply_hysteresis_threshold
from skimage.morphology import skeletonize,remove_small_objects

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--photo',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
photo=Path(args.photo);out=Path(args.output)
photo_sha=hashlib.sha256(photo.read_bytes()).hexdigest()
if photo_sha!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Require the unchanged own foundation photo.')
if out.exists():raise ValueError('Preserve actual diagnostic')
out.mkdir(parents=True)
original=Image.open(photo).convert('RGB').crop((649,344,727,368))
original.save(out/'original_source_crop.png')
scale=4
grey=np.asarray(original.convert('L').resize((312,96),Image.Resampling.BICUBIC),dtype=float)/255
contrast=grey-gaussian_filter(grey,12)
contrast=(contrast-contrast.min())/(contrast.max()-contrast.min())
candidates=[]
for method,func in [('meijering',meijering),('sato',sato),('frangi',frangi)]:
    ridge=func(contrast,sigmas=[1,2,3],black_ridges=False)
    ridge/=max(ridge.max(),1e-12)
    for high in [.22,.35]:
        positive=apply_hysteresis_threshold(ridge,high*.5,high)&(grey>.23)
        positive=remove_small_objects(positive,max_size=7)
        skeleton=skeletonize(positive)
        name=f'{method}_{high:.2f}'
        Image.fromarray((skeleton*255).astype('uint8')).save(out/(name+'.png'))
        candidates.append({'name':name,'skeletonPixels':int(skeleton.sum()),'approved':False})
board=Image.new('RGB',(960,7*145),'#242424');draw=ImageDraw.Draw(board)
for row,item in enumerate([{'name':'original'}]+candidates):
    y=row*145
    board.paste(original.resize((468,144),Image.Resampling.NEAREST),(0,y))
    if row:
        overlay=original.resize((468,144),Image.Resampling.BICUBIC)
        mask=Image.open(out/(item['name']+'.png')).resize((468,144),Image.Resampling.NEAREST)
        overlay.paste('#72edaa',(0,0),mask);board.paste(overlay,(480,y))
    draw.text((488,y+4),item['name'],fill='white')
board.save(out/'ridge_candidates.png')
(out/'diagnostic.json').write_text(json.dumps({'photo':str(photo.resolve()),'photoSha256':photo_sha,
    'crop':[649,344,727,368],'workingScale':scale,'originalPhotoChanged':False,'candidates':candidates,
    'fidelityVerified':False,'newModelAuthored':False,
    'methodDocumentation':'https://scikit-image.org/docs/stable/auto_examples/edges/plot_ridge_filter.html'},indent=2),encoding='utf-8')
print(json.dumps(candidates))
