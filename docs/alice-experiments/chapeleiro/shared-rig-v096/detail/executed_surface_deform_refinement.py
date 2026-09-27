"""Bind original detail to each actual regular carrier with Blender Surface Deform.

The recorded physical trajectory stays byte-exact. Only the original detail's
deformation is re-evaluated. Independent in-memory copies preserve all sources.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from collections import Counter
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
assert sha(g['editableBlend']) == g['editableBlendSha256'] == r['parentEditableSha256']
assert sha(r['dataFile']) == r['dataSha256']
assert sha(g['exports']['foundation']['sourcePhoto']) == r['sourcePhotoSha256']
assert len(r['frames']) == 29 and not out.exists()
old = np.load(r['dataFile'])
assert 'actual_simulation_skin_targets' in old.files
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
for pose in rig.pose.bones: pose.matrix_basis = Matrix.Identity(4)
scene.frame_set(1); bpy.context.view_layer.update()
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_sewn_cloth_assembly import _raw_hash

def coords(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    points = np.asarray([tuple(ev.matrix_world @ v.co) for v in mesh.vertices], np.float32)
    ev.to_mesh_clear()
    return points

copies, bindings, source_hashes, targets = [], [], {}, []
face_start = 0
for part in r['parts']:
    source = bpy.data.objects[part['source']]
    source_hashes[source.name] = _raw_hash(source)
    assert source_hashes[source.name] == part['sourceRawGeometrySha256']
    expected = old[part['key'] + '_original_world_points']
    actual_rest = np.asarray([tuple(source.matrix_world @ v.co) for v in source.data.vertices], np.float32)
    assert np.max(np.abs(actual_rest - expected)) < 1e-6
    faces = old['simulation_faces'][face_start:face_start + part['faces']]
    face_start += part['faces']
    ids, inverse = np.unique(faces, return_inverse=True)
    local_faces = inverse.reshape(-1, 4)
    face_counts = Counter(tuple(sorted((face[i], face[(i+1) % 4]))) for face in local_faces for i in range(4))
    assert max(face_counts.values()) <= 2
    mesh = bpy.data.meshes.new('Actual regular carrier target / ' + part['key'])
    mesh.from_pydata(old['simulation_rest_points'][ids].tolist(), [], local_faces.tolist())
    mesh.update()
    target = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(target)
    proxy = source.copy(); proxy.data = source.data.copy()
    proxy.name = 'Original high detail / actual Surface Deform / ' + part['key']
    world = source.matrix_world.copy()
    proxy.parent = None; proxy.matrix_world = world
    proxy.modifiers.clear()
    scene.collection.objects.link(proxy)
    modifier = proxy.modifiers.new('Actual regular carrier / native detail deformation', 'SURFACE_DEFORM')
    modifier.target = target
    copies.append(proxy); targets.append((target, ids))
    for collection in bpy.data.collections: collection.hide_viewport = False
    for obj in scene.objects:
        obj.hide_viewport = obj not in [*copies, *[t[0] for t in targets]]
        if not obj.hide_viewport: obj.hide_set(False)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    proxy.select_set(True); bpy.context.view_layer.objects.active = proxy
    bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    assert modifier.is_bound
    points = coords(proxy)
    assert points.shape == expected.shape
    error = float(np.max(np.abs(points - expected)))
    assert error < 1e-6
    bindings.append({'key': part['key'], 'source': source.name, 'independentCopy': proxy.name,
                     'target': target.name, 'actualTargetVertices': len(ids), 'actualTargetQuads': len(local_faces),
                     'actualTargetFaceEdgesWithMoreThanTwoFaces': 0,
                     'actualDenseVertices': len(points), 'actualBound': bool(modifier.is_bound),
                     'actualSurfaceDeformFalloff': modifier.falloff, 'actualSurfaceDeformStrength': modifier.strength,
                     'originalUvLayerNamesPreserved': [u.name for u in proxy.data.uv_layers] == [u.name for u in source.data.uv_layers],
                     'restMaximumError': error})

def evaluate(physical):
    for target, ids in targets:
        target.data.vertices.foreach_set('co', physical[ids].astype(np.float32).ravel())
        target.data.update()
    bpy.context.view_layer.update()
    actual = np.concatenate([coords(proxy) for proxy in copies])
    assert actual.shape == old['rest_points'].shape and np.isfinite(actual).all()
    return actual

rest = evaluate(old['simulation_rest_points'])
edges = old['edges']
lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
valid = lengths > 1e-6
points, inputs, rows = [], [], []
for frame in range(29):
    actual = evaluate(old['actual_simulation_points'][frame])
    skin = evaluate(old['actual_simulation_skin_targets'][frame])
    actual_lengths = np.linalg.norm(actual[edges[:, 0]] - actual[edges[:, 1]], axis=1)
    pieces = []
    for part, inherited in zip(r['parts'], r['frames'][frame]['pieces']):
        lo, hi = part['start'], part['start'] + part['vertices']
        selected = valid & (edges[:, 0] >= lo) & (edges[:, 0] < hi) & (edges[:, 1] >= lo) & (edges[:, 1] < hi)
        ratios = actual_lengths[selected] / lengths[selected]
        pieces.append({**inherited, 'maximumEdgeStretch': float(ratios.max()),
                       'edgeStretch95Percentile': float(np.percentile(ratios, 95)),
                       'bounds': [actual[lo:hi].min(0).tolist(), actual[lo:hi].max(0).tolist()]})
    rows.append({**r['frames'][frame], 'pieces': pieces,
                 'maximumFullyPinnedInputError': float(np.linalg.norm(actual-skin, axis=1)[old['pin_weights'] > .999].max()),
                 'actualAllFiveSurfaceDeformBindingsPresent': all(proxy.modifiers[0].is_bound for proxy in copies)})
    points.append(actual); inputs.append(skin)
    print('ACTUAL_SURFACE_DEFORM_TRANSFER', frame + 1, 29, flush=True)
assert {n: _raw_hash(bpy.data.objects[n]) for n in source_hashes} == source_hashes
arrays = {name: old[name] for name in old.files}
arrays.update(points=np.asarray(points), actual_skin_targets=np.asarray(inputs), rest_points=rest)
datafile = out / 'actual_surface_deform_detail_frames.npz'
np.savez_compressed(datafile, **arrays)
preserved = ['actual_simulation_points', 'actual_simulation_skin_targets', 'simulation_rest_points', 'simulation_faces',
             'simulation_edges', 'simulation_loose_edges', 'simulation_pin_weights', 'physical_seam_pairs', 'rig_deformations', 'bone_names']
for name in preserved: assert np.array_equal(arrays[name], old[name])
assembly = {**r['assembly'], 'detailTransferIsApproximationNotApproval': True,
            'detailUsesActualBlenderSurfaceDeform': True, 'inheritedTangentArraysNotUsedForNewDetailCoordinates': True}
report = {**r, 'assembly': assembly, 'frames': rows, 'dataFile': str(datafile), 'dataSha256': sha(datafile),
          'scriptSha256': sha(__file__), 'actualBlenderVersion': bpy.app.version_string,
          'sourcePhysicalProbe': str(Path(a.probe)), 'sourcePhysicalProbeSha256': sha(a.probe),
          'sourcePhysicalDataSha256': r['dataSha256'], 'sourcePhysicalSolverScriptSha256': r['scriptSha256'],
          'physicalSolverReexecutedInThisStep': False, 'exactPreservedPhysicalArrays': preserved,
          'actualSurfaceDeformBindings': bindings, 'sourceGeometryUvAndMaterialsNotEdited': True,
          'restDetailReconstructionMaximumError': max(b['restMaximumError'] for b in bindings),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'exportedModelUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'allLayersFinished': False, 'motionVerified': False, 'fidelityVerified': False, 'clothCollisionVerified': False,
          'responseBakedIntoRig': False, 'modelExported': False, 'finalFbxExported': False,
          'limitation': 'Only native detail deformation is evaluated. The physical spring gaps, penetration and coarse motion are unchanged. Other garments, all actions, rig bake and photo fidelity remain incomplete.'}
(out / 'actual_sewn_solver_motion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_surface_deform_refinement.py')
print('ACTUAL_SURFACE_DEFORM_DETAIL_SAVED', len(rows), flush=True)
