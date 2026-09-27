"""Inspect the actual intact rigged head from fixed projection cameras.

Only camera, visibility and temporary shaders change. The complete master,
mesh geometry, weights, UVs and materials on disk remain unchanged.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--face-reference', required=True)
parser.add_argument('--scope', choices=['head', 'dress'], default='head')
parser.add_argument('--garment-reference')
parser.add_argument('--basecolor-only', action='store_true', help='Direct color audit without redundant surface renders')
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
g = read(args.generation)
face = read(args.face_reference)
assert sha(g['editableBlend']) == g['editableBlendSha256']
assert sha(face['canonicalPath']) == face['sha256']
if args.scope == 'dress':
    assert args.garment_reference and Path(args.garment_reference).is_file()
out = Path(args.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
inherited_denoising = scene.cycles.use_denoising
print('INHERITED_DENOISING', inherited_denoising, flush=True)
rig = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
whole = bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
assert len(whole.data.vertices) == 197575
rig.animation_data.action = None
for track in rig.animation_data.nla_tracks: track.mute = True
rig.data.pose_position = 'REST'
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
for collection in bpy.data.collections: collection.hide_viewport = collection.hide_render = False
for obj in scene.objects:
    obj.hide_viewport = obj not in (whole, rig)
    obj.hide_render = obj != whole
    obj.hide_set(obj not in (whole, rig))
    for modifier in obj.modifiers:
        if obj != whole: modifier.show_viewport = modifier.show_render = False
scene.frame_set(1)
bpy.context.view_layer.update()
points = np.array([whole.matrix_world @ vertex.co for vertex in whole.data.vertices])
head_joint = rig.matrix_world @ rig.data.bones['Head'].head_local
low_z = float(head_joint.z) - .14
upper = points[points[:, 2] > low_z] if args.scope == 'head' else points
assert len(upper) > 1000
minimum, maximum = upper.min(0), upper.max(0)
center = Vector((minimum + maximum) / 2)
span = max(float(maximum[2] - minimum[2]), float(maximum[0] - minimum[0]),
           float(maximum[1] - minimum[1])) * 1.12
camera_data = bpy.data.cameras.new('Fixed Alice ' + args.scope + ' projection camera')
camera = bpy.data.objects.new(camera_data.name, camera_data)
scene.collection.objects.link(camera)
camera_data.type = 'ORTHO'
camera_data.ortho_scale = span
camera_data.clip_start = .001
scene.camera = camera
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.render.resolution_x = scene.render.resolution_y = 1024
if args.scope == 'dress':
    scene.render.resolution_y = 1536
    scene.cycles.samples = 8
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = True
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Neutral Alice head baseline')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.2, .2, .2, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .65
scene.world = world
for name, direction, energy in [('Key', (1, -2, 2), 25), ('Fill', (-2, -1, 1), 15), ('Back', (0, 2, 1), 25)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.size = energy * span ** 2, span * 1.5
    lamp = bpy.data.objects.new(name, data)
    scene.collection.objects.link(lamp)
    lamp.location = center + Vector(direction).normalized() * span * 2
    lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
mesh = whole.data
mesh.calc_loop_triangles()
vertices = np.empty(len(mesh.vertices) * 3, np.float32)
mesh.vertices.foreach_get('co', vertices)
triangles = np.array([triangle.vertices[:] for triangle in mesh.loop_triangles], np.int32)
loops = np.array([triangle.loops[:] for triangle in mesh.loop_triangles], np.int32)
uv = np.array([entry.uv[:] for entry in mesh.uv_layers.active.data], np.float32)
np.savez_compressed(out / 'native_head_projection_geometry.npz', vertices=vertices.reshape(-1, 3),
                    world_points=points, triangles=triangles, triangle_loops=loops, uv=uv,
                    polygon_indices=np.array([triangle.polygon_index for triangle in mesh.loop_triangles], np.int32))
images = []
for material in mesh.materials:
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            item = {'name': node.image.name, 'size': list(node.image.size),
                    'colorspace': node.image.colorspace_settings.name, 'node': node.name}
            if node.image.packed_file: item['packed'] = True
            images.append(item)
print('HEAD_BASELINE_GEOMETRY_READY', json.dumps({'headJoint': list(head_joint), 'center': list(center), 'span': span, 'images': images}), flush=True)
directions = [('front', (0, -1, 0)), ('left', (1, 0, 0)), ('right', (-1, 0, 0)), ('back', (0, 1, 0))]
renders = []
for view, direction in directions:
    if args.basecolor_only: break
    camera.location = center + Vector(direction) * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / f'{view}_surface.png')
    bpy.ops.render.render(write_still=True)
    renders.append({'view': view, 'kind': 'surface', 'file': scene.render.filepath,
                    'sha256': sha(scene.render.filepath), 'cameraWorldMatrix': np.array(camera.matrix_world).tolist(),
                    'cameraProjectionMatrix': np.array(camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),
                      x=scene.render.resolution_x, y=scene.render.resolution_y)).tolist()})
    print('ACTUAL_HEAD_BASELINE_RENDERED', view, 'surface', flush=True)
# A direct base-color pass distinguishes baked dirt from actual 3D lighting.
for index, original in enumerate(list(mesh.materials)):
    material = original.copy()
    mesh.materials[index] = material
    nodes = material.node_tree.nodes
    bsdf = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL')
    emission = nodes.new('ShaderNodeEmission')
    base = bsdf.inputs['Base Color']
    if base.is_linked:
        material.node_tree.links.new(base.links[0].from_socket, emission.inputs['Color'])
    else:
        emission.inputs['Color'].default_value = base.default_value
    material.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
# Denoising changes surrounding original material pixels when garment colors
# change. Disable it for a deterministic direct-color comparison; surface
# lighting renders retain their normal presentation settings.
scene.cycles.samples = 4
scene.cycles.use_denoising = False
scene.cycles.use_adaptive_sampling = False
scene.cycles.seed = 0
scene.cycles.use_animated_seed = False
for view, direction in directions:
    camera.location = center + Vector(direction) * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / f'{view}_basecolor.png')
    bpy.ops.render.render(write_still=True)
    renders.append({'view': view, 'kind': 'basecolor', 'file': scene.render.filepath,
                    'sha256': sha(scene.render.filepath), 'cameraWorldMatrix': np.array(camera.matrix_world).tolist(),
                    'cameraProjectionMatrix': np.array(camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),
                      x=scene.render.resolution_x, y=scene.render.resolution_y)).tolist()})
    print('ACTUAL_HEAD_BASELINE_RENDERED', view, 'basecolor', flush=True)
report = {'generation': str(Path(args.generation).resolve()),
          'scope': args.scope, 'resolution': [scene.render.resolution_x, scene.render.resolution_y],
          'garmentReference': args.garment_reference,
          'garmentReferenceSha256': sha(args.garment_reference) if args.garment_reference else None,
          'parentEditableSha256': g['editableBlendSha256'], 'parentEditableUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'canonicalFaceReference': face['canonicalPath'], 'canonicalFaceReferenceSha256': face['sha256'],
          'nativeWholeObject': whole.name, 'nativeVertices': len(mesh.vertices), 'nativeTriangles': len(triangles),
          'nativeUvLayers': [layer.name for layer in mesh.uv_layers], 'sourceImages': images,
          'headJoint': list(head_joint), 'cameraCenter': list(center), 'orthoScale': span,
          'renders': renders, 'geometryFile': str(out / 'native_head_projection_geometry.npz'),
          'basecolorRenderSettings': {'samples': 4, 'denoising': False, 'adaptiveSampling': False, 'seed': 0},
          'inheritedDenoising': inherited_denoising,
          'geometrySha256': sha(out / 'native_head_projection_geometry.npz'),
          'scriptSha256': sha(__file__), 'hairSegmentationPending': True, 'hairUv4kBakePending': True,
          'dressSegmentationPending': args.scope == 'dress', 'dressUv4kBakePending': args.scope == 'dress',
          'headFidelityVerified': False, 'allModelsUpdated': False, 'newGlbOrFbxExported': False,
          'additionalTripoCreditsConsumed': 0}
(out / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_render.py')
print('ACTUAL_HEAD_BASELINE_COMPLETE', flush=True)
