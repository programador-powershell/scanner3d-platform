"""Run native hair guides under an authored Alice action without mutating source.

This measures the full guide set, not a subset, and does not equate guide
stability with approved fiber/dress collision or exported game physics.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser()
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
p.add_argument('--action', choices=['Walk', 'Run', 'Attack', 'Jump'], required=True)
p.add_argument('--frames', type=int, default=12)
p.add_argument('--contact-guide-ids', default='', help='Comma-separated guide IDs for per-frame closed proxy 0 contact audit')
p.add_argument('--save-frame-snapshots', action='store_true', help='Save evaluated guide control positions after every simulated frame')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
assert 2 <= a.frames <= 96
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


g = json.loads(Path(a.generation).read_text())
assert sha(g['editableBlend']) == g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
s = bpy.context.scene
s.render.fps = 30
s.frame_start = 1
s.frame_end = a.frames
rig = next(o for o in s.objects if o.type == 'ARMATURE')
guides = next(o for o in s.objects if o.type == 'CURVES' and 'dynamics guides' in o.name)
for o in s.objects:
    if o.type == 'CURVES' and o != guides:
        o.hide_viewport = True
        o.hide_set(True)
rig.data.pose_position = 'POSE'
rig.animation_data.action = None
selected = []
for track in rig.animation_data.nla_tracks:
    track.mute = not track.name.startswith(a.action + ' /')
    if not track.mute:
        selected.append(dict(name=track.name, strips=[dict(name=strip.name,
                                                           frameStart=strip.frame_start,
                                                           frameEnd=strip.frame_end,
                                                           actionStart=strip.action_frame_start,
                                                           actionEnd=strip.action_frame_end)
                                                      for strip in track.strips]))
assert len(selected) == 1, selected
head = rig.pose.bones['Head']
gn = guides.modifiers[0].node_group
dyn = next(n for n in gn.nodes if n.bl_idname == 'GeometryNodeGroup')
dyn.inputs['Mode'].default_value = 'Physics (Experimental)'
assert dyn.inputs['Effectors Collection'].default_value is not None
C = len(guides.data.curves)
N = len(guides.data.points) // C
assert C == 2112
contact_ids = sorted(set(int(x) for x in a.contact_guide_ids.split(',') if x))
assert all(0 <= x < C for x in contact_ids)
contact_proxy = bpy.data.objects['Chapeleiro / hair contact proxy / 0'] if contact_ids else None
ray_directions = [Vector(x).normalized() for x in ((1, .173, .093), (.137, 1, .071), (.113, .197, 1))]


def changed_guide_contacts(positions, depsgraph):
    ev = contact_proxy.evaluated_get(depsgraph)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    verts = [ev.matrix_world @ v.co for v in mesh.vertices]
    faces = [tuple(t.vertices) for t in mesh.loop_triangles]
    tree = BVHTree.FromPolygons(verts, faces, all_triangles=True)
    bounds = np.asarray(verts)
    lo, hi = bounds.min(axis=0), bounds.max(axis=0)
    matrix = np.asarray(guides.matrix_world)
    total_inside = total_disagree = 0
    by_guide = {}
    for gid in contact_ids:
        path = positions[gid] @ matrix[:3, :3].T + matrix[:3, 3]
        samples = np.concatenate((path, (path[:-1] + path[1:]) * .5), axis=0)
        inside = disagree = 0
        for point in samples:
            if np.any(point < lo) or np.any(point > hi):
                continue
            votes = []
            for direction in ray_directions:
                origin = Vector(point)
                crossings = 0
                for _ in range(64):
                    hit, _, _, _ = tree.ray_cast(origin, direction, 2)
                    if hit is None:
                        break
                    crossings += 1
                    origin = hit + direction * .000001
                votes.append(crossings % 2)
            disagree += len(set(votes)) > 1
            if sum(votes) >= 2:
                _, _, _, depth = tree.find_nearest(Vector(point))
                inside += depth > .0001
        by_guide[str(gid)] = dict(samples=len(samples), insideSamples=int(inside),
                                  rayDisagreements=int(disagree))
        total_inside += inside
        total_disagree += disagree
    ev.to_mesh_clear()
    return dict(proxy=contact_proxy.name, guides=by_guide,
                insideSamples=int(total_inside), rayDisagreements=int(total_disagree),
                scope='Edited guides only; full fibers and other colliders not covered')


rest = np.empty(len(guides.data.points) * 3, np.float32)
guides.data.attributes['position'].data.foreach_get('vector', rest)
rest = rest.reshape(C, N, 3)
rest_lengths = np.linalg.norm(np.diff(rest, axis=1), axis=2)
rows = []
previous = None
for frame in range(1, a.frames + 1):
    s.frame_set(frame)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    evaluated = guides.evaluated_get(dg).data
    points = np.empty(len(evaluated.points) * 3, np.float32)
    evaluated.attributes['position'].data.foreach_get('vector', points)
    points = points.reshape(C, N, 3)
    assert np.isfinite(points).all()
    if a.save_frame_snapshots:
        np.savez_compressed(out / f'guides_frame_{frame:03d}.npz',
                            guidePositions=points, frame=np.int32(frame),
                            sourceBlendSha256=np.array(g['editableBlendSha256']))
    transform = np.array(rig.matrix_world @ head.matrix @ head.bone.matrix_local.inverted() @ rig.matrix_world.inverted())
    roots_expected = rest[:, 0] @ transform[:3, :3].T + transform[:3, 3]
    root_error = np.linalg.norm(points[:, 0] - roots_expected, axis=1)
    stretch = np.linalg.norm(np.diff(points, axis=1), axis=2) / np.maximum(rest_lengths, 1e-8)
    step = np.linalg.norm(points - previous, axis=2) if previous is not None else np.zeros((C, N))
    worst_guide, worst_segment = np.unravel_index(int(np.argmax(stretch)), stretch.shape)
    deformed_lengths = np.linalg.norm(np.diff(points, axis=1), axis=2)
    row = dict(frame=frame, maxRootErrorM=float(root_error.max()), rootErrorP95M=float(np.percentile(root_error, 95)),
               maxSegmentStretch=float(stretch.max()), segmentStretchP95=float(np.percentile(stretch, 95)),
               worstGuideId=int(worst_guide), worstSegmentIndex=int(worst_segment),
               worstRestSegmentMm=float(rest_lengths[worst_guide, worst_segment] * 1000),
               worstDeformedSegmentMm=float(deformed_lengths[worst_guide, worst_segment] * 1000),
               meanTipDisplacementFromRestM=float(np.linalg.norm(points[:, -1] - rest[:, -1], axis=1).mean()),
               maxPointStepM=float(step.max()))
    if contact_ids:
        row['changedGuideProxy0Contacts'] = changed_guide_contacts(points, dg)
    rows.append(row)
    (out / 'live_measurements.json').write_text(json.dumps(rows, indent=2) + '\n')
    print('ACTION_HAIR_FRAME', a.action, json.dumps(row), flush=True)
    previous = points.copy()
    if row['maxRootErrorM'] > .0005 or row['maxSegmentStretch'] > 1.2 or row['maxPointStepM'] > .1:
        report = dict(sourceGeneration=a.generation, action=a.action, track=selected[0],
                      guideCount=C, controlsPerGuide=N, contactGuideIds=contact_ids,
                      frameSnapshotsSaved=a.save_frame_snapshots, frames=rows,
                      rootThresholdM=.0005, stretchThreshold=1.2, pointStepThresholdM=.1,
                      stable=False, finalPhysicsApproved=False, published=False)
        (out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
        raise RuntimeError('Authored action hair dynamics exceeded provisional stability thresholds')
report = dict(sourceGeneration=a.generation, action=a.action, track=selected[0],
              guideCount=C, controlsPerGuide=N, contactGuideIds=contact_ids,
              frameSnapshotsSaved=a.save_frame_snapshots, frames=rows,
              rootThresholdM=.0005, stretchThreshold=1.2, pointStepThresholdM=.1,
              stable=True,
              changedGuideProxy0ContactsClear=(all(r['changedGuideProxy0Contacts']['insideSamples'] == 0
                                                  for r in rows) if contact_ids else None),
              bodyDressCollisionVerified=False, fullFiberMotionVerified=False,
              exportedGamePhysicsVerified=False, finalPhysicsApproved=False, published=False,
              sourceUnchanged=sha(g['editableBlend']) == g['editableBlendSha256'])
(out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print('ACTION_HAIR_AUDIT', a.action, 'stable', len(rows), flush=True)
