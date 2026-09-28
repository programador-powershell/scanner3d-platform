"""Export the whole Chapeleiro with disconnected, Head-rigged individual fiber ribbons."""
import argparse, hashlib, json, shutil, struct, sys
from pathlib import Path
import bpy, bmesh, numpy as np
from mathutils import Matrix
p=argparse.ArgumentParser();p.add_argument('--generation',required=True);p.add_argument('--output',required=True)
p.add_argument('--draco',action='store_true',help='Measure whole-character geometry compression for future individual-fiber checkpoint')
p.add_argument('--image-format',choices=['AUTO','WEBP','JPEG'],default='AUTO')
p.add_argument('--image-quality',type=int,default=100)
p.add_argument('--fiber-count',type=int,default=-1,help='Bounded full-character export probe; -1 means every fiber')
p.add_argument('--fiber-width-scale',type=float,default=1.0,help='Non-destructive ribbon-width study; 1 preserves source radius')
p.add_argument('--fiber-tone-variation',action='store_true',help='Use stable dark per-fiber fallback tone instead of one uniform fallback')
p.add_argument('--hair-roughness',type=float,default=.42,help='Base roughness of unprojected dark fibers')
p.add_argument('--hair-specular',type=float,default=.5,help='Specular IOR level of unprojected dark fibers')
p.add_argument('--samples',type=int,default=24)
p.add_argument('--chunk-size',type=int,default=2048)
p.add_argument('--projection-atlas',help='Local UV projection probe; requires --alignment')
p.add_argument('--alignment',help='Four-view 2D registration report')
p.add_argument('--hair-mask',help='Conservative 4K source-image hair-only mask')
p.add_argument('--depth-gate-mm',type=float,default=0,help='Screen-space self-occlusion gate on painted fiber faces; 0 disables')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
g=json.loads(Path(a.generation).read_text());assert sha(g['editableBlend'])==g['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
whole=bpy.data.objects['Chapeleiro / intact whole exterior / skin study']
rig=next(m.object for m in whole.modifiers if m.type=='ARMATURE')
mask=whole.data.attributes['alice_original_hair_review_mask'];hair_faces={i for i,v in enumerate(mask.data) if v.value}
original_faces=len(whole.data.polygons);original_vertices=len(whole.data.vertices)
whole.name='Alice / complete body and dress / individual hair checkpoint'
for mod in list(whole.modifiers):
    if mod.type!='ARMATURE':whole.modifiers.remove(mod)
bm=bmesh.new();bm.from_mesh(whole.data);bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[face for i,face in enumerate(bm.faces) if i in hair_faces],context='FACES')
isolated=[v for v in bm.verts if not v.link_faces]
if isolated:bmesh.ops.delete(bm,geom=isolated,context='VERTS')
bm.to_mesh(whole.data);bm.free();whole.data.update()
assert len(whole.data.polygons)+len(hair_faces)==original_faces

source_hair=next(o for o in bpy.context.scene.objects if o.type=='CURVES' and 'individual hair fibers' in o.name)
C=len(source_hair.data.curves);N=len(source_hair.data.points)//C
assert 8<=a.samples<=N and a.chunk_size>0 and (a.fiber_count==-1 or 1<=a.fiber_count<=C)
assert .15<=a.fiber_width_scale<=1.5
assert 0<=a.hair_roughness<=1 and 0<=a.hair_specular<=1
v=np.empty(len(source_hair.data.points)*3,np.float32);source_hair.data.attributes['position'].data.foreach_get('vector',v);v=v.reshape(C,N,3)
r=np.empty(len(source_hair.data.points),np.float32);source_hair.data.attributes['radius'].data.foreach_get('value',r);r=r.reshape(C,N)
selected_fiber_ids=np.arange(C) if a.fiber_count==-1 else np.linspace(0,C-1,a.fiber_count,dtype=int)
sample=np.linspace(0,N-1,a.samples).round().astype(int)
mat=bpy.data.materials.new('Alice / individual dark hair ribbons / checkpoint');mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.025,.020,.019,1);bs.inputs['Roughness'].default_value=a.hair_roughness
if 'Specular IOR Level' in bs.inputs:bs.inputs['Specular IOR Level'].default_value=a.hair_specular
mat.use_backface_culling=False
fallback_mat=mat
assert bool(a.projection_atlas)==bool(a.alignment)
assert not a.hair_mask or a.projection_atlas
assert 0<=a.depth_gate_mm<=20 and (not a.depth_gate_mm or a.projection_atlas)
projection=None
fallback_palette=[fallback_mat]
if a.projection_atlas:
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    info=json.loads(Path(a.alignment).read_text(encoding='utf-8'))
    assert info['allViewsProjectionApproved'] is False
    by_view={row['renderView']:row for row in info['views']}
    assert set(by_view)=={'front','back','left','right'}
    assert all(row['status'] in ('estimated','provisional_from_opposite_profile') for row in by_view.values())
    atlas=bpy.data.images.load(a.projection_atlas,check_existing=False)
    assert tuple(atlas.size)==(4096,4096)
    import cv2
    atlas_pixels=cv2.imread(a.projection_atlas,cv2.IMREAD_UNCHANGED)
    assert atlas_pixels.shape[:2]==(4096,4096)
    hair_mask_pixels=cv2.imread(a.hair_mask,cv2.IMREAD_GRAYSCALE) if a.hair_mask else None
    assert hair_mask_pixels is None or hair_mask_pixels.shape==(4096,4096)
    fallback_mat=mat.copy();fallback_mat.name='Alice / unpainted dark fiber / occluded or nonhair image pixels'
    fallback_bs=fallback_mat.node_tree.nodes.get('Principled BSDF')
    fallback_bs.inputs['Roughness'].default_value=.68
    if 'Specular IOR Level' in fallback_bs.inputs:
        fallback_bs.inputs['Specular IOR Level'].default_value=.12
    if a.fiber_tone_variation:
        fallback_palette=[]
        for i,level in enumerate((.013,.019,.025,.033,.043,.057)):
            variant=fallback_mat.copy()
            variant.name=f'Alice / dark individual fiber tone {i}'
            variant_bs=variant.node_tree.nodes.get('Principled BSDF')
            variant_bs.inputs['Base Color'].default_value=(level,level*.81,level*.77,1)
            variant_bs.inputs['Roughness'].default_value=(.73,.71,.68,.66,.63,.60)[i]
            fallback_palette.append(variant)
    mat.name='Alice / visible fiber painting / guarded UV probe'
    tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas
    mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value=.58
    if 'Specular IOR Level' in bs.inputs:bs.inputs['Specular IOR Level'].default_value=.15
    cameras={}
    center=Vector((0,.025,.808))
    for view,direction in [('front',(0,-1,0)),('back',(0,1,0)),('left',(-1,0,0)),('right',(1,0,0))]:
        cam=bpy.context.scene.camera.copy();cam.data=bpy.context.scene.camera.data.copy()
        cam.location=center+Vector(direction)*1.2
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.data.type='ORTHO';cam.data.ortho_scale=.4
        cameras[view]=cam
    tiles={'front':(0,0),'right':(2048,0),'back':(0,2048),'left':(2048,2048)}
    projection=dict(atlas=a.projection_atlas,alignment=a.alignment,hairMask=a.hair_mask,
                    depthGateMm=a.depth_gate_mm,validLoopPoints=0,clampedLoopPoints=0,
                    imageHairFaces=0,imageRejectedFaces=0,depthRejectedFaces=0)
    transforms={view:np.array(cam.matrix_world.inverted()@source_hair.matrix_world,dtype=np.float32)
                for view,cam in cameras.items()}
    depth_maps={}
    if a.depth_gate_mm:
        centers=((v[:,sample[:-1]]+v[:,sample[1:]])*.5).reshape(-1,3)
        for view,transform in transforms.items():
            local=centers@transform[:3,:3].T+transform[:3,3]
            ix=np.floor((.5+local[:,0]/.4)*768).astype(np.int32)
            iy=np.floor((.5-local[:,1]/.4)*768).astype(np.int32)
            distance=-local[:,2]
            inside=(ix>=0)&(ix<768)&(iy>=0)&(iy<768)&(distance>0)
            grid=np.full(768*768,np.inf,np.float32)
            np.minimum.at(grid,iy[inside]*768+ix[inside],distance[inside])
            depth_maps[view]=grid.reshape(768,768)
        del centers,local,ix,iy,distance,inside,grid
    def depth_visible(point,view):
        transform=transforms[view]
        local=transform[:3,:3]@point+transform[:3,3]
        ix=int(np.floor((.5+local[0]/.4)*768))
        iy=int(np.floor((.5-local[1]/.4)*768))
        if not (0<=ix<768 and 0<=iy<768):return False
        nearest=depth_maps[view][iy,ix]
        return bool(np.isfinite(nearest) and -local[2]<=nearest+a.depth_gate_mm*.001)
    def project_path(path,view):
        row=by_view[view]
        transform=transforms[view]
        local=path@transform[:3,:3].T+transform[:3,3]
        px=(.5+local[:,0]/.4)*768
        py=(.5-local[:,1]/.4)*768
        m=np.asarray(row['matrixRenderToPaint'],np.float32)
        sx=m[0,0]*px+m[0,1]*py+m[0,2]
        sy=m[1,0]*px+m[1,1]*py+m[1,2]
        valid=(sx>=0)&(sx<1254)&(sy>=0)&(sy<1254)
        sx=np.clip(sx,1,1253);sy=np.clip(sy,1,1253)
        tx,ty=tiles[row['paintView']]
        return np.stack(((tx+sx*2048/1254)/4096,
                         1-(ty+sy*2048/1254)/4096),axis=1),valid
    probe=np.array([[0,.025,.808]],np.float32)
    for view,cam in cameras.items():
        reference=world_to_camera_view(bpy.context.scene,cam,source_hair.matrix_world@Vector(probe[0]))
        local=probe@transforms[view][:3,:3].T+transforms[view][:3,3]
        assert abs(reference.x-(.5+local[0,0]/.4))<1e-4
        assert abs(reference.y-(.5+local[0,1]/.4))<1e-4
hair_chunks=[]
for chunk_start in range(0,len(selected_fiber_ids),a.chunk_size):
    fibers=selected_fiber_ids[chunk_start:chunk_start+a.chunk_size]
    verts=[];faces=[];uv=[];face_materials=[]
    for fid in fibers:
        tone_index=int((int(fid)*2654435761 & 0xffffffff)%len(fallback_palette))
        path=v[fid,sample];radius=r[fid,sample]
        tangent=np.gradient(path,axis=0);tangent/=np.maximum(np.linalg.norm(tangent,axis=1,keepdims=True),1e-9)
        radial=path-np.array([0,.012,.82],np.float32);radial[:,2]=0
        radial/=np.maximum(np.linalg.norm(radial,axis=1,keepdims=True),1e-9)
        side=np.cross(tangent,radial);side/=np.maximum(np.linalg.norm(side,axis=1,keepdims=True),1e-9)
        first=len(verts)
        for i in range(a.samples):
            width=max(float(radius[i])*a.fiber_width_scale,.000012)
            verts.extend([tuple(path[i]-side[i]*width),tuple(path[i]+side[i]*width)])
        if projection:
            projected={view:project_path(path,view) for view in cameras}
        for i in range(a.samples-1):
            faces.append((first+2*i,first+2*i+1,first+2*i+3,first+2*i+2))
            if projection:
                midpoint=(path[i]+path[i+1])*.5
                radial=midpoint-np.array([0,.006,.864],np.float32)
                view=('left' if radial[0]<0 else 'right') if abs(radial[0])>abs(radial[1]) else ('front' if radial[1]<0 else 'back')
                uv_path,valid=projected[view]
                a0=tuple(uv_path[i]);a1=tuple(uv_path[i+1])
                projection['validLoopPoints']+=int(valid[i])+int(valid[i+1])
                projection['clampedLoopPoints']+=2-int(valid[i])-int(valid[i+1])
                uv.extend([a0,a0,a1,a1])
                middle=(np.asarray(a0)+np.asarray(a1))*.5
                px=int(np.clip(middle[0]*4095,0,4095));py=int(np.clip((1-middle[1])*4095,0,4095))
                pixel=atlas_pixels[py,px]
                blue,green,red=(int(pixel[0]),int(pixel[1]),int(pixel[2]))
                bright=max(red,green,blue)
                image_hair=bool(valid[i] and valid[i+1] and 7<=bright<=105
                                and green<=red*1.16+4 and blue<=red*1.3+5
                                and (len(pixel)<4 or int(pixel[3])>127)
                                and (hair_mask_pixels is None or hair_mask_pixels[py,px]>127))
                if image_hair and a.depth_gate_mm and not depth_visible(midpoint,view):
                    image_hair=False
                    projection['depthRejectedFaces']+=1
                face_materials.append(len(fallback_palette) if image_hair else tone_index)
                projection['imageHairFaces']+=int(image_hair)
                projection['imageRejectedFaces']+=int(not image_hair)
            else:
                t0=i/(a.samples-1);t1=(i+1)/(a.samples-1)
                uv.extend([(0,t0),(1,t0),(1,t1),(0,t1)])
    mesh=bpy.data.meshes.new('Alice separated fiber ribbons '+str(chunk_start//a.chunk_size));mesh.from_pydata(verts,[],faces);mesh.update()
    layer=mesh.uv_layers.new(name='Hair UV')
    for loop,coordinate in zip(layer.data,uv):loop.uv=coordinate
    if projection:
        for fallback in fallback_palette:mesh.materials.append(fallback)
        mesh.materials.append(mat)
        mesh.polygons.foreach_set('material_index',face_materials)
    else:mesh.materials.append(mat)
    obj=bpy.data.objects.new('Alice / individual hair fibers / '+str(chunk_start//a.chunk_size),mesh)
    bpy.context.scene.collection.objects.link(obj);obj.parent=rig;obj.matrix_world=source_hair.matrix_world.copy()
    group=obj.vertex_groups.new(name='Head');group.add(list(range(len(mesh.vertices))),1.0,'REPLACE')
    modifier=obj.modifiers.new('Alice Head skin','ARMATURE');modifier.object=rig
    obj['aliceRole']='hair';obj['hairFiberCount']=len(fibers);obj['hairRepresentation']='separate mesh ribbon per source fiber; static Head skin, runtime dynamics pending'
    hair_chunks.append(obj)
    print('HAIR_RIBBON_CHUNK',len(hair_chunks),len(fibers),flush=True)
    del verts,faces,uv
selected=[whole,rig]+hair_chunks+[bpy.data.objects[name] for name in g['posteriorBodice']['objects']]
selected += [bpy.data.objects[g['posteriorBodice']['underlyingSkinObject']],bpy.data.objects['Chapeleiro / reconstructed closed head interior / review'],bpy.data.objects['Chapeleiro / reconstructed neck interior / review']]
assert not any(o.get('alice_collision_proxy') for o in selected)
if rig.animation_data:rig.animation_data.action=None
rig.data.pose_position='POSE'
for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
for track in list(rig.animation_data.nla_tracks):
    if track.name.split(' /')[0] in ('Walk','Run','Jump','Attack'):track.mute=False
    else:rig.animation_data.nla_tracks.remove(track)
for col in bpy.data.collections:col.hide_render=col.hide_viewport=False
for obj in bpy.context.scene.objects:
    obj.hide_render=obj not in selected;obj.hide_viewport=obj not in selected;obj.hide_set(obj not in selected);obj.select_set(obj in selected)
bpy.context.view_layer.objects.active=rig;bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
unweighted={}
for obj in selected:
    if obj.type=='MESH' and any(m.type=='ARMATURE' for m in obj.modifiers):
        empty=[v.index for v in obj.data.vertices if not any(w.weight>1e-8 for w in v.groups)]
        if empty:unweighted[obj.name]=len(empty)
assert not unweighted,unweighted
model=out/'alice_chapeleiro_complete_individual_hair_checkpoint.glb'
bpy.ops.export_scene.gltf(filepath=str(model),export_format='GLB',use_selection=True,export_yup=True,export_extras=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_frame_range=False,export_all_influences=True,export_draco_mesh_compression_enable=a.draco,export_draco_mesh_compression_level=6,export_image_format=a.image_format,export_image_quality=a.image_quality)
with model.open('rb') as f:
    magic,version,total=struct.unpack('<4sII',f.read(12));length,kind=struct.unpack('<II',f.read(8));data=json.loads(f.read(length))
assert magic==b'glTF' and total==model.stat().st_size
names=[x['name'] for x in data['animations']];assert len(names)==4
assert {name.split(' /')[0] for name in names}=={'Walk','Run','Jump','Attack'}
assert sum(n.get('extras',{}).get('hairFiberCount',0) for n in data['nodes'])==len(selected_fiber_ids)
assert any('finished posterior bodice' in n.get('name','') for n in data['nodes'])
report=dict(sourceGeneration=a.generation,sourceBlend=g['editableBlend'],sourceBlendSha256=g['editableBlendSha256'],sourceEditableUnchanged=sha(g['editableBlend'])==g['editableBlendSha256'],model=str(model),modelSha256=sha(model),modelBytes=model.stat().st_size,wholeCharacterWithDress=True,sourceFaceCount=original_faces,sourceVertices=original_vertices,sourceHairFacesExcluded=len(hair_faces),originalTripoHairIncluded=False,hairRepresentation='One disconnected mesh ribbon per source fiber; Head skin only; independent wind dynamics remain Blender authoring',exportedFiberCount=len(selected_fiber_ids),sourceFiberCount=C,fiberSamples=a.samples,fiberWidthScale=a.fiber_width_scale,fiberToneVariation=a.fiber_tone_variation,hairRoughness=a.hair_roughness,hairSpecular=a.hair_specular,hairRibbonMeshCount=len(hair_chunks),meshCount=len(data['meshes']),skinCount=len(data['skins']),animations=names,posteriorBodiceObjects=g['posteriorBodice']['objects'],collisionProxiesExcluded=True,allRiggedVerticesWeighted=True,characterFinished=False,physicsApproved=False,published=False,dracoEnabled=a.draco,imageFormat=a.image_format,imageQuality=a.image_quality)
report['hairProjectionProbe']=projection
if projection:
    report['hairProjectionProbe']['visibleFaceOcclusionValidated']=False
    report['hairProjectionProbe']['selfOcclusionDepthGateApplied']=bool(a.depth_gate_mm)
    report['hairProjectionProbe']['depthGateScope']='Hair segment-center screen depth only; body, hat and subpixel ribbon coverage remain unverified.' if a.depth_gate_mm else None
    report['hairProjectionProbe']['rightViewRegistrationValidated']=False
    report['hairProjectionProbe']['uvFidelityApproved']=False
(out/'export.json').write_text(json.dumps(report,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_export.py')
print('WHOLE_INDIVIDUAL_HAIR_CHECKPOINT_EXPORTED',json.dumps({k:v for k,v in report.items() if k!='posteriorBodiceObjects'}),flush=True)
