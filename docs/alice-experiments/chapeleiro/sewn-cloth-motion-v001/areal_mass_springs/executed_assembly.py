"""Build a local sewn simulation assembly from actual authored petticoats.

Visual garments and the intact dressed character are preserved. Only the new
simulation assembly aligns flounce roots to measured support rings. Each part
keeps its explicit Ivory/Black field; no spatial guess assigns its family.
"""
from collections import defaultdict
import hashlib
import json
import bpy
import numpy as np
from mathutils import Vector
from chapeleiro_shared_rig_fields import GarmentFields, WEIGHT_QUANTIZATION

def _world_points(obj):
    return np.asarray([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices], np.float32)

def _raw_hash(obj):
    points = np.asarray([tuple(v.co) for v in obj.data.vertices], np.float32)
    faces = [list(p.vertices) for p in obj.data.polygons]
    return hashlib.sha256(points.tobytes() + json.dumps(faces).encode()).hexdigest()

def _values(obj, name):
    if name not in obj.vertex_groups: return np.zeros(len(obj.data.vertices), np.float32)
    index = obj.vertex_groups[name].index
    return np.asarray([next((w.weight for w in v.groups if w.group == index), 0.) for v in obj.data.vertices], np.float32)

def assemble_sewn_petticoats(scene, rig, schema, include_ivory=True, seam_clearance=.001):
    names = ['01 / black petticoat continuous waist support'] + ['01 / black gathered flounce ' + str(i) for i in range(1, 4)]
    keys = ['support', 'tier1', 'tier2', 'tier3']
    if include_ivory:
        names.insert(0, '01 / long ivory gathered petticoat')
        keys.insert(0, 'ivory')
    sources = [bpy.data.objects['Authoring / ' + n] for n in names]
    # Ivory uses an explicit skinned midsurface created later than its visual
    # authoring receiver. Preserve that actual 192 x 37 carrier as the source.
    if include_ivory:
        sources[0] = bpy.data.objects['01 / long ivory gathered petticoat / petticoat simulation midsurface']
    source_hashes = {o.name: _raw_hash(o) for o in sources}
    original = [_world_points(o) for o in sources]
    expected = {'ivory': 7104, 'support': 7488, 'tier1': 2496, 'tier2': 2496, 'tier3': 2496}
    assert all(len(points) == expected[key] for key, points in zip(keys, original))
    around = 192
    support_index = keys.index('support')
    support = original[support_index].reshape(39, around, 3)
    edited = [p.copy() for p in original]
    offsets = np.cumsum([0] + [len(p) for p in original[:-1]]).tolist()
    seams, parts = [], []
    for i, (key, source, points) in enumerate(zip(keys, sources, edited)):
        local_seams = []
        if key.startswith('tier'):
            for col in range(around):
                row = int(np.argmin(np.abs(support[:, col, 2] - points[col, 2])))
                measured = support[row, col].copy()
                outward = measured - support[row].mean(0)
                outward[2] = 0
                outward /= np.linalg.norm(outward)
                target = measured + outward * seam_clearance
                delta = target - points[col]
                # Adjust only the new simulation rest pattern. A smooth falloff
                # preserves the original flounce bottom and its visual mesh.
                for r in range(13):
                    t = r / 12
                    fade = 1 - t * t * (3 - 2 * t)
                    points[r * around + col] += delta * fade
                pair = [offsets[support_index] + row * around + col, offsets[i] + col]
                seams.append(pair)
                local_seams.append(pair)
        movement = np.linalg.norm(points - original[i], axis=1)
        parts.append({'key': key, 'source': source.name, 'visibleGarment': names[i],
                      'family': 'IvoryCloth' if key == 'ivory' else 'BlackCloth',
                      'start': offsets[i], 'vertices': len(points), 'faces': len(source.data.polygons),
                      'originalPhotoSha256': source.get('originalLayerPhotoSha256', ''),
                      'sourceRawGeometrySha256': source_hashes[source.name],
                      'originalWorldPointsSha256': hashlib.sha256(original[i].tobytes()).hexdigest(),
                      'localRestPatternMaximumAdjustmentMeters': float(movement.max()),
                      'localRestPatternAdjustedVertices': int(np.count_nonzero(movement > 1e-7)),
                      'sewingEdges': local_seams})
    vertices = np.concatenate(edited)
    faces = [tuple(offsets[i] + j for j in p.vertices) for i, source in enumerate(sources) for p in source.data.polygons]
    mesh = bpy.data.meshes.new('Local sewn Ivory and Black simulation pattern')
    mesh.from_pydata(vertices.tolist(), seams, faces)
    mesh.update()
    cage = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(cage)
    assert sum(e.is_loose for e in mesh.edges) == len(seams) == 576
    for name in ['pinned', 'stiffness', 'shrinking', 'pressure']:
        group = cage.vertex_groups.new(name=name)
        for i, source in enumerate(sources):
            values = _values(source, name)
            if name == 'pinned' and keys[i].startswith('tier'): values[:] = 0
            for value in np.unique(values):
                if value > 0:
                    ids = (np.flatnonzero(values == value) + offsets[i]).tolist()
                    group.add(ids, float(value), 'REPLACE')
    fields = GarmentFields(rig, schema['clothFamilies'])
    batches = defaultdict(list)
    for part in parts:
        for index in range(part['start'], part['start'] + part['vertices']):
            weights = fields.cloth(Vector(vertices[index]), part['family'])
            integers = {n: round(w * WEIGHT_QUANTIZATION) for n, w in weights.items()}
            largest = max(weights, key=weights.get)
            integers[largest] += WEIGHT_QUANTIZATION - sum(integers.values())
            for name, weight in integers.items():
                if weight > 0: batches[(name, weight)].append(index)
    groups = {n: cage.vertex_groups.new(name=n) for n in sorted({n for n, w in batches})}
    for (name, weight), indices in batches.items(): groups[name].add(indices, weight / WEIGHT_QUANTIZATION, 'REPLACE')
    indices = {g.index for g in groups.values()}
    maximum_error, maximum_influences = 0., 0
    for v in mesh.vertices:
        weights = [w.weight for w in v.groups if w.group in indices]
        assert weights
        maximum_error = max(maximum_error, abs(sum(weights) - 1))
        maximum_influences = max(maximum_influences, len(weights))
    assert maximum_error < 1e-7 and maximum_influences <= 4
    arm = cage.modifiers.new('Existing shared garment rig / before sewn Cloth', 'ARMATURE')
    arm.object = rig
    assert {o.name: _raw_hash(o) for o in sources} == source_hashes
    return cage, parts, {
        'includedIvory': include_ivory, 'actualSewingEdges': len(seams),
        'seamClearanceMeters': seam_clearance, 'actualVertices': len(mesh.vertices),
        'actualFaces': len(mesh.polygons), 'actualLooseEdges': sum(e.is_loose for e in mesh.edges),
        'maximumSkinWeightNormalizationError': maximum_error, 'maximumSkinInfluences': maximum_influences,
        'visualSourceGeometryUnchanged': True, 'sewingReplacesFlouncePinConstraints': True,
        'restPatternChangesApplyOnlyToNewSimulationAssembly': True,
        'sourceHashes': source_hashes,
        'originalPointsByPart': {key: points for key, points in zip(keys, original)}}
