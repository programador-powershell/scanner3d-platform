import json,hashlib,numpy as np
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';E=O/'Evidence';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pkg=read(O/'package_export_v520.json');views=['front','threequarter','back','left_profile','right_profile'];metrics={}
board=Image.new('RGB',(1800,3900),'#202020');draw=ImageDraw.Draw(board)
for ri,v in enumerate(views):
 base=np.asarray(Image.open(E/f'whole_coelho_{v}_rear_bow_wip_v498.png').convert('RGB'),float)
 for ci,k in enumerate(['source','glb','fbx']):
  p=E/f'whole_coelho_{v}_rear_bow_wip_v498.png' if k=='source' else E/f'whole_reimport_{k}_{v}_v{522 if k=="glb" else 502}.png';im=Image.open(p).convert('RGB');tile=ImageOps.contain(im,(580,730));board.paste(tile,(ci*600+(600-tile.width)//2,ri*780+40));draw.text((ci*600+14,ri*780+12),f'{k.upper()} / {v} / WHOLE STATIC WIP520',fill='white')
  if k!='source':
   delta=np.abs(np.asarray(im,float)-base);metrics[k+'_'+v]=dict(meanRGB=float(delta.mean()),p95RGB=float(np.percentile(delta,95)),maxRGB=float(delta.max()),renderSHA256=sha(p),scope='Whole-frame diagnostic, not reference fidelity approval.')
board.save(E/'whole_source_glb_fbx_views_v525.jpg',quality=94)
for view in ['front','back']:
 cmp=Image.new('RGB',(1200,850),'#202020');draw=ImageDraw.Draw(cmp)
 for col,(p,title) in enumerate([(E/f'whole_coelho_{view}_ornament_wip_v422.png','Public424 source421'),(E/f'whole_coelho_{view}_rear_bow_wip_v498.png','Candidate520 source497')]):
  tile=ImageOps.contain(Image.open(p).convert('RGB'),(580,800));cmp.paste(tile,(col*600+(600-tile.width)//2,40));draw.text((col*600+12,12),title+' - same camera',fill='white')
 cmp.save(E/f'whole_before_after_{view}_v525.jpg',quality=94)
(O/'whole_comparison_diagnostics_v525.json').write_text(json.dumps(dict(version='v525',metrics=metrics,requiresActualImageInspection=True,productionComplete=False),indent=2),encoding='utf-8');print('WHOLE500_COMPARISON_PANELS_CREATED_NOT_VISUAL_APPROVAL')
