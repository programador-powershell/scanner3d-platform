"""Publish an unfinished measured Ivory rig response with its real evidence.

Reused reference views are explicitly tied to the previous GLB and exact field
comparison. New response views come from the actual reimported foundation GLB.
The complete editable remains local; the final FBX is not produced here.
"""
import argparse, hashlib, json, shutil, struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', required=True)
p.add_argument('--previous', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
root, previous, out = map(Path, [a.root, a.previous, a.output])
repo = Path(__file__).resolve().parents[1]
workspace = repo.parent
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
write = lambda f, v: Path(f).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
g, identity = read(root / 'generation.json'), read(root / 'actual_glb_field_identity.json')
review_dir = root / 'actual_ivory_export_review_v001'
review = read(review_dir / 'comparison.json')
fit = read(g['ivoryFitReport'])
seed = read(fit['seedReport'])
physics = read(fit['physicsReport'])
reopen = read(root / 'full_editable_reopen.json')
measured = read(root / 'actual_shell_fit_measurement.json')
assert sha(g['editableBlend']) == g['editableBlendSha256'] == reopen['editableSha256']
assert reopen['actualSkinnedPreviewPieces'] == 230 and reopen['actualBones'] == 173
assert reopen['additionalIvoryStudyAction'] == g['ivoryStudyClip']
assert identity['geometryUvNormalsSkinWeightsIndicesMaterialsImagesBindJointsIdentical']
assert len(identity['fourOriginalAnimationsCompared']) == 4
assert all(row['maximumChannelDifference'] == 0 for row in identity['fourOriginalAnimationsCompared'])
assert identity['newModelSha256'] == review['modelSha256'] == g['exports']['foundation']['modelSha256']
assert fit['other137BonesUnchanged'] and fit['actualGeometryAndWeightsUnchanged']
assert sha(fit['dataFile']) == fit['dataSha256'] == measured['fitDataSha256']
assert not out.exists(), 'Preserve prior published study packages.'
out.mkdir(parents=True)
inventory = []
def copy(file, relative, expected=None):
    file = Path(file)
    digest = sha(file)
    if expected: assert digest == expected, str(file)
    assert file.stat().st_size < 100 * 1024 * 1024, 'Keep complete large editables local.'
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target)
    assert sha(target) == digest
    row = {'file': str(Path(relative).as_posix()), 'sourceFile': str(file),
           'sha256': digest, 'bytes': target.stat().st_size}
    inventory.append(row)
    return row

notes = {
    'foundation': [
        'A geometria, os UVs, materiais, pesos, bind e quatro ações anteriores permanecem exatamente iguais. As quatro vistas e doze poses de referência foram conservadas com prova de igualdade dos campos; não foram renderizadas novamente.',
        'O novo clipe Corrida com tecido / anágua em refinamento contém a aproximação da simulação por 36 ossos IvoryCloth em 29 poses. Sete renders novos foram feitos do GLB reimportado, com a fundação completa e as 33 peças da família Ivory.',
        'A aproximação ainda chega a 2,55 cm de diferença da simulação. A saia preta atravessa a anágua perto do quadril; as pernas e adornos também exigem revisão de contato. A saia preta e as demais famílias ainda não têm a mesma resposta física.',
        'Corset, costuras finas, franzidos, cascatas diagonais, trama das meias e renda continuam diferentes da foto. O clipe de estudo inclui uma entrada da pose de referência na corrida e ainda não é um ciclo fechado. As quatro ações originais não receberam esta resposta física.'
    ],
    'whole': [
        'O GLB exterior permanece exatamente o da v093, inclusive as quatro ações e o refinamento dos pesos das mãos. As quatro vistas e doze poses conservam sua própria foto e os renders anteriores.',
        'Palma, dedos, acabamento das luvas, abertura na axila, colapso da manga, transição do cabelo para o braço e penetração da perna na saia continuam pendentes. A resposta física da anágua desta versão pertence somente ao export da fundação.'
    ]
}
families = {}
for family, count in [('foundation', 229), ('whole', 1)]:
    generation = read(root / (family + '_generation.json'))
    old = previous / family
    for file in old.rglob('*'):
        if file.is_file() and file.suffix.lower() in {'.png', '.jpg'}:
            copy(file, family + '/' + file.relative_to(old).as_posix())
    model = copy(generation['model'], family + '/skin_study.glb', generation['modelSha256'])
    photo = copy(generation['sourcePhoto'], family + '/source_photo.png', generation['sourcePhotoSha256'])
    raw = Path(generation['model']).read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    document = json.loads(raw[20:20 + length])
    clips = [c['name'] for c in document['animations']]
    assert len([n for n in document['nodes'] if 'skin' in n and 'mesh' in n]) == count
    assert len(document['skins']) == 1 and len(document['skins'][0]['joints']) == 173
    assert len(clips) == (5 if family == 'foundation' else 4)
    for filename in ['comparison.json', 'motion_comparison.json']:
        record = read(old / filename)
        rendered_hash = record['modelSha256']
        if family == 'foundation': assert rendered_hash == identity['oldModelSha256']
        else: assert rendered_hash == generation['modelSha256']
        assert record['sourcePhotoSha256'] == generation['sourcePhotoSha256']
        record.update(model=model['file'], modelSha256=model['sha256'], sourcePhoto=photo['file'],
                      displayModel={k: model[k] for k in ['file', 'sha256', 'bytes']},
                      renderedModelSha256=rendered_hash, actualDisplayedClips=clips,
                      evidenceReused=True, evidenceReuseReason='Exact geometry/UV/skin/bind/material and original animation identity; additional Ivory action reviewed separately.',
                      visibleDifferences=notes[family], visualReviewPerformed=True)
        write(out / family / filename, record)
    families[family] = {'model': {k: model[k] for k in ['file', 'sha256', 'bytes']},
                        'sourcePhoto': {k: photo[k] for k in ['file', 'sha256', 'bytes']},
                        'actualSkinnedMeshes': count, 'actualSkeletons': 1, 'actualJoints': 173,
                        'actualClips': clips, 'visualStatus': 'needs_refinement'}

photo = Image.open(g['exports']['foundation']['sourcePhoto']).convert('RGB')
board = Image.new('RGB', (2800, 1870), (24, 26, 29))
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 25)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
draw.text((24, 20), 'CHAPELEIRO / ANÁGUA NO GLB / RESPOSTA NOS OSSOS EM REFINAMENTO', font=font, fill='white')
photo.thumbnail((520, 1200))
board.paste(photo, (24, 80))
draw.text((24, 760), 'Foto original completa da etapa 01', font=small, fill='#e3d3b4')
for line, y in zip(['O GLB foi reimportado no Blender.', 'Os sete renders são do novo clipe.', 'Diferença da simulação: até 2,55 cm.', 'Contato entre camadas pendente.', 'Saia preta sem resposta física.', 'Fidelidade ainda sem aprovação.'], range(820, 1130, 46)):
    draw.text((24, y), line, font=small, fill='#e3d3b4')
for i, row in enumerate(review['renders']):
    x, y = 580 + (i % 4) * 550, 80 + (i // 4) * 855
    artifact = copy(row['file'], 'ivory_response/renders/' + Path(row['file']).name, row['sha256'])
    im = Image.open(row['file']).convert('RGBA')
    im.thumbnail((530, 780))
    board.paste(im, (x, y), im)
    scope = 'Fundação completa' if row['scope'] == 'foundation' else 'Família Ivory inteira'
    draw.text((x, y + 790), f"{scope} / pose {row['sourcePhysicsFrame']} / {row['view']}", font=small, fill='white')
draw.text((24, 1820), 'As quatro ações originais permanecem iguais. Este estudo ainda não valida corrida, todas as camadas, colisões ou FBX final.', font=small, fill='#e3d3b4')
board_file = root / 'photo_vs_actual_ivory_joint_motion.jpg'
board.save(board_file, quality=94)
board_artifact = copy(board_file, 'photo_vs_actual_ivory_joint_motion.jpg')
response = dict(review)
response['renders'] = [{**r, 'file': 'ivory_response/renders/' + Path(r['file']).name} for r in review['renders']]
response.update(sourcePhoto='foundation/source_photo.png', board=board_artifact,
                actualCarrierToSolverMaximumMeters=max(r['fittedSkinErrorToActualSolver']['maximum'] for r in fit['frames']),
                actualExportToFittedCarrierMaximumMeters=max(r['actualShellToFittedCarrierMaximumMeters'] for r in measured['frames']),
                visibleDifferences=notes['foundation'], originalFourActionsPhysicsUnchanged=True,
                responseBaked=True, signedContactVerified=False, closedLoopVerified=False)
write(out / 'ivory_response/comparison.json', response)

raw = [
    (root / 'generation.json', 'generation.json', None),
    (root / 'foundation_generation.json', 'foundation_generation.json', None),
    (root / 'whole_generation.json', 'whole_generation.json', None),
    (root / 'shared_rig_bind.json', 'inherited_shared_rig_bind.json', None),
    (root / 'executed_bake.py', 'executed_bake.py', g['scriptSha256']),
    (Path(g['ivoryFitReport']), 'fit.json', None),
    (Path(fit['dataFile']), 'fitted_ivory_joint_motion.npz', fit['dataSha256']),
    (Path(g['ivoryFitReport']).parent / 'executed_fit.py', 'executed_fit.py', fit['scriptSha256']),
    (Path(fit['seedReport']), 'seed.json', None),
    (Path(seed['dataFile']), 'actual_ivory_skin_seed.npz', seed['dataSha256']),
    (Path(fit['seedReport']).parent / 'executed_extraction.py', 'executed_extraction.py', seed['executedExtractionSha256']),
    (Path(fit['physicsReport']), 'actual_continuous_solver_motion.json', None),
    (Path(fit['physicsReport']).parent / 'actual_continuous_cloth_frames.npz', 'actual_continuous_cloth_frames.npz', fit['actualPhysicsDataSha256']),
    (root / 'actual_glb_field_identity.json', 'actual_glb_field_identity.json', None),
    (workspace / 'tools/compare_chapeleiro_v094_glb_fields.py', 'executed_compare_glb_fields.py', identity['scriptSha256']),
    (root / 'full_editable_reopen.json', 'full_editable_reopen.json', None),
    (repo / 'blender/audit_chapeleiro_shared_rig_checkpoint.py', 'executed_full_editable_audit.py', None),
    (review_dir / 'comparison.json', 'actual_export_comparison.json', None),
    (review_dir / 'actual_pose_measurements.json', 'actual_pose_measurements.json', None),
    (review_dir / 'actual_exported_ivory_poses.npz', 'actual_exported_ivory_poses.npz', review['actualExportDataSha256']),
    (review_dir / 'executed_review.py', 'executed_review.py', review['scriptSha256']),
    (root / 'actual_shell_fit_measurement.json', 'actual_shell_fit_measurement.json', None),
    (repo / 'scripts/measure_chapeleiro_exported_ivory_fit.py', 'executed_measure_exported_fit.py', measured['scriptSha256']),
    (Path(__file__), 'executed_package.py', sha(__file__)),
]
for file, name, digest in raw: copy(file, 'raw/' + name, digest)
copy(root / 'skin_audit.json', 'skin_audit.json')
schema = read(root / 'shared_rig_bind.json')
schema['clothFamilies']['IvoryCloth'].update(response='Measured approximation baked only in the additional Ivory study action; four original actions retain parent motion.',
                                          studyClip=g['ivoryStudyClip'], responseBaked=True, collisionVerified=False)
schema['inheritedDefinitionSourceSha256'] = sha(root / 'shared_rig_bind.json')
write(out / 'shared_rig_bind.json', schema)
copy(previous / 'photo_vs_actual_hand_motion_before_after.jpg', 'photo_vs_actual_hand_motion_before_after.jpg')
write(out / 'checkpoint.json', {'status': 'needs_refinement', 'families': families,
      'fullLocalEditable': {'file': g['editableBlend'], 'bytes': g['editableBytes'], 'sha256': g['editableBlendSha256']},
      'additionalIvoryResponseBaked': True, 'otherLayersPhysicsResponseBaked': False, 'wholeGlbUnchanged': True,
      'allLayersFinished': False, 'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False,
      'finalFbxExported': False, 'nextVariantMayStart': False, 'additionalCreditsConsumed': 0,
      'visibleDifferences': notes, 'referenceEvidenceSourceRevision': '4b56a7268c7f206c76f2dfd512deb90ed1df1604'})
write(out / 'artifact_inventory.json', {'artifacts': inventory, 'preservedExactlyAsBytes': True})
(out / '.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n', encoding='utf-8', newline='\n')
(out / 'README.md').write_text('''# Chapeleiro v094 — anágua em refinamento

O GLB da fundação inclui uma quinta animação: **Corrida com tecido / anágua em refinamento**. Ela aproxima 29 poses medidas do solver em 36 ossos IvoryCloth existentes. O exterior permanece inteiro e idêntico à v093. Nenhum crédito adicional foi consumido.

A [foto completa e sete renders novos do GLB reimportado](photo_vs_actual_ivory_joint_motion.jpg) mostram a fundação e a família Ivory inteira. A aproximação ainda apresenta até 2,55 cm de diferença da simulação. Saia preta, demais camadas, contato entre peças, continuidade do ciclo, polimento, UVs e todas as fotos permanecem em trabalho. As quatro ações originais conservam sua resposta anterior.

As vistas de referência e doze poses anteriores foram reutilizadas de forma explícita: os 1.153 arrays de atributos, materiais, imagens, bind e quatro ações do GLB foram comparados sem diferença. Veja [a medição](raw/actual_glb_field_identity.json). Isso não substitui os sete renders do novo clipe nem aprova fidelidade.

O arquivo Blender completo permanece local, com seu tamanho e SHA em [checkpoint.json](checkpoint.json). Ele foi reaberto com 230 peças, um rig de 173 ossos, cinco ações, 14 suportes e 12 imagens de arquivo empacotadas. O FBX final não foi exportado; nenhuma próxima variante pode começar. [Dados, programas executados e hashes](artifact_inventory.json) permitem revisar a simulação, ajuste, exportação e reimportação.
''', encoding='utf-8', newline='\n')
print('ACTUAL_IVORY_JOINT_STUDY_PACKAGED', len(inventory), g['editableBytes'])
