"""Create review boards from unchanged own-stage photo and actual render files."""
import hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

base = Path('F:/Alice/Deliverables/Alice_Variants/alice_chapeleiro')
root = base / 'foundation_shared_rig_v095_export_v002'
out = root / 'photo_review_boards_v001'
assert not out.exists()
out.mkdir()
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
g = read(root / 'generation.json')
photo = Path(g['exports']['foundation']['sourcePhoto'])
assert sha(photo) == g['exports']['foundation']['sourcePhotoSha256']
assert sha(g['exports']['foundation']['model']) == g['exports']['foundation']['modelSha256']
motion = read(root / 'actual_shared_rig_review_v001/motion_comparison.json')
ivory = read(root / 'actual_ivory_export_review_v001/comparison.json')
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 25)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 19)
boards, sources = [], []

def board(name, title, rows, labels, note):
    width, cell_width, cell_height = 2120, 500, 800
    columns = 3
    nrows = (len(rows)+columns-1)//columns
    im = Image.new('RGB', (width, max(1000, 135+nrows*cell_height)), (25,27,31))
    draw = ImageDraw.Draw(im)
    draw.text((24,20), title, font=font, fill='white')
    draw.text((24,60), note, font=small, fill='#e7d8b9')
    p = Image.open(photo).convert('RGB')
    p.thumbnail((500,800))
    im.paste(p,(24,120))
    draw.text((24,940),'Foto original completa / etapa 01',font=small,fill='#e7d8b9')
    for i, (row, label) in enumerate(zip(rows,labels)):
        file = Path(row.get('file',row.get('render','')))
        expected = row.get('sha256',row.get('renderSha256'))
        assert sha(file) == expected
        x,y = 590+(i%columns)*cell_width,120+(i//columns)*cell_height
        render = Image.open(file).convert('RGBA')
        render.thumbnail((480,735))
        im.paste(render,(x,y),render)
        draw.text((x,y+745),label,font=small,fill='white')
        sources.append({'file':str(file),'sha256':expected})
    target = out / name
    im.save(target,quality=95)
    boards.append({'file':str(target),'sha256':sha(target),'actualRenderFiles':[row.get('file',row.get('render')) for row in rows]})

board('photo_vs_geometry.jpg','CHAPELEIRO / REIMPORTAÇÃO DO GLB / REPOUSO / EM REFINAMENTO',
      motion['restRenders'],[r['view'] for r in motion['restRenders']],
      'A geometria anterior permanece inteira. Forma, costuras e renda ainda precisam de refinamento.')
for clip in motion['clips']:
    label=clip['clip'].split(' /')[0]
    board('photo_vs_'+label.lower()+'.jpg','CHAPELEIRO / GLB REIMPORTADO / '+label.upper()+' / EM REFINAMENTO',
          clip['poses'],[f'Pose {i+1} / frame {r["frame"]:.2f}' for i,r in enumerate(clip['poses'])],
          'Três poses reais desta ação. Rig presente não aprova a física ou a fidelidade completa.')
board('photo_vs_shared_skin_motion.jpg','CHAPELEIRO / GLB REIMPORTADO / DOZE POSES / EM REFINAMENTO',
      [r for c in motion['clips'] for r in c['poses']],
      [f'{c["clip"].split(" /")[0]} / pose {i+1}' for c in motion['clips'] for i,r in enumerate(c['poses'])],
      'Quatro ações no rig compartilhado. O movimento das camadas e o contato ainda precisam de refinamento.')
board('photo_vs_actual_ivory_joint_motion.jpg','CHAPELEIRO / GLB REIMPORTADO / ESTUDO DA ANÁGUA / EM REFINAMENTO',
      ivory['renders'],[f'{r["scope"]} / pose {r["sourcePhysicsFrame"]} / {r["view"]}' for r in ivory['renders']],
      'Estudo nos ossos já existente. Nova simulação com costuras independentes ainda não foi incorporada ao GLB.')
rows,labels=[],[]
for version,title in [(7,'Antes / costuras independentes'),(8,'Transferência Surface Deform'),(9,'Após corrigir rig da cintura')]:
    review=read(base/f'retopo_ivory_black_cloth_v{version:03d}'/'actual_receiver_review/comparison.json')
    assert len(review['renders'])==2
    for row in review['renders']:
        rows.append(row);labels.append(f'{title} / pose {row["sourcePhysicsFrame"]}')
board('photo_vs_actual_waist_cloth_contact.jpg','CHAPELEIRO / CINTURA E CONTATO / EM REFINAMENTO',rows,labels,
      'Pontos totalmente presos: 34 dentro dos bloomers antes, zero após. Babados e contato do tecido ainda falham.')
report={'sourcePhoto':str(photo),'sourcePhotoSha256':sha(photo),'modelSha256':g['exports']['foundation']['modelSha256'],
        'boards':boards,'actualRenderSources':list({r['file']:r for r in sources}.values()),'allLayersFinished':False,'fidelityVerified':False,
        'motionVerified':False,'clothCollisionVerified':False,'finalFbxExported':False,
        'visualAssessmentPending':True,'scriptSha256':sha(__file__)}
(out/'boards.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('ACTUAL_V095_PHOTO_BOARDS_CREATED',len(boards),len(sources))
