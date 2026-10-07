"""QA contact sheets from actual immutable renders; no retouch or source editing."""
from pathlib import Path
import json,hashlib,numpy as np
from PIL import Image,ImageDraw,ImageFont
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';D=O/'corset_patch_weights_whole_CANDIDATE_v1226';j=json.loads((D/'manifest.json').read_text(encoding='utf-8-sig'));assert j['twoSameCameraNativeBeforeAfterPairsComplete']
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',22);rows=[]
for view,candidate,crop in [('front','corset_peak',(445,300,590,490)),('left_profile','corset_peak_left_profile',(300,270,565,515))]:
    a=next(r for r in j['baselineRenders'] if r['view']==view);b=next(r for r in j['renders'] if r['view']==candidate)
    assert a['frame']==b['frame']==27
    for r in [a,b]:assert hashlib.sha256((R/r['path']).read_bytes()).hexdigest()==r['sha256']
    old=Image.open(R/a['path']).convert('RGB');new=Image.open(R/b['path']).convert('RGB');assert old.size==new.size==(900,1100)
    delta=np.abs(np.asarray(old.crop(crop)).astype(float)-np.asarray(new.crop(crop)).astype(float));tiles=[im.crop(crop).resize(((crop[2]-crop[0])*3,(crop[3]-crop[1])*3),Image.Resampling.LANCZOS) for im in [old,new]]
    fig=Image.new('RGB',(tiles[0].width*2+30,tiles[0].height+100),(25,27,33));draw=ImageDraw.Draw(fig);draw.text((10,8),'Quadro 27 · câmera e iluminação iguais · '+view,font=font,fill='white');draw.text((10,45),'Antes: fonte inteira v1200',font=font,fill='white');draw.text((tiles[0].width+25,45),'Depois: candidata inteira v1226',font=font,fill='white')
    for i,im in enumerate(tiles):fig.paste(im,(10+i*(im.width+10),90))
    p=D/f'actual_before_after_corset_frame27_{view}_v1229.png';assert not p.exists();fig.save(p)
    rows.append(dict(view=view,frame=27,baseline=a,candidate=b,fixedCrop=crop,meanAbsoluteRGBDifference=float(delta.mean()),maximumAbsoluteRGBDifference=float(delta.max()),comparisonPath=p.relative_to(R).as_posix(),comparisonSHA256=hashlib.sha256(p.read_bytes()).hexdigest()))
report=dict(version='v1229',actualSameCameraNativeBeforeAfter=True,pixelDifferencesAreNotFidelityMetrics=True,noRetouchOrSourceEditing=True,rows=rows,productionComplete=False)
(D/'actual_before_after_comparison_v1229.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ACTUAL_TWO_NATIVE_BEFORE_AFTER_CONTACT_SHEETS_CREATED')
