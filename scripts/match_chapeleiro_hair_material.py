"""Restore the reviewed matte hair material in a whole-character GLB."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--input', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
src, dst = Path(a.input), Path(a.output)
assert src.is_file() and not dst.exists()
blob = src.read_bytes()
magic, version, size = struct.unpack_from('<4sII', blob)
assert magic == b'glTF' and version == 2 and size == len(blob)
json_size, kind = struct.unpack_from('<II', blob, 12)
assert kind == 0x4E4F534A
document = json.loads(blob[20:20 + json_size])
material = next(m for m in document['materials'] if m['name'] == 'Alice / individual dark hair ribbons / checkpoint')
assert abs(material['pbrMetallicRoughness']['roughnessFactor'] - .42) < .001
material['pbrMetallicRoughness']['roughnessFactor'] = .68
material.setdefault('extensions', {})['KHR_materials_specular'] = {'specularFactor': .24}
used = document.setdefault('extensionsUsed', [])
if 'KHR_materials_specular' not in used:
    used.append('KHR_materials_specular')
json_bytes = json.dumps(document, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
json_bytes += b' ' * ((-len(json_bytes)) % 4)
binary_chunk = blob[20 + json_size:]
result = (struct.pack('<4sII', b'glTF', 2, 20 + len(json_bytes) + len(binary_chunk)) +
          struct.pack('<II', len(json_bytes), 0x4E4F534A) + json_bytes + binary_chunk)
assert len(result) == struct.unpack_from('<I', result, 8)[0]
dst.write_bytes(result)
report = dict(source=str(src), output=str(dst), sourceSha256=hashlib.sha256(blob).hexdigest(),
              modelSha256=hashlib.sha256(result).hexdigest(), modelBytes=len(result),
              hairRoughness=.68, specularFactor=.24, binaryChunkUnchanged=True)
dst.with_suffix('.material.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
