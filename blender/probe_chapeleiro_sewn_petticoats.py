"""Measure sewn petticoats and mutual self-collision in one actual Cloth solver."""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--assembly', choices=['ivory_black', 'black_only'], default='ivory_black')
p.add_argument('--sewing-force', type=float, default=.25)
p.add_argument('--warmup', type=int, default=12)
p.add_argument('--mass-mode', choices=['inherited', 'areal'], default='inherited')
p.add_argument('--areal-density', type=float, default=.18)
p.add_argument('--seam-mode', choices=['springs', 'welded'], default='springs')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert a.sewing_force > 0 and a.warmup > 0 and a.areal_density > 0
path, out = Path(a.generation), Path(a.output)
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g, schema, audit = read(path), read(path.parent / 'shared_rig_bind.json'), read(path.parent / 'skin_audit.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert not out.exists()
out.mkdir(parents=True)
start = time.time()
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_sewn_cloth_assembly import assemble_sewn_petticoats
from chapeleiro_cloth_colliders import thin_underlayer_colliders
from chapeleiro_cloth_motion_entry import rest_transition_action
if a.seam_mode == 'welded':
    from chapeleiro_welded_cloth_assembly import assemble_welded_petticoats
    cage, parts, assembly = assemble_welded_petticoats(scene, rig, schema, include_ivory=a.assembly == 'ivory_black')
else:
    cage, parts, assembly = assemble_sewn_petticoats(scene, rig, schema, include_ivory=a.assembly == 'ivory_black')
original = assembly.pop('originalPointsByPart')
logical_mapping = assembly.pop('logicalVertexToSimulationVertex', np.arange(len(cage.data.vertices), dtype=np.int32))
measurement_edges = assembly.pop('measurementEdges', None)
measurement_loose = assembly.pop('measurementLooseEdges', None)
source = bpy.data.objects['01 / long ivory gathered petticoat / petticoat simulation midsurface']
source_cloth = next(m for m in source.modifiers if m.type == 'CLOTH')
cloth = cage.modifiers.new('Actual sewn petticoats / coupled self-collision', 'CLOTH')
def copy_settings(source, target):
    values = {}
    for prop in source.bl_rna.properties:
        key = prop.identifier
        if key == 'rna_type' or prop.is_readonly or prop.type not in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}: continue
        value = getattr(source, key)
        if target is not None: setattr(target, key, value)
        values[key] = list(value) if getattr(prop, 'is_array', False) else value
    return values
inherited_settings = copy_settings(source_cloth.settings, cloth.settings)
copy_settings(source_cloth.collision_settings, cloth.collision_settings)
# Blender mass is uniform per vertex, not kilograms per square metre. Measure
# the actual world-space rest surface, excluding loose sewing edges.
cage.data.calc_loop_triangles()
rest_world = np.asarray([tuple(cage.matrix_world @ v.co) for v in cage.data.vertices], np.float64)
triangles = np.asarray([tuple(t.vertices) for t in cage.data.loop_triangles], np.int32)
triangle_area = .5 * np.linalg.norm(np.cross(rest_world[triangles[:, 1]] - rest_world[triangles[:, 0]],
                                            rest_world[triangles[:, 2]] - rest_world[triangles[:, 0]]), axis=1)
triangle_polygons = np.asarray([t.polygon_index for t in cage.data.loop_triangles], np.int32)
surface_area = float(triangle_area.sum())
assert surface_area > 0
inherited_mass = float(cloth.settings.mass)
if a.mass_mode == 'areal':
    cloth.settings.mass = a.areal_density * surface_area / len(rest_world)
mass_calibration = {
    'mode': a.mass_mode, 'actualBlenderVersion': bpy.app.version_string,
    'installedMassPropertyDescription': cloth.settings.bl_rna.properties['mass'].description,
    'massSemanticsPrimarySource': 'https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/cloth.cc',
    'surfaceAreaSquareMeters': surface_area, 'vertices': len(rest_world),
    'assumedArealDensityKgPerSquareMeter': a.areal_density if a.mass_mode == 'areal' else None,
    'densityIsProvisionalMaterialAssumption': True,
    'inheritedMassPerVertexKg': inherited_mass,
    'inheritedTotalMassKg': inherited_mass * len(rest_world),
    'actualMassPerVertexKg': float(cloth.settings.mass),
    'actualTotalMassKg': float(cloth.settings.mass) * len(rest_world),
    'uniformVertexMassCannotRepresentDifferentLocalSamplingDensities': True,
    'parts': []}
seen_mass_vertices, face_start = set(), 0
for part in parts:
    lo, hi = part['start'], part['start'] + part['vertices']
    local = (triangle_polygons >= face_start) & (triangle_polygons < face_start + part['faces'])
    face_start += part['faces']
    area = float(triangle_area[local].sum())
    owned = set(logical_mapping[lo:hi].tolist()) - seen_mass_vertices
    seen_mass_vertices.update(owned)
    mass = float(cloth.settings.mass) * len(owned)
    mass_calibration['parts'].append({'key': part['key'], 'areaSquareMeters': area,
                                    'allocatedUniqueSolverVertices': len(owned), 'sharedSeamMassAllocatedToSupport': a.seam_mode == 'welded',
                                    'actualMassKg': mass, 'effectiveArealDensityKgPerSquareMeter': mass / area})
(out / 'mass_calibration.json').write_text(json.dumps(mass_calibration, indent=2) + '\n', encoding='utf-8', newline='\n')
print('ACTUAL_MASS_CALIBRATION', json.dumps(mass_calibration), flush=True)
cloth.settings.use_sewing_springs = a.seam_mode == 'springs'
cloth.settings.sewing_force_max = a.sewing_force
cloth.settings.use_dynamic_mesh = False
cloth.collision_settings.use_self_collision = True
cloth.show_viewport = False  # Only while constructing the local motion action.
for track in rig.animation_data.nla_tracks: track.mute = True
action = next(x for x in bpy.data.actions if x.name.startswith('Run / current fitted'))
local, end, initial_error = rest_transition_action(rig, action, a.warmup, 1)
cloth.show_viewport = True
assert end == a.warmup + 17
collider_names = ['01 / left stocking / fitted leg ankle and closed toe', '01 / right stocking / fitted leg ankle and closed toe',
                  '01 / bloomers / continuous waist and sewn crotch']
colliders, collider_rows = thin_underlayer_colliders(scene, audit, collider_names, rig)
for obj in colliders:
    obj.modifiers.new('Actual animated underlayer / coupled petticoats', 'COLLISION')
    obj.collision.thickness_outer = obj.collision.thickness_inner = .0008
    obj.collision.cloth_friction = 5
target = cage.copy()
target.name = 'Measurement only / identical sewn assembly Armature input'
scene.collection.objects.link(target)
target.modifiers.remove(next(m for m in target.modifiers if m.type == 'CLOTH'))
for collection in bpy.data.collections: collection.hide_viewport = False
active = {rig, cage, target, *colliders}
for obj in scene.objects:
    obj.hide_viewport = obj not in active
    obj.hide_render = True
    if obj in active: obj.hide_set(False)
scene.frame_start, scene.frame_end = 1, end
cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, end
assert cloth.settings.vertex_group_mass == 'pinned'
def coords(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    m = np.asarray(ev.matrix_world)
    result = xyz.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    ev.to_mesh_clear()
    return result
simulation_rest = np.asarray([tuple(cage.matrix_world @ v.co) for v in cage.data.vertices], np.float32)
rest = simulation_rest[logical_mapping]
raw_edges = np.empty(len(cage.data.edges) * 2, np.int32)
cage.data.edges.foreach_get('vertices', raw_edges)
edges = raw_edges.reshape(-1, 2) if measurement_edges is None else measurement_edges
loose = np.asarray([e.is_loose for e in cage.data.edges], bool) if measurement_loose is None else measurement_loose
lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
valid = (lengths > 1e-6) & ~loose
pin_index = cage.vertex_groups['pinned'].index
simulation_pins = np.asarray([next((w.weight for w in v.groups if w.group == pin_index), 0.) for v in cage.data.vertices], np.float32)
pins = simulation_pins[logical_mapping]
names = [b.name for b in rig.data.bones]
inverse = [b.matrix_local.inverted() for b in rig.data.bones]
points, simulation_points, inputs, matrices, rows = [], [], [], [], []
for frame in range(1, end + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    physical, physical_skin = coords(cage), coords(target)
    actual, skin = physical[logical_mapping], physical_skin[logical_mapping]
    assert actual.shape == skin.shape == rest.shape and np.isfinite(actual).all() and cloth.show_viewport
    edge_lengths = np.linalg.norm(actual[edges[:, 0]] - actual[edges[:, 1]], axis=1)
    seam_lengths = edge_lengths[loose]
    error = np.linalg.norm(actual - skin, axis=1)
    measurements = []
    for part in parts:
        lo, hi = part['start'], part['start'] + part['vertices']
        local_edges = valid & (edges[:, 0] >= lo) & (edges[:, 0] < hi) & (edges[:, 1] >= lo) & (edges[:, 1] < hi)
        ratios = edge_lengths[local_edges] / lengths[local_edges]
        measurements.append({'key': part['key'], 'maximumEdgeStretch': float(ratios.max()),
                             'edgeStretch95Percentile': float(np.percentile(ratios, 95)),
                             'bounds': [actual[lo:hi].min(0).tolist(), actual[lo:hi].max(0).tolist()]})
    rows.append({'frame': frame, 'pieces': measurements, 'maximumSeamGapMeters': float(seam_lengths.max()),
                 'seamGap95PercentileMeters': float(np.percentile(seam_lengths, 95)),
                 'maximumFullyPinnedInputError': float(error[pins > .999].max()),
                 'cacheInfo': cloth.point_cache.info, 'cacheOutdated': bool(cloth.point_cache.is_outdated)})
    points.append(actual)
    simulation_points.append(physical)
    inputs.append(skin)
    matrices.append([np.asarray(rig.pose.bones[n].matrix @ inv) for n, inv in zip(names, inverse)])
    print('ACTUAL_SEWN_CLOTH_FRAME', frame, end, round(time.time() - start, 2), flush=True)
    if frame % 2 == 0:
        (out / 'progress.json').write_text(json.dumps({'completed': False, 'lastActualFrame': frame, 'plannedFrames': end, 'frames': rows}) + '\n', encoding='utf-8', newline='\n')
data = out / 'actual_sewn_petticoat_frames.npz'
np.savez_compressed(data, points=np.asarray(points), actual_skin_targets=np.asarray(inputs), rest_points=rest,
                    edges=edges, loose_edges=loose, pin_weights=pins, rig_deformations=np.asarray(matrices), bone_names=np.asarray(names),
                    actual_simulation_points=np.asarray(simulation_points), simulation_rest_points=simulation_rest,
                    logical_vertex_to_simulation_vertex=logical_mapping, simulation_pin_weights=simulation_pins,
                    **{key + '_original_world_points': value for key, value in original.items()})
report = {'parentEditableSha256': g['editableBlendSha256'], 'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'],
          'actualSolver': 'One Blender Cloth solver with mutual self-collision and ' + ('explicit welded seam vertices' if a.seam_mode == 'welded' else 'sewing springs'),
          'assembly': assembly, 'parts': parts, 'actualColliders': collider_rows,
          'seamMode': a.seam_mode,
          'inheritedIvorySolverSettings': inherited_settings,
          'massCalibration': mass_calibration,
          'actualSolverSettings': copy_settings(cloth.settings, None),
          'actualCollisionSettings': copy_settings(cloth.collision_settings, None),
          'sourceAction': action.name, 'localAction': local.name, 'initialRestTransformMaximumError': initial_error,
          'actualModifierOrder': [m.type for m in cage.modifiers], 'clothNeverBypassedDuringSequence': True,
          'frames': rows, 'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'assemblyHelperSha256': sha(Path(__file__).with_name('chapeleiro_sewn_cloth_assembly.py')),
          'weldedAssemblyHelperSha256': sha(Path(__file__).with_name('chapeleiro_welded_cloth_assembly.py')) if a.seam_mode == 'welded' else None,
          'fieldHelperSha256': sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
          'entryHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_motion_entry.py')),
          'colliderHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_colliders.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'exportedModelUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'responseBakedIntoRig': False, 'modelExported': False, 'finalFbxExported': False,
          'allLayersFinished': False, 'clothCollisionVerified': False, 'motionVerified': False, 'fidelityVerified': False,
          'limitation': 'Source geometry is preserved; only simulation flounce roots are aligned. Fine lace, other garments, hidden body and all-action fidelity still require completion.',
          'elapsedSeconds': time.time() - start}
(out / 'actual_sewn_solver_motion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_probe.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_sewn_cloth_assembly.py'), out / 'executed_assembly.py')
if a.seam_mode == 'welded': shutil.copyfile(Path(__file__).with_name('chapeleiro_welded_cloth_assembly.py'), out / 'executed_welded_assembly.py')
print('ACTUAL_SEWN_PETTICOATS_SAVED', end, flush=True)
