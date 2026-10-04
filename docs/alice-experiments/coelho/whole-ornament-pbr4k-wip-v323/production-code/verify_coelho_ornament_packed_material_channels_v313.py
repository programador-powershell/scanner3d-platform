"""Independent PNG pixel/channel verification after local diagnostic GLB export."""
from pathlib import Path
import json,hashlib,numpy as np
from PIL import Image
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def pixels(p):
    with Image.open(p) as im:assert im.size==(4096,4096);return np.asarray(im.convert('RGB'))
a=read(O/'apron_ornament_pbr_atlas_authoring_audit_v301.json');e=read(O/'apron_ornament_material_format_payload_v308.json');assert a['sha256']==e['sourceSHA256'];rough=pixels(R/a['maps']['roughness']['path']);metal=pixels(R/a['maps']['metallic']['path']);rows=[]
for mat in e['GLBMaterialBindings']:
    assert mat['metallicFactor']==mat['roughnessFactor']==1;orm=pixels(R/mat['bindings']['metallicRoughness']['path']);assert np.array_equal(orm[:,:,1],rough[:,:,0]) and np.array_equal(orm[:,:,2],metal[:,:,0]);checks={}
    for role in ['basecolor','normal']:
        src=pixels(R/a['maps'][role]['path']);dst=pixels(R/mat['bindings'][role]['path']);assert np.array_equal(src,dst);checks[role]=dict(allPixelsAndChannelsExactlyEqual=True)
    rows.append(dict(material=mat['name'],metallicBEqualsSourceMetallicR=True,roughnessGEqualsSourceRoughnessR=True,baseAndNormal=checks))
report=dict(version='v313',sourceCandidate='v301',sourceSHA256=a['sha256'],GLBPackedMetalRoughChannelsExactlyMatchSource=True,materialRows=rows,allMapResolutions4096=True,formatActualReimportAndAppearanceSeparate=True,notPublished=True,productionComplete=False);(O/'apron_ornament_material_packed_channel_audit_v313.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ORNAMENT_MATERIAL313_ALL_SOURCE_PIXELS_AND_PACKED_CHANNELS_EXACT')
