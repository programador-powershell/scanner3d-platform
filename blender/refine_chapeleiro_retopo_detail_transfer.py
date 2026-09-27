"""Polish detail transfer using a verified completed physical trajectory.

No Cloth solver is executed here. The stored physical vertices and rig poses
remain exact; only the shared tangent frames used by the dense detail change.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g, r = read(path), read(a.probe)
assert r['parentEditableUnchanged'] and r['exportedModelUnchanged'] and len(r['frames']) == 29
assert sha(g['editableBlend']) == g['editableBlendSha256'] == r['parentEditableSha256']
assert sha(r['dataFile']) == r['dataSha256']
assert not out.exists()
out.mkdir(parents=True)
old = np.load(r['dataFile'])
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_retopo_cloth_assembly import assemble_retopo_petticoats, RestDetailTransfer
reference_root = Path(g.get('authoringReferenceRoot', path.parent))
schema = read(reference_root / 'shared_rig_bind.json')
cage, parts, assembly = assemble_retopo_petticoats(scene, rig, schema, r['parts'][0]['simulationAround'],
                                                  r['assembly']['angularLowpass'], r['parts'][2]['simulationRows'] - 1,
                                                  smooth_detail=True, outward_winding=r['assembly'].get('outwardWinding', False),
                                                  seam_mode=r['assembly'].get('seamMode', 'welded'),
                                                  seam_clearance=r['assembly'].get('independentSeamClearanceMeters', .0015) or .0015)
transfer = assembly.pop('detailTransfer')
original = assembly.pop('originalPointsByPart')
assembly.pop('partSolverOwnership')
seams = assembly.pop('physicalSeamPairs')
edges = assembly.pop('measurementEdges')
rest = np.asarray([tuple(cage.matrix_world @ v.co) for v in cage.data.vertices], np.float32)
faces = np.asarray([tuple(p.vertices) for p in cage.data.polygons], np.int32)
assert np.array_equal(rest, old['simulation_rest_points'])
assert np.array_equal(faces, old['simulation_faces'])
assert np.array_equal(seams, old['physical_seam_pairs'])
assert np.array_equal(edges, old['edges'])
old_transfer = RestDetailTransfer(old['detail_corner_indices'], old['detail_weights'], old['detail_u'], old['detail_v'],
                                  rest, np.concatenate([original[p['key']] for p in parts]))
for collection in bpy.data.collections: collection.hide_viewport = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, cage]
    obj.hide_render = True
    if obj in [rig, cage]: obj.hide_set(False)
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
names = old['bone_names'].tolist()
assert names == [b.name for b in rig.data.bones]
bind = {b.name: b.matrix_local.copy() for b in rig.data.bones}
assert [m.type for m in cage.modifiers] == ['ARMATURE']

def coords(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    m = np.asarray(ev.matrix_world)
    result = xyz.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    ev.to_mesh_clear()
    return result.astype(np.float32)

logical_rest = transfer.apply(rest)
lengths = np.linalg.norm(logical_rest[edges[:, 0]] - logical_rest[edges[:, 1]], axis=1)
valid = lengths > 1e-6
points, inputs, physical_inputs, rows = [], [], [], []
for frame in range(29):
    desired = {n: Matrix(old['rig_deformations'][frame, i].tolist()) @ bind[n] for i, n in enumerate(names)}
    for bone in rig.data.bones:
        kw = {'parent_matrix': desired[bone.parent.name], 'parent_matrix_local': bind[bone.parent.name]} if bone.parent else {}
        rig.pose.bones[bone.name].matrix_basis = bone.convert_local_to_pose(desired[bone.name], bind[bone.name], invert=True, **kw)
    bpy.context.view_layer.update()
    rig_error = float(np.abs(np.asarray([np.asarray(rig.pose.bones[n].matrix @ bind[n].inverted()) for n in names]) - old['rig_deformations'][frame]).max())
    assert rig_error < 1e-5
    physical_input = coords(cage)
    previous_input_error = float(np.abs(old_transfer.apply(physical_input) - old['actual_skin_targets'][frame]).max())
    assert previous_input_error < 1e-6
    actual = transfer.apply(old['actual_simulation_points'][frame])
    skin = transfer.apply(physical_input)
    actual_lengths = np.linalg.norm(actual[edges[:, 0]] - actual[edges[:, 1]], axis=1)
    pieces = []
    for part, inherited in zip(parts, r['frames'][frame]['pieces']):
        lo, hi = part['start'], part['start'] + part['vertices']
        selected = valid & (edges[:, 0] >= lo) & (edges[:, 0] < hi) & (edges[:, 1] >= lo) & (edges[:, 1] < hi)
        ratios = actual_lengths[selected] / lengths[selected]
        pieces.append({**inherited, 'maximumEdgeStretch': float(ratios.max()),
                       'edgeStretch95Percentile': float(np.percentile(ratios, 95)),
                       'bounds': [actual[lo:hi].min(0).tolist(), actual[lo:hi].max(0).tolist()]})
    error = np.linalg.norm(actual - skin, axis=1)
    rows.append({**r['frames'][frame], 'pieces': pieces,
                 'maximumFullyPinnedInputError': float(error[old['pin_weights'] > .999].max()),
                 'recordedRigReconstructionMaximumError': rig_error,
                 'previousDenseSkinInputReconstructionMaximumError': previous_input_error})
    points.append(actual)
    inputs.append(skin)
    physical_inputs.append(physical_input)
arrays = {name: old[name] for name in old.files}
arrays.update(points=np.asarray(points), actual_skin_targets=np.asarray(inputs), rest_points=logical_rest,
              actual_simulation_skin_targets=np.asarray(physical_inputs), **transfer.arrays())
data = out / 'actual_reconstructed_detail_frames.npz'
np.savez_compressed(data, **arrays)
preserved = ['actual_simulation_points', 'simulation_rest_points', 'simulation_faces', 'simulation_edges',
             'simulation_pin_weights', 'physical_seam_pairs', 'rig_deformations', 'bone_names']
for name in preserved: assert np.array_equal(arrays[name], old[name]), name
report = {**r, 'assembly': assembly, 'parts': parts, 'frames': rows, 'dataFile': str(data), 'dataSha256': sha(data),
          'scriptSha256': sha(__file__), 'retopoAssemblyHelperSha256': sha(Path(__file__).with_name('chapeleiro_retopo_cloth_assembly.py')),
          'sourcePhysicalProbe': str(Path(a.probe)), 'sourcePhysicalProbeSha256': sha(a.probe),
          'sourcePhysicalDataFile': r['dataFile'], 'sourcePhysicalDataSha256': r['dataSha256'],
          'sourcePhysicalSolverScriptSha256': r['scriptSha256'],
          'physicalSolverReexecutedInThisStep': False,
          'physicalClothSequenceReusedFromVerifiedCompletedProbe': True,
          'exactPreservedPhysicalArrays': preserved,
          'restDetailReconstructionMaximumError': transfer.rest_reconstruction_error,
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'exportedModelUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'sourcePhotoComparisonPending': True,
          'limitation': 'Only the detail-transfer tangent field changes. The physical trajectory is identical to the completed source probe; geometry, cloth contact, all adornments, rig bake and all-action fidelity remain pending.'}
(out / 'actual_sewn_solver_motion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_refinement.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_retopo_cloth_assembly.py'), out / 'executed_retopo_assembly.py')
print('ACTUAL_SMOOTH_DETAIL_TRANSFER_RECONSTRUCTED', len(rows), flush=True)
