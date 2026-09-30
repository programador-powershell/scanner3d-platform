"""Render Walk and Jump from the reimported whole GLB to check hair skin."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

p = argparse.ArgumentParser()
p.add_argument('--generation', required=True)
p.add_argument('--export', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
out = Path(a.output)
assert not out.exists()
g = json.loads(Path(a.generation).read_text())
e = json.loads(Path(a.export).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert sha(e['model']) == e['modelSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
scene.frame_set(1)
original = set(scene.objects)
original_actions = set(bpy.data.actions)
for obj in original:
    if obj.type in {'MESH', 'CURVES', 'CURVE', 'ARMATURE'}:
        obj.hide_render = True
bpy.ops.import_scene.gltf(filepath=e['model'])
imported = [obj for obj in scene.objects if obj not in original]
rigs = [obj for obj in imported if obj.type == 'ARMATURE']
assert len(rigs) == 1
rig = rigs[0]
for obj in imported:
    obj.hide_render = False
rig.animation_data_create()
for track in rig.animation_data.nla_tracks:
    track.mute = True
scene.camera.data.ortho_scale = .4
target = Vector((0, .025, .808))
scene.camera.location = target + Vector((0, -1.2, 0))
scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x = scene.render.resolution_y = 768
scene.cycles.samples = 24
scene.cycles.use_denoising = True
out.mkdir(parents=True)
reviews = []
for label in ('Walk', 'Jump'):
    actions = [action for action in bpy.data.actions if action not in original_actions and
               action.name.startswith(label + ' /')]
    assert len(actions) == 1, (label, [x.name for x in actions])
    action = actions[0]
    rig.animation_data.action = action
    if action.slots:
        rig.animation_data.action_slot = action.slots[0]
    first, last = action.frame_range
    frame = round(first + (last - first) * .33)
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    scene.render.filepath = str(out / (label.lower() + '_front.png'))
    bpy.ops.render.render(write_still=True)
    reviews.append(dict(action=action.name, frame=frame, first=first, last=last,
                        render=scene.render.filepath))
report = dict(model=e['model'], modelSha256=e['modelSha256'],
              wholeCharacterWithDress=e['wholeCharacterWithDress'],
              importedHairFiberCount=sum(obj.get('hairFiberCount', 0) for obj in imported),
              reviews=reviews, physicsTransferred=False, appearanceApproved=False,
              renderOnlyNoBlendSaved=True)
assert report['importedHairFiberCount'] == e['exportedFiberCount']
(out / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
print('EXPORTED_HAIR_MOTION_REVIEW', json.dumps(report), flush=True)
