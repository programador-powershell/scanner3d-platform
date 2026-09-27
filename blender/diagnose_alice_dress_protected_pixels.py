"""Attribute render differences to actual intact mesh faces without saving a model."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generation',required=True);p.add_argument('--baseline',required=True)
p.add_argument('--probes',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);read=lambda s:json.loads(Path(s).read_text())
g,b=read(a.generation),read(a.baseline)
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
whole=bpy.data.objects[g['nativeWholeObject']];mesh=whole.data;mesh.calc_loop_triangles()
points=np.array([whole.matrix_world@v.co for v in mesh.vertices])
triangles=np.array([t.vertices[:] for t in mesh.loop_triangles],np.int32)
polygon_ids=np.array([t.polygon_index for t in mesh.loop_triangles],np.int32)
tree=BVHTree.FromPolygons(points.tolist(),triangles.tolist(),all_triangles=True)
uvs=[dict(name=l.name,active=l==mesh.uv_layers.active,activeRender=l.active_render) for l in mesh.uv_layers]
materials=[]
for i,m in enumerate(mesh.materials):
    nodes=[]
    for n in m.node_tree.nodes:
        nodes.append(dict(type=n.type,name=n.name,uvMap=getattr(n,'uv_map',None),image=n.image.name if n.type=='TEX_IMAGE' and n.image else None,vectorLinks=[(q.from_node.name,q.from_socket.name) for q in n.inputs['Vector'].links] if 'Vector' in n.inputs else []))
    materials.append(dict(index=i,name=m.name,nodes=nodes))
probes=np.load(a.probes);rows=[]
for row in b['renders']:
    if row['kind']!='basecolor':continue
    view=row['view'];cam=Matrix(row['cameraWorldMatrix']);proj=np.array(row['cameraProjectionMatrix'])
    direction=-(cam.to_3x3()@Vector((0,0,1)))
    by_slot={};changed_hits=[]
    for x,y,delta in probes[view]:
        ndc=np.array([(x+.5)/b['resolution'][0]*2-1,1-(y+.5)/b['resolution'][1]*2])
        local=(ndc-proj[:2,3])/np.diag(proj)[:2]
        origin=cam@Vector((float(local[0]),float(local[1]),0))
        location,normal,index,distance=tree.ray_cast(origin,direction,b['orthoScale']*6)
        slot=mesh.polygons[int(polygon_ids[index])].material_index if index is not None else -1
        by_slot.setdefault(slot,[]).append(int(delta))
        if delta>8 and slot in (0,1):changed_hits.append((int(x),int(y),int(delta),int(polygon_ids[index])))
    rows.append(dict(view=view,materialHitDifferences={str(k):dict(count=len(v),maximum=max(v),greaterThan8=sum(d>8 for d in v)) for k,v in by_slot.items()},protectedHighDifferenceHits=changed_hits[:80]))
report=dict(generation=a.generation,uvLayers=uvs,materials=materials,views=rows,sourceUnchanged=hashlib.sha256(Path(g['editableBlend']).read_bytes()).hexdigest()==g['editableBlendSha256'])
Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(uvLayers=uvs,views=[dict(view=r['view'],materialHitDifferences=r['materialHitDifferences']) for r in rows])))
