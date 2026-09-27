"""Archive actual cloth results, independent rig and reviewed export, byte exact."""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
workspace=Path(__file__).resolve().parents[1];repo=workspace/'scanner3d-platform'
b=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
out=repo/'docs/alice-experiments/chapeleiro/shared-rig-v096'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(b/'foundation_shared_rig_sewn_cloth_export_v001/generation.json')
entry=g['exports']['foundation'];review_root=b/'foundation_shared_rig_sewn_cloth_export_v001/actual_joint_export_review_v001'
review=read(review_root/'comparison.json');fields=read(b/'foundation_shared_rig_sewn_cloth_export_v001/glb_field_comparison.json')
assert len(review['renders'])==6 and review['modelSha256']==fields['afterModelSha256']==sha(entry['model'])
assert sha(review['dataFile'])==review['dataSha256']
assert fields['originalFourActionArraysPreservedExactly'] and fields['actualWeightValuesPreservedExactly']
assert sha(g['editableBlend'])==g['editableBlendSha256'] and Path(g['editableBlend']).stat().st_size>100*1024*1024
old_review_path=b/'foundation_shared_rig_v095_export_v002/actual_ivory_export_review_v001'
old_review=read(old_review_path/'comparison.json')
assert old_review['modelSha256']=='bccd78d0312de37a67b5b5b5bc49c21079943fc88c670535020a6ac92462295b'
old_poses=read(old_review_path/'actual_pose_measurements.json')
assert sha(old_poses['dataFile'])==old_poses['dataSha256']
old_data=np.load(old_poses['dataFile']);new_data=np.load(review['dataFile'])
fixed_names=[n for n in old_data['bone_names'].tolist() if not n.startswith(('IvoryCloth_','BlackCloth_'))]
assert len(fixed_names)==101
oi=[old_data['bone_names'].tolist().index(n) for n in fixed_names]
ni=[new_data['bone_names'].tolist().index(n) for n in fixed_names]
assert np.array_equal(old_data['actual_joint_deformations'][:,oi],new_data['actual_joint_deformations'][:,ni])
assert not out.exists();out.mkdir(parents=True)
inventory=[]
def cp(source,name,digest=None):
 source=Path(source)
 if digest:assert sha(source)==digest,str(source)
 target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 assert sha(target)==sha(source)
 inventory.append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
def write(name,data):
 target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 inventory.append({'file':name,'bytes':target.stat().st_size,'sha256':sha(target)})
cp(entry['model'],'foundation/skin_study.glb',entry['modelSha256'])
cp(entry['sourcePhoto'],'foundation/source_photo.png',entry['sourcePhotoSha256'])
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/generation.json','foundation/generation.json')
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/glb_field_comparison.json','foundation/glb_field_comparison.json')
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/executed_export.py','foundation/executed_export.py',g['scriptSha256'])
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/glb_field_comparison.log','foundation/glb_field_comparison.log')
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/executed_glb_field_comparison.py','foundation/executed_glb_field_comparison.py',fields['scriptSha256'])
cp(b/'foundation_shared_rig_sewn_cloth_export_v001.log','foundation/actual_export.log')
for file in ['comparison.json','actual_pose_measurements.json','executed_review.py']:
 cp(review_root/file,'foundation/review/'+file)
cp(review['dataFile'],'foundation/review/actual_exported_five_garment_frames.npz',review['dataSha256'])
cp(b/'foundation_shared_rig_sewn_cloth_export_v001/actual_joint_export_review_v001.log','foundation/review/actual_review.log')
for row in review['renders']:cp(row['file'],'foundation/review/'+Path(row['file']).name,row['sha256'])
for folder,label in [('xpbd_ivory_black_cloth_v003','physical'),('xpbd_ivory_black_cloth_v003_surface_deform_v001','detail')]:
 path=b/folder;r=read(path/'actual_sewn_solver_motion.json')
 assert len(r['frames'])==29 and sha(r['dataFile'])==r['dataSha256']
 cp(path/'actual_sewn_solver_motion.json',label+'/actual_motion.json')
 cp(r['dataFile'],label+'/actual_motion.npz',r['dataSha256']);cp(b/(folder+'.log'),label+'/actual_execution.log')
 code='executed_xpbd_probe.py' if label=='physical' else 'executed_surface_deform_refinement.py'
 cp(path/code,label+'/'+code,r['scriptSha256'])
 if label=='physical':cp(path/'executed_surface_contact_helper.py',label+'/executed_surface_contact_helper.py',r['surfaceContactHelperSha256'])
 contact_folder='dynamic_clearance_inspection' if label=='physical' else 'fine_dynamic_clearance_inspection'
 contact=read(path/contact_folder/'dynamic_clearance_inspection.json')
 assert contact['sourcePhysicalDataSha256']==r['dataSha256']
 cp(path/contact_folder/'dynamic_clearance_inspection.json',label+'/contact.json')
 cp(contact['dataFile'],label+'/actual_contact_queries.npz',contact['dataSha256'])
 cp(path/contact_folder/'executed_inspection.py',label+'/executed_contact_inspection.py',contact['scriptSha256'])
 cp(path/contact_folder/'executed_closed_proxy_helper.py',label+'/executed_closed_proxy_helper.py',contact['closedProxyHelperSha256'])
 cp(path/('dynamic_clearance.log' if label=='physical' else 'fine_dynamic_clearance.log'),label+'/actual_contact_execution.log')
 rv=read(path/'actual_receiver_review/comparison.json');assert rv['probeDataSha256']==r['dataSha256']
 cp(path/'actual_receiver_review/comparison.json',label+'/review/comparison.json')
 cp(path/'actual_receiver_review/executed_render.py',label+'/review/executed_render.py',rv['scriptSha256'])
 cp(path/'actual_receiver_review.log',label+'/review/actual_execution.log')
 for row in rv['renders']:cp(row['file'],label+'/review/'+Path(row['file']).name,row['sha256'])
for folder,label in [('xpbd_ivory_black_cloth_v002','previous_triangle_contacts'),('xpbd_ivory_black_cloth_v003','current_triangle_contacts')]:
 path=b/folder/'triangle_contact_inspection_v001';r=read(path/'triangle_contact_inspection.json')
 cp(path/'triangle_contact_inspection.json',label+'/inspection.json')
 cp(r['dataFile'],label+'/actual_triangle_crossings.npz',r['dataSha256'])
 cp(path/'executed_inspection.py',label+'/executed_inspection.py',r['scriptSha256'])
for folder,label in [('five_cage_skin_seed_v002','previous_seed'),('independent_flounce_skin_seed_v001','independent_seed')]:
 path=b/folder;r=read(path/'seed.json')
 cp(path/'seed.json',label+'/seed.json');cp(r['dataFile'],label+'/actual_skin_seed.npz',r['dataSha256'])
 cp(path/'executed_skin_seed.py',label+'/executed_skin_seed.py',r['scriptSha256']);cp(b/(folder+'.log'),label+'/actual_execution.log')
for folder,label in [('sewn_cloth_joint_fit_v001','shared_control_fit'),('independent_flounce_joint_fit_v001','independent_control_fit')]:
 path=b/folder;r=read(path/'fit.json')
 cp(path/'fit.json',label+'/fit.json');cp(r['dataFile'],label+'/actual_joint_fit.npz',r['dataSha256'])
 cp(path/'executed_joint_fit.py',label+'/executed_joint_fit.py',r['scriptSha256']);cp(b/(folder+'.log'),label+'/actual_execution.log')
for folder,filename,code,label in [('foundation_shared_rig_independent_flounces_v003','independent_flounce_rig.json','executed_independent_flounce_rig.py','rig'),
                                  ('foundation_shared_rig_sewn_cloth_v001','sewn_cloth_bake.json','executed_bake.py','bake')]:
 path=b/folder;r=read(path/filename)
 assert sha(r['editableBlend'])==r['editableBlendSha256']
 cp(path/filename,label+'/'+filename);cp(path/code,label+'/'+code,r['scriptSha256']);cp(b/(folder+'.log'),label+'/actual_execution.log')
 write(label+'/complete_authoring_checkpoint.json',{'path':r['editableBlend'],'bytes':r['editableBytes'],'sha256':r['editableBlendSha256'],
    'completeCheckpointRetainedLocally':True,'notTrimmedToFitGitHub':True,'fullBlendDuplicatedInThisGitPackage':False})
for file in ['metrics.json','photo_comparison.jpg','actual_photo_board_sources.json','checkpoint.json']:
 cp(b/'ordered_cloth_contact_photo_review_v001'/file,'contacts/'+file)
cp(workspace/'tools/build_chapeleiro_ordered_contact_review.py','contacts/executed_photo_comparison.py')

write('foundation/actual_body_motion_comparison.json',{'beforeModelSha256':old_review['modelSha256'],'afterModelSha256':entry['modelSha256'],
       'actualFramesCompared':29,'actualBodyAndExteriorJointNames':fixed_names,'actualMatrixMaximumDifference':0.,
       'actualReimportedBodyAndExteriorMatricesIdentical':True,'beforePoseDataSha256':old_poses['dataSha256'],'afterPoseDataSha256':review['dataSha256']})
# Every image stays intact. The same two recorded pose/view pairs are compared.
im=Image.new('RGB',(2120,1770),(25,27,31));draw=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
draw.text((24,20),'CHAPELEIRO / GLB COM BABADOS INDEPENDENTES / EM REFINAMENTO',font=font,fill='white')
draw.text((24,60),'Foto completa da etapa 01. GLB reimportado e tecido medido. Colisões e fidelidade ainda pendentes.',font=small,fill='#e7d8b9')
photo=Image.open(entry['sourcePhoto']).convert('RGB');photo.thumbnail((500,1000));im.paste(photo,(24,120))
draw.text((24,1130),'Foto original completa / etapa 01',font=small,fill='#e7d8b9')
board_rows=[];physical_review=read(b/'xpbd_ivory_black_cloth_v003_surface_deform_v001/actual_receiver_review/comparison.json')
for col,(r,label) in enumerate([(old_review,'GLB anterior / v095'),(physical_review,'Tecido medido'),(review,'GLB com controles independentes')]):
 for row,(frame,view) in enumerate([(20,'front'),(29,'threequarter')]):
  e=next(e for e in r['renders'] if e['sourcePhysicsFrame']==frame and e['view']==view and e['scope']=='foundation')
  assert sha(e['file'])==e['sha256'];board_rows.append({'label':label,**e})
  reference=next(q for q in old_review['renders'] if q['sourcePhysicsFrame']==frame and q['view']==view and q['scope']=='foundation')
  assert max(abs(x-y) for x,y in zip(e['cameraPosition'],reference['cameraPosition']))<1e-5
  x,y=590+col*500,120+row*805;image=Image.open(e['file']).convert('RGBA');image.thumbnail((480,735));im.paste(image,(x,y),image)
  draw.text((x,y+745),label,font=small,fill='white');draw.text((x,y+772),f'Pose {frame} / {view}',font=small,fill='#e7d8b9')
im.save(out/'foundation/photo_vs_actual_sewn_joint_motion.jpg',quality=95)
inventory.append({'file':'foundation/photo_vs_actual_sewn_joint_motion.jpg','bytes':(out/'foundation/photo_vs_actual_sewn_joint_motion.jpg').stat().st_size,'sha256':sha(out/'foundation/photo_vs_actual_sewn_joint_motion.jpg')})
write('foundation/actual_photo_board_sources.json',{'sourcePhotoSha256':entry['sourcePhotoSha256'],'actualRenders':board_rows,'visualAssessmentPending':True})
write('checkpoint.json',{'fullEditableBlend':g['editableBlend'],'fullEditableBytes':g['editableBytes'],'fullEditableSha256':g['editableBlendSha256'],
    'actualModelSha256':entry['modelSha256'],'actualModelBytes':entry['bytes'],'actualSharedBones':209,'actualSkinnedMeshes':229,
    'studyClip':g['sewnClothStudyClip'],'wholeModelInheritedUnchanged':g['exports']['whole']['modelSha256'],
    'allLayersFinished':False,'motionVerified':False,'clothCollisionVerified':False,'fidelityVerified':False,'finalFbxExported':False,
    'nextVariantMayStart':False,'additionalTripoCreditsConsumed':0})
cp(repo/'scripts/verify_chapeleiro_waist_glb.py','helpers/verify_chapeleiro_waist_glb.py')
cp(repo/'blender/chapeleiro_retopo_cloth_assembly.py','helpers/chapeleiro_retopo_cloth_assembly.py')
(out/'.gitattributes').write_text('* -text whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n')
inventory.append({'file':'.gitattributes','bytes':(out/'.gitattributes').stat().st_size,'sha256':sha(out/'.gitattributes')})
write('artifact_inventory.json',{'artifacts':inventory,'totalBytes':sum(r['bytes'] for r in inventory),
                               'allLayersFinished':False,'fidelityVerified':False,'finalFbxExported':False})
print('ACTUAL_INDEPENDENT_CLOTH_PACKAGE_SAVED',len(inventory),flush=True)
