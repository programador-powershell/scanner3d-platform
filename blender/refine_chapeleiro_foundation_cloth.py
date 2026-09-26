"""Author foundation cloth and physical lace without cutting the complete outfit.

The supplied Bystedt node asset supplies evaluated thickness and automatic UV.
Photo-traced lace has actual geometric apertures and follows its cloth carrier.
This checkpoint is not a finished garment, motion rig, or collision approval.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--whole', required=True)
parser.add_argument('--lace', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
whole = json.loads(Path(args.whole).read_text(encoding='utf-8'))
trace = json.loads(Path(args.lace).read_text(encoding='utf-8'))
for field in ['model', 'editableBlend']:
    if sha(whole[field]) != whole[field + 'Sha256']:
        raise ValueError('The whole-outfit checkpoint changed.')
if sha(trace['sourcePhoto']) != trace['sourcePhotoSha256']:
    raise ValueError('The original foundation photograph changed.')
out = Path(args.output)
if out.exists():
    raise ValueError('Choose a new checkpoint directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=whole['editableBlend'])
scene = bpy.context.scene
exterior = [o for o in scene.objects if o.type == 'MESH']
if len(exterior) != 1:
    raise ValueError('Expected the single preserved whole dressed character.')
exterior = exterior[0]
def geometry_hash(obj):
    array = np.empty(len(obj.data.vertices)*3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', array)
    return hashlib.sha256(array.tobytes()).hexdigest()
exterior_hash = geometry_hash(exterior)
exterior.hide_render = True
exterior.name = 'Complete baked Tripo outfit / preserved / hidden for internal review'
import BystedtsClothBuilder as BCB
from BystedtsClothBuilder import simulation
if not hasattr(bpy.types.Scene, 'BCB_props'):
    BCB.register()
asset = Path(BCB.__file__).parent / 'BCB cloth assets' / 'Human garment assets.blend'
with bpy.data.libraries.load(str(asset), link=False) as (_, loaded):
    loaded.node_groups = ['Post sim cloth']
post = bpy.data.node_groups['Post sim cloth']
uv_group = bpy.data.node_groups['UV unwrap solidified']
for node in uv_group.nodes:
    if node.bl_idname == 'GeometryNodeStoreNamedAttribute':
        links = [l.from_socket for l in uv_group.links if l.to_node == node and l.to_socket.name == 'Value']
        node.data_type = 'FLOAT2'
        for source_socket in links:
            uv_group.links.new(source_socket, node.inputs['Value'])
scene.render.fps = 30
scene.frame_end = 24
scene.BCB_props.use_triangulate = False
scene.BCB_props.simulation_frames = 24
scene.BCB_props.sim_quality = 12
scene.BCB_props.collision_quality = 5
scene.BCB_props.collision_distance = .00065
pieces, carriers, audits = [], [], []

def image_array(name, array, color=False):
    image = bpy.data.images.new(name, width=array.shape[1], height=array.shape[0], alpha=True)
    image.colorspace_settings.name = 'sRGB' if color else 'Non-Color'
    rgba = np.ones((*array.shape[:2], 4), dtype=np.float32)
    rgba[:,:,:3] = array
    image.pixels.foreach_set(np.flipud(rgba).ravel())
    image.filepath_raw = str(out / (name.replace(' ', '_') + '.png'))
    image.file_format = 'PNG'
    image.save()
    image.pack()
    return image

size = 1024
yy, xx = np.mgrid[:size,:size] / size
warp = np.sin(xx * math.tau * 128)
weft = np.sin(yy * math.tau * 128)
height = .15 * warp + .15 * weft + .10 * warp * weft
dy, dx = np.gradient(height)
normal = np.stack([-dx*1.4, dy*1.4, np.ones_like(height)], axis=2)
normal /= np.linalg.norm(normal,axis=2)[:,:,None]
weave_normal = image_array('Foundation cotton weave normal', normal*.5+.5)
def cotton(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .78
    # The bundled glTF exporter ignores an unlinked Sheen Weight when deriving
    # the tint factor. Avoid exporting white full-strength sheen on dark cloth.
    shader.inputs['Sheen Weight'].default_value = 0
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = weave_normal
    bump = mat.node_tree.nodes.new('ShaderNodeNormalMap')
    bump.inputs['Strength'].default_value = .10
    mat.node_tree.links.new(tex.outputs['Color'], bump.inputs['Color'])
    mat.node_tree.links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return mat
ivory = cotton('Foundation / warm ivory cotton', (.52,.435,.322))
black = cotton('Foundation / black cotton', (.0016,.0013,.0011))
metal = bpy.data.materials.new('Foundation / aged brass eyelets and busk')
metal.use_nodes = True
metal.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.23,.15,.065,1)
metal.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = .82
metal.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .42

def object_mesh(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj['originalLayerPhotoSha256'] = trace['sourcePhotoSha256']
    obj['constructedNewInternalLayer'] = True
    pieces.append(obj)
    return obj

def post_modifier(obj, thickness):
    mod = obj.modifiers.new('Bystedt / Post sim cloth / new internal surface', 'NODES')
    mod.node_group = post
    values = {'Separate seams': 0., 'Thickness': thickness, 'Subdiv level': 0,
              'UV unwrap': True, 'UVMap name': 'UVMap', 'Supportive loops offset': 0.}
    for socket in post.interface.items_tree:
        if socket.item_type == 'SOCKET' and socket.in_out == 'INPUT' and socket.name in values:
            if bpy.app.version >= (5,0,0):
                getattr(mod.properties.inputs, socket.identifier).value = values[socket.name]
            else:
                mod[socket.identifier] = values[socket.name]
    return mod

def prepare_cloth(obj, around, rows, thickness=-.00045, sim=True):
    sharp = obj.data.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    for edge, value in zip(obj.data.edges, sharp.data):
        a,b = edge.vertices
        value.value = a%around == b%around and a%around%(around//8) == 0
        edge.use_seam = value.value
    if sim:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        simulation.add_cloth_to_objects(bpy.context, [obj])
        cloth = next(m for m in obj.modifiers if m.type == 'CLOTH')
        cloth.settings.mass = .12
        cloth.settings.tension_stiffness = 35
        cloth.settings.compression_stiffness = 35
        cloth.settings.shear_stiffness = 12
        cloth.settings.bending_stiffness = .6
        cloth.settings.shrink_min = cloth.settings.shrink_max = 0
        cloth.collision_settings.use_self_collision = True
        cloth.point_cache.frame_start = 1
        cloth.point_cache.frame_end = 24
        obj.vertex_groups['pinned'].add(list(range(around)), 1, 'REPLACE')
        obj.vertex_groups['pinned'].add(list(range(around, around*2)), .7, 'REPLACE')
        carriers.append(obj)
    post_modifier(obj, thickness)

def irregular(theta, t, count, amplitude, phase=0):
    # Broad drapes, unequal gather spacing and small secondary fabric wrinkles.
    phase_shift = .31*math.sin(theta*3+.4)+.17*math.sin(theta*7+1.1)
    strength = .8+.2*math.sin(theta*5+.6)
    return amplitude*strength*((.25+.75*t)*math.cos(count*theta+phase_shift+phase+t*.5)
                              +.22*t*math.sin((count*2+3)*theta+t*1.8))

def skirt(name, top, bottom, rx0, ry0, rx1, ry1, mat, count=22, amplitude=.0042, rows=32, phase=0):
    around = 192
    def position(u,v, outward=0):
        theta = u*math.tau
        t = max(0,min(1,v))
        progress = t**.87
        fold = irregular(theta,t,count,amplitude,phase)
        rx = rx0+(rx1-rx0)*progress+fold+outward
        ry = ry0+(ry1-ry0)*progress+fold*.72+outward
        z = top+(bottom-top)*t+.0015*t*math.sin(theta*9+.7)*math.sin(theta*13)
        return (rx*math.sin(theta),-ry*math.cos(theta),z)
    vertices = [position(col/around,row/rows) for row in range(rows+1) for col in range(around)]
    faces = []
    for row in range(rows):
        for col in range(around):
            a = row*around+col
            b = row*around+(col+1)%around
            faces.append((a,b,b+around,a+around))
    obj = object_mesh(name,vertices,faces,mat)
    prepare_cloth(obj,around,rows)
    print('FOUNDATION_CARRIER',name,flush=True)
    obj['role'] = 'internal_petticoat'
    obj['attachment'] = 'waist carrier' if top>.6 else 'sewn ruffle on internal waist carrier'
    return obj, position

main, _ = skirt('01 / long ivory gathered petticoat',.637,.399,.063,.043,.173,.105,ivory,
                count=22,amplitude=.0045,rows=36)
flounce, ivory_position = skirt('01 / ivory lower gathered flounce',.408,.360,.172,.104,.187,.113,ivory,
                              count=43,amplitude=.0038,rows=12,phase=.37)
# Full support cloth connects all three dark tiers to the waist. It is not a
# replacement or extraction of the existing complete exterior dress.
support, _ = skirt('01 / black petticoat continuous waist support',.633,.282,.062,.041,.189,.109,black,
                  count=23,amplitude=.0033,rows=38,phase=1)
tier_parameters = [(.351,.326,.158,.094,.189,.110),
                   (.316,.294,.171,.100,.196,.114),
                   (.282,.263,.182,.105,.203,.118)]
black_tiers = []
for index,p in enumerate(tier_parameters,1):
    obj,position = skirt(f'01 / black gathered flounce {index}',*p,black,count=43,
                        amplitude=.0037,rows=12,phase=index*.63)
    black_tiers.append((obj,position))

def attach_flounce(obj, target):
    # Sewn gather roots must follow an actual waist-connected support. A pinned
    # ring in world space would float when the character moves. Evaluate the
    # carrier before Cloth, and use its animated geometry for the pinned roots.
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    transform=obj.matrix_world.copy()
    obj.parent=target
    obj.matrix_parent_inverse=target.matrix_world.inverted()
    obj.matrix_world=transform
    attachment = obj.modifiers.new('Sewn ruffle follows continuous waist support','SURFACE_DEFORM')
    attachment.target = target
    while list(obj.modifiers).index(attachment) > 0:
        bpy.ops.object.modifier_move_up(modifier=attachment.name)
    bpy.ops.object.surfacedeform_bind(modifier=attachment.name)
    if not attachment.is_bound:
        raise ValueError('Ruffle attachment failed: '+obj.name)
    next(m for m in obj.modifiers if m.type=='CLOTH').settings.use_dynamic_mesh = True
    obj['attachment'] = 'Bound to '+target.name+' before Cloth; dynamic pinned roots'
    obj['actualClothCarrier'] = target.name
    print('FOUNDATION_RUFFLE_ATTACHED',obj.name,target.name,flush=True)

attach_flounce(flounce,main)
for obj,_ in black_tiers:
    attach_flounce(obj,support)

lace_materials = {}
def lace_material(tile):
    if tile['name'] in lace_materials:
        return lace_materials[tile['name']]
    if sha(tile['crop']) != tile['cropSha256']:
        raise ValueError('Photo lace crop changed.')
    mat = bpy.data.materials.new('Photo 1 / '+tile['name']+' lace / opaque actual holes')
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Roughness'].default_value = .76
    shader.inputs['Sheen Weight'].default_value = 0
    uv = mat.node_tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'PhotoLaceUV'
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(tile['crop'], check_existing=True)
    tex.image.pack()
    mat.node_tree.links.new(uv.outputs['UV'],tex.inputs['Vector'])
    mat.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
    pixels = np.empty(len(tex.image.pixels),dtype=np.float32)
    tex.image.pixels.foreach_get(pixels)
    rgb = np.flipud(pixels.reshape(tile['height'],tile['width'],4)[:,:,:3])
    dy,dx = np.gradient(rgb.mean(axis=2))
    normals = np.stack([-dx*.65,dy*.65,np.ones_like(dx)],axis=2)
    normals /= np.linalg.norm(normals,axis=2)[:,:,None]
    normal_image = image_array('Foundation '+tile['name']+' lace normal',normals*.5+.5)
    normal_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    normal_tex.image = normal_image
    bump = mat.node_tree.nodes.new('ShaderNodeNormalMap')
    bump.uv_map = 'PhotoLaceUV'
    bump.inputs['Strength'].default_value = .5
    mat.node_tree.links.new(uv.outputs['UV'],normal_tex.inputs['Vector'])
    mat.node_tree.links.new(normal_tex.outputs['Color'],bump.inputs['Color'])
    mat.node_tree.links.new(bump.outputs['Normal'],shader.inputs['Normal'])
    lace_materials[tile['name']] = mat
    return mat

def flat_trace(tile):
    vertices,edges=[],[]
    for contour in tile['contours']:
        offset=len(vertices)
        vertices.extend(Vector((x/(tile['width']-1),1-y/(tile['height']-1)))
                        for x,y in contour['points'])
        edges.extend((offset+i,offset+(i+1)%len(contour['points']))
                     for i in range(len(contour['points'])))
    # Keep contour edges constrained, then select the material side using the
    # original binary trace. Legacy curve filling may fill the wrong islands.
    vertices,_,triangles,*_=delaunay_2d_cdt(vertices,edges,[],0,1e-7,False)
    mask=bpy.data.images.load(tile['mask'],check_existing=True)
    pixels=np.empty(len(mask.pixels),dtype=np.float32)
    mask.pixels.foreach_get(pixels)
    pixels=pixels.reshape(tile['height'],tile['width'],4)
    faces=[]
    for triangle in triangles:
        center=sum((vertices[i] for i in triangle),Vector((0,0)))/len(triangle)
        x=max(0,min(tile['width']-1,round(center.x*(tile['width']-1))))
        y=max(0,min(tile['height']-1,round(center.y*(tile['height']-1))))
        if pixels[y,x,0]>.5:
            faces.append(triangle)
    mesh=bpy.data.meshes.new('temporary lace contour triangulation')
    mesh.from_pydata([(v.x,v.y,0) for v in vertices],[],faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(mesh)
    bm.free()
    vertices = [v.co.copy() for v in mesh.vertices]
    faces = [tuple(p.vertices) for p in mesh.polygons]
    bpy.data.meshes.remove(mesh)
    if not faces:
        raise ValueError('Lace contour fill failed.')
    return vertices,faces

def lace_band(name, carrier, position, tile, repeats, length):
    base, polygons = flat_trace(tile)
    vertices, faces, uv_faces = [], [], []
    # Continue the cloth's fold field into the lace. The carrier's final row is
    # the attachment seam; no planar cards or alpha-only holes are exported.
    def map_vertex(u,v):
        top = Vector(position(u,1,.00045))
        below = Vector(position(u,.96,.00045))
        direction = (top-below).normalized()
        return tuple(top+direction*(1-v)*length)
    for repeat in range(repeats):
        offset = len(vertices)
        vertices.extend(map_vertex((repeat+v.x)/repeats,v.y) for v in base)
        faces.extend(tuple(offset+i for i in poly) for poly in polygons)
        uv_faces.extend([[(base[i].x,base[i].y) for i in poly] for poly in polygons])
    obj = object_mesh(name,vertices,faces,lace_material(tile))
    transform=obj.matrix_world.copy()
    obj.parent=carrier
    obj.matrix_parent_inverse=carrier.matrix_world.inverted()
    obj.matrix_world=transform
    layer = obj.data.uv_layers.new(name='PhotoLaceUV')
    for poly,uvs in zip(obj.data.polygons,uv_faces):
        for loop,uv in zip(poly.loop_indices,uvs):
            layer.data[loop].uv = uv
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    follow = obj.modifiers.new('Lace follows actual internal cloth carrier','SURFACE_DEFORM')
    follow.target = carrier
    print('FOUNDATION_LACE_BIND',name,len(vertices),flush=True)
    bpy.ops.object.surfacedeform_bind(modifier=follow.name)
    if not follow.is_bound:
        raise ValueError('Detailed lace must be bound to its actual cloth carrier.')
    post_modifier(obj,-.00020)
    obj['role'] = 'internal_photographic_lace'
    obj['opaqueGeometryApertures'] = True
    obj['sourceCrop'] = json.dumps(tile['sourcePhotoCrop'])
    obj['traceHolesPerRepeat'] = tile['retainedHoles']
    obj['traceRepeats'] = repeats
    obj['carrier'] = carrier.name
    obj['attachment'] = 'Surface Deform bound; rig and game cloth validation pending'
    print('FOUNDATION_LACE_BOUND',name,flush=True)
    return obj

ivory_tile,black_tile = trace['tiles']
lace_band('01 / ivory scalloped floral lace / real apertures',flounce,ivory_position,ivory_tile,18,.028)
for index,(obj,position) in enumerate(black_tiers,1):
    lace_band(f'01 / black floral lace tier {index} / real apertures',obj,position,black_tile,16,.030)

def tube(name, points, radius, mat, sides=6):
    vertices=[]
    for index,point in enumerate(points):
        point=Vector(point)
        tangent=Vector(points[min(index+1,len(points)-1)])-Vector(points[max(0,index-1)])
        tangent.normalize()
        side=tangent.cross(Vector((0,1,0)))
        if side.length<.001:
            side=tangent.cross(Vector((1,0,0)))
        side.normalize()
        other=tangent.cross(side).normalized()
        for col in range(sides):
            angle=col/sides*math.tau
            vertices.append(tuple(point+radius*(side*math.cos(angle)+other*math.sin(angle))))
    faces=[tuple(range(sides-1,-1,-1))]
    for row in range(len(points)-1):
        for col in range(sides):
            a=row*sides+col
            b=row*sides+(col+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple((len(points)-1)*sides+col for col in range(sides)))
    obj=object_mesh(name,vertices,faces,mat)
    uv=obj.data.uv_layers.new(name='UVMap')
    for poly in obj.data.polygons:
        for loop in poly.loop_indices:
            index=obj.data.loops[loop].vertex_index
            col=index%sides
            uv.data[loop].uv=(col/sides,(index//sides)/max(1,len(points)-1))
    obj['role']='corset_structural_detail'
    return obj

# Tailored boned foundation corset from the same photo, with a front point,
# raised boning channels, front busk and actual back eyelets/lacing.
around,rows=128,24
def corset_pos(u,t,offset=0):
    theta=u*math.tau
    front=max(0,math.cos(theta))
    bottom=.625-.030*front**4
    top=.732-.016*abs(math.sin(theta))
    z=top+(bottom-top)*t
    bulge=(abs(t-.56)/(.56 if t<=.56 else .44))**1.8
    rx=.055+.023*bulge+offset
    ry=.039+.014*bulge+offset
    front_point_overlap=.012*front**4*t**3
    return (rx*math.sin(theta),-ry*math.cos(theta)-front_point_overlap,z)
vertices=[corset_pos(col/around,row/rows) for row in range(rows+1) for col in range(around)]
faces=[]
for row in range(rows):
    for col in range(around):
        a=row*around+col;b=row*around+(col+1)%around
        faces.append((a,b,b+around,a+around))
corset=object_mesh('01 / ivory fitted boned corset / pointed front',vertices,faces,ivory)
prepare_cloth(corset,around,rows,thickness=-.00065,sim=False)
corset['role']='boned_foundation_corset'
for index in range(14):
    u=index/14
    for edge in [-1,1]:
        tube(f'01 / corset boning channel {index:02d} edge {edge}',
             [corset_pos(u+edge*.0018,t/32,.0007) for t in range(33)],.00036,ivory)
for t in [0,1]:
    tube('01 / corset bound '+('upper' if t==0 else 'lower')+' edge',
         [corset_pos(i/192,t,.0007) for i in range(193)],.00065,ivory)
for index in range(6):
    z=.714-index*.0165
    t=(.732-z)/(.732-.595)
    center=Vector(corset_pos(0,t,.001))
    tube(f'01 / brass busk hook {index}',
         [tuple(center+Vector((.0028+math.cos(k/12*math.pi)*.002,-.0005,math.sin(k/12*math.pi)*.0014))) for k in range(13)],.00043,metal)
    tube(f'01 / brass busk catch {index}',
         [tuple(center+Vector((-.0025,.0002,-.0016))),tuple(center+Vector((-.0025,-.0006,.0016)))],.00065,metal)
back_rows=[]
for index in range(8):
    t=.09+index*.113
    pair=[]
    for edge in [-1,1]:
        center=Vector(corset_pos(.5+edge*.022,t,.0009))
        ring=[tuple(center+Vector((math.cos(k/12*math.tau)*.00145,0,math.sin(k/12*math.tau)*.00145))) for k in range(13)]
        tube(f'01 / rear eyelet {index} side {edge}',ring,.00032,metal)
        pair.append(center+Vector((0,.0007,0)))
    back_rows.append(pair)
for index in range(7):
    for side in [0,1]:
        a=back_rows[index][side];b=back_rows[index+1][1-side]
        tube(f'01 / rear corset crossing {index} side {side}',
             [tuple(a.lerp(b,t/6)+Vector((0,.0005*math.sin(t/6*math.pi),0))) for t in range(7)],.00052,ivory)

for obj in pieces:
    if obj.get('role')=='corset_structural_detail':
        transform=obj.matrix_world.copy()
        obj.parent=corset
        obj.matrix_parent_inverse=corset.matrix_world.inverted()
        obj.matrix_world=transform
        obj['actualClothCarrier']=corset.name
        obj['attachment']='Parented to the actual corset; bone deformation pending'

scene.frame_set(1)
depsgraph=bpy.context.evaluated_depsgraph_get()
for obj in pieces:
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    uv_coords=np.asarray([d.uv[:] for d in uv.data]) if uv else np.empty((0,2))
    audit={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),
           'basePolygons':len(obj.data.polygons),'evaluatedVertices':len(mesh.vertices),
           'triangles':len(mesh.loop_triangles),'uvMaps':[l.name for l in mesh.uv_layers],
           'uvFinite':bool(uv and np.isfinite(uv_coords).all()),
           'photoLaceUVPreserved': 'PhotoLaceUV' in mesh.uv_layers,
           'actualThickness':any(m.type=='NODES' for m in obj.modifiers),
           'attachment':obj.get('attachment'),
           'parent':obj.parent.name if obj.parent else None,
           'surfaceDeformBindings':[{'target':m.target.name,'bound':bool(m.is_bound)}
                                    for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
           'rigPresent':False,'fidelityVerified':False}
    if not audit['uvFinite']:
        raise ValueError('Actual BCB UV evaluation failed: '+obj.name)
    if obj.get('opaqueGeometryApertures'):
        if not audit['photoLaceUVPreserved']:
            raise ValueError('Photographic lace UV lost during node evaluation.')
        audit.update(traceHolesPerRepeat=obj['traceHolesPerRepeat'],traceRepeats=obj['traceRepeats'],
                     actualGeometricApertures=True,clothCarrier=obj['carrier'])
    audits.append(audit)
    evaluated.to_mesh_clear()
if geometry_hash(exterior)!=exterior_hash:
    raise ValueError('The complete outer outfit was altered.')
editable=out/'chapeleiro_foundation_refined.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True)
bpy.ops.object.select_all(action='DESELECT')
for obj in pieces:
    obj.select_set(True)
model=out/'foundation_refined.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,
                          export_apply=True,export_yup=True,export_animations=False)
report={'variant':'alice_chapeleiro','method':'new_internal_gathered_cloth_photo_traced_geometric_lace_and_boned_corset',
        'sourcePhoto':trace['sourcePhoto'],'sourcePhotoSha256':trace['sourcePhotoSha256'],
        'reusedGeometry':False,'modelUpAxis':'Y','status':'generated_awaiting_visual_review',
        'model':str(model.resolve()),'modelSha256':sha(model),'editableBlend':str(editable.resolve()),
        'editableBlendSha256':sha(editable),'completeExteriorSha256':whole['modelSha256'],
        'completeExteriorVerticesUnchanged':True,'wholeOutfitPolicy':'preserve whole dressed master; author missing internals',
        'addon':'Bystedts Cloth Builder','author':'Daniel Bystedt','addonVersion':[1,0,1],
        'originalAssetSha256':sha(asset),'proceduralNodeAsset':post.name,
        'compatibilityAdjustment':'Loaded UV attribute node upgraded to FLOAT2 for Blender 5.2; vendor package unchanged.',
        'laceTrace':str(Path(args.lace).resolve()),'laceTraceSha256':sha(args.lace),
        'pieces':audits,'additionalCreditsConsumed':0,'allLayersFinished':False,
        'fidelityVerified':False,'rigPresent':False,'motionVerified':False,'clothCollisionVerified':False,
        'limitations':['Original photo remains authoritative; trace is affected by shading and unseen repeats are inferred.',
                       'Blouse, bloomers, garters and stockings remain to construct for the full foundation stage.',
                       'Pins and lace carrier bindings exist; rigged gameplay motion and collisions are not yet verified.',
                       'Corset measurements are inferred inside the preserved exterior and require photo review.']}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_REFINEMENT_SAVED',json.dumps({'pieces':len(audits),'triangles':sum(a['triangles'] for a in audits),
                                              'completeExteriorVerticesUnchanged':True,'rigPresent':False}),flush=True)
