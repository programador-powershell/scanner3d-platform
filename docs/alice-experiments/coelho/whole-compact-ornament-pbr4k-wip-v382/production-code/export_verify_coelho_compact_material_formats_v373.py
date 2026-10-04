"""LOCAL diagnostic exports only; never publish ornaments as separate asset."""
import bpy,json,hashlib,time,sys,struct
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'Diagnostics/ornament_material_v373';D.mkdir(parents=True,exist_ok=True);start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v370.json');source=R/a['path'];assert sha(source)==a['sha256'];assert read(O/'apron_ornament_pbr_atlas_reopen_audit_v371.json')['sourceSHA256']==a['sha256'];uvAudit=read(O/'apron_ornament_continuous_uv_audit_v372.json');assert uvAudit['sourceSHA256']==a['sha256'] and uvAudit['continuousUVOverlapPairs']==0
bpy.ops.object.select_all(action='DESELECT');objects=[]
for row in a['newObjects']:
    ob=bpy.data.objects[row['object']];ob.hide_set(False);ob.hide_render=False;ob.select_set(True);objects.append(ob)
bpy.context.view_layer.objects.active=objects[0];glb=D/'DIAGNOSTIC_LOCAL_ONLY_ornament_material_v373.glb';fbx=D/'DIAGNOSTIC_LOCAL_ONLY_ornament_material_v373.fbx';assert not glb.exists() and not fbx.exists()
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_image_format='AUTO',export_draco_mesh_compression_enable=False,export_animations=False,export_extras=True)
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,global_scale=1,axis_forward='-Z',axis_up='Y',bake_space_transform=False,use_mesh_modifiers=True,add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,use_custom_props=True)
payload=glb.read_bytes();assert payload[:4]==b'glTF';N,kind=struct.unpack_from('<II',payload,12);assert kind==0x4e4f534a;j=json.loads(payload[20:20+N]);off=20+N;BN,BK=struct.unpack_from('<II',payload,off);assert BK==0x004e4942;binary=payload[off+8:off+8+BN];images=[]
for i,im in enumerate(j['images']):
    v=j['bufferViews'][im['bufferView']];blob=binary[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']];p=D/('glb_image_'+str(i)+'.png');p.write_bytes(blob);images.append(dict(index=i,path=p.relative_to(R).as_posix(),sha256=sha(p),bytes=len(blob),name=im.get('name')))
materials=[]
for mat in j['materials']:
    pbr=mat['pbrMetallicRoughness'];assert 'baseColorTexture' in pbr and 'metallicRoughnessTexture' in pbr and 'normalTexture' in mat;bindings={}
    for role,tex in [('basecolor',pbr['baseColorTexture']),('metallicRoughness',pbr['metallicRoughnessTexture']),('normal',mat['normalTexture'])]:
        idx=j['textures'][tex['index']]['source'];bindings[role]=images[idx];assert tex.get('texCoord',0)==0
        if role in ['basecolor','normal']:assert images[idx]['sha256']==a['maps'][role]['sha256']
    materials.append(dict(name=mat['name'],bindings=bindings,metallicFactor=pbr.get('metallicFactor',1),roughnessFactor=pbr.get('roughnessFactor',1)))
sys.path.insert(0,'F:/Programas/5.2/scripts/addons_core');from io_scene_fbx import parse_fbx
root,_=parse_fbx.parse(str(fbx));obs=next(e for e in root.elems if e.id==b'Objects');con=next(e for e in root.elems if e.id==b'Connections');byid={e.props[0]:e for e in obs.elems};videos={};connections=[]
for e in obs.elems:
    if e.id==b'Video':
        blob=next(x for x in e.elems if x.id==b'Content').props[0];digest=hashlib.sha256(blob).hexdigest();roles=[role for role,v in a['maps'].items() if v['sha256']==digest];assert roles,(e.props[:3],digest);videos[e.props[0]]=dict(sha256=digest,roles=roles,bytes=len(blob))
for e in con.elems:
    p=e.props
    if p[0]==b'OP' and byid.get(p[1]) is not None and byid[p[1]].id==b'Texture':
        video=next(x.props[1] for x in con.elems if x.props[0]==b'OO' and x.props[2]==p[1] and byid.get(x.props[1]) is not None and byid[x.props[1]].id==b'Video');connections.append(dict(material=byid[p[2]].props[1].split(b'\x00')[0].decode(),property=p[3].decode(),**videos[video]))
for name in {x['material'] for x in connections}:
    got={x['property']:x['roles'] for x in connections if x['material']==name};assert 'basecolor' in got.get('DiffuseColor',[]) and 'roughness' in got.get('ShininessExponent',[]) and 'metallic' in got.get('ReflectionFactor',[]) and 'normal' in got.get('NormalMap',[]),got
assert sha(source)==a['sha256'];report=dict(version='v373',sourceCandidate='v370',sourceSHA256=a['sha256'],diagnosticLocalOnlyNotWholeCharacterExport=True,files={k:dict(path=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for k,p in [('glb',glb),('fbx',fbx)]},GLBImages=images,GLBMaterialBindings=materials,FBXEmbeddedVideos=list(videos.values()),FBXMaterialBindings=connections,basecolorAndNormalGLBImageBytesExact=True,FBXAllEmbeddedImagesExact=True,GLBMetalRoughPackedChannelValidationPending=True,requiresActualFormatReimportAndAppearanceReview=True,notPublished=True,productionComplete=False,elapsedSeconds=time.time()-start);(O/'apron_ornament_material_format_payload_v373.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENT_FORMAT373_PAYLOAD_VERIFIED_AWAIT_CHANNEL_REIMPORT',flush=True)
