"""Measure the actual imported garment against the fitted cloth carrier.

The exported shell has thickness and UV splits. Nearest rest-position pairs
measure that shell correspondence; they do not prove signed contact or fidelity.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g = read(a.generation)
root = Path(a.generation).parent
fit = read(g['ivoryFitReport'])
seed = read(fit['seedReport'])
review = read(root / 'actual_ivory_export_review_v001/comparison.json')
actual_file = root / 'actual_ivory_export_review_v001/actual_exported_ivory_poses.npz'
assert sha(actual_file) == review['actualExportDataSha256']
assert sha(fit['dataFile']) == fit['dataSha256']
actual, fitted = np.load(actual_file), np.load(fit['dataFile'])
seed_file = Path(fit['seedReport']).parent / 'actual_ivory_skin_seed.npz'
assert sha(seed_file) == fit['actualSeedDataSha256']
rest = np.load(seed_file)['rest_points']
distances, indices = cKDTree(actual['rest_points']).query(rest)
assert len(indices) == 7104 and distances.max() < .001
rows = []
for i in range(29):
    exported = actual['points'][i, indices]
    shell_error = np.linalg.norm(exported - fitted['fitted_points'][i], axis=1)
    solver_error = np.linalg.norm(exported - fitted['actual_solver_points'][i], axis=1)
    rows.append({'sourcePhysicsFrame': i + 1,
                 'actualShellToFittedCarrierMaximumMeters': float(shell_error.max()),
                 'actualShellToFittedCarrier95PercentileMeters': float(np.percentile(shell_error, 95)),
                 'actualShellToSolverMaximumMeters': float(solver_error.max()),
                 'actualShellToSolver95PercentileMeters': float(np.percentile(solver_error, 95))})
report = {'modelSha256': review['modelSha256'], 'sourcePhotoSha256': review['sourcePhotoSha256'],
          'actualExportDataSha256': sha(actual_file), 'fitDataSha256': fit['dataSha256'],
          'actualRestShellCorrespondenceMaximumMeters': float(distances.max()),
          'actualCarrierVerticesCompared': len(indices), 'actualExportedShellVertices': len(actual['rest_points']),
          'frames': rows, 'scriptSha256': sha(__file__),
          'limitation': 'Nearest rest-position correspondence includes shell thickness. Signed contact, fine folds and other components remain unapproved.',
          'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False, 'allLayersFinished': False}
Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('ACTUAL_EXPORTED_IVORY_FIT_MEASURED', max(r['actualShellToFittedCarrierMaximumMeters'] for r in rows),
      max(r['actualShellToSolverMaximumMeters'] for r in rows))
