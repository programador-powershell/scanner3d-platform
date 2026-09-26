"""Keep the intact exterior in its existing Git-tracked Blender library.

Only replace the hidden master's local data by identical linked data. Garment
geometry, modifiers and bindings remain in the foundation's editable file.
"""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation',required=True)
parser.add_argument('--master',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads(Path(args.generation).read_text(encoding='utf-8'))
if sha(parent['editableBlend'])!=parent['editableBlendSha256']:
    raise ValueError('Changed foundation source.')
out=Path(args.output)
if out.exists(): raise ValueError('Use a new editable checkpoint directory.')
out.mkdir(parents=True)
master=out/'alice-vestido-chapeleiro.blend'
shutil.copyfile(args.master,master)
if sha(master)!=sha(args.master): raise ValueError('Changed master library copy.')
bpy.ops.wm.open_mainfile(filepath=parent['editableBlend'])
def mesh_hash(mesh):
    co=np.empty(len(mesh.vertices)*3,np.float32)
    mesh.vertices.foreach_get('co',co)
    loops=np.empty(len(mesh.loops),np.int32)
    mesh.loops.foreach_get('vertex_index',loops)
    counts=np.empty(len(mesh.polygons),np.int32)
    mesh.polygons.foreach_get('loop_total',counts)
    return hashlib.sha256(co.tobytes()+loops.tobytes()+counts.tobytes()).hexdigest()
before={o.name:mesh_hash(o.data) for o in bpy.context.scene.objects if o.type=='MESH'}
obj=bpy.data.objects['Complete baked Tripo outfit / preserved / hidden for internal review']
expected=mesh_hash(obj.data)
with bpy.data.libraries.load(str(master),link=True) as (source,target):
    if obj.data.name not in source.meshes: raise ValueError('The existing exterior mesh is absent from the master.')
    target.meshes=[obj.data.name]
linked=target.meshes[0]
if mesh_hash(linked)!=expected: raise ValueError('Linked master would change the complete exterior.')
obj.data=linked
linked.library.filepath='//alice-vestido-chapeleiro.blend'
removed=bpy.data.orphans_purge(do_recursive=True)
if any(mesh_hash(bpy.data.objects[name].data)!=value for name,value in before.items()):
    raise ValueError('Editable packaging changed actual geometry.')
editable=out/'chapeleiro_foundation_lower.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(editable),compress=True,relative_remap=False)
if editable.stat().st_size>=100*1024*1024: raise ValueError('Editable file still exceeds GitHub hard limit.')
report={**parent,'editableBlend':str(editable.resolve()),'editableBlendSha256':sha(editable),
        'editablePackaging':'identical intact exterior linked to existing Git-tracked Blender master',
        'editableLibraryDependencies':[{'file':master.name,'sha256':sha(master),'bytes':master.stat().st_size,
                                         'mesh':linked.name,'meshGeometrySha256':expected}],
        'allActualMeshCoordinatesAndFacesUnchanged':True,
        'editablePackagingSource':str(Path(args.generation).resolve()),
        'editablePackagingSourceSha256':sha(args.generation),
        'unusedDatablocksRemoved':removed}
(out/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FOUNDATION_LINKED_MASTER_SAVED',json.dumps({'editableBytes':editable.stat().st_size,
      'masterBytes':master.stat().st_size,'allGeometryUnchanged':True}),flush=True)
