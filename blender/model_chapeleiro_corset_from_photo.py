"""New tailored corset surface with photo-mapped front/back and actual eyelets/lacing.

This is one component of sheet 2, never the completed sheet or outfit.
No existing 3D file is read. Dimensions/depth are modeled estimates to be reviewed.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

parser=argparse.ArgumentParser()
parser.add_argument('--photo',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source,out=Path(args.photo),Path(args.output)
out.mkdir(parents=True,exist_ok=True)
if (out/'generation.json').exists(): raise ValueError('Existing construction record: use a new version directory.')
bpy.ops.wm.read_factory_settings(use_empty=True)
image=bpy.data.images.load(str(source));image.pack()
if tuple(image.size)!=(1122,1402): raise ValueError('This annotation belongs to the 1122x1402 Chapeleiro sheet 2.')
cloth=bpy.data.materials.new('Green textile / original stage photo projection');cloth.use_nodes=True
nodes=cloth.node_tree.nodes;links=cloth.node_tree.links
shader=nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.65
texture=nodes.new('ShaderNodeTexImage');texture.image=image
links.new(texture.outputs['Color'],shader.inputs['Base Color'])
gold=bpy.data.materials.new('Antique gold / actual trim geometry');gold.diffuse_color=(.28,.17,.055,1);gold.use_nodes=True
metal=gold.node_tree.nodes.get('Principled BSDF');metal.inputs['Base Color'].default_value=(.28,.17,.055,1)
metal.inputs['Metallic'].default_value=.8;metal.inputs['Roughness'].default_value=.38
cord=bpy.data.materials.new('Dark crossed cord');cord.diffuse_color=(.023,.032,.02,1);cord.use_nodes=True
cord.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.023,.032,.02,1)

profile=[(.74,.265,.145),(.84,.258,.14),(.96,.175,.105),(1.08,.21,.136),(1.18,.246,.153),(1.30,.276,.145),(1.40,.298,.12)]
def radii(z):
    for a,b in zip(profile,profile[1:]):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]);return a[1]*(1-t)+b[1]*t,a[2]*(1-t)+b[2]*t
    return profile[0][1:] if z<profile[0][0] else profile[-1][1:]
def lower(angle):
    front=max(math.cos(angle),0)
    return .845-.085*front**5+.012*abs(math.sin(6*angle))
def upper(angle):
    front=math.cos(angle)>=0
    # The stage photograph has a rounded neckline, with a shallow centre dip.
    # A fractional power creates a sharp V and mismatches that silhouette.
    return (1.185 if front else 1.19)+(.19 if front else .185)*math.sin(angle)**2
def point(angle,t):
    z=lower(angle)+(upper(angle)-lower(angle))*t
    rx,ry=radii(z)
    # Shallow new seam channels follow the vertical boning; no imported mesh.
    fluting=.0008*math.cos(angle*14)*math.sin(math.pi*t)
    return ((rx+fluting)*math.sin(angle),-(ry+fluting)*math.cos(angle),z)
def photo_uv(vertex,front):
    x,y,z=vertex
    px=856+x*820
    py=575-(z-.76)*790 if front else 940-(z-.845)*860
    return px/1122,1-py/1402
angular,vertical=192,100
vertices=[point(2*math.pi*i/angular,j/vertical) for j in range(vertical+1) for i in range(angular)]
faces=[]
for j in range(vertical):
    for i in range(angular):
        next_i=(i+1)%angular
        faces.append((j*angular+i,j*angular+next_i,(j+1)*angular+next_i,(j+1)*angular+i))
mesh=bpy.data.meshes.new('Fresh tailored quad surface');mesh.from_pydata(vertices,[],faces);mesh.update()
obj=bpy.data.objects.new('Chapeleiro / new corset textile shell',mesh);bpy.context.collection.objects.link(obj)
obj.data.materials.append(cloth)
uv=mesh.uv_layers.new(name='Original stage front and back')
for polygon in mesh.polygons:
    center=sum((Vector(vertices[v]) for v in polygon.vertices),Vector())/len(polygon.vertices)
    for loop in polygon.loop_indices:
        uv.data[loop].uv=photo_uv(vertices[mesh.loops[loop].vertex_index],center.y<0)
    polygon.use_smooth=True
solid=obj.modifiers.new('Open wearable shell / 1 mm textile','SOLIDIFY');solid.thickness=.001;solid.offset=-1

def curve(name,points,radius,material,cyclic=False):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=2
    spline=data.splines.new('POLY');spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):p.co=(*co,1)
    spline.use_cyclic_u=cyclic;data.bevel_depth=radius;data.bevel_resolution=3
    result=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(result);result.data.materials.append(material)
    return result
for name,t in [('Neckline gold binding',1),('Pointed hem gold binding',0)]:
    curve(name,[point(2*math.pi*i/angular,t) for i in range(angular)],.0015,gold,True)
for index,angle in enumerate([-.98,-.68,-.38,.38,.68,.98,2.35,2.7,3.58,3.94]):
    curve(f'Raised boning seam {index:02d}',[point(angle,j/vertical) for j in range(vertical+1)],.0009,gold)
def front_depth(z,x):
    rx,ry=radii(z);return -ry*math.sqrt(max(0,1-(x/rx)**2))-.0025
def ring(name,x,z,front):
    y=front_depth(z,x) if front else -front_depth(z,x)
    points=[(x+.0042*math.cos(t),y,z+.0042*math.sin(t)) for t in [2*math.pi*i/32 for i in range(32)]]
    curve(name,points,.00125,gold,True)
    return (x,y-.001 if front else y+.001,z)
for front in [True,False]:
    eyelets=[]
    for index in range(9):
        z=.855+index*.035
        eyelets.append([ring(f'{"Front" if front else "Back"} actual eyelet {index:02d} {side}',side*.023,z,front) for side in [-1,1]])
    for index in range(8):
        for side in [0,1]:
            a,b=Vector(eyelets[index][side]),Vector(eyelets[index+1][1-side])
            middle=(a+b)/2;middle.y+=-.0015 if front else .0015
            curve(f'{"Front" if front else "Back"} crossed lace {index:02d}-{side}',[a,middle,b],.0018,cord)
# Bottom structural tabs have their own mesh, photo UV and thickness.
for index,angle in enumerate([-.95,-.65,-.35,.35,.65,.95]):
    coords=[point(angle-.12,.14),point(angle+.12,.14),point(angle+.1,0),point(angle,0),point(angle-.1,0)]
    coords=[(x,y-.0015 if y<0 else y+.0015,z-.01 if n==3 else z) for n,(x,y,z) in enumerate(coords)]
    data=bpy.data.meshes.new(f'New pointed tab {index}');data.from_pydata(coords,[],[(0,1,2,3,4)]);data.update()
    tab=bpy.data.objects.new(f'Independent pointed tab {index}',data);bpy.context.collection.objects.link(tab);data.materials.append(cloth)
    layer=data.uv_layers.new(name='Original photo')
    for loop in data.loops:layer.data[loop.index].uv=photo_uv(coords[loop.vertex_index],True)
    mod=tab.modifiers.new('Tab thickness','SOLIDIFY');mod.thickness=.0015
    curve(f'Tab gold edge {index}',coords,.0013,gold,True)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'corset_editable.blend'))
bpy.ops.export_scene.gltf(filepath=str(out/'model.glb'),export_format='GLB',export_yup=True)
model=out/'model.glb'
record={'status':'generated_awaiting_visual_review','method':'new_blender_surface_from_stage_photo',
        'editableBlend':str((out/'corset_editable.blend').resolve()),
        'editableBlendSha256':hashlib.sha256((out/'corset_editable.blend').read_bytes()).hexdigest(),
        'sourcePhoto':str(source.resolve()),'sourcePhotoSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'sourceCrop':[590,65,1110,600],'additionalPhotoRegions':{'back':[595,605,1110,958]},
        'model':str(model.resolve()),'modelSha256':hashlib.sha256(model.read_bytes()).hexdigest(),'modelUpAxis':'Y',
        'reusedGeometry':False,'fidelityVerified':False,'completedOutfit':False,
        'builtComponents':['new_open_corset_shell','pointed_tabs','neck_and_hem_binding','boning_seams','eyelets','crossed_laces'],
        'pendingComponents':['puff_sleeves','lace_trims','separate_jewelry_and_embroidery'],
        'limitations':['Depth and dimensions are modeled estimates from the photo; not scanned measurements.',
                       'Photo color includes original lighting; no measured PBR material recovery.',
                       'Corset is one component of sheet 2, not the completed layer or outfit.']}
(out/'generation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print('FRESH_PHOTO_GUIDED_CORSET_SAVED',model)
