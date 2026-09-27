"""Measure actual exported round lace yarn triangles and their primary UVs."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--model')
parser.add_argument('--output')
args=parser.parse_args()
generation=Path(args.generation);record=json.loads(generation.read_text(encoding='utf-8'))
if not record.get('garterLaceThreadRefinement'):raise ValueError('Require actual rounded-yarn construction.')
path=Path(args.model or record['model']);data=path.read_bytes()
digest=hashlib.sha256(data).hexdigest()
if not args.model and digest!=record['modelSha256']:raise ValueError('Changed actual generated model.')
if data[:4]!=b'glTF' or struct.unpack_from('<I',data,4)[0]!=2:raise ValueError('Require a real GLB 2 file.')
size=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+size]);binary=data[28+size:]
def accessor(index):
    a=doc['accessors'][index];view=doc['bufferViews'][a['bufferView']]
    dtype={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]
    cols={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];width=np.dtype(dtype).itemsize
    return np.ndarray((a['count'],cols),dtype=dtype,buffer=binary,
        offset=view.get('byteOffset',0)+a.get('byteOffset',0),strides=(view.get('byteStride',cols*width),width))
name=record['garterLaceThreadRefinement']['mesh']
nodes=[n for n in doc['nodes'] if n.get('name')==name and 'mesh' in n]
if len(nodes)!=1:raise ValueError('Wrong actual yarn mesh node.')
rows=[]
for primitive in doc['meshes'][nodes[0]['mesh']]['primitives']:
    if primitive.get('mode',4)!=4:raise ValueError('Require actual yarn triangles.')
    attrs=primitive['attributes'];xyz=accessor(attrs['POSITION']).astype(float)
    uv=accessor(attrs['TEXCOORD_0']).astype(float)
    normals=accessor(attrs['NORMAL']).astype(float)
    indices=accessor(primitive['indices']).ravel().reshape(-1,3)
    a,b,c=(xyz[indices[:,i]] for i in range(3));areas=np.linalg.norm(np.cross(b-a,c-a),axis=1)*.5
    ua,ub,uc=(uv[indices[:,i]] for i in range(3));ab,ac=ub-ua,uc-ua
    uv_fraction=float(np.mean(np.abs(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])*.5>1e-12))
    finite=all(np.isfinite(a).all() for a in [xyz,uv,normals,areas])
    minimum=float(areas.min());normal_min=float(np.linalg.norm(normals,axis=1).min())
    passed=finite and uv_fraction>=.95 and minimum>1e-14 and normal_min>.99
    rows.append({'actualTriangles':len(indices),'actualVertices':len(xyz),'allValuesFinite':finite,
        'uvNonDegenerateTriangleFraction':uv_fraction,'minimumTriangleArea':minimum,
        'minimumNormalLength':normal_min,'passed':passed})
result={'model':str(path.resolve()),'modelSha256':digest,'modelBytes':len(data),'mesh':name,
    'measuredActualExportedMesh':True,'primaryUvMeasured':True,'primitives':rows,
    'passed':bool(rows) and all(r['passed'] for r in rows),'actualSkins':len(doc.get('skins',[])),
    'actualAnimationClips':len(doc.get('animations',[])),
    'fidelityVerified':False,'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False}
output=Path(args.output) if args.output else generation.parent/'exported_lace_threads_audit.json'
if output.exists():raise ValueError('Preserve the previous actual export inspection.')
output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if not result['passed']:raise SystemExit('Actual exported yarn geometry/UV inspection failed.')
