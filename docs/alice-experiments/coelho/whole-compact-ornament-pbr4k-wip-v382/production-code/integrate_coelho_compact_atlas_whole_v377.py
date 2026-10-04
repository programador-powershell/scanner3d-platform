"""Recoverable WHOLE dressed WIP integration; does not finalize the asset."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def signatures(names):
    result={}
    for name in names:
        ob=bpy.data.objects[name];m=ob.data;result[name]=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([x.uv[:] for x in u.data],np.float32).tobytes()).hexdigest() for u in m.uv_layers],keys={} if not m.shape_keys else {k.name:hashlib.sha256(np.asarray([v.co[:] for v in k.data],np.float32).tobytes()).hexdigest() for k in m.shape_keys.key_blocks},materials=[mat.name for mat in m.materials],matrixWorld=[list(row) for row in ob.matrix_world])
    return result
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a';review=read(O/'apron_ornament_atlas_review_decision_v376.json');assert review['acceptedForWholeStaticWIPIntegrationReview'] and review['allImagesActuallyInspected'];a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v370.json');source=R/a['path'];assert sha(source)==a['sha256'];prior=read(O/'apron_ornament_whole_integration_audit_v318.json');priorNames=list(prior['wholeCopySignatures']);assert signatures(priorNames)==prior['wholeCopySignatures'];oldNames=[x['name'] for x in prior['objects'] if x['role'] in {'character','apron','chain','cord','lace'}];assert len(oldNames)==5
names=oldNames+[r['object'] for r in a['newObjects']];roles=['character','apron','chain','cord','lace']+['ornament_'+r['id'] for r in a['newObjects']];before=signatures(names);col=bpy.data.collections.new('COELHO_WHOLE_CHECKPOINT_V377_WIP');bpy.context.scene.collection.children.link(col);objects=[]
for name,role in zip(names,roles):
    src=bpy.data.objects[name];ob=src.copy();ob.data=src.data.copy();ob.name='Alice.Coelho.WholeCheckpoint377.'+role;col.objects.link(ob);ob['alice_role']=role;ob['rigged']=False;ob['physicsVerified']=False;objects.append(ob)
for ob in bpy.context.scene.objects:
    if ob.type in {'MESH','CURVE'}:ob.hide_render=True;ob.hide_set(True)
for ob in objects:ob.hide_render=False;ob.hide_set(False)
assert signatures(names)==before
for name,ob in zip(names,objects):assert signatures([ob.name])[ob.name]==before[name]
assert not bpy.data.libraries
for im in bpy.data.images:
    if im.type=='IMAGE' and im.size[0]:assert im.packed_file,im.name
scene=bpy.context.scene;scene['alice_stage']='coelho_complete_ornament_mounts_own_pbr4k_v377_WIP';scene['productionComplete']=False;scene['rigged']=False;scene['canonicalIdentityApproved']=False;scene['anatomicalHeightVerified']=False
text=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_INTEIRA_V377_WIP');text.write('Alice INTEIRA com vestido, checkpoint estÃ¡tico em produÃ§Ã£o. Integra cinco pendentes370: armaÃ§Ãµes unificadas,5 bails,4 capas ocas,249 elos interligados,192 fios de tassels; geometria estÃ¡tica verificada, UV sem sobreposiÃ§Ã£o nos testes e quatro mapas4K incorporados/reimportados GLB/FBX localmente. Azul metÃ¡lico opaco Ã© aproximaÃ§Ã£o artÃ­stica; nÃ£o alegar Ã³ptica real de safira, novo detalhe fotogrÃ¡fico ou normal highpoly. Todo corpo/vestido318, raÃ­zes, fonte Tripo e candidatas anteriores preservados. Relevos compactos de canto revisados; filigranas/fidelidade, base comum/168cm/rosto/corpo/rig, camadas/LOD, cabelo individual, tecido/fÃ­sica/vento/colisÃµes, movimentos/expressÃµes/gameplay continuam pendentes. NÃƒO usar diagnÃ³stico de pendentes como Alice para galeria. Exportar/reimportar e publicar somente personagem completo; checkpoint nÃ£o conclui asset nem autoriza prÃ³ximo Tripo.\n')
out=O/'alice_coelho_complete_ornament_pbr4k_working_v377.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256'];report=dict(version='v377',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),source=source.relative_to(R).as_posix(),sourceSHA256=a['sha256'],wholeCharacterWithDress=True,collection=col.name,objects=[dict(role=role,name=ob.name,source=name) for role,name,ob in zip(roles,names,objects)],sourceSignatures=before,wholeCopySignatures=signatures([ob.name for ob in objects]),allFivePreviousWhole318BaseMeshesExactlyPreserved=True,allLocalOrnament370MeshesExactlyPreserved=True,oldSourcesRecoverableHidden=True,portablePackedImages=True,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,physicsVerified=False,productionComplete=False,notPublished=True,wholeVisualAndFormatReviewPending=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start);(O/'apron_ornament_whole_integration_audit_v377.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENTS318_INTEGRATED_WHOLE_STATIC_WIP_AWAIT_REOPEN',flush=True)
