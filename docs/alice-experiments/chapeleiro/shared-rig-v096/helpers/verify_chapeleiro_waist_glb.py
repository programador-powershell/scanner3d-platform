"""Compare actual GLB buffers, allowing only documented upper bloomer weights."""
import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def glb(path):
    raw = Path(path).read_bytes()
    assert raw[:4] == b'glTF'
    size = struct.unpack_from('<I', raw, 12)[0]
    return json.loads(raw[20:20 + size]), raw[28 + size:]


def accessor(doc, binary, index):
    a = doc['accessors'][index]
    view = doc['bufferViews'][a['bufferView']]
    assert 'sparse' not in a
    dtype = np.dtype({5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2',
                      5125: '<u4', 5126: '<f4'}[a['componentType']])
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    return np.ndarray((a['count'], width), dtype=dtype, buffer=binary,
                      offset=view.get('byteOffset', 0) + a.get('byteOffset', 0),
                      strides=(view.get('byteStride', width * dtype.itemsize), dtype.itemsize)).copy()


def nodes(doc):
    return {node['name']: node for node in doc['nodes'] if 'mesh' in node and 'skin' in node}


def image_bytes(doc, binary, image):
    view = doc['bufferViews'][image['bufferView']]
    start = view.get('byteOffset', 0)
    return binary[start:start + view['byteLength']]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before', required=True)
    p.add_argument('--after', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    old, new = read(args.before), read(args.after)
    old_entry, new_entry = old['exports']['foundation'], new['exports']['foundation']
    assert sha(old_entry['model']) == old_entry['modelSha256']
    assert sha(new_entry['model']) == new_entry['modelSha256']
    waist = read(new['waistSkinRefinement'])
    allowed = {row['object'] for row in waist['actualEditedObjects']} & set(nodes(glb(new_entry['model'])[0]))
    assert len(allowed) == 9
    before, before_binary = glb(old_entry['model'])
    after, after_binary = glb(new_entry['model'])
    old_nodes, new_nodes = nodes(before), nodes(after)
    assert set(old_nodes) == set(new_nodes) and len(new_nodes) == 229
    joints = lambda doc: [doc['nodes'][i]['name'] for i in doc['skins'][0]['joints']]
    assert joints(before) == joints(after) and len(joints(after)) == 173
    for name in old_nodes:
        # Both exports place these mesh coordinates directly in the shared rig space.
        assert {k: v for k, v in old_nodes[name].items() if k != 'mesh'} == {k: v for k, v in new_nodes[name].items() if k != 'mesh'}
    checked, rows = 0, []
    for name, node in old_nodes.items():
        primitives = before['meshes'][node['mesh']]['primitives']
        next_primitives = after['meshes'][new_nodes[name]['mesh']]['primitives']
        assert len(primitives) == len(next_primitives)
        changes, low_changes, max_error, minimum_height = 0, 0, 0., None
        for old_p, new_p in zip(primitives, next_primitives):
            assert set(old_p['attributes']) == set(new_p['attributes'])
            assert old_p.get('material') == new_p.get('material')
            assert np.array_equal(accessor(before, before_binary, old_p['indices']), accessor(after, after_binary, new_p['indices']))
            values = {}
            for field in old_p['attributes']:
                a = accessor(before, before_binary, old_p['attributes'][field])
                b = accessor(after, after_binary, new_p['attributes'][field])
                assert a.shape == b.shape
                checked += 1
                if field not in ['JOINTS_0', 'WEIGHTS_0'] or name not in allowed:
                    assert np.array_equal(a, b), (name, field)
                values[field] = (a, b)
            old_j, new_j = values['JOINTS_0']
            old_w, new_w = values['WEIGHTS_0']
            changed = np.any(old_j != new_j, axis=1) | np.any(old_w != new_w, axis=1)
            height = values['POSITION'][0][:, 1]  # glTF Y up, rest coordinates unchanged
            changes += int(changed.sum())
            low_changes += int((changed & (height <= waist['lowerTransitionMeters'])).sum())
            assert not np.any(changed & (height <= waist['lowerTransitionMeters']))
            if changed.any():
                minimum_height = float(height[changed].min()) if minimum_height is None else min(minimum_height, float(height[changed].min()))
            assert np.max(new_j) < 173 and (new_w >= 0).all()
            max_error = max(max_error, float(np.abs(new_w.sum(1)-1).max()))
            assert max_error < 1e-7
        rows.append({'mesh': name, 'changedWeightVertices': changes,
                     'changedVerticesAtOrBelowTransition': low_changes,
                     'minimumChangedRestHeightMeters': minimum_height,
                     'maximumNormalizationError': max_error})
    changed_names = {r['mesh'] for r in rows if r['changedWeightVertices']}
    assert changed_names == allowed
    assert before['materials'] == after['materials'] and before['textures'] == after['textures']
    assert len(before['images']) == len(after['images'])
    for a, b in zip(before['images'], after['images']):
        assert image_bytes(before, before_binary, a) == image_bytes(after, after_binary, b)
    assert np.array_equal(accessor(before, before_binary, before['skins'][0]['inverseBindMatrices']),
                          accessor(after, after_binary, after['skins'][0]['inverseBindMatrices']))
    channel_map = lambda clip, doc: {(doc['nodes'][ch['target']['node']]['name'], ch['target']['path']):
                                     clip['samplers'][ch['sampler']] for ch in clip['channels']}
    assert [a['name'] for a in before['animations']] == [a['name'] for a in after['animations']]
    animations = []
    for a, b in zip(before['animations'], after['animations']):
        x, y = channel_map(a, before), channel_map(b, after)
        assert set(x) == set(y)
        for key in x:
            assert x[key].get('interpolation', 'LINEAR') == y[key].get('interpolation', 'LINEAR')
            for field in ['input', 'output']:
                assert np.array_equal(accessor(before, before_binary, x[key][field]), accessor(after, after_binary, y[key][field])), (a['name'], key, field)
        animations.append({'clip': a['name'], 'actualChannelArraysIdentical': True, 'channels': len(x)})
    report = {'beforeModelSha256': sha(old_entry['model']), 'afterModelSha256': sha(new_entry['model']),
              'actualMeshNodes': 229, 'actualJoints': 173, 'actualAttributeArraysCompared': checked,
              'changedWeightMeshes': [row for row in rows if row['changedWeightVertices']],
              'unchangedWeightMeshes': len(rows)-len(changed_names),
              'restGeometryUvNormalsIndicesMaterialsImagesBindJointsIdentical': True,
              'allFiveAnimationChannelArraysIdentical': True, 'animations': animations,
              'noChangesAtOrBelowWaistTransition': True, 'sourcePhotoSha256': new_entry['sourcePhotoSha256'],
              'scriptSha256': sha(__file__), 'allLayersFinished': False, 'fidelityVerified': False,
              'clothCollisionVerified': False, 'motionVerified': False, 'finalFbxExported': False}
    out = Path(args.output)
    assert not out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    shutil.copyfile(__file__, out.with_name('executed_glb_field_comparison.py'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
