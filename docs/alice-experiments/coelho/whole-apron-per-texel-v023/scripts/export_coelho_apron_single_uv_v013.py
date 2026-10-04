import bpy,json,hashlib,numpy as np
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
X=R/'Assets/Characters/alice_coelho/Exports/apron_single_uv_checkpoint_v013';X.mkdir(parents=True,exist_ok=True)
ob=bpy.data.objects['Alice.Coelho.Complete.GameCandidate'];high=bpy.data.objects['Alice.Coelho.Complete.High.SourcePreserved'];s=bpy.context.scene
audit=json.loads((O/'apron_single_uv_audit_v012.json').read_text())
assert audit['geometryExactlyPreserved'] and audit['nonApronUVExactlyPreserved'] and audit['UVLayers']==1
assert len(ob.data.uv_layers)==1 and len(ob.data.materials)==2
ob.data.calc_loop_triangles();assert len(ob.data.loop_triangles)==150000
old=np.load(O/'projection_geometry_v006.npz');print('SOURCE_ARRAY_KEYS',old.files,flush=True)
P=np.array([v.co[:] for v in ob.data.vertices],np.float32)
positionHash=hashlib.sha256(P.tobytes()).hexdigest();assert positionHash=='75636cc438501d8d08910894b2f3479afea5ddd3c482299840d5bf1f054ab486'
for im in bpy.data.images:
 if im.type=='IMAGE' and im.size[0]:assert im.packed_file is not None,im.name
assert not bpy.data.libraries
s['alice_stage']='coelho_apron_single_uv_4k_checkpoint_v013_not_final';s['rigged']=False
text=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_V013');text.write('Checkpoint LOCAL do personagem inteiro. UV principal do avental atualizado em 2270 faces, dois conjuntos de mapas 4K por material e um canal UV compatível com FBX. Geometria inteira preservada. Foto original 222x455 reamostrada: não cria detalhe novo. Bake normal na nova base tangente; malha Tripo ainda não é retopologia para animação. Não aprova base canônica, altura anatômica, fidelidade integral, rig, camadas, cabelo, física ou gameplay. Não iniciar outra parte antes do checkpoint inteiro publicado; reserva global do Dot Cheshire continua vigente.\n')
bpy.ops.object.select_all(action='DESELECT');high.hide_render=True;high.hide_set(True);ob.hide_render=False;ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob
stem='alice_coelho_complete_apron_single_uv_checkpoint_v013'
blend=O/(stem+'.blend');assert not blend.exists();bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
glb=X/(stem+'.glb');fbx=X/(stem+'.fbx');assert not glb.exists() and not fbx.exists()
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_texcoords=True,export_normals=True,export_yup=True,export_image_format='AUTO')
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},use_mesh_modifiers=True,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS')
report=dict(assetId='alice_coelho',stage='local_apron_single_uv_checkpoint_not_final',wholeCharacterWithDress=True,additionalTripoCredits=0,creditsConsumed=55,geometryPositionSha256=positionHash,geometryExactlyPreserved=True,UVLayers=1,materialAtlases=2,apronFaces=2270,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,publicationPerformed=False,productionComplete=False,files={})
for key,p in [('blend',blend),('glb',glb),('fbx',fbx)]:report['files'][key]=dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(O/'package_export_v013.json').write_text(json.dumps(report,indent=2));print('WHOLE_COELHO_V013_EXPORTED',json.dumps(report),flush=True)
