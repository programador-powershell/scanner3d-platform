"""Export and inspect an actual character asset. No primitive fallback.

Run inside Blender: blender -b --factory-startup --python-exit-code 1
 --python blender/export_character.py -- --job job.json --base-mesh source.glb
 --out output --stage full
Stages identify the subject under review, not newly generated body parts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--base-mesh', required=True)
    parser.add_argument('--stage', default='full', choices=['full', 'skeleton', 'muscles', 'garment', 'skin', 'nails', 'face', 'eyes', 'hair'])
    # Accepted for compatibility. References must never be sampled as a single
    # skin colour or projected indiscriminately onto the character's head.
    parser.add_argument('--ref-image', default='')
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def main():
    args = parse_args()
    source, out = Path(args.base_mesh), Path(args.out)
    if not source.is_file():
        raise RuntimeError('A real source mesh is required. No generic body will be substituted.')
    job = json.loads(Path(args.job).read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if source.suffix.lower() == '.glb':
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif source.suffix.lower() == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(source))
    else:
        raise RuntimeError('Source must be an embedded GLB or FBX')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    if not meshes or not any(len(o.data.polygons) for o in meshes):
        raise RuntimeError('No actual mesh faces in source')
    target_height = job.get('params', {}).get('target_height_m')
    if target_height is not None:
        if not isinstance(target_height, (float, int)) or not 0.5 <= target_height <= 3:
            raise RuntimeError('Explicit target height must be between 0.5 and 3 metres')
        bpy.context.view_layer.update()
        points = [o.matrix_world @ Vector(p) for o in meshes for p in o.bound_box]
        height = max(p.z for p in points) - min(p.z for p in points)
        ratio = target_height / height
        for obj in bpy.context.scene.objects:
            if obj.parent is None:
                obj.scale *= ratio
                obj.location *= ratio
        bpy.context.view_layer.update()
    for mesh in meshes:
        mesh.data.update()
    points = [o.matrix_world @ Vector(p) for o in meshes for p in o.bound_box]
    minimum = Vector([min(p[i] for p in points) for i in range(3)])
    maximum = Vector([max(p[i] for p in points) for i in range(3)])
    size = maximum - minimum
    if min(size) < 1e-5:
        raise RuntimeError('Source is planar; a photograph is not a 3D character')
    if args.stage == 'skeleton' and not rigs:
        raise RuntimeError('Source has no rig; no invented rig approval is possible')
    print(f'[build] Imported actual geometry: {sum(len(o.data.polygons) for o in meshes)} polygons, {len(rigs)} rigs', flush=True)
    print('[build] Stage selects review focus only. No claim of anatomical reconstruction or cloth simulation.', flush=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes + rigs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.export_scene.gltf(filepath=str(out / 'character.glb'), export_format='GLB',
                              use_selection=True, export_animations=True, export_skins=True)
    bpy.ops.export_scene.fbx(filepath=str(out / 'character.fbx'), use_selection=True,
                             object_types={'MESH', 'ARMATURE'}, add_leaf_bones=False,
                             axis_forward='-Y', axis_up='Z', path_mode='COPY', embed_textures=True)
    # Record the real asset before any render-only lighting/camera setup.
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'character.blend'))
    center = (maximum + minimum) / 2
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 440
    scene.render.resolution_y = 850
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    # Albedo-style evidence: use the existing colour texture and do not add
    # highlights that could be mistaken for detail restored from the reference.
    temporary_materials = []
    for o in meshes:
        for slot in o.material_slots:
            original = slot.material
            if not original:
                continue
            material = original.copy()
            material.use_nodes = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
            if bsdf and output:
                emission = nodes.new('ShaderNodeEmission')
                color = bsdf.inputs.get('Base Color')
                emission.inputs['Color'].default_value = color.default_value
                if color.is_linked:
                    links.new(color.links[0].from_socket, emission.inputs['Color'])
                links.new(emission.outputs[0], output.inputs['Surface'])
            slot.material = material
            temporary_materials.append(material)
    camera_data = bpy.data.cameras.new('Evidence camera')
    camera = bpy.data.objects.new('Evidence camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = size.z * 1.12
    distance = max(size) * 5
    cameras = {'front': Vector((0, -1, 0)), 'side': Vector((1, 0, 0)), 'back': Vector((0, 1, 0))}
    for view, direction in cameras.items():
        camera.location = center + direction * distance
        camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / f'preview_{view}.png')
        bpy.ops.render.render(write_still=True)
        print(f'[build] Real orthographic render: {view}', flush=True)
    report = {'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'jobId': job.get('id'), 'stage': args.stage, 'geometrySource': 'imported-asset',
              'geometryReconstructed': False, 'fidelityStatus': 'awaiting_review',
              'meshes': [{'name': o.name, 'vertices': len(o.data.vertices), 'polygons': len(o.data.polygons)} for o in meshes],
              'rigs': [{'name': o.name, 'bones': len(o.data.bones)} for o in rigs],
              'renderViews': list(cameras), 'rigVerified': False, 'clothPhysicsVerified': False,
              'renderSpace': 'Blender Z-up; front=-Y, profile=+X, back=+Y',
              'bounds': {'min': list(minimum), 'max': list(maximum)},
              'limitations': ['Exporting an asset does not prove reference fidelity or UE 5.7 compatibility.',
                              'Stages do not generate missing geometry; the original imported asset is inspected.']}
    (out / 'build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('[build] Actual asset exported with three views. Visual review is pending.', flush=True)


if __name__ == '__main__':
    main()
