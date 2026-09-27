"""Append the installed RNA check without rewriting archived executed controls."""
import hashlib, json, shutil
from pathlib import Path
workspace = Path(__file__).resolve().parents[1]
root = workspace / 'scanner3d-platform/docs/alice-experiments/chapeleiro/retopo-cloth-motion-v001'
source = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/retopo_ivory_black_cloth_v005/stiffness_assignment_check')
target = root / 'corrected_stiffness_assignment'
assert not target.exists()
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
r = read(source / 'actual_assignment.json')
assert r['allSixActualRnaFieldsScaledExactlyOnce'] and r['checkpointUnchanged']
assert not r['clothSimulationExecuted']
assert sha(source / 'executed_check.py') == r['scriptSha256']
assert sha(source / 'executed_helper.py') == r['helperSha256']
inventory = read(root / 'artifact_inventory.json')
target.mkdir()
for file in [source / 'actual_assignment.json', source / 'executed_check.py', source / 'executed_helper.py', source.parent / 'stiffness_assignment_check.log']:
    dest = target / file.name
    shutil.copyfile(file, dest)
    inventory['artifacts'].append({'file': dest.relative_to(root).as_posix(), 'sha256': sha(dest), 'bytes': dest.stat().st_size})
dest = root / 'executed_append_assignment_check.py'
shutil.copyfile(__file__, dest)
inventory['artifacts'].append({'file': dest.name, 'sha256': sha(dest), 'bytes': dest.stat().st_size})
readme = root / 'README.md'
with readme.open('a', encoding='utf-8', newline='\n') as file:
    file.write('\nA atribuição de rigidez foi corrigida no helper atual. A [verificação no Blender instalado](corrected_stiffness_assignment/actual_assignment.json) lê os seis campos reais e confirma fator 8 uma única vez: tensão/compressão e seus máximos ficam em 280; cisalhamento e máximo ficam em 96. Esse teste não executa Cloth nem aprova material ou animação. Os controles anteriores continuam preservados com o código e os valores que efetivamente executaram.\n')
for row in inventory['artifacts']:
    if row['file'] == 'README.md': row.update(sha256=sha(readme), bytes=readme.stat().st_size)
(root / 'artifact_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('ACTUAL_RETOPO_ASSIGNMENT_CHECK_APPENDED', len(inventory['artifacts']))
