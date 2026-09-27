"""Measure the existing shared-joint approximation to five garment surfaces.

The fixed weights are read from the actual fine skin previews. Body and whole
exterior joints are unchanged. Fitting never approves a bad physical target,
changes a checkpoint, bakes an action or exports a GLB/FBX.
"""
import argparse, hashlib, json, shutil, time
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--seed', required=True)
p.add_argument('--physics', required=True)
p.add_argument('--output', required=True)
p.add_argument('--iterations', type=int, default=64)
a = p.parse_args()
assert a.iterations > 0
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
s, r = read(a.seed), read(a.physics)
assert s['sourceEditableUnchanged'] and s['sourceGeometryUvMaterialsAndWeightsUnchanged']
assert s.get('physicalReferenceParentSha256', s['parentEditableSha256']) == r['parentEditableSha256']
assert s['sourcePhotoSha256'] == r['sourcePhotoSha256']
assert sha(s['dataFile']) == s['dataSha256'] and sha(r['dataFile']) == r['dataSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
started = time.time()
seed, data = np.load(s['dataFile']), np.load(r['dataFile'])
assert np.array_equal(seed['physics_bone_names'] if 'physics_bone_names' in seed else seed['bone_names'], data['bone_names'])
source_indices = seed['physics_bone_source_indices'] if 'physics_bone_source_indices' in seed else np.arange(len(seed['bone_names']))
x, w = seed['rest_points'].astype(np.float64), seed['weights'].astype(np.float64)
assert x.shape == data['rest_points'].shape and w.shape == (22080, len(seed['bone_names']))
rest_error = float(np.max(np.abs(x - data['rest_points'])))
assert rest_error < 1e-6
indices = seed['cloth_bone_indices']
assert len(indices) == len(seed['bone_names']) - 101 and len(indices) in [72, 108]
fixed = np.asarray([k for k in range(w.shape[1]) if k not in set(indices)])
world = seed['rig_world'].astype(np.float64)
inverse = np.linalg.inv(world)
source_deformations = data['rig_deformations'][:, source_indices]
base = np.asarray([[world @ m @ inverse for m in frame] for frame in source_deformations])
targets = data['points'].astype(np.float64)
assert np.isfinite(targets).all()
importance = 1 + 9 * data['pin_weights'].astype(np.float64)
supports = {k: np.flatnonzero(w[:, k] > 0) for k in range(w.shape[1])}

def skin(matrices):
    result = np.zeros_like(x)
    for k, ids in supports.items():
        if len(ids):
            result[ids] += (x[ids] @ matrices[k, :3, :3].T + matrices[k, :3, 3]) * w[ids, k, None]
    return result

def stats(errors):
    return {'maximumMeters': float(errors.max()), 'meanMeters': float(errors.mean()),
            'p95Meters': float(np.percentile(errors, 95))}

fitted, predicted, rows = [], [], []
for frame, goal in enumerate(targets):
    matrices = base[frame].copy()
    if frame:
        for k in indices:
            matrices[k] = base[frame, k] @ np.linalg.inv(base[frame - 1, k]) @ fitted[-1][k]
    baseline = skin(base[frame])
    points = skin(matrices)
    history = []
    for iteration in range(a.iterations):
        for k in (indices if iteration % 2 == 0 else indices[::-1]):
            ids = supports[int(k)]
            if not len(ids):
                continue
            weight = w[ids, k]
            q = importance[ids] * weight ** 2
            old = x[ids] @ matrices[k, :3, :3].T + matrices[k, :3, 3]
            desired = old + (goal[ids] - points[ids]) / weight[:, None]
            cx = (x[ids] * q[:, None]).sum(0) / q.sum()
            cy = (desired * q[:, None]).sum(0) / q.sum()
            u, _, vt = np.linalg.svd((x[ids] - cx).T @ ((desired - cy) * q[:, None]))
            correction = np.eye(3)
            correction[2, 2] = np.linalg.det(vt.T @ u.T)
            rotation = vt.T @ correction @ u.T
            translation = cy - rotation @ cx
            update = x[ids] @ rotation.T + translation
            points[ids] += (update - old) * weight[:, None]
            matrices[k, :3, :3], matrices[k, :3, 3] = rotation, translation
        if iteration % 8 == 0 or iteration == a.iterations - 1:
            history.append({'iteration': iteration + 1,
                            'weightedSquaredError': float((importance[:, None] * (points - goal) ** 2).sum())})
    assert np.array_equal(matrices[fixed], base[frame, fixed])
    assert np.max(np.abs(points - skin(matrices))) < 1e-9
    assert np.max(np.abs(np.linalg.det(matrices[indices, :3, :3]) - 1)) < 1e-9
    residual = np.linalg.norm(points - goal, axis=1)
    pieces = []
    for part in s['parts']:
        lo, hi = part['start'], part['start'] + part['vertices']
        pieces.append({'key': part['key'], 'fittedError': stats(residual[lo:hi]),
                       'baselineError': stats(np.linalg.norm(baseline[lo:hi] - goal[lo:hi], axis=1))})
    rows.append({'frame': frame + 1, 'pieces': pieces, 'fittedError': stats(residual),
                 'maximumFullyPinnedErrorMeters': float(residual[data['pin_weights'] > .999].max()),
                 'originalFineSkinVsCalculatorTargets': stats(np.linalg.norm(baseline - data['actual_skin_targets'][frame], axis=1)),
                 'optimization': history})
    fitted.append(matrices); predicted.append(points)
    print('ACTUAL_FIVE_CAGE_JOINT_FIT', frame + 1, len(targets), rows[-1]['fittedError'], flush=True)
file = out / 'fitted_five_cage_joint_frames.npz'
np.savez_compressed(file, rig_deformations=np.asarray([[inverse @ m @ world for m in frame] for frame in fitted]),
                    fitted_points=np.asarray(predicted), actual_solver_points=targets,
                    original_rig_deformations=source_deformations, bone_names=seed['bone_names'],
                    modified_bone_indices=indices)
report = {'method': 'Fixed actual fine preview weights; alternating rigid weighted Kabsch transforms on both existing cloth joint families',
          'seedReport': str(Path(a.seed).resolve()), 'physicsReport': str(Path(a.physics).resolve()),
          'parentEditableSha256': s['parentEditableSha256'], 'physicalReferenceParentSha256': r['parentEditableSha256'],
          'sourcePhotoSha256': r['sourcePhotoSha256'],
          'actualSeedDataSha256': s['dataSha256'], 'actualPhysicsDataSha256': r['dataSha256'],
          'actualFrames': len(targets), 'iterationsPerFrame': a.iterations, 'frames': rows,
          'originalRestMaximumErrorMeters': rest_error, 'actualModifiedBones': seed['bone_names'][indices].tolist(),
          'actualClothBonesFitted': len(indices), 'actualSharedRigBones': len(seed['bone_names']),
          'other101BodyAndExteriorBonesUnchanged': True, 'actualGeometryUvMaterialsAndWeightsUnchanged': True,
          'dataFile': str(file), 'dataSha256': sha(file), 'scriptSha256': sha(__file__),
          'elapsedSeconds': time.time() - started, 'responseFitted': True, 'responseBaked': False,
          'physicalTargetCollisionOrFidelityApproved': False,
          'limitation': 'Only five fine midsurface responses are approximated. Thickness, lace, other layers, all actions, collisions and actual reimported exports still require review.',
          'allLayersFinished': False, 'motionVerified': False, 'fidelityVerified': False,
          'clothCollisionVerified': False, 'finalFbxExported': False, 'nextVariantMayStart': False}
(out / 'fit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_joint_fit.py')
print('ACTUAL_FIVE_CAGE_JOINT_FIT_SAVED', flush=True)
