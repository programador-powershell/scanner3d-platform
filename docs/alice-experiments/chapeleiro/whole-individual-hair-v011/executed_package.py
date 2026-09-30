"""Package only a reviewed complete dressed character checkpoint, never pieces."""
import argparse, hashlib, json, shutil
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--base',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert not a.output.exists()
exp=a.base/'v009_head_residue_cleanup_whole_glb_export_v001'
review=a.base/'v009_head_residue_cleanup_whole_glb_reimport_review_v001'
generation=a.base/'v009_head_residue_cleanup_candidate_v001'
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
e=read(exp/'export.json');mapping=read(exp/'guide_mapping_audit.json')
payload=read(exp/'payload_comparison.json');r=read(review/'review.json')
decision=read(review/'checkpoint_decision.json');g=read(generation/'generation.json')
assert decision['checkpointApproved'] and not decision['finalAppearanceApproved']
assert sha(Path(e['model']))==e['modelSha256']==mapping['modelSha256']==r['modelSha256']==decision['modelSha256']
assert e['wholeCharacterWithDress'] and e['allRiggedVerticesWeighted'] and e['exportedFiberCount']==102924
assert e['sourceHairFacesExcluded']==91605 and e['skinCount']==1
assert mapping['guideIdsMatchEditableSource'] and mapping['consistentGuidePerFiber'] and mapping['uniqueGuideCount']==2118
assert all(payload['exactPayloadMatches'].values())
assert set(r['views'])=={'front','left','right','back'} and r['additionalFullBodyViews']==['front','back']
assert g['headResidueCleanup']['additionalFacesHidden']==9 and sha(Path(g['editableBlend']))==g['editableBlendSha256']
a.output.mkdir(parents=True)
shutil.copy2(e['model'],a.output/'alice_chapeleiro_complete.glb')
for view in r['views']:shutil.copy2(review/f'{view}.png',a.output/f'{view}_reimport.png')
for view in ('front','back'):shutil.copy2(review/f'{view}_fullbody.png',a.output/f'{view}_fullbody.png')
for src,name in [(exp/'export.json','export.json'),(exp/'guide_mapping_audit.json','guide_mapping_audit.json'),
    (exp/'payload_comparison.json','payload_comparison.json'),(exp/'executed_export.py','executed_export.py'),
    (review/'review.json','reimport_review.json'),(review/'checkpoint_decision.json','checkpoint_decision.json'),
    (generation/'executed_authoring.py','executed_authoring.py'),(generation/'recoverable_mask.npz','recoverable_mask.npz')]:
    shutil.copy2(src,a.output/name)
for folder in ('v009_head_residue_cleanup_hidden_review_v001','v009_head_residue_cleanup_fullbody_review_v001'):
    src=a.base/folder;assert read(src/'review.json')['headResidueCleanupReopenIntegrity']['exactChangedMaskFaceCount']==9
    dst=a.output/folder;dst.mkdir()
    for path in src.iterdir():
        if path.suffix in ('.png','.json'):shutil.copy2(path,dst/path.name)
report=dict(kind='whole_character_checkpoint',version='v011',stage='Alice Chapeleiro inteira com vestido',
    model='alice_chapeleiro_complete.glb',modelSha256=e['modelSha256'],modelBytes=e['modelBytes'],
    sourceBlendSha256=g['editableBlendSha256'],wholeCharacterWithDress=True,
    changesSinceV010='Nove faces residuais do cabelo original próximas à cabeça foram ocultadas por máscara reversível no projeto completo e excluídas do GLB. Demais estudos rejeitados não foram integrados.',
    exportedFiberCount=102924,hairGuideCount=2118,skinCount=1,allRiggedVerticesWeighted=True,
    animations=e['animations'],exactHairSkinAndAnimationPayloadsMatchV010=True,
    reimportReviewedViews=r['views'],fullBodyReviewedViews=['front','back'],
    appearanceApproved=False,physicsApproved=False,checkpointOnly=True,
    runtimeMotion='Skin da cabeça e oscilação leve na galeria; simulação independente e colisões não transferidas.',
    pending=['resíduos adicionais de cabelo e acabamento da cabeça','fluxo, volume e separação fina das mechas contra a referência',
        'identidade facial canônica e fidelidade 3D','UV 4K com oclusão','física/colisões de cabelo e vestido em todas as ações',
        'FBX final após validação','concluir Chapeleiro e todas as outras variantes'])
(a.output/'checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
shutil.copy2(__file__,a.output/'executed_package.py')
print(json.dumps(dict(package=str(a.output),modelSha256=e['modelSha256'],modelBytes=e['modelBytes'])))
