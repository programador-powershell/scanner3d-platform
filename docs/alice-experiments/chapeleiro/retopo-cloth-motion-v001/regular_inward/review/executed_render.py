"""Review measured sewn cloth through existing garment receivers and actual lace.

The complete foundation remains visible for context. Only the ivory support,
Black support, three flounces and their three lace receivers are reconstructed
from this coupled solver. Other adornments retain the recorded body-driven rig
and are explicitly not approved by this diagnostic.
"""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--probe', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
path, out = Path(a.generation), Path(a.output)
g, probe = read(path), read(a.probe)
assert probe['assembly']['includedIvory']
assert sha(g['editableBlend']) == g['editableBlendSha256'] == probe['parentEditableSha256']
assert sha(probe['dataFile']) == probe['dataSha256']
assert sha(g['exports']['foundation']['sourcePhoto']) == probe['sourcePhotoSha256']
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
audit, schema = read(path.parent / 'skin_audit.json'), read(path.parent / 'shared_rig_bind.json')
previews = [bpy.data.objects[r['mesh']] for r in audit['pieces'][:-1]]
assert len(previews) == 229
parts = {r['key']: r for r in probe['parts']}
sources = {key: bpy.data.objects[r['source']] for key, r in parts.items()}
black_names = [n for n, family in schema['pieceFamilies'].items() if family == 'BlackCloth']
black = [bpy.data.objects['Authoring / ' + n] for n in black_names]
ivory_name = parts['ivory']['visibleGarment']
ivory = bpy.data.objects['Authoring / ' + ivory_name]
assert len(black) == 7
for key, obj in sources.items():
    for mod in list(obj.modifiers):
        if key == 'ivory' and mod.type != 'TRIANGULATE': obj.modifiers.remove(mod)
        elif mod.type in {'ARMATURE', 'CLOTH', 'SURFACE_DEFORM'}:
            mod.show_viewport = mod.show_render = False
assert [m.type for m in sources['ivory'].modifiers] == ['TRIANGULATE']
assert ivory.modifiers[0].type == 'SURFACE_DEFORM' and ivory.modifiers[0].is_bound
for collection in bpy.data.collections: collection.hide_viewport = collection.hide_render = False
visible = {rig, *previews, *black, ivory, *sources.values()}
for obj in scene.objects:
    obj.hide_viewport = obj not in visible
    obj.hide_render = obj not in previews
    obj.hide_set(obj not in visible)
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
for pose in rig.pose.bones: pose.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
bpy.context.view_layer.update()

def coords(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    xyz = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get('co', xyz)
    m = np.asarray(ev.matrix_world)
    points = xyz.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
    ev.to_mesh_clear()
    return points

bounds = np.concatenate([coords(o) for o in previews])
center = Vector((bounds.min(0) + bounds.max(0)) / 2)
extent = bounds.max(0) - bounds.min(0)
span = max(float(extent[2]), float(math.hypot(*extent[:2])) * 820 / 620) * 1.22
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 12
scene.render.resolution_x, scene.render.resolution_y = 620, 820
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
scene.world = bpy.data.worlds.new('Measured sewn petticoat review')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .35, .35, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
cam_data = bpy.data.cameras.new('Fixed full foundation comparison camera')
camera = bpy.data.objects.new(cam_data.name, cam_data)
scene.collection.objects.link(camera)
scene.camera = camera
cam_data.type, cam_data.ortho_scale, cam_data.clip_start = 'ORTHO', span, .001
for name, direction, energy in [('Key', (1, -2, 2), 25), ('Fill', (-2, -1, 1), 15), ('Back', (0, 2, 1), 25)]:
    d = bpy.data.lights.new(name, 'AREA')
    d.energy, d.size = energy * span ** 2, span * 1.5
    lamp = bpy.data.objects.new(name, d)
    scene.collection.objects.link(lamp)
    lamp.location = center + Vector(direction).normalized() * span * 2
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
data = np.load(probe['dataFile'])
lace_targets = []
for tier in range(1, 4):
    source = sources['tier' + str(tier)]
    proxy = source.copy()
    proxy.data = source.data.copy()
    proxy.name = 'Stable thin lace target / measured sewn tier ' + str(tier)
    proxy.modifiers.clear()
    world = source.matrix_world.copy()
    proxy.parent = None
    proxy.matrix_world = world
    scene.collection.objects.link(proxy)
    proxy.hide_viewport, proxy.hide_render = False, True
    proxy.hide_set(False)
    lace = bpy.data.objects['Authoring / 01 / black floral lace tier ' + str(tier) + ' / real apertures']
    bpy.ops.object.select_all(action='DESELECT')
    lace.select_set(True)
    bpy.context.view_layer.objects.active = lace
    modifier = next(m for m in lace.modifiers if m.type == 'SURFACE_DEFORM')
    if modifier.is_bound: bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    modifier.target = proxy
    bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    assert modifier.is_bound and len(proxy.data.vertices) == 2496
    lace_targets.append((proxy, lace, modifier))
names = data['bone_names'].tolist()
assert names == [b.name for b in rig.data.bones]
bind = {b.name: b.matrix_local.copy() for b in rig.data.bones}
before = read(path.parent / 'actual_ivory_export_review_v001/comparison.json')
renders = []
specs = [(1, 'front', 'foundation'), (20, 'front', 'foundation'), (29, 'threequarter', 'foundation'),
         (29, 'threequarter', 'sewn_receivers')]

def reconstruct(obj, world):
    m = np.asarray(obj.matrix_world.inverted())
    local = world @ m[:3, :3].T + m[:3, 3]
    assert len(local) == len(obj.data.vertices)
    obj.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
    obj.data.update()
    actual = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
    error = float(np.abs(actual - world).max())
    assert error < 1e-6
    return error

for frame, view, scope in specs:
    desired = {n: Matrix(data['rig_deformations'][frame - 1, i].tolist()) @ bind[n] for i, n in enumerate(names)}
    for bone in rig.data.bones:
        arguments = {'parent_matrix': desired[bone.parent.name], 'parent_matrix_local': bind[bone.parent.name]} if bone.parent else {}
        rig.pose.bones[bone.name].matrix_basis = bone.convert_local_to_pose(desired[bone.name], bind[bone.name], invert=True, **arguments)
    errors = {}
    for key, obj in sources.items():
        part = parts[key]
        world = data['points'][frame - 1, part['start']:part['start'] + part['vertices']]
        errors[key] = reconstruct(obj, world)
    for tier, (proxy, lace, modifier) in enumerate(lace_targets, 1):
        part = parts['tier' + str(tier)]
        reconstruct(proxy, data['points'][frame - 1, part['start']:part['start'] + part['vertices']])
        assert modifier.is_bound and len(coords(proxy)) == 2496
    for obj in previews:
        obj.hide_viewport = obj.hide_render = scope == 'sewn_receivers' or obj.name in [ivory_name, *black_names]
    for obj in [ivory, *black]: obj.hide_viewport = obj.hide_render = False
    bpy.context.view_layer.update()
    matrix_error = float(np.abs(np.array([np.asarray(rig.pose.bones[n].matrix @ bind[n].inverted()) for n in names]) - data['rig_deformations'][frame - 1]).max())
    assert matrix_error < 1e-5
    direction = Vector((0, -1, 0)) if view == 'front' else Vector((.65, -1, .12)).normalized()
    camera.location = center + direction * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    old = next(r for r in before['renders'] if r['sourcePhysicsFrame'] == frame and r['view'] == view and r['scope'] == 'foundation')
    camera_error = max(abs(x - y) for x, y in zip(camera.location, old['cameraPosition']))
    assert camera_error < 1e-5
    file = out / f'{scope}_{frame:02d}_{view}.png'
    scene.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)
    renders.append({'sourcePhysicsFrame': frame, 'view': view, 'scope': scope, 'file': str(file), 'sha256': sha(file),
                    'cameraPosition': list(camera.location), 'previousIvoryRenderCameraMaximumError': camera_error,
                    'recordedRigMatrixMaximumError': matrix_error, 'sourceReconstructionMaximumErrors': errors,
                    'actualStableLaceTargetVertices': [len(coords(p)) for p, _, _ in lace_targets],
                    'actualLaceBindingsPresent': all(m.is_bound for _, _, m in lace_targets),
                    'actualVisibleSurfaces': 229 if scope == 'foundation' else 8})
    (out / 'progress.json').write_text(json.dumps({'completed': False, 'renders': renders}) + '\n', encoding='utf-8', newline='\n')
    print('ACTUAL_SEWN_RECEIVER_RENDERED', frame, view, scope, flush=True)
report = {'parentEditableSha256': g['editableBlendSha256'], 'sourcePhoto': g['exports']['foundation']['sourcePhoto'],
          'sourcePhotoSha256': probe['sourcePhotoSha256'], 'probeDataSha256': probe['dataSha256'],
          'scope': 'Recorded coupled Ivory and Black cloth reconstructed through eight actual authored receivers; other 221 foundation surfaces remain body-driven context and are not collision-approved.',
          'stableThinLaceTargets': True, 'thicknessOutputTopologyNotUsedAsLaceBindingTarget': True,
          'renders': renders, 'scriptSha256': sha(__file__), 'checkpointUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'parentGlbUnchanged': sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256'],
          'responseBakedIntoGlb': False, 'allLayersFinished': False, 'motionVerified': False,
          'fidelityVerified': False, 'clothCollisionVerified': False, 'finalFbxExported': False}
(out / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_render.py')
