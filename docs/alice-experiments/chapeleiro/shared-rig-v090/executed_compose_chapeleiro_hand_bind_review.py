"""Keep the full own photograph beside both actual native hand-bind overlays."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',required=True);args=parser.parse_args();root=Path(args.root)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
left=read(root/'hand_bind_left/comparison.json');right=read(root/'hand_bind_right/comparison.json')
for key in ['modelSha256','sourcePhotoSha256']:
    if left[key]!=right[key]:raise ValueError('Mixed native hand evidence.')
if sha(left['model'])!=left['modelSha256'] or sha(left['sourcePhoto'])!=left['sourcePhotoSha256']:
    raise ValueError('Changed model or own photograph.')
board=Image.new('RGB',(2860,1900),(24,26,30));draw=ImageDraw.Draw(board)
draw.text((24,20),'CHAPELEIRO / JUNTAS E HIERARQUIA REAIS DO GLB / ENCAIXE A REVISAR',fill='white')
def put(file,box):
    photo=Image.open(file).convert('RGBA');photo.thumbnail((box[2],box[3]),Image.Resampling.LANCZOS)
    board.paste(photo,(box[0]+(box[2]-photo.width)//2,box[1]+(box[3]-photo.height)//2),photo)
draw.text((24,65),'FOTO ORIGINAL COMPLETA DESTA ETAPA',fill=(210,205,193))
put(left['sourcePhoto'],(24,100,680,1700))
for row,(side,record) in enumerate([('Left',left),('Right',right)]):
    for column,name in enumerate(['front','side','back']):
        artifact=record['renders'][name]
        if sha(artifact['file'])!=artifact['sha256']:raise ValueError('Changed actual bone overlay.')
        x,y=730+column*700,65+row*880
        draw.text((x,y),side+' / '+name+' / alpha diagnóstico 0,28',fill=(210,205,193))
        put(artifact['file'],(x,y+30,670,835))
draw.text((24,1830),'Juntas internas inferidas na superfície nativa. Anatomia, poses, contatos e tecido ainda exigem revisão.',fill=(215,198,160))
draw.text((24,1855),'Material transparente e ossos coloridos são sobreposições de diagnóstico; a geometria original permanece intacta.',fill=(215,198,160))
file=root/'photo_vs_actual_hand_bind.jpg';board.save(file,quality=94)
record={'modelSha256':left['modelSha256'],'sourcePhotoSha256':left['sourcePhotoSha256'],
    'sourcePhotoUnchanged':True,'board':{'file':str(file),'sha256':sha(file)},
    'leftEvidence':'hand_bind_left/comparison.json','rightEvidence':'hand_bind_right/comparison.json',
    'scriptSha256':sha(__file__),'rigFitVerified':False,'fidelityVerified':False,'motionVerified':False}
(root/'hand_bind_comparison_board.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(file)
