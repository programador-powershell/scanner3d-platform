"""Integrate the visibility-tested posterior atlas without changing topology or weights."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
import bpy, numpy as np
p=argparse.ArgumentParser();p.add_argument('--bake',required=True);p.add_argument('--texture',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);assert not out.exists();out.mkdir(parents=True)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
b=json.loads(Path(a.bake).read_text());g=json.loads(Path(b['sourceGeneration']).read_text())
assert sha(g['editableBlend'])==b['sourceBlendSha256']==g['editableBlendSha256']
assert b['visibleTexels']>0 and b['sourceUnchanged']
bpy.ops.wm.open_mainfile(filepath=g['editableBlend'])
image=bpy.data.images.load(a.texture,check_existing=False);assert tuple(image.size)==(4096,4096)
image.name='Chapeleiro / posterior visibility atlas / 4K';image.colorspace_settings.name='sRGB';image.pack()
coords=np.load(b['uvCoordinates'])
def signature(obj):
    h=hashlib.sha256()
    for v in obj.data.vertices:
        h.update(np.asarray(v.co,np.float32).tobytes())
        for w in v.groups:h.update(np.asarray([w.group,w.weight],np.float64).tobytes())
    for f in obj.data.polygons:h.update(np.asarray(f.vertices,np.int32).tobytes())
    return h.hexdigest()
checks={}
for row in b['objects']:
    obj=bpy.data.objects[row['name']];before=signature(obj);uv=obj.data.uv_layers.new(name='PosteriorUV4K')
    assert len(uv.data)==row['loops']==len(coords[row['key']])
    uv.data.foreach_set('uv',coords[row['key']].ravel())
    for slot in row['materialSlots']:
        mat=obj.data.materials[slot].copy();mat.name='Chapeleiro / posterior corset / visible UV4K';obj.data.materials[slot]=mat
        tex=next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE');tex.image=image
        mapping=mat.node_tree.nodes.new('ShaderNodeUVMap');mapping.uv_map=uv.name;mat.node_tree.links.new(mapping.outputs['UV'],tex.inputs['Vector'])
    assert signature(obj)==before;checks[obj.name]=before
blend=out/'chapeleiro_complete_posterior_uv4k.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
r=dict(g);r.update(parentGeneration=b['sourceGeneration'],editableBlend=str(blend),editableBlendSha256=sha(blend),published=False)
r['posteriorBodice']=dict(g['posteriorBodice'],visibleUv4kBakePending=False,bakeManifest=a.bake,texture=a.texture,textureSha256=sha(a.texture),geometryAndWeightSignatures=checks,comparisonRendersPending=True)
(out/'generation.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copyfile(__file__,out/'executed_integration.py')
print('POSTERIOR_UV4K_INTEGRATED',str(blend),flush=True)
