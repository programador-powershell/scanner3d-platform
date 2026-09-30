"""Package the verified whole Alice after restoring the reviewed brim mask."""
import argparse, hashlib, json, shutil
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--base', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
assert not a.output.exists()
base = a.base
export = base / 'v011_reviewed_brim_cleanup_restored_whole_glb_export_v002'
review = base / 'v011_reviewed_brim_cleanup_restored_whole_glb_review_v001'
source = base / 'v011_reviewed_brim_cleanup_restored_candidate_v001'
read = lambda f: json.loads(f.read_text(encoding='utf-8-sig'))
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
e, r, g = read(export/'export.json'), read(review/'review.json'), read(source/'generation.json')
m = read(export/'guide_mapping_audit.json')
d = read(review/'checkpoint_decision.json')
i = read(source/'reopen_integrity.json')
payload = read(export/'payload_comparison.json')
assert d['checkpointApproved'] and not d['finalAppearanceApproved']
assert sha(Path(e['model'])) == e['modelSha256'] == m['modelSha256'] == r['modelSha256'] == d['modelSha256']
assert sha(Path(g['editableBlend'])) == g['editableBlendSha256']
assert e['wholeCharacterWithDress'] and e['allRiggedVerticesWeighted']
assert e['exportedFiberCount'] == 102924 and e['skinCount'] == 1 and e['sourceHairFacesExcluded'] == 91708
assert m['guideIdsMatchEditableSource'] and m['consistentGuidePerFiber'] and m['uniqueGuideCount'] == 2118
assert all(payload['exactPayloadMatches'].values())
assert r['fullBodyFraming'] and set(r['views']) == {'front','left','right','back'} and r['sourceGlbUnchanged']
assert i['rawFibersGuidesBodyDressAndRigPreserved']
assert g['backBrimResidueMaskStudy']['additionalSourceFacesHidden'] == 103
a.output.mkdir(parents=True)
shutil.copy2(e['model'], a.output/'alice_chapeleiro_complete.glb')
for view in r['views']:
    shutil.copy2(review/f'{view}.png', a.output/f'{view}_reimport.png')
for folder, names in [(export, ['export.json','guide_mapping_audit.json','payload_comparison.json','executed_export.py']),
                      (review, ['review.json','checkpoint_decision.json']),
                      (source, ['generation.json','reopen_integrity.json','recoverable_source_mask.npz'])]:
    for name in names: shutil.copy2(folder/name, a.output/name)
for name in ['v011_reviewed_brim_mask_correspondence_v001.json','v011_reviewed_brim_cleanup_restore_review_v001.json']:
    shutil.copy2(base/name, a.output/name)
pair = base/'v011_reviewed_brim_cleanup_restored_bind_rest_review_v001'
for name in ['baseline_back.png','candidate_back.png']:
    shutil.copy2(pair/name, a.output/name)
manifest = dict(version='v012', kind='whole_character_checkpoint', wholeCharacterWithDress=True,
    model='alice_chapeleiro_complete.glb', modelSha256=e['modelSha256'], modelBytes=e['modelBytes'],
    sourceBlendSha256=g['editableBlendSha256'], exportedFiberCount=102924, hairGuideCount=2118,
    changesSinceV011='Restaurada a máscara reversível de 103 faces residuais sob o chapéu, anteriormente revisadas; corpo, vestido, fios, rig e animações preservados.',
    fullBodyReviewedViews=r['views'], checkpointOnly=True, appearanceApproved=False, physicsApproved=False,
    runtimeMotion='Skin da cabeça; física independente e colisões não transferidas automaticamente.',
    pending=['fidelidade e separação das mechas','UV 4K validado','identidade facial canônica e base compartilhada',
             'física e colisões do cabelo/vestido em todas as ações','FBX final','todas as variantes'])
(a.output/'checkpoint.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
shutil.copy2(__file__, a.output/'executed_package.py')
print(json.dumps(manifest, ensure_ascii=False))
