"""Close boundary loops on independent thin proxies, preserving source skins."""
import hashlib, json
import bmesh
import numpy as np
from chapeleiro_cloth_colliders import thin_underlayer_colliders

def _state(obj):
    return {'points': np.asarray([tuple(v.co) for v in obj.data.vertices], np.float32),
            'faces': [list(p.vertices) for p in obj.data.polygons],
            'groups': [g.name for g in obj.vertex_groups],
            'weights': [[(w.group, w.weight) for w in v.groups] for v in obj.data.vertices]}

def closed_thin_underlayer_proxies(scene, audit, names, rig):
    proxies, rows = thin_underlayer_colliders(scene, audit, names, rig)
    for obj, row in zip(proxies, rows):
        source_data = obj.data
        before = _state(obj)
        # Never cap the shared original mesh: only this independent copy changes.
        obj.data = source_data.copy()
        assert [g.name for g in obj.vertex_groups] == before['groups']
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        boundary = [e for e in bm.edges if e.is_boundary]
        created = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)['faces']
        bm.normal_update()
        assert not any(e.is_boundary or not e.is_manifold for e in bm.edges)
        cap_count = len(created)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        after = _state(obj)
        assert np.array_equal(after['points'], before['points'])
        assert after['groups'] == before['groups'] and after['weights'] == before['weights']
        assert len(obj.data.vertices) == len(source_data.vertices)
        assert np.array_equal(np.asarray([tuple(v.co) for v in source_data.vertices], np.float32), before['points'])
        assert [list(p.vertices) for p in source_data.polygons] == before['faces']
        row.update({'closedIndependentProxy': True, 'boundaryEdgesBefore': len(boundary),
                    'boundaryEdgesAfter': 0, 'capsCreated': cap_count,
                    'verticesBoneGroupsAndWeightsExactlyPreserved': True,
                    'originalSharedMeshCoordinatesAndFacesExactlyPreserved': True,
                    'proxyRawGeometrySha256': hashlib.sha256(after['points'].tobytes() + json.dumps(after['faces']).encode()).hexdigest()})
    return proxies, rows
