"""Validate guide identity on the fully reimported, Draco-compressed Alice GLB."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--export', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
report = json.loads(Path(args.export).read_text(encoding='utf-8'))
model = Path(report['model'])
digest = hashlib.sha256()
with model.open('rb') as stream:
    for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
        digest.update(block)
assert digest.hexdigest() == report['modelSha256']

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(model))
hair = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.get('aliceRole') == 'hair']
assert len(hair) == report['hairRibbonMeshCount']
count = int(report['exportedFiberCount'])
guides = np.full(count, -1, dtype=np.int32)
minimum_t = np.full(count, np.inf, dtype=np.float32)
maximum_t = np.full(count, -np.inf, dtype=np.float32)
total_vertices = 0
max_fiber_deviation = 0.0
max_guide_deviation = 0.0
for obj in hair:
    mesh = obj.data
    assert {'_FIBER_ID', '_FIBER_T', '_GUIDE_ID'} <= set(mesh.attributes.keys())
    n = len(mesh.vertices)
    arrays = []
    for name in ('_FIBER_ID', '_FIBER_T', '_GUIDE_ID'):
        values = np.empty(n, dtype=np.float32)
        mesh.attributes[name].data.foreach_get('value', values)
        arrays.append(values)
    fid, factor, gid = arrays
    assert np.isfinite(fid).all() and np.isfinite(factor).all() and np.isfinite(gid).all()
    max_fiber_deviation = max(max_fiber_deviation, float(np.max(np.abs(fid - np.rint(fid)))))
    max_guide_deviation = max(max_guide_deviation, float(np.max(np.abs(gid - np.rint(gid)))))
    assert np.all((fid >= -.5) & (fid < count + .5)) and np.all((factor >= 0) & (factor <= 1))
    fid = np.rint(fid).astype(np.int32)
    gid = np.rint(gid).astype(np.int32)
    for fiber_id in np.unique(fid):
        mask = fid == fiber_id
        unique_guides = np.unique(gid[mask])
        assert len(unique_guides) == 1
        previous = guides[fiber_id]
        assert previous < 0 or previous == unique_guides[0]
        guides[fiber_id] = unique_guides[0]
        minimum_t[fiber_id] = min(minimum_t[fiber_id], float(factor[mask].min()))
        maximum_t[fiber_id] = max(maximum_t[fiber_id], float(factor[mask].max()))
    total_vertices += n

assert int(np.count_nonzero(guides >= 0)) == report['exportedFiberCount']
selected = guides >= 0
assert np.all(minimum_t[selected] == 0) and np.all(maximum_t[selected] == 1)
assert max_fiber_deviation < .5 and max_guide_deviation < .5
source_generation = json.loads(Path(report['sourceGeneration']).read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=source_generation['editableBlend'])
source_hair = next(obj for obj in bpy.context.scene.objects
                   if obj.type == 'CURVES' and 'individual hair fibers' in obj.name)
expected_guides = np.empty(count, np.int32)
source_count = int(report['sourceFiberCount'])
source_guides = np.empty(source_count, np.int32)
source_hair.data.attributes['guide_id'].data.foreach_get('value', source_guides)
expected_guides[:source_count] = source_guides
if report.get('addedRearBraidFiberCount', 0):
    braid = bpy.data.objects['Chapeleiro / rear braid individual fibers / study']
    added = len(braid.data.curves)
    assert added == count - source_count == report['addedRearBraidFiberCount']
    sides = np.empty(added, np.int32)
    tresses = np.empty(added, np.int32)
    braid.data.attributes['alice_braid_side'].data.foreach_get('value', sides)
    braid.data.attributes['alice_braid_tress'].data.foreach_get('value', tresses)
    assert set(sides) == {-1, 1} and set(tresses) == {0, 1, 2}
    expected_guides[source_count:] = 2112 + np.where(sides == -1, 0, 3) + tresses
assert np.array_equal(guides[selected], expected_guides[selected])
result = dict(model=str(model), modelSha256=report['modelSha256'],
              wholeCharacterWithDress=report['wholeCharacterWithDress'],
              hairChunks=len(hair), fiberCount=int(selected.sum()),
              uniqueGuideCount=int(len(np.unique(guides[selected]))),
              hairVertices=total_vertices, consistentGuidePerFiber=True,
              guideIdsMatchEditableSource=True,
              maxFiberIdQuantizationError=max_fiber_deviation,
              maxGuideIdQuantizationError=max_guide_deviation,
              rootAndTipFactorsPresent=True, sourcePhysicsTransferred=False,
              published=False)
Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print('REIMPORTED_GUIDE_MAPPING', json.dumps(result), flush=True)
