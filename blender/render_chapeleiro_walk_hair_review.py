"""Render the whole Alice under native Walk hair physics for visual review."""
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
p.add_argument('--frame', type=int, default=4)
p.add_argument('--views', default='front,right,back,left')
p.add_argument('--framing', choices=['whole', 'upper-body'], default='whole')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert 2 <= a.frame <= 42
views = a.views.split(',')
directions = dict(front=(0, -1, 0), right=(1, 0, 0), back=(0, 1, 0), left=(-1, 0, 0))
assert views and len(set(views)) == len(views) and all(v in directions for v in views)
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


g = json.loads(Path(a.generation).read_text(encoding='utf-8'))
assert sha(g['editableBlend']) == g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = a.frame
rig = next(o for o in scene.objects if o.type == 'ARMATURE')
guides = next(o for o in scene.objects if o.type == 'CURVES' and 'dynamics guides' in o.name)
rig.data.pose_position = 'POSE'
rig.animation_data.action = None
selected = []
for track in rig.animation_data.nla_tracks:
    track.mute = not track.name.startswith('Walk /')
    if not track.mute:
        selected.append(track.name)
assert len(selected) == 1
node = next(n for n in guides.modifiers[0].node_group.nodes if n.bl_idname == 'GeometryNodeGroup')
node.inputs['Mode'].default_value = 'Physics (Experimental)'
assert node.inputs['Effectors Collection'].default_value is not None
for frame in range(1, a.frame + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = guides.evaluated_get(bpy.context.evaluated_depsgraph_get())
    assert len(evaluated.data.curves) == 2112
    print('WALK_REVIEW_EVALUATED_FRAME', frame, flush=True)

scene.render.resolution_x = scene.render.resolution_y = 768
scene.cycles.samples = 24
scene.cycles.use_denoising = True
camera = scene.camera
target = Vector((0, .025, .56 if a.framing == 'whole' else .808))
camera.data.ortho_scale = 1.22 if a.framing == 'whole' else .4
for view in views:
    camera.location = target + Vector(directions[view]) * (2 if a.framing == 'whole' else 1.2)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / (view + '.png'))
    bpy.ops.render.render(write_still=True)
    print('WALK_REVIEW_RENDERED', view, flush=True)
report = dict(sourceGeneration=a.generation, sourceBlendSha256=g['editableBlendSha256'],
              actionTrack=selected[0], frame=a.frame, views=views,
              framing=a.framing, wholeCharacterRendered=a.framing == 'whole', appearanceApproved=False,
              collisionApproved=False, published=False)
(out / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
