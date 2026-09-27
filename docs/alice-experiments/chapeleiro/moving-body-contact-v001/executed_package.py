"""Archive completed cloth studies and own-photo review without approving them."""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

workspace=Path(__file__).resolve().parents[1]
repo=workspace/'scanner3d-platform'
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
out=repo/'docs/alice-experiments/chapeleiro/moving-body-contact-v001'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(root/'foundation_shared_rig_sewn_cloth_export_v001/generation.json')
entry=g['exports']['foundation'];photo=Path(entry['sourcePhoto'])
assert sha(photo)==entry['sourcePhotoSha256']
assert sha(entry['model'])==entry['modelSha256']=='1c2e1a9a3af242acaaf2dd48e8c482e57e6013f8f7f84e0744012dd13752dc45'
assert sha(g['editableBlend'])==g['editableBlendSha256']
assert Path(g['editableBlend']).stat().st_size==130167778
before=read(root/'xpbd_ivory_black_cloth_v003/actual_sewn_solver_motion.json')
after=read(root/'xpbd_ivory_black_cloth_v004/actual_sewn_solver_motion.json')
old=np.load(before['dataFile']);new=np.load(after['dataFile'])
preserved=[key for key in old.files if key not in ['points','actual_simulation_points']]
assert all(np.array_equal(old[key],new[key]) for key in preserved)
oldbody=read(root/'fixed_closed_body_reference_v001/dynamic_clearance_inspection.json')
newbody=read(root/'xpbd_ivory_black_cloth_v004/fixed_dynamic_clearance_inspection/dynamic_clearance_inspection.json')
bo,bn=np.load(oldbody['dataFile']),np.load(newbody['dataFile'])
for index in range(3):
 for field in ['animated_world_points','animated_triangles']:
  key=f'proxy_{index}_{field}'
  assert np.array_equal(bo[key],bn[key]),key
 triangles=bo[f'proxy_{index}_animated_triangles']
 assert all(np.array_equal(triangles[0],t) for t in triangles)
ccd2=read(root/'moving_body_face_diagnostic_v002/moving_body_face_contacts.json')
ccd=read(root/'moving_body_face_diagnostic_v003/moving_body_face_contacts.json')
c2,c3=np.load(ccd2['dataFile']),np.load(ccd['dataFile'])
assert c2.files==c3.files and all(np.array_equal(c2[k],c3[k]) for k in c2.files)
assert ccd['analyticEnteringExitingTranslatingAndCubicCasesPassed']
assert not out.exists();out.mkdir(parents=True)
inventory=[]
def cp(file,name,digest=None):
 file=Path(file)
 if digest:assert sha(file)==digest,file
 target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
 assert sha(target)==sha(file)
 inventory.append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
def record(name,data):
 target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 inventory.append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
cp(photo,'source_photo.png',entry['sourcePhotoSha256'])
for folder,label,script in [('xpbd_ivory_black_cloth_v004','physical','executed_xpbd_probe.py'),
                          ('xpbd_ivory_black_cloth_v004_surface_deform_v001','detail','executed_surface_deform_refinement.py')]:
 path=root/folder;r=read(path/'actual_sewn_solver_motion.json')
 assert len(r['frames'])==29 and sha(r['dataFile'])==r['dataSha256']
 cp(path/'actual_sewn_solver_motion.json',label+'/actual_motion.json')
 cp(r['dataFile'],label+'/actual_motion.npz',r['dataSha256'])
 cp(path/script,label+'/'+script,r['scriptSha256'])
 cp(root/(folder+'.log'),label+'/execution.log')
 if label=='physical':cp(path/'executed_surface_contact_helper.py',label+'/executed_surface_contact_helper.py',r['surfaceContactHelperSha256'])
for folder,label in [('fixed_closed_body_reference_v001','body/reference'),
                    ('xpbd_ivory_black_cloth_v004/fixed_dynamic_clearance_inspection','body/strain_study')]:
 path=root/folder;r=read(path/'dynamic_clearance_inspection.json')
 assert r['actualBodyTrianglesFrozenBeforeDeformation']
 cp(path/'dynamic_clearance_inspection.json',label+'/contact.json')
 cp(r['dataFile'],label+'/body_and_query_arrays.npz',r['dataSha256'])
 cp(path/'executed_inspection.py',label+'/executed_inspection.py',r['scriptSha256'])
 cp(path/'executed_closed_proxy_helper.py',label+'/executed_closed_proxy_helper.py',r['closedProxyHelperSha256'])
for folder,label in [('v003_fine_fixed_body_contacts','body/previous_fine'),
                    ('xpbd_ivory_black_cloth_v004_surface_deform_v001/fine_recorded_body_contacts','body/new_fine'),
                    ('v096_actual_glb_body_contacts_v001','body/published_glb')]:
 path=root/folder;r=read(path/'recorded_surface_body_contacts.json')
 cp(path/'recorded_surface_body_contacts.json',label+'/contact.json')
 cp(r['dataFile'],label+'/contacts.npz',r['dataSha256'])
 cp(path/'executed_inspection.py',label+'/executed_inspection.py',r['scriptSha256'])
 cp(path/'executed_surface_contact_helper.py',label+'/executed_surface_contact_helper.py')
path=root/'moving_body_face_diagnostic_v003'
cp(path/'moving_body_face_contacts.json','moving_faces/contacts.json')
cp(ccd['dataFile'],'moving_faces/contacts.npz',ccd['dataSha256'])
cp(path/'executed_inspection.py','moving_faces/executed_inspection.py',ccd['scriptSha256'])
cp(path/'executed_point_face_helper.py','moving_faces/executed_point_face_helper.py',ccd['pointFaceHelperSha256'])
cp(root/'moving_body_face_diagnostic_v003.log','moving_faces/execution.log')
for path,name in [(root/'v096_strain_diagnostic_v001.json','prior_strain.json'),
                  (root/'xpbd_ivory_black_cloth_v004/triangle_contact_inspection_v001/triangle_contact_inspection.json','triangles/contact.json'),
                  (root/'xpbd_ivory_black_cloth_v004/triangle_contact_inspection_v001/actual_triangle_crossings.npz','triangles/crossings.npz'),
                  (root/'xpbd_ivory_black_cloth_v004/triangle_contact_inspection_v001/executed_inspection.py','triangles/executed_inspection.py')]:cp(path,name)

sources=[(root/'xpbd_ivory_black_cloth_v003_surface_deform_v001/actual_receiver_review/comparison.json','Tecido anterior'),
         (root/'foundation_shared_rig_sewn_cloth_export_v001/actual_joint_export_review_v001/comparison.json','GLB publicado / v096'),
         (root/'xpbd_ivory_black_cloth_v004_surface_deform_v001/actual_receiver_review/comparison.json','Ensaio de estiramento')]
renders=[]
for col,(path,label) in enumerate(sources):
 review=read(path)
 cp(path,f'review_{col}/comparison.json')
 for frame,view in [(20,'front'),(29,'threequarter')]:
  row=next(r for r in review['renders'] if r['sourcePhysicsFrame']==frame and r['view']==view and r['scope']=='foundation')
  cp(row['file'],f'review_{col}/'+Path(row['file']).name,row['sha256'])
  renders.append({'column':col,'label':label,**row})
for frame in [20,29]:
 selected=[r for r in renders if r['sourcePhysicsFrame']==frame]
 assert all(np.max(np.abs(np.asarray(r['cameraPosition'])-selected[0]['cameraPosition']))<1e-5 for r in selected)
image=Image.new('RGB',(2120,1770),(25,27,31));draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
draw.text((24,20),'CHAPELEIRO / NOVO ESTUDO DE CONTATO / EM REFINAMENTO',font=font,fill='white')
draw.text((24,60),'Foto completa da etapa 01. Mesmas poses e camera. A perna ainda atravessa a anagua.',font=small,fill='#e7d8b9')
photo_image=Image.open(photo).convert('RGB');photo_image.thumbnail((500,1000));image.paste(photo_image,(24,120))
draw.text((24,1130),'Foto original completa / etapa 01',font=small,fill='#e7d8b9')
for item in renders:
 col=item['column'];row=0 if item['sourcePhysicsFrame']==20 else 1
 x,y=590+col*500,120+row*805
 render=Image.open(item['file']).convert('RGBA');render.thumbnail((480,735));image.paste(render,(x,y),render)
 draw.text((x,y+745),item['label'],font=small,fill='white')
 draw.text((x,y+772),f'Pose {item["sourcePhysicsFrame"]} / {item["view"]}',font=small,fill='#e7d8b9')
board=out/'photo_comparison.jpg';image.save(board,quality=95)
inventory.append({'file':board.name,'bytes':board.stat().st_size,'sha256':sha(board)})
record('photo_board_sources.json',{'sourcePhotoSha256':sha(photo),'actualRenders':renders,'sameCameraVerified':True,
                                 'photoBoardSha256':sha(board),'visualApproval':False})
summary={'sourcePhotoSha256':sha(photo),'exactPreservedPhysicalInputArrays':preserved,
         'closedBodyCoordinatesAndFixedTrianglesExactlyEqualInBothStudies':True,
         'movingBroadPhaseOptimizationPreservesAll45RecordedOutputArraysExactly':True,
         'movingAnalyticTestsPassed':True,'actualMovingContacts':ccd['actualFramesAndProxies'],
         'visualAssessment':{'actualNewTwoRendersReviewed':True,
             'observations':['Front pose still exposes black support through the ivory layer.',
                             'The raised leg still passes through the ivory surface in pose 29.',
                             'Waist discontinuities and reference folds, cascades and lace remain unfinished.'],
             'strainStudyApprovedForRigBakeOrPublication':False},
         'maximumPhysicalStretch':{label:{key:max(q['solverMaximumEdgeStretch'] for f in r['frames'] for q in f['pieces'] if q['key']==key)
                                        for key in ['ivory','support','tier1','tier2','tier3']}
                                   for label,r in [('previous',before),('new',after)]},
         'completeAuthoring':{'path':g['editableBlend'],'bytes':Path(g['editableBlend']).stat().st_size,'sha256':g['editableBlendSha256'],'trimmed':False},
         'publishedGlbSha256':entry['modelSha256'],'publishedGlbUnchanged':True,
         'nextCalculation':'Moving point/face response using fixed closed body triangles; full new trajectory still pending.',
         'additionalTripoCreditsConsumed':0,'allLayersFinished':False,'motionVerified':False,'fidelityVerified':False,
         'clothCollisionVerified':False,'finalFbxExported':False,'nextVariantMayStart':False}
record('assessment.json',summary)
protected=read(repo/'docs/alice-experiments/chapeleiro/shared-rig-v096/protected_assets.json')
for row in protected['masters']:assert sha(row['file'])==row['sha256']
record('protected_assets.json',protected)
readme='''# Chapeleiro: moving body contact study, unfinished

Compare the complete own-stage photo in `photo_comparison.jpg` with the actual
same-pose renders: previous measured cloth, published v096 GLB, and the new
strain/normal-velocity trial. Both new trial renders were visually inspected.
The leg still penetrates the ivory layer, black support remains exposed, and
the waist, gathers, cascades, lace, UV/normal polish and all other layers remain
unfinished. This trial is not approved for baking or replacing the GLB.

The complete 29-frame trial only marginally reduces the support's peak stretch
from 5.47 to 5.23. A requested 1.1 unilateral edge bound does not establish
convergence: final contact corrections reintroduce excess strain. Proper
triangle crossings remain 533 and 823 in the two reviewed moving poses.

Body calculation copies are now triangulated in bind geometry before rig
deformation. All 29 poses retain identical closed triangle topology, original
vertices, bone groups and weights; original visible meshes remain untouched.
Both compared studies use exactly equal body coordinates and frozen faces.

Moving point/face tests pass independent entering, exiting, outside-triangle,
translating-body, repeated-root and three-root cases. They record 283 entering
point/face candidates across three selected pose intervals of the old study.
The acceleration filter preserves all 45 output arrays exactly. Those tests
do not implement the full robust cloth collision algorithm: garment edge/edge
contacts, friction, substep response and final contact approval remain pending.

The source includes a provisional moving point/face response with previous
outside and endpoint exterior checks. Its new complete trajectory is still
being calculated and is not included as a completed result here. Source FBXs
provide bones/actions only. No new model is exported in this package.

The full 130,167,778-byte authoring checkpoint remains local without trimming;
the v096 GLB and protected Alice/intact dressed Chapeleiro masters are unchanged.
The final FBX, low-poly delivery, all actions, all stage photographs and the
remaining Chapeleiro layers must be completed before another Alice variant.
No additional Tripo credits or premium operations are used.

Point/face and strain reference: https://graphics.stanford.edu/papers/cloth-sig02/cloth.pdf
'''
(out/'README.md').write_text(readme,encoding='utf-8',newline='\n')
(out/'.gitattributes').write_text('* -text\n',encoding='utf-8',newline='\n')
for name in ['README.md','.gitattributes']:
 file=out/name;inventory.append({'file':name,'bytes':file.stat().st_size,'sha256':sha(file)})
cp(__file__,'executed_package.py')
for row in inventory:
 file=out/row['file'];assert file.stat().st_size==row['bytes'] and sha(file)==row['sha256']
 assert row['bytes']<100*1024*1024
(out/'artifact_inventory.json').write_text(json.dumps({'artifacts':inventory,'totalBytes':sum(r['bytes'] for r in inventory)},indent=2)+'\n',encoding='utf-8',newline='\n')
print('ACTUAL_MOVING_CONTACT_PHOTO_STUDY_PACKAGED',len(inventory),sum(r['bytes'] for r in inventory),flush=True)
