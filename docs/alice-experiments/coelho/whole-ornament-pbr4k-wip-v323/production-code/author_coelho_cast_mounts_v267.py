"""Recoverable cast settings, hollow tassel caps and central charm bail.

Keeps cloth/body and all chain/fiber geometry. All additions need independent
saved topology, actual contact, linkage, UV/PBR and multiview review.
"""
import bpy,numpy as np,json,hashlib,time,sys,math
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';sys.path.insert(0,str(R/'Tools'))
from coelho_cast_mesh import topology,object_from_mesh,tube,hollow_cap,unit,tidy_boolean_result
from coelho_ring_linking import disk_crossings
from coelho_ring_clearance import distances
start=time.time()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
a=read(O/'apron_ornament_linked_rigid_solver_audit_v233.json');source=R/a['path'];assert digest(source)==a['sha256'];assert read(O/'apron_ornament_cast_union_study_v247.json')['allClosedSingleConnectedCast'];assert read(O/'apron_ornament_ring_interlocking_audit_v237.json')['nominalInterlockingFailures']==0
col=bpy.data.collections.new('COELHO_APRON_ORNAMENTS_V249_CAST_MOUNTS_NOT_APPROVED');bpy.context.scene.collection.children.link(col)
temp=bpy.data.collections.new('DIAGNOSTIC_COELHO_CAST_TEMP267');bpy.context.scene.collection.children.link(temp)
gold=bpy.data.materials.new('Alice.Coelho.Ornaments.CastGold.PROVISIONAL.v267');gold.use_nodes=True;bs=gold.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.60,.335,.115,1);bs.inputs['Metallic'].default_value=1;bs.inputs['Roughness'].default_value=.25
gold['scope']='Clean provisional gold shader, no legacy cord normal map. Own UV/PBR4K maps must be baked and verified before approval.'
blue=bpy.data.materials['Alice.Coelho.Ornaments.BlueCrystal.PROVISIONAL.v201'];records=[]
for row in a['newObjects']:
    original=bpy.data.objects[row['object']];assert np.array_equal(np.asarray(original.matrix_world),np.eye(4));P=np.asarray([v.co[:] for v in original.data.vertices],np.float32);oldCenter=np.asarray(row['gemCenter']);center=oldCenter.copy();shift=np.array([0,0,-.0025]);center+=shift;parts=[];inputRows=[]
    def source_component(c):
        lo=c['firstVertex'];hi=lo+c['vertices'];faces=[tuple(i-lo for i in p.vertices) for p in original.data.polygons if min(p.vertices)>=lo and max(p.vertices)<hi];assert len(faces)==c['faces'];return P[lo:hi].astype(float),faces
    def add_cast(label,points,faces):
        ob=object_from_mesh('Coelho.CastTemp267.'+row['id']+'.'+label,points,faces,temp,center);parts.append(ob);inputRows.append(dict(role=label,topology=topology(ob)));return ob
    for c in row['components']:
        if c['type'] in ['gold_outer_setting','gold_inner_rim','gold_prong']:
            points,faces=source_component(c);add_cast(c['type'],points+shift,faces)
    assert len(parts)==6;mountData={}
    connector=next((c for c in row['components'] if c['type']=='tassel_connector'),None)
    if connector:
        points,faces=source_component(connector);line=points.reshape(2,6,3).mean(1);oldLine=line.copy();line[0]=center+[0,-.0006,-1.08*row['gemHeightM']/2];newP,newF=tube(line,.0006,False,8);add_cast('tassel_adapter_clear_of_gem_tip',newP,newF);capP,capF=hollow_cap(line[-1]);add_cast('hollow_tassel_cap',capP,capF);mountData=dict(tasselAdapterBefore=oldLine.tolist(),tasselAdapterAfter=line.tolist(),hollowCapRoot=line[-1].tolist(),hollowCapOuterRadiusM=.003,hollowCapBottomInnerRadiusM=.0026,hollowCapDropM=.003,individualFiberCoordinatesPreserved=True,fiberRootRigMountNotAuthored=True)
    if True:
        last=next(c for c in reversed(row['components']) if c['type']=='individual_connector_ring');lastP,_=source_component(last);lastPath=lastP.reshape(20,6,3).mean(1);lastC=lastPath.mean(0);U=unit(lastPath[0]-lastC);V=unit(lastPath[5]-lastC-U*np.dot(lastPath[5]-lastC,U));N=unit(np.cross(U,V));bailC=lastC+U*.00283;angles=np.arange(32)*2*np.pi/32+.113;bailPath=bailC+np.cos(angles)[:,None]*U*.0025+np.sin(angles)[:,None]*N*.0010;forward=disk_crossings(lastPath,bailPath);reverse=disk_crossings(bailPath,lastPath);assert abs(forward['linkingNumber'])==abs(reverse['linkingNumber'])==1 and not forward['boundaryAmbiguous'] and not reverse['boundaryAmbiguous'];assert float(distances(lastPath[None],bailPath[None])[0])>.00065;bailP,bailF=tube(bailPath,.0003,True,8);add_cast('gem_upper_bail',bailP,bailF);apex=center+[0,-.0006,1.08*row['gemHeightM']/2];bailLow=bailC+U*.0025;stemDirection=unit(bailLow-apex);stemP,stemF=tube([apex-stemDirection*.00018,bailLow+stemDirection*.00018],.0004,False,8);add_cast('gem_bail_cast_stem',stemP,stemF);mountData.update(dict(gemRigidShiftM=shift.tolist(),bailCenterline=bailPath.tolist(),lastChainRingComponentFirstVertex=last['firstVertex'],preBooleanBailNominalLinkOne=True,topologyTestDoesNotVerifyCastSurfaceClearance=True))
    cast=parts[0];stages=[]
    order=parts[2:6]+[parts[1]]+parts[6:]
    for operand in order:
        current=topology(cast)
        if 'gem_bail_cast_stem' in operand.name and current['connectedComponents']==1 and current['nonManifoldEdges']==0 and current['zeroAreaTriangles']==0:
            stages.append(dict(role=operand.name,unusedRedundantStem=True,reason='The upper bail already forms one closed positive cast with the setting; adding a redundant crossing stem is unnecessary.',result=current));bpy.data.objects.remove(operand,do_unlink=True);continue
        bpy.ops.object.select_all(action='DESELECT');cast.select_set(True);bpy.context.view_layer.objects.active=cast;mod=cast.modifiers.new('Exact.Cast.Union267','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=operand;bpy.ops.object.modifier_apply(modifier=mod.name);preCleanup=topology(cast);cleanup=tidy_boolean_result(cast) if preCleanup['nonManifoldEdges'] or preCleanup['zeroAreaTriangles'] else None;stages.append(dict(role=operand.name,result=topology(cast),microscopicBooleanCleanup=cleanup));print('CAST_UNION267_STAGE',row['id'],json.dumps(stages[-1]),flush=True);bpy.data.objects.remove(operand,do_unlink=True)
    finalCastTriangulationCleanup=tidy_boolean_result(cast);castTopology=topology(cast);assert castTopology['connectedComponents']==1 and castTopology['nonManifoldEdges']==0 and castTopology['zeroAreaTriangles']==0 and castTopology['signedVolumeM3']>0,(row['id'],castTopology)
    castP=np.asarray([v.co[:] for v in cast.data.vertices])+center;castF=[tuple(p.vertices) for p in cast.data.polygons];outP=[];outF=[];material=[];components=[];preserved=[]
    def append(label,points,faces,mi,sourceC=None):
        offset=len(outP);outP.extend(np.asarray(points).tolist());outF.extend(tuple(offset+i for i in f) for f in faces);material.extend([mi]*len(faces));c=dict(type=label,firstVertex=offset,vertices=len(points),faces=len(faces));components.append(c)
        if sourceC:preserved.append(dict(sourceFirstVertex=sourceC['firstVertex'],newFirstVertex=offset,vertices=len(points),type=label,rigidShiftM=shift.tolist() if label=='blue_crystal_table_crown_pavilion' else [0,0,0]))
    for c in row['components']:
        if c['type'] in ['gold_outer_setting','gold_inner_rim','gold_prong','tassel_connector']:continue
        points,faces=source_component(c)
        if c['type']=='blue_crystal_table_crown_pavilion':points+=shift
        append(c['type'],points,faces,1 if c['type']=='blue_crystal_table_crown_pavilion' else 0,c)
    append('cast_gold_setting_and_mounts',castP,castF,0);bpy.data.objects.remove(cast,do_unlink=True)
    m=bpy.data.meshes.new('Coelho.Ornament.CastMounts.'+row['id']+'.v267');m.from_pydata(outP,[],outF);m.update();m.materials.append(gold);m.materials.append(blue)
    for p,mi in zip(m.polygons,material):p.material_index=mi;p.use_smooth=mi==0
    ob=bpy.data.objects.new('Alice.Coelho.Apron.Ornament.'+row['id']+'.Candidate.v267',m);col.objects.link(ob);g=ob.vertex_groups.new(name='Ornament.Root.'+row['id']);g.add(list(range(len(m.vertices))),1,'REPLACE');bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.008);bpy.ops.object.mode_set(mode='OBJECT');m.uv_layers.active.name='CoelhoOrnamentUV4K';ob.hide_render=True;ob.hide_set(True);ob['scope']='Recoverable cast metal union, hollow tassel caps and central bail. Original body/cloth, rings and fibers preserved. UV is provisional unbaked. Component/contact/linkage/reference/rig/physics review required.'
    newP=np.asarray([v.co[:] for v in m.vertices],np.float32)
    for pair in preserved:
        old=P[pair['sourceFirstVertex']:pair['sourceFirstVertex']+pair['vertices']];new=newP[pair['newFirstVertex']:pair['newFirstVertex']+pair['vertices']]
        if pair['type']!='blue_crystal_table_crown_pavilion' :assert np.array_equal(old,new)
        else:assert np.linalg.norm(new.astype(float)-old-shift,axis=1).max()<1e-7
    records.append(dict(row,object=ob.name,vertices=len(outP),faces=len(outF),components=components,gemCenter=center.tolist(),castTopology=castTopology,finalExplicitTriangulationCleanup=finalCastTriangulationCleanup,castInputParts=inputRows,unionStages=stages,newMounts=mountData,preservedSourceComponents=preserved,allChainAndIndividualFiberCoordinatesExactlyPreserved=True,ownUVRebuilt=True,UVMapName='CoelhoOrnamentUV4K',own4KMaterialMapsNotBaked=True,legacyCordGoldNormalMapNotReused=True,rootGroupOnlyNotRig=True))
    print('CAST_MOUNTS267_AUTHORED',row['id'],json.dumps(castTopology),flush=True)
bpy.data.collections.remove(temp);out=O/'Dress/alice_coelho_apron_ornaments_cast_mounts_candidate_v267.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert digest(source)==a['sha256'];report=dict(version='v267',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=digest(out),source=dict(path=source.relative_to(R).as_posix(),sha256=a['sha256']),newObjects=records,allOldSourcesAndWhole181Preserved=True,newObjectsDefaultHidden=True,allChainAndFiberCoordinatesExactlyPreserved=True,allGemRigidPositionAdjustmentM=.0025,hollowTasselCapsAuthored=4,allGemBailsAuthored=5,ownUVRebuiltButUnbaked=True,cleanProvisionalGoldShaderWithoutWrongLegacyNormalMap=True,actualCastGeometryExplicitlyTriangulated=True,requiresIndependentSavedComponentContactLinkageAndVisualReview=True,rigged=False,physicsVerified=False,fidelityApproved=False,productionComplete=False,notIntegrated=True,notPublished=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start);(O/'apron_ornament_cast_mounts_authoring_audit_v267.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CAST_MOUNTS267_SAVED_AWAIT_INDEPENDENT_QA',flush=True)
