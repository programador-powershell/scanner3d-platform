"""Make the actual bloomer waist follow the same torso field as the skirt anchors.

Keep the original rest geometry, UV, materials, cloth fields, rig and actions.
Only bone weights above the measured waist transition change in independent
local mesh copies. Preserve the complete editable checkpoint without trimming.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from collections import defaultdict
import bpy
import numpy as np
from mathutils import Matrix

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--lower', type=float, default=.55)
p.add_argument('--upper', type=float, default=.61)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert a.lower < a.upper
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g = read(path)
reference_root = Path(g.get('authoringReferenceRoot', path.parent))
schema, audit = read(reference_root / 'shared_rig_bind.json'), read(reference_root / 'skin_audit.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
for pose in rig.pose.bones: pose.matrix_basis = Matrix.Identity(4)
scene.frame_set(1); bpy.context.view_layer.update()
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_shared_rig_fields import GarmentFields, blend, smooth, WEIGHT_QUANTIZATION
from chapeleiro_sewn_cloth_assembly import _raw_hash
fields = GarmentFields(rig, schema['clothFamilies'])
bone_names = {b.name for b in rig.data.bones}
objects = [bpy.data.objects[p['mesh']] for p in audit['pieces'] if 'bloomers' in p['mesh']]
objects += [bpy.data.objects[p['mesh']] for p in audit['authoringCages'] if 'bloomers' in p['receiver']]
assert len(objects) == 20 and len(set(objects)) == 20
all_geometry_before = {o.name: _raw_hash(o) for o in scene.objects if o.type == 'MESH'}
def curve_hash(action):
    curves = [(fc.data_path, fc.array_index, [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right), k.interpolation) for k in fc.keyframe_points])
              for layer in action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
    return hashlib.sha256(json.dumps(curves, sort_keys=True).encode()).hexdigest()
actions = {s.action for t in rig.animation_data.nla_tracks for s in t.strips}
before_actions = {act.name: curve_hash(act) for act in actions}
assert len(actions) == 5
rows = []
for obj in objects:
    world = np.asarray([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices], np.float32)
    selected = np.flatnonzero(world[:, 2] > a.lower)
    if not len(selected): continue
    by_index = {group.index: group.name for group in obj.vertex_groups}
    old_weights = [{by_index[w.group]: w.weight for w in obj.data.vertices[int(i)].groups if by_index[w.group] in bone_names} for i in selected]
    assert all(old_weights)
    non_bone_before = [[(by_index[w.group], w.weight) for w in v.groups if by_index[w.group] not in bone_names] for v in obj.data.vertices]
    uv_before = [(layer.name, [tuple(v.uv) for v in layer.data]) for layer in obj.data.uv_layers]
    below_before = [[(by_index[w.group], w.weight) for w in obj.data.vertices[int(i)].groups if by_index[w.group] in bone_names] for i in np.flatnonzero(world[:, 2] <= a.lower)]
    obj.data = obj.data.copy()
    for group in obj.vertex_groups:
        if group.name in bone_names: group.remove(selected.tolist())
    batches, maximum_delta = defaultdict(list), 0.
    for index, old in zip(selected, old_weights):
        point = obj.matrix_world @ obj.data.vertices[int(index)].co
        factor = smooth((point.z-a.lower)/(a.upper-a.lower))
        weights = blend(old, fields.torso(point), factor)
        quantized = {name: round(value * WEIGHT_QUANTIZATION) for name, value in weights.items()}
        quantized[max(weights, key=weights.get)] += WEIGHT_QUANTIZATION - sum(quantized.values())
        maximum_delta = max(maximum_delta, max(abs(quantized.get(name, 0)/WEIGHT_QUANTIZATION-old.get(name, 0)) for name in set(old)|set(weights)))
        for name, value in quantized.items():
            if value > 0: batches[(name, value)].append(int(index))
    for (name, value), ids in batches.items():
        group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
        group.add(ids, value / WEIGHT_QUANTIZATION, 'REPLACE')
    names_after = {group.index: group.name for group in obj.vertex_groups}
    assert non_bone_before == [[(names_after[w.group], w.weight) for w in v.groups if names_after[w.group] not in bone_names] for v in obj.data.vertices]
    assert uv_before == [(layer.name, [tuple(v.uv) for v in layer.data]) for layer in obj.data.uv_layers]
    assert below_before == [[(names_after[w.group], w.weight) for w in obj.data.vertices[int(i)].groups if names_after[w.group] in bone_names] for i in np.flatnonzero(world[:, 2] <= a.lower)]
    actual = [[w.weight for w in v.groups if names_after[w.group] in bone_names] for v in obj.data.vertices]
    assert max(len(w) for w in actual) <= 4 and max(abs(sum(w)-1) for w in actual) < 1e-7
    rows.append({'object': obj.name, 'vertices': len(world), 'waistVerticesUpdated': len(selected),
                 'maximumSingleInfluenceWeightChange': maximum_delta,
                 'sourceRestGeometryUnchanged': _raw_hash(obj) == all_geometry_before[obj.name],
                 'actualUvCoordinatesAndNonBoneClothFieldsUnchanged': True,
                 'boneWeightsAtOrBelowTransitionUnchanged': True, 'maximumInfluences': max(len(w) for w in actual),
                 'maximumNormalizationError': max(abs(sum(w)-1) for w in actual)})
assert {o.name: _raw_hash(o) for o in scene.objects if o.type == 'MESH'} == all_geometry_before
assert {act.name: curve_hash(act) for act in actions} == before_actions
file = out / 'chapeleiro_shared_rig_bloomer_waist.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(file), check_existing=False)
assert file.stat().st_size > 100 * 1024 * 1024
assert sha(g['editableBlend']) == g['editableBlendSha256']
report = {'parentGeneration': str(path), 'parentEditableSha256': g['editableBlendSha256'],
          'editableBlend': str(file), 'editableBlendSha256': sha(file), 'editableBytes': file.stat().st_size,
          'actualBlenderVersion': bpy.app.version_string, 'actualEditedObjects': rows,
          'lowerTransitionMeters': a.lower, 'upperTransitionMeters': a.upper,
          'torsoWeightFieldSharedWithSkirtAnchors': True, 'allActualRestMeshesUnchanged': True,
          'allFiveActualActionCurvesUnchanged': True, 'actualActionCurveHashes': before_actions,
          'sharedRigBoneNamesAndTopologyUnchanged': True, 'bones': len(rig.data.bones),
          'parentEditableUnchanged': True, 'scriptSha256': sha(__file__),
          'fieldHelperSha256': sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
          'modelExported': False, 'allLayersFinished': False, 'fidelityVerified': False,
          'motionVerified': False, 'clothCollisionVerified': False, 'finalFbxExported': False,
          'limitation': 'Only upper bloomer bone weights change. Contact and all-action appearance require actual new motion inspection; rest geometry fidelity is still incomplete.'}
(out / 'waist_skin_refinement.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
new_g = {**g, 'parentGeneration': str(path), 'editableBlend': str(file), 'editableBlendSha256': sha(file),
         'editableBytes': file.stat().st_size, 'authoringReferenceRoot': str(reference_root),
         'exportsInheritedForReferenceOnly': True, 'modelExportedInThisRefinement': False,
         'method': 'Existing complete shared rig checkpoint with upper bloomer weights fitted to the skirt torso anchor field',
         'waistSkinRefinement': str(out / 'waist_skin_refinement.json'), 'allLayersFinished': False,
         'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False,
         'finalFbxExported': False, 'nextVariantMayStart': False,
         'publicationStatus': 'local_authoring_checkpoint_not_exported', 'additionalCreditsConsumed': 0}
(out / 'generation.json').write_text(json.dumps(new_g, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_waist_skin_refinement.py')
print('ACTUAL_BLOOMER_WAIST_SKIN_SAVED', len(rows), file.stat().st_size, flush=True)
