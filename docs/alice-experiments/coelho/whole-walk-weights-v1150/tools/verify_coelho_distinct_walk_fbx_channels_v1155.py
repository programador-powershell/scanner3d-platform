"""Check whole1048 FBX channels against actual native1041 material capture1046."""
import json,hashlib
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
source=read(O/'whole_source_material_semantics_v1046.json'); fb=read(O/'whole_fbx_embedded_material_audit_v1154.json');pkg=read(O/'package_skin_export_v1150.json');assert fb['sha256']==pkg['files']['fbx']['sha256']
records=[];used=set(c['material'] for c in fb['channelConnections'])
for mat in source['materials']:
 if mat['name'] not in used:continue
 for socket,prop in [('Base Color','DiffuseColor'),('Roughness','ShininessExponent'),('Metallic','ReflectionFactor'),('Normal','NormalMap')]:
  links=mat['principledInputs'][socket]['links']
  if not links:continue
  assert len(links)==1;link=links[0]
  if socket=='Normal':
   n=next(n for n in mat['nodes'] if n['name']==link['node']);assert n['space']=='TANGENT' and n['strength']>=0 and len(n['links'])==1;assert abs(fb['materialProperties'][mat['name']].get('BumpFactor',[1.])[0]-n['strength'])<1e-7;link=n['links'][0]
  im=next(im for im in mat['images'] if im['node']==link['node']);assert hashlib.sha256((R/im['path']).read_bytes()).hexdigest()==im['sha256']
  bindings=[c for c in fb['channelConnections'] if c['material']==mat['name'] and c['property']==prop];assert len(bindings)==1 and bindings[0]['imageSHA256']==im['sha256'],(mat['name'],socket,bindings)
  record=dict(material=mat['name'],socket=socket,property=prop,sourceImageSHA256=im['sha256'],exactConnection=True)
  if socket=='Normal':record.update(sourceStrength=n['strength'],rawFBXBumpFactor=fb['materialProperties'][mat['name']].get('BumpFactor',[1.])[0],strengthTolerance=1e-7)
  records.append(record)
assert len(records)==len(fb['channelConnections'])
constants=[]
for mat in source['materials']:
 if mat['name'] not in fb['materialProperties'] or mat['images']:continue
 inp=mat['principledInputs'];props=fb['materialProperties'][mat['name']];color=inp['Base Color']['default'][:3]
 expected={'DiffuseColor':color,'SpecularColor':color,'ReflectionColor':color,'ReflectionFactor':[inp['Metallic']['default']], 'SpecularFactor':[inp['Specular IOR Level']['default']/2], 'Shininess':[((1-inp['Roughness']['default'])*10)**2], 'ShininessExponent':[((1-inp['Roughness']['default'])*10)**2]}
 for name,value in expected.items():assert name in props and len(props[name])==len(value) and max(abs(a-b) for a,b in zip(props[name],value))<1e-7,(mat['name'],name,props.get(name),value)
 # Alpha=1 is represented by omitted default Opacity=1, TransparencyFactor=0.
 assert inp['Alpha']['default']==1 and props.get('Opacity',[1])==[1] and props.get('TransparencyFactor',[0])==[0]
 constants.append(dict(material=mat['name'],rawFBXColorMetallicRoughnessShininessSpecularAndOpaqueAlphaVerified=True,expectedProperties=expected))
assert len(constants)==2
report=dict(version='v1155',sha256=pkg['files']['fbx']['sha256'],allSourceTextureChannelBindingsPreserved=True,allEmbeddedImagesVerifiedV1013=True,records=records,constantClockMaterials=constants,officialExporterFormulaPath='F:/Programas/5.2/scripts/addons_core/io_scene_fbx/export_fbx_bin.py',officialExporterFormulaSHA256=hashlib.sha256(Path('F:/Programas/5.2/scripts/addons_core/io_scene_fbx/export_fbx_bin.py').read_bytes()).hexdigest(),productionComplete=False)
(O/'whole_fbx_channel_semantics_audit_v1155.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FBX_SOURCE_CHANNEL_BINDINGS_VERIFIED',len(records))
