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
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a';review=read(O/'apron_ornament_atlas_review_decision_v420.json');assert review['acceptedForWholeStaticWIPIntegrationReview'] and review['allImagesActuallyInspected'];a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v417.json');source=R/a['path'];assert sha(source)==a['sha256'];prior=read(O/'apron_ornament_whole_integration_audit_v377.json');priorNames=list(prior['wholeCopySignatures']);assert signatures(priorNames)==prior['wholeCopySignatures'];oldNames=[x['name'] for x in prior['objects'] if x['role'] in {'character','apron','chain','cord','lace'}];assert len(oldNames)==5
names=oldNames+[r['object'] for r in a['newObjects']];roles=['character','apron','chain','cord','lace']+['ornament_'+r['id'] for r in a['newObjects']];before=signatures(names);col=bpy.data.collections.new('COELHO_WHOLE_CHECKPOINT_V421_WIP');bpy.context.scene.collection.children.link(col);objects=[]
for name,role in zip(names,roles):
    src=bpy.data.objects[name];ob=src.copy();ob.data=src.data.copy();ob.name='Alice.Coelho.WholeCheckpoint421.'+role;col.objects.link(ob);ob['alice_role']=role;ob['rigged']=False;ob['physicsVerified']=False;objects.append(ob)
for ob in bpy.context.scene.objects:
    if ob.type in {'MESH','CURVE'}:ob.hide_render=True;ob.hide_set(True)
for ob in objects:ob.hide_render=False;ob.hide_set(False)
assert signatures(names)==before
for name,ob in zip(names,objects):assert signatures([ob.name])[ob.name]==before[name]
assert not bpy.data.libraries
for im in bpy.data.images:
    if im.type=='IMAGE' and im.size[0]:assert im.packed_file,im.name
scene=bpy.context.scene;scene['alice_stage']='coelho_complete_ornament_front_corner_own_pbr4k_v421_WIP';scene['productionComplete']=False;scene['rigged']=False;scene['canonicalIdentityApproved']=False;scene['anatomicalHeightVerified']=False
text=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_INTEIRA_V421_WIP');text.write('Alice INTEIRA com vestido em produção. Integra somente os cinco pendentes417 com conta de ouro e borda frontal refinadas, UV próprio e quatro mapas4K incorporados. Geometria anterior do corpo, vestido, avental, corrente, cordão e renda da fonte377 preservada. Fontes anteriores ocultas e recuperáveis. Azul opaco com reflexão colorida é aproximação artística; não afirmar óptica real de safira, nova projeção fotográfica ou detalhe normal highpoly. Exportar/reimportar GLB/FBX inteiros e verificar antes de publicar. Base comum/168cm/rosto/corpo/rig, camadas/LOD, cabelo individual, tecido/física/colisões, ações/expressões/gameplay seguem pendentes. Checkpoint não conclui asset nem autoriza próximo Tripo.\n')
out=O/'alice_coelho_complete_ornament_pbr4k_working_v421.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256'];report=dict(version='v421',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),source=source.relative_to(R).as_posix(),sourceSHA256=a['sha256'],wholeCharacterWithDress=True,collection=col.name,objects=[dict(role=role,name=ob.name,source=name) for role,name,ob in zip(roles,names,objects)],sourceSignatures=before,wholeCopySignatures=signatures([ob.name for ob in objects]),allFivePreviousWhole377BaseMeshesExactlyPreserved=True,allLocalOrnament417MeshesExactlyPreserved=True,oldSourcesRecoverableHidden=True,portablePackedImages=True,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,physicsVerified=False,productionComplete=False,notPublished=True,wholeVisualAndFormatReviewPending=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start);(O/'apron_ornament_whole_integration_audit_v421.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENTS417_INTEGRATED_WHOLE421_STATIC_WIP_AWAIT_REOPEN',flush=True)
