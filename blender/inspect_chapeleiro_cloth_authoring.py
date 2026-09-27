"""Inspect actual cloth, supports and secondary joints without changing a checkpoint."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--generation',required=True);parser.add_argument('--output',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);path=Path(args.generation)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(path);assert sha(r['editableBlend'])==r['editableBlendSha256']
bpy.ops.wm.open_mainfile(filepath=r['editableBlend']);scene=bpy.context.scene
rigs=[o for o in scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
rig=rigs[0];schema=read(path.parent/'shared_rig_bind.json');audit=read(path.parent/'skin_audit.json')
def settings(block,keys):return {k:getattr(block,k) for k in keys if hasattr(block,k)}
def modifiers(obj):
 rows=[]
 for m in obj.modifiers:
  row={'name':m.name,'type':m.type,'showViewport':m.show_viewport,'showRender':m.show_render}
  if m.type=='ARMATURE':row['rig']=m.object.name if m.object else None
  if m.type=='SURFACE_DEFORM':row.update(target=m.target.name if m.target else None,isBound=m.is_bound)
  if m.type=='CLOTH':
   row['settings']=settings(m.settings,['quality','mass','time_scale','air_damping','tension_stiffness','compression_stiffness','shear_stiffness','bending_stiffness','pin_stiffness','vertex_group_mass','use_dynamic_mesh','effector_weights'])
   row['settings'].pop('effector_weights',None)
   row['collision']=settings(m.collision_settings,['use_collision','collision_quality','distance_min','friction','use_self_collision','self_distance_min','self_friction'])
   row['cache']=settings(m.point_cache,['frame_start','frame_end','is_baked','is_outdated','use_disk_cache'])
  rows.append(row)
 return rows
rows=[]
for entry in audit['authoringCages']:
 obj=bpy.data.objects[entry['mesh']];p=np.array([obj.matrix_world@v.co for v in obj.data.vertices])
 receiver=bpy.data.objects['Authoring / '+entry['receiver']]
 preview=bpy.data.objects[entry['receiver']]
 fields={}
 for name in entry['authoredFields']:
  group=obj.vertex_groups[name];values=np.array([next((m.weight for m in v.groups if m.group==group.index),0) for v in obj.data.vertices])
  fields[name]={'minimum':float(values.min()),'maximum':float(values.max()),'positiveVertices':int((values>0).sum()),'fullyPinnedVertices':int((values>.999).sum())}
 rows.append({'mesh':obj.name,'receiver':entry['receiver'],'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'bounds':[p.min(0).tolist(),p.max(0).tolist()],
  'supportModifiers':modifiers(obj),'authoringReceiverModifiers':modifiers(receiver),'exportedPreviewModifiers':modifiers(preview),'authoredFields':fields,
  'clothFamily':schema['pieceFamilies'].get(entry['receiver'])})
report={'editableSha256':r['editableBlendSha256'],'actualAuthoringCages':rows,'clothFamilies':schema['clothFamilies'],
 'secondaryBoneParents':{b.name:b.parent.name if b.parent else None for b in rig.data.bones if 'Cloth_' in b.name},
 'actualCollisionObjects':[o.name for o in scene.objects if any(m.type=='COLLISION' and m.show_viewport for m in o.modifiers)],
 'sceneUnits':{'system':scene.unit_settings.system,'scaleLength':scene.unit_settings.scale_length,'fps':scene.render.fps},
 'sourceEditableUnchanged':sha(r['editableBlend'])==r['editableBlendSha256'],'saved':False,'clothCollisionVerified':False,'motionVerified':False}
out=Path(args.output);assert not out.exists();out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('ACTUAL_CLOTH_AUTHORING_INSPECTED',len(rows),flush=True)
