"""Local recoverable foliate setting study; no body, cloth, chains or gem edits."""
import bpy,bmesh,numpy as np,json,hashlib,time,sys
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';sys.path.insert(0,str(R/'Tools'))
from coelho_cast_mesh import topology,object_from_mesh,tube,tidy_boolean_result
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
start=time.time();pub=read(O/'publication_complete_v344.json');assert pub['wholeCheckpoint']=='v323' and pub['ownPublicationLeaseReleasedAfterVerification']
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
source=R/pub['release']['files']['blend']['path'];assert sha(source)==pub['release']['files']['blend']['sha256']
old=read(O/'apron_ornament_cast_mounts_authoring_audit_v267.json');integration=read(O/'apron_ornament_whole_integration_audit_v318.json')
col=bpy.data.collections.new('COELHO_ORNAMENT_FOLIATE361_LOCAL_NOT_APPROVED');bpy.context.scene.collection.children.link(col)
temp=bpy.data.collections.new('DIAGNOSTIC_FOLIATE361_TEMP');bpy.context.scene.collection.children.link(temp)
gold=bpy.data.materials.new('Alice.Coelho.FoliateCast.Gold.PROVISIONAL361');gold.use_nodes=True;bs=gold.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.60,.335,.115,1);bs.inputs['Metallic'].default_value=1;bs.inputs['Roughness'].default_value=.25
blue=bpy.data.materials.new('Alice.Coelho.CornerCast.Blue.PROVISIONAL361');blue.use_nodes=True;bs=blue.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.012,.048,.095,1);bs.inputs['Metallic'].default_value=1;bs.inputs['Roughness'].default_value=.24;bs.inputs['Coat Weight'].default_value=0
def bezier(points,n=20):
 p=np.asarray(points,float);t=np.linspace(0,1,n,endpoint=False)[:,None];return (1-t)**3*p[0]+3*(1-t)**2*t*p[1]+3*(1-t)*t*t*p[2]+t**3*p[3]
records=[]
for row in old['newObjects']:
 original=bpy.data.objects['Alice.Coelho.WholeCheckpoint318.ornament_'+row['id']];m=original.data;P=np.asarray([v.co[:] for v in m.vertices],np.float32);center=np.asarray(row['gemCenter']);c=row['components'][-1];assert c['type']=='cast_gold_setting_and_mounts';lo=c['firstVertex'];hi=lo+c['vertices'];F=[tuple(i-lo for i in p.vertices) for p in m.polygons if min(p.vertices)>=lo and max(p.vertices)<hi];assert len(F)==c['faces'];cast=object_from_mesh('Coelho.FoliateCast361.'+row['id'],P[lo:hi],F,temp,center)
 a=1.08*row['gemWidthM']/2;b=1.08*row['gemHeightM']/2;factor=.60 if row['id'].startswith('outer') else 1.;stages=[];paths=[];parts=[]
 corners=np.array([[0,b],[a,0],[0,-b],[-a,0]])
 rim=[]
 for k in range(4):
  for f in np.linspace(0,1,8,endpoint=False):
   uv=corners[k]*(1-f)+corners[(k+1)%4]*f;rim.append(center+[uv[0],-.0010,uv[1]])
 rimP,rimF=tube(rim,.00030*factor,True,8);parts.append(('front_rim',object_from_mesh('Coelho.CornerRim361.'+row['id'],rimP,rimF,temp,center)))
 for k,uv in enumerate(corners):
  local=bmesh.new();bmesh.ops.create_icosphere(local,subdivisions=2,radius=1.);local.verts.ensure_lookup_table();local.faces.ensure_lookup_table();radius=np.array([.00065,.00030,.00090])*factor
  if k%2:radius[[0,2]]=radius[[2,0]]
  angle=.113+k*.193;rot=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]]);points=(np.array([v.co[:] for v in local.verts])@rot.T)*radius+center+[uv[0],-.0010,uv[1]];faces=[tuple(v.index for v in f.verts) for f in local.faces];local.free();parts.append(('corner_lobe_'+str(k),object_from_mesh('Coelho.CornerLobe361.'+row['id'],points,faces,temp,center)));paths.append(dict(corner=k,position=(center+[uv[0],-.0010,uv[1]]).tolist(),radiusM=radius.tolist()))
 for label,leaf in parts:
  bpy.ops.object.select_all(action='DESELECT');cast.select_set(True);bpy.context.view_layer.objects.active=cast;mod=cast.modifiers.new('Exact.CompactCorner361.Union','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=leaf;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(leaf,do_unlink=True);cleanup=tidy_boolean_result(cast);q=topology(cast)
  assert q['connectedComponents']==1 and q['nonManifoldEdges']==q['zeroAreaTriangles']==0 and q['signedVolumeM3']>0,(row['id'],label,q)
  stages.append(dict(part=label,result=q,cleanup=cleanup));print('COMPACT361_CAST_UNION',row['id'],label,flush=True)
 castP=np.asarray([v.co[:] for v in cast.data.vertices])+center;castF=[tuple(p.vertices) for p in cast.data.polygons];worldCast=object_from_mesh('Coelho.NewCastingWorldPrecision361.'+row['id'],castP,castF,temp,np.zeros(3));worldCleanup=tidy_boolean_result(worldCast);worldTopology=topology(worldCast);assert worldTopology['connectedComponents']==1 and worldTopology['nonManifoldEdges']==worldTopology['zeroAreaTriangles']==0 and worldTopology['signedVolumeM3']>0,(row['id'],'World float32 casting',worldTopology);castP=np.asarray([v.co[:] for v in worldCast.data.vertices]);castF=[tuple(p.vertices) for p in worldCast.data.polygons];outP=P[:lo].tolist()+castP.tolist();outF=[tuple(p.vertices) for p in m.polygons if max(p.vertices)<lo]+[tuple(lo+i for i in f) for f in castF];indices=[p.material_index for p in m.polygons if max(p.vertices)<lo]+[0]*len(castF)
 mesh=bpy.data.meshes.new('Coelho.Ornament.Foliate361.'+row['id']);mesh.from_pydata(outP,[],outF);mesh.update();mesh.materials.append(gold);mesh.materials.append(blue)
 for p,mi in zip(mesh.polygons,indices):p.material_index=mi;p.use_smooth=mi==0
 ob=bpy.data.objects.new('Alice.Coelho.Apron.Ornament.'+row['id']+'.Candidate.v361',mesh);col.objects.link(ob);ob.hide_render=True;ob.hide_set(True);group=ob.vertex_groups.new(name='Ornament.Root.'+row['id']);group.add(list(range(len(outP))),1,'REPLACE')
 bpy.ops.object.select_all(action='DESELECT');ob.hide_set(False);ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.008);bpy.ops.object.mode_set(mode='OBJECT');mesh.uv_layers.active.name='CoelhoFoliateProvisionalUV361';ob.hide_set(True)
 assert np.array_equal(np.asarray([v.co[:] for v in mesh.vertices],np.float32)[:lo],P[:lo]);oldFaces=[tuple(p.vertices) for p in m.polygons if max(p.vertices)<lo];assert outF[:len(oldFaces)]==oldFaces
 ob['scope']='Compact corner lobes and a front gold rim modeled in 3D as a reference-guided relief study. Only cast changed; gem/rings/tassel fibers exact. Relief depth and corner silhouette inferred, not fidelity approved. New UV unbaked, clean constant provisional materials; do not publish this candidate.'
 components=[dict(x) for x in row['components'][:-1]]+[dict(type='cast_gold_setting_compact_corner_and_mounts',firstVertex=lo,vertices=len(castP),faces=len(castF))]
 records.append(dict(row,object=ob.name,components=components,vertices=len(outP),faces=len(outF),castTopology=worldTopology,worldCoordinateFloat32CastingCleanup=worldCleanup,castUnionStages=stages,foliatePaths=paths,allNonCastVertexCoordinatesAndFacesExactlyPreserved=True,compactCornerLobeCount=4,geometryPositionSHA256=hashlib.sha256(np.asarray(outP,np.float32).tobytes()).hexdigest(),ownUVRebuiltButUnbaked=True,rootGroupOnlyNotRig=True));bpy.data.objects.remove(cast,do_unlink=True);bpy.data.objects.remove(worldCast,do_unlink=True)
 bpy.context.view_layer.update()
bpy.data.collections.remove(temp);assert not bpy.data.libraries
out=O/'Dress/alice_coelho_apron_ornaments_compact_corner_cast_candidate_v361.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(source)==pub['release']['files']['blend']['sha256']
report=dict(previous355RejectedAfterIndependentSavedFloat32Audit=True,newBeadFacetsRotatedBeforeEllipsoidScale=True,strictTopologyToleranceUnchanged=True,version='v361',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourceWhole='v318',sourceSHA256=pub['release']['files']['blend']['sha256'],newObjects=records,wholeCheckpoint318Preserved=True,originalGemChainsAndTasselsExactlyPreserved=True,reference='Assets/Characters/alice_coelho/References/ChatGPT Image 7 de jun. de 2026, 13_26_40 (5).png',referenceSHA256='91b93bd3d72155ef1edf5dc0aec1fbca43dffd98e355a10342080c3320d5bcd9',cornerReliefDepthInferred=True,ownPBR4KMustBeRebakedBeforeIntegration=True,requiresSavedTopologyContactsAndVisualReview=True,rigged=False,physicsVerified=False,fidelityApproved=False,productionComplete=False,notIntegrated=True,notPublished=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'apron_ornament_compact_corner_authoring_audit_v361.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('FOLIATE361_SAVED_AWAIT_INDEPENDENT_QA',flush=True)
