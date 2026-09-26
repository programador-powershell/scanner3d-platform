"""Original stage photo beside actual geometry renders, with no automatic fidelity claim."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

parser=argparse.ArgumentParser()
parser.add_argument('--comparison',required=True)
args=parser.parse_args()
report_path=Path(args.comparison)
report=json.loads(report_path.read_text(encoding='utf-8'))
source=Path(report['sourcePhoto'])
sha=lambda file:hashlib.sha256(Path(file).read_bytes()).hexdigest()
if sha(source)!=report['sourcePhotoSha256'] or sha(report['model'])!=report['modelSha256']:
    raise ValueError('Photo or model no longer matches the comparison record.')
board=Image.new('RGB',(1920,1500),'#18191e')
draw=ImageDraw.Draw(board)
scope=report.get('selectedComponentGroup') or report.get('selectedRolePrefix') or 'conjunto da etapa'
draw.text((24,18),f"{report['stageId']} / {scope} / FOTO DESTA ETAPA / FIDELIDADE A VERIFICAR",fill='white')
def paste(image,box):
    x,y,w,h=box
    image=ImageOps.contain(image,(w,h))
    position=(x+(w-image.width)//2,y+(h-image.height)//2)
    board.paste(image,position,image if image.mode=='RGBA' else None)
with Image.open(source) as image:
    image=image.convert('RGB')
    paste(image,(20,65,1040,730))
    crop=image.crop(report['sourceCrop']) if report.get('sourceCrop') else image
    paste(crop,(20,840,550,610))
draw.text((24,45),'FOTO ORIGINAL DA ETAPA (sem substituir pela foto do vestido final)',fill='#e1d3b6')
draw.text((24,820),'REFERENCIA UTILIZADA NA RECONSTRUCAO',fill='#e1d3b6')
for name,box in {'front':(1080,70,380,700),'threequarter':(1500,70,380,700),
                 'side':(650,840,550,610),'back':(1270,840,550,610)}.items():
    render=report['renders'][name]
    if sha(render['file'])!=render['sha256']:
        raise ValueError('Render changed after its evidence record.')
    with Image.open(render['file']) as image:
        if image.mode!='RGBA' or image.getchannel('A').getbbox() is None:
            raise ValueError('Expected a nonempty transparent geometry render.')
        paste(image,box)
    draw.text((box[0],box[1]-20),'RENDER 3D / '+name.upper(),fill='#bfcbd9')
output=report_path.parent/'photo_vs_geometry.jpg'
board.save(output,quality=96)
report['comparisonBoard']={'file':str(output.resolve()),'sha256':sha(output)}
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(output)
