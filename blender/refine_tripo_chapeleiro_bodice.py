"""Reconstruct sheet-2 surfaces around the newly generated Chapeleiro scan.

Only this variant's authorized Tripo extraction is read. Hidden torso surfaces
are inferred from its measurements and the front/back patterns on sheet 2.
The saved result is a review checkpoint, not a finished or rigged layer.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--extraction', required=True)
parser.add_argument('--stage-plan', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
record = json.loads(Path(args.extraction).read_text(encoding='utf-8'))
plan = json.loads(Path(args.stage_plan).read_text(encoding='utf-8'))
stage = next(s for s in plan['stages'] if s['id'] == 'alice_chapeleiro_stage_02')
if record.get('studioModelId') != '32254621-cdf9-43bd-8297-54446796d892':
    raise ValueError('This study requires the authorized new Chapeleiro Tripo model.')
if record.get('reusedGeometry') is not False or record.get('variant') != stage['variant']:
    raise ValueError('Legacy or another variant geometry is not permitted.')
photo = Path(stage['sourcePhoto'])
if record['sourcePhotoSha256'] != stage['sourcePhotoSha256'] or sha(photo) != stage['sourcePhotoSha256']:
    raise ValueError('The exact layer-2 photograph is required.')
if sha(record['editableBlend']) != record['editableBlendSha256']:
    raise ValueError('The extraction changed since its provenance record.')
out = Path(args.output)
if out.exists():
    raise ValueError('Use a new version directory; preserve previous geometry and evidence.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])

def interpolate(value, samples):
    value = max(samples[0][0], min(samples[-1][0], value))
    for (a, x), (b, y) in zip(samples, samples[1:]):
        if a <= value <= b:
            return x + (y - x) * (value - a) / (b - a)
    return samples[-1][1]

def simple_material(name, color, roughness, metallic=0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return material

photo_image = bpy.data.images.load(str(photo), check_existing=True)
photo_image.pack()
cloth = bpy.data.materials.new('Tecido verde / foto original da camada 2')
cloth.use_nodes = True
nodes, links = cloth.node_tree.nodes, cloth.node_tree.links
shader = nodes.get('Principled BSDF')
texture = nodes.new('ShaderNodeTexImage')
texture.image = photo_image
texture.extension = 'EXTEND'
links.new(texture.outputs['Color'], shader.inputs['Base Color'])
shader.inputs['Roughness'].default_value = .73
shader.inputs['Metallic'].default_value = 0
lining = simple_material('Forro verde escuro / superfície interna inferida', (.018, .036, .030), .82)
gold = simple_material('Latão envelhecido / bordas e ilhós em volume', (.19, .12, .044), .44, .68)
cord = simple_material('Cordão verde escuro / cruzamentos em volume', (.025, .043, .031), .77)

# Cross sections are fitted to the new scan (approximately 0.98 m normalized
# total height). Rear values exclude the hair/bow envelope and remain inferred.
profiles = [
    (.589, .072, .074, .056), (.620, .066, .069, .044),
    (.640, .050, .061, .038), (.670, .044, .059, .032),
    (.690, .056, .059, .035), (.710, .064, .068, .040),
    (.730, .066, .065, .043), (.750, .067, .052, .038),
    (.800, .083, .027, .031),
]

def radii(z):
    return tuple(interpolate(z, [(p[0], p[k]) for p in profiles]) for k in (1, 2, 3))

def top(theta):
    u = abs(math.sin(theta))
    if math.cos(theta) >= 0:
        samples = [(0, .741), (.30, .751), (.52, .767), (.69, .796),
                   (.84, .790), (.95, .752), (1, .718)]
    else:
        samples = [(0, .770), (.30, .770), (.52, .782), (.69, .800),
                   (.84, .790), (.95, .748), (1, .718)]
    return interpolate(u, samples)

def hem(theta):
    # The pattern has a pointed center and separate small scalloped tabs.
    return .619 - .030 * abs(math.cos(theta)) ** 7 + .004 * abs(math.sin(theta * 6))

def surface(theta, z, offset=0):
    rx, front, rear = radii(z)
    depth = front if math.cos(theta) >= 0 else rear
    flute = .00065 * math.sin(theta * 24) * math.sin(math.pi * max(0, min(1, (z - .62) / .17)))
    return Vector((-.002 + (rx + flute + offset) * math.sin(theta),
                   .002 - (depth + flute + offset) * math.cos(theta), z))

front_edges = [(87, 699, 957), (120, 594, 1059), (160, 614, 1045),
               (220, 638, 1025), (280, 679, 993), (330, 699, 980),
               (395, 695, 980), (435, 681, 994), (480, 651, 1020),
               (514, 650, 1028), (555, 787, 885), (573, 830, 840)]
back_edges = [(600, 633, 1030), (640, 658, 1005), (700, 672, 986),
              (780, 704, 968), (840, 700, 972), (900, 670, 995),
              (935, 677, 988), (965, 830, 846)]

# Find the cloth silhouette on the actual pattern photograph. Fixed bounding
# boxes sampled the dark background at the sides of the fitted torso.
photo_pixels = np.empty(photo_image.size[0] * photo_image.size[1] * photo_image.channels, dtype=np.float32)
photo_image.pixels.foreach_get(photo_pixels)
photo_pixels = photo_pixels.reshape(photo_image.size[1], photo_image.size[0], photo_image.channels)[::-1]

def measured_pattern_edges(box):
    x0, y0, x1, y1 = box
    color = photo_pixels[y0:y1, x0:x1, :3]
    green = ((color[:, :, 1] > color[:, :, 0] * 1.08)
             & (color[:, :, 1] > color[:, :, 2] * 1.025)
             & (color.mean(axis=2) > .008))
    measurements = []
    for row in range(len(green)):
        coordinates = np.nonzero(green[max(0, row - 2):row + 3])[1]
        if len(coordinates) >= 6:
            measurements.append((row + y0, float(np.quantile(coordinates, .01)) + x0,
                                 float(np.quantile(coordinates, .99)) + x0))
    if len(measurements) < (y1 - y0) * .8:
        raise ValueError('Own-photo cloth silhouette could not be measured reliably.')
    # Gentle smoothing removes individual embroidery pixels from the outline.
    return [(row[0], float(np.mean([p[1] for p in measurements[max(0, i - 3):i + 4]])),
             float(np.mean([p[2] for p in measurements[max(0, i - 3):i + 4]])))
            for i, row in enumerate(measurements)]

front_edges = measured_pattern_edges((585, 87, 1080, 573))
back_edges = measured_pattern_edges((600, 600, 1080, 965))
pattern_arrays = {True: np.asarray(front_edges).T, False: np.asarray(back_edges).T}

def photo_uv(theta, z, front_override=None):
    front = math.cos(theta) >= 0 if front_override is None else front_override
    py = 573 - (z - .589) * 2230 if front else 965 - (z - .589) * 1810
    ordinates, left, right = pattern_arrays[front]
    lo = float(np.interp(py, ordinates, left)) + 7
    hi = float(np.interp(py, ordinates, right)) - 7
    if hi < lo:
        lo, hi = (lo + hi) / 2 - 1, (lo + hi) / 2 + 1
    scale = 2670 if front else 2450
    # Preserve the central embroidery's scale. Clamp only samples that leave
    # the cloth instead of stretching every row to its measured silhouette.
    px = max(lo, min(hi, 837 + radii(z)[0] * math.sin(theta) * scale))
    return px / photo_image.size[0], 1 - py / photo_image.size[1]

def make_mesh(name, vertices, faces, uv, material, face_uv=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if uv:
        layer = mesh.uv_layers.new(name='Foto da própria camada')
        for polygon in mesh.polygons:
            for corner, loop_index in enumerate(polygon.loop_indices):
                layer.data[loop_index].uv = (face_uv[polygon.index][corner] if face_uv is not None
                                           else uv[mesh.loops[loop_index].vertex_index])
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj['alice_stage'] = stage['id']
    obj['fidelity_verified'] = False
    obj['rig_pending'] = True
    return obj

def add_lining(obj, thickness):
    obj.data.materials.append(lining)
    modifier = obj.modifiers.new('Espessura e forro reais / sem fechar aberturas de vestir', 'SOLIDIFY')
    modifier.thickness = thickness
    modifier.offset = -1
    modifier.use_even_offset = True
    modifier.material_offset = 1
    modifier.material_offset_rim = 1

scan_sleeves = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('Manga ')]
if len(scan_sleeves) != 2:
    raise ValueError('Expected the two sleeves from the authorized new extraction.')
for obj in list(bpy.context.scene.objects):
    if obj not in scan_sleeves:
        bpy.data.objects.remove(obj, do_unlink=True)

sleeve_audit = []
source_shader = next(n for n in scan_sleeves[0].data.materials[0].node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
source_atlas = next(l.from_node.image for l in source_shader.inputs['Base Color'].links
                    if l.from_node.type == 'TEX_IMAGE')
source_pixels = np.empty(source_atlas.size[0] * source_atlas.size[1] * source_atlas.channels, dtype=np.float32)
source_atlas.pixels.foreach_get(source_pixels)
source_pixels = source_pixels.reshape(source_atlas.size[1], source_atlas.size[0], source_atlas.channels)
for obj in scan_sleeves:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    original_area = sum(f.calc_area() for f in bm.faces)
    # The imported atlas splits connected cloth at UV seams. Weld coincident
    # positions before classifying components so folds are not lost as specks.
    original_vertices = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.000001)
    welded_vertices = original_vertices - len(bm.verts)
    old_uv = bm.loops.layers.uv.active
    hair_faces = []
    for face in bm.faces:
        center = face.calc_center_median()
        upper_rear_cut = center.z > .788 and abs(center.x) < .109 and center.y > .005
        if upper_rear_cut:
            hair_faces.append(face)
            continue
        if center.z < .766 or abs(center.x) > .107:
            continue
        coords = face.loops[0][old_uv].uv
        u = max(0, min(source_atlas.size[0] - 1, int(coords.x * (source_atlas.size[0] - 1))))
        v = max(0, min(source_atlas.size[1] - 1, int(coords.y * (source_atlas.size[1] - 1))))
        r, g, b = source_pixels[v, u, :3]
        if (r + g + b) / 3 < .070 and not (g > r * 1.025 and g > b * 1.025):
            hair_faces.append(face)
    bmesh.ops.delete(bm, geom=hair_faces, context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    remaining = set(bm.verts)
    groups = []
    while remaining:
        todo = [remaining.pop()]
        component = set(todo)
        while todo:
            for edge in todo.pop().link_edges:
                for vertex in edge.verts:
                    if vertex in remaining:
                        remaining.remove(vertex)
                        component.add(vertex)
                        todo.append(vertex)
        groups.append(component)
    specks = [v for g in groups if len(g) < 32 for v in g]
    removed = len(specks)
    bmesh.ops.delete(bm, geom=specks, context='VERTS')
    boundary = [v for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    for unused in range(3):
        bmesh.ops.smooth_vert(bm, verts=boundary, factor=.18, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    retained_area = sum(f.calc_area() for f in bm.faces) / original_area
    if retained_area < .90:
        raise ValueError('Sleeve refinement removed substantial cloth surface; refusing to export.')
    bm.to_mesh(obj.data)
    bm.free()
    side = -1 if sum(v.co.x for v in obj.data.vertices) < 0 else 1
    center_x = -.107 if side < 0 else .105
    photo_x = 152 if side < 0 else 416
    uv = obj.data.uv_layers.active
    for loop in obj.data.loops:
        p = obj.matrix_world @ obj.data.vertices[loop.vertex_index].co
        px = photo_x + (p.x - center_x) * 3300
        py = 1285 - (p.z - .690) * 3100
        uv.data[loop.index].uv = (px / photo_image.size[0], 1 - py / photo_image.size[1])
    obj.data.materials.clear()
    obj.data.materials.append(cloth)
    for polygon in obj.data.polygons:
        polygon.material_index = 0
    add_lining(obj, .0005)
    obj['alice_stage'] = stage['id']
    obj['rig_pending'] = True
    sleeve_audit.append({'name': obj.name, 'coincidentAtlasVerticesWelded': welded_vertices,
                         'removedDisconnectedSpeckVertices': removed,
                         'removedUpperHairFaces': len(hair_faces), 'surfaceAreaRetention': retained_area,
                         'boundarySmoothed': len(boundary), 'foldsFromNewTripoScan': True,
                         'textureSource': 'Own sheet 2 isolated sleeve; unseen back pattern inferred.'})

segments, rows = 256, 120
vertices, faces, uv, face_uv = [], [], [], []
for row in range(rows + 1):
    t = row / rows
    for i in range(segments):
        theta = i * math.tau / segments
        z = hem(theta) + (top(theta) - hem(theta)) * t
        vertices.append(surface(theta, z))
        uv.append(photo_uv(theta, z))
for row in range(rows):
    for i in range(segments):
        j = (i + 1) % segments
        face = (row * segments + i, row * segments + j,
                (row + 1) * segments + j, (row + 1) * segments + i)
        middle = (i + .5) * math.tau / segments
        z = sum(vertices[k].z for k in face) / 4
        # The rear photograph shows a narrow opening behind its lacing.
        if abs(middle - math.pi) < .075 and .606 < z < .765:
            continue
        faces.append(face)
        front = math.cos(middle) >= 0
        # UV seams are per face corner, so side faces never interpolate
        # across the background between the front and back patterns.
        face_uv.append([photo_uv((k % segments) * math.tau / segments, vertices[k].z, front) for k in face])

# Sew shoulder bridges to existing top vertices. This produces distinct neck
# and arm openings rather than a tube with its arm sockets covered by cloth.
for side in (-1, 1):
    grid = []
    for step in range(33):
        t = step / 32
        strip = []
        for i in range(30, 48):
            front_i = (side * i) % segments
            back_i = (side * (segments // 2 - i)) % segments
            a, b = vertices[rows * segments + front_i], vertices[rows * segments + back_i]
            if step in (0, 32):
                strip.append(rows * segments + (front_i if step == 0 else back_i))
            else:
                point = a.lerp(b, t)
                point.z += .006 * math.sin(math.pi * t)
                strip.append(len(vertices))
                vertices.append(point)
                # Cloth from the shoulder area of the front pattern.
                px = (669 if side < 0 else 989) + side * (i - 39) * 3
                uv.append((px / photo_image.size[0], 1 - (135 + 30 * math.sin(math.pi * t)) / photo_image.size[1]))
        grid.append(strip)
    for a, b in zip(grid, grid[1:]):
        for j in range(len(a) - 1):
            face = (a[j], a[j + 1], b[j + 1], b[j])
            faces.append(face)
            face_uv.append([uv[k] for k in face])

bodice = make_mesh('Corpete / frente verde, costas e alças reconstruídas da foto 2', vertices, faces, uv, cloth, face_uv)
add_lining(bodice, .00065)

def curve_mesh(name, paths, radius, material):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 2
    for points, cyclic in paths:
        spline = data.splines.new('POLY')
        spline.points.add(len(points) - 1)
        for p, point in zip(spline.points, points):
            p.co = (*point, 1)
        spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj['alice_stage'] = stage['id']
    obj['rig_pending'] = True
    return obj

# Actual boundary loops include neck, both armholes and lower hem.
bm = bmesh.new()
bm.from_mesh(bodice.data)
edges = {e for e in bm.edges if e.is_boundary}
loops = []
while edges:
    edge = edges.pop()
    start, current = edge.verts
    points = [start.co.copy(), current.co.copy()]
    while current != start:
        following = next((e for e in current.link_edges if e in edges), None)
        if following is None:
            break
        edges.remove(following)
        current = following.other_vert(current)
        points.append(current.co.copy())
    loops.append((points[:-1] if current == start else points, current == start))
bm.free()
if len(loops) != 5:
    raise ValueError('Expected neck, two armholes, hem and the rear lacing opening.')
curve_mesh('Vivo de latão / decote, cavas e bainha em volume', loops, .00065, gold)

seams = []
for theta in [-.90, -.68, -.46, -.25, .25, .46, .68, .90,
              math.pi - .80, math.pi - .52, math.pi - .25,
              math.pi + .25, math.pi + .52, math.pi + .80]:
    lo, hi = hem(theta) + .002, top(theta) - .002
    seams.append(([surface(theta, lo + (hi - lo) * i / 80, .00055) for i in range(81)], False))
curve_mesh('Barbatanas / costuras douradas em relevo', seams, .00037, gold)

eyelets, laces = [], []
front_lacing = [(337, 780, 872), (374, 786, 870), (411, 788, 870),
                (448, 790, 866), (482, 791, 865), (507, 809, 848), (539, 816, 841)]
back_lacing = [(651, 807, 846), (684, 808, 847), (720, 808, 847),
               (753, 808, 847), (784, 808, 847), (816, 808, 847),
               (848, 808, 847), (880, 808, 847), (911, 808, 847), (941, 807, 846)]
for rear, rows_from_photo in [(False, front_lacing), (True, back_lacing)]:
    attachments = []
    for py, left, right in rows_from_photo:
        z = .589 + ((965 - py) / 1810 if rear else (573 - py) / 2230)
        pair = []
        for px in (left, right):
            scale = 2450 if rear else 2670
            theta = math.asin(max(-.99, min(.99, (px - 837) / scale / radii(z)[0])))
            if rear:
                theta = math.pi - theta
            center = surface(theta, z, .0013)
            pair.append(center)
            eyelets.append(([center + Vector((.0018 * math.cos(t * math.tau / 20), 0,
                                              .0018 * math.sin(t * math.tau / 20))) for t in range(20)], True))
        attachments.append(pair)
        if rear:
            laces.append(([pair[0].lerp(pair[1], i / 16) for i in range(17)], False))
    for upper, lower in zip(attachments, attachments[1:]):
        for side in (0, 1):
            a, b = upper[side].copy(), lower[1 - side].copy()
            if rear:
                middle = (upper[0].x + upper[1].x + lower[0].x + lower[1].x) / 4
                a.x = middle + (a.x - middle) * .46
                b.x = middle + (b.x - middle) * .46
            path = []
            for i in range(33):
                t = i / 32
                p = a.lerp(b, t)
                p.y += (1 if rear else -1) * (.0012 * math.sin(math.pi * t) + (.0006 if side else 0))
                path.append(p)
            laces.append((path, False))
curve_mesh('Ilhós de latão / amarrações frontal e traseira', eyelets, .0005, gold)
curve_mesh('Cordões cruzados / frente e costas', laces, .0008, cord)

ornaments = []
# Small antique loops follow the neckline instead of painting the lace flat.
for rear in (False, True):
    for i in range(43):
        theta = -.72 + i * 1.44 / 42
        if rear:
            theta = math.pi - theta
        center = surface(theta, top(theta), .0008)
        tangent = Vector((math.cos(theta), math.sin(theta), 0))
        ornaments.append(([center + tangent * (.0015 * math.cos(math.tau * t / 16))
                           + Vector((0, 0, .002 + .0022 * math.sin(math.tau * t / 16)))
                           for t in range(16)], True))
front_center = surface(0, .740, .0016)
for side in (-1, 1):
    ornaments.append(([front_center + Vector((side * (.004 + .005 * math.cos(math.tau * i / 32)),
                                               -.001 * math.sin(math.tau * i / 32),
                                               .004 * math.sin(math.tau * i / 32))) for i in range(32)], True))
curve_mesh('Renda do decote e fecho / pequenos laços de latão em volume', ornaments, .00035, gold)

bpy.context.view_layer.update()
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
stats = []
depsgraph = bpy.context.evaluated_depsgraph_get()
for obj in meshes:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    stats.append({'component': obj.name, 'vertices': len(mesh.vertices),
                  'triangles': len(mesh.loop_triangles), 'rigged': False, 'fidelityVerified': False})
    evaluated.to_mesh_clear()
blend = out / 'chapeleiro_bodice_refinement.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_animations=False)
record['parentExtractionAudit'] = record.pop('extractionAudit', [])
record.update(method='own_layer_2_tailoring_fitted_to_authorized_new_Tripo_scan',
              modelGenerator='Blender local reconstruction around the authorized new Tripo scan',
              model=str(model.resolve()), modelSha256=sha(model),
              editableBlend=str(blend.resolve()), editableBlendSha256=sha(blend),
              geometryParentSha256=record['modelSha256'],
              sourceCrop=[30, 175, 555, 708], sourceViews=[],
              status='generated_awaiting_visual_review', modelUpAxis='Y',
              localWorkStatus='layer_2_surface_reconstruction_pending_visual_review_and_rig',
              vertices=sum(s['vertices'] for s in stats), triangles=sum(s['triangles'] for s in stats),
              componentAudit=stats, sleeveRefinementAudit=sleeve_audit,
              refinementScriptSha256=sha(__file__),
              bodyConstruction={'neckAndArmOpenings': 3, 'rearClosureOpening': True,
                                'shoulderBridgesSewnToBody': True,
                                'liningThickness': .00065, 'frontAndBackPhotoProjection': True,
                                'rearDepthInferredWithoutHairEnvelope': True},
              materialAudit=['Original sheet-2 color projection; lighting baked in the photograph remains approximate.',
                             'Fabric and metal roughness are local estimates, not measured material scans.'],
              additionalCreditsConsumed=0, rigPresent=False, fidelityVerified=False,
              motionVerified=False, clothCollisionVerified=False, countsAsFinishedLayer=False,
              limitations=['Sleeve cuff shape and unseen rear folds still require comparison with sheet 2.',
                           'Tailoring, photo projection and proportions require actual four-view review.',
                           'No shared rig or walk/run/jump/attack deformation approval yet.'])
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('LAYER_2_REFINEMENT_CREATED', json.dumps({'vertices': record['vertices'], 'triangles': record['triangles'],
                                             'boundaryLoops': len(loops), 'additionalCredits': 0}))
