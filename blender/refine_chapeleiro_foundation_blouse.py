"""Append the photo-1 gathered blouse to the preserved whole/foundation master.

The sleeve roots are lofted from the actual open armhole boundaries. Existing
fabric and the complete exterior are retained byte-for-byte at the cage level.
This is an incremental modeling checkpoint, not rig or gameplay validation.
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent = json.loads(Path(args.parent).read_text(encoding='utf-8'))
for field in ['model', 'editableBlend', 'sourcePhoto']:
    if sha(parent[field]) != parent[field + 'Sha256']:
        raise ValueError('Changed parent evidence: ' + field)
if parent['sourcePhotoSha256'] != 'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('The blouse must be compared with its own foundation photo.')
out = Path(args.output)
if out.exists():
    raise ValueError('Choose a new checkpoint directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene = bpy.context.scene
scene.frame_set(1)


def cage_hash(obj):
    data = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', data)
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    return hashlib.sha256(data.tobytes() + json.dumps(faces).encode()).hexdigest()


existing = {o.name: cage_hash(o) for o in scene.objects if o.type == 'MESH'}
inherited = [o for o in scene.objects if o.type == 'MESH' and o.get('constructedNewInternalLayer')]
temporarily_disabled = []
for obj in inherited:
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            temporarily_disabled.append(modifier)
            modifier.show_viewport = False
corset = bpy.data.objects['01 / ivory fitted boned corset / pointed front']
post = bpy.data.node_groups[parent['proceduralNodeAsset']]
import BystedtsClothBuilder as BCB
from BystedtsClothBuilder import simulation
if not hasattr(bpy.types.Scene, 'BCB_props'):
    BCB.register()
scene.BCB_props.use_triangulate = False
scene.BCB_props.simulation_frames = 24
scene.BCB_props.sim_quality = 12
scene.BCB_props.collision_quality = 5
scene.BCB_props.collision_distance = .00065
ivory = bpy.data.materials['Foundation / warm ivory cotton'].copy()
ivory.name = 'Photo 1 / ivory blouse batiste'
ivory.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .74
for node in ivory.node_tree.nodes:
    if node.type == 'NORMAL_MAP':
        node.inputs['Strength'].default_value = .065
brass = bpy.data.materials['Foundation / aged brass eyelets and busk']
new, seam_audits, physics_carriers = [], [], {}


def mesh_object(name, vertices, faces, role, material=ivory):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj['constructedNewInternalLayer'] = True
    obj['originalLayerPhotoSha256'] = parent['sourcePhotoSha256']
    obj['role'] = role
    new.append(obj)
    return obj


def parent_to(obj, carrier):
    transform = obj.matrix_world.copy()
    obj.parent = carrier
    obj.matrix_parent_inverse = carrier.matrix_world.inverted()
    obj.matrix_world = transform
    obj['actualClothCarrier'] = carrier.name
    obj['attachment'] = 'Actual sewn carrier hierarchy; skin and gameplay verification pending'


def post_modifier(obj, thickness=-.00035):
    if any(m.type == 'CLOTH' for m in obj.modifiers):
        # Surface Deform must bind to the simulation midsurface, before BCB
        # creates thickness/support loops. Keep one solver per fabric piece;
        # the visible receiver and trims follow that same solved surface.
        cage = obj.copy()
        cage.data = obj.data
        cage.name = obj.name + ' / simulation midsurface'
        scene.collection.objects.link(cage)
        cage.hide_render = True
        cage.display_type = 'WIRE'
        cage['constructedNewInternalLayer'] = False
        cage['isBlouseSimulationCage'] = True
        cage['visibleFabric'] = obj.name
        # Gathered quads can become concave after deformation. Triangulate the
        # evaluated binding target, retaining the editable quad/cloth cage.
        triangulate = cage.modifiers.new('Valid evaluated midsurface for deformation bindings', 'TRIANGULATE')
        triangulate.quad_method = 'BEAUTY'
        physics_carriers[obj.name] = cage
        for modifier in list(obj.modifiers):
            if modifier.type in ['CLOTH', 'SURFACE_DEFORM']:
                obj.modifiers.remove(modifier)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        follower = obj.modifiers.new('Visible fabric follows its single simulation midsurface', 'SURFACE_DEFORM')
        follower.target = cage
        bpy.ops.object.surfacedeform_bind(modifier=follower.name)
        if not follower.is_bound:
            raise ValueError('The visible fabric receiver could not bind to its midsurface.')
        obj['simulationCage'] = cage.name
    mod = obj.modifiers.new('Bystedt / blouse thickness and UV', 'NODES')
    mod.node_group = post
    values = {'Separate seams': 0., 'Thickness': thickness, 'Subdiv level': 0,
              'UV unwrap': True, 'UVMap name': 'UVMap', 'Supportive loops offset': 0.}
    for socket in post.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT' and socket.name in values:
            getattr(mod.properties.inputs, socket.identifier).value = values[socket.name]
    temporarily_disabled.append(mod)
    mod.show_viewport = False


def cloth(obj, pins):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    simulation.add_cloth_to_objects(bpy.context, [obj])
    mod = next(m for m in obj.modifiers if m.type == 'CLOTH')
    mod.settings.mass = .08
    mod.settings.tension_stiffness = 35
    mod.settings.compression_stiffness = 35
    mod.settings.shear_stiffness = 12
    mod.settings.bending_stiffness = .45
    mod.settings.shrink_min = mod.settings.shrink_max = 0
    mod.settings.use_dynamic_mesh = True
    mod.collision_settings.use_self_collision = True
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = 24
    group = obj.vertex_groups['pinned']
    group.remove(list(range(len(obj.data.vertices))))
    for weight, indices in pins.items():
        if indices:
            group.add(indices, weight, 'REPLACE')


def surface_follow(obj, carrier, deformation_target=None):
    parent_to(obj, carrier)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new('Sewn blouse attachment follows actual fabric', 'SURFACE_DEFORM')
    target = deformation_target or carrier
    mod.target = physics_carriers.get(target.name, target)
    while list(obj.modifiers).index(mod) > 0:
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    print('BLOUSE_BIND_START', obj.name, mod.target.name, flush=True)
    bpy.ops.object.surfacedeform_bind(modifier=mod.name)
    if not mod.is_bound:
        raise ValueError('Failed fabric attachment: ' + obj.name)
    print('BLOUSE_BIND_OK', obj.name, flush=True)


def sharp_seams(obj, indices):
    sharp = obj.data.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    for edge in obj.data.edges:
        enabled = all(v in indices for v in edge.vertices)
        edge.use_seam = enabled
        sharp.data[edge.index].value = enabled


def sleeve_faces(around, rows):
    return [(r * around + c, r * around + (c + 1) % around,
             (r + 1) * around + (c + 1) % around, (r + 1) * around + c)
            for r in range(rows) for c in range(around)]


around, rows = 160, 44


def torso_position(u, t):
    theta = math.tau * u
    front = max(0., math.cos(theta))
    back = max(0., -math.cos(theta))
    top = .812 - .047 * front ** 2 - .021 * back ** 2
    z = top + (.703 - top) * t
    bust = math.sin(math.pi * t) ** 1.2
    fold_phase = theta * 37 + .35 * math.sin(theta * 3) + .18 * math.sin(theta * 7)
    folds = (.0009 + .0014 * math.sin(math.pi * t)) * math.cos(fold_phase + .3 * t)
    folds += .00035 * math.sin(theta * 73 + 2 * t) * math.sin(math.pi * t)
    rx = .078 + .008 * bust + folds
    ry = .047 + .015 * bust + folds * .75
    # Fit the lower shirt INSIDE the existing, unchanged boned corset.
    corset_top = .732 - .016 * abs(math.sin(theta))
    corset_bottom = .625 - .030 * front ** 4
    ct = max(0., min(1., (corset_top - z) / (corset_top - corset_bottom)))
    bulge = (abs(ct - .56) / (.56 if ct <= .56 else .44)) ** 1.8
    crx, cry = .055 + .023 * bulge - .0012, .039 + .014 * bulge - .0012
    blend = max(0., min(1., (corset_top + .006 - z) / .006))
    rx = rx * (1 - blend) + min(rx, crx) * blend
    ry = ry * (1 - blend) + min(ry, cry) * blend
    return Vector((rx * math.sin(theta), -ry * math.cos(theta), z))


vertices = [torso_position(c / around, r / rows) for r in range(rows + 1) for c in range(around)]
faces = []
for r in range(rows):
    for c in range(around):
        theta = math.tau * (c + .5) / around
        # Two real open cavas, with a shoulder strap and an underarm bridge.
        at_side = abs(math.cos(theta)) < .36
        if at_side and 3 <= r < 23:
            continue
        a, b = r * around + c, r * around + (c + 1) % around
        faces.append((a, a + around, b + around, b))
# Drop unused vertices inside the armhole rather than retaining loose geometry.
used = sorted({v for face in faces for v in face})
remap = {old: i for i, old in enumerate(used)}
torso = mesh_object('01 / gathered blouse / real open armholes',
                    [vertices[i] for i in used], [tuple(remap[i] for i in face) for face in faces],
                    'foundation_gathered_blouse')
parent_to(torso, corset)
cloth(torso, {1.: [remap[i] for i in used if i // around in [0, rows]],
              .65: [remap[i] for i in used if i // around in [1, rows - 1]]})
sharp_seams(torso, {remap[i] for i in used if i % around == around // 2})
post_modifier(torso)


def boundary_loops(obj):
    counts = Counter(tuple(sorted((f.vertices[i], f.vertices[(i + 1) % len(f.vertices)])))
                     for f in obj.data.polygons for i in range(len(f.vertices)))
    graph = defaultdict(list)
    for (a, b), count in counts.items():
        if count == 1:
            graph[a].append(b)
            graph[b].append(a)
    if any(len(neighbors) != 2 for neighbors in graph.values()):
        raise ValueError('The authored fabric boundary is not a clean closed loop.')
    remaining, loops = set(graph), []
    while remaining:
        start = min(remaining)
        ordered, previous, current = [], None, start
        while current not in ordered:
            ordered.append(current)
            candidates = [i for i in graph[current] if i != previous]
            previous, current = current, candidates[0]
        if current != start:
            raise ValueError('Armhole boundary ordering failed.')
        remaining.difference_update(ordered)
        loops.append([obj.data.vertices[i].co.copy() for i in ordered])
    return loops


loops = boundary_loops(torso)
armholes = [loop for loop in loops if abs(sum(p.x for p in loop) / len(loop)) > .06]
if len(armholes) != 2 or len(loops) != 4:
    raise ValueError('Expected neckline, waist and exactly two genuine armholes.')


def tube(name, points, radius, material=ivory, role='foundation_blouse_trim', sides=8):
    vertices = []
    for index, point in enumerate(points):
        point = Vector(point)
        tangent = (Vector(points[min(index + 1, len(points) - 1)])
                   - Vector(points[max(0, index - 1)])).normalized()
        side = tangent.cross(Vector((0, 1, 0)))
        if side.length < .001:
            side = tangent.cross(Vector((1, 0, 0)))
        side.normalize()
        other = tangent.cross(side).normalized()
        for c in range(sides):
            angle = math.tau * c / sides
            vertices.append(point + radius * (side * math.cos(angle) + other * math.sin(angle)))
    faces = sleeve_faces(sides, len(points) - 1)
    faces += [tuple(range(sides - 1, -1, -1)), tuple((len(points) - 1) * sides + c for c in range(sides))]
    obj = mesh_object(name, vertices, faces, role, material)
    uv = obj.data.uv_layers.new(name='UVMap')
    for poly in obj.data.polygons:
        for loop in poly.loop_indices:
            index = obj.data.loops[loop].vertex_index
            uv.data[loop].uv = ((index % sides) / sides, (index // sides) / (len(points) - 1))
    return obj


def sewn_eyelets(name, edge, count, height, direction, carrier, deformation_target):
    """Actual looped thread on the photographed ruffle, not a solid alpha card."""
    edge = [Vector(p) for p in edge]
    lengths = [(edge[(i + 1) % len(edge)] - p).length for i, p in enumerate(edge)]
    cumulative = np.cumsum([0.] + lengths)
    def seam_point(t):
        distance = (t % 1) * cumulative[-1]
        index = min(len(edge) - 1, int(np.searchsorted(cumulative, distance, side='right')) - 1)
        return edge[index].lerp(edge[(index + 1) % len(edge)],
                                (distance - cumulative[index]) / lengths[index])
    vertices, faces, uv_faces = [], [], []
    sides, segments = 6, 16
    for repeat in range(count):
        start, end = seam_point(repeat/count), seam_point((repeat+1)/count)
        points = [start.lerp(end, k/segments) + direction * height * math.sin(math.pi*k/segments)
                  for k in range(segments+1)]
        offset = len(vertices)
        for row, p in enumerate(points):
            tangent = (points[min(row+1,segments)] - points[max(0,row-1)]).normalized()
            side = tangent.cross(direction).normalized()
            other = tangent.cross(side).normalized()
            for c in range(sides):
                angle = c/sides*math.tau
                vertices.append(p + .00024*(side*math.cos(angle)+other*math.sin(angle)))
        for face in sleeve_faces(sides,segments):
            faces.append(tuple(offset+i for i in face))
            uv_faces.append([((i%sides)/sides,(i//sides)/segments) for i in face])
        for face in [tuple(range(sides-1,-1,-1)),tuple(segments*sides+c for c in range(sides))]:
            faces.append(tuple(offset+i for i in face))
            uv_faces.append([((i%sides)/sides,(i//sides)/segments) for i in face])
    obj = mesh_object(name,vertices,faces,'foundation_blouse_needle_lace')
    uv = obj.data.uv_layers.new(name='UVMap')
    for polygon, coords in zip(obj.data.polygons,uv_faces):
        for loop, coordinate in zip(polygon.loop_indices,coords):
            uv.data[loop].uv = coordinate
    obj['actualThreadLoops'] = count
    obj['unseenRepeatsInferred'] = True
    surface_follow(obj,carrier,deformation_target)
    return obj


for root_loop in armholes:
    side = 1 if sum(p.x for p in root_loop) > 0 else -1
    label = 'right' if side == 1 else 'left'
    # Additional seam samples lie ON the actual boundary edges.
    root = [a.lerp(root_loop[(i + 1) % len(root_loop)], k / 2)
            for i, a in enumerate(root_loop) for k in range(2)]
    center = sum(root, Vector()) / len(root)
    cuff_center = Vector((side * .113, .000, .733))
    axis = (cuff_center - center).normalized()
    normal = sum(((root[i] - center).cross(root[(i + 1) % len(root)] - center)
                  for i in range(len(root))), Vector())
    if normal.dot(axis) < 0:
        root.reverse()
    basis_x = axis.cross(Vector((0, 1, 0))).normalized()
    basis_y = axis.cross(basis_x).normalized()
    angles = [math.atan2((p - center).dot(basis_y), (p - center).dot(basis_x)) for p in root]
    n, sleeve_rows = len(root), 30
    vertices = []
    for row in range(sleeve_rows + 1):
        t = row / sleeve_rows
        for point, angle in zip(root, angles):
            radial = basis_x * math.cos(angle) + basis_y * math.sin(angle)
            cuff = cuff_center + radial * (.0178 + .0008 * math.cos(15 * angle + .3))
            puff = .0165 * math.sin(math.pi * t) ** .85
            gather = (.0025 * math.sin(math.pi * t) + .001 * math.sin(math.pi * t) ** .3)
            phase = 15 * angle + .42 * math.sin(3 * angle) + .3 * t
            fold = gather * (.8 * math.cos(phase) + .2 * math.sin(31 * angle + t))
            vertices.append(point.lerp(cuff, t) + radial * (puff + fold))
    sleeve = mesh_object(f'01 / {label} gathered puff sleeve / sewn armhole', vertices,
                         sleeve_faces(n, sleeve_rows), 'foundation_puffed_sleeve')
    cloth(sleeve, {1.: list(range(n)) + list(range(sleeve_rows * n, (sleeve_rows + 1) * n)),
                  .7: list(range(n, n * 2))})
    surface_follow(sleeve, torso)
    sharp_seams(sleeve, set(range(0, len(vertices), n)))
    post_modifier(sleeve)
    # Binding coincides with actual sleeve roots; no floating primitive cap.
    actual_root = [sleeve.data.vertices[i].co for i in range(n)]
    seam_error = max((a - b).length for a, b in zip(actual_root, root))
    seam_audits.append({'name':label + ' armhole', 'rootVertices':n, 'maximumRootGap':seam_error,
                        'rootOnActualTorsoBoundary':True, 'unseenBackShapeInferred':True})
    if seam_error > 1e-7:
        raise ValueError('The puff sleeve is detached from its actual armhole.')
    cuff_ring = [Vector(v) for v in vertices[-n:]]
    binding = tube(f'01 / {label} sleeve elastic binding', cuff_ring + [cuff_ring[0]], .00065)
    surface_follow(binding, sleeve)
    cuff_vertices, cuff_rows = [], 8
    for row in range(cuff_rows + 1):
        t = row / cuff_rows
        for p, angle in zip(cuff_ring, angles):
            radial = basis_x * math.cos(angle) + basis_y * math.sin(angle)
            ruffle = t * (.0028 + .0018 * math.cos(21 * angle + .4))
            cuff_vertices.append(p + axis * .0075 * t + radial * ruffle)
    cuff = mesh_object(f'01 / {label} gathered cuff frill', cuff_vertices,
                       sleeve_faces(n, cuff_rows), 'foundation_blouse_cuff')
    surface_follow(cuff, sleeve)
    sharp_seams(cuff, set(range(0, len(cuff_vertices), n)))
    post_modifier(cuff, -.00022)
    sewn_eyelets(f'01 / {label} cuff looped needle lace', cuff_vertices[-n:], 28,
                 .0038, axis, cuff, sleeve)
    seam_audits.append({'name':label + ' cuff', 'rootVertices':n, 'maximumRootGap':0.,
                        'rootOnActualSleeveCuff':True})

# A genuine open scooped neck, pleated border and stitched binding rail.
n, frill_rows = around * 2, 8
neck = [vertices for vertices in (torso_position(c / around, 0) for c in range(around))]
root = [a.lerp(neck[(i + 1) % around], k / 2) for i, a in enumerate(neck) for k in range(2)]
frill_vertices = []
for row in range(frill_rows + 1):
    t = row / frill_rows
    for c, point in enumerate(root):
        angle = c / n * math.tau
        radial = Vector((math.sin(angle), -math.cos(angle), 0))
        fold = math.cos(43 * angle + .36 * math.sin(5 * angle))
        frill_vertices.append(point + Vector((0, 0, .0058 * t))
                              + radial * (.001 * t + .0016 * t * fold))
neck_frill = mesh_object('01 / gathered scoop neckline frill', frill_vertices,
                         [(r*n+c, (r+1)*n+c, (r+1)*n+(c+1)%n, r*n+(c+1)%n)
                          for r in range(frill_rows) for c in range(n)], 'foundation_neckline_frill')
surface_follow(neck_frill, torso)
sharp_seams(neck_frill, set(range(0, len(frill_vertices), n)))
post_modifier(neck_frill, -.00020)
sewn_eyelets('01 / neckline looped needle lace', frill_vertices[-n:], 68,
             .0038, Vector((0,0,1)), neck_frill, torso)
binding = tube('01 / neckline stitched binding', neck + [neck[0]], .00065)
surface_follow(binding, torso)
seam_audits.append({'name':'neckline', 'rootVertices':n, 'maximumRootGap':0.,
                    'rootOnActualBlouseBoundary':True})

for side in [-1, 1]:
    rail = [torso_position(side * .004, t / 40) + Vector((0, -.00045, 0)) for t in range(29)]
    obj = tube(f'01 / blouse center placket rail {side}', rail, .0004)
    surface_follow(obj, torso)

# Small diamond-loop cross/key ornament visible at the center of this photo.
center = torso_position(0, .12) + Vector((0, -.0012, .0015))
diamond = [(0,0,.006),(.0022,0,.003),(0,0,0),(-.0022,0,.003),(0,0,.006)]
ornament_paths = [diamond, [(0,0,0),(0,0,-.012)],
                  [(-.0035,0,-.0035),(.0035,0,-.0035)],
                  [(-.0018,0,-.0085),(.0018,0,-.0085)]]
for index, path in enumerate(ornament_paths):
    obj = tube(f'01 / blouse aged brass key ornament {index}',
               [center + Vector(p) for p in path], .00055, brass, 'foundation_blouse_ornament')
    surface_follow(obj, torso)

for i in range(3):
    center = torso_position(0, .35 + i * .14) + Vector((0, -.0009, 0))
    points = [center + Vector((math.cos(k/16*math.tau)*.0008, 0,
                               math.sin(k/16*math.tau)*.0008)) for k in range(17)]
    obj = tube(f'01 / blouse center sewn button {i}', points, .0003)
    surface_follow(obj, torso)

scene.frame_set(1)
for modifier in temporarily_disabled:
    modifier.show_viewport = True
bpy.context.view_layer.update()
if any(cage_hash(bpy.data.objects[name]) != digest for name, digest in existing.items()):
    raise ValueError('The existing foundation or intact exterior cage was modified.')
audits = []
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in inherited + new:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.get('UVMap')
    uv_coords = np.asarray([d.uv[:] for d in uv.data]) if uv else np.empty((0,2))
    if not uv or not np.isfinite(uv_coords).all():
        raise ValueError('Evaluated BCB UVs failed: ' + obj.name)
    audit = {'name':obj.name, 'role':obj['role'], 'baseVertices':len(obj.data.vertices),
                   'basePolygons':len(obj.data.polygons), 'evaluatedVertices':len(mesh.vertices),
                   'triangles':len(mesh.loop_triangles), 'uvMaps':[l.name for l in mesh.uv_layers],
                   'uvFinite':True, 'actualThickness':any(m.type=='NODES' for m in obj.modifiers),
                   'parent':obj.parent.name if obj.parent else None, 'attachment':obj.get('attachment'),
                   'surfaceDeformBindings':[{'target':m.target.name, 'bound':bool(m.is_bound)}
                                            for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
                   'rigPresent':False, 'fidelityVerified':False}
    if obj.get('actualThreadLoops'):
        audit.update(actualThreadLoops=obj['actualThreadLoops'], unseenRepeatsInferred=True)
    audits.append(audit)
    evaluated.to_mesh_clear()
editable = out / 'chapeleiro_foundation_blouse.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable), compress=True)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited + new:
    obj.select_set(True)
model = out / 'foundation_blouse.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True, export_animations=False)
report = {**parent, 'method':'incremental_photo_1_blouse_open_armholes_sewn_gathers_and_existing_foundation',
           'model':str(model.resolve()), 'modelSha256':sha(model),
           'editableBlend':str(editable.resolve()), 'editableBlendSha256':sha(editable),
           'parentGeneration':str(Path(args.parent).resolve()), 'parentGenerationSha256':sha(args.parent),
           'inheritedInternalPieces':len(inherited), 'addedInternalPieces':len(new),
           'existingCagesUnchanged':True, 'incrementalRefinement':True, 'pieces':audits,
           'blouseSeamAudit':seam_audits, 'additionalCreditsConsumed':0,
           'simulationCages':[{'name':o.name,'visibleFabric':o['visibleFabric'],
                               'vertices':len(o.data.vertices),'oneClothSolver':True,
                               'simulationVerified':False} for o in physics_carriers.values()],
           'needleLaceConstruction':'Looped opaque thread geometry based on the visible neckline and cuffs; unseen repeats are inferred.',
           'limitations':['Blouse proportions and unseen back shape are inferred and require the four-view photo review.',
                          'Bloomers, garters and stockings are still missing; existing petticoat drapes require further tailoring.',
                          'Surface Deform and parenting are attachments, not skinning or gameplay cloth verification.']}
(out / 'generation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('FOUNDATION_BLOUSE_SAVED', json.dumps({'inheritedPieces':len(inherited), 'addedPieces':len(new),
                                          'triangles':sum(p['triangles'] for p in audits),
                                          'existingCagesUnchanged':True, 'rigPresent':False}), flush=True)
