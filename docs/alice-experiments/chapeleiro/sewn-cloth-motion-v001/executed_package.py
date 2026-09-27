"""Preserve completed local sewn-cloth controls and their full-photo review."""
import argparse, hashlib, json, shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--review', required=True)
a = p.parse_args()
workspace = Path(__file__).resolve().parents[1]
repo = workspace / 'scanner3d-platform'
base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
out = repo / 'docs/alice-experiments/chapeleiro/sewn-cloth-motion-v001'
assert not out.exists()
out.mkdir(parents=True)
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
write = lambda f, r: Path(f).write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
inventory = []
def copy(file, relative, digest=None):
    file = Path(file)
    if digest: assert sha(file) == digest, str(file)
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target)
    assert sha(target) == sha(file)
    inventory.append({'file': Path(relative).as_posix(), 'sha256': sha(target), 'bytes': target.stat().st_size})

g = read(base / 'foundation_shared_rig_v094/generation.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert Path(g['editableBlend']).stat().st_size > 100 * 1024 * 1024
cases, reports, arrays, reviews = [], [], [], []
for label, version in [('inherited_mass_springs', 2), ('areal_mass_springs', 3), ('areal_mass_welded', 5)]:
    folder = base / f'sewn_ivory_black_cloth_v{version:03d}'
    r = read(folder / 'actual_sewn_solver_motion.json')
    assert r['parentEditableUnchanged'] and r['exportedModelUnchanged'] and r['clothNeverBypassedDuringSequence']
    assert len(r['frames']) == 29 and r['parentEditableSha256'] == g['editableBlendSha256']
    reports.append(r)
    arrays.append(np.load(r['dataFile']))
    for name, digest in [('actual_sewn_solver_motion.json', None), ('executed_probe.py', r['scriptSha256']),
                         ('executed_assembly.py', r['assemblyHelperSha256'])]:
        copy(folder / name, label + '/' + name, digest)
    copy(r['dataFile'], label + '/actual_cloth_frames.npz', r['dataSha256'])
    copy(base / (folder.name + '.log'), label + '/actual_execution.log')
    if version != 2: copy(folder / 'mass_calibration.json', label + '/mass_calibration.json')
    if version == 5: copy(folder / 'executed_welded_assembly.py', label + '/executed_welded_assembly.py', r['weldedAssemblyHelperSha256'])
    summary = {'case': label, 'frames': len(r['frames']), 'dataSha256': r['dataSha256'],
               'actualSolverVertices': r['assembly']['actualVertices'],
               'sequenceMaximumSeamGapMeters': max(f['maximumSeamGapMeters'] for f in r['frames']),
               'sequenceMaximumFullyPinnedInputError': max(f['maximumFullyPinnedInputError'] for f in r['frames']),
               'mass': r.get('massCalibration', {'mode': 'inherited', 'actualMassPerVertexKg': r['actualSolverSettings']['mass'],
                       'actualTotalMassKg': r['actualSolverSettings']['mass'] * r['assembly']['actualVertices']}), 'pieces': {}}
    for key in ['ivory', 'support', 'tier1', 'tier2', 'tier3']:
        rows = [next(p for p in f['pieces'] if p['key'] == key) for f in r['frames']]
        summary['pieces'][key] = {'sequenceMaximumEdgeStretch': max(p['maximumEdgeStretch'] for p in rows),
                                  'sequenceMaximumEdgeStretch95Percentile': max(p['edgeStretch95Percentile'] for p in rows),
                                  'lastFrameMaximumEdgeStretch': rows[-1]['maximumEdgeStretch']}
    cases.append(summary)
    if version != 2:
        review = read(folder / 'actual_receiver_review/comparison.json')
        assert review['probeDataSha256'] == r['dataSha256'] and review['sourcePhotoSha256'] == r['sourcePhotoSha256']
        assert review['checkpointUnchanged'] and review['parentGlbUnchanged'] and len(review['renders']) == 4
        for flag in ['allLayersFinished', 'fidelityVerified', 'motionVerified', 'clothCollisionVerified', 'finalFbxExported']:
            assert review[flag] is False
        log = (folder / 'actual_receiver_review.log').read_text(encoding='utf-8')
        assert 'Target vertices changed' not in log
        copy(folder / 'actual_receiver_review/comparison.json', label + '/review/comparison.json')
        copy(folder / 'actual_receiver_review/executed_render.py', label + '/review/executed_render.py', review['scriptSha256'])
        copy(folder / 'actual_receiver_review.log', label + '/review/actual_execution.log')
        for row in review['renders']:
            assert row['actualStableLaceTargetVertices'] == [2496] * 3 and row['actualLaceBindingsPresent']
            copy(row['file'], label + '/review/renders/' + Path(row['file']).name, row['sha256'])
        reviews.append(review)

unchanged = ['rest_points', 'edges', 'loose_edges', 'pin_weights', 'bone_names', 'rig_deformations', 'actual_skin_targets']
for key in unchanged: assert np.array_equal(arrays[0][key], arrays[1][key]), key
settings_delta = {k: [reports[0]['actualSolverSettings'][k], reports[1]['actualSolverSettings'][k]]
                  for k in reports[0]['actualSolverSettings'] if reports[0]['actualSolverSettings'][k] != reports[1]['actualSolverSettings'][k]}
assert set(settings_delta) == {'mass'}, settings_delta
assert reports[0]['actualCollisionSettings'] == reports[1]['actualCollisionSettings']
assert np.array_equal(arrays[1]['rig_deformations'], arrays[2]['rig_deformations'])
assert np.array_equal(arrays[2]['points'], arrays[2]['actual_simulation_points'][:, arrays[2]['logical_vertex_to_simulation_vertex']])
assert cases[2]['sequenceMaximumSeamGapMeters'] == 0
assert reports[2]['assembly']['actualWeldedSeamPairs'] == 576
for name, field in [('chapeleiro_shared_rig_fields.py', 'fieldHelperSha256'), ('chapeleiro_cloth_motion_entry.py', 'entryHelperSha256'),
                    ('chapeleiro_cloth_colliders.py', 'colliderHelperSha256')]:
    assert len({r[field] for r in reports}) == 1
    copy(repo / 'blender' / name, 'executed_helpers/' + name, reports[2][field])
for version, files in [(1, ['executed_failed_probe.py', 'executed_assembly.py']),
                       (4, ['executed_failed_probe.py', 'executed_assembly.py', 'executed_failed_welded_assembly.py'])]:
    folder = base / f'sewn_ivory_black_cloth_v{version:03d}'
    for name in files: copy(folder / name, 'initialization_failures/v' + str(version) + '/' + name)
    copy(base / (folder.name + '.log'), 'initialization_failures/v' + str(version) + '/actual_execution.log')
copy(g['exports']['foundation']['sourcePhoto'], 'source_photo.png', g['exports']['foundation']['sourcePhotoSha256'])
assessment = read(a.review)
assert assessment['actuallyViewedAllEightRenders'] is True
copy(a.review, 'visual_assessment.json')
localization = read(base / 'sewn_ivory_black_cloth_v005/strain_localization.json')
assert localization['probeDataSha256'] == reports[2]['dataSha256']
copy(base / 'sewn_ivory_black_cloth_v005/strain_localization.json', 'areal_mass_welded/strain_localization.json')
copy(Path(__file__).with_name('analyze_chapeleiro_sewn_strain.py'), 'executed_strain_analysis.py', localization['scriptSha256'])
board = Image.new('RGB', (1760, 2350), (24, 26, 29))
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
draw.text((24, 20), 'CHAPELEIRO / COSTURAS DAS CAMADAS INFERIORES / EM REFINAMENTO', font=font, fill='white')
photo = Image.open(g['exports']['foundation']['sourcePhoto']).convert('RGB')
photo.thumbnail((510, 1000))
board.paste(photo, (24, 95))
draw.text((24, 760), 'Foto original completa / etapa 01', font=small, fill='#e3d3b4')
for line, y in zip(['Mesma foto, rig e câmeras.', 'Antes: raízes afastam-se do suporte.', 'Depois: pontos da costura unidos.', 'As dobras e a renda exigem revisão.', 'Outros adornos seguem o rig anterior.', 'Este ensaio não altera o GLB do site.', 'Sem aprovação final ou FBX.'], range(830, 1200, 45)):
    draw.text((24, y), line, font=small, fill='#e3d3b4')
draw.text((580, 70), 'Antes / raízes separadas', font=font, fill='white')
draw.text((1160, 70), 'Depois / raízes unidas', font=font, fill='white')
for i in range(3):
    before, after = reviews[0]['renders'][i], reviews[1]['renders'][i]
    assert (before['sourcePhysicsFrame'], before['view'], before['scope']) == (after['sourcePhysicsFrame'], after['view'], after['scope'])
    assert max(abs(x - y) for x, y in zip(before['cameraPosition'], after['cameraPosition'])) < 1e-5
    for row, x in [(before, 580), (after, 1160)]:
        im = Image.open(row['file']).convert('RGBA')
        im.thumbnail((530, 670))
        y = 115 + i * 720
        board.paste(im, (x, y), im)
        draw.text((x, y + 675), f"Pose {row['sourcePhysicsFrame']} / {row['view']}", font=small, fill='white')
draw.text((24, 2310), 'Costura unida no solver não aprova forma, renda, colisões ou animações. O vestido exterior permanece inteiro.', font=small, fill='#e3d3b4')
file = base / 'photo_vs_actual_sewn_cloth_before_after.jpg'
board.save(file, quality=95)
copy(file, file.name)
copy(__file__, 'executed_package.py')
write(out / 'controls.json', {'cases': cases, 'massControlExactUnchangedFields': unchanged,
      'massControlSolverSettingsDelta': settings_delta, 'massControlCollisionSettingsIdentical': True,
      'weldedControlSameRigMatrices': True, 'logicalToActualSolverMappingVerified': True,
      'weldingChangedOnlyIndependentSimulationMesh': True,
      'fullLocalEditable': {'file': g['editableBlend'], 'bytes': Path(g['editableBlend']).stat().st_size, 'sha256': g['editableBlendSha256']},
      'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'],
      'parentGlbSha256': g['exports']['foundation']['modelSha256'], 'responseBakedIntoGlb': False,
      'allLayersFinished': False, 'fidelityVerified': False, 'clothCollisionVerified': False, 'motionVerified': False,
      'finalFbxExported': False, 'nextVariantMayStart': False, 'additionalTripoCreditsConsumed': 0})
write(out / 'artifact_inventory.json', {'artifacts': inventory, 'preservedExactlyAsExecutedBytes': True})
(out / '.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n', encoding='utf-8', newline='\n')
(out / 'README.md').write_text('''# Chapeleiro — costuras das camadas inferiores em refinamento

Três ensaios reais de 29 poses reúnem a anágua clara, o suporte preto e três babados em um solver Cloth com colisões das meias e bloomers e autocontato das camadas. A [foto completa da própria etapa](source_photo.png) acompanha [as vistas reais antes/depois](photo_vs_actual_sewn_cloth_before_after.jpg). O resultado ainda requer refinamento e não foi incorporado ao GLB publicado.

No primeiro ensaio, a massa herdada era 0,12 kg por vértice: 2.649,6 kg nos 22.080 vértices do solver. A descrição da propriedade no Blender instalado e o [código primário do Blender](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/cloth.cc) confirmam essa semântica. O segundo ensaio calcula a massa pela área de repouso medida. A densidade de 0,18 kg/m² é uma hipótese provisória; a massa uniforme por vértice não representa exatamente a mesma densidade em regiões com amostragem diferente. Geometria de repouso, pin, entradas do rig, colisões e outros parâmetros são exatamente iguais entre esses dois controles. A massa foi o único parâmetro físico alterado, e corrigir a massa não resolveu a abertura das costuras.

No terceiro ensaio, 576 pares de raiz/suporte são unidos somente na malha independente de simulação. Há 21.504 vértices físicos e 22.080 posições lógicas para reconstruir os receptores originais. A costura tem afastamento zero nas 29 poses, por construção; isso não aprova a forma, dobras, renda, colisões ou movimento. O vestido exterior, os modelos publicados e o checkpoint completo permanecem intactos.

Os oito renders passam pelos receptores reais, pela renda original vinculada a alvos finos estáveis e pela espessura/UV do Bystedt. As outras 221 superfícies da fundação permanecem como contexto animado pelo rig anterior. Elas não receberam aprovação física neste ensaio. Consulte [a avaliação visual](visual_assessment.json), [as medições por peça](controls.json) e [os dados e hashes preservados](artifact_inventory.json).

As falhas de inicialização foram arquivadas com seus programas e logs. Não há créditos Tripo adicionais, FBX final ou início de outra variante. O refinamento da Chapeleiro continua antes da próxima Alice.
''', encoding='utf-8', newline='\n')
print('ACTUAL_SEWN_CLOTH_REVIEW_PACKAGED', len(inventory))
