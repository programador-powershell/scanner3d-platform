"""Verify exact executed controls, original photo, actual poses and proxy data."""
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
for flag in ['allLayersFinished', 'fidelityVerified', 'clothCollisionVerified', 'motionVerified', 'finalFbxExported', 'nextVariantMayStart', 'responseBakedIntoGlb']:
    assert controls[flag] is False
assert controls['additionalTripoCreditsConsumed'] == 0
labels = ['regular_inward', 'smooth_detail_same_physics', 'stiffness_control', 'regular_outward_quality12']
reports, arrays, rendered_hashes = {}, {}, set()
for label in labels:
    folder = root / label
    r = reports[label] = read(folder / 'actual_sewn_solver_motion.json')
    assert r['parentEditableSha256'] == checkpoint['sha256'] and r['sourcePhotoSha256'] == controls['sourcePhotoSha256']
    assert sha(folder / 'actual_cloth_frames.npz') == r['dataSha256']
    script = 'executed_refinement.py' if label == 'smooth_detail_same_physics' else 'executed_probe.py'
    assert sha(folder / script) == r['scriptSha256']
    assert sha(folder / 'executed_retopo_assembly.py') == r['retopoAssemblyHelperSha256']
    if label != 'smooth_detail_same_physics':
        assert sha(folder / 'executed_assembly.py') == r['assemblyHelperSha256']
    assert r['clothNeverBypassedDuringSequence'] and r['parentEditableUnchanged'] and r['exportedModelUnchanged']
    assert [f['frame'] for f in r['frames']] == list(range(1, 30))
    assert not any(f['cacheOutdated'] for f in r['frames'])
    d = arrays[label] = np.load(folder / 'actual_cloth_frames.npz')
    assert d['actual_simulation_points'].shape == (29, 8736, 3)
    assert d['simulation_faces'].shape == (8544, 4)
    assert d['points'].shape == (29, 22080, 3) and np.isfinite(d['points']).all()
    assert np.array_equal(d['actual_simulation_points'][:, d['physical_seam_pairs'][:, 0]], d['actual_simulation_points'][:, d['physical_seam_pairs'][:, 1]])
    assert r['restDetailReconstructionMaximumError'] < 1e-6
    review = read(folder / 'review/comparison.json')
    assert review['probeDataSha256'] == r['dataSha256'] and review['sourcePhotoSha256'] == controls['sourcePhotoSha256']
    assert review['checkpointUnchanged'] and review['parentGlbUnchanged'] and review['responseBakedIntoGlb'] is False
    assert sha(folder / 'review/executed_render.py') == review['scriptSha256']
    assert 'Target vertices changed' not in (folder / 'review/actual_execution.log').read_text(encoding='utf-8')
    for row in review['renders']:
        assert sha(folder / 'review/renders' / Path(row['file']).name) == row['sha256']
        assert row['actualStableLaceTargetVertices'] == [2496] * 3 and row['actualLaceBindingsPresent']
        assert row['recordedRigMatrixMaximumError'] < 1e-5
        assert max(row['sourceReconstructionMaximumErrors'].values()) < 1e-6
        rendered_hashes.add(row['sha256'])
before, smooth = arrays[labels[0]], arrays[labels[1]]
for key in controls['exactPreservedPhysicalArraysForDetailOnlyControl']:
    assert np.array_equal(before[key], smooth[key]), key
for label in labels[2:]:
    for key in controls['sameRestPinsRigAndBodyInputFields']:
        assert np.array_equal(before[key], arrays[label][key]), (label, key)
outward = arrays[labels[3]]
assert np.array_equal(before['simulation_faces'][:, [0, 3, 2, 1]], outward['simulation_faces'])
def delta(first, second):
    return {k: [first['actualSolverSettings'][k], second['actualSolverSettings'][k]] for k in first['actualSolverSettings'] if first['actualSolverSettings'][k] != second['actualSolverSettings'][k]}
assert not delta(reports[labels[0]], reports[labels[3]])
stiffness = delta(reports[labels[0]], reports[labels[2]])
assert stiffness == controls['stiffnessActualSolverSettingsDelta']
assert all(new / old == (64 if k.endswith('_max') else 8) for k, (old, new) in stiffness.items())
assert len({json.dumps(r['actualCollisionSettings'], sort_keys=True) for r in reports.values()}) == 1
assert len({json.dumps(r['actualColliders'], sort_keys=True) for r in reports.values()}) == 1
for label in labels[3:]:
    folder = root / label / 'dynamic_clearance_inspection'
    r = read(folder / 'dynamic_clearance_inspection.json')
    assert r['sourcePhysicalDataSha256'] == reports[label]['dataSha256']
    assert sha(folder / 'actual_dynamic_clearance.npz') == r['dataSha256']
    assert sha(folder / 'executed_inspection.py') == r['scriptSha256']
    assert sha(folder / 'executed_closed_proxy_helper.py') == r['closedProxyHelperSha256']
    assert r['parentEditableUnchanged'] and r['parentGlbUnchanged']
    assert len(r['frames']) == 29
    assert all(f['recordedRigMatrixMaximumError'] < 1e-5 for f in r['frames'])
    assert all(p['closedIndependentProxy'] and p['boundaryEdgesAfter'] == 0 and not p['sharedActualMeshData'] for p in r['actualClosedProxies'])
    d = np.load(folder / 'actual_dynamic_clearance.npz')
    masks = d['certain_inside_masks']
    assert masks.shape == (29, 3, 8736) and not np.any(masks & ~d['two_ray_agreements'])
    for frame in range(29):
        for proxy in range(3):
            row = r['frames'][frame]['proxies'][proxy]
            assert int(masks[frame, proxy].sum()) == row['certainInsideVertices']
            penetration = d['nearest_distances'][frame, proxy][masks[frame, proxy]]
            assert (float(penetration.max()) if len(penetration) else 0.) == row['maximumCertainPenetrationMeters']
rest = read(root / labels[3] / 'closed_rest_clearance_inspection/rest_clearance_inspection.json')
assert all(p['verticesInsideClosedProxy'] == 0 for p in rest['actualClosedProxyRestInspection'])
crossings = read(root / labels[3] / 'rest_intersection_inspection/rest_intersection_inspection.json')
assert crossings['actualEdgesWithMoreThanTwoFaces'] == 192
assert crossings['properRestEdgeFaceCrossings'] == 0 and crossings['nonAdjacentBroadPhasePairs'] == 0
assessment = read(root / 'visual_assessment.json')
assert assessment['actuallyViewedAllTwelveRenders'] and rendered_hashes == set(assessment['viewedRenderSha256'])
stopped = read(root / 'quality48_stopped/stopped_execution.json')
assert stopped['completed'] is False and stopped['stoppedDueToMeasuredDivergence']
assert stopped['lastCompletedFrameInPreservedProgress'] == 22
assert stopped['sequenceMeasuredMaximumPhysicalEdgeStretch'] > 8
assert sha(root / 'quality48_stopped/progress.json') == stopped['progressSha256']
assert not stopped['actualCompletedTrajectoryFileExists'] and stopped['noRenderedQuality48ComparisonExists']
for name, digest in stopped['executedSources'].items():
    assert sha(root / 'quality48_stopped' / name) == digest
assignment = read(root / 'corrected_stiffness_assignment/actual_assignment.json')
assert assignment['checkpointUnchanged'] and assignment['allSixActualRnaFieldsScaledExactlyOnce']
assert assignment['parentEditableSha256'] == checkpoint['sha256']
assert assignment['clothSimulationExecuted'] is False
assert all(assignment['actualAfter'][k] / value == 8 for k, value in assignment['before'].items())
assert sha(root / 'corrected_stiffness_assignment/executed_check.py') == assignment['scriptSha256']
assert sha(root / 'corrected_stiffness_assignment/executed_helper.py') == assignment['helperSha256']
print('ACTUAL_RETOPO_CLOTH_ARTIFACTS_VERIFIED', len(inventory['artifacts']), 'indexed' if a.indexed else 'local')
