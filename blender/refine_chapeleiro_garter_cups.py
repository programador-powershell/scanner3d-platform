"""Refine the photographed thigh cups, curved seams and sewn side ribbons.

Keep both cup rims, stockings and the intact exterior unchanged. New details
sample the actual edited cup; unseen rear construction remains inferred.
"""
import argparse, ast, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parent = json.loads(Path(args.parent).read_text(encoding='utf-8'))
for field in ['model', 'editableBlend', 'sourcePhoto']:
    if sha(parent[field]) != parent[field + 'Sha256']:
        raise ValueError('Changed parent evidence: ' + field)
if parent['sourcePhotoSha256'] != 'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Require the unchanged original foundation photo.')
out = Path(args.output)
if out.exists():
    raise ValueError('Use a new modeling checkpoint; preserve earlier reviews.')
out.mkdir(parents=True)
for dependency in parent.get('editableLibraryDependencies', []):
    source = Path(parent['editableBlend']).parent / dependency['file']
    if sha(source) != dependency['sha256']:
        raise ValueError('The intact master library changed.')
    shutil.copyfile(source, out / dependency['file'])
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene = bpy.context.scene
scene.frame_set(1)

def cage_hash(obj):
    values = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get('co', values)
    return hashlib.sha256(values.tobytes() + json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()

inherited = [o for o in scene.objects if o.type == 'MESH' and o.get('constructedNewInternalLayer')]
before = {o.name: cage_hash(o) for o in scene.objects if o.type == 'MESH'}
disabled = []
for obj in scene.objects:
    for modifier in obj.modifiers:
        if modifier.show_viewport:
            disabled.append(modifier)
            modifier.show_viewport = False
ivory = bpy.data.materials['Foundation / warm ivory cotton']
post = bpy.data.node_groups[parent['proceduralNodeAsset']]
new, temporarily_disabled, physics_carriers = [], [], {}
helper = Path(__file__).with_name('refine_chapeleiro_foundation_blouse.py')
names = {'mesh_object', 'parent_to', 'post_modifier', 'surface_follow', 'sleeve_faces', 'tube'}
body = [n for n in ast.parse(helper.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name in names]
if {n.name for n in body} != names:
    raise ValueError('Changed own construction helper interface.')
exec(compile(ast.Module(body=body, type_ignores=[]), str(helper), 'exec'), globals())

def tube_positions(points, radius, sides=8):
    vertices = []
    for row, point in enumerate(points):
        tangent = (points[min(row + 1, len(points) - 1)] - points[max(0, row - 1)]).normalized()
        side = tangent.cross(Vector((0, 1, 0)))
        if side.length < .001:
            side = tangent.cross(Vector((1, 0, 0)))
        side.normalize()
        other = tangent.cross(side).normalized()
        vertices.extend(point + radius * (side * math.cos(c / sides * math.tau) + other * math.sin(c / sides * math.tau)) for c in range(sides))
    return vertices

def rebind(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for modifier in obj.modifiers:
        if modifier.type == 'SURFACE_DEFORM':
            modifier.show_viewport = True
            if modifier.is_bound:
                bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
            bpy.ops.object.surfacedeform_bind(modifier=modifier.name)
            if not modifier.is_bound:
                raise ValueError('Actual edited cup attachment failed: ' + obj.name)

allowed, constructions = set(), []
for label in ['left', 'right']:
    cup = bpy.data.objects[f'01 / {label} garter / pointed thigh reinforcement']
    stocking = bpy.data.objects[f'01 / {label} stocking / fitted leg ankle and closed toe']
    target = bpy.data.objects[stocking['skinCage']]
    physics_carriers[stocking.name] = target
    for modifier in target.modifiers:
        modifier.show_viewport = True
        if modifier.type == 'TRIANGULATE':
            modifier.quad_method = 'FIXED'
    if len(cup.data.vertices) != 96 * 15:
        raise ValueError('Unexpected actual cup quad topology.')
    raw = np.asarray([v.co[:] for v in cup.data.vertices])
    edited = raw.copy()
    def panel_angle(t):
        return .58 - .40 * t + .08 * math.sin(math.pi * t)
    for row in range(1, 14):
        t = row / 14
        envelope = math.sin(math.pi * t)
        for column in range(96):
            angle = column / 96 * math.tau
            signed = (angle + math.pi) % math.tau - math.pi
            front = max(0., math.cos(angle))
            volume = .0028 * envelope * front ** 2 + .00035 * envelope * (1 - front)
            wrinkle = .00018 * envelope * math.sin(angle * 31 + 1.5 * t) * (1 - .65 * front)
            darts = 0.
            for direction in [-1, 1]:
                delta = signed - direction * panel_angle(t)
                darts += envelope * (.00030 * math.exp(-(delta / .048) ** 2) - .00017 * math.exp(-((delta - direction * .06) / .035) ** 2))
            edited[row * 96 + column] += np.asarray([math.sin(angle), -math.cos(angle), 0]) * (volume + wrinkle + darts)
    if not np.array_equal(edited[:96], raw[:96]) or not np.array_equal(edited[-96:], raw[-96:]):
        raise ValueError('The sewn cup rims must remain fixed.')
    cup.data.vertices.foreach_set('co', edited.astype(np.float32).ravel())
    cup.data.update()
    rebind(cup)
    allowed.add(cup.name)
    def sample(u, t, offset=.00028):
        index = (u % 1) * 96
        col = int(index)
        row_index = min(14., max(0., t * 14))
        row = min(13, int(row_index))
        a = Vector(edited[row * 96 + col]).lerp(Vector(edited[row * 96 + (col + 1) % 96]), index - col)
        b = Vector(edited[(row + 1) * 96 + col]).lerp(Vector(edited[(row + 1) * 96 + (col + 1) % 96]), index - col)
        return a.lerp(b, row_index - row) + Vector((math.sin(u * math.tau), -math.cos(u * math.tau), 0)) * offset
    # Preserve the two existing center stitches' topology and UVs while moving
    # their actual thread vertices onto the edited fabric, then bind anew.
    for delta in [-.003, .003]:
        stitch = bpy.data.objects[f'01 / {label} garter / cup front stitch {delta}']
        points = [sample(delta, row / 24, .00046) for row in range(25)]
        values = np.asarray([p[:] for p in tube_positions(points, .00032)], np.float32)
        if len(values) != len(stitch.data.vertices):
            raise ValueError('Changed center stitch topology.')
        stitch.data.vertices.foreach_set('co', values.ravel())
        stitch.data.update()
        rebind(stitch)
        allowed.add(stitch.name)
    def attach(obj, thickness=None):
        surface_follow(obj, cup, stocking)
        if thickness is not None:
            post_modifier(obj, thickness)
        obj['garterOwnPhotoDetail'] = True
        return obj
    def cuff_t(u):
        return .0048 / (sample(u, 0).z - sample(u, 1).z)
    points = [sample(c / 96, cuff_t(c / 96) * r / 4, .00042) for r in range(5) for c in range(96)]
    cuff = attach(mesh_object(f'01 / {label} garter / narrow top facing band', points,
        [f[::-1] for f in sleeve_faces(96, 4)], 'foundation_garter_trim'), -.00018)
    for edge in [0, 1]:
        rail = [sample(c / 128, cuff_t(c / 128) * edge, .00058) for c in range(129)]
        attach(tube(f'01 / {label} garter / top facing stitch {edge}', rail, .00018, role='foundation_garter_trim'))
    for direction in [-1, 1]:
        rail = [sample(direction * panel_angle(r / 36) / math.tau, r / 36, .00038) for r in range(37)]
        attach(tube(f'01 / {label} garter / curved panel seam {direction}', rail, .00022, role='foundation_garter_trim'))
    # Visible sewing dashes are closed real thread geometry, not an alpha plane.
    vertices, faces = [], []
    for direction in [-1, 1]:
        for repeat in range(20):
            start = .05 + .90 * repeat / 20
            points = [sample(direction * (panel_angle(t) + .018) / math.tau, t, .00064)
                      for t in [start + .022 * r / 4 for r in range(5)]]
            offset = len(vertices)
            vertices.extend(tube_positions(points, .00012, 6))
            faces.extend(tuple(offset + i for i in face) for face in sleeve_faces(6, 4))
            faces.extend([tuple(offset + i for i in range(5, -1, -1)), tuple(offset + 24 + i for i in range(6))])
    threads = attach(mesh_object(f'01 / {label} garter / curved seam sewing threads', vertices, faces, 'foundation_garter_trim'))
    uv = threads.data.uv_layers.new(name='UVMap')
    for polygon in threads.data.polygons:
        for loop in polygon.loop_indices:
            index = threads.data.loops[loop].vertex_index % 30
            if len(polygon.vertices) == 6:
                angle = (index % 6) / 6 * math.tau
                uv.data[loop].uv = (.5 + .5 * math.cos(angle), .5 + .5 * math.sin(angle))
            else:
                uv.data[loop].uv = ((index % 6) / 6, (index // 6) / 4)
    threads['actualSewingDashes'] = 40
    # Sewn outboard bows: two flat folded wings, a wrapped knot and two tails.
    u = .195 if label == 'left' else .805
    angle = u * math.tau
    normal = Vector((math.sin(angle), -math.cos(angle), 0))
    transverse = Vector((math.cos(angle), math.sin(angle), 0))
    vertical = Vector((0, 0, 1))
    center = sample(u, .70, .0010)
    def ribbon(name, position, rows=28):
        values = [position(r / rows, c / 4 - .5) for r in range(rows + 1) for c in range(5)]
        ribbon_faces = [(r * 5 + c, r * 5 + c + 1, (r + 1) * 5 + c + 1, (r + 1) * 5 + c) for r in range(rows) for c in range(4)]
        # Align the fabric face with the outboard surface, keeping GN thickness inward.
        a, b, c = (values[i] for i in ribbon_faces[len(ribbon_faces) // 2][:3])
        if (b - a).cross(c - a).dot(normal) < 0:
            ribbon_faces = [f[::-1] for f in ribbon_faces]
        return attach(mesh_object(name, values, ribbon_faces, 'foundation_garter_ribbon'), -.00016)
    for direction in [-1, 1]:
        def wing(t, width, direction=direction):
            return (center + transverse * direction * (.001 + .0085 * math.sin(math.pi * t))
                    + normal * (.0004 + .0028 * math.sin(math.pi * t) ** 2)
                    + vertical * (.0017 * math.sin(math.tau * t) + width * .0054 * (.45 + .55 * math.sin(math.pi * t)))
                    + normal * .00045 * math.cos(width * math.tau) * math.sin(math.pi * t))
        ribbon(f'01 / {label} garter / side bow folded wing {direction}', wing)
        def tail(t, width, direction=direction):
            return (center + transverse * (direction * (.0012 + .0026 * t) + width * .0046 * (1 - .10 * t))
                    + vertical * (-.001 - (.027 if direction == 1 else .023) * t)
                    + normal * (.001 + .002 * math.sin(math.pi * t) + .0016 * t ** 3
                                + .00055 * math.cos(width * math.tau + t * 2) * math.sin(math.pi * t)))
        ribbon(f'01 / {label} garter / side bow hanging ribbon {direction}', tail)
    def knot(t, width):
        theta = t * math.tau
        return center + vertical * (.0018 * math.cos(theta)) + normal * (.0005 + .0015 * math.sin(theta)) + transverse * (width * .0027)
    ribbon(f'01 / {label} garter / side bow wrapped knot', knot, 32)
    cup['ownPhotoRoundedCupRefinement'] = True
    cup['originalCupRimsPreserved'] = True
    constructions.append({'mesh': cup.name, 'skinCage': target.name, 'rawVertices': len(edited),
        'topAndPointedHemVerticesUnchanged': True, 'maximumRawDisplacement': float(np.linalg.norm(edited - raw, axis=1).max()),
        'centerStitchesRepositionedAndRebound': True, 'curvedPanelSeams': 2, 'actualSewingDashes': 40,
        'topFacingWidth': .0048, 'sideBowFoldedWings': 2, 'sideBowHangingRibbons': 2,
        'detailSampledFromActualEditedCup': True, 'rearConstructionInferred': True,
        'sharedRigVerified': False, 'motionVerified': False, 'collisionVerified': False})
    print('ACTUAL_GARTER_CUP_REFINED', json.dumps(constructions[-1]), flush=True)

for modifier in disabled + temporarily_disabled:
    modifier.show_viewport = True
scene.frame_set(1)
changed = [name for name, digest in before.items() if cage_hash(bpy.data.objects[name]) != digest]
if set(changed) != allowed:
    raise ValueError('Unexpected changed raw meshes: ' + str(set(changed) ^ allowed))
pieces = []
deps = bpy.context.evaluated_depsgraph_get()
for obj in inherited + new:
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    uv = mesh.uv_layers.get('UVMap')
    if not uv or not np.isfinite(np.asarray([d.uv[:] for d in uv.data])).all():
        raise ValueError('Actual refined garment UVs failed: ' + obj.name)
    piece = {'name': obj.name, 'role': obj['role'], 'baseVertices': len(obj.data.vertices), 'basePolygons': len(obj.data.polygons),
        'evaluatedVertices': len(mesh.vertices), 'triangles': len(mesh.loop_triangles), 'uvMaps': [u.name for u in mesh.uv_layers],
        'uvFinite': True, 'parent': obj.parent.name if obj.parent else None,
        'surfaceDeformBindings': [{'target': m.target.name, 'bound': m.is_bound} for m in obj.modifiers if m.type == 'SURFACE_DEFORM'],
        'rigPresent': False, 'fidelityVerified': False}
    if obj.get('opaqueGeometryApertures'):
        piece.update(actualGeometricApertures=True, traceRepeats=obj['traceRepeats'], traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):
        piece['actualThreadLoops'] = obj['actualThreadLoops']
    if obj.get('actualSewingDashes'):
        piece['actualSewingDashes'] = obj['actualSewingDashes']
    pieces.append(piece)
    evaluated.to_mesh_clear()
for library in bpy.data.libraries:
    library.filepath = '//' + Path(bpy.path.abspath(library.filepath)).name
editable = out / 'chapeleiro_foundation_garter_cups.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable), compress=True, relative_remap=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited + new:
    obj.select_set(True)
model = out / 'foundation_garter_cups.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True, export_apply=True,
                         export_yup=True, export_animations=False)
report = {**parent, 'method': 'own_photo_rounded_garter_cups_curved_seams_and_sewn_side_bows',
    'model': str(model.resolve()), 'modelSha256': sha(model), 'editableBlend': str(editable.resolve()), 'editableBlendSha256': sha(editable),
    'parentGeneration': str(Path(args.parent).resolve()), 'parentGenerationSha256': sha(args.parent), 'pieces': pieces,
    'existingCagesUnchanged': False, 'untouchedRawMeshesUnchanged': True, 'changedExistingRawMeshes': changed,
    'garterCupConstruction': constructions, 'ownHelperSources': [{'file': str(helper.resolve()), 'sha256': sha(helper)}],
    'inheritedInternalPieces': len(inherited), 'addedInternalPieces': len(new), 'refinedInternalPieces': 2,
    'completeExteriorVerticesUnchanged': True, 'allLayersFinished': False, 'rigPresent': False, 'fidelityVerified': False,
    'motionVerified': False, 'clothCollisionVerified': False, 'additionalCreditsConsumed': 0, 'nextVariantMayStart': False}
(out / 'generation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('GARTER_CUP_CHECKPOINT_SAVED', json.dumps({'pieces': len(pieces), 'addedPieces': len(new), 'changedRawMeshes': changed,
    'triangles': sum(p['triangles'] for p in pieces), 'exteriorUnchanged': True}), flush=True)
