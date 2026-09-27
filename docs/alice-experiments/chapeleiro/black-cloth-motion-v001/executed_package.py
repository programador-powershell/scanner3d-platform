import hashlib, json, shutil
from pathlib import Path
import numpy as np
workspace = Path(__file__).resolve().parents[1]
repo = workspace / 'scanner3d-platform'
base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
root = base / 'foundation_shared_rig_v094'
out = repo / 'docs/alice-experiments/chapeleiro/black-cloth-motion-v001'
assert not out.exists()
out.mkdir(parents=True)
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
write = lambda f, r: Path(f).write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
inventory = []
def copy(file, relative, digest=None):
    file = Path(file)
    if digest: assert sha(file) == digest
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(file, target)
    assert sha(target) == sha(file)
    inventory.append({'file': str(Path(relative).as_posix()), 'sha256': sha(target), 'bytes': target.stat().st_size})
    return inventory[-1]
cases, arrays = [], []
for label, folder in [('with_ivory', 'black_cloth_family_ivory_collision_v001'), ('without_ivory_control', 'black_cloth_family_no_ivory_collision_v001')]:
    d = base / folder
    r = read(d / 'actual_black_family_solver_motion.json')
    assert sha(d / 'executed_probe.py') == r['scriptSha256']
    assert r['parentEditableUnchanged'] and r['clothNeverBypassedDuringSequence']
    arrays.append(np.load(r['dataFile']))
    for file, name, expected in [(d / 'executed_probe.py', 'executed_probe.py', r['scriptSha256']),
                                 (d / 'actual_black_family_solver_motion.json', 'actual_solver_motion.json', None),
                                 (Path(r['dataFile']), 'actual_cloth_frames.npz', r['dataSha256']),
                                 (base / (folder + '.log'), 'actual_execution.log', None)]:
        copy(file, label + '/' + name, expected)
    summary = {'case': label, 'dataSha256': r['dataSha256'], 'frames': len(r['frames']), 'pieces': {}}
    for key in ['support', 'tier1', 'tier2', 'tier3']:
        rows = [next(p for p in f['pieces'] if p['key'] == key) for f in r['frames']]
        summary['pieces'][key] = {'sequenceMaximumEdgeStretch': max(p['maximumEdgeStretch'] for p in rows),
                                  'lastFrameMaximumEdgeStretch': rows[-1]['maximumEdgeStretch'],
                                  'sequenceMaximumFullyPinnedInputError': max(p['maximumFullyPinnedInputError'] for p in rows)}
    cases.append(summary)
for key in ['rig_deformations', 'bone_names', 'support_inputs'] + [k + suffix for k in ['support', 'tier1', 'tier2', 'tier3'] for suffix in ['_rest_points', '_pin_weights', '_edges']]:
    assert np.array_equal(arrays[0][key], arrays[1][key]), key
inspection = read(root / 'actual_black_cloth_supports.json')
copy(root / 'actual_black_cloth_supports.json', 'actual_authored_black_supports.json')
copy(repo / 'blender/inspect_chapeleiro_black_cloth_supports.py', 'executed_inspection.py', inspection['scriptSha256'])
for name, field in [('chapeleiro_shared_rig_fields.py', 'fieldHelperSha256'), ('chapeleiro_cloth_colliders.py', 'colliderHelperSha256')]:
    copy(repo / 'blender' / name, 'executed_' + name, r[field])
g = read(root / 'generation.json')
copy(g['exports']['foundation']['sourcePhoto'], 'source_photo.png', g['exports']['foundation']['sourcePhotoSha256'])
bad = base / 'black_cloth_family_ivory_collision_v001/actual_receiver_review'
comparison = read(bad / 'comparison.json')
copy(bad / 'executed_render.py', 'rejected_thickness_target/executed_render.py', comparison['scriptSha256'])
for name in ['comparison.json', 'visual_failure.json']:
    copy(bad / name, 'rejected_thickness_target/' + name)
copy(bad.parent / 'actual_receiver_review.log', 'rejected_thickness_target/actual_execution.log')
for row in comparison['renders']:
    copy(row['file'], 'rejected_thickness_target/renders/' + Path(row['file']).name, row['sha256'])
copy(__file__, 'executed_package.py')
write(out / 'controls.json', {'cases': cases, 'sameRigMatricesRestGeometryPinFieldsAndMainSkinInputs': True,
      'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'], 'parentEditableSha256': g['editableBlendSha256'],
      'stableLaceTargetReviewPending': True, 'responseBakedIntoGlb': False, 'allLayersFinished': False,
      'fidelityVerified': False, 'clothCollisionVerified': False, 'motionVerified': False, 'nextVariantMayStart': False})
write(out / 'artifact_inventory.json', {'artifacts': inventory, 'preservedExactlyAsExecutedBytes': True})
(out / '.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n', encoding='utf-8', newline='\n')
(out / 'README.md').write_text('''# Saia preta — controles físicos locais em refinamento

Dois ensaios reais de 29 poses usam cópias independentes do suporte preto e dos três babados originais, com o rig atual e colisores das meias e bloomers. Um ensaio acrescenta a superfície animada da anágua. Matrizes do rig, geometria de repouso, campos de pin e entrada do suporte principal são exatamente iguais entre os controles.

Os babados continuam instáveis nos dois casos. O ensaio com a anágua chega a 14,58 vezes de esticamento em alguma aresta da sequência; o controle sem anágua chega a 23,38 vezes. Retirar a anágua melhora o suporte principal na última pose, mas não valida o sistema. Consulte [as medições por peça](controls.json), incluindo máximos de toda a sequência.

Os primeiros renders foram rejeitados: a espessura procedural altera a quantidade de vértices de alguns babados e invalida o vínculo Surface Deform da renda. Os avisos do Blender, fotos e renders foram preservados em `rejected_thickness_target/`. O vínculo deve usar uma superfície fina com topologia estável antes da espessura e UV. A [foto completa](source_photo.png) é a própria referência das camadas inferiores.

Estes controles não foram incorporados ao GLB publicado. Não há novo crédito Tripo, FBX final, aprovação de movimento ou de colisão, nem autorização para começar a próxima variante. [Dados e hashes](artifact_inventory.json).
''', encoding='utf-8', newline='\n')
print('ACTUAL_BLACK_CLOTH_CONTROLS_PACKAGED', len(inventory))
