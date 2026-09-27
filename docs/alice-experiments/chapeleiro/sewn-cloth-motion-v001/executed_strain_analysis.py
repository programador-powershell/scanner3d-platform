"""Localize actual maximum strain and inspect continuity of welded seam paths."""
import hashlib, json
from pathlib import Path
import numpy as np

base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/sewn_ivory_black_cloth_v005')
r = json.loads((base / 'actual_sewn_solver_motion.json').read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
assert sha(r['dataFile']) == r['dataSha256']
d = np.load(r['dataFile'])
rest, points, edges = d['rest_points'], d['points'], d['edges']
lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
valid = (lengths > 1e-6) & ~d['loose_edges']
actual_lengths = np.linalg.norm(points[:, edges[:, 0]] - points[:, edges[:, 1]], axis=2)
rows = []
support_start = next(p['start'] for p in r['parts'] if p['key'] == 'support')
for part in r['parts']:
    lo, hi = part['start'], part['start'] + part['vertices']
    mask = valid & (edges[:, 0] >= lo) & (edges[:, 0] < hi) & (edges[:, 1] >= lo) & (edges[:, 1] < hi)
    ids = np.flatnonzero(mask)
    ratios = actual_lengths[:, ids] / lengths[ids]
    flat = np.argsort(ratios.ravel())[-10:][::-1]
    worst = []
    for index in flat:
        frame, local = np.unravel_index(index, ratios.shape)
        edge = int(ids[local])
        logical = edges[edge] - lo
        worst.append({'frame': int(frame + 1), 'stretch': float(ratios[frame, local]),
                      'logicalVertices': logical.tolist(), 'rows': (logical // 192).tolist(),
                      'columns': (logical % 192).tolist(), 'restLengthMeters': float(lengths[edge]),
                      'actualLengthMeters': float(actual_lengths[frame, edge])})
    row = {'piece': part['key'], 'worstEdgesAcrossActualSequence': worst}
    if part['key'].startswith('tier'):
        pairs = np.asarray(part['sewingEdges'], np.int32)
        support_rows = (pairs[:, 0] - support_start) // 192
        jumps = np.abs(support_rows - np.roll(support_rows, 1))
        row['seamPath'] = {'supportRowsByColumn': support_rows.tolist(),
                           'adjacentColumnsWithDifferentSupportRows': int(np.count_nonzero(jumps)),
                           'maximumAdjacentRowJump': int(jumps.max()),
                           'reviewRequired': bool(np.any(jumps)),
                           'limitation': 'Nearest-height ring selection per column can produce a stepped seam path; zero welded gap does not establish smooth seam continuity.'}
    rows.append(row)
out = {'probeDataSha256': r['dataSha256'], 'actuallyMeasuredAll29Frames': True, 'parts': rows,
       'scriptSha256': sha(__file__), 'notAVisualOrPhysicalApproval': True}
(base / 'strain_localization.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'parts': [{'key': x['piece'], 'worst': x['worstEdgesAcrossActualSequence'][0],
                           'rowChanges': x.get('seamPath', {}).get('adjacentColumnsWithDifferentSupportRows')} for x in rows]}, indent=2))
