"""Author connected bloomers, garters and closed-foot stockings from photo 1.

Keep all prior garment cages and the whole Tripo exterior intact. Motion files
supply measurements only. Hidden midsurfaces carry future skin/cloth deformation
before Bystedt thickness and UVs, without exporting duplicate clothing.
"""
import argparse
import ast
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

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent',required=True)
parser.add_argument('--measurements',required=True)
parser.add_argument('--lace',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.parent).read_text(encoding='utf-8'))
measurements=json.loads(Path(args.measurements).read_text(encoding='utf-8'))
trace=json.loads(Path(args.lace).read_text(encoding='utf-8'))
for field in ['model','editableBlend','sourcePhoto']:
    if sha(parent[field])!=parent[field+'Sha256']:
        raise ValueError('Changed parent evidence: '+field)
if (parent['sourcePhotoSha256']!=trace['sourcePhotoSha256']
        or measurements['foreignCharacterGeometryUsed'] is not False
        or sha(measurements['sourceFbx'])!=measurements['sourceFbxSha256']):
    raise ValueError('Requires the same original photo and measured motion bones only.')
out=Path(args.output)
if out.exists():
    raise ValueError('Choose a new checkpoint directory.')
out.mkdir(parents=True)
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
scene=bpy.context.scene
scene.frame_set(1)

def cage_hash(obj):
    coords=np.empty(len(obj.data.vertices)*3,dtype=np.float32)
    obj.data.vertices.foreach_get('co',coords)
    return hashlib.sha256(coords.tobytes()+json.dumps([tuple(p.vertices) for p in obj.data.polygons]).encode()).hexdigest()

existing={o.name:cage_hash(o) for o in scene.objects if o.type=='MESH'}
inherited=[o for o in scene.objects if o.type=='MESH' and o.get('constructedNewInternalLayer')]
temporarily_disabled=[]
for obj in scene.objects:
    if obj.type=='MESH':
        for modifier in obj.modifiers:
            if modifier.show_viewport:
                temporarily_disabled.append(modifier)
                modifier.show_viewport=False
post=bpy.data.node_groups[parent['proceduralNodeAsset']]
corset=bpy.data.objects['01 / ivory fitted boned corset / pointed front']
ivory=bpy.data.materials['Foundation / warm ivory cotton'].copy()
ivory.name='Photo 1 / bloomers and garter cotton'
ivory.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.77
brass=bpy.data.materials['Foundation / aged brass eyelets and busk']
stock_material=ivory.copy()
stock_material.name='Photo 1 / warm ivory stocking knit'
stock_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.47,.39,.29,1)
stock_material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.72
import BystedtsClothBuilder as BCB
from BystedtsClothBuilder import simulation
if not hasattr(bpy.types.Scene,'BCB_props'):
    BCB.register()
scene.BCB_props.use_triangulate=False
new,seam_audits,physics_carriers,skin_carriers=[],[],{},{}
lace_materials={}

def own_functions(filename,names):
    """Reuse only bounded functions from our authoring scripts, no top-level runs."""
    tree=ast.parse(filename.read_text(encoding='utf-8'))
    body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if {n.name for n in body}!=set(names):
        raise ValueError('Own construction helper interface changed.')
    exec(compile(ast.Module(body=body,type_ignores=[]),str(filename),'exec'),globals())

helper=Path(__file__).with_name('refine_chapeleiro_foundation_blouse.py')
own_functions(helper,['mesh_object','parent_to','post_modifier','cloth','surface_follow',
                      'sharp_seams','sleeve_faces','tube','sewn_eyelets'])
lace_helper=Path(__file__).with_name('refine_chapeleiro_foundation_cloth.py')
own_functions(lace_helper,['image_array','lace_material','flat_trace'])

def quads(a,b):
    return [(a[i],b[i],b[(i+1)%len(a)],a[(i+1)%len(a)]) for i in range(len(a))]

def static_skin_receiver(obj):
    """One pre-thickness surface to receive the future leg/strap skin weights."""
    cage=obj.copy()
    cage.data=obj.data
    cage.name=obj.name+' / skin midsurface'
    scene.collection.objects.link(cage)
    cage.hide_render=True
    cage.display_type='WIRE'
    cage['constructedNewInternalLayer']=False
    cage['isFoundationSkinCage']=True
    cage['visibleFabric']=obj.name
    triangulate=cage.modifiers.new('Valid evaluated skin midsurface','TRIANGULATE')
    triangulate.quad_method='BEAUTY'
    physics_carriers[obj.name]=cage
    skin_carriers[obj.name]=cage
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    follow=obj.modifiers.new('Visible fabric follows its skin midsurface','SURFACE_DEFORM')
    follow.target=cage
    bpy.ops.object.surfacedeform_bind(modifier=follow.name)
    if not follow.is_bound:
        raise ValueError('The skin receiver did not bind.')
    obj['skinCage']=cage.name

def ring_sample(ring,u):
    index=(u%1)*len(ring)
    a=int(index)
    return Vector(ring[a]).lerp(Vector(ring[(a+1)%len(ring)]),index-a)

def photographed_hem(name,carrier,target,ring,tile,repeats,length):
    base,polygons=flat_trace(tile)
    vertices,faces,uv_faces=[],[],[]
    for repeat in range(repeats):
        offset=len(vertices)
        for p in base:
            u=(repeat+p.x)/repeats
            point=ring_sample(ring,u)
            vertices.append(point+Vector((0,0,-length*(1-p.y))))
        faces.extend(tuple(offset+i for i in poly) for poly in polygons)
        uv_faces.extend([[(base[i].x,base[i].y) for i in poly] for poly in polygons])
    obj=mesh_object(name,vertices,faces,'foundation_bloomers_photographic_lace',lace_material(tile))
    uv=obj.data.uv_layers.new(name='PhotoLaceUV')
    for poly,coords in zip(obj.data.polygons,uv_faces):
        for loop,coordinate in zip(poly.loop_indices,coords):
            uv.data[loop].uv=coordinate
    surface_follow(obj,carrier,target)
    post_modifier(obj,-.00018)
    obj['opaqueGeometryApertures']=True
    obj['traceHolesPerRepeat']=tile['retainedHoles']
    obj['traceRepeats']=repeats
    obj['carrier']=carrier.name
    obj['sourceCrop']=json.dumps(tile['sourcePhotoCrop'])
    return obj

# One connected pair-of-pants surface: waist plus two true leg openings.
# The two leg roots share the SAME crotch vertices/edges, rather than two tubes.
around,hip_rows=128,18
def hip_position(u,t):
    angle=u*math.tau
    z=.624-(.624-.560)*t
    # The gathered waistband opens into the hips without a second bulb.
    # Uneven long folds continue into the leg panels below the crotch seam.
    bulge=math.sin(math.pi*t*.5)
    phase=31*angle+.6*math.sin(3*angle)+.45*t
    gather=(.0025+.0028*math.sin(math.pi*t*.65))*math.cos(phase)
    gather+=.0012*math.sin(11*angle-.8*t)*math.sin(math.pi*t)
    rx=.064+.013*bulge+gather
    ry=.042+.008*bulge+gather*.65
    return Vector((rx*math.sin(angle),-ry*math.cos(angle),z))
vertices=[hip_position(c/around,r/hip_rows) for r in range(hip_rows+1) for c in range(around)]
faces=[]
for row in range(hip_rows):
    faces.extend(quads(list(range(row*around,(row+1)*around)),list(range((row+1)*around,(row+2)*around))))
bottom=hip_rows*around
front,back=vertices[bottom],vertices[bottom+around//2]
bridge=[bottom]
for i in range(1,16):
    t=i/16
    bridge.append(len(vertices))
    vertices.append(front.lerp(back,t)+Vector((0,0,-.048*math.sin(math.pi*t))))
bridge.append(bottom+around//2)
leg_roots={1:list(range(bottom,bottom+around//2+1))+bridge[-2:0:-1],
           -1:list(range(bottom+around//2,bottom+around))+[bottom]+bridge[1:-1]}
leg_rings={}
pin_cuffs=[]
for side,root in leg_roots.items():
    label='Left' if side==1 else 'Right'
    center=Vector((side*.046,0,.548))
    angles=[math.atan2((vertices[i]-center).y/.055,(vertices[i]-center).x/.044) for i in root]
    previous=root
    for row in range(1,25):
        t=row/24
        ring=[]
        for original,angle in zip(root,angles):
            radial=Vector((math.cos(angle),math.sin(angle),0))
            cuff=Vector((side*.0475+.0315*radial.x,.001+.0335*radial.y,.421))
            puff=.014*math.sin(math.pi*t)*(.3+.7*max(0,side*radial.x))
            fold=.0045*math.sin(math.pi*t)*math.cos(23*angle+.6*math.sin(angle*3)+t*.8)
            fold+=.002*math.sin(math.pi*t)**2*math.cos(9*angle-2.8*t)
            p=vertices[original].lerp(cuff,t)+radial*(puff+fold)
            p.x=side*max(side*p.x,.00035*math.sin(math.pi*t))
            ring.append(len(vertices))
            vertices.append(p)
        faces.extend(quads(previous,ring))
        previous=ring
    leg_rings[side]=[vertices[i].copy() for i in previous]
    pin_cuffs.extend(previous)
bloomers=mesh_object('01 / bloomers / continuous waist and sewn crotch',vertices,faces,'foundation_bloomers')
bloomers['rigSide']='both legs'
bloomers['sharedCrotchVertices']=len(bridge)
parent_to(bloomers,corset)
cloth(bloomers,{1.:list(range(around))+pin_cuffs,.6:list(range(around,around*2))})
sharp_seams(bloomers,{i for i in range(len(vertices)) if i<bottom and i%around in [0,around//2]})
post_modifier(bloomers,-.0004)
print('FOUNDATION_CONNECTED_BLOOMERS_BUILT',len(vertices),flush=True)

waist=[]
for row in range(7):
    t=row/6
    waist.extend(hip_position(c/around,t*.105)+Vector((.00045*math.sin(c/around*math.tau),
                        -.00045*math.cos(c/around*math.tau),0)) for c in range(around))
band=mesh_object('01 / bloomers / gathered waist elastic casing',waist,
                 [face[::-1] for face in sleeve_faces(around,6)],'foundation_bloomers_trim')
surface_follow(band,bloomers)
post_modifier(band,-.00035)
for side in [-1,1]:
    rail=[hip_position((side*.005)%1,t/30*.86)+Vector((0,-.0005,0)) for t in range(31)]
    obj=tube(f'01 / bloomers / front placket seam {side}',rail,.00038,role='foundation_bloomers_trim')
    surface_follow(obj,bloomers)
for i in range(5):
    center=hip_position(0,.17+i*.105)+Vector((0,-.001,0))
    points=[center+Vector((math.cos(k/12*math.tau)*.0007,0,math.sin(k/12*math.tau)*.0007)) for k in range(13)]
    obj=tube(f'01 / bloomers / sewn ivory button {i}',points,.00025,role='foundation_bloomers_trim')
    surface_follow(obj,bloomers)
for side,ring in leg_rings.items():
    label='left' if side==1 else 'right'
    obj=tube(f'01 / {label} bloomers / cuff elastic casing',ring+[ring[0]],.0008,role='foundation_bloomers_trim')
    surface_follow(obj,bloomers)
    n=len(ring)
    cuff_vertices=[]
    center=Vector((side*.0475,.001,.421))
    for row in range(7):
        t=row/6
        for i,p in enumerate(ring):
            radial=(p-center).normalized()
            phase=24*i/n*math.tau+.4*math.sin(7*i/n*math.tau)
            cuff_vertices.append(p+Vector((0,0,-.010*t+.0016*t*math.cos(phase)))
                                 +radial*t*(.007+.0035*math.cos(phase)))
    cuff=mesh_object(f'01 / {label} bloomers / gathered cuff frill',cuff_vertices,
                     [face[::-1] for face in sleeve_faces(n,6)],'foundation_bloomers_trim')
    surface_follow(cuff,bloomers)
    post_modifier(cuff,-.00022)
    photographed_hem(f'01 / {label} bloomers / bloomer hem floral lace',cuff,bloomers,
                      cuff_vertices[-n:],trace['tiles'][0],10,.015)
    knot=center+Vector((side*.0335,0,.003))
    for wing in [-1,1]:
        path=[knot+Vector((side*.001,wing*.004*math.sin(k/20*math.tau),
                           .0025*(1-math.cos(k/20*math.tau)))) for k in range(21)]
        obj=tube(f'01 / {label} bloomers / cuff bow wing {wing}',path,.00055,role='foundation_bloomers_trim')
        surface_follow(obj,bloomers)

# Anatomical leg/ankle/foot lofts from the measured rest chain, not straight tubes.
stockings={}
for side,label in [(1,'Left'),(-1,'Right')]:
    bones=measurements['bones']
    thigh,knee,ankle=(Vector(bones[label+n]['head']) for n in ['UpLeg','Leg','Foot'])
    controls=[(thigh.x,.005,.516,.0295,.034), (thigh.x,.002,.43,.028,.031),
              (knee.x,knee.y,.31,.020,.023), (knee.x,.002,.245,.026,.028),
              (ankle.x,.009,.16,.019,.024), (ankle.x,ankle.y,.077,.0148,.020),
              (ankle.x,.008,.048,.017,.021), (ankle.x,-.012,.030,.021,.018),
              (thigh.x+side*.003,-.038,.020,.024,.013),
              (thigh.x+side*.003,-.060,.018,.020,.010),
              (thigh.x+side*.003,-.078,.018,.009,.005),
              (thigh.x+side*.003,-.083,.018,.002,.002)]
    samples=[]
    for index in range(len(controls)-1):
        p0=np.asarray(controls[max(0,index-1)])
        p1,p2=np.asarray(controls[index]),np.asarray(controls[index+1])
        p3=np.asarray(controls[min(index+2,len(controls)-1)])
        for k in range(6):
            t=k/6
            samples.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
    samples.append(np.asarray(controls[-1]))
    n=64
    points=[]
    for row,s in enumerate(samples):
        center=Vector(s[:3])
        tangent=(Vector(samples[min(row+1,len(samples)-1)][:3])-Vector(samples[max(0,row-1)][:3])).normalized()
        x_axis=Vector((1,0,0))
        other=tangent.cross(x_axis).normalized()
        rib=.00015*math.exp(-((s[2]-.23)/.17)**4)*math.cos(s[2]/.013*math.tau)**8
        for c in range(n):
            angle=c/n*math.tau
            points.append(center+x_axis*max(.001,s[3]+rib)*math.cos(angle)
                          +other*max(.001,s[4]+rib)*math.sin(angle))
    faces=sleeve_faces(n,len(samples)-1)
    toe_center=len(points)
    points.append(Vector(samples[-1][:3]))
    faces.extend((toe_center,(len(samples)-1)*n+c,(len(samples)-1)*n+(c+1)%n) for c in range(n))
    obj=mesh_object(f'01 / {label.lower()} stocking / fitted leg ankle and closed toe',points,faces,
                    'foundation_stocking',stock_material)
    obj['rigSide']=label
    obj['anatomicalFootLoft']=True
    parent_to(obj,corset)
    static_skin_receiver(obj)
    sharp_seams(obj,set(range(0,len(samples)*n,n)))
    post_modifier(obj,-.00025)
    stockings[side]=obj
    # Narrow horizontal knit bands and sewn panels are visible in photo 1.
    # Build them as real surfaces on the same leg receiver; no alpha cutouts.
    band_vertices,band_faces=[],[]
    leg_samples=samples[:31]
    for height in np.arange(.09,.503,.013):
        row=next(i for i in range(len(leg_samples)-1)
                 if leg_samples[i][2]>=height>=leg_samples[i+1][2])
        a,b=leg_samples[row],leg_samples[row+1]
        s=a+(b-a)*(a[2]-height)/(a[2]-b[2])
        offset=len(band_vertices)
        for dz in [.00055,0,-.00055]:
            for c in range(n):
                angle=c/n*math.tau
                band_vertices.append(Vector((s[0]+(s[3]+.00032)*math.cos(angle),
                                               s[1]-(s[4]+.00032)*math.sin(angle),height+dz)))
        band_faces.extend(tuple(offset+i for i in face) for face in sleeve_faces(n,2))
    knit=mesh_object(f'01 / {label.lower()} stocking / horizontal knitted bands',
                     band_vertices,band_faces,'foundation_stocking_trim',stock_material)
    surface_follow(knit,obj)
    post_modifier(knit,-.00012)
    for name,column in [('front',n//4),('rear',3*n//4)]:
        rail=[points[row*n+column]+Vector((0,-.0004 if name=='front' else .0004,0))
              for row in range(31)]
        seam=tube(f'01 / {label.lower()} stocking / sewn {name} panel seam',rail,.00035,
                  role='foundation_stocking_trim')
        surface_follow(seam,obj)

# Narrow gathered garter belt, two pointed thigh reinforcements and four webs.
n=128
def belt_position(u,t):
    theta=u*math.tau
    fold=.0007*math.cos(theta*43+.2*math.sin(theta*5))*math.sin(math.pi*t)
    return Vector(((.063+fold)*math.sin(theta),-(.043+fold*.7)*math.cos(theta),.605-.019*t))
points=[belt_position(c/n,r/8) for r in range(9) for c in range(n)]
belt=mesh_object('01 / garter belt / gathered waist casing',points,
                 [face[::-1] for face in sleeve_faces(n,8)],'foundation_garter_belt')
parent_to(belt,corset)
cloth(belt,{1.:list(range(n)),.7:list(range(n,n*2))})
post_modifier(belt,-.00035)
for edge,direction in [(0,1),(1,-1)]:
    root=[belt_position(c/n,edge) for c in range(n)]
    vertices=[]
    for r in range(7):
        t=r/6
        for c,p in enumerate(root):
            theta=c/n*math.tau
            radial=Vector((math.sin(theta),-math.cos(theta),0))
            wave=math.cos(32*theta+.4*math.sin(5*theta))
            vertices.append(p+Vector((0,0,direction*(.0065*t+.0013*t*wave)))
                            +radial*t*(.005+.0027*wave))
    frill=mesh_object(f'01 / garter belt / ruffled edge {edge}',vertices,
                      [face if direction==1 else face[::-1] for face in sleeve_faces(n,6)],'foundation_garter_trim')
    surface_follow(frill,belt)
    post_modifier(frill,-.0002)
    sewn_eyelets(f'01 / garter belt / looped lace edge {edge}',vertices[-n:],48,.003,
                 Vector((0,0,direction)),frill,belt)
    new[-1]['role']='foundation_garter_trim'
for side,stocking in stockings.items():
    label='left' if side==1 else 'right'
    cx=measurements['bones'][('Left' if side==1 else 'Right')+'UpLeg']['head'][0]
    def cup_position(u,t):
        angle=u*math.tau
        front=max(0,math.cos(angle))
        z=.510+(.483-.018*front**4-.510)*t
        return Vector((cx+(.0305-.0015*t)*math.sin(angle),.003-(.034-.002*t)*math.cos(angle),z))
    cup_points=[cup_position(c/96,r/14) for r in range(15) for c in range(96)]
    cup=mesh_object(f'01 / {label} garter / pointed thigh reinforcement',cup_points,
                    [face[::-1] for face in sleeve_faces(96,14)],'foundation_garter_cup')
    surface_follow(cup,stocking)
    post_modifier(cup,-.00035)
    for t in [0,1]:
        path=[cup_position(c/128,t)+Vector((0,-.0003,0)) for c in range(129)]
        obj=tube(f'01 / {label} garter / cup bound edge {t}',path,.00065,role='foundation_garter_trim')
        surface_follow(obj,cup,stocking)
    for delta in [-.003,.003]:
        path=[cup_position(delta,t/24)+Vector((0,-.0005,0)) for t in range(25)]
        obj=tube(f'01 / {label} garter / cup front stitch {delta}',path,.00032,role='foundation_garter_trim')
        surface_follow(obj,cup,stocking)
    lower_ring=[cup_position(c/96,1) for c in range(96)]
    frill_points=[]
    for row in range(7):
        t=row/6
        for c,p in enumerate(lower_ring):
            angle=c/96*math.tau
            wave=math.cos(26*angle+.3*math.sin(3*angle))
            radial=Vector((math.sin(angle),-math.cos(angle),0))
            frill_points.append(p+radial*t*(.0035+.0018*wave)
                                 +Vector((0,0,-.0065*t+.001*t*wave)))
    hem=mesh_object(f'01 / {label} garter / gathered thigh cup frill',frill_points,
                    [face[::-1] for face in sleeve_faces(96,6)],'foundation_garter_trim')
    surface_follow(hem,cup,stocking)
    post_modifier(hem,-.00018)
    sewn_eyelets(f'01 / {label} garter / thigh cup needle lace',frill_points[-96:],28,.002,
                 Vector((0,0,-1)),hem,stocking)
    new[-1]['role']='foundation_garter_trim'
    for front in [True,False]:
        u=(.1 if side==1 else .9) if front else (.4 if side==1 else .6)
        start=belt_position(u,1)
        end=Vector((cx,-.033 if front else .034,.466 if front else .483))
        rows=24
        centers=[start.lerp(end,r/rows)+Vector((0,(-1 if front else 1)*.0012*math.sin(math.pi*r/rows),0)) for r in range(rows+1)]
        vertices=[p+Vector((width*.0038,0,0)) for p in centers for width in [-1,1]]
        strap=mesh_object(f'01 / {label} garter / '+('front' if front else 'rear')+' suspension web',
                          vertices,[(2*r,2*r+2,2*r+3,2*r+1) if front else (2*r+1,2*r+3,2*r+2,2*r)
                                    for r in range(rows)],'foundation_garter_strap')
        parent_to(strap,belt)
        strap['rigSide']='Left' if side==1 else 'Right'
        strap['requiredDualSkinAttachment']='Hips at belt root; thigh at stocking clasp'
        static_skin_receiver(strap)
        post_modifier(strap,-.00045)
        for index,t in enumerate([.3,.69]):
            center=start.lerp(end,t)+Vector((0,-.0007 if front else .0007,0))
            path=[center+Vector((x,0,z)) for x,z in [(-.0048,-.0019),(.0048,-.0019),(.0048,.0019),(-.0048,.0019),(-.0048,-.0019)]]
            obj=tube(f'01 / {label} garter / {front} brass slider {index}',path,.00045,brass,'foundation_garter_hardware')
            surface_follow(obj,strap)
        path=[end+Vector((math.sin(k/24*math.tau)*.0023,-.001 if front else .001,-.003+math.cos(k/24*math.tau)*.0035)) for k in range(25)]
        obj=tube(f'01 / {label} garter / {front} brass stocking clasp',path,.00055,brass,'foundation_garter_hardware')
        surface_follow(obj,strap)

for name,cage in physics_carriers.items():
    if name not in skin_carriers:
        cage['isBlouseSimulationCage']=False
        cage['isFoundationSimulationCage']=True
for modifier in temporarily_disabled:
    modifier.show_viewport=True
scene.frame_set(1)
bpy.context.view_layer.update()
if any(cage_hash(bpy.data.objects[name])!=digest for name,digest in existing.items()):
    raise ValueError('The preserved exterior or prior garment cage changed.')
audits=[]
depsgraph=bpy.context.evaluated_depsgraph_get()
for obj in inherited+new:
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    mesh.calc_loop_triangles()
    uv=mesh.uv_layers.get('UVMap')
    if not uv or not np.isfinite(np.asarray([d.uv[:] for d in uv.data])).all():
        raise ValueError('Actual garment UVs failed: '+obj.name)
    audit={'name':obj.name,'role':obj['role'],'baseVertices':len(obj.data.vertices),
           'basePolygons':len(obj.data.polygons),'evaluatedVertices':len(mesh.vertices),
           'triangles':len(mesh.loop_triangles),'uvMaps':[l.name for l in mesh.uv_layers],
           'uvFinite':True,'parent':obj.parent.name if obj.parent else None,
           'surfaceDeformBindings':[{'target':m.target.name,'bound':m.is_bound} for m in obj.modifiers if m.type=='SURFACE_DEFORM'],
           'rigPresent':False,'fidelityVerified':False}
    if obj.get('opaqueGeometryApertures'):
        audit.update(actualGeometricApertures=True,traceRepeats=obj['traceRepeats'],traceHolesPerRepeat=obj['traceHolesPerRepeat'])
    if obj.get('actualThreadLoops'):
        audit['actualThreadLoops']=obj['actualThreadLoops']
    audits.append(audit)
    evaluated.to_mesh_clear()
editable=out/'chapeleiro_foundation_lower.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True)
bpy.ops.object.select_all(action='DESELECT')
for obj in inherited+new:
    obj.select_set(True)
model=out/'foundation_lower.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,
                          export_apply=True,export_yup=True,export_animations=False)
report={**parent,'method':'incremental_photo_1_connected_bloomers_garters_and_anatomical_stockings',
        'model':str(model.resolve()),'modelSha256':sha(model),
        'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
        'parentGeneration':str(Path(args.parent).resolve()),'parentGenerationSha256':sha(args.parent),
        'pieces':audits,'inheritedInternalPieces':len(inherited),'addedInternalPieces':len(new),
        'existingCagesUnchanged':True,'incrementalRefinement':True,
        'additionalLaceTrace':str(Path(args.lace).resolve()),'additionalLaceTraceSha256':sha(args.lace),
        'lowerBoneMeasurements':str(Path(args.measurements).resolve()),'lowerBoneMeasurementsSha256':sha(args.measurements),
        'ownHelperSources':[{'file':str(helper.resolve()),'sha256':sha(helper)},
                           {'file':str(lace_helper.resolve()),'sha256':sha(lace_helper)}],
        'additionalSimulationCages':[{'name':o.name,'visibleFabric':name,'simulationVerified':False}
                                    for name,o in physics_carriers.items() if name not in skin_carriers],
        'additionalSkinCages':[{'name':o.name,'visibleFabric':name,'rigPresent':False} for name,o in skin_carriers.items()],
        'additionalCreditsConsumed':0,'allLayersFinished':False,'fidelityVerified':False,'rigPresent':False,
        'motionVerified':False,'clothCollisionVerified':False,
        'limitations':['Bloomers/garters/stockings and unseen back surfaces require their own isolated photo reviews.',
                       'Garter webs require true dual skin attachment during walking/running/jumping/attacking.',
                       'Existing petticoat drapes, corset frills/ribbons and whole-body fit still need refinement.',
                       'Construction carriers are not a verified shared rig or gameplay cloth/collision solution.']}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_LOWER_SAVED',json.dumps({'addedPieces':len(new),'totalPieces':len(audits),
      'triangles':sum(p['triangles'] for p in audits),'existingCagesUnchanged':True,'rigPresent':False}),flush=True)
