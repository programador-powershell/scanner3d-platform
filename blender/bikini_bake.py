"""Bake ONE existing Geometry Nodes collection to static candidate geometry.
Run in the pinned external BIKINI, never with Python alone. No image reconstruction.
Input .blend is read-only; rigged/shape-key/cloth layers are rejected, not flattened.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def digest(file):
    h = hashlib.sha256()
    with open(file, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def arguments():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--collection', required=True)
    parser.add_argument('--out', type=Path, required=True)
    return parser.parse_args(argv)


def main():
    args = arguments()
    source, out = args.input.resolve(), args.out.resolve()
    if source.suffix.lower() != '.blend' or not source.is_file():
        raise ValueError('A real .blend containing the layer is required')
    # Host wrapper creates the empty folder; do not overwrite old candidate outputs.
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Output must be empty')
    source_hash = digest(source)
    import bpy
    if tuple(bpy.app.version[:2]) != (5, 3):
        raise RuntimeError('Expected the pinned Blender 5.3 BIKINI build')
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    collection = bpy.data.collections.get(args.collection)
    if collection is None:
        raise ValueError('Collection not found: ' + args.collection)
    originals = list(bpy.data.objects)
    layers = list(collection.all_objects)
    meshes = [o for o in layers if o.type == 'MESH']
    if not meshes:
        raise ValueError('The selected collection contains no mesh')
    if any(o.type not in {'MESH', 'EMPTY'} for o in layers):
        raise ValueError('Static-mesh lane only. Do not flatten armatures, curves or other objects silently.')
    if not any(m.type == 'NODES' for o in meshes for m in o.modifiers):
        raise ValueError('No Geometry Nodes modifier in the selected layer')
    for obj in meshes:
        if obj.data.shape_keys or obj.vertex_groups or any(m.type in {'ARMATURE', 'CLOTH', 'SOFT_BODY'} for m in obj.modifiers):
            raise ValueError('Deformable layer rejected: ' + obj.name + '. Preserve rig/weights and use a dedicated character workflow.')
    graph = bpy.context.evaluated_depsgraph_get()
    for instance in graph.object_instances:
        parent = instance.parent
        if instance.is_instance and parent is not None and parent.original in meshes:
            raise ValueError('Unrealized instances detected. Add Realize Instances before baking this layer.')
    generated, stats = [], []
    for obj in meshes:
        evaluated = obj.evaluated_get(graph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
        if not mesh or not len(mesh.vertices) or not len(mesh.polygons):
            raise RuntimeError('Empty evaluated geometry: ' + obj.name)
        if not all(math.isfinite(float(c)) for v in mesh.vertices for c in v.co):
            raise RuntimeError('Non-finite vertex: ' + obj.name)
        mesh.calc_loop_triangles()
        candidate = bpy.data.objects.new(obj.name + '_BakedCandidate', mesh)
        candidate.matrix_world = obj.matrix_world.copy()
        candidate['source_object'] = obj.name
        candidate['fidelity_status'] = 'awaiting_visual_review'
        candidate['source_sha256'] = source_hash
        bpy.context.scene.collection.objects.link(candidate)
        generated.append(candidate)
        stats.append({'object': obj.name, 'vertices': len(mesh.vertices), 'triangles': len(mesh.loop_triangles),
                      'uvLayers': [uv.name for uv in mesh.uv_layers],
                      'nodeGroups': [m.node_group.name for m in obj.modifiers if m.type == 'NODES' and m.node_group]})
    # Only the requested layer is exported. The source stays intact on disk.
    for obj in originals:
        bpy.data.objects.remove(obj, do_unlink=True)
    for obj in generated:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = generated[0]
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'candidate.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out / 'candidate.glb'), export_format='GLB', use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(out / 'candidate.fbx'), use_selection=True,
                             object_types={'MESH'}, add_leaf_bones=False, bake_anim=False)
    if digest(source) != source_hash:
        raise RuntimeError('Source changed during bake; do not approve candidate')
    hashes = {}
    for name in ['candidate.blend', 'candidate.glb', 'candidate.fbx']:
        file = out / name
        if not file.is_file() or not file.stat().st_size:
            raise RuntimeError('Export missing: ' + name)
        hashes[name] = digest(file)
    report = {'schemaVersion': 1, 'operation': 'bikini.geometry_nodes_static_bake',
              'status': 'candidate_exported_not_approved', 'sourceSha256': source_hash,
              'collection': args.collection, 'objects': stats, 'artifacts': hashes,
              'unitScaleMeters': bpy.context.scene.unit_settings.scale_length,
              'fidelityVerified': False, 'unrealVerified': False,
              'limitations': ['Unreal does not execute BIKINI nodes; this exports evaluated static meshes.',
                              'Material graphs/textures are not baked by this geometry operation.',
                              'Realize instances in the node graph before export; verify the result visually.',
                              'Bounds, scale, normals, UVs and materials still require engine validation.']}
    (out / 'bake_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('[BIKINI] Static layer candidate exported; fidelity and Unreal remain unverified.')


if __name__ == '__main__':
    main()
