"""Verify the supplied free add-on and inventory its original node assets."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--addon-root', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
root = Path(args.addon_root).resolve()
if not (root / 'BystedtsClothBuilder' / '__init__.py').is_file():
    raise ValueError('Expected extracted BystedtsClothBuilder package.')
sys.path.insert(0, str(root))
import BystedtsClothBuilder
BystedtsClothBuilder.register()
report = {'blender': bpy.app.version_string, 'addonInfo': BystedtsClothBuilder.bl_info,
          'registered': hasattr(bpy.types.Scene, 'BCB_props'), 'libraries': [], 'nodeGroups': []}
for file in sorted((root / 'BystedtsClothBuilder' / 'BCB cloth assets').glob('*.blend')):
    with bpy.data.libraries.load(str(file), link=False) as (available, append):
        report['libraries'].append({'file': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
                                    'objects': list(available.objects), 'nodeGroups': list(available.node_groups)})
        append.node_groups = list(available.node_groups)
for group in bpy.data.node_groups:
    if group.bl_idname != 'GeometryNodeTree':
        continue
    report['nodeGroups'].append({'name': group.name, 'nodes': [n.bl_idname for n in group.nodes],
                                 'namedAttributes': [{'node': n.name, 'attribute': n.inputs['Name'].default_value,
                                                       'type': n.data_type}
                                                      for n in group.nodes if n.bl_idname in
                                                      ['GeometryNodeInputNamedAttribute', 'GeometryNodeStoreNamedAttribute']],
                                 'interface': [{'name': s.name, 'identifier': s.identifier,
                                                'direction': s.in_out, 'socketType': s.socket_type,
                                                'default': str(getattr(s, 'default_value', ''))}
                                               for s in group.interface.items_tree if s.item_type == 'SOCKET']})
decimate = bpy.types.DecimateModifier.bl_rna.properties
report['reductionProperties'] = {p: decimate[p].description for p in ['vertex_group', 'invert_vertex_group', 'vertex_group_factor']}
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print('BCB_PROBE', json.dumps(report))
