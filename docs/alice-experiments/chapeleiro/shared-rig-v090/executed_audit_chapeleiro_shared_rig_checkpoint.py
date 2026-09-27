"""Reopen the complete local study and verify actual rig/cloth definitions."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(args.generation);record=json.loads(path.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(record['editableBlend'])!=record['editableBlendSha256']:raise ValueError('Changed full checkpoint.')
audit=json.loads((path.parent/'skin_audit.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=record['editableBlend']);scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE']
if len(rigs)!=1 or len(rigs[0].data.bones)!=173:raise ValueError('Changed actual common skeleton.')
rig=rigs[0];bones={b.name for b in rig.data.bones};pieces=[]
for entry in audit['pieces']:
    obj=bpy.data.objects[entry['mesh']];modifiers=[m for m in obj.modifiers if m.type=='ARMATURE']
    if len(modifiers)!=1 or modifiers[0].object!=rig or obj.parent!=rig:raise ValueError('Lost actual shared-rig attachment.')
    indices={g.index for g in obj.vertex_groups if g.name in bones};error=0.;unweighted=0;maximum=0
    for vertex in obj.data.vertices:
        weights=[g.weight for g in vertex.groups if g.group in indices and g.weight>0]
        unweighted+=not bool(weights);error=max(error,abs(sum(weights)-1));maximum=max(maximum,len(weights))
    if unweighted or error>1e-7 or maximum>4:raise ValueError('Invalid weights in reopened full checkpoint.')
    pieces.append({'mesh':obj.name,'vertices':len(obj.data.vertices),'unweighted':unweighted,'maximumWeightError':error,'maximumInfluences':maximum})
cages=[]
for entry in audit['authoringCages']:
    obj=bpy.data.objects[entry['mesh']];order=[m.type for m in obj.modifiers]
    if order!=entry['modifierOrder'] or any(name not in obj.vertex_groups for name in entry['authoredFields']):
        raise ValueError('Lost original cloth definitions or modifier order.')
    if order[0]!='ARMATURE' or obj.modifiers[0].object!=rig:raise ValueError('Actual support does not receive the common skeleton.')
    cages.append({'mesh':obj.name,'modifierOrder':order,'authoredFields':entry['authoredFields'],
        'inheritedSurfaceDeformNeedsMotionCompositionReview':'SURFACE_DEFORM' in order,'clothMotionVerified':False})
linked=[o for o in scene.objects if o.type=='MESH' and o.data.library]
if len(linked)!=1:raise ValueError('Missing intact protected exterior library.')
master=linked[0];file=bpy.path.abspath(master.data.library.filepath)
if sha(file)!='ab9af2be98449a3cc0d2d1f593bbd52243fc5be26dd28bbc0c8868bed69dc9d9':raise ValueError('Changed protected whole library.')
mesh=master.data;xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
loops=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('vertex_index',loops)
counts=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('loop_total',counts)
geometry_sha=hashlib.sha256(xyz.tobytes()+loops.tobytes()+counts.tobytes()).hexdigest()
if geometry_sha!='10d6825fa75b34de11fbd71b7b61f69c71ec14589fb1cd035d36a6c07c5d7ece':raise ValueError('Changed actual uncut whole geometry.')
tracks=[t for t in rig.animation_data.nla_tracks if t.strips]
if len(tracks)!=4 or not all(any(t.name.startswith(label+' /') for t in tracks) for label in ['Walk','Run','Jump','Attack']):
    raise ValueError('Lost actual action tracks on reopen.')
images=[i for i in bpy.data.images if i.type=='IMAGE' and i.source=='FILE' and i.users]
if any(not i.packed_file for i in images):raise ValueError('A used file image is unpacked.')
report={'editableSha256':record['editableBlendSha256'],'editableBytes':Path(record['editableBlend']).stat().st_size,
    'actualArmatures':1,'actualBones':len(bones),'actualSkinnedPreviewPieces':len(pieces),'pieces':pieces,'authoringCages':cages,
    'protectedLibrarySha256':sha(file),'protectedWholeGeometrySha256':geometry_sha,'protectedWholeVertices':len(mesh.vertices),
    'actualActionTracks':[t.name for t in tracks],'packedUsedFileImages':len(images),'reopenedWithoutSaving':True,
    'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,'allLayersFinished':False,
    'limitation':'Preserved skins/actions/cloth fields are construction evidence, not full pose/contact or physical simulation approval.'}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('ACTUAL_FULL_RIG_CHECKPOINT_REOPENED',len(pieces),flush=True)
