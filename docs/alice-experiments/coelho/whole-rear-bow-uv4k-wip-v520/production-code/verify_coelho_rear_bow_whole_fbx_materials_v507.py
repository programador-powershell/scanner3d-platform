import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,'F:/Programas/5.2/scripts/addons_core');from io_scene_fbx import parse_fbx
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';a=json.loads((O/'package_export_v500.json').read_text(encoding='utf-8-sig'));s=json.loads((O/'whole_source_material_semantics_v505.json').read_text(encoding='utf-8-sig'));root,_=parse_fbx.parse(str(R/a['files']['fbx']['path']));obs=next(e for e in root.elems if e.id==b'Objects');co=next(e for e in root.elems if e.id==b'Connections');byid={e.props[0]:e for e in obs.elems};videos=[];connections=[]
for e in obs.elems:
 if e.id==b'Video':
  c=next(c for c in e.elems if c.id==b'Content');blob=c.props[0];digest=hashlib.sha256(blob).hexdigest();sources=[i for m in s['materials'] for i in m['images'] if i['sha256']==digest];assert sources,(e.props[:3],len(blob),digest);videos.append(dict(id=e.props[0],sha256=digest,bytes=len(blob),sourceImageNames=sorted(set(i['name'] for i in sources))))
for e in co.elems:
 p=e.props
 if p[0]==b'OP' and byid.get(p[1]) is not None and byid[p[1]].id==b'Texture':
  vid=next(x.props[1] for x in co.elems if x.props[0]==b'OO' and x.props[2]==p[1] and byid.get(x.props[1]) is not None and byid[x.props[1]].id==b'Video');v=next(v for v in videos if v['id']==vid);mat=byid[p[2]].props[1].split(b'\x00')[0].decode();connections.append(dict(material=mat,property=p[3].decode(),imageSHA256=v['sha256']))
report=dict(version='v507',allFBXEmbeddedVideoBytesMatchSource=True,format='FBX',sourceWholeVersion='v497',sha256=a['files']['fbx']['sha256'],videos=videos,channelConnections=connections,productionComplete=False);(O/'whole_fbx_embedded_material_audit_v507.json').write_text(json.dumps(report,indent=2));print(json.dumps(connections,indent=2))
