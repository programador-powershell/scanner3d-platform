"""Compare exact GLB hair, skin and animation payloads after source-mask cleanup."""
import argparse, hashlib, json, struct
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert not a.output.exists()
def load(path):
    raw=path.read_bytes();magic,version,total=struct.unpack_from('<4sII',raw)
    assert magic==b'glTF' and version==2 and total==len(raw)
    length,kind=struct.unpack_from('<II',raw,12);assert kind==0x4e4f534a
    doc=json.loads(raw[20:20+length]);start=20+length
    size,kind=struct.unpack_from('<II',raw,start);assert kind==0x004e4942
    return doc,raw[start+8:start+8+size]
def view(doc,blob,index):
    v=doc['bufferViews'][index];start=v.get('byteOffset',0)
    return blob[start:start+v['byteLength']]
def digest(data):return hashlib.sha256(data).hexdigest()
def accessor(doc,blob,index):
    x=doc['accessors'][index];assert 'sparse' not in x
    sizes={5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}
    widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
    width=sizes[x['componentType']]*widths[x['type']]
    v=doc['bufferViews'][x['bufferView']];data=view(doc,blob,x['bufferView'])
    stride=v.get('byteStride',width);start=x.get('byteOffset',0)
    payload=b''.join(data[start+i*stride:start+i*stride+width] for i in range(x['count']))
    return dict(count=x['count'],type=x['type'],componentType=x['componentType'],sha256=digest(payload))
def extract(doc,blob):
    hair={}
    for node in doc['nodes']:
        if not node.get('extras',{}).get('hairFiberCount'):continue
        primitives=doc['meshes'][node['mesh']]['primitives']
        hair[node['name']]=[dict(dracoSha256=digest(view(doc,blob,p['extensions']['KHR_draco_mesh_compression']['bufferView'])),
            attributes=p['extensions']['KHR_draco_mesh_compression']['attributes'],
            fiberCount=node['extras']['hairFiberCount']) for p in primitives]
    skins=[dict(joints=[doc['nodes'][i]['name'] for i in skin['joints']],
        inverseBindMatrices=accessor(doc,blob,skin['inverseBindMatrices'])) for skin in doc['skins']]
    joint_nodes={doc['nodes'][i]['name']:{k:v for k,v in doc['nodes'][i].items() if k in ('translation','rotation','scale','matrix')}
        for skin in doc['skins'] for i in skin['joints']}
    animations={}
    for animation in doc['animations']:
        channels=[]
        for channel in animation['channels']:
            sampler=animation['samplers'][channel['sampler']]
            channels.append(dict(node=doc['nodes'][channel['target']['node']]['name'],path=channel['target']['path'],
                interpolation=sampler.get('interpolation','LINEAR'),
                input=accessor(doc,blob,sampler['input']),output=accessor(doc,blob,sampler['output'])))
        animations[animation['name']]=channels
    return dict(hair=hair,skins=skins,jointNodes=joint_nodes,animations=animations)
before=extract(*load(a.baseline));after=extract(*load(a.candidate))
report=dict(baseline=str(a.baseline),candidate=str(a.candidate),
    hairChunkCount=len(after['hair']),animationCount=len(after['animations']),
    exactPayloadMatches={key:before[key]==after[key] for key in before},
    changedHairChunks=[key for key in before['hair'] if before['hair'][key]!=after['hair'].get(key)],
    scope='Byte-exact compressed hair and sampled animation/skin payload comparisons; does not verify source face semantics, reference fidelity or runtime physics.')
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert all(report['exactPayloadMatches'].values()),'Unexpected change beyond reviewed source-face mask'
