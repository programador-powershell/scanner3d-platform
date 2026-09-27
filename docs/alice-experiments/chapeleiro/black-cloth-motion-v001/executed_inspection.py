"""Inspect actual authored BlackCloth supports without changing the checkpoint."""
import argparse, hashlib, json, sys
from pathlib import Path
import bpy
import numpy as np

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
path = Path(a.generation)
g, schema = read(path), read(path.parent / 'shared_rig_bind.json')
assert sha(g['editableBlend']) == g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
names = [n for n, family in schema['pieceFamilies'].items() if family == 'BlackCloth']
rows = []
for name in names:
    preview, authoring = bpy.data.objects[name], bpy.data.objects.get('Authoring / ' + name)
    assert authoring is not None
    xyz = np.array([list(v.co) for v in authoring.data.vertices])
    modifiers = []
    for m in authoring.modifiers:
        row = {'name': m.name, 'type': m.type}
        if m.type == 'NODES': row['group'] = m.node_group.name
        if m.type == 'SURFACE_DEFORM': row.update(target=m.target.name, bound=m.is_bound)
        modifiers.append(row)
    rows.append({'preview': preview.name, 'authoring': authoring.name,
                 'previewVertices': len(preview.data.vertices), 'authoredVertices': len(authoring.data.vertices),
                 'authoredPolygons': len(authoring.data.polygons),
                 'authoredPolygonSizes': sorted({len(p.vertices) for p in authoring.data.polygons}),
                 'modifiers': modifiers, 'vertexGroups': [v.name for v in authoring.vertex_groups],
                 'parent': authoring.parent.name if authoring.parent else None,
                 'bounds': [xyz.min(0).tolist(), xyz.max(0).tolist()],
                 'authoringProperties': {k: str(authoring[k]) for k in authoring.keys()}})
report = {'editableSha256': g['editableBlendSha256'], 'sourcePhotoSha256': g['exports']['foundation']['sourcePhotoSha256'],
          'actualBlackFamilyPieces': len(rows), 'pieces': rows, 'scriptSha256': sha(__file__),
          'checkpointUnchanged': sha(g['editableBlend']) == g['editableBlendSha256'],
          'allLayersFinished': False, 'clothCollisionVerified': False}
Path(a.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print('ACTUAL_BLACK_CLOTH_SUPPORTS_INSPECTED', len(rows))
