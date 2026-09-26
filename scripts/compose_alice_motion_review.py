"""Factual contact sheet: original layer photo and unaltered exported skin renders."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

parser = argparse.ArgumentParser()
parser.add_argument('--comparison', required=True)
args = parser.parse_args()
path = Path(args.comparison)
report = json.loads(path.read_text(encoding='utf-8'))
sha = lambda file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
if sha(report['sourcePhoto']) != report['sourcePhotoSha256']:
    raise ValueError('The original layer photograph changed.')
board = Image.new('RGB', (1920, 1840), '#18191e')
draw = ImageDraw.Draw(board)
draw.text((24, 18), 'CAMADA 2 CHAPELEIRO / RENDERS DO GLB EXPORTADO / MOVIMENTO E COLISOES A VERIFICAR', fill='white')
draw.text((24, 52), 'FOTO ORIGINAL DA PROPRIA CAMADA', fill='#e1d3b6')
with Image.open(report['sourcePhoto']) as original:
    photo = ImageOps.contain(original.convert('RGB'), (520, 1670))
    board.paste(photo, (24, 85))
for row, clip in enumerate(report['clips']):
    for col, pose in enumerate(clip['poses']):
        if sha(pose['render']) != pose['renderSha256']:
            raise ValueError('An actual rendered pose changed.')
        x, y = 600 + col * 430, 85 + row * 425
        with Image.open(pose['render']) as actual:
            if actual.mode != 'RGBA' or not actual.getchannel('A').getbbox():
                raise ValueError('Expected a nonempty actual geometry render.')
            actual = ImageOps.contain(actual, (405, 390))
            board.paste(actual, (x + (405 - actual.width) // 2, y), actual)
        draw.text((x, y - 20), clip['clip'].split(' /')[0] + ' / frame ' + str(round(pose['frame'], 2)), fill='#bfcbd9')
draw.text((24, 1775), '40 componentes no mesmo rig. Salto e oscilacao secundaria sao ensaios autorais; nao comprovam fisica de tecido.', fill='#e1d3b6')
draw.text((24, 1800), 'Recortes/costuras dos ombros e pesos em poses extremas ainda precisam de refino. Conjunto completo permanece pendente.', fill='#e1d3b6')
output = path.parent / 'photo_vs_skin_motion.jpg'
board.save(output, quality=96)
report['contactBoard'] = {'file': str(output.resolve()), 'sha256': sha(output)}
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(output)
