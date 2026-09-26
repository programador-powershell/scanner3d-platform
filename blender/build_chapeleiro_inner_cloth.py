"""Build new internal petticoat shells using the supplied author's cloth nodes.

The complete exterior is retained as a separate immutable scene object. Only
newly authored internal quad meshes receive Cloth / Post sim cloth modifiers.
This is a construction checkpoint, not finished photo fidelity or game physics.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', required=True)
parser.add_argument('--photo', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
source = json.loads(Path(args.generation).read_text(encoding='utf-8'))
if digest(source['model']) != source['modelSha256']:
    raise ValueError('Changed complete exterior.')
photo_hash = digest(args.photo)
if photo_hash != 'f8cb9734a26e1c78211b12e6a25aa5f56ca64bbc1d3b476e798a49ef5cfe26e4':
    raise ValueError('Expected original Chapeleiro foundation photograph.')
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
if any(out.iterdir()):
    raise ValueError('Use a new checkpoint directory.')
# Keep registered add-on RNA classes alive; loading factory preferences after
# startup invalidates the legacy 3.6 PointerProperty in Blender 5.2.
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
print('BCB_CHECKPOINT scene cleared', flush=True)
import BystedtsClothBuilder as BCB
from BystedtsClothBuilder import simulation
if not hasattr(bpy.types.Scene, 'BCB_props'):
    BCB.register()
print('BCB_CHECKPOINT registered', flush=True)
asset_file = Path(BCB.__file__).parent / 'BCB cloth assets' / 'Human garment assets.blend'
with bpy.data.libraries.load(str(asset_file), link=False) as (available, append):
    append.node_groups = ['Post sim cloth']
post = bpy.data.node_groups['Post sim cloth']
# Original 3.6 asset stores UV as a 3D vector, which is not a UV layer in 5.2.
# Update only the loaded node data in this .blend; vendor zip/code stay intact.
uv_group = bpy.data.node_groups['UV unwrap solidified']
for node in uv_group.nodes:
    if node.bl_idname == 'GeometryNodeStoreNamedAttribute':
        value_links = [(l.from_socket, l.to_socket.name) for l in list(uv_group.links) if l.to_node == node and l.to_socket.name == 'Value']
        node.data_type = 'FLOAT2'
        for socket, name in value_links:
            uv_group.links.new(socket, node.inputs[name])
bpy.ops.import_scene.gltf(filepath=source['model'])
print('BCB_CHECKPOINT exterior imported', flush=True)
exterior = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(exterior) != 1:
    raise ValueError('Expected a whole exterior, without extracted garment studies.')
def mesh_digest(obj):
    coords = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', coords)
    return hashlib.sha256(coords.tobytes()).hexdigest()
outer_hash = mesh_digest(exterior[0])
exterior[0].name = 'Complete Tripo exterior / preserved / toggle to inspect inners'
exterior[0].hide_render = True
scene = bpy.context.scene
scene.render.fps = 30
scene.frame_end = 12
scene.BCB_props.use_triangulate = False  # retain quads; old optional flag removed in 5.x
scene.BCB_props.simulation_frames = 12
scene.BCB_props.sim_quality = 8
scene.BCB_props.collision_quality = 4
scene.BCB_props.collision_distance = .00065
print('BCB_CHECKPOINT properties configured', flush=True)

def cloth_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    shader = nt.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .76
    shader.inputs['Sheen Weight'].default_value = .28
    shader.inputs['Sheen Roughness'].default_value = .6
    uv = nt.nodes.new('ShaderNodeTexCoord')
    weave = nt.nodes.new('ShaderNodeTexNoise')
    weave.inputs['Scale'].default_value = 700
    weave.inputs['Detail'].default_value = 2
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .12
    bump.inputs['Distance'].default_value = .00012
    nt.links.new(uv.outputs['UV'], weave.inputs['Vector'])
    nt.links.new(weave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat
ivory = cloth_material('Foundation / ivory cotton / photo 1', (.58, .49, .36))
black = cloth_material('Foundation / black petticoat / photo 1', (.009, .007, .006))
pieces = []

def shell(name, top, bottom, rx0, ry0, rx1, ry1, folds, amplitude, rings, material):
    around = 144
    vertices = []
    for row in range(rings + 1):
        t = row / rings
        z = top + (bottom - top) * t
        rx = rx0 + (rx1 - rx0) * t ** .8
        ry = ry0 + (ry1 - ry0) * t ** .8
        for col in range(around):
            angle = col / around * 2 * math.pi
            # Gathered folds continue from the pinned waist to the lower ruffle.
            fold = amplitude * (.28 + .72 * t) * math.cos(folds * angle + .2 * math.sin(t * 4))
            ripple = .0012 * t * math.sin(folds * 2 * angle)
            vertices.append(((rx + fold) * math.sin(angle),
                             -(ry + fold * .65) * math.cos(angle), z + ripple))
    faces = []
    for row in range(rings):
        for col in range(around):
            a = row * around + col
            b = row * around + (col + 1) % around
            faces.append((a, b, b + around, a + around))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    mesh.materials.append(material)
    # Explicit rear and panel UV seams are authored on new cloth only.
    sharp = mesh.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    for edge, attr in zip(mesh.edges, sharp.data):
        a, b = edge.vertices
        vertical = a % around == b % around
        attr.value = bool(vertical and a % around % 24 == 0)
        edge.use_seam = attr.value
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    simulation.add_cloth_to_objects(bpy.context, [obj])
    print('BCB_CHECKPOINT cloth added ' + name, flush=True)
    cloth = next(m for m in obj.modifiers if m.type == 'CLOTH')
    cloth.settings.mass = .12
    cloth.settings.tension_stiffness = 35
    cloth.settings.compression_stiffness = 35
    cloth.settings.shear_stiffness = 12
    cloth.settings.bending_stiffness = .8
    cloth.settings.shrink_min = 0
    cloth.settings.shrink_max = 0
    cloth.collision_settings.use_self_collision = True
    cloth.point_cache.frame_start = 1
    cloth.point_cache.frame_end = 12
    pinned = obj.vertex_groups['pinned']
    pinned.add(list(range(around)), 1, 'REPLACE')
    pinned.add(list(range(around, around * 2)), .75, 'REPLACE')
    # Exact original node asset from the supplied zip, with UV datatype upgrade.
    nodes = obj.modifiers.new('BCB / Post sim cloth / internal layers only', 'NODES')
    nodes.node_group = post
    values = {'Separate seams': 0.0, 'Thickness': -.00055, 'Subdiv level': 0,
              'UV unwrap': True, 'UVMap name': 'UVMap', 'Supportive loops offset': 0.0}
    for socket in post.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT' and socket.name in values:
            if bpy.app.version >= (5, 0, 0):
                entry = getattr(nodes.properties.inputs, socket.identifier)
                if 'value' not in entry.bl_rna.properties:
                    raise ValueError('Unsupported node input RNA: ' + str([(p.identifier, p.type) for p in entry.bl_rna.properties]))
                entry.value = values[socket.name]
            else:
                nodes[socket.identifier] = values[socket.name]
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj['originalLayerPhotoSha256'] = photo_hash
    obj['constructedNewInternalLayer'] = True
    pieces.append(obj)
    return obj

shell('01 / ivory inner petticoat / gathered quad shell', .637, .346,
      .062, .042, .173, .107, 36, .0028, 28, ivory)
shell('01 / ivory gathered lower flounce', .354, .307,
      .170, .104, .190, .114, 48, .0032, 10, ivory)
for tier, (top, bottom, rx0, ry0, rx1, ry1) in enumerate([
    (.361, .306, .155, .093, .183, .107),
    (.324, .276, .164, .096, .193, .111),
    (.290, .248, .178, .101, .202, .115)], 1):
    shell(f'01 / black inner petticoat tier {tier}', top, bottom,
          rx0, ry0, rx1, ry1, 48, .003, 10, black)

def evaluated_audit(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    coords = np.asarray([v.co[:] for v in mesh.vertices])
    uv = mesh.uv_layers.get('UVMap')
    uvcoords = np.asarray([d.uv[:] for d in uv.data]) if uv else np.empty((0, 2))
    result = {'name': obj.name, 'baseVertices': len(obj.data.vertices),
              'baseQuads': len(obj.data.polygons), 'evaluatedVertices': len(mesh.vertices),
              'evaluatedPolygons': len(mesh.polygons), 'bounds': [coords.min(axis=0).tolist(), coords.max(axis=0).tolist()],
              'uvMaps': [l.name for l in mesh.uv_layers], 'uvFinite': bool(uv and np.isfinite(uvcoords).all()),
              'uvNonDegenerate': bool(uv and np.ptp(uvcoords[:,0]) > .2 and np.ptp(uvcoords[:,1]) > .2),
              'clothPinGroup': next(m for m in obj.modifiers if m.type == 'CLOTH').settings.vertex_group_mass,
              'postSimNodeGroup': post.name, 'separateSeams': 0, 'thickness': -.00055,
              'rigPresent': False, 'photoFidelityApproved': False}
    evaluated.to_mesh_clear()
    return result
scene.frame_set(1)
audits = [evaluated_audit(obj) for obj in pieces]
if not all(a['uvFinite'] and a['uvNonDegenerate'] and a['evaluatedVertices'] > a['baseVertices'] for a in audits):
    raise ValueError('Actual node evaluation failed to produce thickness and proper UV layers.')
if outer_hash != mesh_digest(exterior[0]):
    raise ValueError('Complete exterior unexpectedly changed.')
editable = out / 'chapeleiro_inner_cloth_builder.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable))
bpy.ops.object.select_all(action='DESELECT')
for obj in pieces:
    obj.select_set(True)
model = out / 'inner_layers.glb'
bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLB', use_selection=True,
                          export_apply=True, export_yup=True, export_animations=False)
report = {'sourcePhoto': args.photo, 'sourcePhotoSha256': photo_hash,
          'variant': 'alice_chapeleiro', 'method': 'new_internal_quad_cloth_from_own_foundation_photo_with_BCB_nodes',
          'reusedGeometry': False, 'modelUpAxis': 'Y', 'status': 'generated_awaiting_visual_review',
          'completeExteriorSha256': source['modelSha256'], 'completeExteriorVerticesUnchanged': True,
          'addon': 'Bystedts Cloth Builder', 'author': 'Daniel Bystedt', 'addonVersion': [1,0,1],
          'originalAssetSha256': digest(asset_file), 'proceduralNodeAsset': post.name,
          'compatibilityAdjustment': 'Loaded UV Store Named Attribute upgraded FLOAT_VECTOR to FLOAT2 for Blender 5.2.',
          'newInternalPieces': audits, 'model': str(model), 'modelSha256': digest(model),
          'editableBlend': str(editable), 'editableBlendSha256': digest(editable),
          'additionalCreditsConsumed': 0, 'allLayersFinished': False, 'fidelityVerified': False,
          'rigPresent': False, 'motionVerified': False, 'clothCollisionVerified': False,
          'limitations': ['Foundation construction study: blouse, corset, bloomers, stockings, garters, lace detail remain pending.',
                         'Gravity settings exist, but animation/collision behavior has not been verified.',
                         'Measurements inferred to fit the intact exterior; compare all views to photo 1.']}
(out / 'cloth_builder_checkpoint.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
(out / 'generation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('NEW_INTERNAL_CLOTH_SAVED', json.dumps(report))
