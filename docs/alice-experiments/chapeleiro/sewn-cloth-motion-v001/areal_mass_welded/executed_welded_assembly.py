"""Stitch only the independent simulation pattern at explicit seam pairs.

Original visual garments and their UVs are never edited. A logical-to-solver
mapping reconstructs every original carrier vertex for the existing receivers.
"""
from collections import defaultdict
import bpy
import numpy as np
from chapeleiro_sewn_cloth_assembly import assemble_sewn_petticoats

def assemble_welded_petticoats(scene, rig, schema, include_ivory=True):
    cage, parts, report = assemble_sewn_petticoats(scene, rig, schema, include_ivory, seam_clearance=0.)
    old = cage.data
    points = np.asarray([tuple(v.co) for v in old.vertices], np.float32)
    edges = np.asarray([tuple(e.vertices) for e in old.edges], np.int32)
    loose = np.asarray([e.is_loose for e in old.edges], bool)
    seam_pairs = edges[loose]
    assert len(seam_pairs) == 576
    representative = np.arange(len(points), dtype=np.int32)
    for support, root in seam_pairs: representative[root] = support
    unique, mapping = np.unique(representative, return_inverse=True)
    mapping = mapping.astype(np.int32)
    assert len(unique) == len(points) - 576
    assert np.array_equal(mapping[seam_pairs[:, 0]], mapping[seam_pairs[:, 1]])
    assert np.abs(points[seam_pairs[:, 0]] - points[seam_pairs[:, 1]]).max() < 1e-6
    faces = [tuple(int(mapping[i]) for i in p.vertices) for p in old.polygons]
    assert all(len(set(face)) == len(face) == 4 for face in faces)
    groups = defaultdict(list)
    group_names = [g.name for g in cage.vertex_groups]
    for new, original in enumerate(unique):
        for weight in old.vertices[int(original)].groups:
            groups[(weight.group, weight.weight)].append(new)
    mesh = bpy.data.meshes.new('Actual stitched petticoats / independent simulation only')
    mesh.from_pydata(points[unique].tolist(), [], faces)
    mesh.update()
    cage.data = mesh
    cage.name = mesh.name
    cage.vertex_groups.clear()
    for name in group_names: cage.vertex_groups.new(name=name)
    for (index, value), ids in groups.items(): cage.vertex_groups[index].add(ids, value, 'REPLACE')
    assert len(mesh.polygons) == len(old.polygons) and not any(e.is_loose for e in mesh.edges)
    report.update({'actualSewingEdges': 0, 'actualWeldedSeamPairs': len(seam_pairs),
                   'actualVertices': len(mesh.vertices), 'actualLooseEdges': 0,
                   'logicalCarrierVertices': len(points), 'weldingChangesOnlyNewSimulationMesh': True,
                   'weldedSeamsReplaceFlouncePinConstraints': True,
                   'sewingReplacesFlouncePinConstraints': False,
                   'measurementEdges': edges, 'measurementLooseEdges': loose,
                   'logicalVertexToSimulationVertex': mapping})
    return cage, parts, report
