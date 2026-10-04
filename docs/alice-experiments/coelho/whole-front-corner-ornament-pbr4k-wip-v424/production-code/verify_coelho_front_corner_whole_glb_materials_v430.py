from pathlib import Path
import struct,json,io,hashlib,numpy as np
from PIL import Image
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';a=json.loads((O/'package_export_v424.json').read_text(encoding='utf-8-sig'));src=json.loads((O/'whole_source_material_semantics_v429.json').read_text(encoding='utf-8-sig'));raw=(R/a['files']['glb']['path']).read_bytes();ln,ty=struct.unpack_from('<II',raw,12);doc=json.loads(raw[20:20+ln]);pos=20+ln;bn,bt=struct.unpack_from('<II',raw,pos);binary=raw[pos+8:pos+8+bn]
def image(tex):
 im=doc['images'][doc['textures'][tex['index']]['source']];v=doc['bufferViews'][im['bufferView']];blob=binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']];assert tex.get('texCoord',0)==0;return np.array(Image.open(io.BytesIO(blob)).convert('RGB')),hashlib.sha256(blob).hexdigest()
def source(row,socket):
 links=row['principledInputs'][socket]['links']
 if not links:return None
 assert len(links)==1
 l=links[0]
 if socket=='Normal':
  node=next(x for x in row['nodes'] if x['name']==l['node']);assert node['space']=='TANGENT' and node['strength']==1;assert len(node['links'])==1;l=node['links'][0]
 im=next(x for x in row['images'] if x['node']==l['node']);p=R/im['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==im['sha256'];arr=np.array(Image.open(p).convert('RGB'));assert arr.shape==(4096,4096,3);return arr,im
records=[]
for mat in doc['materials']:
 row=next(x for x in src['materials'] if x['name']==mat['name']);pbr=mat['pbrMetallicRoughness'];result={'name':mat['name'],'channels':{}};base,im=source(row,'Base Color');actual,sha=image(pbr['baseColorTexture']);assert np.array_equal(actual,base);assert pbr.get('baseColorFactor',[1,1,1,1])==[1,1,1,1];result['channels']['baseColor']={'allRGBPixelsExact':True,'textureSHA256':sha,'sourceSHA256':im['sha256']}
 for socket,key,channel in [('Roughness','roughnessFactor',1),('Metallic','metallicFactor',2)]:
  sc=source(row,socket)
  if sc:
   expected,im=sc;actual,sha=image(pbr['metallicRoughnessTexture']);assert np.array_equal(actual[:,:,channel],expected[:,:,0]),(mat['name'],socket);assert pbr.get(key,1)==1;result['channels'][socket]={'allChannelPixelsExact':True,'channel':channel,'sourceSHA256':im['sha256']}
  else:assert abs(pbr.get(key,1)-row['principledInputs'][socket]['default'])<1e-6;result['channels'][socket]={'constantPreserved':True,'value':pbr.get(key,1)}
 sc=source(row,'Normal')
 if sc:
  expected,im=sc;actual,sha=image(mat['normalTexture']);assert np.array_equal(actual,expected);assert mat['normalTexture'].get('scale',1)==1;result['channels']['Normal']={'allRGBPixelsExact':True,'tangentSpaceAndStrengthPreserved':True,'sourceSHA256':im['sha256']}
 assert mat.get('alphaMode','OPAQUE')=='OPAQUE';spec=row['principledInputs']['Specular IOR Level'];assert not spec['links'];value=mat.get('extensions',{}).get('KHR_materials_specular',{}).get('specularFactor',1);assert abs(value-spec['default']*2)<1e-6,(mat['name'],value,spec)
 result['alphaAndSpecularSemanticsPreserved']=True;records.append(result);print('MATERIAL_VERIFIED',mat['name'],flush=True)
report=dict(version='v430',format='GLB',sha256=a['files']['glb']['sha256'],allExportedMaterialsVerified=True,allSourceLinkedImages4096=True,fullPixelComparisons=True,materials=records,unusedMaterialSlotsNotRequiredInGLB=True,productionComplete=False);(O/'whole_glb_material_pixel_audit_v430.json').write_text(json.dumps(report,indent=2))
