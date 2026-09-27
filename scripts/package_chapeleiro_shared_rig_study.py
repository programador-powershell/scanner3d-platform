"""Preserve reviewed experimental skins and evidence without promoting them.

The canonical gallery and protected masters are not rewritten. Full local
editables remain intact regardless of size; this package is not the final FBX.
"""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',required=True);parser.add_argument('--notes',required=True);parser.add_argument('--output',required=True)
parser.add_argument('--historical',action='append',default=[])
args=parser.parse_args();root=Path(args.root);out=Path(args.output)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,value:Path(p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
notes=read(args.notes)
if set(notes)!={'foundation','whole'} or any(not n for n in notes.values()):raise ValueError('Supply actual own-photo/motion inspection differences.')
record=read(root/'generation.json');skin=read(root/'skin_audit.json')
if sha(record['editableBlend'])!=record['editableBlendSha256']:raise ValueError('Changed complete local editable.')
if record['riggedActualPieces']!=230 or not skin['actualRawGeometryUnchanged'] or not skin['actualClothFieldWeightsUnchanged']:
    raise ValueError('Missing actual shared-skin or preservation evidence.')
if any(p['unweightedVertices'] or p['maximumNormalizationError']>1e-7 or p['maximumInfluences']>4 for p in skin['pieces']):
    raise ValueError('Invalid actual weighted garment.')
if out.exists():raise ValueError('Preserve existing study packages.')
out.mkdir(parents=True)
def copy(source,relative,digest=None):
    source=Path(source);actual=sha(source)
    if digest and actual!=digest:raise ValueError('Changed actual artifact: '+str(source))
    if source.stat().st_size>=100*1024*1024:raise ValueError('Retain the full local checkpoint; do not truncate it for Git.')
    target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    if sha(target)!=actual:raise ValueError('Changed artifact while copying.')
    return {'file':str(Path(relative).as_posix()),'sha256':actual,'bytes':target.stat().st_size}

families={}
for family,expected in [('foundation',229),('whole',1)]:
    generation=read(root/(family+'_generation.json'));motion=read(root/('motion_'+family)/'motion_comparison.json')
    comparison=read(root/('rest_'+family)/'comparison.json');model=generation['model'];digest=generation['modelSha256']
    if {sha(model),digest,motion['modelSha256'],comparison['modelSha256']}!={digest}:raise ValueError('Mixed model versions in actual evidence.')
    photo=generation['sourcePhoto'];photo_hash=generation['sourcePhotoSha256']
    if {sha(photo),photo_hash,motion['sourcePhotoSha256'],comparison['sourcePhotoSha256']}!={photo_hash}:raise ValueError('Mixed stage photos.')
    content=Path(model).read_bytes();size=struct.unpack_from('<I',content,12)[0];document=json.loads(content[20:20+size])
    nodes=[n for n in document.get('nodes',[]) if 'mesh' in n and 'skin' in n]
    clips=[a.get('name','') for a in document.get('animations',[])]
    if len(nodes)!=expected or len(document.get('skins',[]))!=1 or motion['actualImportedSkeletons']!=1:
        raise ValueError('Actual exported shared skeleton/piece count changed.')
    if not all(any(n.startswith(label+' /') for n in clips) for label in ['Walk','Run','Jump','Attack']):raise ValueError('Missing required exported clip.')
    if len(motion['clips'])!=4 or any(len(c['poses'])!=3 for c in motion['clips']):raise ValueError('Missing actual pose evidence.')
    model_artifact=copy(model,family+'/skin_study.glb',digest)
    photo_artifact=copy(photo,family+'/source_photo.png',photo_hash)
    comparison['model']=model_artifact['file'];comparison['sourcePhoto']=photo_artifact['file'];comparison['status']='needs_refinement'
    comparison['visibleDifferences']=notes[family];comparison['visualReviewPerformed']=True
    comparison['displayModel']=model_artifact
    comparison['comparisonBoard']=copy(comparison['comparisonBoard']['file'],family+'/photo_vs_geometry.jpg',comparison['comparisonBoard']['sha256'])
    for view,artifact in comparison['renders'].items():
        comparison['renders'][view]={**artifact,**copy(artifact['file'],family+'/rest/'+view+'.png',artifact['sha256'])}
    if set(comparison['renders'])!={'front','side','back','threequarter'}:raise ValueError('Missing actual four-view evidence.')
    motion['model']=model_artifact['file'];motion['sourcePhoto']=photo_artifact['file'];motion['status']='needs_refinement'
    motion['visibleDifferences']=notes[family];motion['visualReviewPerformed']=True
    motion['contactBoard']=copy(motion['contactBoard']['file'],family+'/photo_vs_shared_skin_motion.jpg',motion['contactBoard']['sha256'])
    for clip in motion['clips']:
        for pose in clip['poses']:
            artifact=copy(pose['render'],family+'/motion/'+Path(pose['render']).name,pose['renderSha256']);pose['render']=artifact['file']
    write(out/family/'comparison.json',comparison);write(out/family/'motion_comparison.json',motion)
    families[family]={'model':model_artifact,'sourcePhoto':photo_artifact,'actualSkinnedMeshes':len(nodes),'actualSkeletons':1,
        'actualJoints':len(document['skins'][0]['joints']),'actualClips':clips,'visualStatus':'needs_refinement',
        'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False}
copy(root/'shared_rig_bind.json','shared_rig_bind.json');copy(root/'skin_audit.json','skin_audit.json')
provenance={'localGeneration':record,'sourceGenerationFile':str((root/'generation.json').resolve()),
    'fullEditableRetained':{'file':record['editableBlend'],'sha256':record['editableBlendSha256'],'bytes':record['editableBytes']},
    'historicalLocalCheckpoints':[],'additionalCreditsConsumed':0}
for directory in args.historical:
    folder=Path(directory);prior=read(folder/'generation.json');history={'folder':str(folder.resolve()),'generation':prior,'actualBoards':{}}
    for family in ['foundation','whole']:
        for kind,filename in [('motion','photo_vs_shared_skin_motion.jpg'),('rest','photo_vs_geometry.jpg')]:
            file=folder/(('motion_' if kind=='motion' else 'rest_')+family)/filename
            history['actualBoards'][family+'_'+kind]=copy(file,'historical/'+folder.name+'/'+family+'_'+filename)
    provenance['historicalLocalCheckpoints'].append(history)
write(out/'local_provenance.json',provenance)
write(out/'checkpoint.json',{'status':'needs_refinement','scope':'shared rig for current 229 foundation pieces and intact native exterior',
    'families':families,'fullLocalEditableBytes':record['editableBytes'],'fullLocalEditableSha256':record['editableBlendSha256'],
    'actualClothFieldWeightsUnchanged':True,'actualRawGeometryUnchanged':True,'canonicalGalleryPromoted':False,
    'allLayersFinished':False,'fidelityVerified':False,'motionVerified':False,'clothCollisionVerified':False,
    'finalFbxExported':False,'nextVariantMayStart':False,'additionalCreditsConsumed':0,'visibleDifferences':notes})
print('REVIEWED_EXPERIMENTAL_RIG_PRESERVED',json.dumps({'output':str(out.resolve()),'families':list(families),'finished':False}))
