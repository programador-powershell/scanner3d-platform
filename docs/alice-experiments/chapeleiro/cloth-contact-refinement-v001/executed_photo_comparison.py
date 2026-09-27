"""Measure complete trajectories and compose their actual renders with full photo."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
workspace=Path(__file__).resolve().parents[1]
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
out=base/'cloth_contact_photo_review_v001'
assert not out.exists();out.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda name,d:(out/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
g=read(base/'foundation_shared_rig_v095/generation.json')
photo=g['exports']['foundation']['sourcePhoto']
assert sha(photo)==g['exports']['foundation']['sourcePhotoSha256']
records=[];renders=[]
for folder,label in [('retopo_ivory_black_cloth_v009','Antes'),('retopo_ivory_black_cloth_v011','Normais nativas'),('xpbd_ivory_black_cloth_v002','Restrições e contato corrigido')]:
    source=base/folder;r=read(source/'actual_sewn_solver_motion.json')
    assert len(r['frames'])==29 and sha(r['dataFile'])==r['dataSha256']
    contact=read(source/'dynamic_clearance_inspection/dynamic_clearance_inspection.json')
    assert contact['sourcePhysicalDataSha256']==r['dataSha256'] and sha(contact['dataFile'])==contact['dataSha256']
    review=read(source/'actual_receiver_review/comparison.json')
    assert len(review['renders'])==2 and review['probeDataSha256']==r['dataSha256']
    for row in review['renders']:
        assert sha(row['file'])==row['sha256']
        renders.append({'label':label,**row})
    records.append({'label':label,'physicsSha256':r['dataSha256'],
      'physicalMaximumStretchByPart':{part['key']:max(piece['solverMaximumEdgeStretch'] for frame in r['frames'] for piece in frame['pieces'] if piece['key']==part['key']) for part in r['parts']},
      'physical95PercentileStretchPeakByPart':{part['key']:max(piece['solverEdgeStretch95Percentile'] for frame in r['frames'] for piece in frame['pieces'] if piece['key']==part['key']) for part in r['parts']},
      'maximumSeamGapMeters':max(frame['maximumSeamGapMeters'] for frame in r['frames']),
      'maximumFullyPinnedErrorMeters':max(frame['maximumPhysicalFullyPinnedInputError'] for frame in r['frames']),
      'bodyContacts':[{'proxyIndex':j,'maximumCertainInsideVertices':max(frame['proxies'][j]['certainInsideVertices'] for frame in contact['frames']),
        'maximumCertainPenetrationMeters':max(frame['proxies'][j]['maximumCertainPenetrationMeters'] for frame in contact['frames']),
        'totalAmbiguousQueries':sum(frame['proxies'][j]['ambiguousRayQueries'] for frame in contact['frames'])} for j in range(3)]})
native=np.load(base/'retopo_ivory_black_cloth_v011/actual_sewn_petticoat_frames.npz')
guarded=np.load(base/'xpbd_ivory_black_cloth_v002/actual_sewn_petticoat_frames.npz')
preserved=[key for key in native.files if key not in ['actual_simulation_points','points']]
assert all(np.array_equal(native[key],guarded[key]) for key in preserved)
write('metrics.json',{'sourcePhotoSha256':sha(photo),'controls':records,'exactlyPreservedInputArrays':preserved,
      'ownSourceGeometryUvRigInputsPinsAndRestPreserved':True,'allLayersFinished':False,'clothCollisionVerified':False})
im=Image.new('RGB',(2120,1770),(25,27,31));draw=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',25)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
draw.text((24,20),'CHAPELEIRO / CONTATO DAS CAMADAS / EM REFINAMENTO',font=font,fill='white')
draw.text((24,60),'Foto completa da etapa 01 e as mesmas duas poses reais. Novo cálculo ainda fora do GLB.',font=small,fill='#e7d8b9')
p=Image.open(photo).convert('RGB');p.thumbnail((500,1000));im.paste(p,(24,120))
draw.text((24,1130),'Foto original completa / etapa 01',font=small,fill='#e7d8b9')
for col in range(3):
    for row in range(2):
        entry=renders[col*2+row]
        x,y=590+col*500,120+row*805
        image=Image.open(entry['file']).convert('RGBA');image.thumbnail((480,735));im.paste(image,(x,y),image)
        draw.text((x,y+745),entry['label'],font=small,fill='white')
        draw.text((x,y+772),f'Pose {entry["sourcePhysicsFrame"]} / {entry["view"]}',font=small,fill='#e7d8b9')
im.save(out/'photo_comparison.jpg',quality=95)
write('actual_photo_board_sources.json',{'sourcePhoto':photo,'sourcePhotoSha256':sha(photo),'actualRenders':renders,
      'photoBoardSha256':sha(out/'photo_comparison.jpg'),'visualAssessmentPending':True})
protected=[
 ('scanner3d-platform/data/assets/alice-detail.glb','27200e6ea06b7940aa21ae86a18e6ad7442f1ff844add0cf0e471336cfa48c05'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb','84e27a46ecc472db6f3d5345dbf1c6d2164c5830c6bd6104cfb919fd10bc4943'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-vestido-chapeleiro.blend','ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.glb','d8ae24de525947e104218c5e518e217535b2c8bc0ce452338590ba738abea2e1'),
 ('project-alice-game/Content/Assets/3D/personagens/alice-chapeleiro-fundacao.blend','55ae0b5e32aa7b6374d02e82752e7a21893bc95bc480397f56172ad9236e9fbd')]
proof=[]
for file,digest in protected:
    path=workspace/file;assert sha(path)==digest,str(path)
    proof.append({'file':str(path),'bytes':path.stat().st_size,'sha256':digest,'unchanged':True})
assert sha(g['editableBlend'])==g['editableBlendSha256']
write('protected_assets.json',{'assets':proof,'completeAuthoringBytes':Path(g['editableBlend']).stat().st_size,
      'completeAuthoringSha256':g['editableBlendSha256'],'unchanged':True})
print(json.dumps(records,indent=2))
