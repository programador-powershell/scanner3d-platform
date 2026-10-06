"""Recoverable rear bow pattern surfaces guided by native board8; no Tripo body/dress cuts."""
import bpy,numpy as np,json,hashlib,time,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';start=time.time()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pub=read(O/'publication_complete_v440.json');assert pub['published'] and pub['ownPublicationLeaseReleasedAfterVerification'] and pub['wholeCheckpoint']=='v424'
assert read(R/'Coordination/Claims/alice_coelho.json')['nonce']=='f88f8d53fab24a619579580190e6207a'
prior=read(O/'apron_ornament_whole_integration_audit_v421.json');src=R/prior['path'];assert Path(bpy.data.filepath).resolve()==src.resolve() and sha(src)==prior['sha256']
ref=R/'Assets/Characters/alice_coelho/References/ChatGPT Image 7 de jun. de 2026, 13_26_42 (8).png';assert sha(ref)=='fb44d70585d08a851ed9161528100a0b772160a44cb185f5b61c2f13ac37b0af'
def signatures():
 out={}
 for row in prior['objects']:
  ob=bpy.data.objects[row['name']];m=ob.data
  out[ob.name]=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([u.uv[:] for u in a.data],np.float32).tobytes()).hexdigest() for a in m.uv_layers],matrix=[list(r) for r in ob.matrix_world],materials=[mat.name for mat in m.materials])
 return out
before=signatures();q=np.load(O/'whole_export_source_character_v424.npz');bvh=BVHTree.FromPolygons(q['positions'].tolist(),q['triangles'].tolist(),all_triangles=True)
def back_surface(x,z):
 hit=bvh.ray_cast(Vector((float(x),2.,float(z))),Vector((0,-1,0)),4.)
 return float(hit[0].y) if hit[0] is not None else .065
col=bpy.data.collections.new('COELHO_REAR_BOW_LAYERS_V447_LOCAL_REVIEW');bpy.context.scene.collection.children.link(col)
def material(name,color,rough):
 m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Sheen Weight'].default_value=.08;bs.inputs['Specular IOR Level'].default_value=.35;return m
navy=material('Alice.Coelho.RearBow.Navy.PROVISIONAL447',(.006,.010,.017),.46);lining=material('Alice.Coelho.RearBow.SatinLining.PROVISIONAL447',(.008,.011,.017),.33);interfacing=material('Alice.Coelho.RearBow.Interfacing.PROVISIONAL447',(.022,.027,.038),.65)
rows=[];z0=1.055
def panel(name,P,F,UV,mat,role,side,thickness,pins):
 mesh=bpy.data.meshes.new(name+'.Mesh');mesh.from_pydata(P,[],F);mesh.update();mesh.materials.append(mat);uv=mesh.uv_layers.new(name='RearBow.PatternUV447')
 for poly in mesh.polygons:
  poly.use_smooth=True
  for loop in poly.loop_indices:uv.data[loop].uv=UV[mesh.loops[loop].vertex_index]
 ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);g=ob.vertex_groups.new(name='Cloth.Pin.Waist');
 for i,w in enumerate(pins):
  if w>0:g.add([i],float(w),'REPLACE')
 mod=ob.modifiers.new('Procedural.Textile.Thickness447','SOLIDIFY');mod.thickness=thickness;mod.offset=0;mod.use_even_offset=False
 ob['reference_board']=ref.relative_to(R).as_posix();ob['role']=role;ob['root_group_is_not_rig']=True;ob['not_final']=True;ob.hide_render=True;ob.hide_set(True)
 P=np.asarray(P,np.float32);assert np.isfinite(P).all();rows.append(dict(name=name,role=role,side=side,vertices=len(P),faces=len(F),midSurfacePositionSHA256=hashlib.sha256(P.tobytes()).hexdigest(),baseFacesSHA256=hashlib.sha256(json.dumps(F).encode()).hexdigest(),uvSHA256=hashlib.sha256(np.asarray(UV,np.float32).tobytes()).hexdigest(),thicknessM=thickness,waistPinGroupOnlyNotRig=True,bounds=[P.min(0).tolist(),P.max(0).tolist()],realPatternGeometry=True,provisionalMaterialNoPhotoProjection=True));return ob
for side,sign in [('left',-1),('right',1)]:
 nu,nv=65,25;P=[];UV=[];pins=[]
 for i in range(nu):
  u=i/(nu-1);s=math.sin(math.pi*u);w=.011+.083*s**.60
  for j in range(nv):
   v=2*j/(nv-1)-1;x=sign*(.015+.140*s*(1+.10*(1-v*v)));z=z0+.013*math.cos(math.pi*u)+w*v
   y=.112+.030*s+.012*math.cos(math.pi*u)+.006*math.cos(3*math.pi*(v+1)/2+.30*s)*s**.65
   P.append((x,y,z));UV.append((u,j/(nv-1)));pins.append(max(0,1-min(u,1-u)/.08))
 F=[]
 for i in range(nu-1):
  for j in range(nv-1):
   a=i*nv+j;f=[a,a+1,a+nv+1,a+nv];F.append(f if sign>0 else f[::-1])
 for role,offset,mat,thick in [('base_loop',0,navy,.00065),('structured_interfacing',-.0014,interfacing,.00045),('satin_lining',-.0027,lining,.00045)]:
  p=[(x,y+offset,z) for x,y,z in P];panel('Alice.Coelho.RearBow.'+side+'.'+role+'.Candidate447',p,F,UV,mat,role,side,thick,pins)
 # Actual printed/lining tail surfaces with a V-cut pattern; no solid wedge or flat proxy.
 nt,nw=41,17;P=[];UV=[];pins=[]
 for i in range(nt):
  t=i/(nt-1);center=sign*(.025+.058*t);width=.025+.029*math.sin(math.pi*t/2);baseZ=z0-.017
  for j in range(nw):
   v=2*j/(nw-1)-1;x=center+width*v;length=.355-.065*(1-abs(v));z=baseZ-t*length
   drop=z0-z;y=.083+.52*drop-.06*drop*drop-.30*x*x+.013+.018*(1-t)**2+.0035*math.cos(2*math.pi*v+.35*t)*math.sin(math.pi*t)**.6
   P.append((x,y,z));UV.append((j/(nw-1),1-t));pins.append(max(0,1-t/.10))
 F=[]
 for i in range(nt-1):
  for j in range(nw-1):a=i*nw+j;F.append([a,a+1,a+nw+1,a+nw])
 for role,offset,mat in [('printed_tail',0,navy),('plain_satin_tail_back',-.0015,lining)]:panel('Alice.Coelho.RearBow.'+side+'.'+role+'.Candidate447',[(x,y+offset,z) for x,y,z in P],F,UV,mat,role,side,.00050,pins)
# Center wrap is a textile strip with actual closed cross-section and UV, covering tucked loop roots.
P=[];UV=[];pins=[];nu,nv=48,9;rootY=.118
for i in range(nu):
 u=i/nu;a=2*math.pi*u
 for j in range(nv):
  v=2*j/(nv-1)-1;P.append((.018*v,rootY+.020*math.cos(a),z0+.036*math.sin(a)));UV.append((u,j/(nv-1)));pins.append(1.)
F=[]
for i in range(nu):
 for j in range(nv-1):a=i*nv+j;b=((i+1)%nu)*nv+j;F.append([a,b,b+1,a+1])
panel('Alice.Coelho.RearBow.center_wrap.Candidate447',P,F,UV,navy,'center_wrap','center',.00065,pins)
# Bound evaluated normal extrusion against each authored vertex; never accept long miter spikes.
bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
for row in rows:
 ob=bpy.data.objects[row['name']];P=np.asarray([v.co[:] for v in ob.data.vertices],float);mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(deps));Q=np.asarray([v.co[:] for v in mesh.vertices],float);assert len(Q)==2*len(P);maximum=max(np.linalg.norm(Q[:len(P)]-P,axis=1).max(),np.linalg.norm(Q[len(P):]-P,axis=1).max());assert maximum<=row['thicknessM']*.501+1e-6,(ob.name,maximum);row['maximumEvaluatedNormalExtrusionM']=float(maximum);row['noMiterAmplification']=True;bpy.data.meshes.remove(mesh)
assert signatures()==before and not bpy.data.libraries
for im in bpy.data.images:
 if im.type=='IMAGE' and im.size[0]:assert im.packed_file
out=O/'Dress/alice_coelho_rear_bow_layers_candidate_v447.blend';assert not out.exists();bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True);assert sha(src)==prior['sha256']
report=dict(smoothParametricBowAndTailShapesInsteadOfPerVertexTripoRayDeformation=True,periodicCenterWrapWeldedBySharedVertexIndices=True,solidifyEvenOffsetMiterAmplificationDisabledAndBounded=True,prior445RejectedForRoughRayDeformationAndDuplicateBandSeam=True,version='v447',path=out.relative_to(R).as_posix(),bytes=out.stat().st_size,sha256=sha(out),sourceWholeVersion='v421',sourceWholeSHA256=prior['sha256'],reference=ref.relative_to(R).as_posix(),referenceSHA256=sha(ref),collection=col.name,newObjects=rows,allTenWholeSourceObjectsPreservedExactly=True,wholeSourceSignatures=before,oldDressNotCutOrDeformed=True,recoverableHiddenAuthoringLayers=True,dimensionsInferredFromNativeBoard8AndCurrentWholeWaist=True,anatomical168cmNotVerified=True,ownPatternUVNotYetPacked4K=True,printedFabricNotYetProjected=True,clockMedallionChainsBustleAndInnerCascadeStillPending=True,requiresSavedGeometryContactAndNativeReferenceComparison=True,rigged=False,clothSimulationVerified=False,physicsVerified=False,fidelityApproved=False,productionComplete=False,notIntegrated=True,notPublished=True,additionalTripoCredits=0,elapsedSeconds=time.time()-start)
(O/'rear_bow_layer_authoring_audit_v447.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('REAR_BOW447_ELEVEN_REAL_PATTERN_LAYERS_SAVED_REQUIRE_INDEPENDENT_REVIEW',flush=True)
