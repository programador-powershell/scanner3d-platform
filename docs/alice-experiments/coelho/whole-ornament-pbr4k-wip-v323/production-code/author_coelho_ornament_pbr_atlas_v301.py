"""Own shared 4K UV atlas and native surface-material bake on exact casting267.

No new photographed detail is invented by this bake. Metallic blue is an
art-directed opaque PBR approximation, selected for portable colored reflection.
Does not approve gemstone optics, filigree, rig, physics or the whole asset.
"""
import bpy,numpy as np,json,hashlib,time,sys
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=O/'Textures';start=time.time();W=4096
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
a=read(O/'apron_ornament_cast_mounts_authoring_audit_v267.json');source=R/a['path'];assert sha(source)==a['sha256'];assert read(O/'apron_ornament_triangle_contact_audit_v269.json')['totalSelfSATTrianglePairs']==0
scene=bpy.context.scene;col=bpy.data.collections.new('COELHO_ORNAMENTS_PBR_ATLAS_V301_LOCAL_NOT_APPROVED');scene.collection.children.link(col);objects=[];rows=[];positions=[];faces=[];mi=[];uvs=[];offset=0
tiles=[(.02,.68),(.52,.68),(.02,.35),(.52,.35),(.02,.02)]
for row,tile in zip(a['newObjects'],tiles):
    old=bpy.data.objects[row['object']];ob=old.copy();ob.data=old.data.copy();ob.name=old.name.replace('v267','v301');ob.data.name=ob.name+'.Mesh';col.objects.link(ob);ob.hide_render=True;ob.hide_set(True);objects.append(ob)
    P=np.asarray([v.co[:] for v in ob.data.vertices],np.float32);F=[tuple(p.vertices) for p in ob.data.polygons];uv=np.asarray([x.uv[:] for x in ob.data.uv_layers.active.data],np.float32);assert np.isfinite(uv).all() and uv.min()>=-1e-7 and uv.max()<=1.0000001
    uv=uv*np.array([.46,.29],np.float32)+np.array(tile,np.float32);ob.data.uv_layers.active.data.foreach_set('uv',uv.ravel());ob.data.uv_layers.active.name='CoelhoOrnamentAtlas4K.v301';ob.data.uv_layers.active.active_render=True
    positions.extend(P.tolist());faces.extend(tuple(offset+v for v in f) for f in F);mi.extend(p.material_index for p in ob.data.polygons);uvs.extend(uv.tolist());offset+=len(P)
    rows.append(dict(row,object=ob.name,geometryPositionSHA256=hashlib.sha256(P.tobytes()).hexdigest(),uvSHA256=hashlib.sha256(uv.tobytes()).hexdigest(),atlasTileOrigin=tile,atlasTileScale=[.46,.29],UVMapName='CoelhoOrnamentAtlas4K.v301'))
m=bpy.data.meshes.new('DIAGNOSTIC_CoelhoAtlasBake301');m.from_pydata(positions,[],faces);m.update();uvlayer=m.uv_layers.new(name='CoelhoOrnamentAtlas4K.v301');uvlayer.data.foreach_set('uv',np.asarray(uvs,np.float32).ravel());uvlayer.active_render=True
for p,slot in zip(m.polygons,mi):p.material_index=slot;p.use_smooth=slot==0
temp=bpy.data.objects.new('DIAGNOSTIC_CoelhoAtlasBake301',m);col.objects.link(temp);m.calc_loop_triangles();uv=np.asarray(uvs,np.float64);owner=np.full((W,W),-1,np.int32)
def raster():
    owner.fill(-1);overlap=0;degenerate=0;bad=set()
    for i,t in enumerate(m.loop_triangles):
        U=uv[list(t.loops)];M=np.column_stack((U[1]-U[0],U[2]-U[0]));det=np.linalg.det(M)
        if abs(det)<1e-16:degenerate+=1;continue
        lo=np.maximum(np.floor(U.min(0)*W).astype(int),0);hi=np.minimum(np.ceil(U.max(0)*W).astype(int),W-1)
        if (hi<lo).any():continue
        xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5);samples=np.column_stack((xx.ravel(),yy.ravel()))/W;b=(samples-U[0])@np.linalg.inv(M).T;inside=np.minimum(1-b.sum(1),b.min(1))>1e-7;pixels=(samples[inside]*W).astype(int);x=pixels[:,0];y=pixels[:,1];previous=owner[y,x];hits=previous>=0
        if hits.any():
            overlap+=int(hits.sum());bad.add(t.polygon_index);bad.update(m.loop_triangles[int(k)].polygon_index for k in previous[hits])
        owner[y,x]=i
    return overlap,degenerate,bad
overlap,degenerate,bad=raster()
priorUV=read(O/'apron_ornament_continuous_uv_audit_v296.json');assert priorUV['sourceSHA256']==read(O/'apron_ornament_pbr_atlas_authoring_audit_v288.json')['sha256'] and priorUV['continuousUVOverlapPairs']==195
priorPairs=np.load(O/'apron_ornament_continuous_uv_overlap_pairs_v296.npz');polygonOffsets=np.r_[0,np.cumsum([len(ob.data.polygons) for ob in objects])];involved=np.unique(priorPairs['pairs']);bad.update(int(polygonOffsets[priorPairs['triangleObjectIndex'][t]]+priorPairs['trianglePolygonIndex'][t]) for t in involved)
history=[dict(overlapTexelCenters=overlap,conflictingPolygons=len(bad))];repairs=[];allP=np.asarray(positions,np.float64);reserved=[]
for yy in range(int(.03*W),int(.30*W)-16,16):
    for xx in range(int(.53*W),int(.97*W)-16,16):reserved.append((xx,yy))
assert len(bad)<=len(reserved)
for polygon,cell in zip(sorted(bad),reserved):
    poly=m.polygons[polygon];ids=list(poly.loop_indices);P=allP[list(poly.vertices)];e1=P[1]-P[0];e1/=np.linalg.norm(e1);normal=np.cross(P-P[0],np.roll(P,-1,axis=0)-P[0]).sum(0);normal/=np.linalg.norm(normal);e2=np.cross(normal,e1);planar=np.column_stack(((P-P[0])@e1,(P-P[0])@e2));planar-=planar.min(0);span=planar.max();assert span>1e-10
    old=uv[ids].copy();uv[ids]=(planar/span*10+np.array(cell)+3)/W;repairs.append(dict(polygon=polygon,cell=[*cell,16,16],loopCount=len(ids),oldUV=old.tolist(),newUV=uv[ids].tolist(),method='Actual polygon projected to its local geometry plane; one reserved nonoverlapping cell, no geometry change.'))
uvlayer.data.foreach_set('uv',uv.astype(np.float32).ravel());uv=np.asarray([x.uv[:] for x in uvlayer.data],np.float64);overlap,degenerate,bad=raster();history.append(dict(overlapTexelCenters=overlap,conflictingPolygons=len(bad)));assert overlap==0 and degenerate==0,(overlap,degenerate,len(bad))
loopStart=0
for ob,row in zip(objects,rows):
    count=len(ob.data.loops);local=uv[loopStart:loopStart+count].astype(np.float32);ob.data.uv_layers.active.data.foreach_set('uv',local.ravel());row['uvSHA256']=hashlib.sha256(local.tobytes()).hexdigest();row['localUVRepairCount']=sum(loopStart<=m.polygons[x['polygon']].loop_start<loopStart+count for x in repairs);loopStart+=count
assert loopStart==len(uv)
sys.path.insert(0,str(R/'Tools'));from coelho_uv_triangle_sat import overlaps,unit_tests
assert unit_tests();actualTriangles=uv[np.asarray([t.loops[:] for t in m.loop_triangles],np.int32)];continuousPairs,broadCount=overlaps(actualTriangles);assert len(continuousPairs)==0,('Continuous overlaps after local repair',len(continuousPairs))
print('ATLAS301_CONTINUOUS_UV',json.dumps(dict(overlapPairs=len(continuousPairs),broadphasePairs=broadCount,unitTestsPassed=True)),flush=True)

audit=dict(version='v301',coveredTexelCenters=int((owner>=0).sum()),interiorOverlapTexelCenters=overlap,degenerateUVTriangles=degenerate,resolution=[W,W],subpixelContinuousOverlapsNotProven=False,geometryUnchanged=True,localRepairHistory=history,localRepairs=repairs,continuousOverlapPairs=0,continuous2DGridBroadphasePairs=broadCount,continuousToleranceUV=1e-12,continuousUnitTestsPassed=True,continuousMethod='Inclusive 128x128 grid actual triangle AABB, six normalized 2D edge-axis strict SAT',prior288PixelCleanBut195ContinuousPairsRejected=True,failed285NoBakeOrModelSaved=True)
(O/'apron_ornament_atlas_uv_audit_v301.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print('ATLAS301_UV',json.dumps(dict(covered=audit['coveredTexelCenters'],history=history,locallyRepairedPolygons=len(repairs))),flush=True)
sourceMats=[]
for label,color,rough in [('Gold',(.60,.335,.115,1),.25),('Blue',(.012,.048,.095,1),.24)]:
    mat=bpy.data.materials.new('DIAGNOSTIC_CoelhoBake.'+label+'.301');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Base Color'].default_value=color;bs.inputs['Metallic'].default_value=1;bs.inputs['Roughness'].default_value=rough;bs.inputs['Coat Weight'].default_value=0
    coord=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=12000 if label=='Gold' else 1500;noise.inputs['Detail'].default_value=2;l.new(coord.outputs['Position'],noise.inputs['Vector']) if coord.outputs.get('Position') else None
    # Geometry Position is in metres; never use camera illumination as albedo.
    geom=n.new('ShaderNodeNewGeometry');l.new(geom.outputs['Position'],noise.inputs['Vector']);rr=n.new('ShaderNodeMapRange');rr.inputs['From Min'].default_value=0;rr.inputs['From Max'].default_value=1;rr.inputs['To Min'].default_value=.235 if label=='Gold' else .234;rr.inputs['To Max'].default_value=.265 if label=='Gold' else .246;l.new(noise.outputs['Fac'],rr.inputs['Value']);l.new(rr.outputs['Result'],bs.inputs['Roughness'])
    sourceMats.append(mat);m.materials.append(mat)
scene.render.engine='CYCLES';scene.cycles.samples=8;scene.render.bake.use_selected_to_active=False;scene.render.bake.margin=2;scene.render.bake.margin_type='EXTEND'
for ob in scene.objects:
    if ob.type in {'MESH','CURVE'}:ob.hide_render=ob!=temp
bpy.ops.object.select_all(action='DESELECT');temp.hide_set(False);temp.select_set(True);bpy.context.view_layer.objects.active=temp;maps={}
for label,socket in [('basecolor','Base Color'),('roughness','Roughness'),('metallic','Metallic'),('normal','Normal')]:
    image=bpy.data.images.new('Alice.Coelho.Ornaments.'+label+'.4096.v301',W,W,alpha=False);image.colorspace_settings.name='sRGB' if label=='basecolor' else 'Non-Color';emissions=[]
    for mat in sourceMats:
        n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');out=n.get('Material Output');tex=n.new('ShaderNodeTexImage');tex.image=image;n.active=tex
        for node in n:node.select=node==tex
        if label!='normal':
            em=n.new('ShaderNodeEmission');inp=bs.inputs[socket]
            if inp.is_linked:l.new(inp.links[0].from_socket,em.inputs['Color'])
            else:
                value=inp.default_value;em.inputs['Color'].default_value=(value,value,value,1) if isinstance(value,(int,float)) else value
            l.new(em.outputs[0],out.inputs['Surface']);emissions.append((mat,em))
    print('ATLAS301_BAKE_BEGIN',label,flush=True);bpy.ops.object.bake(type='NORMAL' if label=='normal' else 'EMIT',normal_space='TANGENT',use_clear=True)
    for mat,em in emissions:mat.node_tree.nodes.remove(em);mat.node_tree.links.new(mat.node_tree.nodes.get('Principled BSDF').outputs[0],mat.node_tree.nodes.get('Material Output').inputs['Surface'])
    image.file_format='PNG';image.filepath_raw=str(T/('alice_coelho_ornaments_'+label+'_4096_v301.png'));image.save();image.pack();maps[label]=dict(path=Path(image.filepath_raw).relative_to(R).as_posix(),sha256=sha(Path(image.filepath_raw)),size=[W,W],packed=True,colorSpace=image.colorspace_settings.name)
    print('ATLAS301_BAKE_END',label,flush=True)
bpy.data.objects.remove(temp,do_unlink=True)
finalMats=[]
for label in ['Gold','Blue']:
    mat=bpy.data.materials.new('Alice.Coelho.Ornaments.'+label+'.AtlasPBR4K.v301');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');bs.inputs['Coat Weight'].default_value=0;uvnode=n.new('ShaderNodeUVMap');uvnode.uv_map='CoelhoOrnamentAtlas4K.v301'
    for role,socket in [('basecolor','Base Color'),('roughness','Roughness'),('metallic','Metallic'),('normal','Normal')]:
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images['Alice.Coelho.Ornaments.'+role+'.4096.v301'];l.new(uvnode.outputs['UV'],tex.inputs['Vector'])
        if role=='normal':
            normal=n.new('ShaderNodeNormalMap');normal.uv_map=uvnode.uv_map;l.new(tex.outputs['Color'],normal.inputs['Color']);l.new(normal.outputs['Normal'],bs.inputs['Normal'])
        else:l.new(tex.outputs['Color'],bs.inputs[socket])
    mat['scope']='Actual own-UV 4K bake. Metallic blue is an art-directed opaque reflection approximation, not optically accurate sapphire. No new photographic detail, no camera shadows in albedo.';finalMats.append(mat)
for ob,row in zip(objects,rows):
    for i,mat in enumerate(finalMats):ob.data.materials[i]=mat
    assert hashlib.sha256(np.asarray([v.co[:] for v in ob.data.vertices],np.float32).tobytes()).hexdigest()==row['geometryPositionSHA256'];ob.hide_render=True;ob.hide_set(True);ob['scope']='Own PBR4K atlas on exact casting267 geometry. Await saved UV/image/export/reference verification. Rig/physics not approved.'
for label in ['character','apron','chain','cord','lace']:bpy.data.objects['Alice.Coelho.WholeCheckpoint181.'+label].hide_render=False
out=O/'Dress/alice_coelho_apron_ornaments_pbr_atlas_candidate_v301.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==a['sha256']
report=dict(version='v301',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourceCandidate='v267',sourceSHA256=a['sha256'],newObjects=rows,maps=maps,UVMapName='CoelhoOrnamentAtlas4K.v301',ownUVAtlasBaked=True,UVPixelAudit=audit,allGeometryPositionsAndFacesPreserved=True,photoReferenceProjectionPerformed=False,newPhotographicDetailNotCreated=True,blueAppearanceModel='Art-directed opaque metallic colored reflection; gemstone optics are not proven.',allNewObjectsDefaultHidden=True,requiresIndependentReopenUVMapImageGeometryAndFormatVerification=True,rigged=False,physicsVerified=False,fidelityApproved=False,notIntegrated=True,notPublished=True,productionComplete=False,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'apron_ornament_pbr_atlas_authoring_audit_v301.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ATLAS301_SAVED_AWAIT_REOPEN_AND_VISUAL_REVIEW',flush=True)
