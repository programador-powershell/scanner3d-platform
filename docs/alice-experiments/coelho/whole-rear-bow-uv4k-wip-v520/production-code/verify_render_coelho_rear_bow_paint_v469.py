"""Independent saved material/UV/geometry verification and unchanged-camera review renders."""
import bpy,numpy as np,json,hashlib,time
from pathlib import Path
from mathutils import Vector
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';start=time.time();read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(O/'rear_bow_visible_ink_authoring_audit_v467.json');source=R/a['path'];assert Path(bpy.data.filepath).resolve()==source.resolve() and sha(source)==a['sha256'];original=read(O/'rear_bow_layer_authoring_audit_v460.json');arrays=np.load(O/'rear_bow_uv_arrays_v466.npz');rows=[]
def groups(m):return [[(g.group,round(g.weight,9)) for g in v.groups] for v in m.vertices]
for i,row in enumerate(a['newObjects']):
 ob=bpy.data.objects[row['name']];m=ob.data;m.calc_loop_triangles();P=np.asarray([v.co[:] for v in m.vertices],np.float32);T=np.asarray([t.vertices[:] for t in m.loop_triangles],np.int32);U=np.asarray([x.uv[:] for x in m.uv_layers['RearBow.Atlas4K.v466'].data],float)
 assert np.array_equal(P,arrays[f'object{i}_positions']);assert np.array_equal(T,arrays[f'object{i}_triangles']);assert np.array_equal(U,arrays[f'object{i}_uv']);old=bpy.data.objects[row['sourceObject']];assert groups(m)==groups(old.data);assert [g.name for g in ob.vertex_groups]==[g.name for g in old.vertex_groups];assert len(m.materials)==1
 mat=m.materials[0];bs=mat.node_tree.nodes.get('Principled BSDF');assert bs.inputs['Metallic'].default_value==0;uvNode=next(n for n in mat.node_tree.nodes if n.type=='UVMAP');assert uvNode.uv_map=='RearBow.Atlas4K.v466'
 normalMaximum=None
 if 'proceduralSource460' in row:
  referenceObject=bpy.data.objects[row['proceduralSource460']];deps=bpy.context.evaluated_depsgraph_get();ev=referenceObject.evaluated_get(deps);reference=ev.to_mesh();reference.calc_loop_triangles();referenceNormals=np.asarray([n.vector[:] for n in reference.corner_normals],float);mapping={}
  for tri in reference.loop_triangles:
   ids=list(tri.vertices);key=tuple(np.roll(ids,-int(np.argmin(ids))));mapping[key]={int(v):referenceNormals[l] for v,l in zip(tri.vertices,tri.loops)}
  actualNormals=np.asarray([n.vector[:] for n in m.corner_normals],float);errors=[]
  for tri in m.loop_triangles:
   ids=list(tri.vertices);key=tuple(np.roll(ids,-int(np.argmin(ids))))
   for v,l in zip(tri.vertices,tri.loops):errors.append(np.linalg.norm(actualNormals[l]-mapping[key][int(v)]))
  normalMaximum=float(max(errors));assert normalMaximum<.0007;ev.to_mesh_clear()
 rows.append(dict(object=ob.name,positionsTrianglesUVExact466=True,pinWeightsExact466=True,maximumSavedSource460CornerNormalError=normalMaximum,normalTolerance=.0007 if normalMaximum is not None else None,rigged=False))
for name,before in original['wholeSourceSignatures'].items():
 ob=bpy.data.objects[name];m=ob.data;actual=dict(positions=hashlib.sha256(np.asarray([v.co[:] for v in m.vertices],np.float32).tobytes()).hexdigest(),faces=hashlib.sha256(json.dumps([list(p.vertices) for p in m.polygons]).encode()).hexdigest(),uv=[hashlib.sha256(np.asarray([u.uv[:] for u in l.data],np.float32).tobytes()).hexdigest() for l in m.uv_layers],matrix=[list(r) for r in ob.matrix_world],materials=[mat.name for mat in m.materials]);assert actual==before
maps=[]
for label,row in a['maps'].items():
 p=R/row['path'];assert sha(p)==row['sha256'];image=bpy.data.images['Alice.Coelho.RearBow.'+label+'.4096.v467'];assert tuple(image.size)==(4096,4096) and image.packed_file;assert hashlib.sha256(image.packed_file.data).hexdigest()==row['sha256'];assert image.colorspace_settings.name==row['colorSpace'];maps.append(dict(label=label,dimensions=list(image.size),packedPNGBytesExact=True,colorSpace=image.colorspace_settings.name))
mask=np.load(O/'rear_bow_projection_masks_v467.npz');visible=mask['visiblePhotoProjection'].astype(bool);assert int(visible.sum())==a['visibleProjectedTexels'];assert not (visible&~mask['covered']).any();assert not (mask['geometryTailPrintedEdge'].astype(bool)&~mask['covered']).any()
audit=dict(version='v469',sourceCandidate='v467',sourceSHA256=a['sha256'],allElevenSavedGeometriesUVWeightsAndTenWholeObjectsExactlyVerified=True,maps=maps,records=rows,visibleProjectionMasksInsideActualCoverageVerified=True,fidelityApproved=False,productionComplete=False,readOnlyNoSaveOrExport=True,requiresActualNativeReferenceInspection=True)
(O/'rear_bow_paint_saved_audit_v469.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print('BOW469_SAVED_GEOMETRY_UV_WEIGHTS_PACKED_MAPS_PASSED',flush=True)
scene=bpy.context.scene;cam=scene.camera;names={r['name'] for r in a['newObjects']};whole=set(original['wholeSourceSignatures']);scene.cycles.samples=24;scene.render.resolution_percentage=100;renders=[]
views=[('whole_back',(0,0,.886),(0,4,0),2.05,(900,1100),True),('whole_rear_threequarter',(0,0,.886),(2,4,0),2.05,(900,1100),True),('bow_back',(0,.14,.985),(0,3,0),.83,(900,1000),True),('bow_left_profile',(0,.14,.985),(-3,0,0),.83,(900,1000),True),('bow_right_profile',(0,.14,.985),(3,0,0),.83,(900,1000),True),('bow_layers_only_back',(0,.14,.985),(0,3,0),.83,(900,1000),False)]
for view,target,direction,scale,res,full in views:
 for ob in scene.objects:
  if ob.type in {'MESH','CURVE','FONT'}:ob.hide_render=ob.name not in (names|whole if full else names)
 cam.location=np.asarray(target)+np.asarray(direction);cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.resolution_x,scene.render.resolution_y=res;p=E/('rear_bow_'+view+'_v469.png');scene.render.filepath=str(p);bpy.ops.render.render(write_still=True);renders.append(dict(view=view,path=p.relative_to(R).as_posix(),sha256=sha(p),target=target,direction=direction,orthoScale=scale));audit.update(renders=renders,elapsedSeconds=time.time()-start);(O/'rear_bow_paint_saved_audit_v469.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print('BOW469_RENDERED',view,flush=True)
assert sha(source)==a['sha256'];audit.update(allSixRendersCompleted=True,elapsedSeconds=time.time()-start);(O/'rear_bow_paint_saved_audit_v469.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print('BOW469_ALL_SIX_RENDERS_COMPLETED_ACTUAL_REVIEW_REQUIRED',flush=True)
