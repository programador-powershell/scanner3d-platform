"""Independent XPBD garment study on unchanged recorded photo-derived carriers.

This is a local diagnostic, not a native Blender Cloth result or an approved
game garment. Particle self contact does not establish triangle self contact.
"""
import argparse, copy, hashlib, json, shutil, sys, time
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--probe', required=True)
p.add_argument('--contacts', required=True)
p.add_argument('--output', required=True)
p.add_argument('--substeps', type=int, default=8)
p.add_argument('--iterations', type=int, default=24)
p.add_argument('--verified-body-recovery',action=argparse.BooleanOptionalAction,default=False)
p.add_argument('--layer-order-contacts',action=argparse.BooleanOptionalAction,default=False)
p.add_argument('--maximum-stretch-ratio',type=float)
p.add_argument('--damp-contact-velocity',action=argparse.BooleanOptionalAction,default=False)
p.add_argument('--moving-body-face-contacts',action=argparse.BooleanOptionalAction,default=False)
p.add_argument('--body-motion-reference-probe')
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
assert a.substeps > 0 and a.iterations > 0
assert a.maximum_stretch_ratio is None or a.maximum_stretch_ratio > 1
assert not a.damp_contact_velocity or a.verified_body_recovery
read = lambda f: json.loads(Path(f).read_text(encoding='utf-8'))
sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
r, contact = read(a.probe), read(a.contacts)
assert sha(r['dataFile']) == r['dataSha256']
assert sha(contact['dataFile']) == contact['dataSha256']
d, bodies = np.load(r['dataFile']), np.load(contact['dataFile'])
body_compatibility={'clothDataMatchesOriginalBodyQuery':r['dataSha256']==contact['sourcePhysicalDataSha256']}
if not body_compatibility['clothDataMatchesOriginalBodyQuery']:
    assert a.body_motion_reference_probe, 'Supply the original body-query cloth to prove identical recorded rig motion'
    reference=read(a.body_motion_reference_probe)
    assert sha(reference['dataFile'])==reference['dataSha256']==contact['sourcePhysicalDataSha256']
    assert reference['parentEditableSha256']==r['parentEditableSha256']
    assert reference['sourcePhotoSha256']==r['sourcePhotoSha256']==contact['sourcePhotoSha256']
    reference_data=np.load(reference['dataFile'])
    for key in ['bone_names','rig_deformations']:
        assert np.array_equal(reference_data[key],d[key]), key
    body_compatibility.update(originalBodyQueryProbe=str(Path(a.body_motion_reference_probe).resolve()),
                              originalBodyQueryDataSha256=reference['dataSha256'],
                              originalBodyQueryProbeSha256=sha(a.body_motion_reference_probe),
                              allRecordedRigMatricesAndNamesExactlyEqual=True)
if a.moving_body_face_contacts:
    assert a.verified_body_recovery and contact.get('actualBodyTrianglesFrozenBeforeDeformation')
out = Path(a.output)
assert not out.exists()
out.mkdir(parents=True)
sys.path.insert(0, str(Path(__file__).parent))
from chapeleiro_retopo_cloth_assembly import RestDetailTransfer
from chapeleiro_xpbd_surface_contacts import closed_state,outside_candidate,ordered_layer_contact,barycentric
from chapeleiro_moving_point_face_contacts import MovingBodyFaceIndex
rest = d['simulation_rest_points'].astype(np.float64)
faces = d['simulation_faces']
edges = d['simulation_edges'][~d['simulation_loose_edges']]
seams = d['physical_seam_pairs']
pins = d['simulation_pin_weights']
targets = d['actual_simulation_skin_targets'].astype(np.float64)
transfer = RestDetailTransfer(d['detail_corner_indices'], d['detail_weights'], d['detail_u'], d['detail_v'], rest, d['rest_points'])
assert np.max(np.abs(transfer.offsets-d['detail_frame_offsets'])) < 1e-6
diagonals = np.concatenate([faces[:,[0,2]], faces[:,[1,3]]])
structural = np.unique(np.sort(np.concatenate([edges,diagonals,seams]),axis=1),axis=0)
bending, start, part_ids, part_grids = [], 0, [], []
for part in r['parts']:
    rows, around = part['simulationRows'],part['simulationAround']
    grid = np.arange(start,start+rows*around).reshape(rows,around)
    part_ids.append(grid.ravel())
    part_grids.append(grid)
    bending.extend(np.stack([grid[:-2].ravel(),grid[2:].ravel()],axis=1).tolist())
    bending.extend(np.stack([grid.ravel(),np.roll(grid,-2,axis=1).ravel()],axis=1).tolist())
    start += rows*around
assert start == len(rest)
bending = np.unique(np.sort(np.asarray(bending),axis=1),axis=0)

def colors(pairs):
    used = [set() for _ in rest]
    batches = []
    for i,(u,v) in enumerate(pairs):
        color = 0
        while color in used[u] or color in used[v]: color += 1
        while len(batches) <= color: batches.append([])
        batches[color].append(i); used[u].add(color); used[v].add(color)
    for batch in batches:
        assert len(np.unique(pairs[batch])) == len(batch)*2
    return [np.asarray(batch) for batch in batches]

structural_colors, bending_colors = colors(structural), colors(bending)
mass = r['massCalibration']['actualMassPerVertexKg']
inverse = np.full(len(rest),1/mass)
fully_pinned = pins > .999
partial = (pins > 0) & ~fully_pinned
inverse[fully_pinned] = 0
movable = np.flatnonzero(~fully_pinned)
ray_directions = [Vector((.837,.324,.439)).normalized(), Vector((-.413,.823,.388)).normalized()]
dt = 1/(30*a.substeps)
structural_rest = np.linalg.norm(rest[structural[:,0]]-rest[structural[:,1]],axis=1)
bending_rest = np.linalg.norm(rest[bending[:,0]]-rest[bending[:,1]],axis=1)
adjacent = {tuple(pair) for pair in np.concatenate([structural,bending])}
margin, self_distance = .0015, .0015
positions = rest.copy(); velocity = np.zeros_like(rest)
history, rows, contact_counts = [positions.copy()], [], []
start_time = time.time()

def distances(pairs, desired, batches, multipliers, compliance):
    alpha = compliance/(dt*dt)
    for batch in batches:
        u,v = pairs[batch].T
        delta = positions[u]-positions[v]
        length = np.maximum(np.linalg.norm(delta,axis=1),1e-12)
        denom = inverse[u]+inverse[v]+alpha
        step = np.divide(-(length-desired[batch])-alpha*multipliers[batch],denom,
                         out=np.zeros(len(batch)),where=denom>0)
        multipliers[batch] += step
        correction = delta*(step/length)[:,None]
        positions[u] += inverse[u,None]*correction
        positions[v] -= inverse[v,None]*correction

def limit_stretch():
    """Unilateral mass-weighted strain bound; permits compression and folding.

    Contact can reintroduce strain afterwards. Measure the final result rather
    than treating this provisional constraint as proof of convergence.
    """
    if a.maximum_stretch_ratio is None:return 0
    count=0
    maximum=structural_rest*a.maximum_stretch_ratio
    for batch in structural_colors:
        u,v=structural[batch].T
        delta=positions[u]-positions[v]
        length=np.maximum(np.linalg.norm(delta,axis=1),1e-12)
        denominator=inverse[u]+inverse[v]
        violation=np.maximum(length-maximum[batch],0)
        count+=int(np.sum((violation>1e-10)&(denominator>0)))
        step=np.divide(-violation,denominator,out=np.zeros(len(batch)),where=denominator>0)
        correction=delta*(step/length)[:,None]
        positions[u]+=inverse[u,None]*correction
        positions[v]-=inverse[v,None]*correction
    return count

def ray_inside(tree, point, direction):
    hits=0;origin=Vector(point)
    for _ in range(128):
        location,normal,index,distance=tree.ray_cast(origin,direction,10)
        if location is None: return bool(hits%2)
        hits += 1
        origin=location+direction*1e-6
    raise ValueError('Unexpected repeated closed-body ray intersections')

def body_contact(trees, bounds, meshes=None, previous_meshes=None, velocity_contacts=None):
    count = 0
    for body_index,(tree,(low,high)) in enumerate(zip(trees,bounds)):
        ids = movable[np.all((positions[movable]>=low)&(positions[movable]<=high),axis=1)]
        for i in ids:
            nearest, normal, index, distance = tree.find_nearest(Vector(positions[i]))
            assert nearest is not None
            signed = (Vector(positions[i])-nearest).dot(normal)
            if a.verified_body_recovery:
                state=closed_state(tree,positions[i])
                if state is None:continue
                if state:
                    candidate=outside_candidate(tree,positions[i],nearest,normal,margin)
                    if candidate is not None:
                        positions[i]=candidate;count+=1
                        if velocity_contacts is not None:
                            save_velocity_contact(velocity_contacts,i,body_index,index,nearest,candidate,meshes,previous_meshes)
                    continue
                if 1e-10<distance<margin:
                    candidate=outside_candidate(tree,positions[i],nearest,normal,margin)
                    if candidate is not None:
                        positions[i]=candidate;count+=1
                        if velocity_contacts is not None:
                            save_velocity_contact(velocity_contacts,i,body_index,index,nearest,candidate,meshes,previous_meshes)
                continue
            if signed < 0:
                answers=[ray_inside(tree,positions[i],direction) for direction in ray_directions]
                if answers[0] != answers[1]: continue
                if answers[0]:
                    positions[i]=np.asarray(nearest)+np.asarray(normal)*margin
                    count += 1
                    continue
            # A point outside a concave collider can lie behind its nearest
            # triangle normal. Only actual two-ray interior agreement permits
            # a deep recovery; outside points retain the nearest-point direction.
            if 1e-10 < distance < margin:
                delta=positions[i]-np.asarray(nearest)
                positions[i]=np.asarray(nearest)+delta*(margin/distance)
                count += 1
    return count

def save_velocity_contact(records,i,body_index,triangle_index,nearest,candidate,meshes,previous_meshes):
    points,triangles=meshes[body_index]
    triangle=triangles[triangle_index]
    weights=barycentric(np.asarray(nearest),points[triangle])
    if weights is None:return
    normal=np.asarray(candidate)-np.asarray(nearest)
    length=np.linalg.norm(normal)
    if length<1e-10:return
    obstacle_velocity=np.sum((points[triangle]-previous_meshes[body_index][triangle])*weights[:,None],axis=0)/dt
    records[(int(i),body_index)]=(normal/length,obstacle_velocity)

def damp_body_contact_velocity(records,trees):
    """Inelastic normal velocity at actual recovered body contacts only.

    This removes the artificial bounce from finite position recovery while
    retaining tangential sliding. It is not friction or continuous collision.
    """
    count=0
    for (i,body_index),(normal,obstacle_velocity) in records.items():
        nearest=trees[body_index].find_nearest(Vector(positions[i]))
        if nearest[0] is None or nearest[3]>margin*2:continue
        relative=velocity[i]-obstacle_velocity
        velocity[i]-=normal*np.dot(relative,normal)
        count+=1
    return count

def moving_body_contact(indices,previous,trees,previous_trees,meshes,previous_meshes,velocity_contacts):
    """Keep an entering point on the identified moving face's exterior side.

    Only previously verified outside points are recovered this way. The
    endpoint is checked against the actual closed proxy; ambiguous candidates
    are preserved as unresolved. This is provisional point/face response, not
    edge/edge or continuous collision approval for the garment.
    """
    totals={'candidatePairs':0,'enteringPoints':0,'correctedPoints':0,'unresolvedPoints':0}
    for body_index,query in enumerate(indices):
        hits,stats=query.entering_contacts(previous,positions,movable)
        totals['candidatePairs']+=stats['sweptCandidatePairs']
        totals['enteringPoints']+=len(hits)
        points,triangles=meshes[body_index]
        for hit in hits:
            i=hit['vertex']
            if closed_state(previous_trees[body_index],previous[i]) is not False:
                totals['unresolvedPoints']+=1;continue
            triangle=triangles[hit['triangle']];weights=hit['barycentric']
            xyz=points[triangle];old_xyz=previous_meshes[body_index][triangle]
            normal=np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])
            length=np.linalg.norm(normal)
            if length<1e-10:totals['unresolvedPoints']+=1;continue
            normal/=length
            end=np.sum(xyz*weights[:,None],axis=0)
            body_delta=np.sum((xyz-old_xyz)*weights[:,None],axis=0)
            remaining=positions[i]-hit['pointAtImpact']-(1-hit['time'])*body_delta
            tangent=remaining-normal*np.dot(remaining,normal)
            accepted=None
            for on_face in [end+tangent,end]:
                for factor in [1.,2.]:
                    candidate=on_face+normal*margin*factor
                    if closed_state(trees[body_index],candidate) is False:
                        nearest=trees[body_index].find_nearest(Vector(candidate))
                        if nearest[0] is not None and nearest[3]>=margin*.75:
                            accepted=candidate;break
                if accepted is not None:break
            if accepted is None:totals['unresolvedPoints']+=1;continue
            positions[i]=accepted;totals['correctedPoints']+=1
            if velocity_contacts is not None:
                velocity_contacts[(int(i),body_index)]=(normal,body_delta/dt)
    return totals

def self_contact():
    tree = KDTree(len(rest))
    for i,point in enumerate(positions): tree.insert(point,i)
    tree.balance()
    count = 0
    for i in movable:
        for co,j,distance in tree.find_range(positions[i],self_distance):
            if j <= i or (int(i),int(j)) in adjacent or distance < 1e-10: continue
            delta = positions[i]-positions[j]
            length = np.linalg.norm(delta)
            if length >= self_distance: continue
            denom = inverse[i]+inverse[j]
            if denom == 0: continue
            correction = delta*((self_distance-length)/(length*denom))
            positions[i] += inverse[i]*correction
            positions[j] -= inverse[j]*correction
            count += 1
    return count

def measure(frame):
    measurements = []
    for part,ids in zip(r['parts'],part_ids):
        mask = np.isin(edges[:,0],ids)&np.isin(edges[:,1],ids)
        pairs=edges[mask]
        ratios=np.linalg.norm(positions[pairs[:,0]]-positions[pairs[:,1]],axis=1)/np.linalg.norm(rest[pairs[:,0]]-rest[pairs[:,1]],axis=1)
        logical=transfer.apply(positions)[part['start']:part['start']+part['vertices']]
        measurements.append({'key':part['key'],'solverMaximumEdgeStretch':float(ratios.max()),
                             'solverEdgeStretch95Percentile':float(np.percentile(ratios,95)),
                             'bounds':[logical.min(0).tolist(),logical.max(0).tolist()]})
    seam=np.linalg.norm(positions[seams[:,0]]-positions[seams[:,1]],axis=1)
    return {'frame':frame,'pieces':measurements,'maximumSeamGapMeters':float(seam.max()),
            'maximumPhysicalFullyPinnedInputError':float(np.linalg.norm(positions-targets[frame-1],axis=1)[fully_pinned].max())}

rows.append(measure(1))
for frame in range(1,len(targets)):
    projected_body=projected_self=projected_layers=ambiguous_layers=unresolved_layers=0
    limited_stretch=damped_body_velocity=0
    moving_totals={'candidatePairs':0,'enteringPoints':0,'correctedPoints':0,'unresolvedPoints':0}
    for substep in range(1,a.substeps+1):
        fraction=substep/a.substeps
        target=targets[frame-1]*(1-fraction)+targets[frame]*fraction
        previous=positions.copy()
        positions += velocity*dt + np.asarray([0,0,-9.81])*dt*dt
        positions[fully_pinned]=target[fully_pinned]
        trees,bounds,meshes,previous_meshes=[],[],[],[]
        velocity_contacts={} if a.damp_contact_velocity else None
        moving_indices,previous_trees=[],[]
        for j in range(3):
            points=bodies[f'proxy_{j}_animated_world_points'][frame-1]*(1-fraction)+bodies[f'proxy_{j}_animated_world_points'][frame]*fraction
            triangles=bodies[f'proxy_{j}_animated_triangles'][frame]
            previous_fraction=(substep-1)/a.substeps
            previous_meshes.append(bodies[f'proxy_{j}_animated_world_points'][frame-1]*(1-previous_fraction)+bodies[f'proxy_{j}_animated_world_points'][frame]*previous_fraction)
            meshes.append((points,triangles))
            if a.moving_body_face_contacts:
                assert np.array_equal(triangles,bodies[f'proxy_{j}_animated_triangles'][frame-1])
                moving_indices.append(MovingBodyFaceIndex(previous_meshes[-1],points,triangles))
                previous_trees.append(BVHTree.FromPolygons(previous_meshes[-1].tolist(),triangles.tolist(),all_triangles=True))
            trees.append(BVHTree.FromPolygons(points.tolist(),triangles.tolist(),all_triangles=True))
            bounds.append((points.min(0)-margin,points.max(0)+margin))
        ls,lb=np.zeros(len(structural)),np.zeros(len(bending))
        for iteration in range(a.iterations):
            distances(bending,bending_rest,bending_colors,lb,.2)
            distances(structural,structural_rest,structural_colors,ls,1e-7)
            # Provisional partial waist tether, explicitly separate from hard pins.
            positions[partial] += (target[partial]-positions[partial])*.15
            positions[fully_pinned]=target[fully_pinned]
            limited_stretch+=limit_stretch()
            if iteration%4==3 or iteration==a.iterations-1:
                projected_self += self_contact()
                if a.layer_order_contacts:
                    outer=np.concatenate([part_ids[i] for i in [0,2,3,4]])
                    result=ordered_layer_contact(positions,inverse,part_grids[1],outer,margin)
                    projected_layers+=result['corrections']
                    ambiguous_layers+=result['ambiguousQueries']
                    unresolved_layers+=result['unresolvedQueries']
                if a.moving_body_face_contacts:
                    result=moving_body_contact(moving_indices,previous,trees,previous_trees,meshes,previous_meshes,velocity_contacts)
                    for key in moving_totals:moving_totals[key]+=result[key]
                projected_body += body_contact(trees,bounds,meshes,previous_meshes,velocity_contacts)
        velocity=(positions-previous)/dt*.985
        if velocity_contacts is not None:damped_body_velocity+=damp_body_contact_velocity(velocity_contacts,trees)
        positions[fully_pinned]=target[fully_pinned]
        assert np.isfinite(positions).all()
    history.append(positions.copy());rows.append(measure(frame+1))
    contact_counts.append({'frame':frame+1,'actualBodyCorrections':projected_body,'actualParticleSelfCorrections':projected_self,
                          'actualOrderedSurfaceCorrections':projected_layers,'ambiguousOrderedQueries':ambiguous_layers,
                          'unresolvedOrderedQueries':unresolved_layers,'actualStretchLimitCorrections':limited_stretch,
                          'actualBodyContactVelocitiesDamped':damped_body_velocity})
    contact_counts[-1]['actualMovingBodyPointFaceContacts']=moving_totals
    (out/'progress.json').write_text(json.dumps({'completed':False,'lastActualFrame':frame+1,'frames':rows})+'\n')
    print('ACTUAL_XPBD_FRAME',frame+1,len(targets),round(time.time()-start_time,2),flush=True)

arrays={key:d[key] for key in d.files}
arrays['actual_simulation_points']=np.asarray(history,np.float32)
arrays['points']=np.asarray([transfer.apply(points) for points in history])
data=out/'actual_sewn_petticoat_frames.npz'
np.savez_compressed(data,**arrays)
report=copy.deepcopy(r)
native_reference={key:report.pop(key) for key in ['actualSolverSettings','actualCollisionSettings',
                 'actualModifierOrder','clothNeverBypassedDuringSequence','actualColliders',
                 'requestedSolverQuality','requestedColliderNormalResponse','provisionalInplaneStiffnessScale'] if key in report}
report.update({'actualSolver':'Independent XPBD distance/shear and two-ring bend constraints; closed recorded body projection and particle self contact',
               'nativeBlenderClothSolverReexecuted':False,'independentPhysicalSolverExecuted':True,
               'sourcePhysicalDataSha256':r['dataSha256'],'sourceBodyContactDataSha256':contact['dataSha256'],
               'actualBodyInputCompatibility':body_compatibility,
               'dataFile':str(data),'dataSha256':sha(data),'frames':rows,'scriptSha256':sha(__file__),
               'actualNativeSettingsAreReferenceOnly':True,
               'nativeBlenderParentReference':native_reference,
               'actualClosedBodyProxyReference':contact['actualClosedProxies'],
               'surfaceContactHelperSha256':sha(Path(__file__).with_name('chapeleiro_xpbd_surface_contacts.py')),
               'movingPointFaceHelperSha256':sha(Path(__file__).with_name('chapeleiro_moving_point_face_contacts.py')),
               'independentSolverSettings':{'fps':30,'substeps':a.substeps,'iterations':a.iterations,
                   'structuralCompliance':1e-7,'twoRingBendingCompliance':.2,'massPerVertex':mass,
                   'unilateralMaximumStretchRatio':a.maximum_stretch_ratio,
                   'inelasticNormalVelocityAtVerifiedBodyContacts':a.damp_contact_velocity,
                   'movingBodyPointFaceResponseEnabled':a.moving_body_face_contacts,
                   'movingBodyResponseRequiresPreviousOutsideAndVerifiedExteriorEndpoint':a.moving_body_face_contacts,
                   'bodyCalculationTrianglesFrozenBeforeDeformation':contact.get('actualBodyTrianglesFrozenBeforeDeformation',False),
                   'stretchLimitAndVelocityPrimarySource':'https://graphics.stanford.edu/papers/cloth-sig02/cloth.pdf',
                   'primarySourceFullCollisionAlgorithmImplemented':False,
                   'bodyClearanceMeters':margin,'selfParticleDistanceMeters':self_distance,
                   'partialPinIterationTether':.15,'velocityRetentionPerSubstep':.985,
                   'deepBodyRecoveryRequiresTwoRayInteriorAgreement':True,
                   'allBodySignsQueriedAndRecoveryCandidateVerifiedOutside':a.verified_body_recovery,
                   'authoredOuterSheetsOrderedOutsideBlackSupport':a.layer_order_contacts,
                   'orderedLayerCorrectionsUseOriginalTriangleMasses':a.layer_order_contacts,
                   'orderedLayerVirtualCapsAreOnlyClassificationVolumes':a.layer_order_contacts,
                   'seamsKeepAuthoredCalculationClearance':True,'distanceConstraintPrimarySource':'https://mmacklin.com/xpbd.pdf',
                   'parametersAreProvisional':True},
               'actualContactCorrections':contact_counts,'finalFbxExported':False,'responseBakedIntoRig':False,
               'allLayersFinished':False,'motionVerified':False,'clothCollisionVerified':False,'fidelityVerified':False,
               'limitation':'Particle self contacts, two-ray guarded closed-body projection and two-ring bend distances are approximations; ambiguous body queries are not projected. Continuous-time and triangle self contact and visual fidelity are not approved.',
               'elapsedSeconds':time.time()-start_time})
(out/'actual_sewn_solver_motion.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
shutil.copyfile(__file__,out/'executed_xpbd_probe.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_xpbd_surface_contacts.py'),out/'executed_surface_contact_helper.py')
shutil.copyfile(Path(__file__).with_name('chapeleiro_moving_point_face_contacts.py'),out/'executed_moving_point_face_helper.py')
print('ACTUAL_XPBD_TRAJECTORY_SAVED',len(history),flush=True)
