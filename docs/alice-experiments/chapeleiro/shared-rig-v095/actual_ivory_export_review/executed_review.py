"""Measure and render the actual reimported foundation's additional cloth clip."""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--fit', required=True)
p.add_argument('--output', required=True)
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g, fit = read(args.generation), read(args.fit)
entry = g['exports']['foundation']
assert sha(entry['model']) == entry['modelSha256']
assert sha(entry['sourcePhoto']) == entry['sourcePhotoSha256'] == fit['sourcePhotoSha256']
assert sha(fit['dataFile']) == fit['dataSha256']
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
data = np.load(fit['dataFile'])
names = data['bone_names'].tolist()
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=entry['model'])
scene = bpy.context.scene
rigs = [o for o in scene.objects if o.type == 'ARMATURE']
assert len(rigs) == 1
rig = rigs[0]
assert set(names).issubset(rig.data.bones.keys())
meshes = [o for o in scene.objects if o.type == 'MESH' and
          any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
assert len(meshes) == 229
for obj in scene.objects:
    if obj.type == 'MESH' and obj not in meshes:
        obj.hide_render = True
main = next(o for o in meshes if o.name == '01 / long ivory gathered petticoat')
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()

def coords(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    matrix = np.asarray(evaluated.matrix_world)
    result = xyz.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    edges = np.empty(len(mesh.edges) * 2, np.int32)
    mesh.edges.foreach_get('vertices', edges)
    evaluated.to_mesh_clear()
    return result, edges.reshape(-1, 2)

rest, edges = coords(main)
rest_lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
valid = rest_lengths > 1e-5
rest_bounds = np.asarray([row for obj in meshes for row in [coords(obj)[0].min(0), coords(obj)[0].max(0)]])
rig.data.pose_position = 'POSE'
action = next(a for a in bpy.data.actions if a.name == g['ivoryStudyClip'])
rig.animation_data.action = action
if action.slots:
    rig.animation_data.action_slot = action.slots[0]
first, last = action.frame_range
bind_inverse = {n: rig.data.bones[n].matrix_local.inverted() for n in names}
world = np.asarray(rig.matrix_world)
inverse = np.linalg.inv(world)
points, matrices, rows = [], [], []
for i, expected in enumerate(data['rig_deformations']):
    frame = first + (last - first) * i / (len(data['rig_deformations']) - 1)
    scene.frame_set(math.floor(frame), subframe=frame % 1)
    bpy.context.view_layer.update()
    actual = np.array([world @ np.asarray(rig.pose.bones[n].matrix @ bind_inverse[n]) @ inverse for n in names])
    error = float(np.abs(actual - expected).max())
    assert error < 2e-5, (i, error)
    xyz, actual_edges = coords(main)
    assert np.array_equal(edges, actual_edges) and np.isfinite(xyz).all()
    ratios = np.linalg.norm(xyz[edges[:, 0]] - xyz[edges[:, 1]], axis=1)[valid] / rest_lengths[valid]
    rows.append({'sourcePhysicsFrame': i + 1, 'actualImportedFrame': frame,
                 'actualExportedJointDeformationMaximumError': error,
                 'actualMainPetticoatEdgeStretchMaximum': float(ratios.max()),
                 'actualMainPetticoatEdgeStretch95Percentile': float(np.percentile(ratios, 95)),
                 'actualMainPetticoatBounds': [xyz.min(0).tolist(), xyz.max(0).tolist()]})
    points.append(xyz)
    matrices.append(actual)
    print('ACTUAL_EXPORTED_IVORY_POSE_MEASURED', i + 1, error, flush=True)
actual_data = out / 'actual_exported_ivory_poses.npz'
np.savez_compressed(actual_data, points=np.asarray(points), rest_points=rest, edges=edges,
                    actual_joint_deformations=np.asarray(matrices), bone_names=data['bone_names'])
write = lambda name, r: (out / (name + '.json')).write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
write('actual_pose_measurements', {'modelSha256': entry['modelSha256'], 'sourcePhotoSha256': entry['sourcePhotoSha256'],
      'clip': action.name, 'actualSkinnedMeshes': 229, 'actualSkeletons': 1, 'measuredJointNames': names,
      'frames': rows, 'dataFile': str(actual_data), 'dataSha256': sha(actual_data),
      'scriptSha256': sha(__file__), 'motionVerified': False, 'clothCollisionVerified': False, 'fidelityVerified': False})
reference_root = Path(g.get('authoringReferenceRoot', Path(args.generation).parent))
schema = read(reference_root / 'shared_rig_bind.json')
ivory_names = {n for n, family in schema['pieceFamilies'].items() if family == 'IvoryCloth'}
ivory = [o for o in meshes if o.name in ivory_names]
assert main in ivory
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 12
scene.render.resolution_x = 620
scene.render.resolution_y = 820
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.world = bpy.data.worlds.new('Actual exported cloth response review')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .35, .35, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
lo, hi = rest_bounds.min(0), rest_bounds.max(0)
center = Vector((lo + hi) / 2)
span = max(float((hi - lo)[2]), float(math.hypot(*(hi - lo)[:2])) * 820 / 620) * 1.22
cam_data = bpy.data.cameras.new('Fixed actual foundation camera')
camera = bpy.data.objects.new(cam_data.name, cam_data)
scene.collection.objects.link(camera)
scene.camera = camera
cam_data.type = 'ORTHO'
cam_data.ortho_scale = span
cam_data.clip_start = .001
for name, direction, energy in [('Key', (1, -2, 2), 25), ('Fill', (-2, -1, 1), 15), ('Back', (0, 2, 1), 25)]:
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = energy * span ** 2
    d.size = span * 1.5
    lamp = bpy.data.objects.new(name, d)
    scene.collection.objects.link(lamp)
    lamp.location = center + Vector(direction).normalized() * span * 2
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
renders = []
specs = [(1, 'front', 'foundation'), (12, 'front', 'foundation'), (20, 'front', 'foundation'),
         (29, 'front', 'foundation'), (29, 'threequarter', 'foundation'),
         (20, 'front', 'ivory_family'), (29, 'threequarter', 'ivory_family')]
for source_frame, view, scope in specs:
    frame = rows[source_frame - 1]['actualImportedFrame']
    scene.frame_set(math.floor(frame), subframe=frame % 1)
    for obj in meshes:
        obj.hide_render = scope == 'ivory_family' and obj not in ivory
    bpy.context.view_layer.update()
    direction = Vector((0, -1, 0)) if view == 'front' else Vector((.65, -1, .12)).normalized()
    camera.location = center + direction * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    file = out / f'{scope}_{source_frame:02d}_{view}.png'
    scene.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)
    renders.append({'sourcePhysicsFrame': source_frame, 'actualImportedFrame': frame, 'view': view, 'scope': scope,
                    'file': str(file), 'sha256': sha(file), 'cameraPosition': list(camera.location),
                    'visibleSkinnedMeshes': len(meshes) if scope == 'foundation' else len(ivory)})
    print('ACTUAL_EXPORTED_IVORY_RENDERED', source_frame, view, scope, flush=True)
write('comparison', {'modelSha256': entry['modelSha256'], 'sourcePhoto': entry['sourcePhoto'],
      'sourcePhotoSha256': entry['sourcePhotoSha256'], 'clip': action.name, 'renders': renders,
      'actualIvoryFamilyMeshes': len(ivory), 'actualSkinnedMeshes': 229, 'actualSkeletons': 1,
      'actualMaterialAndGeometryUnchanged': True, 'actualExportDataSha256': sha(actual_data),
      'scriptSha256': sha(__file__), 'modelUnchanged': sha(entry['model']) == entry['modelSha256'],
      'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False, 'allLayersFinished': False})
shutil.copyfile(__file__, out / 'executed_review.py')
