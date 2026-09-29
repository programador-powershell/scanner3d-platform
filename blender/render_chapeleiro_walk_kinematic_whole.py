"""Render the intact, fully dressed Alice at an authored Walk pose."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

p = argparse.ArgumentParser()
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--frame', type=int, default=21)
p.add_argument('--views', default='front,back')
p.add_argument('--framing', choices=['whole', 'upper-body'], default='whole')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert 1 <= a.frame <= 42
directions = dict(front=(0, -1, 0), right=(1, 0, 0), back=(0, 1, 0), left=(-1, 0, 0))
views = a.views.split(',')
assert views and len(set(views)) == len(views) and all(view in directions for view in views)
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


g = json.loads(Path(a.generation).read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
rig.data.pose_position = 'POSE'
rig.animation_data.action = None
active = []
for track in rig.animation_data.nla_tracks:
    track.mute = not track.name.startswith('Walk /')
    if not track.mute:
        active.append(track.name)
assert len(active) == 1
guides = next(obj for obj in scene.objects if obj.type == 'CURVES' and 'dynamics guides' in obj.name)
node = next(node for node in guides.modifiers[0].node_group.nodes if node.bl_idname == 'GeometryNodeGroup')
node.inputs['Mode'].default_value = 'Animation'
scene.frame_set(a.frame)
bpy.context.view_layer.update()
assert len(next(obj for obj in scene.objects if obj.type == 'CURVES' and 'individual hair fibers' in obj.name).data.curves) == 101424
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.cycles.samples = 12
scene.cycles.use_denoising = True
camera = scene.camera
target = Vector((0, .025, .56 if a.framing == 'whole' else .808))
camera.data.ortho_scale = 1.22 if a.framing == 'whole' else .4
files = {}
for view in views:
    camera.location = target + Vector(directions[view]) * (2 if a.framing == 'whole' else 1.2)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    path = out / (view + '.png')
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    files[view] = dict(path=str(path), sha256=sha(path))
    print('KINEMATIC_WHOLE_WALK_RENDERED', view, flush=True)
report = dict(sourceGeneration=a.generation, sourceBlendSha256=g['editableBlendSha256'],
              actionTrack=active[0], frame=a.frame, files=files,
              framing=a.framing, wholeCharacterRendered=a.framing == 'whole', nativeHairPhysics=False,
              visualFidelityApproved=False, published=False)
(out / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
