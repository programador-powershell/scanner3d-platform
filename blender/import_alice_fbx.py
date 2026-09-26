"""Import the pinned Project Alice FBX, select one real LOD and repair colour.

blender -b --factory-startup --python-exit-code 1 --python
 blender/import_alice_fbx.py -- --source alice.fbx --out data/assets/alice-detail.glb

The upstream FBX has five overlapping LODs and places its embedded colour map
on Emission Color. Select LOD3 only and connect the existing UV atlas to Base
Color. No geometry, texture or rig is invented. This asset is a static mesh.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

EXPECTED_SHA256 = '707db04639e87b74d21b298bc8c32033e2fb144c2c22c38f11acf8092d05b248'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--lod', type=int, choices=range(5), default=3)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    source, out = Path(args.source).resolve(), Path(args.out).resolve()
    actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual_hash != EXPECTED_SHA256:
        raise RuntimeError('FBX hash differs from the pinned Project Alice source; inspect it before changing the manifest.')
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(source))
    mesh = bpy.data.objects.get(f'model_LOD{args.lod}')
    if not mesh or mesh.type != 'MESH':
        raise RuntimeError('Expected LOD mesh is missing')
    for o in list(bpy.context.scene.objects):
        if o != mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    for material in mesh.data.materials:
        nodes, links = material.node_tree.nodes, material.node_tree.links
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        image = next((n for n in nodes if n.type == 'TEX_IMAGE' and n.image and n.image.size[0] > 0), None)
        if not image:
            raise RuntimeError('The embedded colour atlas is missing; refusing an untextured success.')
        image.image.colorspace_settings.name = 'sRGB'
        links.new(image.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Emission Strength'].default_value = 0
        bsdf.inputs['Metallic'].default_value = 0
        bsdf.inputs['Roughness'].default_value = 0.68
        # Empty Normal Map nodes are not evidence of a captured normal texture.
        for link in list(bsdf.inputs['Normal'].links):
            links.remove(link)
        material.name = 'Alice · original embedded UV colour atlas'
    bpy.context.view_layer.update()
    points = [mesh.matrix_world @ Vector(p) for p in mesh.bound_box]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    scale = 1.70433886 / (hi.z - lo.z)
    mesh.scale *= scale; mesh.location *= scale
    bpy.context.view_layer.update()
    points = [mesh.matrix_world @ Vector(p) for p in mesh.bound_box]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    mesh.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(out), export_format='GLB', use_selection=True, export_animations=False)
    report = {'method': 'existing-fbx-lod-import-and-material-repair', 'sourceSha256': actual_hash,
              'outputSha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'lod': args.lod,
              'polygons': len(mesh.data.polygons), 'vertices': len(mesh.data.vertices),
              'geometryReconstructed': False, 'fidelityStatus': 'unverified', 'rigged': False,
              'source': {'repository': 'https://github.com/programador-powershell/project-alice-game',
                         'commit': 'f6e534865a7b3432b6c7b374e8e10921905b4e4c',
                         'path': 'Content/Assets/3D/personagens/alice.fbx',
                         'author': 'Programador de Powershell · Project Alice — Challenge'},
              'repairs': ['Select one LOD to avoid five overlapping copies.',
                          'Use the embedded shaded.png UV atlas as base colour instead of emission.'],
              'limitations': ['Static fused mesh: no independent garment layers, verified rig or cloth physics.',
                              'Original shaded texture includes baked lighting; this is not captured PBR albedo.',
                              'Visual similarity still requires front, side and back review.']}
    out.with_suffix('.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
