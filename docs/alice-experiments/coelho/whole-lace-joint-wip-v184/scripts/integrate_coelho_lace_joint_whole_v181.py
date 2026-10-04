"""Integrate the verified local lace correction into a recoverable whole-character WIP."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
R=Path('F:/Alice/SharedProduction'); O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'; start=time.time()
a=json.loads((O/'apron_neighbor_sections_authoring_audit_v177.json').read_text(encoding='utf-8-sig')); q=json.loads((O/'apron_all_lace_contact_audit_v178.json').read_text(encoding='utf-8-sig')); decision=json.loads((O/'apron_joint_clearance_review_decision_v180.json').read_text(encoding='utf-8-sig'))
assert q['crossMotifSATTrianglePairs']==q['diamondNetSATTrianglePairs']==0 and q['independentSavedFloat32Reopen'] and decision['acceptedForWholeIntegrationReview']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()
src=R/a['path']; assert sha(src)==a['sha256']
def sig(names):
    result={}
    for name in names:
        ob=bpy.data.objects[name]; m=ob.data
        result[name]=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([x.uv[:] for x in u.data],np.float32).tobytes()).hexdigest() for u in m.uv_layers],keys={} if not m.shape_keys else {k.name:hashlib.sha256(np.asarray([v.co[:] for v in k.data],np.float32).tobytes()).hexdigest() for k in m.shape_keys.key_blocks},materials=[mat.name for mat in m.materials],matrixWorld=[list(row) for row in ob.matrix_world])
    return result
names=['Alice.Coelho.WholeCheckpoint145.'+role for role in ['character','apron','chain','cord']]+[a['object']]; roles=['character','apron','chain','cord','lace']
preservedNames=names+['Alice.Coelho.WholeCheckpoint145.lace','Alice.Coelho.Complete.High.SourcePreserved']; before=sig(preservedNames)
col=bpy.data.collections.new('COELHO_WHOLE_CHECKPOINT_V181_WIP'); bpy.context.scene.collection.children.link(col); objects=[]
for role,name in zip(roles,names):
    source=bpy.data.objects[name]; ob=source.copy(); ob.data=source.data.copy(); col.objects.link(ob); ob.name='Alice.Coelho.WholeCheckpoint181.'+role; ob['alice_role']=role; ob['rigged']=False; ob['physicsVerified']=False; objects.append(ob)
for ob in bpy.context.scene.objects:
    if ob.type in {'MESH','CURVE'}: ob.hide_render=True; ob.hide_set(True)
for ob in objects: ob.hide_render=False; ob.hide_set(False)
for im in bpy.data.images:
    if im.type=='IMAGE' and im.size[0]: assert im.packed_file
assert not bpy.data.libraries and sig(preservedNames)==before
for role,name,ob in zip(roles,names,objects): assert sig([ob.name])[ob.name]==before[name]
scene=bpy.context.scene; scene['alice_stage']='coelho_apron_lace_joint_clearance_whole_v181_WIP'; scene['productionComplete']=False; scene['rigged']=False; scene['canonicalIdentityApproved']=False; scene['anatomicalHeightVerified']=False
intro=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_V181_WIP'); intro.write('Alice INTEIRA com vestido, autoria estática. Renda v177 integrada: contatos entre motivos e entre fios da rede foram corrigidos e reabertos/verificados. Os demais contatos internos da renda ainda não são juntas de costura aprovadas. Todas as fontes anteriores ficam ocultas e recuperáveis. Rig, identidade/corpo comum de 168 cm, camadas reais, topologia/LOD, cabelo individual, tecido, vento/colisões, ações/expressões e gameplay continuam pendentes. Esta integração não é conclusão do asset nem publicação: reabrir/renderizar/exportar/reimportar o personagem inteiro e publicar antes de mudar de parte/movimento. A geração Tripo de 55 créditos já ocorreu uma vez; não gastar créditos adicionais.\n')
out=O/'alice_coelho_complete_apron_lace_joint_working_v181.blend'; assert not out.exists(); bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True); assert sha(src)==a['sha256']
report=dict(version='v181',source=src.relative_to(R).as_posix(),sourceSHA256=a['sha256'],path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),wholeCharacterWithDress=True,collection=col.name,objects=[dict(role=role,name=ob.name,source=name) for role,ob,name in zip(roles,objects,names)],sourceSignatures=before,wholeCopySignatures=sig([ob.name for ob in objects]),sourceWholeHighAndAllCandidatesPreserved=True,portablePackedImages=True,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,physicsVerified=False,productionComplete=False,notPublished=True,wholeVisualAndFormatReviewPending=True,elapsedSeconds=time.time()-start)
(O/'apron_whole_integration_audit_v181.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print('WHOLE_JOINT_CLEARANCE_INTEGRATED',report['path'],flush=True)
