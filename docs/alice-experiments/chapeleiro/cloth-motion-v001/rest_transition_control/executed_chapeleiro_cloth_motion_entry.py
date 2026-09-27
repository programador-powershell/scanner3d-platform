"""Create a local rest-to-source transition; preserve all original actions."""
import bpy
from mathutils import Matrix


def rest_transition_action(rig, source, warmup, cycles):
    """Return a local physics-only action sampled from the real source action.

    The first frame is the rest pose. Over warmup frames each local transform
    interpolates into the source's first pose, then the original motion plays.
    This avoids initializing Cloth in an already raised-knee pose.
    """
    first, last = source.frame_range
    assert int(first) == first and int(last) == last
    names = [b.name for b in rig.data.bones]
    rig.animation_data.action = source
    if source.slots:
        rig.animation_data.action_slot = source.slots[0]
    samples = []
    for frame in range(int(first), int(last) + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        samples.append({n: rig.pose.bones[n].matrix_basis.copy() for n in names})
    local = bpy.data.actions.new('Local cloth entry only / rest to ' + source.name)
    rig.animation_data.action = local
    count = warmup + 1 + (len(samples) - 1) * cycles
    for frame in range(1, count + 1):
        if frame <= warmup + 1:
            factor = (frame - 1) / warmup
            transforms = {n: Matrix.Identity(4).lerp(samples[0][n], factor) for n in names}
        else:
            source_index = (frame - warmup - 1) % (len(samples) - 1)
            if frame == count:
                source_index = len(samples) - 1
            transforms = samples[source_index]
        for name in names:
            bone = rig.pose.bones[name]
            bone.rotation_mode = 'QUATERNION'
            bone.matrix_basis = transforms[name]
            for channel in ['location', 'rotation_quaternion', 'scale']:
                bone.keyframe_insert(data_path=channel, frame=frame, group=name)
    for layer in local.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = 'LINEAR'
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    error = max(max(abs(b.matrix_basis[r][c] - Matrix.Identity(4)[r][c])
                    for r in range(4) for c in range(4)) for b in rig.pose.bones)
    assert error < 1e-6
    return local, count, error
