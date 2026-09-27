"""Read five garment midsurfaces and weights from their actual skin previews.

No geometry, UV, material, weight, pose or checkpoint is saved or modified.
This prepares a measured skin approximation; it does not approve the input
cloth motion or replace the high detail garments with calculator surfaces.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
g, r = read(a.generation), read(a.probe)
assert sha(g['editableBlend']) == g['editableBlendSha256'] == r['parentEditableSha256']
assert sha(r['dataFile']) == r['dataSha256']
assert sha(g['exports']['foundation']['sourcePhoto']) == r['sourcePhotoSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
d = np.load(r['dataFile'])
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
names = [b.name for b in rig.data.bones]
assert names == d['bone_names'].tolist() and len(names) == 173
cloth = np.array([i for i, n in enumerate(names) if n.startswith(('IvoryCloth_', 'BlackCloth_'))])
assert len(cloth) == 72
all_points, all_weights, rows, start = [], [], [], 0
for part in r['parts']:
    source = bpy.data.objects[part['source']]
    obj = bpy.data.objects[part['visibleGarment']]
    # BCB's evaluated rest previews retain the original surface first, followed
    # by their thickness output. Establish the correspondence by actual coords,
    # rather than assuming the second surface has the same vertex order.
    count = len(source.data.vertices)
    assert len(obj.data.vertices) == 2 * count
    points = np.asarray([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices], np.float32)
    points = points[:count]
    expected = d[part['key'] + '_original_world_points']
    assert points.shape == expected.shape and np.max(np.abs(points - expected)) < 1e-6
    weights = np.zeros((len(points), len(names)), np.float32)
    lookup = {group.index: names.index(group.name) for group in obj.vertex_groups if group.name in names}
    for vertex in obj.data.vertices[:count]:
        for group in vertex.groups:
            if group.group in lookup:
                weights[vertex.index, lookup[group.group]] = group.weight
    assert np.max(np.abs(weights.sum(1) - 1)) < 1e-6
    assert np.max(np.sum(weights > 0, axis=1)) <= 4
    assert part['start'] == start and part['vertices'] == len(points)
    all_points.append(points); all_weights.append(weights)
    rows.append({'key': part['key'], 'source': source.name, 'actualWeightedPreview': obj.name,
                 'previewOriginalSurfaceIndexRange': [0, count], 'start': start,
                 'vertices': len(points), 'originalWorldPointsMaximumError': float(np.max(np.abs(points - expected))),
                 'maximumWeightSumError': float(np.max(np.abs(weights.sum(1) - 1))),
                 'maximumInfluences': int(np.max(np.sum(weights > 0, axis=1)))})
    start += len(points)
points, weights = np.concatenate(all_points), np.concatenate(all_weights)
assert points.shape == d['rest_points'].shape and len(points) == 22080
rest_error = float(np.max(np.abs(points - d['rest_points'])))
assert rest_error < 1e-6
world = np.asarray(rig.matrix_world, np.float64)
inverse = np.linalg.inv(world)
hom = np.c_[points, np.ones(len(points))]
supports = {k: np.flatnonzero(weights[:, k] > 0) for k in range(len(names))}
skin_errors = []
for frame in range(len(d['rig_deformations'])):
    matrices = np.asarray([world @ matrix @ inverse for matrix in d['rig_deformations'][frame]])
    posed = np.zeros_like(points, dtype=np.float64)
    for k, ids in supports.items():
        if len(ids):
            posed[ids] += (hom[ids] @ matrices[k].T)[:, :3] * weights[ids, k, None]
    errors = np.linalg.norm(posed - d['actual_skin_targets'][frame], axis=1)
    skin_errors.append({'frame': frame + 1, 'maximumMeters': float(errors.max()),
                        'p95Meters': float(np.percentile(errors, 95)), 'meanMeters': float(errors.mean())})
data = out / 'actual_five_cage_skin_seed.npz'
np.savez_compressed(data, rest_points=points, weights=weights, bone_names=np.asarray(names),
                    bind_matrices=np.asarray([np.asarray(b.matrix_local) for b in rig.data.bones]),
                    rig_world=world, cloth_bone_indices=cloth,
                    bone_parents=np.asarray([names.index(b.parent.name) if b.parent else -1 for b in rig.data.bones]))
report = {'parentEditableSha256': g['editableBlendSha256'], 'sourcePhotoSha256': r['sourcePhotoSha256'],
          'referencePhysicalDataSha256': r['dataSha256'], 'referenceProbe': str(Path(a.probe).resolve()),
          'actualRigBones': len(names), 'actualClothBones': len(cloth), 'actualVertices': len(points),
          'parts': rows, 'originalRestMaximumError': rest_error,
          'originalFineSkinVsCalculatorDetailTargets': skin_errors,
          'limitation': 'The actual original surface of each skin preview supplies its existing weights. The separate thickness output is not reordered or assumed to match by index. Calculator detail targets can differ from these fine weights; errors are measured and no motion or fidelity is approved.',
          'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'sourceEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'sourceGeometryUvMaterialsAndWeightsUnchanged': True,
          'responseFitted': False, 'responseBaked': False, 'finalFbxExported': False,
          'allLayersFinished': False, 'motionVerified': False, 'clothCollisionVerified': False, 'fidelityVerified': False}
(out / 'seed.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_skin_seed.py')
print('ACTUAL_FIVE_CAGE_SKIN_SEED', len(points), len(cloth), max(row['maximumMeters'] for row in skin_errors), flush=True)
