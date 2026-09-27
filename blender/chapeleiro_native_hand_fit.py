"""Native arm/hand bind inference from the actual Chapeleiro geometry and atlas.

Internal joints are inferred. Existing action channels are retained only as
deformation probes and require renewed pose/retarget review after a bind change.
No garment or character geometry is cut, replaced, or imported here.
"""
import hashlib
import bpy
import numpy as np
from mathutils import Matrix,Vector

def native_samples(obj):
    mesh=obj.data
    xyz=np.empty(len(mesh.vertices)*3,np.float32);mesh.vertices.foreach_get('co',xyz)
    matrix=np.asarray(obj.matrix_world);points=xyz.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    loops=np.empty(len(mesh.loops),np.int32);mesh.loops.foreach_get('vertex_index',loops)
    uv=np.empty(len(mesh.loops)*2,np.float32);mesh.uv_layers.active.data.foreach_get('uv',uv);uv=uv.reshape(-1,2)
    face_material=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('material_index',face_material)
    face_sizes=np.empty(len(mesh.polygons),np.int32);mesh.polygons.foreach_get('loop_total',face_sizes)
    vertices,first=np.unique(loops,return_index=True)
    if len(vertices)!=len(mesh.vertices):raise ValueError('Native hand sample has unused vertices.')
    slots=np.repeat(face_material,face_sizes)[first];uv=uv[first]
    colors=np.full((len(points),3),np.nan,np.float32);images=[]
    for slot,material in enumerate(mesh.materials):
        nodes=[n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED']
        if len(nodes)!=1:raise ValueError('Unexpected native base-color shader.')
        links=list(nodes[0].inputs['Base Color'].links)
        if len(links)!=1 or links[0].from_node.type!='TEX_IMAGE':raise ValueError('Expected actual native atlas input.')
        image=links[0].from_node.image
        width,height=image.size[:];pixels=np.empty(width*height*image.channels,np.float32)
        image.pixels.foreach_get(pixels);pixels=pixels.reshape(height,width,image.channels)
        selected=slots==slot;coord=uv[selected]%1
        x=np.clip((coord[:,0]*width).astype(int),0,width-1);y=np.clip((coord[:,1]*height).astype(int),0,height-1)
        colors[selected]=pixels[y,x,:3]
        images.append({'material':material.name,'image':image.name,'size':[width,height],
            'packedImageSha256':hashlib.sha256(bytes(image.packed_file.data)).hexdigest() if image.packed_file else None})
    if not np.isfinite(colors).all():raise ValueError('Invalid real native UV/color samples.')
    r,g,b=colors.T;lo=np.minimum.reduce([r,g,b]);hi=np.maximum.reduce([r,g,b])
    skin=(r>g*1.06)&(r>b*1.08)&(b>g*.60)&(lo>.08)&(hi>.16)&((hi-lo)/np.maximum(hi,1e-8)<.55)
    return points,skin,images

def section(points,mask,label):
    data=points[mask]
    if len(data)<60:raise ValueError('Insufficient actual atlas/geometry candidates for '+label)
    low,high=np.quantile(data,[.10,.90],axis=0)
    return (low+high)/2,{'label':label,'actualCandidateVertices':len(data),
        'quantile10':low.tolist(),'quantile90':high.tolist(),'inferredCenter':((low+high)/2).tolist()}

def elbow_surface_section(whole,points,z,side,sign):
    """Measure intersections with the original edges, without editing the mesh.

    Vertex density on the exposed forearm is too low for a color histogram.
    The actual surface contour, rather than an increased color search radius,
    supplies its transverse center. Internal anatomy remains inferred.
    """
    edges=np.empty(len(whole.data.edges)*2,np.int32)
    whole.data.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
    a,b=points[edges[:,0]],points[edges[:,1]]
    crossing=((a[:,2]<=z)&(b[:,2]>z))|((b[:,2]<=z)&(a[:,2]>z))
    a,b=a[crossing],b[crossing]
    contour=a+(b-a)*((z-a[:,2])/(b[:,2]-a[:,2]))[:,None]
    region=(contour[:,0]*sign>.085)&(contour[:,0]*sign<.155)&(contour[:,1]>-.075)&(contour[:,1]<.05)
    contour=np.unique(np.round(contour[region],7),axis=0)
    if len(contour)<8:raise ValueError('Insufficient actual arm surface intersections for '+side)
    low,high=contour.min(0),contour.max(0);center=(low+high)/2
    if high[0]-low[0]>.055 or high[1]-low[1]>.080:
        raise ValueError('Ambiguous arm surface contour for '+side)
    return center,{'label':side+' elbow','method':'original edge intersections at the existing joint height',
        'actualContourPoints':contour.tolist(),'bounds':[low.tolist(),high.tolist()],
        'inferredCenter':center.tolist(),'internalJointInferred':True,'meshEdited':False}

def infer_targets(rig,whole,finger_guides=None):
    points,skin,images=native_samples(whole);heads={};tails={};guides=[]
    for side,sign in [('Left',1),('Right',-1)]:
        current={b.name:b.head_local.copy() for b in rig.data.bones if b.name.startswith(side+'Hand')}
        region=skin&(points[:,0]*sign>.15)&(points[:,0]*sign<.21)&(points[:,1]>-.065)&(points[:,1]<.025)
        wrist_z=rig.data.bones[side+'Hand'].head_local.z
        wrist,row=section(points,region&(np.abs(points[:,2]-wrist_z)<.007),side+' wrist')
        wrist[2]=wrist_z;row['inferredCenter']=wrist.tolist();guides.append(row)
        elbow_z=rig.data.bones[side+'ForeArm'].head_local.z
        elbow,row=elbow_surface_section(whole,points,elbow_z,side,sign)
        elbow[2]=elbow_z;row['inferredCenter']=elbow.tolist();guides.append(row)
        heads[side+'ForeArm']=Vector(elbow);tails[side+'Arm']=Vector(elbow)
        heads[side+'Hand']=Vector(wrist);tails[side+'ForeArm']=Vector(wrist)
        if finger_guides:
            targets=finger_guides['boneTargets']
            required={side+'Hand'+digit+str(joint) for digit in ['Thumb','Index','Middle','Ring','Pinky'] for joint in range(1,5)}
            if not required.issubset(targets):raise ValueError('Missing individual native finger targets.')
            for name in required:
                value=targets[name]
                if not np.isfinite([value['head'],value['tail']]).all():raise ValueError('Non-finite native finger target.')
                heads[name]=Vector(value['head']);tails[name]=Vector(value['tail'])
            tails[side+'Hand']=sum((heads[side+'Hand'+digit+'1'] for digit in ['Index','Middle','Ring','Pinky']),Vector())/4
            guides.append({'label':side+' individual digits','method':finger_guides['method'],
                'individualDigitEvidence':[p for p in finger_guides['individualDigitEvidence'] if p['side']==side]})
            continue
        digits=['Index','Middle','Ring','Pinky'];levels={}
        for joint,(lo,hi) in enumerate([(.480,.495),(.465,.480),(.450,.465),(.445,.453)],1):
            centre,row=section(points,region&(points[:,2]>=lo)&(points[:,2]<hi),side+' finger joint '+str(joint))
            guides.append(row);levels[joint]=Vector(centre)
            names=[side+'Hand'+digit+str(joint) for digit in digits]
            original=sum((current[name] for name in names),Vector())/len(names)
            for name in names:
                offset=current[name]-original
                heads[name]=levels[joint]+Vector((offset.x*.70,offset.y*.70,offset.z*.65))
        tails[side+'Hand']=sum((heads[side+'Hand'+digit+'1'] for digit in digits),Vector())/len(digits)
        for digit in digits:
            for joint in range(1,4):tails[side+'Hand'+digit+str(joint)]=heads[side+'Hand'+digit+str(joint+1)]
            terminal=side+'Hand'+digit+'4';previous=side+'Hand'+digit+'3'
            tails[terminal]=heads[terminal]+(heads[terminal]-heads[previous]).normalized()*.0025
        palm=levels[1]
        thumb_mask=region&(points[:,0]*sign<abs(palm.x)-.010)&(points[:,1]<-.033)&(points[:,2]>=.472)&(points[:,2]<.496)
        thumb,row=section(points,thumb_mask,side+' native thumb region');guides.append(row)
        upper,row=section(points,thumb_mask&(points[:,2]>=.483),side+' thumb upper section');guides.append(row)
        lower,row=section(points,thumb_mask&(points[:,2]<.483),side+' thumb distal section');guides.append(row)
        tip_data=points[thumb_mask&(points[:,2]<.478)]
        if len(tip_data)<30:raise ValueError('Insufficient actual distal thumb candidates.')
        tip=(np.quantile(tip_data,.10,axis=0)+np.quantile(tip_data,.90,axis=0))/2
        thumb_base=Vector((wrist[0],(wrist[1]+thumb[1])/2,.512))
        thumb_targets=[thumb_base,Vector(upper),Vector(lower),Vector(tip)]
        for joint,target in enumerate(thumb_targets,1):heads[side+'HandThumb'+str(joint)]=target
        for joint in range(1,4):tails[side+'HandThumb'+str(joint)]=heads[side+'HandThumb'+str(joint+1)]
        name=side+'HandThumb4';tails[name]=heads[name]+(heads[name]-heads[side+'HandThumb3']).normalized()*.0025
    return heads,tails,guides,images

def fit_native_hands(rig,whole,finger_guides=None):
    heads,tails,guides,images=infer_targets(rig,whole,finger_guides)
    names=set(heads)|set(tails)
    before={name:{'head':list(rig.data.bones[name].head_local),'tail':list(rig.data.bones[name].tail_local),
        'matrix':[[v for v in row] for row in rig.data.bones[name].matrix_local]} for name in names}
    bone_count=len(rig.data.bones)
    old_z={name:rig.data.bones[name].matrix_local.to_3x3()@Vector((0,0,1)) for name in names}
    bpy.ops.object.select_all(action='DESELECT');rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
    bpy.ops.object.mode_set(mode='EDIT')
    connections={name:rig.data.edit_bones[name].use_connect for name in names}
    for name in names:rig.data.edit_bones[name].use_connect=False
    for name in sorted(names):
        bone=rig.data.edit_bones[name];head=heads.get(name,Vector(before[name]['head']));tail=tails.get(name,Vector(before[name]['tail']))
        direction=tail-head
        if direction.length<1e-5:raise ValueError('Degenerate inferred native hand bone.')
        y=direction.normalized();z=old_z[name]-y*old_z[name].dot(y)
        if z.length<1e-5:z=Vector((0,1,0))-y*y.y
        z.normalize();x=y.cross(z).normalized();z=x.cross(y).normalized()
        bone.matrix=Matrix(((x.x,y.x,z.x,head.x),(x.y,y.y,z.y,head.y),(x.z,y.z,z.z,head.z),(0,0,0,1)))
        bone.length=direction.length
    for name,connected in connections.items():
        bone=rig.data.edit_bones[name]
        if connected and bone.parent:
            if (bone.head-bone.parent.tail).length>1e-6:raise ValueError('Changed an actual connected limb junction.')
            bone.use_connect=True
    bpy.ops.object.mode_set(mode='OBJECT')
    if len(rig.data.bones)!=bone_count:raise ValueError('Native hand fit changed the common skeleton topology.')
    for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    after={name:{'head':list(rig.data.bones[name].head_local),'tail':list(rig.data.bones[name].tail_local),
        'matrix':[[v for v in row] for row in rig.data.bones[name].matrix_local]} for name in names}
    return {'method':'inferred elbow/wrist bind and individual native finger surface centerlines' if finger_guides else 'inferred elbow/wrist/finger bind from actual native atlas and real 3D surface sections',
        'guides':guides,'actualAtlasImages':images,'before':before,'after':after,
        'existingCommonSkeletonTopologyPreserved':True,'actualChangedBones':len(names),'geometryChanged':False,
        'individualNativeFingerSurfaceGuidesUsed':bool(finger_guides),
        'inheritedLocalActionChannelsRequireRetargetAndPoseReview':True,
        'rigFitVerified':False,'motionVerified':False,'fidelityVerified':False,'clothCollisionVerified':False,
        'limitations':['Internal anatomy is inferred; color candidates may include ornaments.',
            'Section centers do not prove individual finger joints or wrist motion.',
            'Original local action channels remain experimental after this bind change.']}
