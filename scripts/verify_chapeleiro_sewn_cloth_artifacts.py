"""Verify exact archived controls, original photo and logical sewn mappings."""
import argparse, hashlib, json, subprocess
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', required=True)
p.add_argument('--indexed', action='store_true')
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
root = Path(a.root).resolve()
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
inventory = read(root / 'artifact_inventory.json')
assert inventory['preservedExactlyAsExecutedBytes']
for row in inventory['artifacts']:
    file = root / row['file']
    assert file.stat().st_size == row['bytes'] and sha(file) == row['sha256'], str(file)
    if a.indexed:
        raw = subprocess.check_output(['git', 'show', ':' + file.relative_to(repo).as_posix()], cwd=repo)
        assert hashlib.sha256(raw).hexdigest() == row['sha256'], 'Indexed bytes changed: ' + str(file)
controls = read(root / 'controls.json')
assert sha(root / 'source_photo.png') == controls['sourcePhotoSha256']
checkpoint = controls['fullLocalEditable']
assert Path(checkpoint['file']).stat().st_size == checkpoint['bytes'] > 100 * 1024 * 1024
assert sha(checkpoint['file']) == checkpoint['sha256']
for flag in ['allLayersFinished', 'fidelityVerified', 'clothCollisionVerified', 'motionVerified',
             'finalFbxExported', 'nextVariantMayStart', 'responseBakedIntoGlb']:
    assert controls[flag] is False, flag
assert controls['additionalTripoCreditsConsumed'] == 0
arrays, reports = [], []
for label in ['inherited_mass_springs', 'areal_mass_springs', 'areal_mass_welded']:
    folder = root / label
    r = read(folder / 'actual_sewn_solver_motion.json')
    assert r['parentEditableSha256'] == checkpoint['sha256']
    assert r['sourcePhotoSha256'] == controls['sourcePhotoSha256']
    assert sha(folder / 'actual_cloth_frames.npz') == r['dataSha256']
    assert sha(folder / 'executed_probe.py') == r['scriptSha256']
    assert sha(folder / 'executed_assembly.py') == r['assemblyHelperSha256']
    assert r['clothNeverBypassedDuringSequence'] and r['parentEditableUnchanged'] and r['exportedModelUnchanged']
    assert [f['frame'] for f in r['frames']] == list(range(1, 30))
    assert not any(f['cacheOutdated'] for f in r['frames'])
    arrays.append(np.load(folder / 'actual_cloth_frames.npz'))
    reports.append(r)
    if label != 'inherited_mass_springs':
        review = read(folder / 'review/comparison.json')
        assert review['probeDataSha256'] == r['dataSha256'] and review['sourcePhotoSha256'] == controls['sourcePhotoSha256']
        assert review['checkpointUnchanged'] and review['parentGlbUnchanged']
        assert sha(folder / 'review/executed_render.py') == review['scriptSha256']
        assert 'Target vertices changed' not in (folder / 'review/actual_execution.log').read_text(encoding='utf-8')
        for row in review['renders']:
            assert sha(folder / 'review/renders' / Path(row['file']).name) == row['sha256']
            assert row['actualStableLaceTargetVertices'] == [2496] * 3 and row['actualLaceBindingsPresent']
            assert row['recordedRigMatrixMaximumError'] < 1e-5
            assert max(row['sourceReconstructionMaximumErrors'].values()) < 1e-6
for key in controls['massControlExactUnchangedFields']:
    assert np.array_equal(arrays[0][key], arrays[1][key]), key
delta = {key for key in reports[0]['actualSolverSettings']
         if reports[0]['actualSolverSettings'][key] != reports[1]['actualSolverSettings'][key]}
assert delta == {'mass'} and reports[0]['actualCollisionSettings'] == reports[1]['actualCollisionSettings']
assert np.array_equal(arrays[1]['rig_deformations'], arrays[2]['rig_deformations'])
assert np.array_equal(arrays[2]['points'], arrays[2]['actual_simulation_points'][:, arrays[2]['logical_vertex_to_simulation_vertex']])
edges = arrays[2]['edges'][arrays[2]['loose_edges']]
assert len(edges) == 576
assert np.array_equal(arrays[2]['points'][:, edges[:, 0]], arrays[2]['points'][:, edges[:, 1]])
assert all(f['maximumSeamGapMeters'] == 0 for f in reports[2]['frames'])
assert reports[2]['assembly']['actualVertices'] == 21504
assert reports[2]['actualSolverSettings']['use_sewing_springs'] is False
assert sha(root / 'areal_mass_welded/executed_welded_assembly.py') == reports[2]['weldedAssemblyHelperSha256']
print('ACTUAL_SEWN_CLOTH_ARTIFACTS_VERIFIED', len(inventory['artifacts']), 'indexed' if a.indexed else 'local')
