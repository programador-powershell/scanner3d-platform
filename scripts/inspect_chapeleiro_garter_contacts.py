"""Diagnose cup/web contacts in the actual exported GLB, without scene changes."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser()
parser.add_argument('--generation',required=True)
parser.add_argument('--minimum-clearance',type=float,default=.00015)
args=parser.parse_args()
if args.minimum_clearance<=0:raise ValueError('Require a positive rest-clearance threshold.')
generation=Path(args.generation)
record=json.loads(generation.read_text(encoding='utf-8'))
data=Path(record['model']).read_bytes()
if hashlib.sha256(data).hexdigest()!=record['modelSha256']:
    raise ValueError('The actual model changed after generation.')
size=struct.unpack_from('<I',data,12)[0]
doc=json.loads(data[20:20+size]);binary=data[28+size:]
def accessor(index):
    a=doc['accessors'][index];view=doc['bufferViews'][a['bufferView']]
    dtype={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]
    cols={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];width=np.dtype(dtype).itemsize
    return np.ndarray((a['count'],cols),dtype=dtype,buffer=binary,
        offset=view.get('byteOffset',0)+a.get('byteOffset',0),strides=(view.get('byteStride',cols*width),width))
def mesh(name):
    index=next(i for i,n in enumerate(doc['nodes']) if n.get('name')==name)
    node=doc['nodes'][index]
    # These exported construction objects have identity local transforms.
    current=index;seen=set()
    while current is not None:
        if current in seen:raise ValueError('Cyclic actual node hierarchy.')
        seen.add(current)
        if any(k in doc['nodes'][current] for k in ['matrix','rotation','translation','scale']):
            raise ValueError('Inspect the actual node or ancestor transform before projecting.')
        parents=[i for i,n in enumerate(doc['nodes']) if current in n.get('children',[])]
        if len(parents)>1:raise ValueError('Ambiguous actual node hierarchy.')
        current=parents[0] if parents else None
    primitives=doc['meshes'][node['mesh']]['primitives']
    if len(primitives)!=1:raise ValueError('Inspect all materials before projecting this mesh.')
    primitive=primitives[0]
    points=accessor(primitive['attributes']['POSITION']).astype(float)
    points=np.stack([points[:,0],-points[:,2],points[:,1]],axis=1)
    faces=accessor(primitive['indices']).ravel().reshape(-1,3)
    return points,faces
reports=[]
for label in ['left','right']:
    cp,cf=mesh(f'01 / {label} garter / pointed thigh reinforcement')
    wp,wf=mesh(f'01 / {label} garter / front suspension web')
    a,b,c=cp[cf[:,0]],cp[cf[:,1]],cp[cf[:,2]]
    ax,az=a[:,0],a[:,2];bx,bz=b[:,0],b[:,2];cx,cz=c[:,0],c[:,2]
    den=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz)
    valid=np.abs(den)>1e-14
    den=np.where(valid,den,1)
    samples=np.concatenate([wp,wp[wf].mean(axis=1)])
    rows=[]
    for sample_index,p in enumerate(samples):
        wa=((bz-cz)*(p[0]-cx)+(cx-bx)*(p[2]-cz))/den
        wb=((cz-az)*(p[0]-cx)+(ax-cx)*(p[2]-cz))/den
        wc=1-wa-wb
        hits=valid&(wa>=-1e-8)&(wb>=-1e-8)&(wc>=-1e-8)
        if not hits.any():continue
        y=float((wa*a[:,1]+wb*b[:,1]+wc*c[:,1])[hits].min())
        rows.append({'clearance':y-float(p[1]),'webPoint':p.tolist(),'cupFrontY':y,
                     'sampleKind':'vertex' if sample_index<len(wp) else 'triangle_centroid'})
    if not rows:raise ValueError('No projected actual contacts were found.')
    reports.append({'side':label,'sampledContacts':len(rows),
                    'minimumClearance':min(r['clearance'] for r in rows),
                    'vertexSamples':sum(r['sampleKind']=='vertex' for r in rows),
                    'triangleCentroidSamples':sum(r['sampleKind']=='triangle_centroid' for r in rows),
                    'worstSamples':sorted(rows,key=lambda r:r['clearance'])[:8]})
passed=all(r['minimumClearance']>=args.minimum_clearance for r in reports)
result={'modelSha256':record['modelSha256'],'measuredActualExportedGeometry':True,'contacts':reports,
    'minimumRequiredClearance':args.minimum_clearance,'sampledRestClearancePassed':passed,
    'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False}
(generation.parent/'exported_contact_diagnostic.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
if not passed:raise SystemExit('Actual exported rest separation failed.')
