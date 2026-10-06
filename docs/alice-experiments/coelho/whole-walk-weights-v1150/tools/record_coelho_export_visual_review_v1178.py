"""Record actual inspected exports and correct an inherited filter-audit label."""
from pathlib import Path
import json,hashlib,datetime
R=Path('F:/Alice/SharedProduction');O=R/'Blender/Work/alice_coelho/tripo_h31_budget55_v001';T=R/'Tools'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pkg=read(O/'package_skin_export_v1150.json')
records=[]
for kind,version in [('glb',1172),('fbx',1176)]:
    p=O/f'reimport_whole_{kind}_audit_v{version}.json';j=read(p)
    assert j['sha256']==pkg['files'][kind]['sha256'] and len(j['renders'])==8
    for row in j['renders']:
        assert hashlib.sha256((R/row['path']).read_bytes()).hexdigest()==row['sha256']
    if kind=='glb':
        oldSHA=hashlib.sha256(p.read_bytes()).hexdigest()
        assert j['officialFilterAnalyticAudit1165Used']
        j['officialFilterAnalyticAudit1165Used']=False
        j['officialFilterAnalyticAudit1171Used']=True
        j['filterAuditMetadataCorrection']='Inherited field name corrected; executed source already reads actual1171. Numeric pose/corner results and render hashes unchanged.'
        p.write_text(json.dumps(j,indent=2),encoding='utf-8')
        script=T/'reimport_coelho_whole_true_walk_glb_v1172.py'
        code=script.read_text(encoding='utf-8-sig')
        assert "officialFilterAnalyticAudit1165Used=(kind=='glb')" in code
        script.write_text(code.replace("officialFilterAnalyticAudit1165Used=(kind=='glb')", "officialFilterAnalyticAudit1165Used=False,officialFilterAnalyticAudit1171Used=(kind=='glb')"),encoding='utf-8')
    records.append(dict(format=kind,report=p.relative_to(R).as_posix(),reportSHA256=hashlib.sha256(p.read_bytes()).hexdigest(),renders=j['renders'],allEightImagesActuallyInspected=True))
report=dict(version='v1178',records=records,allSixteenEffectiveExportImagesInspected=True,inspection='Actual GLB1172 Walk views, six unchanged1166 neutral/manual views; actual FBX1176 clock/2elbow/2Walk views plus three unchanged1173 rest views. Old Walk1166 views rejected as original-Walk proof.',visibleLimitations=['Solid hair stretches and intersects shoulder area during Walk; individual strands not completed','Puff-sleeve attachment still deforms at torso boundary','Separate authored cloth layers remain provisionally pelvis-bound','Canonical face/body and anatomical168cm not approved'],glb1172ReportBeforeMetadataCorrectionSHA256=oldSHA,onlyMetadataLabelAndReproductionScriptFieldCorrected=True,meshExportAndNumericTestsNotChanged=True,productionComplete=False,createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat())
p=O/'actual_export_visual_review_v1178.json';assert not p.exists();p.write_text(json.dumps(report,indent=2),encoding='utf-8');print('SIXTEEN_ACTUAL_IMAGES_REVIEWED_WHOLE_INTERMEDIATE_ONLY')
