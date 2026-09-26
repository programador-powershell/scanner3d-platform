"""Trace lace apertures from the original foundation photo for mesh construction.

These are diagnostic crops and contour data, not replacement reference images.
Shaded photographic folds remain an uncertainty; every contour is reviewable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--photo', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--section', choices=['petticoats', 'bloomers', 'corset'], default='petticoats')
args = parser.parse_args()
photo = Path(args.photo)
photo_hash = hashlib.sha256(photo.read_bytes()).hexdigest()
if photo_hash != 'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('The unmodified foundation photograph is required.')
out = Path(args.output)
if out.exists():
    raise ValueError('Choose a new diagnostic directory.')
out.mkdir(parents=True)
source = np.asarray(Image.open(photo).convert('RGB'))
records = []
tiles = [
    ('ivory', (758, 685, 866, 737), 94, 5),
    ('black', (715, 1000, 860, 1059), 26, 4),
]
if args.section == 'bloomers':
    tiles = [('bloomer hem', (62, 1283, 141, 1308), 85, 3)]
if args.section == 'corset':
    tiles = [('corset hem', (663, 251, 703, 286), 88, 2)]
for label, box, threshold, header in tiles:
    x0, y0, x1, y1 = box
    tile = source[y0:y1, x0:x1].copy()
    grey = cv2.cvtColor(tile, cv2.COLOR_RGB2GRAY)
    mask = (grey >= threshold).astype(np.uint8) * 255
    # The photograph's attachment seam is structurally continuous. Keep a
    # narrow sewn header, rather than disconnected islands floating at the hem.
    seam = [11, 24] if args.section == 'corset' else None
    if seam:
        # The pointed corset's photographed hem is inclined. Keep its actual
        # raw photo UVs while mapping the sewn header onto the curved 3D rim.
        for x in range(mask.shape[1]):
            start=int(round(seam[0]+(seam[1]-seam[0])*x/(mask.shape[1]-1)))
            mask[:start, x]=0
            mask[start:start+header, x]=255
    else:
        mask[:header, :] = 255
    count, components, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    retained = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= 4:
            retained[components == index] = 255
    contours, hierarchy = cv2.findContours(retained, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    outlines = []
    for index, contour in enumerate(contours):
        if abs(cv2.contourArea(contour)) < 1.5:
            continue
        points = cv2.approxPolyDP(contour, .35, True)[:, 0, :].astype(float)
        if len(points) < 3:
            continue
        outlines.append({'hole': bool(hierarchy[0, index, 3] >= 0), 'points': points.tolist()})
    tile_file = out / (label + '_source_crop.png')
    Image.fromarray(tile).save(tile_file)
    mask_file = out / (label + '_contour_mask.png')
    Image.fromarray(retained).save(mask_file)
    board = Image.new('RGB', (tile.shape[1] * 8, tile.shape[0] * 4 + 28), '#242424')
    board.paste(Image.fromarray(tile).resize((tile.shape[1]*4, tile.shape[0]*4)), (0,28))
    board.paste(Image.fromarray(retained).convert('RGB').resize((tile.shape[1]*4,tile.shape[0]*4)), (tile.shape[1]*4,28))
    ImageDraw.Draw(board).text((8,8), label + ': ORIGINAL PHOTO CROP / TRACE MASK (review shadows)', fill='white')
    board.save(out / (label + '_trace_review.png'))
    records.append({'name': label, 'sourcePhotoCrop': list(box),
                    'width': tile.shape[1], 'height': tile.shape[0],
                    'threshold': threshold, 'continuousHeaderPixels': header,
                    'crop': str(tile_file.resolve()), 'mask': str(mask_file.resolve()),
                    'cropSha256': hashlib.sha256(tile_file.read_bytes()).hexdigest(),
                    'contours': outlines, 'retainedHoles': sum(o['hole'] for o in outlines),
                    'occupiedFraction': float(np.count_nonzero(retained) / retained.size)})
    if seam:
        records[-1].update(attachmentSeamPixels=seam,laceDepthPixels=16,
                           seamMapping='Raw photo UV retained; inclined seam flattened only in authored geometry.')
report = {'sourcePhoto': str(photo.resolve()), 'sourcePhotoSha256': photo_hash,
          'section': args.section,
          'purpose': 'Actual apertures for new internal lace geometry; original photo stays authoritative.',
          'limitation': 'Photographic shadows and folds affect tracing; unseen repeats are inferred.',
          'tiles': records}
(out / 'lace_contours.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='tiles'}))
print(json.dumps([{'name':r['name'], 'holes':r['retainedHoles'], 'occupiedFraction':r['occupiedFraction']} for r in records]))
