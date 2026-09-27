"""Compare actual 3D renders in identical cameras and protect non-dress pixels."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
from scipy.ndimage import binary_dilation
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',required=True);p.add_argument('--after',required=True)
p.add_argument('--scope',required=True);p.add_argument('--output',required=True)
a=p.parse_args();read=lambda path:json.loads(Path(path).read_text())
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
before,after,scope=read(a.before),read(a.after),read(a.scope)
assert before['resolution']==after['resolution']
reference=Path(before['garmentReference'])
assert sha(reference)==before['garmentReferenceSha256']==after['garmentReferenceSha256']
out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
rows=[]
for view in ['front','left','right','back']:
    b=next(r for r in before['renders'] if r['view']==view and r['kind']=='basecolor')
    f=next(r for r in after['renders'] if r['view']==view and r['kind']=='basecolor')
    s=next(r for r in scope['renders'] if r['view']==view)
    for r in [b,f,s]:assert sha(r['file'])==r['sha256']
    camera_error=float(np.max(np.abs(np.array(b['cameraWorldMatrix'])-f['cameraWorldMatrix'])))
    projection_error=float(np.max(np.abs(np.array(b['cameraProjectionMatrix'])-f['cameraProjectionMatrix'])))
    assert camera_error<1e-7 and projection_error<1e-7
    original=np.array(Image.open(b['file']).convert('RGBA'))
    final=np.array(Image.open(f['file']).convert('RGBA'))
    mask=np.array(Image.open(s['file']).convert('RGBA'))
    cloth=mask[:,:,:3].max(2)>10
    protected=(~binary_dilation(cloth,iterations=3))&(original[:,:,3]>250)
    delta=np.abs(original[:,:,:3].astype(np.int16)-final[:,:,:3].astype(np.int16))
    maxima=delta.max(2)
    rows.append(dict(view=view,before=b['file'],after=f['file'],scopeMask=s['file'],
        cameraMaximumError=camera_error,projectionMaximumError=projection_error,
        protectedVisiblePixels=int(protected.sum()),
        protectedMaximumChannelDifference=int(maxima[protected].max()) if protected.any() else 0,
        protectedChangedBeyondOneChannelLevel=int((maxima[protected]>1).sum()),
        garmentMaskPixels=int(cloth.sum()),garmentMeanChannelChange=float(delta[cloth].mean()),
        changedGarmentPixels=int((maxima[cloth]>1).sum())))
    # A contact sheet is a deterministic comparison of actual 3D renders,
    # not a generated alternate character or an edited garment source painting.
    sheet=Image.new('RGBA',(original.shape[1]*2,original.shape[0]),(0,0,0,0))
    sheet.paste(Image.fromarray(original),(0,0));sheet.paste(Image.fromarray(final),(original.shape[1],0))
    sheet.save(out/(view+'_actual_3d_before_after.png'))
    reference_sheet=Image.new('RGBA',(original.shape[1]*3,original.shape[0]),(0,0,0,0))
    with Image.open(reference) as photo:
        fitted=ImageOps.contain(photo.convert('RGBA'),(original.shape[1],original.shape[0]))
    reference_sheet.paste(fitted,((original.shape[1]-fitted.width)//2,(original.shape[0]-fitted.height)//2))
    reference_sheet.paste(Image.fromarray(original),(original.shape[1],0))
    reference_sheet.paste(Image.fromarray(final),(original.shape[1]*2,0))
    reference_sheet.save(out/(view+'_reference_before_after.png'))
report=dict(beforeBaseline=a.before,beforeBaselineSha256=sha(a.before),
    afterBaseline=a.after,afterBaselineSha256=sha(a.after),scope=a.scope,scopeSha256=sha(a.scope),
    garmentReference=str(reference),garmentReferenceSha256=sha(reference),
    comparisonPanelOrder=['unaltered variant reference (scaled to fit)','actual 3D before','actual 3D after'],
    views=rows,identicalActual3dCameras=True,
    protectedPixelsPreserved=all(r['protectedChangedBeyondOneChannelLevel']==0 for r in rows),
    actualRendersRequireVisualReview=True,fullDressCoverageApproved=False,
    characterFidelityVerified=False,clothMotionVerified=False,newGlbOrFbxExported=False,published=False)
(out/'comparison_metrics.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
