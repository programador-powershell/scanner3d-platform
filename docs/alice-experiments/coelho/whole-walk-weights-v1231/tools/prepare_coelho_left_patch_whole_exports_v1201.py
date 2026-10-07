"""Run only after actual five native images are inspected; all outputs are whole-character WIP."""
from pathlib import Path
import json,hashlib,py_compile
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=R/'Tools';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
n=read(O/'left_patch_weights_whole_CANDIDATE_v1200/manifest.json');a=read(O/'shoulder_topology_weight_STUDY_v1199/audit.json');assert n['all42NativeFramesVerified'] and n['allFiveSameCameraRendersComplete'] and n['sourceAndLibraryUnchanged'] and len(n['renders'])==5
for r in n['renders']:assert hashlib.sha256((R/r['path']).read_bytes()).hexdigest()==r['sha256']
assert all(f['candidate']['localBad']==0 for f in a['all42Frames']);total=sum(f['shortRestEdgesExpandedBeyond12cm'] for f in n['nativeFrames']);assert total==681
review=dict(version='v1201',acceptedForLimitedWholeWeightCheckpointExport=True,allFiveActualNativeWholeImagesInspected=True,all42OriginalNativeWalkFramesVerified=True,globalRemainingBadEdgeOccurrencesAcross42Frames=total,globalMaximumInOneFrame=max(f['shortRestEdgesExpandedBeyond12cm'] for f in n['nativeFrames']),localSixPatchBadEdgesAcross42Frames=0,only450WeightsChangedAfter1191=True,allOutsideWeightsAndGeometryUVNormalsMaterialsPreserved=True,observation='Local left sleeve/hair-adjacent fragments no longer stretch into long triangles; original solid hair and other shoulders still deform and intersect. This is a whole weight checkpoint, not final cloth, hair, canonical anatomy or gameplay.',canonicalIdentityApproved=False,anatomical168cmApproved=False,individualHairComplete=False,clothPhysicsApproved=False,rigComplete=False,gameplayApproved=False,productionComplete=False)
p=O/'native_left_patch_whole_visual_review_v1201.json';assert not p.exists();p.write_text(json.dumps(review,indent=2),encoding='utf-8')
def save(name,s):
    p=T/name;assert not p.exists();p.write_text(s,encoding='utf-8');py_compile.compile(str(p),doraise=True)
s=(T/'capture_coelho_true_walk_motion_v1170.py').read_text(encoding='utf-8-sig').replace('distinct_stocking_cloth_weights_CANDIDATE_v1146','left_patch_weights_whole_CANDIDATE_v1200').replace('v1170','v1204')
s=s.replace("observed=np.load(O/'whole_skin_motion_walk_study_frame11_v1204.npz')['positions'];original=np.load(O/'walk_continuity_independent_REVIEW_v1147/candidate_whole_frame11_v1147.npz')['positions']", "observed=np.load(O/'whole_skin_motion_walk_study_frame31_v1204.npz')['positions'];original=np.load(O/'shoulder_topology_weight_STUDY_v1199/frame31_topology_comparison_v1199.npz')['candidate']")
s=s.replace('walkReferenceMatchesIndependentOriginalSourceFrame11MaxM','walkReferenceMatchesIndependentCandidateSourceFrame31MaxM');save('capture_coelho_left_patch_true_motion_v1204.py',s)
s=(T/'export_coelho_whole_distinct_walk_weight_v1148.py').read_text(encoding='utf-8-sig').replace('distinct_stocking_cloth_weights_CANDIDATE_v1146','left_patch_weights_whole_CANDIDATE_v1200').replace('v1148','v1202').replace("sourceWorkingVersion='v1146'","sourceWorkingVersion='v1200'")
old="check=json.loads((O/'walk_continuity_independent_REVIEW_v1147/audit.json').read_text(encoding='utf-8-sig'));assert len(check['candidate']['frames'])==42 and check['candidate']['maxSeamSeparationM']<2e-6;"
assert old in s;s=s.replace(old,"check=json.loads((O/'native_left_patch_whole_visual_review_v1201.json').read_text(encoding='utf-8-sig'));assert check['acceptedForLimitedWholeWeightCheckpointExport'] and report['all42NativeFramesVerified'] and max(r['samePhysicalSeamMaxM'] for r in report['nativeFrames'])<2e-6;").replace("assert len(report['renders'])==4","assert len(report['renders'])==5")
save('export_coelho_whole_left_patch_weights_v1202.py',s)
pipeline="""from pathlib import Path
T=Path('F:/Alice/SharedProduction/Tools')
for name in ['capture_coelho_left_patch_true_motion_v1204.py','export_coelho_whole_left_patch_weights_v1202.py']:
    p=T/name;exec(compile(p.read_text(encoding='utf-8-sig'),str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
""";save('export_coelho_capture_then_whole_left_patch_v1202.py',pipeline)
s=(T/'fix_coelho_distinct_walk_glb_sheen_v1150.py').read_text(encoding='utf-8-sig').replace('v1148','v1202').replace('v1150','v1203').replace("sourceWhole='v1146'","sourceWhole='v1200'");save('fix_coelho_left_patch_glb_sheen_v1203.py',s)
s=(T/'audit_coelho_true_walk_weight_filter_v1171.py').read_text(encoding='utf-8-sig').replace('v1170','v1204').replace('v1148','v1202').replace('v1150','v1203').replace('v1171','v1205');save('audit_coelho_left_patch_export_filter_v1205.py',s)
base=(T/'reimport_coelho_whole_fbx_pose_review_v1168.py').read_text(encoding='utf-8-sig').replace('v1148','v1202').replace('v1150','v1203').replace('whole_skin_motion_reference_v1147','whole_skin_motion_reference_v1204').replace('walk_export_filter_analytic_audit_v1165','walk_export_filter_analytic_audit_v1205').replace('officialFilterAnalyticAudit1165Used','officialFilterAnalyticAudit1205Used')
mem=(T/'reimport_coelho_whole_fbx_memory_review_v1176.py').read_text(encoding='utf-8-sig');start=mem.index('# Factory review process only:');end=mem.index("s.render.threads_mode='FIXED';s.render.threads=6",start);cleanup=mem[start:end]
base=base.replace("s.render.threads_mode='FIXED';s.render.threads=6",cleanup+"s.render.threads_mode='FIXED';s.render.threads=6")
base=base.replace("for label,direction in [('walk_study_frame11',(0,-4,0)),('walk_study_frame11_profile',(-4,0,0))]:\n key='walk_study_frame11'", "for label,direction in [('walk_study_frame11',(0,-4,0)),('walk_study_frame11_profile',(-4,0,0)),('walk_study_frame31',(0,-4,0)),('walk_study_frame31_left_profile',(4,0,0))]:\n key='walk_study_frame31' if '31' in label else 'walk_study_frame11'")
save('reimport_coelho_whole_left_patch_glb_v1206.py',base.replace("assert kind=='fbx'","assert kind=='glb'").replace('v1168','v1206'))
save('reimport_coelho_whole_left_patch_fbx_v1207.py',base.replace('v1168','v1207'))
for old,new in [('1151','1208'),('1152','1209'),('1153','1210'),('1154','1211'),('1155','1212')]:
    p=next(T.glob(f'verify_coelho_distinct_walk_*_v{old}.py'));s=p.read_text(encoding='utf-8-sig').replace('v1148','v1202').replace('v1150','v1203').replace(f'v{old}',f'v{new}');save(p.name.replace('distinct_walk','left_patch').replace(f'v{old}',f'v{new}'),s)
print('COMPLETE_EXPORT_CAPTURE_FILTER_REIMPORT_AND_RAW_PROOF_TOOLS_PREPARED')
