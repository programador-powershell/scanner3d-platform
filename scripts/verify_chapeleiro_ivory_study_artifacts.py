"""Check preserved masters and exact bytes of the unfinished Ivory study."""
import argparse, hashlib, json, subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', required=True)
p.add_argument('--indexed', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
workspace = repo.parent
root = Path(a.root).resolve()
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
protected = {
    repo / 'data/assets/alice-detail.glb': '27200e6ea06b7940aa21ae86a18e6ad7442f1ff844add0cf0e471336cfa48c05',
    workspace / 'project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb': '84e27a46ecc472db6f3d5345dbf1c6d2164c5830c6bd6104cfb919fd10bc4943',
    workspace / 'project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.blend': 'ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9',
    workspace / 'project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.glb': 'd8ae24de525947e104218c5e518e217535b2c8bc0ce452338590ba738abea2e1',
    workspace / 'project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.blend': '55ae0b5e32aa7b6374d02e82752e7a21893bc95bc480397f56172ad9236e9fbd',
}
for file, digest in protected.items(): assert sha(file) == digest, str(file)
checkpoint = read(root / 'checkpoint.json')
editable = checkpoint['fullLocalEditable']
assert Path(editable['file']).stat().st_size == editable['bytes'] > 100 * 1024 * 1024
assert sha(editable['file']) == editable['sha256']
for flag in ['allLayersFinished', 'fidelityVerified', 'motionVerified', 'clothCollisionVerified', 'finalFbxExported', 'nextVariantMayStart']:
    assert checkpoint[flag] is False, flag
inventory = read(root / 'artifact_inventory.json')['artifacts']
for row in inventory:
    file = root / row['file']
    assert file.stat().st_size == row['bytes'] and sha(file) == row['sha256'], str(file)
    if a.indexed:
        relative = file.relative_to(repo).as_posix()
        raw = subprocess.check_output(['git', 'show', ':' + relative], cwd=repo)
        assert hashlib.sha256(raw).hexdigest() == row['sha256'], 'Indexed byte change: ' + relative
print('ACTUAL_IVORY_STUDY_ARTIFACTS_VERIFIED', len(protected), len(inventory), 'indexed' if a.indexed else 'local')
