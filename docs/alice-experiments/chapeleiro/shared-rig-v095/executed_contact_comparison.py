"""Compare the actual pre/post waist physics and independently queried contacts."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def case(root):
    root = Path(root)
    probe = read(root / 'actual_sewn_solver_motion.json')
    data = np.load(probe['dataFile'])
    assert sha(probe['dataFile']) == probe['dataSha256']
    contacts = {}
    for folder in ['pinned_input_clearance_inspection', 'dynamic_clearance_inspection']:
        r = read(root / folder / 'dynamic_clearance_inspection.json')
        assert r['sourcePhysicalDataSha256'] == probe['dataSha256']
        assert sha(r['dataFile']) == r['dataSha256']
        a = np.load(r['dataFile'])
        summaries = []
        for i in range(3):
            summaries.append({'proxyIndex': i, 'peakCertainInsideVertices': max(f['proxies'][i]['certainInsideVertices'] for f in r['frames']),
                              'maximumCertainPenetrationMeters': max(f['proxies'][i]['maximumCertainPenetrationMeters'] for f in r['frames']),
                              'ambiguousQueriesAcrossSequence': sum(f['proxies'][i]['ambiguousRayQueries'] for f in r['frames'])})
        if 'actualQueriedPointField' not in r:
            assert folder == 'dynamic_clearance_inspection'
            executed = (root / folder / 'executed_inspection.py').read_text(encoding='utf-8')
            assert "for frame, carrier in enumerate(data['actual_simulation_points'], 1)" in executed
            assert a['certain_inside_masks'].shape[2] == len(data['simulation_rest_points'])
        entry = {'queriedField': r.get('actualQueriedPointField', 'actual_simulation_points'),
                 'queriedVertices': r.get('actualVerticesQueriedPerProxyAndFrame', len(data['simulation_rest_points'])),
                 'dataSha256': r['dataSha256'], 'proxies': summaries}
        if folder.startswith('pinned'):
            assert r['minimumPinWeight'] == .5 and r['actualQueriedPointField'] == 'actual_simulation_skin_targets'
            ids = a['queried_simulation_vertex_indices']
            mask = data['simulation_pin_weights'][ids] > .999
            entry['fullyPinnedVerticesQueried'] = int(mask.sum())
            entry['fullyPinnedBloomerInsidePeak'] = int(a['certain_inside_masks'][:, 2, mask].sum(1).max())
            inside = a['certain_inside_masks'][:, 2, mask]
            distances = a['nearest_distances'][:, 2, mask]
            entry['fullyPinnedBloomerMaximumPenetrationMeters'] = float(distances[inside].max()) if inside.any() else 0.
            ambiguous = (~a['two_ray_agreements'][:, 2, mask]) & (distances > 1e-5)
            entry['fullyPinnedBloomerAmbiguousPeak'] = int(ambiguous.sum(1).max())
            entry['fullyPinnedBloomerAmbiguousQueriesAcrossSequence'] = int(ambiguous.sum())
        contacts[folder] = (r, a, entry)
    return probe, data, contacts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', required=True)
    p.add_argument('--after', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    a, x, old = case(args.before)
    b, y, new = case(args.after)
    same = ['bone_names', 'rig_deformations', 'simulation_rest_points', 'simulation_edges',
            'simulation_faces', 'simulation_pin_weights', 'simulation_loose_edges',
            'physical_seam_pairs', 'actual_simulation_skin_targets', 'actual_skin_targets', 'rest_points']
    for key in same:
        assert np.array_equal(x[key], y[key]), key
    for key in ['assembly', 'actualSolverSettings', 'actualCollisionSettings', 'massCalibration', 'physicalRestEdgeQuality']:
        assert a[key] == b[key], key
    proxy_equal = []
    for i in range(3):
        old_d = old['dynamic_clearance_inspection'][1]
        new_d = new['dynamic_clearance_inspection'][1]
        points = f'proxy_{i}_animated_world_points'
        triangles = f'proxy_{i}_animated_triangles'
        triangles_equal = bool(np.array_equal(old_d[triangles], new_d[triangles]))
        assert old_d[triangles].shape == new_d[triangles].shape
        if i != 2:
            assert triangles_equal
        equal = bool(np.array_equal(old_d[points], new_d[points]))
        assert equal == (i != 2)
        proxy_equal.append({'proxyIndex': i, 'actualTrianglesIdentical': triangles_equal,
                            'changedAnimatedTriangleIndexValues': int((old_d[triangles] != new_d[triangles]).sum()),
                            'animatedWorldCoordinatesIdentical': equal,
                            'bloomerQuadTessellationMayChangeWithWaistDeformation': i == 2})
    def physical(probe):
        return {'maximumSeamGapMeters': max(f['maximumSeamGapMeters'] for f in probe['frames']),
                'maximumPhysicalFullyPinnedInputErrorMeters': max(f['maximumPhysicalFullyPinnedInputError'] for f in probe['frames']),
                'parts': [{'key': part['key'],
                           'maximumPhysicalEdgeStretch': max(f['pieces'][i]['solverMaximumEdgeStretch'] for f in probe['frames']),
                           'maximumDetailEdgeStretch': max(f['pieces'][i]['maximumEdgeStretch'] for f in probe['frames'])}
                          for i, part in enumerate(probe['parts'])]}
    report = {'sourcePhotoSha256': b['sourcePhotoSha256'], 'beforePhysicalDataSha256': a['dataSha256'],
              'afterPhysicalDataSha256': b['dataSha256'], 'actualFramesPerCase': len(b['frames']),
              'identicalActualInputArrays': same, 'solverMaterialMassPinsTopologySeamsUnchanged': True,
              'animatedProxyComparison': proxy_equal,
              'before': {'physical': physical(a), **{k: v[2] for k, v in old.items()}},
              'after': {'physical': physical(b), **{k: v[2] for k, v in new.items()}},
              'waistAnchorConflictEliminatedInMeasuredSequence': new['pinned_input_clearance_inspection'][2]['fullyPinnedBloomerInsidePeak'] == 0 and new['pinned_input_clearance_inspection'][2]['fullyPinnedBloomerAmbiguousPeak'] == 0,
              'freeClothPenetrationStillPresent': True, 'physicalSpringStudyBakedIntoPublishedRig': False,
              'allLayersFinished': False, 'fidelityVerified': False, 'motionVerified': False,
              'clothCollisionVerified': False, 'finalFbxExported': False, 'additionalCreditsConsumed': 0,
              'scriptSha256': sha(__file__),
              'limitation': 'Actual 29-frame vertex diagnostics only. Waist input conflict is resolved in this sequence; free-cloth penetration worsens. No continuous contact, complete photo fidelity or all-action physics approval.'}
    out = Path(args.output)
    assert not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    shutil.copyfile(__file__, out.with_name('executed_contact_comparison.py'))
    print(json.dumps({k: v for k, v in report.items() if k in ['actualFramesPerCase', 'waistAnchorConflictEliminatedInMeasuredSequence', 'before', 'after']}, indent=2))


if __name__ == '__main__':
    main()
