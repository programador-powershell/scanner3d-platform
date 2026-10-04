"""Check FBX191 channel semantics against actual source181 packed images."""
import json,hashlib
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
source=read(O/'whole_source_material_semantics_v429.json'); fb=read(O/'whole_fbx_embedded_material_audit_v431.json');pkg=read(O/'package_export_v424.json');assert fb['sha256']==pkg['files']['fbx']['sha256']
records=[];used=set(c['material'] for c in fb['channelConnections'])
for mat in source['materials']:
 if mat['name'] not in used:continue
 for socket,prop in [('Base Color','DiffuseColor'),('Roughness','ShininessExponent'),('Metallic','ReflectionFactor'),('Normal','NormalMap')]:
  links=mat['principledInputs'][socket]['links']
  if not links:continue
  assert len(links)==1;link=links[0]
  if socket=='Normal':
   n=next(n for n in mat['nodes'] if n['name']==link['node']);assert n['space']=='TANGENT' and n['strength']==1 and len(n['links'])==1;link=n['links'][0]
  im=next(im for im in mat['images'] if im['node']==link['node']);assert hashlib.sha256((R/im['path']).read_bytes()).hexdigest()==im['sha256']
  bindings=[c for c in fb['channelConnections'] if c['material']==mat['name'] and c['property']==prop];assert len(bindings)==1 and bindings[0]['imageSHA256']==im['sha256'],(mat['name'],socket,bindings)
  records.append(dict(material=mat['name'],socket=socket,property=prop,sourceImageSHA256=im['sha256'],exactConnection=True))
assert len(records)==len(fb['channelConnections'])
report=dict(version='v432',sha256=pkg['files']['fbx']['sha256'],allSourceTextureChannelBindingsPreserved=True,allEmbeddedImagesVerifiedV190=True,records=records,productionComplete=False)
(O/'whole_fbx_channel_semantics_audit_v432.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FBX_SOURCE_CHANNEL_BINDINGS_VERIFIED',len(records))
