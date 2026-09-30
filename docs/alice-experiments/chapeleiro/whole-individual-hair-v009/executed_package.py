"""Package the entire dressed Chapeleiro with individual rear-braid fibers."""
import hashlib
import json
import shutil
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
generation = json.loads((base/'rear_braid_strands_study_v009/generation.json').read_text(encoding='utf-8'))
export = json.loads((base/'rear_braid_whole_glb_export_v001/export.json').read_text(encoding='utf-8'))
mapping = json.loads((base/'rear_braid_whole_glb_export_v001/guide_mapping_audit.json').read_text(encoding='utf-8'))
review = json.loads((base/'rear_braid_whole_glb_reimport_review_v001/review.json').read_text(encoding='utf-8'))
full_body = json.loads((base/'rear_braid_whole_glb_fullbody_review_v001/review.json').read_text(encoding='utf-8'))
motion = json.loads((base/'rear_braid_whole_glb_motion_review_v001/review.json').read_text(encoding='utf-8'))
contacts = json.loads((base/'rear_braid_strands_study_v009/braid_audit.json').read_text(encoding='utf-8'))

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()

assert export['wholeCharacterWithDress'] and export['exportedFiberCount'] == 102924
assert export['addedRearBraidFiberCount'] == 1500 and export['skinCount'] == 1
assert export['allRiggedVerticesWeighted'] and len(export['animations']) == 4
assert mapping['fiberCount'] == 102924 and mapping['uniqueGuideCount'] == 2118
assert mapping['consistentGuidePerFiber'] and mapping['guideIdsMatchEditableSource']
assert set(review['views']) == {'front', 'left', 'right', 'back'}
assert full_body['fullBodyFraming'] and set(full_body['views']) == {'front', 'back'}
assert {row['action'].split(' /')[0] for row in motion['reviews']} == {'Walk', 'Jump'}
assert contacts['insideClosedHeadProxy'] == contacts['rayDisagreements'] == 0
assert sha(export['model']) == export['modelSha256'] == mapping['modelSha256'] == motion['modelSha256']
assert sha(generation['editableBlend']) == generation['editableBlendSha256']

target = repo/'docs/alice-experiments/chapeleiro/whole-individual-hair-v009'
assert not target.exists(), target
target.mkdir(parents=True)
files = {
    Path(export['model']): 'alice_chapeleiro_complete.glb',
    base/'rear_braid_whole_glb_export_v001/guide_mapping_audit.json': 'guide_mapping_audit.json',
    base/'rear_braid_strands_study_v009/braid_audit.json': 'braid_rest_binding_audit.json',
    base/'rear_braid_whole_glb_reimport_review_v001/checkpoint_decision_v009.json': 'checkpoint_decision.json',
    base/'rear_braid_whole_glb_motion_review_v001/review.json': 'motion_review.json',
    base/'rear_braid_strands_study_v009/executed_study.py': 'executed_braid_authoring.py',
    repo/'blender/export_chapeleiro_individual_hair_checkpoint.py': 'executed_export.py',
    repo/'blender/audit_chapeleiro_reimported_guide_mapping.py': 'executed_mapping_audit.py',
    repo/'blender/render_chapeleiro_exported_checkpoint.py': 'executed_reimport_review.py',
    repo/'blender/review_chapeleiro_exported_hair_motion.py': 'executed_motion_review.py',
    repo/'scripts/package_chapeleiro_whole_checkpoint_v009.py': 'executed_package.py',
}
for view in ('front', 'left', 'right', 'back'):
    files[base/f'rear_braid_whole_glb_reimport_review_v001/{view}.png'] = f'{view}_reimport.png'
for view in ('front', 'back'):
    files[base/f'rear_braid_whole_glb_fullbody_review_v001/{view}.png'] = f'{view}_fullbody.png'
for action in ('walk', 'jump'):
    files[base/f'rear_braid_whole_glb_motion_review_v001/{action}_front.png'] = f'{action}_front.png'
for source, name in files.items():
    assert source.is_file(), source
    shutil.copyfile(source, target/name)
assert sha(target/'alice_chapeleiro_complete.glb') == export['modelSha256']

checkpoint = dict(
    kind='whole_character_checkpoint', stage='Alice Chapeleiro completa com vestido', version='v009',
    model='alice_chapeleiro_complete.glb', modelSha256=export['modelSha256'],
    modelBytes=export['modelBytes'], sourceGeneration='rear_braid_strands_study_v009',
    sourceBlendSha256=generation['editableBlendSha256'], wholeCharacterWithDress=True,
    exportedFiberCount=102924, addedRearBraidFiberCount=1500, hairGuideCount=2118,
    hairRibbonMeshCount=51, fiberAttributes=['_FIBER_ID', '_FIBER_T', '_GUIDE_ID'],
    guideMappingReimportVerified=True, skinCount=1, animations=export['animations'],
    allRiggedVerticesWeighted=True, reimportReviewedViews=review['views'],
    fullBodyReviewedViews=full_body['views'],
    motionReviewedActions=[f"{row['action'].split(' /')[0]} frame {row['frame']}" for row in motion['reviews']],
    braidRestProxySamples=contacts['sampledNonrootPoints'],
    braidRestProxyInsideSamples=contacts['insideClosedHeadProxy'], checkpointOnly=True,
    changesSinceV008='Foram acrescentados 1.500 fios geométricos individuais em uma faixa trançada discreta nas costas, mantendo os 101.424 fios anteriores e o vestido completo. O GLB inteiro foi reimportado e revisado em quatro vistas, corpo inteiro, Walk e Jump.',
    runtimeMotion='O GLB carrega skin da cabeça e atributos por fio; a galeria aplica oscilação leve. As novas tranças seguem rigidamente a cabeça, sem física independente ou colisões transferidas ao navegador.',
    physicsApproved=False, appearanceApproved=False,
    evidence=dict(mapping='guide_mapping_audit.json', restContact='braid_rest_binding_audit.json',
                  motion='motion_review.json',
                  reimportedViews=[f'{view}_reimport.png' for view in review['views']],
                  fullBodyViews=['front_fullbody.png', 'back_fullbody.png'],
                  motionViews=['walk_front.png', 'jump_front.png'],
                  authoringScript='executed_braid_authoring.py', exportScript='executed_export.py'),
    pending=['fidelidade fina e ondas individuais do cabelo contra as fotos',
             'UV 4K do cabelo com visibilidade e oclusão',
             'simulação independente, vento e colisões em todas as ações',
             'física por guia no runtime da galeria',
             'polimento final do rosto, vestido e suas camadas em movimento',
             'FBX final da personagem inteira após validação'])
(target/'checkpoint.json').write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(package=str(target), fileCount=len(files)+1,
                      modelSha256=export['modelSha256'], modelBytes=export['modelBytes'])))
