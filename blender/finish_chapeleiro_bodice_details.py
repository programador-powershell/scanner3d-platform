"""Model the remaining sheet-2 trim around the new Chapeleiro bodice scan.

Five overlapping tabs, linked chains, cuff bows, pleated frills and perforated
lace are actual curved/thick geometry. This is still a visual-review checkpoint.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

parser = argparse.ArgumentParser()
parser.add_argument('--generation', required=True)
parser.add_argument('--stage-plan', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
record = json.loads(Path(args.generation).read_text(encoding='utf-8'))
stage = next(s for s in json.loads(Path(args.stage_plan).read_text(encoding='utf-8'))['stages']
             if s['id'] == 'alice_chapeleiro_stage_02')
if record.get('studioModelId') != '32254621-cdf9-43bd-8297-54446796d892' or record.get('reusedGeometry') is not False:
    raise ValueError('Only the authorized new Tripo Chapeleiro reconstruction is permitted.')
for file, digest in [(record['editableBlend'], record['editableBlendSha256']),
                     (record['model'], record['modelSha256']),
                     (stage['sourcePhoto'], stage['sourcePhotoSha256'])]:
    if sha(file) != digest:
        raise ValueError('Changed geometry or original stage photograph.')
if record['sourcePhotoSha256'] != stage['sourcePhotoSha256']:
    raise ValueError('Wrong layer photograph.')
out = Path(args.output)
if out.exists():
    raise ValueError('Use a new checkpoint directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=record['editableBlend'])
cloth = bpy.data.materials['Tecido verde / foto original da camada 2']
lining = bpy.data.materials['Forro verde escuro / superfície interna inferida']
gold = bpy.data.materials['Latão envelhecido / bordas e ilhós em volume']
image = next(n.image for n in cloth.node_tree.nodes if n.type == 'TEX_IMAGE')

def material(name, color, roughness, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return mat

ribbon_mat = material('Fita bronze dos punhos / estimativa local da foto 2', (.092, .047, .018), .43)
lace_mat = material('Renda dourada fosca / fios com aberturas reais', (.26, .185, .094), .67, .12)
parts = []

def mesh_object(name, vertices, faces, uvs, mat, role, thickness=0):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    if uvs:
        layer = mesh.uv_layers.new(name='Foto original da própria camada 2')
        for loop in mesh.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if thickness:
        mesh.materials.append(lining)
        modifier = obj.modifiers.new('Espessura e verso reais', 'SOLIDIFY')
        modifier.thickness = thickness
        modifier.offset = -1
        modifier.material_offset = 1
        modifier.material_offset_rim = 1
    obj['alice_stage'] = stage['id']
    obj['rig_role'] = role
    obj['rig_pending'] = True
    obj['fidelity_verified'] = False
    parts.append({'component': name, 'rigRole': role, 'geometryFromOwnPhoto': True})
    return obj

def curves(name, paths, radius, mat, role):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 1
    for points, cyclic in paths:
        spline = data.splines.new('POLY')
        spline.points.add(len(points) - 1)
        for p, value in zip(spline.points, points):
            p.co = (*value, 1)
        spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj['alice_stage'] = stage['id']
    obj['rig_role'] = role
    obj['rig_pending'] = True
    parts.append({'component': name, 'rigRole': role, 'geometryFromOwnPhoto': True})
    return obj

profiles = [(.589, .072, .074, .056), (.620, .066, .069, .044),
            (.640, .050, .061, .038), (.670, .044, .059, .032),
            (.690, .056, .059, .035), (.710, .064, .068, .040),
            (.730, .066, .065, .043), (.750, .067, .052, .038), (.800, .083, .027, .031)]

def interpolate(value, points):
    value = max(points[0][0], min(points[-1][0], value))
    for (a, x), (b, y) in zip(points, points[1:]):
        if a <= value <= b:
            return x + (y - x) * (value - a) / (b - a)
    return points[-1][1]

def radii(z):
    return tuple(interpolate(z, [(p[0], p[k]) for p in profiles]) for k in (1, 2, 3))

def shell(theta, z, offset=0):
    rx, front, rear = radii(z)
    return Vector((-.002 + (rx + offset) * math.sin(theta),
                   .002 - ((front if math.cos(theta) >= 0 else rear) + offset) * math.cos(theta), z))

def neckline(theta):
    front = math.cos(theta) >= 0
    samples = ([(0, .741), (.30, .751), (.52, .767), (.69, .796), (.84, .790), (.95, .752), (1, .718)]
               if front else [(0, .770), (.30, .770), (.52, .782), (.69, .800), (.84, .790), (.95, .748), (1, .718)])
    return interpolate(abs(math.sin(theta)), samples)

def front_photo_point(px, py, offset=.0019):
    z = .589 + (573 - py) / 2230
    theta = math.asin(max(-.99, min(.99, (px - 837) / 2670 / radii(z)[0])))
    return shell(theta, z, offset)

for obj in list(bpy.context.scene.objects):
    if obj.type != 'MESH':
        continue
    obj['rig_role'] = 'torso'
    if obj.name.startswith('Renda do decote e fecho'):
        bpy.data.objects.remove(obj, do_unlink=True)

# Replace the scan's different full-outfit cuffs, retaining its actual puff folds.
for obj in [o for o in bpy.context.scene.objects if o.name.startswith('Manga ')]:
    side = 1 if sum(v.co.x for v in obj.data.vertices) > 0 else -1
    label = 'L' if side > 0 else 'R'
    obj['rig_role'] = 'sleeve_' + label
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                          dist=.000001, plane_co=(0, 0, .731), plane_no=(0, 0, 1), clear_inner=True)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    cuff_center = Vector((side * .104, .019, .731))
    for v in bm.verts:
        t = max(0, min(1, (.744 - v.co.z) / .013))
        if t:
            angle = math.atan2((v.co.y - .019) / .043, (v.co.x - cuff_center.x) / .024)
            target = Vector((cuff_center.x + .024 * math.cos(angle),
                             .019 + .031 * math.sin(angle), v.co.z))
            v.co = v.co.lerp(target, t * t * (3 - 2 * t))
    bm.to_mesh(obj.data)
    bm.free()
    # The even-thickness miter at a cut wrinkle produced a 16 cm spike in the
    # actual v008 side render. Normal offsets keep the inner surface bounded.
    for modifier in obj.modifiers:
        if modifier.type == 'SOLIDIFY':
            modifier.use_even_offset = False
            modifier.use_quality_normals = True
            modifier.thickness_clamp = .5
    parts.append({'component': obj.name, 'rigRole': obj['rig_role'],
                  'retainedNewTripoPuffFolds': True, 'fullOutfitCuffReplacedByOwnSheet2': True})

    axis = Vector((side * .10, 0, -.995)).normalized()
    across = Vector((.995, 0, side * .10)).normalized()
    depth = Vector((0, 1, 0))
    def cuff_point(angle, t):
        flare = .024 + .007 * t
        pleat = (.0008 + .0036 * t) * math.cos(angle * 12)
        return (cuff_center + axis * (.028 * t) + across * ((flare + pleat) * math.cos(angle))
                + depth * ((.031 + .005 * t + pleat) * math.sin(angle))
                + axis * (.0016 * t * math.cos(angle * 12)))
    verts, faces, uv = [], [], []
    rings, count = 20, 192
    for row in range(rings + 1):
        t = row / rings
        for i in range(count):
            angle = math.tau * i / count
            p = cuff_point(angle, t)
            verts.append(p)
            px = (152 if side < 0 else 416) + (p.x - cuff_center.x) * 3000
            py = 1180 + t * 78
            uv.append((px / image.size[0], 1 - py / image.size[1]))
    for row in range(rings):
        for i in range(count):
            j = (i + 1) % count
            faces.append((row * count + i, row * count + j, (row + 1) * count + j, (row + 1) * count + i))
    mesh_object('Punho ' + label + ' / tecido verde plissado da foto 2', verts, faces, uv, cloth, 'cuff_' + label, .00045)

    # Narrow bronze ribbon and its sewn edges.
    band_verts, band_faces = [], []
    for row in range(2):
        for i in range(128):
            angle = math.tau * i / 128
            band_verts.append(cuff_center + axis * (-.003 + row * .0045)
                              + across * (.0246 * math.cos(angle)) + depth * (.0316 * math.sin(angle)))
    for i in range(128):
        j = (i + 1) % 128
        band_faces.append((i, j, 128 + j, 128 + i))
    mesh_object('Punho ' + label + ' / fita bronze', band_verts, band_faces, None, ribbon_mat, 'cuff_' + label, .00035)

    bow_center = cuff_center + Vector((0, -.033, .0018))
    for half in (-1, 1):
        verts, faces = [], []
        for i in range(49):
            t = i / 48
            p = bow_center + Vector((half * .010 * math.sin(math.pi * t),
                                      -.002 * math.sin(math.tau * t), .0045 * math.sin(math.tau * t)))
            width = .0018 * (.45 + math.sin(math.pi * t))
            verts.extend([p + Vector((0, 0, -width)), p + Vector((0, 0, width))])
        for i in range(48):
            faces.append((i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2))
        mesh_object('Laco ' + label + ' / volta ' + str(half), verts, faces, None, ribbon_mat, 'cuff_' + label, .0003)
        verts, faces = [], []
        for i in range(25):
            t = i / 24
            p = bow_center + Vector((half * (.002 + .0055 * t), -.001 + .002 * t, -.0115 * t))
            width = .0017 * (1 - .25 * t)
            verts.extend([p + Vector((-width, 0, 0)), p + Vector((width, 0, 0))])
        for i in range(24):
            faces.append((i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2))
        mesh_object('Laco ' + label + ' / ponta ' + str(half), verts, faces, None, ribbon_mat, 'ribbon_' + label, .0003)
    knot = [bow_center + Vector((.0015 * math.cos(math.tau * i / 24),
                                 -.0015, .0022 * math.sin(math.tau * i / 24))) for i in range(24)]
    curves('Laco ' + label + ' / no e vivos', [(knot, True)], .00055, gold, 'cuff_' + label)

    # Perforated lace: three connected rows, scalloped outer edge and rosettes.
    lace_paths = []
    cells = 32
    def lace_point(angle, level, extra=0):
        return cuff_point(angle, 1) + axis * (level * .007 + extra)
    for level in (0, .45):
        lace_paths.append(([lace_point(math.tau * i / 256, level) for i in range(256)], True))
    for cell in range(cells):
        a, b = cell * math.tau / cells, (cell + 1) * math.tau / cells
        mid = (a + b) / 2
        lace_paths.append(([lace_point(a, 0), lace_point(mid, .45), lace_point(b, 0),
                            lace_point(mid, -.04)], True))
        lace_paths.append(([lace_point(a + (b - a) * i / 16, .45,
                                      .0038 * math.sin(math.pi * i / 16)) for i in range(17)], False))
        for petal in range(4):
            center_a = mid + (petal - 1.5) * .009
            lace_paths.append(([lace_point(center_a + .014 * math.cos(math.tau * i / 12), .62,
                                          .0012 * math.sin(math.tau * i / 12)) for i in range(12)], True))
    curves('Punho ' + label + ' / renda vazada e festonada', lace_paths, .00022, lace_mat, 'lace_' + label)

# Five separately overlapping tabs, using their own isolated photo pieces.
tab_specs = [(-1.00, .21, .630, .609, (594, 1168, 742, 1277)),
             (-.53, .25, .628, .602, (678, 1190, 780, 1273)),
             (0, .32, .624, .586, (755, 1168, 908, 1308)),
             (.53, .25, .628, .602, (886, 1190, 993, 1274)),
             (1.00, .21, .630, .609, (974, 1168, 1088, 1278))]
tab_edges, chain_ends = [], []
for index, (center, halfwidth, upper, lower, box) in enumerate(tab_specs):
    verts, faces, uv = [], [], []
    rows, columns = 18, 32
    for row in range(rows + 1):
        t = row / rows
        for col in range(columns + 1):
            u = col / columns
            theta = center + (u * 2 - 1) * halfwidth * (1 - .12 * t)
            bottom = lower + (.014 if index == 2 else .005) * abs(u * 2 - 1)
            z = upper * (1 - t) + bottom * t
            p = shell(theta, z, .0017 + .004 * t)
            verts.append(p)
            px = box[0] + u * (box[2] - box[0])
            py = box[1] + t * (box[3] - box[1])
            uv.append((px / image.size[0], 1 - py / image.size[1]))
    stride = columns + 1
    for row in range(rows):
        for col in range(columns):
            a = row * stride + col
            faces.append((a, a + 1, a + stride + 1, a + stride))
    role = 'tasset_' + str(index)
    mesh_object('Aba inferior ' + str(index + 1) + ' / painel sobreposto da foto 2', verts, faces, uv, cloth, role, .00055)
    border = ([verts[i] for i in range(stride)]
              + [verts[row * stride + columns] for row in range(1, rows + 1)]
              + [verts[rows * stride + i] for i in range(columns - 1, -1, -1)]
              + [verts[row * stride] for row in range(rows - 1, 0, -1)])
    curves('Aba inferior ' + str(index + 1) + ' / vivo de latao', [(border, True)], .00048, gold, role)
    for theta in (center - halfwidth * .6, center + halfwidth * .6):
        point = shell(theta, upper - .006, .0025)
        circle = [point + Vector((.0015 * math.cos(math.tau * i / 16), 0,
                                  .0015 * math.sin(math.tau * i / 16))) for i in range(16)]
        tab_edges.append((circle, True))
    chain_ends.append(shell(center, lower + .006, .0047))
curves('Abas / ilhoses de fixacao', tab_edges, .00038, gold, 'torso')

chain_paths = []
for start, end in [(chain_ends[0], chain_ends[1]), (chain_ends[3], chain_ends[4])]:
    for i in range(18):
        t = i / 17
        center = start.lerp(end, t) + Vector((0, -.002 * math.sin(math.pi * t), -.006 * math.sin(math.pi * t)))
        chain_paths.append(([center + Vector((.0011 * math.cos(math.tau * j / 12),
                                              .00055 * math.sin(math.tau * j / 12) * (i % 2),
                                              .00075 * math.sin(math.tau * j / 12))) for j in range(12)], True))
curves('Abas / correntes com elos individuais', chain_paths, .00022, gold, 'torso')

# Neck pleats use the isolated trim strip from this same sheet.
for rear in (False, True):
    verts, faces, uv = [], [], []
    for row in range(5):
        for i in range(193):
            t, u = row / 4, i / 192
            theta = -.72 + u * 1.44
            if rear:
                theta = math.pi - theta
            z = neckline(theta) + .0027 * t + .0007 * t * math.cos(u * math.tau * 35)
            verts.append(shell(theta, z, .0008 + .0018 * t + .0006 * math.cos(u * math.tau * 35)))
            uv.append(((601 + u * 450) / image.size[0], 1 - (1029 - t * 32) / image.size[1]))
    for row in range(4):
        for i in range(192):
            a = row * 193 + i
            faces.append((a, a + 1, a + 194, a + 193))
    mesh_object('Decote / tira plissada ' + ('traseira' if rear else 'frontal'), verts, faces, uv, cloth, 'torso', .00025)

    # Raised loops visible along the edge of the original neckline. They have
    # real openings; the narrow pleated strip underneath stays separate.
    neck_lace = []
    for i in range(57):
        theta = -.72 + i * 1.44 / 56
        if rear:
            theta = math.pi - theta
        p = shell(theta, neckline(theta), .0026)
        delta = .0005
        tangent = (shell(theta + delta, neckline(theta + delta))
                   - shell(theta - delta, neckline(theta - delta))).normalized()
        up = Vector((0, 0, 1))
        neck_lace.append(([p + tangent * x + up * z for x, z in
                           [(-.0014, 0), (-.0016, .0026), (-.001, .0043),
                            (.001, .0043), (.0016, .0026), (.0014, 0)]], True))
        neck_lace.append(([p + tangent * (.00055 * math.cos(math.tau * j / 12))
                            + up * (.003 + .0006 * math.sin(math.tau * j / 12))
                            for j in range(12)], True))
    curves('Decote / renda com lacunas ' + ('traseira' if rear else 'frontal'),
           neck_lace, .00020, gold, 'torso')

# Traced filigree from the magnified neckline photograph, not a painted emblem.
filigree_pixels = [
    [(827, 215), (824, 224), (827, 234), (832, 224), (827, 215)],
    [(824, 235), (814, 226), (805, 229), (803, 237), (811, 242), (816, 237), (810, 234)],
    [(831, 235), (843, 227), (851, 230), (853, 239), (845, 244), (841, 239), (847, 235)],
    [(813, 241), (817, 251), (827, 260), (837, 251), (846, 243)],
    [(827, 251), (820, 262), (817, 270), (824, 276), (831, 270), (827, 260), (823, 269)],
    [(827, 251), (835, 262), (839, 270), (832, 276), (824, 270)],
    [(822, 275), (813, 274), (808, 279), (812, 284), (818, 281), (827, 275)],
    [(832, 275), (842, 274), (848, 280), (842, 285), (837, 281), (827, 275)],
    [(827, 276), (831, 288), (827, 299), (823, 288), (827, 276)],
    [(827, 299), (827, 310)],
]
paths = [([front_photo_point(px, py, .0024) for px, py in path], False) for path in filigree_pixels]
curves('Fecho do decote / filigrana tracada da foto 2', paths, .00042, gold, 'torso')

bpy.context.view_layer.update()
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
depsgraph = bpy.context.evaluated_depsgraph_get()
audit = []
for obj in meshes:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    audit.append({'component': obj.name, 'rigRole': obj['rig_role'], 'vertices': len(mesh.vertices),
                  'triangles': len(mesh.loop_triangles), 'rigged': False, 'fidelityVerified': False})
    evaluated.to_mesh_clear()
blend = out / 'chapeleiro_bodice_details.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend))
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:
    obj.select_set(True)
model = out / 'model.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_yup=True, export_apply=True, export_animations=False)
parent_sha = record['modelSha256']
record.update(model=str(model.resolve()), modelSha256=sha(model), editableBlend=str(blend.resolve()),
              editableBlendSha256=sha(blend), geometryParentSha256=parent_sha,
              method='own_layer_2_cuff_lace_tab_and_filigree_refinement_of_new_Tripo',
              status='generated_awaiting_visual_review', detailScriptSha256=sha(__file__),
              componentAudit=audit, photoDetailParts=parts,
              vertices=sum(c['vertices'] for c in audit), triangles=sum(c['triangles'] for c in audit),
              rigPresent=False, countsAsFinishedLayer=False, fidelityVerified=False,
              motionVerified=False, clothCollisionVerified=False, additionalCreditsConsumed=0,
              localWorkStatus='sheet_2_details_created_pending_four_view_and_shared_rig_review',
              limitations=['Tab and cuff construction needs actual four-view comparison with sheet 2.',
                           'Unseen sleeves and internal placement remain inferred from the photo and scan.',
                           'Material colors and roughness are estimated; image lighting is baked in.',
                           'Shared rig, walking, running, jumping, attacking and cloth collisions are not approved.'])
(out / 'generation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print('SHEET_2_DETAILS_CREATED', json.dumps({'components': len(meshes), 'triangles': record['triangles'], 'creditsAdded': 0}))
