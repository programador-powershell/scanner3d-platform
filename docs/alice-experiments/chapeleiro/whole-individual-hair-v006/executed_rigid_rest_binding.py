"""Bind static rest-guide curves to Head in an isolated complete Alice blend.

The physical guides and individual follower curves stay untouched. This is a
local authoring study; action, export and runtime physics still need review.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix


p = argparse.ArgumentParser()
p.add_argument("--generation", type=Path, required=True)
p.add_argument("--snapshot-dir", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index("--") + 1:])
assert not a.output.exists()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def points(obj):
    value = np.empty(len(obj.data.points) * 3, np.float32)
    obj.data.attributes["position"].data.foreach_get("vector", value)
    return value.reshape(len(obj.data.curves), -1, 3)


g = json.loads(a.generation.read_text(encoding="utf-8"))
assert sha(g["editableBlend"]) == g["editableBlendSha256"]
bpy.ops.wm.open_mainfile(filepath=g["editableBlend"])
scene = bpy.context.scene
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 6
rig = next(obj for obj in scene.objects if obj.type == "ARMATURE")
rest = next(obj for obj in scene.objects if obj.type == "CURVES" and
            "animated rest guides" in obj.name)
guides = next(obj for obj in scene.objects if obj.type == "CURVES" and
              "dynamics guides" in obj.name)
hair = next(obj for obj in scene.objects if obj.type == "CURVES" and
            "individual hair fibers" in obj.name)
assert rest.parent is None and len(rest.modifiers) == 1
assert rest.modifiers[0].type == "NODES"
raw_rest = points(rest).copy()
raw_guides_hash = hashlib.sha256(points(guides).tobytes()).hexdigest()
raw_hair_hash = hashlib.sha256(points(hair).tobytes()).hexdigest()
whole = bpy.data.objects["Chapeleiro / intact whole exterior / skin study"]
body = np.empty(len(whole.data.vertices) * 3, np.float32)
whole.data.vertices.foreach_get("co", body)
body_hash = hashlib.sha256(body.tobytes()).hexdigest()

rig.data.pose_position = "POSE"
rig.animation_data.action = None
for track in rig.animation_data.nla_tracks:
    track.mute = not track.name.startswith("Walk /")
scene.frame_set(1)
bpy.context.view_layer.update()
rest.modifiers.remove(rest.modifiers[0])
rest.hide_viewport = False
rest.hide_set(False)
head = rig.pose.bones["Head"]
bind = rig.matrix_world @ head.bone.matrix_local
rest.parent = rig
rest.parent_type = "BONE"
rest.parent_bone = "Head"
rest.matrix_parent_inverse = bind.inverted()
rest.matrix_basis = Matrix.Translation((0, 0, -head.bone.length))
bpy.context.view_layer.update()

rows = []
print("RIGID_REST_TRACKS", json.dumps({"useNla": rig.animation_data.use_nla,
      "tracks": [[track.name, track.mute, len(track.strips)] for track in
                 rig.animation_data.nla_tracks]}), flush=True)
rig.update_tag(refresh={"OBJECT", "DATA"})
scene.frame_set(2)
bpy.context.view_layer.update()
for frame in range(1, 7):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    # Force Blender's simulation/NLA dependency graph to evaluate this frame.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    _ = guides.evaluated_get(depsgraph).data
    _ = rig.evaluated_get(depsgraph).data
    with np.load(a.snapshot_dir / f"guides_frame_{frame:03d}.npz") as file:
        captured = {key: file[key].copy() for key in file.files}
    expected = captured["headRestToAnimated"]
    matrix_error = float(np.max(np.abs(np.asarray(rest.matrix_world) - expected)))
    if matrix_error >= 1e-5:
        print("RIGID_REST_BINDING_DIAGNOSTIC", json.dumps({
            "frame": frame, "actual": np.asarray(rest.matrix_world).tolist(),
            "expected": expected.tolist(),
            "parentInverse": np.asarray(rest.matrix_parent_inverse).tolist(),
            "basis": np.asarray(rest.matrix_basis).tolist(),
            "headPose": np.asarray(rig.pose.bones["Head"].matrix).tolist(),
            "headPoseEvaluated": np.asarray(rig.evaluated_get(depsgraph).pose.bones["Head"].matrix).tolist(),
            "headRest": np.asarray(rig.pose.bones["Head"].bone.matrix_local).tolist(),
        }), flush=True)
    assert matrix_error < 1e-5, (frame, matrix_error)
    evaluated_object = rest.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_local = points(evaluated_object)
    evaluated_h = np.concatenate((evaluated_local.reshape(-1, 3),
                                  np.ones((evaluated_local.size // 3, 1))), axis=1)
    evaluated = (evaluated_h @ np.asarray(evaluated_object.matrix_world).T)[:, :3].reshape(raw_rest.shape)
    raw_h = np.concatenate((raw_rest.reshape(-1, 3),
                            np.ones((raw_rest.size // 3, 1))), axis=1)
    expected_points = (raw_h @ expected.T)[:, :3].reshape(raw_rest.shape)
    point_error = float(np.linalg.norm(evaluated - expected_points, axis=2).max())
    assert point_error < 1e-5, (frame, point_error)
    rows.append({"frame": frame, "matrixMaxError": matrix_error,
                 "evaluatedRestPointMaxErrorM": point_error})
    print("RIGID_REST_BINDING", json.dumps(rows[-1]), flush=True)

assert hashlib.sha256(points(guides).tobytes()).hexdigest() == raw_guides_hash
assert hashlib.sha256(points(hair).tobytes()).hexdigest() == raw_hair_hash
whole.data.vertices.foreach_get("co", body)
assert hashlib.sha256(body.tobytes()).hexdigest() == body_hash
a.output.mkdir(parents=True)
blend = a.output / "chapeleiro_complete_rigid_rest_binding_study.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report = dict(g)
report.update(parentGeneration=str(a.generation), editableBlend=str(blend),
              editableBlendSha256=sha(blend), physicsVerified=False,
              exported=False, published=False,
              rigidRestHeadBinding={"headBone": "Head",
                                    "restModifierRemovedFromIsolatedCandidate": True,
                                    "rawRestGuidesUnchanged": True,
                                    "rawPhysicalGuidesUnchanged": True,
                                    "rawFibersUnchanged": True,
                                    "bodyDressUnchanged": True,
                                    "capturedWalkFrameChecks": rows,
                                    "runtimePhysicsVerified": False})
(a.output / "generation.json").write_text(json.dumps(report, indent=2) + "\n",
                                              encoding="utf-8")
assert sha(g["editableBlend"]) == g["editableBlendSha256"]
print("RIGID_REST_CANDIDATE", json.dumps({"blend": str(blend),
      "sha256": report["editableBlendSha256"]}), flush=True)
