"""Apply measured surface weights to the intact native exterior only."""
import hashlib,json
from pathlib import Path
import numpy as np

def assign_native_surface_weights(obj,rig,guide,parent,whole):
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    record=json.loads(Path(guide).read_text(encoding='utf-8'))
    if record['parentEditableSha256']!=parent['editableBlendSha256'] or record['parentWholeModelSha256']!=whole['modelSha256']:
        raise ValueError('Surface weights belong to another actual parent.')
    if record['sourcePhotoSha256']!=whole['sourcePhotoSha256'] or record['rawGeometrySha256']!=parent['sourceWholeGeometrySha256']:
        raise ValueError('Surface weights belong to another geometry/photo.')
    if sha(record['weightsFile'])!=record['weightsSha256']:raise ValueError('Changed inferred weights.')
    names=record['boneNames']
    if names!=[b.name for b in rig.data.bones]:raise ValueError('Changed actual common joint map.')
    data=np.load(record['weightsFile']);weights=data['weights'];preserve=data['preserved_vertices']
    if weights.shape!=(len(obj.data.vertices),len(names)) or preserve.shape!=(len(obj.data.vertices),):
        raise ValueError('Changed original surface vertex layout.')
    if not np.isfinite(weights).all() or np.any(weights<0) or np.max(abs(weights.sum(1)-1))>1e-7 or np.max((weights>0).sum(1))>4:
        raise ValueError('Invalid inferred skin weights.')
    integers=np.rint(weights*65536).astype(np.int32)
    if not np.array_equal(weights,integers.astype(np.float32)/65536) or not np.all(integers.sum(1)==65536):
        raise ValueError('Lost exact skin quantization.')
    original=np.zeros_like(weights);indexed={name:i for i,name in enumerate(names)}
    groups={g.index:indexed[g.name] for g in obj.vertex_groups if g.name in indexed}
    for v in obj.data.vertices:
        for group in v.groups:
            if group.group in groups:original[v.index,groups[group.group]]=group.weight
    if not np.array_equal(original[preserve],weights[preserve]):raise ValueError('Changed protected separate arm/hand weights.')
    obj.vertex_groups.clear()
    if any(v.groups for v in obj.data.vertices):raise ValueError('Inherited native weights remain.')
    used=[]
    for column,name in enumerate(names):
        values=integers[:,column];indices=np.flatnonzero(values>0)
        if not len(indices):continue
        group=obj.vertex_groups.new(name=name);used.append(name)
        for value in np.unique(values[indices]):group.add(np.flatnonzero(values==value).tolist(),int(value)/65536,'REPLACE')
    error=0;unweighted=0;maximum=0
    for v in obj.data.vertices:
        actual=[g.weight for g in v.groups if g.weight>0]
        unweighted+=not bool(actual);error=max(error,abs(sum(actual)-1));maximum=max(maximum,len(actual))
    if unweighted or error>1e-7 or maximum>4:raise ValueError('Applied native weights failed actual vertex verification.')
    return {'mesh':obj.name,'role':'whole_native','vertices':len(obj.data.vertices),'boneGroups':used,
        'unweightedVertices':unweighted,'maximumNormalizationError':error,'maximumInfluences':maximum,
        'quantization':65536,'preservedClothFields':False,'preservedSeparateArmVertices':int(preserve.sum()),
        'method':record['method'],'inferenceSha256':sha(guide),'weightsSha256':record['weightsSha256'],
        'nativeSurfaceOwnershipInferred':True,'nativeSurfaceOwnershipVerified':False,
        'geometryChanged':False,'motionVerified':False,'clothCollisionVerified':False}
