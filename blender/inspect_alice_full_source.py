"""Read-only source and Geometry Nodes audit before whole-outfit processing."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
source = json.loads(Path(args.generation).read_text(encoding='utf-8'))
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
for path, expected in [('model', 'modelSha256'), ('editableBlend', 'editableBlendSha256')]:
    if digest(source[path]) != source[expected]:
        raise ValueError(f'Source checksum mismatch: {path}')
bpy.ops.wm.open_mainfile(filepath=source['editableBlend'])
report = {'sourceGeneration': args.generation, 'sourceBlendSha256': source['editableBlendSha256'],
          'sourceModelSha256': source['modelSha256'], 'blender': bpy.app.version_string, 'meshes': [], 'nodes': {}}
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    mesh = obj.data
    uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get('uv', uv)
    mesh.calc_loop_triangles()
    materials = []
    for material in mesh.materials:
        materials.append({'name': material.name,
                          'images': [{'name': n.image.name, 'size': list(n.image.size),
                                      'colorspace': n.image.colorspace_settings.name,
                                      'packed': bool(n.image.packed_file)}
                                     for n in material.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image],
                          'links': [(l.from_node.type, l.from_socket.name, l.to_node.type, l.to_socket.name)
                                    for l in material.node_tree.links]})
    report['meshes'].append({'name': obj.name, 'vertices': len(mesh.vertices), 'edges': len(mesh.edges),
                             'polygons': len(mesh.polygons), 'triangles': len(mesh.loop_triangles),
                             'dimensions': list(obj.dimensions), 'uvMaps': [u.name for u in mesh.uv_layers],
                             'uvFinite': bool(np.isfinite(uv).all()), 'uvMin': float(uv.min()), 'uvMax': float(uv.max()),
                             'seams': sum(e.use_seam for e in mesh.edges), 'materials': materials,
                             'shapeKeys': bool(mesh.shape_keys), 'modifiers': [m.type for m in obj.modifiers]})
group = bpy.data.node_groups.new('Audit / temporary', 'GeometryNodeTree')
for node_type in ['GeometryNodeExtrudeMesh', 'GeometryNodeUVUnwrap', 'GeometryNodeUVPackIslands',
                  'GeometryNodeSplitEdges', 'GeometryNodeStoreNamedAttribute', 'GeometryNodeMeshToCurve',
                  'GeometryNodeInputMeshEdgeNeighbors', 'GeometryNodeMergeByDistance', 'GeometryNodeFlipFaces']:
    node = group.nodes.new(node_type)
    report['nodes'][node_type] = {'inputs': [(s.name, s.identifier, s.type) for s in node.inputs],
                                 'outputs': [(s.name, s.identifier, s.type) for s in node.outputs]}
bpy.data.node_groups.remove(group)
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('FULL_SOURCE_AUDIT', json.dumps(report))
