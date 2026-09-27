"""Render actual current skinned corset and trim in three full-object views.

No authoring source is changed. Isolating an authored interior part for review
does not cut or extract the protected whole Tripo dress.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
g = json.loads(Path(a.generation).read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
photo = g['exports']['foundation']['sourcePhoto']
assert sha(photo) == g['exports']['foundation']['sourcePhotoSha256']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
for track in rig.animation_data.nla_tracks: track.mute = True
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
scene.frame_set(1)
shell = bpy.data.objects['01 / ivory fitted boned corset / pointed front']
pieces = [o for o in scene.objects if o.type == 'MESH' and o.name.startswith('01 / ')
          and any(x in o.name.lower() for x in ['corset', 'busk', 'rear eyelet'])]
assert shell in pieces
assert len([o for o in pieces if o.name.startswith('01 / brass busk')]) == 12
assert len([o for o in pieces if o.name.startswith('01 / rear eyelet')]) == 16
for collection in bpy.data.collections: collection.hide_viewport = collection.hide_render = False
visible = {rig, *pieces}
for o in scene.objects:
    o.hide_viewport = o not in visible
    o.hide_render = o not in pieces
    o.hide_set(o not in visible)
bpy.context.view_layer.update()
points = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in pieces])
center = Vector((points.min(0) + points.max(0)) / 2)
span = max(float(np.ptp(points[:, 2])), float(np.linalg.norm(np.ptp(points[:, :2], axis=0))) * 760 / 680) * 1.18
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.resolution_x, scene.render.resolution_y = 680, 760
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Corset close inspection world')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.018, .018, .018, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .65
scene.world = world
camera_data = bpy.data.cameras.new('Full corset orthographic review camera')
camera = bpy.data.objects.new(camera_data.name, camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = 'ORTHO'
camera_data.ortho_scale, camera_data.clip_start = span, .001
for name, direction, energy in [('Key', (1, -2, 2), 25), ('Fill', (-2, -1, 1), 15), ('Back', (0, 2, 1), 25)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.size = energy * span ** 2, span * 1.5
    lamp = bpy.data.objects.new(name, data)
    scene.collection.objects.link(lamp)
    lamp.location = center + Vector(direction).normalized() * span * 2
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
renders = []
for view, direction in [('front', (0, -1, 0)), ('back', (0, 1, 0)), ('profile', (1, 0, 0))]:
    camera.location = center + Vector(direction) * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    file = out / (view + '.png')
    scene.render.filepath = str(file)
    bpy.ops.render.render(write_still=True)
    renders.append({'view': view, 'file': str(file), 'sha256': sha(file), 'cameraPosition': list(camera.location)})
    (out / 'progress.json').write_text(json.dumps({'renders': renders}) + '\n', encoding='utf-8')
    print('ACTUAL_CORSET_VIEW_RENDERED', view, flush=True)
record = {'sourcePhoto': photo, 'sourcePhotoSha256': sha(photo),
          'parentEditable': g['editableBlend'], 'parentEditableSha256': g['editableBlendSha256'],
          'completeSourceUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'actualSkinnedMeshesReviewed': len(pieces), 'actualBones': len(rig.data.bones),
          'scope': 'Actual authored interior corset, busk, rear eyelets, lacing and trim in reference pose; garment fit and all motion remain pending.',
          'pieceNames': [o.name for o in pieces], 'renders': renders,
          'orthoScale': span, 'scriptSha256': sha(__file__), 'fidelityVerified': False,
          'clothCollisionVerified': False, 'finalFbxExported': False}
(out / 'comparison.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_render.py')
