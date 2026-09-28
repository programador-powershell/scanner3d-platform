"""Replace provisional under-hair green closure with a reference-matched rigged bodice back."""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--stages',nargs='+',choices=['before','after'],default=['before','after'])
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend']);s=bpy.context.scene;s.frame_set(1)
old=bpy.data.objects['Chapeleiro / posterior bodice closure beneath hair / review']
rig=next(m.object for m in old.modifiers if m.type=='ARMATURE');original_material=old.data.materials[0]
photo=Path('F:/Alice/References/alice_chapeleiro_back_master_v001.jpg')
paint=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro/back_brocade_paint_v001/back_brocade.png')
image=bpy.data.images.load(str(paint),check_existing=True);image.pack()
def material(name,color,rough=.5,metal=0):
    m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes.get('Principled BSDF')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Roughness'].default_value=rough;n.inputs['Metallic'].default_value=metal
    return m
cloth=material('Chapeleiro / posterior corset / own layer photo',(.015,.04,.03),.5)
n=cloth.node_tree.nodes.new('ShaderNodeTexImage');n.image=image
cloth.node_tree.links.new(n.outputs['Color'],cloth.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
gold=material('Chapeleiro / aged gold posterior seams and eyelets',(.25,.15,.045),.4,.72)
cord=material('Chapeleiro / dark woven posterior laces',(.015,.022,.014),.7)
skin=bpy.data.objects['Chapeleiro / reconstructed neck interior / review'].data.materials[0]
old.data.materials.clear();old.data.materials.append(skin)
old.data.materials.append(cloth)
old['posterior_checkpoint_role']='Underlying upper-back skin; covered by the new complete bodice panel below the neckline.'
tree=KDTree(len(old.data.vertices))
for v in old.data.vertices:tree.insert(old.matrix_world@v.co,v.index)
tree.balance();created=[]
def bind(obj):
    for vg in old.vertex_groups:obj.vertex_groups.new(name=vg.name)
    for v in obj.data.vertices:
        _,index,_=tree.find(obj.matrix_world@v.co)
        for weight in old.data.vertices[index].groups:
            obj.vertex_groups[old.vertex_groups[weight.group].name].add([v.index],weight.weight,'REPLACE')
    mod=obj.modifiers.new('Existing torso rig / posterior refinement','ARMATURE');mod.object=rig
    obj['alice_posterior_checkpoint']=True;created.append(obj)
def surface(u,t,offset=0):
    bottom=.636+.004*abs(u);top=.774+.034*u*u
    z=bottom+(top-bottom)*t
    width=.044+.015*math.sin(math.pi*t/2)+.009*t*t
    depth=.041-.007*t
    return Vector((width*u,.007+depth*math.sqrt(1-(u/1.3)**2)+offset,z))
def photo_uv(u,t):
    # Full-resolution textile sample; hardware and seams remain real geometry.
    return ((u+1)/2,t)
# Below the neckline the supporting surface is clothed, never exposed skin.
support_materials=[]
for face in old.data.polygons:
    co=old.matrix_world@face.center;u=max(-1,min(1,co.x/.064))
    face.material_index=1 if co.z<.771+.034*u*u else 0;support_materials.append(face.material_index)
    for loop in face.loop_indices:
        point=old.matrix_world@old.data.vertices[old.data.loops[loop].vertex_index].co
        t=max(0,min(1,(point.z-.636)/.15));uu=max(-1,min(1,point.x/(.044+.015*math.sin(math.pi*t/2)+.009*t*t)))
        old.data.uv_layers.active.data[loop].uv=photo_uv(uu,t)
verts=[];faces=[];uvs=[];rows=65;cols=65
for j in range(rows):
    t=j/(rows-1)
    for i in range(cols):
        u=2*i/(cols-1)-1;verts.append(surface(u,t,.0009))
        # Photo-space back panel, respecting its curved neckline and pointed lower edge.
        uvs.append(photo_uv(u,t))
        if i<cols-1 and j<rows-1:
            k=j*cols+i;faces.append((k,k+cols,k+cols+1,k+1))
mesh=bpy.data.meshes.new('Posterior corset / shaped panels UV');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('Chapeleiro / finished posterior bodice / checkpoint',mesh);s.collection.objects.link(obj)
mesh.materials.append(cloth);uv=mesh.uv_layers.new(name='OwnBackPhotoUV')
for f in mesh.polygons:
    f.use_smooth=True
    for loop in f.loop_indices:uv.data[loop].uv=uvs[mesh.loops[loop].vertex_index]
bind(obj)
# A fitted dark placket sits under the physical lace bridges.
pv=[];pf=[]
for j in range(65):
    for u in [-.30,.30]:pv.append(surface(u,j/64,.0016))
    if j:pf.append((2*j-2,2*j,2*j+1,2*j-1))
pm=bpy.data.meshes.new('Posterior central closure placket');pm.from_pydata(pv,[],pf);pm.materials.append(cloth);pm.update()
puv=pm.uv_layers.new(name='PlacketTextileUV')
for f in pm.polygons:
    for loop in f.loop_indices:
        vi=pm.loops[loop].vertex_index;puv.data[loop].uv=photo_uv(-.30+.60*(vi%2),(vi//2)/64)
po=bpy.data.objects.new('Chapeleiro / posterior closure placket',pm);s.collection.objects.link(po)
for f in pm.polygons:f.use_smooth=True
bind(po)
def tube(name,points,radius,mat,sides=8):
    vv=[];ff=[]
    for j,point in enumerate(points):
        tangent=(points[min(j+1,len(points)-1)]-points[max(0,j-1)]).normalized()
        side=tangent.cross(Vector((0,1,0))).normalized()
        if side.length<.01:side=tangent.cross(Vector((1,0,0))).normalized()
        normal=tangent.cross(side).normalized()
        for k in range(sides):vv.append(point+radius*(side*math.cos(k*2*math.pi/sides)+normal*math.sin(k*2*math.pi/sides)))
        if j:
            for k in range(sides):ff.append(((j-1)*sides+k,(j-1)*sides+(k+1)%sides,j*sides+(k+1)%sides,j*sides+k))
    data=bpy.data.meshes.new(name);data.from_pydata(vv,[],ff);data.materials.append(mat);data.update()
    o=bpy.data.objects.new(name,data);s.collection.objects.link(o)
    for f in data.polygons:f.use_smooth=True
    bind(o);return o
for u in [-.87,-.48,-.30,.30,.48,.87]:
    tube('Chapeleiro / posterior boning seam '+str(u),[surface(u,j/64,.0014) for j in range(65)],.00028,gold)
for t in [0,1]:
    tube('Chapeleiro / posterior edge binding '+str(t),[surface(-1+2*j/96,t,.0014) for j in range(97)],.00040,gold)
for segment in range(38):
    points=[]
    for j in range(17):
        u=-1+2*(segment+j/16)/38;co=surface(u,1,.0018);co.z+=.0035*math.sin(math.pi*j/16);points.append(co)
    tube('Chapeleiro / posterior neckline lace scallop '+str(segment),points,.00018,cord,6)
    tube('Chapeleiro / posterior neckline lace gold thread '+str(segment),[point+Vector((0,.00012,.00025)) for point in points],.00009,gold,5)
for row in range(7):
    t=.06+row*.135
    for sign in [-1,1]:
        center=surface(sign*.28,t,.0019)
        loop=[center+Vector((.00115*math.cos(j*2*math.pi/24),0,.00115*math.sin(j*2*math.pi/24))) for j in range(25)]
        tube('Chapeleiro / posterior eyelet '+str(row)+' '+str(sign),loop,.00025,gold)
    if row<6:
        for sign in [-1,1]:
            points=[]
            for j in range(25):
                q=j/24;u=sign*(-.28+.56*q);co=surface(u,t+.135*q,.0024+.0006*math.sin(math.pi*q));points.append(co)
            tube('Chapeleiro / posterior crossed lace '+str(row)+' '+str(sign),points,.00048,cord)
# Preserve complete authored hair visibility in the saved master; hide it only for review renders.
blend=out/'chapeleiro_complete_posterior_bodice_checkpoint.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
r=dict(g);r.update(parentGeneration=a.generation,editableBlend=str(blend),editableBlendSha256=sha(blend),posteriorBodice=dict(reference=str(photo),referenceSha256=sha(photo),projectionPainting=str(paint),projectionPaintingSha256=sha(paint),visibleUv4kBakePending=True,objects=[o.name for o in created],underlyingSkinObject=old.name,rig=rig.name,allNewVerticesWeighted=True,originalTripoDressUncut=True),published=False,physicsVerified=False,styleFidelityApproved=False)
(out/'generation.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_posterior_bodice.py')
for o in s.objects:
    if o.type=='CURVES':o.hide_render=True
cam=s.camera;target=Vector((0,.025,.733));cam.data.ortho_scale=.26
s.render.resolution_x=s.render.resolution_y=900;s.cycles.samples=32;s.cycles.use_denoising=True
report=dict(sourceGeneration=str(out/'generation.json'),ownReference=str(photo),hairTemporarilyHidden=True,hairRestoredInSavedMaster=True,renders=[],checkpointOnly=True)
for view,d in [('back',(0,1,0)),('back_oblique',(-.55,1,0))]:
    cam.location=target+Vector(d).normalized()*1.2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    for stage in a.stages:
        old.data.materials[0]=original_material if stage=='before' else skin
        for face,index in zip(old.data.polygons,support_materials):face.material_index=0 if stage=='before' else index
        for o in created:o.hide_render=stage=='before'
        s.render.filepath=str(out/(view+'_'+stage+'.png'));bpy.ops.render.render(write_still=True)
        report['renders'].append(dict(view=view,stage=stage,file=s.render.filepath,sha256=sha(s.render.filepath)))
        (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
assert sha(g['editableBlend'])==g['editableBlendSha256']
print('POSTERIOR_BODICE_REVIEW_READY',json.dumps(r['posteriorBodice']),flush=True)
