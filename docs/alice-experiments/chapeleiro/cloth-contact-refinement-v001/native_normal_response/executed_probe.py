"""Measure regular simulation quads and reconstruct the original garment detail."""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--warmup', type=int, default=12)
p.add_argument('--areal-density', type=float, default=.18)
p.add_argument('--around', type=int, default=96)
p.add_argument('--lowpass', type=int, default=10)
p.add_argument('--tier-rows', type=int, default=5)
p.add_argument('--inplane-stiffness-scale', type=float, default=1.)
p.add_argument('--outward-winding', action=argparse.BooleanOptionalAction, default=True)
p.add_argument('--solver-quality', type=int)
p.add_argument('--seam-mode', choices=['welded', 'springs'], default='welded')
p.add_argument('--seam-clearance', type=float, default=.0015)
p.add_argument('--collider-normal-response', action=argparse.BooleanOptionalAction, default=False)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert a.warmup > 0 and a.areal_density > 0 and a.inplane_stiffness_scale > 0
assert a.solver_quality is None or a.solver_quality > 0
path, out = Path(a.generation), Path(a.output)
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g = read(path)
reference_root = Path(g.get('authoringReferenceRoot', path.parent))
schema, audit = read(reference_root / 'shared_rig_bind.json'), read(reference_root / 'skin_audit.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert not out.exists()
out.mkdir(parents=True)
start = time.time()
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_retopo_cloth_assembly import assemble_retopo_petticoats
from chapeleiro_cloth_colliders import thin_underlayer_colliders
from chapeleiro_cloth_motion_entry import rest_transition_action
from chapeleiro_cloth_material_settings import scale_inplane_stiffness
cage, parts, assembly = assemble_retopo_petticoats(scene, rig, schema, a.around, a.lowpass, a.tier_rows,
                                                 outward_winding=a.outward_winding, seam_mode=a.seam_mode, seam_clearance=a.seam_clearance)
original = assembly.pop('originalPointsByPart')
transfer = assembly.pop('detailTransfer')
ownership = assembly.pop('partSolverOwnership')
physical_seam_pairs = assembly.pop('physicalSeamPairs')
measurement_edges = assembly.pop('measurementEdges')
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
if a.solver_quality is not None: cloth.settings.quality = a.solver_quality
# A controlled material study changes only resistance to stretching/shearing;
# bending, damping, resolution, mass density, pins and collisions stay fixed.
scale_inplane_stiffness(cloth.settings, inherited_settings, a.inplane_stiffness_scale)
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
cloth.settings.mass = a.areal_density * surface_area / len(rest_world)
mass_calibration = {
    'mode': 'areal', 'actualBlenderVersion': bpy.app.version_string,
    'installedMassPropertyDescription': cloth.settings.bl_rna.properties['mass'].description,
    'massSemanticsPrimarySource': 'https://github.com/blender/blender/blob/main/source/blender/blenkernel/intern/cloth.cc',
    'surfaceAreaSquareMeters': surface_area, 'vertices': len(rest_world),
    'assumedArealDensityKgPerSquareMeter': a.areal_density,
    'densityIsProvisionalMaterialAssumption': True,
    'inheritedMassPerVertexKg': inherited_mass,
    'inheritedTotalMassKg': inherited_mass * len(rest_world),
    'actualMassPerVertexKg': float(cloth.settings.mass),
    'actualTotalMassKg': float(cloth.settings.mass) * len(rest_world),
    'uniformVertexMassCannotRepresentDifferentLocalSamplingDensities': True,
    'parts': []}
seen_mass_vertices, face_start = set(), 0
for i, part in enumerate(parts):
    lo, hi = part['start'], part['start'] + part['vertices']
    local = (triangle_polygons >= face_start) & (triangle_polygons < face_start + part['faces'])
    face_start += part['faces']
    area = float(triangle_area[local].sum())
    owned = set(ownership[i].tolist())
    seen_mass_vertices.update(owned)
    mass = float(cloth.settings.mass) * len(owned)
    mass_calibration['parts'].append({'key': part['key'], 'areaSquareMeters': area,
                                    'allocatedUniqueSolverVertices': len(owned), 'sharedSeamMassAllocatedToSupport': a.seam_mode == 'welded',
                                    'actualMassKg': mass, 'effectiveArealDensityKgPerSquareMeter': mass / area})
(out / 'mass_calibration.json').write_text(json.dumps(mass_calibration, indent=2) + '\n', encoding='utf-8', newline='\n')
print('ACTUAL_MASS_CALIBRATION', json.dumps(mass_calibration), flush=True)
cloth.settings.use_sewing_springs = a.seam_mode == 'springs'
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
for obj, row in zip(colliders, collider_rows):
    obj.modifiers.new('Actual animated underlayer / coupled petticoats', 'COLLISION')
    row['inheritedInstalledCollisionSettings'] = copy_settings(obj.collision, None)
    obj.collision.thickness_outer = obj.collision.thickness_inner = .0008
    obj.collision.cloth_friction = 5
    if a.collider_normal_response:
        obj.collision.use_normal = True
    row['actualInstalledCollisionSettings'] = copy_settings(obj.collision, None)
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
rest = transfer.apply(simulation_rest)
raw_edges = np.empty(len(cage.data.edges) * 2, np.int32)
cage.data.edges.foreach_get('vertices', raw_edges)
physical_edges = raw_edges.reshape(-1, 2)
edges = measurement_edges
loose = np.zeros(len(edges), bool)
lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
valid = (lengths > 1e-6) & ~loose
pin_index = cage.vertex_groups['pinned'].index
simulation_pins = np.asarray([next((w.weight for w in v.groups if w.group == pin_index), 0.) for v in cage.data.vertices], np.float32)
pins = np.sum(simulation_pins[transfer.indices] * transfer.weights, axis=1)
physical_lengths = np.linalg.norm(simulation_rest[physical_edges[:, 0]] - simulation_rest[physical_edges[:, 1]], axis=1)
assert physical_lengths.min() > 1e-6
part_edges = []
face_start = 0
for part in parts:
    pairs = set()
    for poly in list(cage.data.polygons)[face_start:face_start + part['faces']]:
        ids = list(poly.vertices)
        pairs.update(tuple(sorted((ids[i], ids[(i + 1) % 4]))) for i in range(4))
    face_start += part['faces']
    part_edges.append(np.asarray(sorted(pairs), np.int32))
physical_quality = []
for part, pairs in zip(parts, part_edges):
    lengths_part = np.linalg.norm(simulation_rest[pairs[:, 0]] - simulation_rest[pairs[:, 1]], axis=1)
    physical_quality.append({'key': part['key'], 'minimumEdgeLengthMeters': float(lengths_part.min()),
                             'edgeLength05PercentileMeters': float(np.percentile(lengths_part, 5)),
                             'edgeLength95PercentileMeters': float(np.percentile(lengths_part, 95)),
                             'maximumEdgeLengthMeters': float(lengths_part.max())})
names = [b.name for b in rig.data.bones]
inverse = [b.matrix_local.inverted() for b in rig.data.bones]
points, simulation_points, inputs, simulation_inputs, matrices, rows = [], [], [], [], [], []
for frame in range(1, end + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    physical, physical_skin = coords(cage), coords(target)
    actual, skin = transfer.apply(physical), transfer.apply(physical_skin)
    assert actual.shape == skin.shape == rest.shape and np.isfinite(actual).all() and cloth.show_viewport
    edge_lengths = np.linalg.norm(actual[edges[:, 0]] - actual[edges[:, 1]], axis=1)
    seam_lengths = np.linalg.norm(physical[physical_seam_pairs[:, 0]] - physical[physical_seam_pairs[:, 1]], axis=1)
    error = np.linalg.norm(actual - skin, axis=1)
    measurements = []
    for part, pairs in zip(parts, part_edges):
        lo, hi = part['start'], part['start'] + part['vertices']
        local_edges = valid & (edges[:, 0] >= lo) & (edges[:, 0] < hi) & (edges[:, 1] >= lo) & (edges[:, 1] < hi)
        ratios = edge_lengths[local_edges] / lengths[local_edges]
        solver_ratios = np.linalg.norm(physical[pairs[:, 0]] - physical[pairs[:, 1]], axis=1) / np.linalg.norm(simulation_rest[pairs[:, 0]] - simulation_rest[pairs[:, 1]], axis=1)
        measurements.append({'key': part['key'], 'maximumEdgeStretch': float(ratios.max()),
                             'edgeStretch95Percentile': float(np.percentile(ratios, 95)),
                             'solverMaximumEdgeStretch': float(solver_ratios.max()),
                             'solverEdgeStretch95Percentile': float(np.percentile(solver_ratios, 95)),
                             'bounds': [actual[lo:hi].min(0).tolist(), actual[lo:hi].max(0).tolist()]})
    rows.append({'frame': frame, 'pieces': measurements, 'maximumSeamGapMeters': float(seam_lengths.max()),
                 'seamGap95PercentileMeters': float(np.percentile(seam_lengths, 95)),
                 'maximumFullyPinnedInputError': float(error[pins > .999].max()),
                 'maximumPhysicalFullyPinnedInputError': float(np.linalg.norm(physical-physical_skin, axis=1)[simulation_pins > .999].max()),
                 'cacheInfo': cloth.point_cache.info, 'cacheOutdated': bool(cloth.point_cache.is_outdated)})
    points.append(actual)
    simulation_points.append(physical)
    inputs.append(skin)
    simulation_inputs.append(physical_skin)
    matrices.append([np.asarray(rig.pose.bones[n].matrix @ inv) for n, inv in zip(names, inverse)])
    print('ACTUAL_SEWN_CLOTH_FRAME', frame, end, round(time.time() - start, 2), flush=True)
    if frame % 2 == 0:
        (out / 'progress.json').write_text(json.dumps({'completed': False, 'lastActualFrame': frame, 'plannedFrames': end, 'frames': rows}) + '\n', encoding='utf-8', newline='\n')
data = out / 'actual_sewn_petticoat_frames.npz'
np.savez_compressed(data, points=np.asarray(points), actual_skin_targets=np.asarray(inputs), rest_points=rest,
                    edges=edges, loose_edges=loose, pin_weights=pins, rig_deformations=np.asarray(matrices), bone_names=np.asarray(names),
                    actual_simulation_points=np.asarray(simulation_points), actual_simulation_skin_targets=np.asarray(simulation_inputs), simulation_rest_points=simulation_rest,
                    simulation_edges=physical_edges, simulation_pin_weights=simulation_pins,
                    simulation_loose_edges=np.asarray([e.is_loose for e in cage.data.edges], bool),
                    physical_seam_pairs=physical_seam_pairs,
                    simulation_faces=np.asarray([tuple(p.vertices) for p in cage.data.polygons], np.int32),
                    **transfer.arrays(),
                    **{key + '_original_world_points': value for key, value in original.items()})
report = {'parentEditableSha256': g['editableBlendSha256'], 'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'],
          'actualSolver': 'One Blender Cloth solver on regular independent simulation quads with mutual self-collision and ' + a.seam_mode + ' seam attachment',
          'assembly': assembly, 'parts': parts, 'actualColliders': collider_rows,
          'seamMode': a.seam_mode + '_regular_carriers',
          'physicalRestEdgeQuality': physical_quality,
          'logicalPointsReconstructOriginalRestDetailThroughRotatingTangentFrames': True,
          'restDetailReconstructionMaximumError': transfer.rest_reconstruction_error,
          'inheritedIvorySolverSettings': inherited_settings,
          'provisionalInplaneStiffnessScale': a.inplane_stiffness_scale,
          'requestedSolverQuality': a.solver_quality,
          'requestedColliderNormalResponse': a.collider_normal_response,
          'massCalibration': mass_calibration,
          'actualSolverSettings': copy_settings(cloth.settings, None),
          'actualCollisionSettings': copy_settings(cloth.collision_settings, None),
          'sourceAction': action.name, 'localAction': local.name, 'initialRestTransformMaximumError': initial_error,
          'actualModifierOrder': [m.type for m in cage.modifiers], 'clothNeverBypassedDuringSequence': True,
          'frames': rows, 'dataFile': str(data), 'dataSha256': sha(data), 'scriptSha256': sha(__file__),
          'assemblyHelperSha256': sha(Path(__file__).with_name('chapeleiro_sewn_cloth_assembly.py')),
          'retopoAssemblyHelperSha256': sha(Path(__file__).with_name('chapeleiro_retopo_cloth_assembly.py')),
          'fieldHelperSha256': sha(Path(__file__).with_name('chapeleiro_shared_rig_fields.py')),
          'entryHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_motion_entry.py')),
          'colliderHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_colliders.py')),
          'materialSettingsHelperSha256': sha(Path(__file__).with_name('chapeleiro_cloth_material_settings.py')),
          'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'exportedModelUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'responseBakedIntoRig': False, 'modelExported': False, 'finalFbxExported': False,
          'allLayersFinished': False, 'clothCollisionVerified': False, 'motionVerified': False, 'fidelityVerified': False,
          'limitation': 'Original visual rest coordinates are retained through approximate tangent-frame detail transfer. Fine lace, other garments, hidden body, all actions and rig baking still require completion.',
          'elapsedSeconds': time.time() - start}
(out / 'actual_sewn_solver_motion.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_probe.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_sewn_cloth_assembly.py'), out / 'executed_assembly.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_retopo_cloth_assembly.py'), out / 'executed_retopo_assembly.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_cloth_material_settings.py'), out / 'executed_material_settings.py')
print('ACTUAL_SEWN_PETTICOATS_SAVED', end, flush=True)
