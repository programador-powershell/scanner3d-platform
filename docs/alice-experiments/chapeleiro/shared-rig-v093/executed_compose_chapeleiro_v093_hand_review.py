import hashlib,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
workspace=Path(__file__).resolve().parents[1];repo=workspace/'scanner3d-platform'
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro');root=base/'foundation_shared_rig_v093'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,r:Path(p).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
before=read(base/'foundation_shared_rig_v092/hand_motion_v093_comparison/comparison.json');after=read(root/'hand_motion_v002/comparison.json')
assert before['sourcePhotoSha256']==after['sourcePhotoSha256']
g=read(root/'generation.json');assert after['modelSha256']==g['exports']['whole']['modelSha256']
board=Image.new('RGB',(1760,2050),(24,26,29));draw=ImageDraw.Draw(board)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
draw.text((24,20),'CHAPELEIRO / MÃOS EM MOVIMENTO / ANTES E DEPOIS REAIS',font=font,fill='white')
photo=Image.open(after['sourcePhoto']).convert('RGB');photo.thumbnail((510,530));board.paste(photo,(24,70))
draw.text((24,620),'Foto original completa desta variante',font=small,fill='#dbc8a2')
draw.text((580,70),'Antes / v092',font=font,fill='white');draw.text((1160,70),'Depois / v093',font=font,fill='white')
for i,(b,a) in enumerate(zip(before['renders'],after['renders'])):
 assert (b['side'],b['motion'],b['fraction'])==(a['side'],a['motion'],a['fraction'])
 assert max(abs(x-y) for x,y in zip(b['cameraPosition'],a['cameraPosition']))<1e-6
 assert max(abs(x-y) for x,y in zip(b['cameraTarget'],a['cameraTarget']))<1e-6
 y=110+i*310
 for row,x in [(b,580),(a,1160)]:
  assert sha(row['file'])==row['sha256'];im=Image.open(row['file']).convert('RGBA');im.thumbnail((530,290))
  board.paste(im,(x,y),im)
  draw.text((x,y+285),f"{a['side']} / {a['motion']} / {a['fraction']}",font=small,fill='#ddd2bd')
draw.text((24,1975),'Menos esticamento não aprova anatomia, fidelidade, todas as poses ou colisões.',font=small,fill='#dbc8a2')
file=root/'photo_vs_actual_hand_motion_before_after.jpg';board.save(file,quality=94)
write(root/'hand_motion_before_after_board.json',{'beforeModelSha256':before['modelSha256'],'afterModelSha256':after['modelSha256'],
 'sourcePhotoSha256':after['sourcePhotoSha256'],'sameActualCameraForBothModels':True,
 'board':{'file':str(file),'sha256':sha(file)},'scriptSha256':sha(__file__),'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False})
print('Actual hand-motion board preserved with full own photo and identical cameras.')
