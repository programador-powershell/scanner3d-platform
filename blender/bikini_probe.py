"""Run INSIDE BIKINI. Calibration exports are explicitly NOT game content.
No character, rig, rendering, fidelity or Unreal approval is issued here.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path


def arguments():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--nonce', required=True)
    return parser.parse_args(argv)


def main():
    args = arguments()
    if not re.fullmatch(r'[a-f0-9]{32}', args.nonce):
        raise ValueError('Invalid nonce')
    import bpy
    from mathutils import Vector
    if tuple(bpy.app.version[:2]) != (5, 3):
        raise RuntimeError('Expected the pinned Blender 5.3 BIKINI build')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any((out / name).exists() for name in ['probe.json', 'calibration.glb', 'calibration.fbx', 'calibration.blend']):
        raise RuntimeError('Probe output must be fresh; refusing overwrite')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    tree = bpy.data.node_groups.new('BIKINI_Capability_Probe', 'GeometryNodeTree')
    nodes = []
    # Discover actual RNA IDs and sockets, rather than trusting documentation-only names.
    pattern = re.compile(r'cgal|bikini|instant.?mesh|quadwild|jolt|pmp|mpm|pbd|flip.*solver|box.*engine', re.I)
    for identifier in sorted(dir(bpy.types)):
        if not identifier.startswith('GeometryNode'):
            continue
        cls = getattr(bpy.types, identifier)
        label = str(getattr(cls, 'bl_label', ''))
        if not pattern.search(identifier + ' ' + label):
            continue
        node = None
        try:
            node = tree.nodes.new(identifier)
            sockets = lambda values: [
                {'name': s.name, 'identifier': s.identifier, 'type': s.bl_idname}
                for s in values
            ]
            nodes.append({'id': node.bl_idname, 'label': node.name, 'instantiated': True,
                          'inputs': sockets(node.inputs), 'outputs': sockets(node.outputs),
                          'solverExecuted': False})
        except Exception as error:
            nodes.append({'id': identifier, 'instantiated': False, 'error': str(error)[:240],
                          'solverExecuted': False})
        finally:
            if node is not None:
                tree.nodes.remove(node)
    bpy.data.node_groups.remove(tree)

    # Standard Blender geometry/export smoke; NOT a benchmark of extra BIKINI nodes.
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.object
    cube.name = 'TECHNICAL_FIXTURE_NOT_GAME_CONTENT'
    cube['technical_fixture'] = True
    cube.scale = (1.0, 2.0, 3.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'calibration.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out / 'calibration.glb'), export_format='GLB', use_selection=True)
    bpy.ops.export_scene.fbx(filepath=str(out / 'calibration.fbx'), use_selection=True,
                             object_types={'MESH'}, add_leaf_bones=False, bake_anim=False)
    for name in ['calibration.glb', 'calibration.fbx', 'calibration.blend']:
        if not (out / name).is_file() or not (out / name).stat().st_size:
            raise RuntimeError('Export missing: ' + name)

    bpy.data.objects.remove(cube, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(out / 'calibration.glb'))
    imported = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    if not imported:
        raise RuntimeError('GLB roundtrip produced no mesh')
    coords = [o.matrix_world @ Vector(v) for o in imported for v in o.bound_box]
    dimensions = [max(v[axis] for v in coords) - min(v[axis] for v in coords) for axis in range(3)]
    ok = all(math.isclose(value, expected, rel_tol=1e-5, abs_tol=1e-5)
             for value, expected in zip(dimensions, [1.0, 2.0, 3.0]))
    if not ok:
        raise RuntimeError('GLB roundtrip changed the 1 x 2 x 3 meter calibration')
    build_hash = bpy.app.build_hash
    if isinstance(build_hash, bytes):
        build_hash = build_hash.decode('utf-8', errors='replace')
    report = {'schemaVersion': 1, 'nonce': args.nonce, 'status': 'export_smoke_passed',
              'scope': 'technical_fixture_not_game_content', 'version': list(bpy.app.version),
              'versionString': bpy.app.version_string, 'buildHash': str(build_hash),
              'exporters': {'glb': True, 'fbx': True},
              'smoke': {'roundtripOk': True, 'dimensionsMeters': dimensions}, 'nodes': nodes,
              'renderTested': False, 'extraSolversTested': False,
              'warnings': ['RNA discovery is not a solver accuracy test.',
                           'Calibration is not a character or visual-fidelity test.',
                           'DLSS/NGX and Unreal were not exercised.']}
    (out / 'probe.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('[BIKINI] Calibration export passed. Character, solvers and Unreal NOT tested.')


if __name__ == '__main__':
    main()
