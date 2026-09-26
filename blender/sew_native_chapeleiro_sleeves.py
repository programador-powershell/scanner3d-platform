"""Keep native Tripo sleeve triangles and reconstruct only the missing inner seam."""
import argparse
import hashlib
import heapq
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--scan-generation', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
read = lambda file: json.loads(Path(file).read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
record, scan = read(args.generation), read(args.scan_generation)
studio = '32254621-cdf9-43bd-8297-54446796d892'
if any(r.get('studioModelId') != studio or r.get('reusedGeometry') is not False for r in [record, scan]):
    raise ValueError('Only the authorized new Tripo Chapeleiro and its own refinement are permitted.')
if record['sourcePhotoSha256'] != '3a7fb91e7a0724f3d631f1a5c56d7e77119af016d1b152a14696d4fff260b7bc':
    raise ValueError('Wrong layer photograph.')
for data in [record, scan]:
    for key in ['model', 'editableBlend', 'sourcePhoto']:
        if sha(data[key]) != data[key + 'Sha256']:
            raise ValueError('Changed source geometry or original photograph.')
out = Path(args.output)
if out.exists():
    raise ValueError('Use a new checkpoint directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=scan['editableBlend'])
source = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
positions = np.empty(len(source.data.vertices) * 3, dtype=np.float32)
source.data.vertices.foreach_get('co', positions)
positions = positions.reshape(-1, 3)
world = np.asarray(source.matrix_world)
positions = positions @ world[:3, :3].T + world[:3, 3]
indices = np.empty(len(source.data.loops), dtype=np.int32)
source.data.loops.foreach_get('vertex_index', indices)
triangles = indices.reshape(-1, 3)
x, y, z = positions[triangles].mean(axis=1).T
parts = {}
for sign in [-1, 1]:
    selected = triangles[(x * sign > .071) & (x * sign < .143) & (z > .728) & (z < .808) & (abs(y) < .068)]
    used, remap = np.unique(selected, return_inverse=True)
    parts[sign] = (positions[used].tolist(), remap.reshape(-1, 3).tolist())
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
body = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('Corpete /'))
cloth = bpy.data.materials['Tecido verde / foto original da camada 2']
lining = bpy.data.materials['Forro verde escuro / superfície interna inferida']
photo = next(n.image for n in cloth.node_tree.nodes if n.type == 'TEX_IMAGE')

def boundary_groups(bm):
    remaining = {e for e in bm.edges if e.is_boundary}
    result = []
    while remaining:
        seed = remaining.pop()
        edges, todo = {seed}, [seed]
        while todo:
            for vertex in todo.pop().verts:
                for edge in vertex.link_edges:
                    if edge in remaining:
                        remaining.remove(edge)
                        edges.add(edge)
                        todo.append(edge)
        result.append((edges, {v for e in edges for v in e.verts}))
    return result

bm = bmesh.new()
bm.from_mesh(body.data)
roots = {}
for edges, vertices in boundary_groups(bm):
    if len(vertices) != 66:
        continue
    points = [v.co.copy() for v in vertices]
    sign = 1 if sum(p.x for p in points) > 0 else -1
    center = sum(points, Vector()) / len(points)
    roots[sign] = sorted(points, key=lambda p: math.atan2(p.y - center.y, p.z - center.z) % math.tau)
bm.free()

def mesh_object(name, coordinates, faces, materials):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(coordinates, [], faces)
    mesh.update()
    for material in materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj

def distances(vertices, edges, seeds):
    graph = [[] for v in vertices]
    for edge in edges:
        a, b = edge.vertices
        length = (vertices[a].co - vertices[b].co).length
        graph[a].append((b, length))
        graph[b].append((a, length))
    result = [math.inf] * len(vertices)
    queue = []
    for index in seeds:
        result[index] = 0
        heapq.heappush(queue, (0, index))
    while queue:
        value, index = heapq.heappop(queue)
        if value != result[index]:
            continue
        for other, length in graph[index]:
            candidate = value + length
            if candidate < result[other]:
                result[other] = candidate
                heapq.heappush(queue, (candidate, other))
    return np.asarray(result)

audit = []
for sign in [1, -1]:
    label = 'L' if sign > 0 else 'R'
    old = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('rig_role') == 'sleeve_' + label)
    cuff = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('rig_role') == 'cuff_' + label
                and o.name.startswith('Punho ' + label + ' / tecido'))
    cuff_points = [v.co.copy() for v in list(cuff.data.vertices)[:192]]
    root_material = bpy.data.materials.new('TEMP sewn root cap ' + label)
    cuff_material = bpy.data.materials.new('TEMP cuff cap ' + label)
    native = mesh_object('Native sleeve ' + label, *parts[sign], [cloth, cuff_material])
    bm = bmesh.new()
    bm.from_mesh(native.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.000002)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                          dist=1e-7, plane_co=(sign * .078, 0, 0),
                          plane_no=(sign, 0, 0), clear_inner=True)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                          dist=1e-7, plane_co=(0, 0, .731), plane_no=(0, 0, 1), clear_inner=True)
    caps = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)['faces']
    for face in caps:
        face.material_index = 1
    # A non-planar scan cut can produce two opposite, coincident cap triangles.
    # Cancel those zero-volume pairs, keeping the adjacent native surface.
    coincident = {}
    for face in bm.faces:
        coincident.setdefault(frozenset(face.verts), []).append(face)
    duplicate_pairs = [f for faces in coincident.values() if len(faces) == 2 for f in faces]
    bmesh.ops.delete(bm, geom=duplicate_pairs, context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    remaining_caps = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)['faces']
    bmesh.ops.triangulate(bm, faces=list(remaining_caps))
    for vertex in bm.verts:
        # Reshape the shoulder envelope against sheet 2, without introducing
        # another cut or erasing dark printed motifs from the native cloth.
        if vertex.co.z > .791:
            excess = vertex.co.z - .791
            vertex.co.z = .791 + .010 * excess / (.010 + excess)
        t = max(0, min(1, (.744 - vertex.co.z) / .013))
        t = t * t * (3 - 2 * t)
        if not t:
            continue
        angle = math.atan2((vertex.co.y - .019) / .043, (vertex.co.x - sign * .104) / .024)
        target_x = sign * .104 + .024 * math.cos(angle)
        target_y = .019 + .031 * math.sin(angle)
        vertex.co.x += (target_x - vertex.co.x) * t
        vertex.co.y += (target_y - vertex.co.y) * t
        vertex.co.z += .10050251256 * sign * (target_x - sign * .104) * t
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if any(len(e.link_faces) != 2 for e in bm.edges):
        counts = {str(n): sum(len(e.link_faces) == n for e in bm.edges) for n in range(5)}
        (out / 'failed_native_volume.json').write_text(json.dumps({'sleeve': label, 'edgeFaceCounts': counts}))
        bm.to_mesh(native.data)
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'failed_native_volume.blend'))
        raise ValueError('Recovered native sleeve is not a closed volume before sewing.')
    bm.to_mesh(native.data)
    bm.free()
    root = roots[sign]
    center = sum(root, Vector()) / len(root)
    count, rows = len(root), 18
    coordinates, faces = [], []
    for row in range(rows + 1):
        t = row / rows
        for point in root:
            phi = math.atan2((point.y - center.y) / .0165, (point.z - center.z) / .030)
            endpoint = Vector((sign * .097, .019 + .021 * math.sin(phi), .764 + .016 * math.cos(phi)))
            coordinates.append(point.lerp(endpoint, t))
    for row in range(rows):
        for col in range(count):
            next_col = (col + 1) % count
            faces.append((row * count + col, row * count + next_col,
                          (row + 1) * count + next_col, (row + 1) * count + col))
    faces.append(tuple(range(count - 1, -1, -1)))
    faces.append(tuple(rows * count + col for col in range(count)))
    bridge = mesh_object('Inner sewn sleeve bridge ' + label, coordinates, faces, [cloth, root_material])
    bridge.data.polygons[len(faces) - 2].material_index = 1
    bm = bmesh.new()
    bm.from_mesh(bridge.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(bridge.data)
    bm.free()
    modifier = native.modifiers.new('Only missing inner seam / exact union', 'BOOLEAN')
    modifier.operation, modifier.solver = 'UNION', 'EXACT'
    modifier.object = bridge
    modifier.material_mode = 'TRANSFER'
    bpy.context.view_layer.objects.active = native
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(bridge, do_unlink=True)
    root_index = list(native.data.materials).index(root_material)
    cuff_index = list(native.data.materials).index(cuff_material)
    bm = bmesh.new()
    bm.from_mesh(native.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in {root_index, cuff_index}], context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    loops = boundary_groups(bm)
    if len(loops) != 2 or any(sum(e in edges for e in v.link_edges) != 2 for edges, vs in loops for v in vs):
        raise ValueError('The sewn sleeve requires separate, continuous root and cuff openings.')
    cuff_loop = min(loops, key=lambda pair: sum(abs(v.co.z - .731) for v in pair[1]) / len(pair[1]))
    for vertex in cuff_loop[1]:
        vertex.co += Vector((-sign * .10, 0, .995)).normalized() * .001
    # Walk the actual boundary edges: sorting folded scan vertices by angle
    # changes adjacency and tears the sewing strip.
    cuff_edges, cuff_vertices = cuff_loop
    phase = lambda v: math.atan2((v.co.y - .019) / .031, (v.co.x - sign * .104) / .024)
    start = min(cuff_vertices, key=lambda v: abs(phase(v)))
    ordered, previous, current = [], None, start
    while True:
        ordered.append(current)
        neighbors = [e.other_vert(current) for e in current.link_edges if e in cuff_edges]
        next_vertex = next(v for v in neighbors if v is not previous)
        previous, current = current, next_vertex
        if current is start:
            break
        if len(ordered) > len(cuff_vertices):
            raise ValueError('Invalid native cuff boundary walk.')
    if sum(a.co.x * b.co.y - b.co.x * a.co.y for a, b in
           zip(ordered, ordered[1:] + ordered[:1])) < 0:
        ordered = ordered[:1] + ordered[:0:-1]
    new_ring = [bm.verts.new(point) for point in cuff_points]
    # Join unequal sampled circles with a short triangulated seam hidden under
    # the ribbon. The endpoint itself is the actual original cuff ring.
    lengths = [(a.co - b.co).length for a, b in zip(ordered, ordered[1:] + ordered[:1])]
    circumference = sum(lengths)
    old_angles, cumulative = [], 0
    for length in lengths:
        old_angles.append(math.tau * cumulative / circumference)
        cumulative += length
    new_order = sorted(new_ring, key=lambda v: math.atan2((v.co.y - .019) / .031,
                                                         (v.co.x - sign * .104) / .024) % math.tau)
    new_angles = [math.atan2((v.co.y - .019) / .031, (v.co.x - sign * .104) / .024) % math.tau for v in new_order]
    i = j = 0
    while i < len(ordered) or j < len(new_order):
        a, b = ordered[i % len(ordered)], new_order[j % len(new_order)]
        ai = old_angles[i + 1] if i + 1 < len(ordered) else math.tau
        bj = new_angles[j + 1] if j + 1 < len(new_order) else math.tau
        if i < len(ordered) and (j >= len(new_order) or ai < bj):
            bm.faces.new((a, ordered[(i + 1) % len(ordered)], b))
            i += 1
        else:
            bm.faces.new((a, new_order[(j + 1) % len(new_order)], b))
            j += 1
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context='EDGES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    openings = boundary_groups(bm)
    if (len(openings) != 2 or sorted(len(vs) for _, vs in openings) != [66, 192]
            or any(len(e.link_faces) != 2 and not e.is_boundary for e in bm.edges)):
        failure = {'sleeve': label, 'openings': [len(vs) for _, vs in openings],
                   'edgeFaceCounts': {str(n): sum(len(e.link_faces) == n for e in bm.edges) for n in range(5)}}
        (out / 'failed_seam_topology.json').write_text(json.dumps(failure), encoding='utf-8')
        bm.to_mesh(native.data)
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'failed_seam_topology.blend'))
        raise ValueError('Sewing must preserve one manifold sleeve with the exact root and cuff rings.')
    bm.to_mesh(native.data)
    bm.free()
    native.data.materials.clear()
    native.data.materials.append(cloth)
    native.data.materials.append(lining)
    for polygon in native.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True
    from mathutils.kdtree import KDTree
    tree = KDTree(len(native.data.vertices))
    for vertex in native.data.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    root_ids = [tree.find(p)[1] for p in root]
    cuff_ids = [tree.find(p)[1] for p in cuff_points]
    if max(tree.find(p)[2] for p in root + cuff_points) > .000002:
        raise ValueError('Boolean sewing changed a required endpoint.')
    root_distance = distances(native.data.vertices, native.data.edges, root_ids)
    cuff_distance = distances(native.data.vertices, native.data.edges, cuff_ids)
    field = root_distance / np.maximum(root_distance + cuff_distance, .0000001)
    if not np.isfinite(field).all():
        raise ValueError('Disconnected native sleeve surface.')
    edges = np.array([list(e.vertices) for e in native.data.edges], dtype=np.int32)
    co = np.array([list(v.co) for v in native.data.vertices])
    weights = 1 / np.maximum(np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1), 1e-7)
    nodes = np.concatenate([edges[:, 0], edges[:, 1]])
    degrees = np.bincount(nodes, weights=np.tile(weights, 2), minlength=len(field))
    fixed = np.zeros(len(field), dtype=bool)
    fixed[root_ids], fixed[cuff_ids] = True, True
    free = np.flatnonzero(~fixed)
    prescribed = np.zeros(len(field))
    prescribed[cuff_ids] = 1

    def neighbor_sum(values):
        products = np.concatenate([values[edges[:, 1]] * weights, values[edges[:, 0]] * weights])
        return np.bincount(nodes, weights=products, minlength=len(field))

    def multiply(values):
        full = np.zeros(len(field))
        full[free] = values
        return (degrees * full - neighbor_sum(full))[free]

    # Solve the Dirichlet surface Laplacian instead of stopping a slow Jacobi
    # relaxation while small native scan edges still have abrupt weight jumps.
    solution = field[free].copy()
    rhs = neighbor_sum(prescribed)[free]
    residual = rhs - multiply(solution)
    conditioned = residual / degrees[free]
    search = conditioned.copy()
    product = float(residual @ conditioned)
    scale = max(float(np.linalg.norm(rhs)), 1)
    delta = float(np.linalg.norm(residual)) / scale
    for iteration in range(5000):
        if delta < 1e-9:
            break
        applied = multiply(search)
        denominator = float(search @ applied)
        if not denominator > 0:
            raise ValueError('The native cloth Laplacian is not positive definite.')
        alpha = product / denominator
        solution += alpha * search
        residual -= alpha * applied
        delta = float(np.linalg.norm(residual)) / scale
        conditioned = residual / degrees[free]
        next_product = float(residual @ conditioned)
        search = conditioned + (next_product / product) * search
        product = next_product
    if delta >= 1e-8:
        raise ValueError('The actual surface weights did not converge.')
    field = prescribed
    field[free] = np.clip(solution, 0, 1)
    attribute = native.data.attributes.new('sleeve_seam_parameter', 'FLOAT', 'POINT')
    attribute.data.foreach_set('value', field.astype(np.float32))
    uv = native.data.uv_layers.new(name='Original own layer-2 cloth photograph')
    for loop in native.data.loops:
        point = native.data.vertices[loop.vertex_index].co
        px = (416 if sign > 0 else 152) + (point.x - sign * .104) * 3300
        py = 1285 - (point.z - .690) * 3100
        uv.data[loop.index].uv = (px / photo.size[0], 1 - py / photo.size[1])
    native.name = 'Manga ' + label + ' / dobras nativas e costura interna'
    native['rig_role'], native['rig_pending'] = 'sleeve_' + label, True
    native['alice_stage'] = 'alice_chapeleiro_stage_02'
    bpy.data.objects.remove(old, do_unlink=True)
    modifier = native.modifiers.new('Continuous sleeve lining', 'SOLIDIFY')
    modifier.thickness, modifier.offset = .0005, -1
    modifier.use_even_offset, modifier.use_quality_normals = False, True
    modifier.material_offset = modifier.material_offset_rim = 1
    audit.append({'sleeve': label, 'nativeScanTrianglesInput': len(parts[sign][1]),
                  'cancelledCoincidentCapFaces': len(duplicate_pairs),
                  'additionalScanCutCaps': len(remaining_caps),
                  'upperShoulderEnvelopeRefined': True,
                  'upperShoulderAsymptoteMetres': .801,
                  'sewnRootVertices': len(root), 'rootRestPoints': [list(p) for p in root],
                  'cuffRestPoints': [list(p) for p in cuff_points], 'separateRootAndCuffOpenings': True,
                  'harmonicIterations': iteration + 1, 'lastFieldDelta': delta,
                  'weightSolver': 'diagonal_preconditioned_conjugate_gradient',
                  'relativeLinearResidual': delta,
                  'hiddenInnerClothInferred': True, 'fidelityVerified': False})
    print('NATIVE_SLEEVE_SEWN', label, len(native.data.vertices), flush=True)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
stats = []
dg = bpy.context.evaluated_depsgraph_get()
for obj in meshes:
    evaluated = obj.evaluated_get(dg)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    stats.append({'component': obj.name, 'rigRole': obj['rig_role'], 'vertices': len(mesh.vertices),
                  'triangles': len(mesh.loop_triangles), 'rigged': False, 'fidelityVerified': False})
    evaluated.to_mesh_clear()
blend = out / 'chapeleiro_native_sleeves_sewn.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_animations=False)
record.update(model=str(model.resolve()), modelSha256=sha(model), editableBlend=str(blend.resolve()),
              editableBlendSha256=sha(blend), geometryParentSha256=record['modelSha256'],
              method='own_layer_2_native_scan_sleeves_sewn_to_real_cavas', sleeveWeightField='harmonic_actual_surface',
              sleeveConstructionAudit=audit, sleeveScriptSha256=sha(__file__), componentAudit=stats,
              originalFullScanSha256=scan['modelSha256'], rigPresent=False,
              vertices=sum(s['vertices'] for s in stats), triangles=sum(s['triangles'] for s in stats),
              status='generated_awaiting_visual_review', fidelityVerified=False, motionVerified=False,
              clothCollisionVerified=False, countsAsFinishedLayer=False, additionalCreditsConsumed=0,
              localWorkStatus='native_fold_sewing_and_harmonic_weights_pending_visual_and_motion_review',
              limitations=['Missing inner cloth is inferred; native exterior triangles come from the same new scan.',
                           'The sewn silhouette, UV projection and deformation still need actual review.',
                           'All clothing layers, body/cloth collision and Soulslike gameplay remain pending.'])
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('NATIVE_SLEEVE_CHECKPOINT_SAVED', out, flush=True)
