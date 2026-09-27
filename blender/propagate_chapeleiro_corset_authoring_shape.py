"""Integrate the pointed corset shape into the complete procedural master.

Rebind dependent authored surfaces at the new rest shape and synchronize the
existing skinned receivers. The intact whole dress, all weights, UVs, materials,
bones and motion curves are preserved. No isolated garment export is produced.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--inventory', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
g, inventory = read(a.generation), read(a.inventory)
assert sha(g['editableBlend']) == g['editableBlendSha256'] == inventory['sourceBlendSha256']
assert g['hiddenProceduralAuthoringShapePropagationPending']
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
rig = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
frame_before, pose_position_before = scene.frame_current, rig.data.pose_position
action_before = rig.animation_data.action
tracks_before = [track.mute for track in rig.animation_data.nla_tracks]
pose_before = [bone.matrix_basis.copy() for bone in rig.pose.bones]
collection_state = {collection: (collection.hide_viewport, collection.hide_render) for collection in bpy.data.collections}
object_state = {obj: (obj.hide_viewport, obj.hide_render, obj.hide_get()) for obj in scene.objects}
modifier_state = [(obj, modifier, modifier.show_viewport, modifier.show_render)
                  for obj in scene.objects for modifier in obj.modifiers]
rig.animation_data.action = None
for track in rig.animation_data.nla_tracks: track.mute = True
rig.data.pose_position = 'REST'
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
for collection in bpy.data.collections: collection.hide_viewport = False
names = sorted(row['name'] for row in g['modifiedSkinnedPieces'])
authored = {name: bpy.data.objects['Authoring / ' + name] for name in names}
assert len(authored) == 24
targets = set(authored.values())
followers = [(obj, modifier) for obj in scene.objects for modifier in obj.modifiers
             if modifier.type == 'SURFACE_DEFORM' and modifier.target in targets]
involved = targets | {obj for obj, modifier in followers}
for obj in involved: obj.hide_viewport = False; obj.hide_set(False)
for obj, modifier, old_viewport, old_render in modifier_state:
    if obj not in involved or modifier.type == 'CLOTH': modifier.show_viewport = False
scene.frame_set(1)
bpy.context.view_layer.update()

def geometry_hash(obj):
    coordinates = np.empty(len(obj.data.vertices) * 3, np.float32)
    loops = np.empty(len(obj.data.loops), np.int32)
    obj.data.vertices.foreach_get('co', coordinates)
    obj.data.loops.foreach_get('vertex_index', loops)
    return hashlib.sha256(coordinates.tobytes() + loops.tobytes()).hexdigest()

def surface_hash(obj):
    digest = hashlib.sha256()
    for layer in obj.data.uv_layers:
        uv = np.empty(len(layer.data) * 2, np.float32)
        layer.data.foreach_get('uv', uv)
        digest.update(layer.name.encode()); digest.update(uv.tobytes())
    digest.update(json.dumps([[(group.group, group.weight) for group in vertex.groups]
                              for vertex in obj.data.vertices]).encode())
    digest.update(json.dumps([group.name for group in obj.vertex_groups]).encode())
    digest.update(json.dumps([material.name if material else None for material in obj.data.materials]).encode())
    return digest.hexdigest()

def actions_hash():
    rows = []
    for action in bpy.data.actions:
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        curves.append([curve.data_path, curve.array_index,
                                       [(list(key.co), list(key.handle_left), list(key.handle_right), key.interpolation)
                                        for key in curve.keyframe_points]])
        rows.append([action.name, curves])
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()

before = {obj.name: geometry_hash(obj) for obj in scene.objects if obj.type == 'MESH'}
actions_before = actions_hash()
assert actions_before == g['actionDataSha256']
weights_before = {name: surface_hash(bpy.data.objects[name]) for name in names}
authored_surfaces_before = {name: surface_hash(obj) for name, obj in authored.items()}
source = authored['01 / ivory fitted boned corset / pointed front']
assert len(source.data.vertices) == 3200
rim = np.array([source.matrix_world @ vertex.co for vertex in source.data.vertices[-128:]])
front = rim[rim[:, 1] <= 1e-6]
front = front[np.argsort(front[:, 0])]
extent = float(np.max(np.abs(front[:, 0])))
tip = float(front[np.argmin(np.abs(front[:, 0])), 2])
side = float((front[0, 2] + front[-1, 2]) / 2)
assert np.all(np.diff(front[:, 0]) > 0)
assert .075 < extent < .085 and .59 < tip < .60 and .62 < side < .63
# Release the old rest binding before moving either the target or receiver.
bindings = []
for obj, modifier in followers:
    assert modifier.is_bound
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    assert not modifier.is_bound
    bindings.append({'mesh': obj.name, 'modifier': modifier.name, 'target': modifier.target.name})
    print('CORSET_AUTHORING_OLD_BIND_RELEASED', obj.name, flush=True)
modified = []
for name, obj in authored.items():
    world = np.array([obj.matrix_world @ vertex.co for vertex in obj.data.vertices])
    x = np.clip(world[:, 0], -extent, extent)
    old_hem = np.interp(x, front[:, 0], front[:, 2])
    new_hem = tip + (side - tip) * np.abs(x) / extent
    taper = np.clip((.665 - world[:, 2]) / (.665 - old_hem), 0, 1) ** 2
    delta = (new_hem - old_hem) * taper * (world[:, 1] < -.0005)
    obj.data = obj.data.copy()
    world[:, 2] += delta
    inverse = np.array(obj.matrix_world.inverted())
    local = world @ inverse[:3, :3].T + inverse[:3, 3]
    obj.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
    if obj.data.has_custom_normals: obj.data.normals_split_custom_set([(0., 0., 0.)] * len(obj.data.loops))
    obj.data.update()
    assert surface_hash(obj) == authored_surfaces_before[name]
    modified.append({'name': obj.name, 'maximumVerticalChangeMeters': float(np.max(np.abs(delta)))})
bpy.context.view_layer.update()
for obj, modifier in followers:
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
    assert modifier.is_bound
    print('CORSET_AUTHORING_NEW_BIND_CREATED', obj.name, flush=True)
bpy.context.view_layer.update()
synchronized = []
for name, obj in authored.items():
    preview = bpy.data.objects[name]
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    world = np.array([ev.matrix_world @ vertex.co for vertex in mesh.vertices])
    old = np.array([preview.matrix_world @ vertex.co for vertex in preview.data.vertices])
    topology_exact = (len(mesh.vertices) == len(preview.data.vertices) and
                      [loop.vertex_index for loop in mesh.loops] == [loop.vertex_index for loop in preview.data.loops])
    print('CORSET_AUTHORING_SYNC_TOPOLOGY', name, len(mesh.vertices), len(preview.data.vertices), topology_exact, flush=True)
    if not topology_exact:
        # BCB merges duplicate traced-lace points after thickness/UV processing;
        # its evaluated vertex count may change with the new rest shape. Keep the
        # already edited skinned UV topology, and measure it against the actual
        # new procedural surface instead of replacing weights by array index.
        mesh.calc_loop_triangles()
        triangles = [tuple(triangle.vertices) for triangle in mesh.loop_triangles]
        tree = BVHTree.FromPolygons(world.tolist(), triangles, all_triangles=True)
        distances = [tree.find_nearest(Vector(point))[3] for point in old]
        assert all(distance is not None for distance in distances)
        maximum_distance = max(distances)
        assert maximum_distance < .00075, (name, maximum_distance)
        assert surface_hash(preview) == weights_before[name]
        synchronized.append({'name': name, 'evaluatedAuthoringVertices': len(mesh.vertices),
                             'preservedSkinnedVertices': len(preview.data.vertices),
                             'evaluatedTopologyExact': False, 'skinnedGeometryRetained': True,
                             'maximumSkinnedPointToAuthoringSurfaceDistanceMeters': maximum_distance,
                             'topologyUvMaterialsAndSkinWeightsExact': True,
                             'evaluatedVertexCountChangeRequiresSurfaceWeightTransferOnFutureRegeneration': True})
        ev.to_mesh_clear()
        continue
    maximum_sync_change = float(np.abs(old - world).max())
    # The pointed study and new evaluated midsurface must agree to submillimeter
    # accuracy; this allowance covers recomputed thickness normals only.
    assert maximum_sync_change < .00075, (name, maximum_sync_change)
    preview.data = preview.data.copy()
    inverse = np.array(preview.matrix_world.inverted())
    local = world @ inverse[:3, :3].T + inverse[:3, 3]
    preview.data.vertices.foreach_set('co', local.astype(np.float32).ravel())
    if preview.data.has_custom_normals: preview.data.normals_split_custom_set([(0., 0., 0.)] * len(preview.data.loops))
    preview.data.update()
    assert surface_hash(preview) == weights_before[name]
    actual = np.array([preview.matrix_world @ vertex.co for vertex in preview.data.vertices])
    consistency_error = float(np.abs(actual - world).max())
    assert consistency_error < 1e-6
    synchronized.append({'name': name, 'maximumSynchronizationChangeMeters': maximum_sync_change,
                         'evaluatedAuthoringPreviewMaximumErrorMeters': consistency_error,
                         'topologyUvMaterialsAndSkinWeightsExact': True})
    ev.to_mesh_clear()
allowed = set(names) | {obj.name for obj in authored.values()}
assert all(geometry_hash(bpy.data.objects[name]) == digest for name, digest in before.items() if name not in allowed)
assert actions_hash() == actions_before
for obj, modifier, old_viewport, old_render in modifier_state:
    modifier.show_viewport, modifier.show_render = old_viewport, old_render
for collection, (viewport, render) in collection_state.items():
    collection.hide_viewport, collection.hide_render = viewport, render
for obj, (viewport, render, hidden) in object_state.items():
    obj.hide_viewport, obj.hide_render = viewport, render
    obj.hide_set(hidden)
rig.data.pose_position = pose_position_before
rig.animation_data.action = action_before
for track, mute in zip(rig.animation_data.nla_tracks, tracks_before): track.mute = mute
for bone, basis in zip(rig.pose.bones, pose_before): bone.matrix_basis = basis
scene.frame_set(frame_before)
blend = out / 'chapeleiro_full_corset_authoring_integrated.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
record = {
    'method': 'Pointed corset refinement integrated into the complete procedural master with new rest bindings and matching skinned surfaces.',
    'parentGeneration': str(Path(a.generation).resolve()), 'parentGenerationSha256': sha(a.generation),
    'editableBlend': str(blend), 'editableBlendSha256': sha(blend), 'editableBytes': blend.stat().st_size,
    'exports': {'foundation': dict(g['exports']['foundation'])},
    'modifiedAuthoringMeshes': modified, 'synchronizedSkinnedMeshes': synchronized, 'recreatedSurfaceBindings': bindings,
    'wholeExteriorAndOtherMeshesExactlyPreserved': True, 'allActionsExact': True,
    'actionDataSha256': actions_before, 'sharedBones': len(rig.data.bones), 'fullAuthoringRetained': True,
    'hiddenProceduralAuthoringShapePropagationPending': False,
    'sourceCheckpointUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
    'scriptSha256': sha(__file__), 'newGlbExported': False, 'finalFbxExported': False,
    'fidelityVerified': False, 'motionVerified': False, 'clothCollisionVerified': False,
    'allLayersFinished': False, 'additionalTripoCreditsConsumed': 0,
    'remainingWork': ['Gathered frills and ribbon tailoring', 'Canonical face and hair correction',
                      'All-layer assembly fit', 'Validated cloth and all four actions', 'Complete dressed-character GLB/FBX update']}
assert sha(g['exports']['foundation']['sourcePhoto']) == g['exports']['foundation']['sourcePhotoSha256']
(out / 'generation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_integration.py')
print('FULL_CORSET_AUTHORING_INTEGRATED', len(modified), len(synchronized), len(bindings), blend.stat().st_size, flush=True)
