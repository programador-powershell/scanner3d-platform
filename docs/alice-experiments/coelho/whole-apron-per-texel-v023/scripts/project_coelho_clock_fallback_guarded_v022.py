from pathlib import Path
import json
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';p=R/'Tools/project_coelho_apron_fallback_photo_v020.py';code=p.read_text().replace('_v020','_v022')
needle="after=before.copy();paint=np.zeros((W,W),bool);tree="
insert="""after=before.copy();metalNode=bs.inputs['Metallic'].links[0].from_node;metal=np.empty(W*W*4,np.float32);metalNode.image.pixels.foreach_get(metal);metal=metal.reshape(W,W,4);guardRejected=0;paint=np.zeros((W,W),bool);tree="""
assert needle in code;code=code.replace(needle,insert)
needle="maskRejected+=int((~gate).sum());visible=[]"
insert="""maskRejected+=int((~gate).sum());txi=(samples[:,0]*W).astype(int);tyi=(samples[:,1]*W).astype(int);oldRGB=before[tyi,txi,:3];protect=(oldRGB[:,2]>oldRGB[:,0]+.04)|(oldRGB[:,2]>oldRGB[:,0]*1.35+.02)|(metal[tyi,txi,0]>.6);lowerClock=(photoY>=370)&(photoY<=520);guardRejected+=int((gate&(~lowerClock|protect)).sum());gate&=lowerClock&~protect;visible=[]"""
assert needle in code;code=code.replace(needle,insert)
code=code.replace('rigged=False,fidelityApproved=False,exportVerified=False','fallbackScopeLowerClockPhotoY=[370,520],navyAndHighMetallicTexelsProtected=True,rejectedScopeOrMaterialGuard=guardRejected,guardsAreProtectionNotFullGarmentSegmentation=True,rigged=False,fidelityApproved=False,exportVerified=False')
exec(compile(code,str(p),'exec'))
