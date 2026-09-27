import hashlib,json,struct
from pathlib import Path
import numpy as np
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro');root=base/'foundation_shared_rig_v094'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def glb(path):
 raw=Path(path).read_bytes();n=struct.unpack_from('<I',raw,12)[0];d=json.loads(raw[20:20+n]);return d,raw[28+n:]

def accessor(d,b,i):
 a=d['accessors'][i];v=d['bufferViews'][a['bufferView']];types={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'};components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
 dtype=np.dtype(types[a['componentType']]);width=components[a['type']];offset=v.get('byteOffset',0)+a.get('byteOffset',0);stride=v.get('byteStride',width*dtype.itemsize)
 return np.ndarray((a['count'],width),dtype=dtype,buffer=b,offset=offset,strides=(stride,dtype.itemsize)).copy()

old=read(base/'foundation_shared_rig_v093/generation.json');new=read(root/'generation.json')
d,b=glb(old['exports']['foundation']['model']);e,c=glb(new['exports']['foundation']['model'])
nodes=lambda x:{n['name']:n for n in x['nodes'] if 'mesh' in n and 'skin' in n}
assert set(nodes(d))==set(nodes(e));checked=0
for name,n in nodes(d).items():
 a=d['meshes'][n['mesh']]['primitives'];z=e['meshes'][nodes(e)[name]['mesh']]['primitives'];assert len(a)==len(z)
 for x,y in zip(a,z):
  assert set(x['attributes'])==set(y['attributes'])
  for field in x['attributes']:
   assert np.array_equal(accessor(d,b,x['attributes'][field]),accessor(e,c,y['attributes'][field])),(name,field)
   checked+=1
  assert np.array_equal(accessor(d,b,x['indices']),accessor(e,c,y['indices']))
  assert x.get('material')==y.get('material')
assert d['materials']==e['materials'] and d['textures']==e['textures']
for x,y in zip(d['images'],e['images']):
 vx,vy=d['bufferViews'][x['bufferView']],e['bufferViews'][y['bufferView']]
 assert b[vx['byteOffset']:vx['byteOffset']+vx['byteLength']]==c[vy['byteOffset']:vy['byteOffset']+vy['byteLength']]
assert np.array_equal(accessor(d,b,d['skins'][0]['inverseBindMatrices']),accessor(e,c,e['skins'][0]['inverseBindMatrices']))
assert [d['nodes'][i]['name'] for i in d['skins'][0]['joints']]==[e['nodes'][i]['name'] for i in e['skins'][0]['joints']]
animation_errors=[]
for a in d['animations']:
 z=next(x for x in e['animations'] if x['name']==a['name'])
 channels=lambda x,doc:{(doc['nodes'][ch['target']['node']]['name'],ch['target']['path']):x['samplers'][ch['sampler']] for ch in x['channels']}
 ca,cz=channels(a,d),channels(z,e);assert set(ca)==set(cz);error=0.
 for key in ca:
  for field in ['input','output']:
   p,q=accessor(d,b,ca[key][field]),accessor(e,c,cz[key][field]);assert p.shape==q.shape
   error=max(error,float(np.abs(p-q).max()));assert error<1e-6,(a['name'],key,error)
 animation_errors.append({'clip':a['name'],'maximumChannelDifference':error})
report={'oldModelSha256':old['exports']['foundation']['modelSha256'],'newModelSha256':new['exports']['foundation']['modelSha256'],
 'actualMeshNodes':len(nodes(e)),'actualAttributeArraysCompared':checked,'geometryUvNormalsSkinWeightsIndicesMaterialsImagesBindJointsIdentical':True,
 'fourOriginalAnimationsCompared':animation_errors,'additionalActualAnimation':e['animations'][-1]['name'],
 'scriptSha256':sha(__file__),'fidelityVerified':False,'clothCollisionVerified':False,'motionVerified':False}
(root/'actual_glb_field_identity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
