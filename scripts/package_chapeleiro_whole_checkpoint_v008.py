"""Package the reviewed complete dressed Chapeleiro GLB as a gallery checkpoint."""
import hashlib
import json
import shutil
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
generation = json.loads((base/'between_channels_layered_length_study_v003/generation.json').read_text(encoding='utf-8'))
export = json.loads((base/'checkpoint_v008_raw_export_v001/material_match_export.json').read_text(encoding='utf-8'))
mapping = json.loads((base/'checkpoint_v008_raw_export_v001/guide_mapping_audit.json').read_text(encoding='utf-8'))
review = json.loads((base/'checkpoint_v008_reimport_review_v001/review.json').read_text(encoding='utf-8'))
motion = json.loads((base/'checkpoint_v008_motion_review_v001/review.json').read_text(encoding='utf-8'))
contacts = json.loads((base/'between_channels_layered_length_study_v003/guide_contact_comparison.json').read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert export['wholeCharacterWithDress'] and export['exportedFiberCount'] == 101424
assert export['skinCount'] == 1 and len(export['animations']) == 4
assert mapping['fiberCount'] == 101424 and mapping['uniqueGuideCount'] == 2112
assert mapping['consistentGuidePerFiber'] and mapping['guideIdsMatchEditableSource']
assert set(review['views']) == {'front', 'left', 'right', 'back'}
assert {row['action'].split(' /')[0] for row in motion['reviews']} == {'Walk', 'Jump'}
assert contacts['newInsideSamples'] == 0 and len(contacts['guideIds']) == 888
assert sha(export['model']) == export['modelSha256'] == mapping['modelSha256'] == motion['modelSha256']
assert sha(generation['editableBlend']) == generation['editableBlendSha256']

target = repo/'docs/alice-experiments/chapeleiro/whole-individual-hair-v008'
assert not target.exists(), target
target.mkdir(parents=True)
files = {
    Path(export['model']): 'alice_chapeleiro_complete.glb',
    base/'checkpoint_v008_raw_export_v001/guide_mapping_audit.json': 'guide_mapping_audit.json',
    base/'checkpoint_v008_motion_review_v001/review.json': 'motion_review.json',
    repo/'blender/study_chapeleiro_between_wave_channels.py': 'executed_between_wave_channels.py',
    repo/'blender/study_chapeleiro_back_wave_length_with_arc.py': 'executed_layered_length.py',
    repo/'blender/export_chapeleiro_individual_hair_checkpoint.py': 'executed_export.py',
    repo/'scripts/match_chapeleiro_hair_material.py': 'executed_material_match.py',
    repo/'blender/render_chapeleiro_exported_checkpoint.py': 'executed_reimport_review.py',
    repo/'blender/review_chapeleiro_exported_hair_motion.py': 'executed_motion_review.py',
    repo/'scripts/package_chapeleiro_whole_checkpoint_v008.py': 'executed_package.py',
}
for view in ('front', 'left', 'right', 'back'):
    files[base/f'checkpoint_v008_reimport_review_v001/{view}.png'] = f'{view}_reimport.png'
for action in ('walk', 'jump'):
    files[base/f'checkpoint_v008_motion_review_v001/{action}_front.png'] = f'{action}_front.png'
for source, name in files.items():
    assert source.is_file(), source
    shutil.copyfile(source, target/name)
assert sha(target/'alice_chapeleiro_complete.glb') == export['modelSha256']
checkpoint = dict(
    kind='whole_character_checkpoint', stage='Alice Chapeleiro completa com vestido', version='v008',
    model='alice_chapeleiro_complete.glb', modelSha256=export['modelSha256'], modelBytes=export['modelBytes'],
    sourceGeneration='between_channels_layered_length_study_v003', sourceBlendSha256=generation['editableBlendSha256'],
    wholeCharacterWithDress=True, exportedFiberCount=101424, hairGuideCount=2112, hairRibbonMeshCount=50,
    fiberAttributes=['_FIBER_ID', '_FIBER_T', '_GUIDE_ID'], guideMappingReimportVerified=True,
    skinCount=1, animations=export['animations'], allRiggedVerticesWeighted=export['allRiggedVerticesWeighted'],
    hairRoughness=.68, hairSpecularExtensionFactor=.24, dracoGenericQuantizationBits=18,
    reimportReviewedViews=review['views'],
    motionReviewedActions=[f"{row['action'].split(' /')[0]} frame {row['frame']}" for row in motion['reviews']],
    changedGuidesBetweenWaves=672, lengthAdjustedRearGuides=888, restProxyGuideSamplesPerGuide=125,
    newRestProxyPenetrations=contacts['newInsideSamples'], checkpointOnly=True,
    changesSinceV007='Canais discretos entre as ondas traseiras e pontas escalonadas de até 35 mm aproximam o comprimento e a separação do cabelo da referência. O vestido, as raízes, os pinos e os demais fios permanecem preservados. O GLB inteiro foi reimportado nas quatro vistas e em Walk/Jump.',
    runtimeMotion='O GLB carrega skin da cabeça e atributos por fio; a galeria aplica oscilação leve. Simulação física independente e colisões do Blender não foram transferidas ao navegador.',
    physicsApproved=False, appearanceApproved=False,
    evidence=dict(guideMapping='guide_mapping_audit.json', motion='motion_review.json',
                  reimportedViews=[f'{view}_reimport.png' for view in review['views']],
                  motionViews=['walk_front.png', 'jump_front.png'],
                  sourceScripts=['executed_between_wave_channels.py', 'executed_layered_length.py'],
                  exportScript='executed_export.py', materialMatchScript='executed_material_match.py'),
    pending=['fidelidade final do rosto e penteado Chapeleiro contra as fotos',
             'remoção completa das placas de cabelo Tripo sem danificar o vestido',
             'UV 4K do cabelo com visibilidade e oclusão',
             'simulação independente, vento e colisões dos fios em todas as ações',
             'física por guia no runtime da galeria',
             'polimento final do vestido, renda, camadas interiores e movimento',
             'FBX final da personagem inteira após validação'])
(target/'checkpoint.json').write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(package=str(target), fileCount=len(files)+1, modelSha256=export['modelSha256'], modelBytes=export['modelBytes'])))
