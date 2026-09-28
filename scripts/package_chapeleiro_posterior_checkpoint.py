"""Package the complete character and unretouched reference/render evidence together."""
from pathlib import Path
import argparse,json,shutil,hashlib
from PIL import Image,ImageOps,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--review',required=True);p.add_argument('--output',required=True);a=p.parse_args()
review=Path(a.review);r=json.loads((review/'review.json').read_text());out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
base=Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
model=Path(r['model']);assert hashlib.sha256(model.read_bytes()).hexdigest()==r['modelSha256']
shutil.copyfile(model,out/'alice_chapeleiro_complete.glb')
shutil.copyfile(model.parent/'export.json',out/'export.json');shutil.copyfile(review/'review.json',out/'review.json')
shutil.copyfile('F:/Alice/References/alice_chapeleiro_back_master_v001.jpg',out/'back_reference.jpg')
shutil.copyfile(base/'posterior_bodice_checkpoint_v001/back_before.png',out/'back_before.png')
for name in ['back_hair_hidden','back_oblique_hair_hidden','back_hair_restored','complete_hair_restored']:
    shutil.copyfile(review/(name+'.png'),out/(name+'.png'))
for folder in ['back_brocade_paint_v001','posterior_visible_bake_v001']:
    dest=out/folder;dest.mkdir()
    for file in (base/folder).iterdir():
        if file.suffix in ['.png','.json','.txt']:shutil.copyfile(file,dest/file.name)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',28)
sheet=Image.new('RGB',(2400,1350),(19,19,21));d=ImageDraw.Draw(sheet)
entries=[('Foto de referência','back_reference.jpg'),('Antes · cabelo oculto','back_before.png'),('GLB exportado · cabelo oculto','back_hair_hidden.png')]
for i,(title,file) in enumerate(entries):
    im=Image.open(out/file).convert('RGBA');bg=Image.new('RGBA',im.size,(19,19,21,255));bg.alpha_composite(im)
    fit=ImageOps.contain(bg.convert('RGB'),(780,1210));sheet.paste(fit,(i*800+(800-fit.width)//2,70+(1210-fit.height)//2));d.text((i*800+20,22),title,font=font,fill='white')
d.text((20,1300),'Checkpoint em refinamento: renda, transições, cabelo e movimento ainda sem aprovação final.',font=font,fill=(225,200,150));sheet.save(out/'back_photo_before_after.jpg',quality=94)
(out/'README.md').write_text('''# Alice Chapeleiro — checkpoint das costas

O GLB contém a personagem inteira com vestido e cabelo original restaurado. A região antes coberta por uma superfície verde lisa recebe corpete traseiro com amarração cruzada, costuras e uma nova textura 4096 × 4096. A foto traseira enviada pelo usuário é a referência principal.

A pintura de tecido foi gerada com imagegen em 1254 × 1254 e transferida para um atlas 4K com teste de visibilidade por texel. O atlas 4K não equivale a uma fonte gerada em 4K. Bordados são uma interpretação da referência; a fidelidade exata ainda não foi aprovada.

O antes e o depois usam a mesma câmera. O depois é render do GLB efetivamente reimportado. A comparação preserva as imagens sem retoques. O cabelo pode ser ocultado na galeria para inspecionar as costas.

Limitações observadas: renda simplificada, transições com mangas e anatomia subjacente, resíduos da malha original e demais detalhes do vestido ainda requerem polimento. O GLB conserva o cabelo original do Tripo; os fios individuais permanecem no Blender local. Quatro ações estão presentes, mas isso não aprova física, colisões ou qualidade de deformação. FBX final pendente. Nenhum crédito Tripo utilizado.
''',encoding='utf-8')
print(str(out))
