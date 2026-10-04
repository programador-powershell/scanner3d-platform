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
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a';review=read(O/'apron_ornament_atlas_review_decision_v316.json');assert review['acceptedForWholeStaticWIPIntegrationReview'] and review['allImagesActuallyInspected'];a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v301.json');source=R/a['path'];assert sha(source)==a['sha256'];prior=read(O/'apron_whole_integration_audit_v181.json');oldNames=list(prior['wholeCopySignatures']);assert signatures(oldNames)==prior['wholeCopySignatures']
names=oldNames+[r['object'] for r in a['newObjects']];roles=['character','apron','chain','cord','lace']+['ornament_'+r['id'] for r in a['newObjects']];before=signatures(names);col=bpy.data.collections.new('COELHO_WHOLE_CHECKPOINT_V318_WIP');bpy.context.scene.collection.children.link(col);objects=[]
for name,role in zip(names,roles):
    src=bpy.data.objects[name];ob=src.copy();ob.data=src.data.copy();ob.name='Alice.Coelho.WholeCheckpoint318.'+role;col.objects.link(ob);ob['alice_role']=role;ob['rigged']=False;ob['physicsVerified']=False;objects.append(ob)
for ob in bpy.context.scene.objects:
    if ob.type in {'MESH','CURVE'}:ob.hide_render=True;ob.hide_set(True)
for ob in objects:ob.hide_render=False;ob.hide_set(False)
assert signatures(names)==before
for name,ob in zip(names,objects):assert signatures([ob.name])[ob.name]==before[name]
assert not bpy.data.libraries
for im in bpy.data.images:
    if im.type=='IMAGE' and im.size[0]:assert im.packed_file,im.name
scene=bpy.context.scene;scene['alice_stage']='coelho_complete_ornament_mounts_own_pbr4k_v318_WIP';scene['productionComplete']=False;scene['rigged']=False;scene['canonicalIdentityApproved']=False;scene['anatomicalHeightVerified']=False
text=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_INTEIRA_V318_WIP');text.write('Alice INTEIRA com vestido, checkpoint estático em produção. Integra cinco pendentes301: armações unificadas,5 bails,4 capas ocas,249 elos interligados,192 fios de tassels; geometria estática verificada, UV sem sobreposição nos testes e quatro mapas4K incorporados/reimportados GLB/FBX localmente. Azul metálico opaco é aproximação artística; não alegar óptica real de safira, novo detalhe fotográfico ou normal highpoly. Todo corpo/vestido181, raízes, fonte Tripo e candidatas anteriores preservados. Filigranas/fidelidade, base comum/168cm/rosto/corpo/rig, camadas/LOD, cabelo individual, tecido/física/vento/colisões, movimentos/expressões/gameplay continuam pendentes. NÃO usar diagnóstico de pendentes como Alice para galeria. Exportar/reimportar e publicar somente personagem completo; checkpoint não conclui asset nem autoriza próximo Tripo.\n')
out=O/'alice_coelho_complete_ornament_pbr4k_working_v318.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256'];report=dict(version='v318',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),source=source.relative_to(R).as_posix(),sourceSHA256=a['sha256'],wholeCharacterWithDress=True,collection=col.name,objects=[dict(role=role,name=ob.name,source=name) for role,name,ob in zip(roles,names,objects)],sourceSignatures=before,wholeCopySignatures=signatures([ob.name for ob in objects]),allFiveOriginalWhole181MeshesExactlyPreserved=True,allLocalOrnament301MeshesExactlyPreserved=True,oldSourcesRecoverableHidden=True,portablePackedImages=True,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,physicsVerified=False,productionComplete=False,notPublished=True,wholeVisualAndFormatReviewPending=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start);(O/'apron_ornament_whole_integration_audit_v318.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENTS318_INTEGRATED_WHOLE_STATIC_WIP_AWAIT_REOPEN',flush=True)
