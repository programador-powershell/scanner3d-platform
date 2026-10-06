import bpy,json,hashlib
from pathlib import Path
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';a=json.loads((O/'rear_bow_whole_integration_audit_v497.json').read_text(encoding='utf-8-sig'));rows=[]
for row in a['objects']:
 ob=bpy.data.objects[row['name']]
 for mat in ob.data.materials:
  if any(r['name']==mat.name for r in rows):continue
  nodes=mat.node_tree.nodes;p=next(n for n in nodes if n.type=='BSDF_PRINCIPLED');r=dict(name=mat.name,principledInputs={},images=[],nodes=[])
  for socket in p.inputs:
   if socket.name in ['Base Color','Metallic','Roughness','Alpha','Normal','Coat Weight','Specular IOR Level']:
    v=socket.default_value;r['principledInputs'][socket.name]=dict(default=list(v) if hasattr(v,'__len__') else v,links=[dict(node=l.from_node.name,socket=l.from_socket.name,type=l.from_node.type) for l in socket.links])
  for n in nodes:
   if n.type=='TEX_IMAGE' and n.image:
    im=n.image;packed=im.packed_file;assert packed,(mat.name,im.name);sha=hashlib.sha256(packed.data).hexdigest();path=O/'MaterialAuditSource505'/(sha+'.png');path.parent.mkdir(exist_ok=True)
    if not path.exists():path.write_bytes(packed.data)
    r['images'].append(dict(node=n.name,name=im.name,size=list(im.size),colorSpace=im.colorspace_settings.name,path=path.relative_to(R).as_posix(),sha256=sha,outputs=[dict(fromSocket=l.from_socket.name,toNode=l.to_node.name,toSocket=l.to_socket.name,toType=l.to_node.type) for l in mat.node_tree.links if l.from_node==n]))
   if n.type=='NORMAL_MAP':r['nodes'].append(dict(name=n.name,type=n.type,space=n.space,uvMap=n.uv_map,strength=n.inputs['Strength'].default_value,links=[dict(input=l.to_socket.name,node=l.from_node.name,socket=l.from_socket.name) for l in mat.node_tree.links if l.to_node==n]))
  rows.append(r)
report=dict(version='v505',sourceWholeVersion='v497',materials=rows,productionComplete=False);(O/'whole_source_material_semantics_v505.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('SOURCE_MATERIALS_DUMPED',len(rows),flush=True)
