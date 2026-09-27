"""Extract reviewable fine thread paths from this stage's own photographic crop.

This is an inferred embroidery construction, not replacement reference art or
approved fidelity. Dark fold regions do not become flat polygonal cut-outs.
"""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--photo',required=True)
parser.add_argument('--mask',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--working-scale',type=int,default=1)
parser.add_argument('--already-skeleton',action='store_true')
parser.add_argument('--minimum-source-length',type=float,default=1.5)
args=parser.parse_args()
photo=Path(args.photo);mask_path=Path(args.mask);out=Path(args.output)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(photo)!='f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Require the unchanged own foundation photo.')
if out.exists():raise ValueError('Preserve each actual diagnostic.')
source=np.asarray(Image.open(photo).convert('RGB'))
crop=source[344:368,649:727].copy()
mask=(np.asarray(Image.open(mask_path).convert('L'))>127).astype(np.uint8)
working_scale=args.working_scale
if working_scale<1 or mask.shape!=tuple(s*working_scale for s in crop.shape[:2]):
    raise ValueError('Wrong photographic interpretation dimensions.')

def thin(values):
    work=np.pad(values,1)
    rounds=0
    for iteration in range(100):
        changed=0
        for second in [False,True]:
            center=work[1:-1,1:-1]
            p=[work[:-2,1:-1],work[:-2,2:],work[1:-1,2:],work[2:,2:],
               work[2:,1:-1],work[2:,:-2],work[1:-1,:-2],work[:-2,:-2]]
            neighbors=sum(p)
            transitions=sum(((p[i]==0)&(p[(i+1)%8]==1)).astype(np.uint8) for i in range(8))
            if second:condition=(p[0]*p[2]*p[6]==0)&(p[0]*p[4]*p[6]==0)
            else:condition=(p[0]*p[2]*p[4]==0)&(p[2]*p[4]*p[6]==0)
            erase=(center==1)&(neighbors>=2)&(neighbors<=6)&(transitions==1)&condition
            changed+=int(erase.sum());center[erase]=0
        rounds=iteration+1
        if not changed:break
    else:raise ValueError('Thread path thinning did not converge.')
    return work[1:-1,1:-1],rounds

skeleton,rounds=(mask,0) if args.already_skeleton else thin(mask)
pixels={(int(x),int(y)) for y,x in np.argwhere(skeleton)}
graph={p:set() for p in pixels}
for x,y in sorted(pixels):
    for dx,dy in [(1,0),(0,1),(1,1),(1,-1)]:
        neighbor=(x+dx,y+dy)
        if neighbor not in pixels:continue
        if dx and dy and ((x+dx,y) in pixels or (x,y+dy) in pixels):continue
        graph[(x,y)].add(neighbor);graph[neighbor].add((x,y))
edges={tuple(sorted((a,b))) for a,neighbors in graph.items() for b in neighbors}
remaining=set(edges);paths=[]
def follow(start,next_point):
    points=[start,next_point]
    remaining.remove(tuple(sorted((start,next_point))))
    previous,current=start,next_point
    while len(graph[current])==2:
        onward=next(p for p in sorted(graph[current]) if p!=previous)
        edge=tuple(sorted((current,onward)))
        if edge not in remaining:break
        remaining.remove(edge);points.append(onward)
        previous,current=current,onward
        if current==start:break
    closed=points[-1]==points[0]
    if closed:points.pop()
    length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    if closed:length+=math.dist(points[-1],points[0])
    if length/working_scale>=args.minimum_source_length and len(points)>=2:
        points=[[(x+.5)/working_scale,(y+.5)/working_scale] for x,y in points]
        paths.append({'closed':closed,'points':points,'sourceLengthPixels':length/working_scale})
for start in sorted(p for p,n in graph.items() if len(n)!=2):
    for neighbor in sorted(graph[start]):
        if tuple(sorted((start,neighbor))) in remaining:follow(start,neighbor)
while remaining:
    start,neighbor=min(remaining);follow(start,neighbor)
if not paths:raise ValueError('No actual photographed thread paths were extracted.')
out.mkdir(parents=True)
Image.fromarray(crop).save(out/'original_source_crop.png')
Image.fromarray(skeleton*255).save(out/'thread_skeleton.png')
scale=8;width,height=crop.shape[1]*scale,crop.shape[0]*scale
board=Image.new('RGB',(width*2+24,height+64),'#242424')
board.paste(Image.fromarray(crop).resize((width,height)),(0,28))
draw=ImageDraw.Draw(board)
for path in paths:
    points=[(width+24+x*scale,28+y*scale) for x,y in path['points']]
    if path['closed']:points.append(points[0])
    draw.line(points,fill='#e8ddc6',width=3)
draw.text((8,8),'UNCHANGED OWN PHOTO / INFERRED THREAD PATHS — REVIEW REQUIRED',fill='white')
draw.text((8,height+38),'Fold shading is not geometric fidelity; the full stage photo stays authoritative.',fill='white')
board.save(out/'original_vs_thread_paths.png')
record={'sourcePhoto':str(photo.resolve()),'sourcePhotoSha256':sha(photo),
    'sourcePhotoCrop':[649,344,727,368],'width':crop.shape[1],'height':crop.shape[0],
    'interpretedMask':str(mask_path.resolve()),'interpretedMaskSha256':sha(mask_path),
    'method':('trace reviewed bright-ridge skeleton; smooth only during 3D authoring' if args.already_skeleton
              else 'thin positive local-contrast thread regions; trace graph chains; smooth only during 3D authoring'),
    'workingScale':working_scale,'minimumSourceLength':args.minimum_source_length,
    'sewnHeaderPixels':3,'thinningRounds':rounds,'sourceGraphPixels':len(pixels),
    'sourceGraphEdges':len(edges),'paths':paths,'openPaths':sum(not p['closed'] for p in paths),
    'closedPaths':sum(p['closed'] for p in paths),'originalPhotoChanged':False,
    'unseenBackAndRepeatsInferred':True,'threadInterpretationApproved':False,
    'fidelityVerified':False,'rigPresent':False,'additionalCreditsConsumed':0}
(out/'thread_paths.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:record[key] for key in ['sourceGraphPixels','sourceGraphEdges','openPaths','closedPaths','fidelityVerified']}))
