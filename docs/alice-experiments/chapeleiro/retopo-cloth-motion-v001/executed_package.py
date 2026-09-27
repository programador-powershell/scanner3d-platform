"""Archive executed cloth controls, exact photo and actual visual comparisons."""
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
out = repo / 'docs/alice-experiments/chapeleiro/retopo-cloth-motion-v001'
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
def generated(file):
    inventory.append({'file': file.relative_to(out).as_posix(), 'sha256': sha(file), 'bytes': file.stat().st_size})

g = read(base / 'foundation_shared_rig_v094/generation.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert Path(g['editableBlend']).stat().st_size > 100 * 1024 * 1024
reports, arrays, reviews = {}, {}, {}
labels = {1: 'regular_inward', 2: 'smooth_detail_same_physics', 3: 'stiffness_control',
          5: 'regular_outward_quality12'}
cases = []
for version, label in labels.items():
    folder = base / f'retopo_ivory_black_cloth_v{version:03d}'
    r = reports[version] = read(folder / 'actual_sewn_solver_motion.json')
    arrays[version] = np.load(r['dataFile'])
    assert r['parentEditableSha256'] == g['editableBlendSha256'] and r['parentEditableUnchanged'] and r['exportedModelUnchanged']
    assert [f['frame'] for f in r['frames']] == list(range(1, 30))
    assert not any(f['cacheOutdated'] for f in r['frames'])
    for flag in ['allLayersFinished', 'fidelityVerified', 'motionVerified', 'clothCollisionVerified', 'finalFbxExported', 'modelExported', 'responseBakedIntoRig']:
        assert r[flag] is False
    copy(folder / 'actual_sewn_solver_motion.json', label + '/actual_sewn_solver_motion.json')
    copy(r['dataFile'], label + '/actual_cloth_frames.npz', r['dataSha256'])
    copy(folder / 'executed_retopo_assembly.py', label + '/executed_retopo_assembly.py', r['retopoAssemblyHelperSha256'])
    if version == 2:
        copy(folder / 'executed_refinement.py', label + '/executed_refinement.py', r['scriptSha256'])
    else:
        copy(folder / 'executed_probe.py', label + '/executed_probe.py', r['scriptSha256'])
        copy(folder / 'executed_assembly.py', label + '/executed_assembly.py', r['assemblyHelperSha256'])
        copy(folder / 'mass_calibration.json', label + '/mass_calibration.json')
        copy(base / (folder.name + '.log'), label + '/actual_execution.log')
    review = reviews[version] = read(folder / 'actual_receiver_review/comparison.json')
    assert review['probeDataSha256'] == r['dataSha256'] and review['sourcePhotoSha256'] == r['sourcePhotoSha256']
    assert review['checkpointUnchanged'] and review['parentGlbUnchanged']
    assert len(review['renders']) == (4 if version in [1, 2] else 2)
    copy(folder / 'actual_receiver_review/comparison.json', label + '/review/comparison.json')
    copy(folder / 'actual_receiver_review/executed_render.py', label + '/review/executed_render.py', review['scriptSha256'])
    copy(folder / 'actual_receiver_review.log', label + '/review/actual_execution.log')
    assert 'Target vertices changed' not in (folder / 'actual_receiver_review.log').read_text(encoding='utf-8')
    for row in review['renders']:
        copy(row['file'], label + '/review/renders/' + Path(row['file']).name, row['sha256'])
    cases.append({'case': label, 'version': version, 'frames': 29, 'physicalVertices': r['assembly']['actualVertices'],
                  'physicalFaces': r['assembly']['actualFaces'], 'solverQuality': r['actualSolverSettings']['quality'],
                  'dataSha256': r['dataSha256'], 'physicalSolverReexecuted': version != 2,
                  'pieces': {key: {field: max(next(p for p in f['pieces'] if p['key'] == key)[field] for f in r['frames'])
                                   for field in ['solverMaximumEdgeStretch', 'solverEdgeStretch95Percentile', 'maximumEdgeStretch', 'edgeStretch95Percentile']}
                             for key in ['ivory', 'support', 'tier1', 'tier2', 'tier3']}})

physical_fields = reports[2]['exactPreservedPhysicalArrays']
for key in physical_fields: assert np.array_equal(arrays[1][key], arrays[2][key]), key
fixed_fields = ['simulation_rest_points', 'simulation_pin_weights', 'physical_seam_pairs', 'rig_deformations', 'bone_names', 'actual_skin_targets']
for version in [3, 5]:
    for key in fixed_fields: assert np.array_equal(arrays[1][key], arrays[version][key]), (version, key)
assert np.array_equal(arrays[1]['simulation_faces'][:, [0, 3, 2, 1]], arrays[5]['simulation_faces'])
delta = lambda before, after: {k: [before['actualSolverSettings'][k], after['actualSolverSettings'][k]] for k in before['actualSolverSettings'] if before['actualSolverSettings'][k] != after['actualSolverSettings'][k]}
assert not delta(reports[1], reports[5])
stiffness_delta = delta(reports[1], reports[3])
assert set(stiffness_delta) == {'tension_stiffness', 'tension_stiffness_max', 'compression_stiffness', 'compression_stiffness_max', 'shear_stiffness', 'shear_stiffness_max'}
# RNA also raises *_max when the base is assigned. The executed v003 loop then
# scaled that raised maximum again. Record the actual values, not the intent.
assert all(after / before == (64 if k.endswith('_max') else 8) for k, (before, after) in stiffness_delta.items())
assert len({json.dumps(r['actualCollisionSettings'], sort_keys=True) for r in reports.values()}) == 1
assert len({json.dumps(r['actualColliders'], sort_keys=True) for r in reports.values()}) == 1

for version, relative, raw, dataset in [(1, 'rest_contact_inspection', 'rest_contact_inspection.json', None),
                                      (5, 'closed_rest_clearance_inspection', 'rest_clearance_inspection.json', 'actual_rest_inside_masks.npz'),
                                      (5, 'rest_intersection_inspection', 'rest_intersection_inspection.json', 'actual_rest_triangle_crossings.npz'),
                                      (5, 'dynamic_clearance_inspection', 'dynamic_clearance_inspection.json', 'actual_dynamic_clearance.npz')]:
    folder = base / f'retopo_ivory_black_cloth_v{version:03d}' / relative
    r = read(folder / raw)
    copy(folder / raw, labels[version] + '/' + relative + '/' + raw)
    copy(folder / 'executed_inspection.py', labels[version] + '/' + relative + '/executed_inspection.py', r['scriptSha256'])
    if dataset:
        copy(folder / dataset, labels[version] + '/' + relative + '/' + dataset, r.get('dataSha256', r.get('rawInsideMasksSha256')))
        if 'closedProxyHelperSha256' in r:
            copy(folder / 'executed_closed_proxy_helper.py', labels[version] + '/' + relative + '/executed_closed_proxy_helper.py', r['closedProxyHelperSha256'])
    copy(folder.parent / (relative + '.log'), labels[version] + '/' + relative + '/actual_execution.log')
for name, field in [('chapeleiro_shared_rig_fields.py', 'fieldHelperSha256'), ('chapeleiro_cloth_motion_entry.py', 'entryHelperSha256'), ('chapeleiro_cloth_colliders.py', 'colliderHelperSha256')]:
    assert len({r[field] for r in reports.values()}) == 1
    copy(repo / 'blender' / name, 'executed_helpers/' + name, reports[5][field])
stopped_folder = base / 'retopo_ivory_black_cloth_v006'
stopped = read(stopped_folder / 'stopped_execution.json')
assert stopped['completed'] is False and stopped['stoppedDueToMeasuredDivergence']
assert stopped['lastCompletedFrameInPreservedProgress'] == 22
assert stopped['sequenceMeasuredMaximumPhysicalEdgeStretch'] > 8
copy(stopped_folder / 'stopped_execution.json', 'quality48_stopped/stopped_execution.json')
copy(stopped_folder / 'progress.json', 'quality48_stopped/progress.json', stopped['progressSha256'])
copy(stopped_folder / 'mass_calibration.json', 'quality48_stopped/mass_calibration.json')
for name, digest in stopped['executedSources'].items():
    copy(stopped_folder / name, 'quality48_stopped/' + name, digest)
copy(base / 'retopo_ivory_black_cloth_v006.log', 'quality48_stopped/actual_execution.log')
copy(g['exports']['foundation']['sourcePhoto'], 'source_photo.png', g['exports']['foundation']['sourcePhotoSha256'])
assessment = read(a.review)
assert assessment['actuallyViewedAllTwelveRenders'] and assessment['sourcePhotoSha256'] == g['exports']['foundation']['sourcePhotoSha256']
assert {row['sha256'] for review in reviews.values() for row in review['renders']} == set(assessment['viewedRenderSha256'])
copy(a.review, 'visual_assessment.json')

board = Image.new('RGB', (1740, 1660), (24, 26, 29))
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
draw.text((24, 20), 'CHAPELEIRO / MALHA DE SIMULAÇÃO E CONTATO / EM REFINAMENTO', font=font, fill='white')
photo = Image.open(out / 'source_photo.png').convert('RGB')
photo.thumbnail((510, 670))
board.paste(photo, (24, 90))
draw.text((24, 765), 'Foto original completa / etapa 01', font=small, fill='#e3d3b4')
for line, y in zip(assessment['boardNotesPortuguese'], range(835, 1400, 45)):
    draw.text((24, y), line, font=small, fill='#e3d3b4')
for version, x, title in [(1, 570, 'Faces para dentro / diagnóstico'), (5, 1150, 'Faces para fora / correção')]:
    draw.text((x, 70), title, font=font, fill='white')
    moving = [row for row in reviews[version]['renders'] if row['scope'] == 'foundation' and row['sourcePhysicsFrame'] != 1]
    for i, row in enumerate(moving):
        other = reviews[5]['renders'][i]
        assert (row['sourcePhysicsFrame'], row['view']) == (other['sourcePhysicsFrame'], other['view'])
        assert max(abs(x-y) for x,y in zip(row['cameraPosition'], other['cameraPosition'])) < 1e-5
        im = Image.open(row['file']).convert('RGBA')
        im.thumbnail((535, 680))
        y = 120 + i * 750
        board.paste(im, (x, y), im)
        draw.text((x, y + 685), f"Pose {row['sourcePhysicsFrame']} / {row['view']}", font=small, fill='white')
draw.text((24, 1615), 'Renders dos receptores reais. Ensaio incompleto; não incorporado ao GLB. Vestido exterior inteiro.', font=small, fill='#e3d3b4')
boardfile = out / 'photo_vs_actual_regular_cloth_contact.jpg'
board.save(boardfile, quality=95)
generated(boardfile)
controls = {'cases': cases, 'exactPreservedPhysicalArraysForDetailOnlyControl': physical_fields,
            'sameRestPinsRigAndBodyInputFields': fixed_fields, 'windingOnlyReversesIndependentFaces': True,
            'windingSolverSettingsIdentical': True, 'quality48ControlIncompleteAndStoppedAfterDivergence': True,
            'stiffnessActualSolverSettingsDelta': stiffness_delta,
            'stiffnessControlMaximumScaledTwiceByExecutedRnaDependentLoop': True,
            'closedRestLegacySharedMeshFlagIsStaleAfterCopy': True,
            'closedRestActualIndependentCopyAndUnchangedOriginalVerified': True,
            'allCollidersAndCollisionSettingsIdentical': True,
            'fullLocalEditable': {'file': g['editableBlend'], 'bytes': Path(g['editableBlend']).stat().st_size, 'sha256': g['editableBlendSha256']},
            'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'], 'parentGlbSha256': g['exports']['foundation']['modelSha256'],
            'allLayersFinished': False, 'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False,
            'responseBakedIntoGlb': False, 'finalFbxExported': False, 'nextVariantMayStart': False, 'additionalTripoCreditsConsumed': 0}
write(out / 'controls.json', controls); generated(out / 'controls.json')
copy(__file__, 'executed_package.py')
(out / '.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n', encoding='utf-8', newline='\n')
(out / 'README.md').write_text('''# Chapeleiro — malha de simulação e contato em refinamento

Os quatro controles completos usam a [foto completa da própria etapa](source_photo.png), o mesmo checkpoint e o rig existente. A malha independente de cálculo tem 8.736 vértices e 8.544 quads, com 288 pares de costura unidos em três anéis contínuos. Os detalhes dos receptores originais são reconstruídos por uma aproximação de coordenadas e referenciais tangentes; essa reconstrução exata em repouso não aprova o movimento. Nenhuma superfície visível ou vestido exterior foi recortado ou substituído.

Três controles executam Cloth por 29 poses; o controle de suavização reutiliza exatamente os dados físicos do primeiro e muda somente a transferência de detalhe. O teste de rigidez também está preservado: a atribuição do valor base no RNA aumenta automaticamente o máximo, e o programa executado voltou a multiplicar esse máximo. Os valores reais foram 8 vezes o base e 64 vezes o máximo. Esse resultado não é apresentado como uma comparação uniforme de fator 8. A orientação para fora altera somente a ordem dos vértices nas faces da malha independente. Um ensaio adicional solicitando 48 passos foi interrompido após a pose 22: as medições físicas chegaram a 8,4 vezes o comprimento das arestas em repouso. Seu progresso parcial, programas e log são preservados, sem alegação de trajetória completa ou render desse ensaio.

As inspeções de repouso e das 29 poses restauram os mesmos ossos e usam cópias das malhas finas reais de meias e bloomers. Tampas fecham os limites dessas cópias para consultas de volume e não alteram as roupas visíveis nem os coliders do solver. As consultas de dois raios distinguem resultados ambíguos; medem vértices dentro do volume e distância à superfície, não colisão contínua ou cruzamento de todas as faces. O relatório antigo de repouso conservou o campo `sharedActualMeshData: true` do helper original; o código executado e suas verificações mostram a cópia independente antes das tampas. As inspeções posteriores corrigem esse campo sem reescrever o relatório histórico.

A inspeção de repouso não encontrou cruzamentos interiores de triângulos não adjacentes, mas encontrou 192 arestas ligadas a três faces nas costuras. No [código primário consultado do Blender](https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/cloth.cc), a terceira face remove a mola de dobra angular naquela aresta. Esse é um candidato para investigar o vínculo das costuras; a medição ainda não prova que seja a causa da instabilidade na versão instalada. O contato medido na corrida com faces externas entra até 3,88 cm no volume dos bloomers, embora em repouso não haja vértices dentro dos três volumes.

Veja [foto e quatro renders reais](photo_vs_actual_regular_cloth_contact.jpg), [avaliação visual](visual_assessment.json), [valores medidos](controls.json) e [inventário com hashes](artifact_inventory.json). Os receptores incluem renda com alvo fino estável e espessura/UV do Bystedt. Outras 221 superfícies são contexto do rig anterior. Forma, franzidos, cascatas, corset, renda, contato e todos os movimentos ainda precisam de refinamento. Nenhum novo GLB ou FBX final foi publicado por este ensaio; não houve créditos Tripo adicionais ou início de outra variante.
''', encoding='utf-8', newline='\n')
generated(out / '.gitattributes'); generated(out / 'README.md')
write(out / 'artifact_inventory.json', {'artifacts': inventory, 'preservedExactlyAsExecutedBytes': True})
print('ACTUAL_RETOPO_CLOTH_REVIEW_PACKAGED', len(inventory))
