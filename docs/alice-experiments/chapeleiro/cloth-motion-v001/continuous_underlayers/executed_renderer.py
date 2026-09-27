"""Render recorded solver vertices through the existing authored receiver.

Only the ivory petticoat and the three actual collider garments are visible.
This diagnostic never substitutes a final skinned GLB or approves all layers.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
r, probe = read(args.generation), read(args.probe)
assert sha(r['editableBlend']) == r['editableBlendSha256'] == probe['parentEditableSha256']
assert sha(probe['dataFile']) == probe['dataSha256']
photo = r['exports']['foundation']['sourcePhoto']
assert sha(photo) == probe['sourcePhotoSha256'] == r['exports']['foundation']['sourcePhotoSha256']
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
arrays = np.load(probe['dataFile'])
bpy.ops.wm.open_mainfile(filepath=r['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
cage = bpy.data.objects[probe['clothCage']]
receiver = bpy.data.objects[probe['receiver']]
colliders = [bpy.data.objects[n] for n in probe['actualColliderSurfaces']]
for collection in bpy.data.collections:
    collection.hide_viewport = False
    collection.hide_render = False
for obj in scene.objects:
    obj.hide_viewport = obj not in [rig, cage, receiver, *colliders]
    obj.hide_render = obj not in [receiver, *colliders]
    obj.hide_set(obj not in [rig, cage, receiver, *colliders])
assert not receiver.hide_render and all(not c.hide_render for c in receiver.users_collection)
for m in list(cage.modifiers):
    if m.type != 'TRIANGULATE':
        cage.modifiers.remove(m)
assert [m.type for m in cage.modifiers] == ['TRIANGULATE']
assert receiver.modifiers[0].type == 'SURFACE_DEFORM' and receiver.modifiers[0].is_bound
for track in rig.animation_data.nla_tracks:
    track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
action = bpy.data.actions[probe['sourceAction']]
track = rig.animation_data.nla_tracks.new()
strip = track.strips.new(action.name, probe['actualWarmupFrames'] + 1, action)
strip.repeat = probe['cycles']
strip.extrapolation = 'HOLD'
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 12
scene.render.resolution_x = 620
scene.render.resolution_y = 760
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.world = bpy.data.worlds.new('Recorded actual cloth inspection')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .35, .35, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
data = bpy.data.cameras.new('Fixed camera for recorded actual cloth')
camera = bpy.data.objects.new(data.name, data)
scene.collection.objects.link(camera)
scene.camera = camera
data.type = 'ORTHO'
data.ortho_scale = .68
data.clip_start = .001
center = Vector((0, 0, .34))
for name, direction, energy in [('Key', (1, -2, 2), 18), ('Fill', (-2, -1, 1), 12), ('Back', (0, 2, 1), 18)]:
    d = bpy.data.lights.new(name, 'AREA')
    d.energy = energy
    d.size = 1
    lamp = bpy.data.objects.new(name, d)
    scene.collection.objects.link(lamp)
    lamp.location = center + Vector(direction).normalized() * 1.5
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
rows = []
last = len(arrays['points'])
specs = [(1, 'front'), (probe['actualWarmupFrames'], 'front'), ((last + probe['actualWarmupFrames']) // 2, 'front'), (last, 'front'), (last, 'threequarter')]
inverse = np.asarray(cage.matrix_world.inverted())
for frame, view in specs:
    scene.frame_set(frame)
    world = arrays['points'][frame - 1]
    local = world @ inverse[:3, :3].T + inverse[:3, 3]
    cage.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
    cage.data.update()
    bpy.context.view_layer.update()
    evaluated = cage.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    points = np.array([evaluated.matrix_world @ v.co for v in mesh.vertices])
    evaluated.to_mesh_clear()
    error = float(np.abs(points - world).max())
    assert error < 1e-6
    direction = Vector((0, -1, 0)) if view == 'front' else Vector((.65, -1, .12)).normalized()
    camera.location = center + direction * 2
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    file = out / f'actual_solver_{frame:02d}_{view}.png'
    scene.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)
    rows.append({'frame': frame, 'view': view, 'file': str(file), 'sha256': sha(file),
                 'recordedCageReconstructionMaximumError': error, 'cameraPosition': list(camera.location)})
    print('ACTUAL_RECORDED_CLOTH_RENDERED', frame, view, flush=True)
report = {'parentEditableSha256': r['editableBlendSha256'], 'probeDataSha256': probe['dataSha256'],
          'sourcePhoto': photo, 'sourcePhotoSha256': probe['sourcePhotoSha256'], 'renders': rows,
          'visibleScope': 'existing authored ivory receiver plus stockings and bloomers; other foundation parts hidden for diagnosis',
          'actualReceiver': receiver.name, 'existingSurfaceDeformAndBystedtNodesPreserved': True,
          'recordedSolverPositionsReconstructed': True, 'scriptSha256': sha(__file__),
          'parentEditableUnchanged': sha(r['editableBlend']) == r['editableBlendSha256'],
          'finalGlbChanged': False, 'allLayersFinished': False, 'motionVerified': False,
          'clothCollisionVerified': False, 'fidelityVerified': False}
(out / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
