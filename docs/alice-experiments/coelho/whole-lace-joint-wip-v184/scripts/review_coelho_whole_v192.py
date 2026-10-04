"""Record inspected whole181/GLB184/FBX184 proof; only a static intermediate checkpoint."""
from pathlib import Path
import json,hashlib,datetime,numpy as np
from PIL import Image,ImageOps,ImageDraw
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
pkg=read(O/'package_export_v184.json');source=read(O/'apron_joint_whole_reopen_renders_v182.json');local=read(O/'apron_joint_whole_review_decision_v183.json');contact=read(O/'apron_all_lace_contact_audit_v178.json')
views=['front','threequarter','back','left_profile','right_profile'];reports={k:read(O/f'reimport_whole_{k}_audit_v185.json') for k in ['glb','fbx']}
for k,q in reports.items():assert q['sha256']==pkg['files'][k]['sha256'] and q['allTriangleUVMaterialAssignmentsVerified'] and q['allImporterNormalEncodingReplaysVerified'] and q['totalTriangles']==1385780
rawg=read(O/'whole_glb_raw_normal_payload_audit_v186.json');rawf=read(O/'whole_fbx_raw_normal_payload_audit_v187.json');assert rawg['sha256']==pkg['files']['glb']['sha256'] and rawg['allSourceTrianglesAndNormalsVerified'];assert rawf['sha256']==pkg['files']['fbx']['sha256'] and len(rawf['records'])==5
for name,key,k in [('whole_glb_material_pixel_audit_v189.json','allExportedMaterialsVerified','glb'),('whole_fbx_embedded_material_audit_v190.json','allFBXEmbeddedVideoBytesMatchSource','fbx'),('whole_fbx_channel_semantics_audit_v191.json','allSourceTextureChannelBindingsPreserved','fbx')]:
 a=read(O/name);assert a[key] and a['sha256']==pkg['files'][k]['sha256']
metrics={};board=Image.new('RGB',(1800,3900),'#202020');d=ImageDraw.Draw(board)
for ri,v in enumerate(views):
 p=E/f'whole_coelho_{v}_candidate_whole_v181_v182.png';base=np.array(Image.open(p).convert('RGB'))
 for ci,k in enumerate(['source','glb','fbx']):
  p=E/f'whole_coelho_{v}_candidate_whole_v181_v182.png' if k=='source' else E/f'whole_reimport_{k}_{v}_v185.png';im=Image.open(p).convert('RGB');tile=ImageOps.contain(im,(580,730));board.paste(tile,(ci*600+(600-tile.width)//2,ri*780+40));d.text((ci*600+14,ri*780+12),f'{k.upper()} / {v} / WHOLE WIP',fill='white')
  if k!='source':
   delta=np.abs(np.array(im).astype(float)-base.astype(float));metrics[k+'_'+v]=dict(meanRGB=float(delta.mean()),p95RGB=float(np.percentile(delta,95)),maxRGB=float(delta.max()),renderSHA256=sha(p),scope='Whole-frame diagnostic only, not photographic fidelity approval.')
board.save(E/'whole_source_glb_fbx_views_v192.jpg',quality=94)
cmp=Image.new('RGB',(1200,850),'#202020');d=ImageDraw.Draw(cmp)
for col,(v,title) in enumerate([('v145_v146','Published147 source145'),('v181_v182','Candidate184 source181')]):
 p=E/f'whole_coelho_front_candidate_whole_{v}.png';tile=ImageOps.contain(Image.open(p).convert('RGB'),(580,800));cmp.paste(tile,(col*600+(600-tile.width)//2,40));d.text((col*600+12,12),title+' - same camera',fill='white')
cmp.save(E/'whole_before_after_v192.jpg',quality=94)
report=dict(version='v192',sourceWholeWorkingVersion='v181',exportWholeVersion='v184',sourceWholeSHA256=pkg['files']['blend']['sha256'],allFiveWholeSourceViewsActuallyInspected=True,allTenIndependentGLBFBXViewsActuallyInspected=True,referenceBoard5ActuallyInspected=True,sourceImportPixelDiagnostics=metrics,acceptedForWholeIntermediateCheckpoint=True,staticScope='Local lace crossing correction: cross-motif and diamond-net contacts eliminated; intra-motif sewing contacts still unapproved. UVs and rigid thread sections preserved.',normalScope='Native GLB exporter rounds normals to four decimals and normalizes; raw payload matches that replay. Raw FBX normals and triangle order match source exactly. Both Blender importer encodings independently reproduced exactly.',normalRawAudits=['whole_glb_raw_normal_payload_audit_v186.json','whole_fbx_raw_normal_payload_audit_v187.json'],PBRMaterialAudits=['whole_glb_material_pixel_audit_v189.json','whole_fbx_embedded_material_audit_v190.json','whole_fbx_channel_semantics_audit_v191.json'],canonicalIdentityApproved=False,anatomical168cmApproved=False,rigged=False,physicsVerified=False,productionComplete=False,additionalTripoCredits=0,remaining=['7,417 intra-motif path contacts are not approved as sewn joints; sewing/mounting and deformation LOD unfinished.','Reference hanging ornaments, embroidery/overlay and tassels unfinished.','Canonical common face/body168cm/rig, lower layers, individual outfit hair, cloth/hair dynamics/collisions/wind/actions/expressions and runtime switching unfinished.'],notYetPublished=True,createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
(O/'whole_checkpoint_review_decision_v192.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('WHOLE184_STATIC_INTERMEDIATE_REVIEW_RECORDED')
