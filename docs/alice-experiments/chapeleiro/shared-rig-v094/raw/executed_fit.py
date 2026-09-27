"""Fit existing Ivory secondary joints to measured Cloth using unchanged weights.

Rigid coordinate descent minimizes the actual carrier's linear skinning error.
Only the 36 existing Ivory joints may change. This is a measured approximation,
not a claim that skinning reproduces every Cloth wrinkle or collision contact.
"""
import argparse, hashlib, json, shutil, time
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--seed', required=True)
p.add_argument('--physics', required=True)
p.add_argument('--output', required=True)
p.add_argument('--iterations', type=int, default=64)
args = p.parse_args()
assert args.iterations > 0
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
seed, physics = read(args.seed), read(args.physics)
assert sha(seed['dataFile']) == seed['dataSha256']
assert sha(physics['dataFile']) == physics['dataSha256'] == seed['actualPhysicsDataSha256']
assert seed['parentEditableSha256'] == physics['parentEditableSha256']
assert seed['sourcePhotoSha256'] == physics['sourcePhotoSha256']
assert physics['clothNeverBypassedDuringSequence']
assert physics['colliderSurface'] == 'authored_midsurfaces'
assert all(not f['cacheOutdated'] for f in physics['frames'])
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
start = time.time()
s = np.load(seed['dataFile'])
a = np.load(physics['dataFile'])
assert np.array_equal(s['bone_names'], a['bone_names'])
assert np.array_equal(s['rest_points'], a['rest_points'])
x, w = s['rest_points'].astype(np.float64), s['weights'].astype(np.float64)
indices = s['ivory_bone_indices']
assert len(indices) == 36 and w.shape == (7104, 173)
world = s['rig_world'].astype(np.float64)
inverse = np.linalg.inv(world)
target = a['points'].astype(np.float64)
base = np.asarray([[world @ d.astype(np.float64) @ inverse for d in frame] for frame in a['rig_deformations']])
importance = 1 + 9 * a['pin_weights'].astype(np.float64)
supports = {int(k): np.flatnonzero(w[:, k] > 0) for k in range(w.shape[1])}

def skin(matrices):
    result = np.zeros_like(x)
    for k, ids in supports.items():
        if len(ids):
            result[ids] += (x[ids] @ matrices[k, :3, :3].T + matrices[k, :3, 3]) * w[ids, k, None]
    return result

def stats(errors):
    return {'maximum': float(errors.max()), 'mean': float(errors.mean()),
            'p95': float(np.percentile(errors, 95))}

fitted, predicted, rows = [], [], []
fixed = np.array([k for k in range(w.shape[1]) if k not in set(indices)])
for frame, goal in enumerate(target):
    matrices = base[frame].copy()
    if frame:
        for k in indices:
            matrices[k] = base[frame, k] @ np.linalg.inv(base[frame - 1, k]) @ fitted[-1][k]
    baseline = skin(base[frame])
    original_error = np.linalg.norm(baseline - a['actual_skin_targets'][frame], axis=1)
    assert original_error.max() < 1e-6
    points = skin(matrices)
    history = []
    for iteration in range(args.iterations):
        order = indices if iteration % 2 == 0 else indices[::-1]
        for k in order:
            ids = supports[int(k)]
            weight = w[ids, k]
            q = importance[ids] * weight ** 2
            old = x[ids] @ matrices[k, :3, :3].T + matrices[k, :3, 3]
            desired = old + (goal[ids] - points[ids]) / weight[:, None]
            total = q.sum()
            cx = (x[ids] * q[:, None]).sum(0) / total
            cy = (desired * q[:, None]).sum(0) / total
            covariance = (x[ids] - cx).T @ ((desired - cy) * q[:, None])
            u, _, vt = np.linalg.svd(covariance)
            correction = np.eye(3)
            correction[2, 2] = np.linalg.det(vt.T @ u.T)
            rotation = vt.T @ correction @ u.T
            translation = cy - rotation @ cx
            update = x[ids] @ rotation.T + translation
            points[ids] += (update - old) * weight[:, None]
            matrices[k, :3, :3], matrices[k, :3, 3] = rotation, translation
        if iteration % 8 == 0 or iteration == args.iterations - 1:
            history.append({'iteration': iteration + 1,
                            'weightedSquaredError': float((importance[:, None] * (points - goal) ** 2).sum())})
    assert np.array_equal(matrices[fixed], base[frame, fixed])
    assert np.abs(points - skin(matrices)).max() < 1e-9
    determinants = np.linalg.det(matrices[indices, :3, :3])
    assert np.abs(determinants - 1).max() < 1e-9
    residual = np.linalg.norm(points - goal, axis=1)
    pinned = a['pin_weights'] > .999
    rows.append({'frame': frame + 1,
                 'originalParentSkinErrorToActualSolver': stats(np.linalg.norm(baseline - goal, axis=1)),
                 'fittedSkinErrorToActualSolver': stats(residual),
                 'maximumFullyPinnedErrorToActualSolver': float(residual[pinned].max()),
                 'unchangedSourceSkinReconstructionMaximumError': float(original_error.max()),
                 'optimization': history})
    fitted.append(matrices)
    predicted.append(points)
    print('IVORY_JOINT_FIT_FRAME', frame + 1, len(target), rows[-1]['fittedSkinErrorToActualSolver'], flush=True)
data = out / 'fitted_ivory_joint_motion.npz'
rig_space = np.asarray([[inverse @ d @ world for d in frame] for frame in fitted])
np.savez_compressed(data, rig_deformations=rig_space, fitted_points=np.asarray(predicted),
                    actual_solver_points=target, original_rig_deformations=a['rig_deformations'],
                    bone_names=s['bone_names'], modified_bone_indices=indices)
report = {'method': 'fixed actual skin weights; alternating rigid weighted Kabsch joint transforms',
          'parentEditableSha256': seed['parentEditableSha256'], 'sourcePhotoSha256': seed['sourcePhotoSha256'],
          'actualPhysicsDataSha256': physics['dataSha256'], 'actualSeedDataSha256': seed['dataSha256'],
          'seedReport': str(Path(args.seed).resolve()), 'physicsReport': str(Path(args.physics).resolve()),
          'actualFrames': len(target), 'iterationsPerFrame': args.iterations,
          'modifiedBones': s['bone_names'][indices].tolist(), 'other137BonesUnchanged': True,
          'actualGeometryAndWeightsUnchanged': True, 'frames': rows,
          'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'elapsedSeconds': time.time() - start, 'responseFitted': True, 'responseBaked': False,
          'scope': 'Ivory carrier approximation; all wrinkles, chain constraints, transitions and other layers require review',
          'allLayersFinished': False, 'motionVerified': False, 'fidelityVerified': False,
          'clothCollisionVerified': False, 'finalFbxExported': False, 'nextVariantMayStart': False}
(out / 'fit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_fit.py')
print('IVORY_JOINT_FIT_SAVED', flush=True)
