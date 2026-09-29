"""Match the complete Alice GLB hair material to a reviewed checkpoint."""
import argparse
import copy
import json
import struct
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True)
parser.add_argument('--reference', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()


def read_glb(path):
    raw = Path(path).read_bytes()
    magic, version, total = struct.unpack_from('<III', raw)
    assert magic == 0x46546C67 and version == 2 and total == len(raw)
    chunks = []
    offset = 12
    while offset < total:
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        chunks.append((kind, raw[offset:offset + size]))
        offset += size
    assert offset == total and chunks[0][0] == 0x4E4F534A
    return json.loads(chunks[0][1]), chunks


source, chunks = read_glb(args.source)
reference, _ = read_glb(args.reference)
name = 'Alice / individual dark hair ribbons / checkpoint'
source_hair = next(m for m in source['materials'] if m.get('name') == name)
reference_hair = next(m for m in reference['materials'] if m.get('name') == name)
source_hair['pbrMetallicRoughness']['roughnessFactor'] = reference_hair['pbrMetallicRoughness']['roughnessFactor']
reference_specular = reference_hair.get('extensions', {}).get('KHR_materials_specular')
assert reference_specular and reference_specular['specularFactor'] == .24
source_hair.setdefault('extensions', {})['KHR_materials_specular'] = copy.deepcopy(reference_specular)
used = source.setdefault('extensionsUsed', [])
if 'KHR_materials_specular' not in used:
    used.append('KHR_materials_specular')

json_bytes = json.dumps(source, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
json_bytes += b' ' * ((-len(json_bytes)) % 4)
chunks[0] = (0x4E4F534A, json_bytes)
total = 12 + sum(8 + len(data) for _, data in chunks)
output = Path(args.output)
assert not output.exists()
with output.open('wb') as stream:
    stream.write(struct.pack('<III', 0x46546C67, 2, total))
    for kind, data in chunks:
        assert len(data) % 4 == 0
        stream.write(struct.pack('<II', len(data), kind))
        stream.write(data)
print(json.dumps(dict(output=str(output), bytes=total,
                      roughness=source_hair['pbrMetallicRoughness']['roughnessFactor'],
                      specular=reference_specular['specularFactor'])))
