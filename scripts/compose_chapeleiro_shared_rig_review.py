"""Own original photo beside twelve actual exported shared-skin poses."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--comparison',required=True)
args=parser.parse_args();path=Path(args.comparison);record=json.loads(path.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for field in ['model','sourcePhoto']:
    if sha(record[field])!=record[field+'Sha256']:raise ValueError('Changed actual motion evidence.')
board=Image.new('RGB',(2240,2440),'#18191e');draw=ImageDraw.Draw(board)
draw.text((24,20),'CHAPELEIRO / '+record['family'].upper()+' / GLB EXPORTADO / DEFORMACAO E COLISOES A VERIFICAR',fill='white')
draw.text((24,55),'FOTO ORIGINAL DESTA ETAPA',fill='#e1d3b6')
with Image.open(record['sourcePhoto']) as source:
    image=ImageOps.contain(source.convert('RGB'),(700,2060));board.paste(image,(24,100+(2060-image.height)//2))
for row,clip in enumerate(record['clips']):
    for col,pose in enumerate(clip['poses']):
        if sha(pose['render'])!=pose['renderSha256']:raise ValueError('Changed actual exported-pose render.')
        x,y=750+col*490,100+row*550
        with Image.open(pose['render']) as image:
            if image.mode!='RGBA' or not image.getchannel('A').getbbox():raise ValueError('Empty actual pose render.')
            image=ImageOps.contain(image,(470,505));board.paste(image,(x+(470-image.width)//2,y),image)
        draw.text((x,y-22),clip['clip'].split(' /')[0]+' / frame '+str(round(pose['frame'],2)),fill='#bfcbd9')
draw.text((24,2340),str(record['actualImportedSkinnedMeshes'])+' malhas reais no mesmo esqueleto. Pesos e clips nao aprovam fidelidade ou fisica.',fill='#e1d3b6')
draw.text((24,2370),'Tecido secundario sem resposta fisica assada. Corpo, contatos entre camadas e movimento no jogo continuam pendentes.',fill='#e1d3b6')
file=path.parent/'photo_vs_shared_skin_motion.jpg';board.save(file,quality=96)
record['contactBoard']={'file':str(file.resolve()),'sha256':sha(file)}
path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(file)
