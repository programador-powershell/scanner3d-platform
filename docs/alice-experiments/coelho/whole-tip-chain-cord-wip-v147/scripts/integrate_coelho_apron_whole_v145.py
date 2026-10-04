"""Whole character WIP integration, preserving authoring/source data and portability."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';start=time.time();a=json.loads((O/'apron_cord_spacing_authoring_audit_v142.json').read_text(encoding='utf-8-sig'));q=json.loads((O/'apron_tip_chain_cord_triangle_audit_v143.json').read_text(encoding='utf-8-sig'));r=q['records'][0];assert r['selfSATTrianglePairs']==0 and all(x['SATTrianglePairs']==0 for x in r['contacts'].values());src=R/a['path'];assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];chain=json.loads((O/'apron_chain_links_v136.json').read_text(encoding='utf-8-sig'));assert len(chain['links'])==212
names=['Alice.Coelho.Complete.GameCandidate',a['clothObject']]+[p['object'] for p in a['parts']];roles=['character','apron','chain','cord','lace'];s=bpy.context.scene
def sig(names):
 out={}
 for name in names:
  m=bpy.data.objects[name].data;out[name]=dict(positions=hashlib.sha256(np.array([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.array([x.uv[:] for x in u.data],np.float32).tobytes()).hexdigest() for u in m.uv_layers],keys={} if not m.shape_keys else {k.name:hashlib.sha256(np.array([v.co[:] for v in k.data],np.float32).tobytes()).hexdigest() for k in m.shape_keys.key_blocks},materials=[mat.name for mat in m.materials])
 return out
before=sig(names+['Alice.Coelho.Complete.High.SourcePreserved']);col=bpy.data.collections.new('COELHO_WHOLE_CHECKPOINT_V145_WIP');s.collection.children.link(col);objects=[]
for role,name in zip(roles,names):
 source=bpy.data.objects[name];ob=source.copy();ob.data=source.data.copy();col.objects.link(ob);ob.name='Alice.Coelho.WholeCheckpoint145.'+role;ob['alice_role']=role;ob['rigged']=False;ob['physicsVerified']=False;objects.append(ob)
for x in s.objects:
 if x.type in {'MESH','CURVE'}:x.hide_render=True;x.hide_set(True)
for ob in objects:ob.hide_render=False;ob.hide_set(False)
for im in bpy.data.images:
 if im.type=='IMAGE' and im.size[0]:assert im.packed_file
assert not bpy.data.libraries and sig(names+['Alice.Coelho.Complete.High.SourcePreserved'])==before
s['alice_stage']='coelho_apron_tip_chain_cord_static_whole_checkpoint_v145_WIP';s['productionComplete']=False;s['rigged']=False;s['canonicalIdentityApproved']=False;s['anatomicalHeightVerified']=False
text=bpy.data.texts.new('LEIA_PRIMEIRO_COELHO_V145_WIP');text.write('Personagem INTEIRO com vestido, checkpoint de autoria estática: ponta do avental corrigida, corrente212elos redistribuída, cordões separados e renda individual. Fontes e estudos preservados e ocultos. Não é Alice final: referência/rosto/corpo comum168cm, camadas, topologia de deformação, rig, cabelo individual, física/colisões/ações/expressões/gameplay continuam pendentes. Não publicar peças isoladas. ReimportaçãoGLB/FBX e revisão do personagem inteiro obrigatórias antes de publicar. Uma geração55créditos, nenhum gasto adicional. Continuar a produção após exportar, sem iniciar outro asset próprio.\n')
out=O/'alice_coelho_complete_apron_tip_chain_cord_working_v145.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert hashlib.sha256(src.read_bytes()).hexdigest()==a['sha256'];report=dict(version='v145',source=src.relative_to(R).as_posix(),sourceSHA256=a['sha256'],path=out.relative_to(R).as_posix(),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),wholeCharacterWithDress=True,collection=col.name,objects=[dict(role=role,name=ob.name,source=name) for role,ob,name in zip(roles,objects,names)],sourceSignatures=before,sourceWholeHighApronChainCordLacePreserved=True,portablePackedImages=True,rigged=False,canonicalIdentityApproved=False,anatomicalHeightVerified=False,physicsVerified=False,productionComplete=False,notPublished=True,wholeVisualAndFormatReviewPending=True,elapsedSeconds=time.time()-start);(O/'apron_whole_integration_audit_v145.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE_INTEGRATED_WIP',out,flush=True)
