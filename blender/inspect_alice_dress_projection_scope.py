"""Review visible garment polygons on the intact weighted character.

No geometry is separated. Current bone ownership and camera-specific garment
contours protect anatomy and hair, then the actual whole-mesh BVH tests occlusion.
The rendered masks must be reviewed before an atlas is baked.
"""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation', required=True)
p.add_argument('--baseline', required=True)
p.add_argument('--output', required=True)
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
g, baseline = read(a.generation), read(a.baseline)
assert baseline['scope'] == 'dress'
assert sha(g['editableBlend']) == g['editableBlendSha256'] == baseline['parentEditableSha256']
assert sha(baseline['geometryFile']) == baseline['geometrySha256']
geometry = np.load(baseline['geometryFile'])
points, triangles = geometry['world_points'], geometry['triangles']
centers = points[triangles].mean(1)
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
scene = bpy.context.scene
whole = bpy.data.objects[baseline['nativeWholeObject']]
mesh = whole.data
assert len(mesh.vertices) == len(points)
groups = {group.index: group.name for group in whole.vertex_groups}
ownership = np.zeros((len(points), 4), np.float32)
for vertex in mesh.vertices:
    for group in vertex.groups:
        name = groups[group.group]
        if name in ['Head', 'HeadTop_End', 'Neck']:
            ownership[vertex.index, 0] += group.weight
        elif 'Hand' in name or 'ForeArm' in name:
            ownership[vertex.index, 1] += group.weight
        elif 'Cloth' in name:
            ownership[vertex.index, 2] += group.weight
        elif name.endswith(('Leg', 'Foot', 'ToeBase', 'Toe_End')):
            ownership[vertex.index, 3] += group.weight
face_owner = ownership[triangles].mean(1)
candidate = ((centers[:, 2] > .18) & (centers[:, 2] < .80) &
             (face_owner[:, 0] < .98) & (face_owner[:, 1] < .55) &
             ((face_owner[:, 2] > .20) | (centers[:, 2] > .56)))
indices = np.flatnonzero(candidate)
print('DRESS_WEIGHT_PROTECTED_CANDIDATES', len(indices), flush=True)

# Coordinates measured from the four actual renders, expressed as fractions
# of the saved portrait frame. These contours restrict paint scope, not mesh shape.
contours = {
    'front': [( .33,.220),(.415,.218),(.435,.270),(.5,.282),(.565,.270),(.582,.218),
              (.665,.220),(.68,.300),(.67,.330),(.60,.334),(.578,.372),(.585,.408),
              (.66,.460),(.71,.535),(.808,.680),(.808,.728),(.193,.728),(.193,.680),
              (.29,.535),(.34,.460),(.415,.408),(.422,.372),(.40,.334),(.322,.330),(.320,.300)],
    'left': [( .477,.225),(.552,.224),(.595,.269),(.605,.320),(.574,.337),
             (.574,.372),(.621,.369),(.667,.457),(.707,.630),(.707,.767),(.645,.767),
             (.636,.727),(.392,.727),(.284,.677),(.290,.606),(.348,.479),(.404,.385),
             (.414,.330),(.399,.281),(.445,.256)],
    'right': [( .445,.225),(.512,.225),(.540,.252),(.588,.281),(.610,.321),
              (.592,.385),(.651,.478),(.707,.606),(.710,.677),(.607,.727),
              (.367,.727),(.356,.767),(.288,.767),(.288,.630),(.327,.457),
              (.378,.369),(.427,.372),(.427,.337),(.406,.320),(.408,.269)],
    'back': [( .332,.223),(.423,.226),(.445,.326),(.557,.326),(.583,.226),
             (.669,.223),(.684,.300),(.669,.329),(.607,.335),(.578,.372),(.588,.412),
             (.659,.460),(.710,.535),(.808,.680),(.808,.758),(.194,.758),(.194,.680),
             (.29,.535),(.341,.46),(.412,.412),(.425,.372),(.395,.335),(.323,.329),(.317,.300)]}

# Some existing shoulder vertices carry large neck influences. Ownership alone
# would wrongly leave the rear puffed sleeves untreated. Actual camera hair
# contours supply the additional semantic protection without editing the rig.
hair_holes = {
    'front': [[(.398,.217),(.455,.216),(.474,.267),(.461,.286),(.426,.280),(.396,.257)],
              [(.548,.216),(.602,.216),(.616,.256),(.581,.285),(.547,.279),(.528,.257)]],
    'left': [[(.560,.219),(.662,.224),(.681,.343),(.579,.357),(.579,.319),(.592,.282)]],
    'right': [[(.339,.224),(.442,.219),(.410,.282),(.425,.319),(.425,.357),(.324,.343)]],
    'back': [[(.413,.218),(.591,.218),(.616,.252),(.600,.294),(.577,.331),
              (.558,.355),(.447,.355),(.425,.331),(.401,.294),(.401,.257)]]}

def inside_polygon(u, v, polygon):
    result = np.zeros(len(u), bool)
    previous = polygon[-1]
    for current in polygon:
        x0, y0 = previous; x1, y1 = current
        if y0 != y1:
            result ^= ((v > min(y0, y1)) & (v <= max(y0, y1)) &
                       (u < x0 + (v - y0) * (x1 - x0) / (y1 - y0)))
        previous = current
    return result

tree = BVHTree.FromPolygons(points.tolist(), triangles.tolist(), all_triangles=True)
views = [row for row in baseline['renders'] if row['kind'] == 'basecolor']
assert [row['view'] for row in views] == ['front', 'left', 'right', 'back']
coverage = np.zeros((4, len(triangles)), bool)
for view_index, row in enumerate(views):
    camera = Matrix(row['cameraWorldMatrix'])
    inverse = np.array(camera.inverted())
    projection = np.array(row['cameraProjectionMatrix'])
    local = centers[indices] @ inverse[:3, :3].T + inverse[:3, 3]
    clip = np.c_[local, np.ones(len(local))] @ projection.T
    uv = clip[:, :2] / clip[:, 3, None] * [.5, -.5] + .5
    within = inside_polygon(uv[:, 0], uv[:, 1], contours[row['view']])
    for hole in hair_holes[row['view']]:
        within &= ~inside_polygon(uv[:, 0], uv[:, 1], hole)
    forward = -(camera.to_3x3() @ Vector((0, 0, 1)))
    for index in np.flatnonzero(within):
        face_index = int(indices[index])
        origin = camera @ Vector((float(local[index, 0]), float(local[index, 1]), 0))
        location, normal, hit, distance = tree.ray_cast(origin, forward, baseline['orthoScale'] * 6)
        if location is not None and (hit == face_index or np.linalg.norm(np.array(location) - centers[face_index]) < 1e-5):
            coverage[view_index, face_index] = True
    print('DRESS_ACTUAL_VISIBLE_FACES', row['view'], int(coverage[view_index].sum()), flush=True)
selected = coverage.any(0)
assert 1000 < int(selected.sum()) < 200000
np.savez_compressed(out / 'visible_dress_faces.npz', polygon_indices=geometry['polygon_indices'][selected],
                    triangle_indices=np.flatnonzero(selected), visible_camera_masks=coverage,
                    candidate_mask=selected, current_vertex_ownership=ownership)
rig = next(obj for obj in scene.objects if obj.type == 'ARMATURE')
rig.animation_data.action = None
for track in rig.animation_data.nla_tracks: track.mute = True
rig.data.pose_position = 'REST'
for bone in rig.pose.bones: bone.matrix_basis = Matrix.Identity(4)
for collection in bpy.data.collections: collection.hide_viewport = collection.hide_render = False
for obj in scene.objects:
    obj.hide_viewport = obj not in (rig, whole)
    obj.hide_render = obj != whole
    obj.hide_set(obj not in (rig, whole))
    for modifier in obj.modifiers:
        if obj != whole: modifier.show_viewport = modifier.show_render = False
scene.frame_set(1)
black = bpy.data.materials.new('Diagnostic only / protected non-dress')
white = bpy.data.materials.new('Diagnostic only / visible dress candidates')
for material, color in [(black, (0., 0., 0., 1.)), (white, (1., 1., 1., 1.))]:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    output = next(node for node in nodes if node.type == 'OUTPUT_MATERIAL')
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = color
    material.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
mesh.materials.clear(); mesh.materials.append(black); mesh.materials.append(white)
polygons = set(geometry['polygon_indices'][selected].tolist())
for polygon in mesh.polygons: polygon.material_index = int(polygon.index in polygons)
data = bpy.data.cameras.new('Actual dress scope review')
data.type = 'ORTHO'; data.ortho_scale = baseline['orthoScale']; data.clip_start = .001
camera = bpy.data.objects.new(data.name, data)
scene.collection.objects.link(camera); scene.camera = camera
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 1
scene.render.resolution_x, scene.render.resolution_y = baseline['resolution']
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = True
scene.view_settings.view_transform = 'Standard'
renders = []
for row in views:
    camera.matrix_world = Matrix(row['cameraWorldMatrix'])
    scene.render.filepath = str(out / (row['view'] + '_dress_mask.png'))
    bpy.ops.render.render(write_still=True)
    renders.append({'view': row['view'], 'file': scene.render.filepath, 'sha256': sha(scene.render.filepath)})
    print('ACTUAL_DRESS_SCOPE_RENDERED', row['view'], flush=True)
rna = bpy.ops.uv.smart_project.get_rna_type()
report = dict(sourceGeneration=str(Path(a.generation).resolve()), sourceBlendSha256=g['editableBlendSha256'],
    baselineFile=str(Path(a.baseline).resolve()), baselineSha256=sha(a.baseline), cameraContours=contours,
    cameraProtectedHairContours=hair_holes,
    selectedTriangles=int(selected.sum()), perCameraVisibleTriangles=coverage.sum(1).tolist(),
    dataFile=str(out / 'visible_dress_faces.npz'), dataSha256=sha(out / 'visible_dress_faces.npz'),
    smartProjectProperties=[prop.identifier for prop in rna.properties], renders=renders,
    scriptSha256=sha(__file__), sourceUnchanged=sha(g['editableBlend']) == g['editableBlendSha256'],
    selectionApproved=False, uvRewriteAnd4kBakePending=True, newGlbOrFbxExported=False, published=False)
(out / 'scope_review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
shutil.copyfile(__file__, out / 'executed_scope_inspection.py')
print('DRESS_SCOPE_REVIEW_COMPLETE', int(selected.sum()), flush=True)
