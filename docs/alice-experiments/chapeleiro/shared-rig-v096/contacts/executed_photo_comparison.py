"""Compose the full own-stage photograph with actual equal-camera cloth poses."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
root=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
out=root/'ordered_cloth_contact_photo_review_v001'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
g=read(root/'foundation_shared_rig_v095/generation.json')
photo=g['exports']['foundation']['sourcePhoto']
assert sha(photo)==g['exports']['foundation']['sourcePhotoSha256']
assert sha(g['editableBlend'])==g['editableBlendSha256']
sources=[('xpbd_ivory_black_cloth_v002','Contato anterior'),
         ('xpbd_ivory_black_cloth_v003','Contato entre camadas'),
         ('xpbd_ivory_black_cloth_v003_surface_deform_v001','Transferência do detalhe')]
records=[];renders=[]
for folder,label in sources:
 path=root/folder; r=read(path/'actual_sewn_solver_motion.json')
 assert sha(r['dataFile'])==r['dataSha256'] and len(r['frames'])==29
 assert r['parentEditableSha256']==g['editableBlendSha256'] and r['sourcePhotoSha256']==sha(photo)
 review=read(path/'actual_receiver_review/comparison.json')
 assert review['probeDataSha256']==r['dataSha256'] and len(review['renders'])==2
 for row in review['renders']:
  assert sha(row['file'])==row['sha256']; renders.append({'label':label,**row})
 row={'label':label,'folder':folder,'dataSha256':r['dataSha256'],
      'physicalMaximumStretchByPart':{p['key']:max(q['solverMaximumEdgeStretch'] for f in r['frames'] for q in f['pieces'] if q['key']==p['key']) for p in r['parts']},
      'physical95PercentileStretchPeakByPart':{p['key']:max(q['solverEdgeStretch95Percentile'] for f in r['frames'] for q in f['pieces'] if q['key']==p['key']) for p in r['parts']},
      'maximumSeamGapMeters':max(f['maximumSeamGapMeters'] for f in r['frames']),
      'maximumFullyPinnedErrorMeters':max(f['maximumPhysicalFullyPinnedInputError'] for f in r['frames'])}
 if folder.endswith('surface_deform_v001'):
  contact=read(path/'fine_dynamic_clearance_inspection/dynamic_clearance_inspection.json')
  assert contact['sourcePhysicalDataSha256']==r['dataSha256'] and contact['actualVerticesQueriedPerProxyAndFrame']==22080
  row['contactSurface']='fine_detail_22080_points'
 else:
  contact=read(path/'dynamic_clearance_inspection/dynamic_clearance_inspection.json')
  assert contact['sourcePhysicalDataSha256']==r['dataSha256'] and contact['actualVerticesQueriedPerProxyAndFrame']==9024
  row['contactSurface']='physical_calculator_9024_points'
 assert sha(contact['dataFile'])==contact['dataSha256']
 row['bodyContacts']=[{'proxyIndex':i,'maximumCertainInsideVertices':max(f['proxies'][i]['certainInsideVertices'] for f in contact['frames']),
                      'maximumCertainPenetrationMeters':max(f['proxies'][i]['maximumCertainPenetrationMeters'] for f in contact['frames']),
                      'totalAmbiguousQueries':sum(f['proxies'][i]['ambiguousRayQueries'] for f in contact['frames'])} for i in range(3)]
 if not folder.endswith('surface_deform_v001'):
  triangles=read(path/'triangle_contact_inspection_v001/triangle_contact_inspection.json')
  row['actualTriangleCrossings']=triangles
 records.append(row)
before=np.load(root/sources[0][0]/'actual_sewn_petticoat_frames.npz')
physical=np.load(root/sources[1][0]/'actual_sewn_petticoat_frames.npz')
detail=np.load(root/sources[2][0]/'actual_surface_deform_detail_frames.npz')
unchanged=[key for key in before.files if key not in ['actual_simulation_points','points']]
assert all(np.array_equal(before[key],physical[key]) for key in unchanged)
same_physics=['actual_simulation_points','actual_simulation_skin_targets','simulation_rest_points','simulation_faces','simulation_edges','simulation_loose_edges','simulation_pin_weights','physical_seam_pairs','rig_deformations','bone_names']
assert all(np.array_equal(physical[key],detail[key]) for key in same_physics)
assert not out.exists();out.mkdir()
def write(name,data):(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
write('metrics.json',{'sourcePhotoSha256':sha(photo),'controls':records,'exactlyPreservedInputArrays':unchanged,
                      'exactlyPreservedPhysicalArraysInDetailTransfer':same_physics,
                      'allLayersFinished':False,'clothCollisionVerified':False,'fidelityVerified':False})
im=Image.new('RGB',(2120,1770),(25,27,31));draw=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
draw.text((24,20),'CHAPELEIRO / CONTATO ENTRE ANÁGUAS / EM REFINAMENTO',font=font,fill='white')
draw.text((24,60),'Foto completa da etapa 01. Mesmas poses e câmera. Estudos ainda fora do GLB.',font=small,fill='#e7d8b9')
p=Image.open(photo).convert('RGB');p.thumbnail((500,1000));im.paste(p,(24,120))
draw.text((24,1130),'Foto original completa / etapa 01',font=small,fill='#e7d8b9')
for col in range(3):
 for row in range(2):
  entry=renders[col*2+row]; x,y=590+col*500,120+row*805
  image=Image.open(entry['file']).convert('RGBA');image.thumbnail((480,735));im.paste(image,(x,y),image)
  assert entry['cameraPosition']==renders[row]['cameraPosition']
  draw.text((x,y+745),entry['label'],font=small,fill='white')
  draw.text((x,y+772),f'Pose {entry["sourcePhysicsFrame"]} / {entry["view"]}',font=small,fill='#e7d8b9')
im.save(out/'photo_comparison.jpg',quality=95)
write('actual_photo_board_sources.json',{'sourcePhoto':photo,'sourcePhotoSha256':sha(photo),'actualRenders':renders,
                                      'photoBoardSha256':sha(out/'photo_comparison.jpg'),'visualAssessmentPending':True})
write('checkpoint.json',{'completeAuthoringSha256':g['editableBlendSha256'],'completeAuthoringBytes':Path(g['editableBlend']).stat().st_size,
                         'completeAuthoringUnchanged':True,'foundationGlbSha256':g['exports']['foundation']['modelSha256'],
                         'newResponseBakedIntoGlb':False,'additionalTripoCreditsConsumed':0,
                         'allLayersFinished':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,
                         'finalFbxExported':False,'nextVariantMayStart':False})
print('ACTUAL_ORDERED_CLOTH_PHOTO_BOARD_SAVED',len(renders),flush=True)
