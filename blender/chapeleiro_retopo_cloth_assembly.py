"""Retopologize only independent simulation carriers; retain visual rest detail.

Dense original garment coordinates remain the reference for a tangent-frame
detail transfer. This does not decimate or cut the visible dressed character.
"""
from collections import defaultdict
import hashlib, json
import bpy
import numpy as np
from mathutils import Vector
from chapeleiro_sewn_cloth_assembly import _world_points, _raw_hash, _values
from chapeleiro_shared_rig_fields import GarmentFields, WEIGHT_QUANTIZATION

def _basis(corners, u, v):
    a, b, c, d = [corners[:, i] for i in range(4)]
    tu = (b - a) * (1 - v[:, None]) + (c - d) * v[:, None]
    tv = (d - a) * (1 - u[:, None]) + (c - b) * u[:, None]
    tu /= np.maximum(np.linalg.norm(tu, axis=1, keepdims=True), 1e-12)
    tv -= tu * np.sum(tu * tv, axis=1, keepdims=True)
    tv /= np.maximum(np.linalg.norm(tv, axis=1, keepdims=True), 1e-12)
    normal = np.cross(tu, tv)
    return np.stack([tu, tv, normal], axis=1)

class RestDetailTransfer:
    def __init__(self, indices, weights, u, v, rest, original):
        self.indices, self.weights, self.u, self.v = indices, weights, u, v
        corners = rest[indices]
        surface = np.sum(corners * weights[:, :, None], axis=1)
        basis = _basis(corners, u, v)
        self.offsets = np.sum((original - surface)[:, None, :] * basis, axis=2)
        self.rest_reconstruction_error = float(np.abs(self.apply(rest) - original).max())
        assert self.rest_reconstruction_error < 1e-6

    def apply(self, physical):
        corners = physical[self.indices]
        surface = np.sum(corners * self.weights[:, :, None], axis=1)
        basis = _basis(corners, self.u, self.v)
        return (surface + np.sum(basis * self.offsets[:, :, None], axis=1)).astype(np.float32)

    def arrays(self):
        return {'detail_corner_indices': self.indices, 'detail_weights': self.weights,
                'detail_u': self.u, 'detail_v': self.v, 'detail_frame_offsets': self.offsets}

class SmoothRestDetailTransfer(RestDetailTransfer):
    """Interpolate shared vertex tangents instead of discontinuous cell frames."""
    def __init__(self, indices, weights, u, v, rest, original, grid_mapping, grid_shapes, frame_corners):
        self.indices, self.weights, self.u, self.v = indices, weights, u, v
        self.grid_mapping, self.grid_shapes, self.frame_corners = grid_mapping, grid_shapes, frame_corners
        surface = np.sum(rest[indices] * weights[:, :, None], axis=1)
        basis = self._frames(rest)
        self.offsets = np.sum((original - surface)[:, None, :] * basis, axis=2)
        self.rest_reconstruction_error = float(np.abs(self.apply(rest) - original).max())
        assert self.rest_reconstruction_error < 1e-6

    def _frames(self, physical):
        tangents_u, tangents_v = [], []
        start = 0
        for rows, around in self.grid_shapes:
            count = rows * around
            grid = physical[self.grid_mapping[start:start + count]].reshape(rows, around, 3)
            tangents_u.append(((np.roll(grid, -1, axis=1) - np.roll(grid, 1, axis=1)) * .5).reshape(-1, 3))
            tangents_v.append(np.gradient(grid, axis=0).reshape(-1, 3))
            start += count
        tu = np.sum(np.concatenate(tangents_u)[self.frame_corners] * self.weights[:, :, None], axis=1)
        tv = np.sum(np.concatenate(tangents_v)[self.frame_corners] * self.weights[:, :, None], axis=1)
        tu /= np.maximum(np.linalg.norm(tu, axis=1, keepdims=True), 1e-12)
        tv -= tu * np.sum(tu * tv, axis=1, keepdims=True)
        tv /= np.maximum(np.linalg.norm(tv, axis=1, keepdims=True), 1e-12)
        return np.stack([tu, tv, np.cross(tu, tv)], axis=1)

    def apply(self, physical):
        surface = np.sum(physical[self.indices] * self.weights[:, :, None], axis=1)
        return (surface + np.sum(self._frames(physical) * self.offsets[:, :, None], axis=1)).astype(np.float32)

    def arrays(self):
        return {**super().arrays(), 'frame_grid_to_simulation_vertex': self.grid_mapping,
                'frame_grid_shapes': np.asarray(self.grid_shapes, np.int32),
                'detail_frame_corner_indices': self.frame_corners}

def assemble_retopo_petticoats(scene, rig, schema, around=96, lowpass=10, tier_rows=5, smooth_detail=False, outward_winding=True):
    assert 192 % around == 0 and 0 < lowpass < around // 2 and tier_rows >= 3
    keys = ['ivory', 'support', 'tier1', 'tier2', 'tier3']
    names = ['01 / long ivory gathered petticoat', '01 / black petticoat continuous waist support'] + ['01 / black gathered flounce ' + str(i) for i in range(1, 4)]
    sources = [bpy.data.objects['01 / long ivory gathered petticoat / petticoat simulation midsurface']] + [bpy.data.objects['Authoring / ' + n] for n in names[1:]]
    original = [_world_points(o) for o in sources]
    hashes = {o.name: _raw_hash(o) for o in sources}
    source_rows = [36, 38, 12, 12, 12]
    assert all(len(points) == (rows + 1) * 192 for points, rows in zip(original, source_rows))
    # Broad cloth shape is simulated. The original narrow gathers are retained
    # in the rotating detail offsets instead of becoming tiny collision cells.
    grids = []
    for points, rows in zip(original, source_rows):
        raw = points.reshape(rows + 1, 192, 3)
        frequency = np.fft.rfft(raw, axis=1)
        frequency[:, lowpass + 1:] = 0
        smooth = np.fft.irfft(frequency, n=192, axis=1)
        grids.append(smooth[:, ::192 // around].astype(np.float32))
    parameters = [np.arange(37, dtype=np.float64), np.arange(39, dtype=np.float64)]
    seam_rings = []
    support = grids[1]
    for i in range(2, 5):
        root_height = original[i].reshape(13, 192, 3)[0, :, 2].mean()
        ring = int(np.argmin(np.abs(support[:, :, 2].mean(1) - root_height)))
        seam_rings.append(ring)
        t = np.linspace(0, 1, 13)
        fade = 1 - t * t * (3 - 2 * t)
        grid = grids[i] + (support[ring] - grids[i][0])[None, :, :] * fade[:, None, None]
        # Redistribute along each actual meridian, including the seam-adjusted
        # root, so short compressed cells do not remain in the solver pattern.
        sampled = np.empty((tier_rows + 1, around, 3), np.float32)
        for col in range(around):
            distance = np.r_[0., np.cumsum(np.linalg.norm(np.diff(grid[:, col], axis=0), axis=1))]
            assert distance[-1] > 0
            wanted = np.linspace(0, distance[-1], tier_rows + 1)
            for axis in range(3): sampled[:, col, axis] = np.interp(wanted, distance, grid[:, col, axis])
        sampled[0] = support[ring]
        grids[i] = sampled
        parameters.append(np.linspace(0, 12, tier_rows + 1))
    offsets = np.cumsum([0] + [g.shape[0] * around for g in grids[:-1]]).astype(np.int32)
    unmerged = np.concatenate([g.reshape(-1, 3) for g in grids])
    seam_pairs = []
    for i, ring in enumerate(seam_rings, 2):
        seam_pairs.extend([(int(offsets[1] + ring * around + c), int(offsets[i] + c)) for c in range(around)])
    seam_pairs = np.asarray(seam_pairs, np.int32)
    representative = np.arange(len(unmerged), dtype=np.int32)
    representative[seam_pairs[:, 1]] = seam_pairs[:, 0]
    unique, mapping = np.unique(representative, return_inverse=True)
    mapping = mapping.astype(np.int32)
    vertices = unmerged[unique]
    faces, parts, ownership = [], [], []
    logical_start, seen = 0, set()
    corner_indices, frame_corners, detail_weights, detail_u, detail_v = [], [], [], [], []
    original_edges = []
    for i, (key, source, points, grid, rows) in enumerate(zip(keys, sources, original, grids, source_rows)):
        count = 0
        for row in range(grid.shape[0] - 1):
            for col in range(around):
                q = [offsets[i] + row * around + col, offsets[i] + row * around + (col + 1) % around,
                     offsets[i] + (row + 1) * around + (col + 1) % around, offsets[i] + (row + 1) * around + col]
                order = [q[0], q[3], q[2], q[1]] if outward_winding else q
                faces.append(tuple(int(mapping[j]) for j in order))
                count += 1
        physical_ids = mapping[offsets[i]:offsets[i] + grid.shape[0] * around]
        owned = sorted(set(physical_ids.tolist()) - seen)
        seen.update(owned)
        ownership.append(np.asarray(owned, np.int32))
        uv_rows = parameters[i]
        for row in range(rows + 1):
            lower = min(int(np.searchsorted(uv_rows, row, side='right') - 1), len(uv_rows) - 2)
            v = float((row - uv_rows[lower]) / (uv_rows[lower + 1] - uv_rows[lower]))
            for col in range(192):
                position = col * around / 192
                left, u = int(position), position % 1
                q = [offsets[i] + lower * around + left, offsets[i] + lower * around + (left + 1) % around,
                     offsets[i] + (lower + 1) * around + (left + 1) % around, offsets[i] + (lower + 1) * around + left]
                corner_indices.append(mapping[q])
                frame_corners.append(q)
                detail_weights.append([(1-u)*(1-v), u*(1-v), u*v, (1-u)*v])
                detail_u.append(u)
                detail_v.append(v)
        original_edges.extend([(logical_start + int(e.vertices[0]), logical_start + int(e.vertices[1])) for e in source.data.edges])
        parts.append({'key': key, 'source': source.name, 'visibleGarment': names[i],
                      'family': 'IvoryCloth' if i == 0 else 'BlackCloth',
                      'start': logical_start, 'vertices': len(points), 'faces': count,
                      'originalSourceFaces': len(source.data.polygons), 'simulationRows': grid.shape[0], 'simulationAround': around,
                      'sourceRawGeometrySha256': hashes[source.name],
                      'originalWorldPointsSha256': hashlib.sha256(points.tobytes()).hexdigest(),
                      'actualOwnedSolverVertices': len(owned), 'uniformSeamSupportRing': seam_rings[i-2] if i >= 2 else None})
        logical_start += len(points)
    mesh = bpy.data.meshes.new('Regular simulation quads / detail preserved on original receivers')
    mesh.from_pydata(vertices.tolist(), [], faces)
    mesh.update()
    centers = np.asarray([tuple(p.center) for p in mesh.polygons], np.float32)
    normals = np.asarray([tuple(p.normal) for p in mesh.polygons], np.float32)
    radial_sign = np.sum(centers[:, :2] * normals[:, :2], axis=1)
    outward_fraction = float(np.mean(radial_sign > 0))
    assert outward_fraction == float(outward_winding)
    cage = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(cage)
    assert not any(e.is_loose for e in mesh.edges)
    for name in ['pinned', 'stiffness', 'shrinking', 'pressure']:
        group = cage.vertex_groups.new(name=name)
        values = []
        for i, source in enumerate(sources):
            dense = _values(source, name).reshape(source_rows[i] + 1, 192)
            sampled = np.stack([np.interp(parameters[i], np.arange(source_rows[i] + 1), dense[:, c]) for c in range(0, 192, 192 // around)], axis=1).ravel()
            if name == 'pinned' and i >= 2: sampled[:] = 0
            values.extend(sampled)
        values = np.asarray(values, np.float32)[unique]
        for value in np.unique(values):
            if value > 0: group.add(np.flatnonzero(values == value).tolist(), float(value), 'REPLACE')
    fields = GarmentFields(rig, schema['clothFamilies'])
    batches = defaultdict(list)
    for physical, unmerged_id in enumerate(unique):
        family = 'IvoryCloth' if unmerged_id < offsets[1] else 'BlackCloth'
        weights = fields.cloth(Vector(vertices[physical]), family)
        quantized = {n: round(w * WEIGHT_QUANTIZATION) for n, w in weights.items()}
        quantized[max(weights, key=weights.get)] += WEIGHT_QUANTIZATION - sum(quantized.values())
        for name, value in quantized.items():
            if value > 0: batches[(name, value)].append(physical)
    groups = {n: cage.vertex_groups.new(name=n) for n in sorted({n for n, w in batches})}
    for (name, value), ids in batches.items(): groups[name].add(ids, value / WEIGHT_QUANTIZATION, 'REPLACE')
    group_ids = {g.index for g in groups.values()}
    assert all(abs(sum(w.weight for w in v.groups if w.group in group_ids) - 1) < 1e-7 for v in mesh.vertices)
    assert all(sum(w.group in group_ids for w in v.groups) <= 4 for v in mesh.vertices)
    arm = cage.modifiers.new('Existing shared rig / before retopologized Cloth', 'ARMATURE')
    arm.object = rig
    transfer_args = [np.asarray(corner_indices, np.int32), np.asarray(detail_weights, np.float32),
                     np.asarray(detail_u, np.float32), np.asarray(detail_v, np.float32), vertices, np.concatenate(original)]
    transfer = (SmoothRestDetailTransfer(*transfer_args, mapping, [g.shape[:2] for g in grids], np.asarray(frame_corners, np.int32))
                if smooth_detail else RestDetailTransfer(*transfer_args))
    assert {o.name: _raw_hash(o) for o in sources} == hashes
    return cage, parts, {'includedIvory': True, 'actualVertices': len(vertices), 'actualFaces': len(faces),
                         'actualLooseEdges': 0, 'actualWeldedSeamPairs': len(seam_pairs),
                         'actualSeamSupportRings': seam_rings, 'seamsUseOneContinuousSupportRingEach': True,
                         'logicalCarrierVertices': logical_start, 'angularLowpass': lowpass,
                         'visualSourceGeometryUnchanged': True, 'thicknessAndUvRemainOnOriginalReceivers': True,
                         'originalRestDetailReconstructionMaximumError': transfer.rest_reconstruction_error,
                         'detailTransferIsApproximationNotApproval': True,
                         'detailUsesInterpolatedVertexTangents': smooth_detail,
                         'outwardWinding': outward_winding,
                         'actualRadialOutwardFacesFraction': outward_fraction,
                         'windingChangeAppliesOnlyToIndependentSimulationMesh': True,
                         'sourceHashes': hashes, 'detailTransfer': transfer,
                         'originalPointsByPart': {k: p for k, p in zip(keys, original)},
                         'partSolverOwnership': ownership,
                         'physicalSeamPairs': mapping[seam_pairs],
                         'measurementEdges': np.asarray(original_edges, np.int32)}
