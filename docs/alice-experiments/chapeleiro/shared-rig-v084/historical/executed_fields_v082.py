"""Bind fields for actual Chapeleiro garments; no foreign character geometry.

These fields are an initial deformation study. Loose fabric requires physical
secondary response and collisions before approval, and hidden anatomy is inferred.
"""
import math
from collections import defaultdict
from mathutils import Vector

def smooth(value):
    value=max(0.,min(1.,value));return value*value*(3-2*value)

def segment_distance(point,head,tail):
    direction=tail-head
    t=max(0.,min(1.,(point-head).dot(direction)/max(direction.length_squared,1e-15)))
    return (point-head-direction*t).length

def normalized(values):
    values={name:max(0.,float(value)) for name,value in values.items() if value>1e-9}
    values=dict(sorted(values.items(),key=lambda item:item[1],reverse=True)[:4])
    total=sum(values.values())
    if total<=0:raise ValueError('Unweighted actual garment point.')
    return {name:value/total for name,value in values.items()}

def blend(a,b,t):
    values=defaultdict(float)
    for name,value in a.items():values[name]+=(1-t)*value
    for name,value in b.items():values[name]+=t*value
    return normalized(values)

class GarmentFields:
    def __init__(self,rig,cloth_families,piece_families=None):
        self.bones={b.name:(b.head_local.copy(),b.tail_local.copy()) for b in rig.data.bones}
        self.cloth_families=cloth_families
        self.piece_families=piece_families or {}

    def near(self,p,names,minimum=.008):
        distances=[(name,segment_distance(p,*self.bones[name])) for name in names if name in self.bones]
        distances=sorted(distances,key=lambda row:row[1])[:3]
        # Compact support reduces unrelated torso/arm influences across gaps.
        best=distances[0][1]
        return normalized({name:1/(distance+minimum)**4 for name,distance in distances if distance<=best+.040})

    def body(self,p):
        side='Left' if p.x>=0 else 'Right'
        if p.z<.50:
            return self.near(p,['Hips',side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase'],.006)
        if abs(p.x)>.12 and p.z<.64:
            names=[side+'ForeArm',side+'Hand']+[n for n in self.bones if n.startswith(side+'Hand')]
            return self.near(p,names,.005)
        if abs(p.x)>.065 and .61<p.z<.83:
            arms=[side+'Shoulder',side+'Arm',side+'ForeArm',side+'Hand']
            torso=['Hips','Spine','Spine1','Spine2','Neck']
            arm_distance=min(segment_distance(p,*self.bones[n]) for n in arms)
            torso_distance=min(segment_distance(p,*self.bones[n]) for n in torso)
            if arm_distance<torso_distance*.85:return self.near(p,['Spine2']+arms)
        if p.z>.82:return self.near(p,['Spine2','Neck','Head'],.010)
        return self.near(p,['Hips','Spine','Spine1','Spine2','Neck'],.010)

    def cloth(self,p,family):
        rule=self.cloth_families[family]
        theta=math.atan2(p.x,-p.y)%math.tau
        angle=theta/math.tau*rule['sectors'];a=int(angle)%rule['sectors'];fraction=angle-int(angle)
        fraction=smooth(fraction)
        levels=rule['levels'];z=p.z
        row=max(0,min(len(levels)-2,next((i for i in range(len(levels)-1) if levels[i]>=z>=levels[i+1]),len(levels)-2)))
        vertical=smooth((levels[row]-z)/max(levels[row]-levels[row+1],1e-8))
        values=defaultdict(float)
        for sector,weight in [(a,1-fraction),((a+1)%rule['sectors'],fraction)]:
            for level,w in [(row,1-vertical),(min(row+1,len(levels)-2),vertical)]:
                values[f'{family}_{sector:02d}_{level}']+=weight*w
        # All roots follow the same anatomical field before the skirt takes over.
        free=smooth((levels[0]-z)/.055)
        return blend(self.body(Vector((p.x,p.y,max(p.z,.55)))),normalized(values),free)

    def weights(self,p,role,name):
        if name in self.piece_families:return self.cloth(p,self.piece_families[name])
        if role=='whole_native':
            # The whole exterior stays a single unchanged mesh. Regions are
            # weighted, never cut into replacement layers.
            if .24<p.z<.64 and abs(p.x)<.16+(.64-p.z)*.38:
                return self.cloth(p,'ExteriorCloth')
            if p.z>.67 and abs(p.x)<.067 and p.y>.022:
                return {'Head':1.}
            return self.body(p)
        if 'garter belt' in name:return self.body(Vector((p.x,p.y,max(p.z,.56))))
        if 'suspension web' in name or 'brass slider' in name or 'stocking clasp' in name:
            side='Left' if p.x>=0 else 'Right'
            t=smooth((.630-p.z)/.150)
            return blend(self.body(Vector((p.x,p.y,.630))),{side+'UpLeg':1.},t)
        if ' garter /' in name or role.startswith('foundation_stocking'):
            side='Left' if p.x>=0 else 'Right'
            return self.near(p,[side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase'],.006)
        if 'petticoat' in name or 'flounce' in name or 'lace tier' in name:
            return self.cloth(p,'BlackCloth' if 'black' in name else 'IvoryCloth')
        if role.startswith('foundation_bloomers'):
            side='Left' if p.x>=0 else 'Right'
            return self.near(p,['Hips',side+'UpLeg',side+'Leg'],.012)
        return self.body(p)

def quantized_assign(obj,rig,fields,role,name,preserve_other_groups=False):
    """Exact sums in 1/1024 increments; batch equal weights through Blender API."""
    if not preserve_other_groups:
        maximum=max((g.group for v in obj.data.vertices for g in v.groups),default=-1)
        while len(obj.vertex_groups)<=maximum:obj.vertex_groups.new(name='Discard inherited non-skin field')
        obj.vertex_groups.clear()
        if any(v.groups for v in obj.data.vertices):raise ValueError('Inherited deformation weights remain.')
    bone_names={b.name for b in rig.data.bones}
    if preserve_other_groups and any(g.name in bone_names for g in obj.vertex_groups):
        raise ValueError('The actual authoring cage was already skinned.')
    batches=defaultdict(list);used=set();error=0.
    for v in obj.data.vertices:
        weights=fields.weights(obj.matrix_world@v.co,role,name)
        integers={bone:round(value*1024) for bone,value in weights.items()}
        largest=max(weights,key=weights.get);integers[largest]+=1024-sum(integers.values())
        for bone,value in integers.items():
            if value>0:batches[(bone,value)].append(v.index);used.add(bone)
    groups={name:obj.vertex_groups.new(name=name) for name in sorted(used)}
    for (name,weight),indices in batches.items():groups[name].add(indices,weight/1024,'REPLACE')
    indices={group.index for group in groups.values()}
    unweighted=0;maximum_influences=0
    for v in obj.data.vertices:
        actual=[g.weight for g in v.groups if g.group in indices]
        if not actual:unweighted+=1
        error=max(error,abs(sum(actual)-1));maximum_influences=max(maximum_influences,len(actual))
    if unweighted or error>1e-7 or maximum_influences>4:raise ValueError('Invalid real shared-rig weights.')
    return {'mesh':obj.name,'role':role,'vertices':len(obj.data.vertices),'boneGroups':sorted(used),
        'unweightedVertices':unweighted,'maximumNormalizationError':error,'maximumInfluences':maximum_influences,
        'quantization':1024,'preservedClothFields':preserve_other_groups,'motionVerified':False}

def solve_leg(hip,ankle,upper_length,lower_length):
    """Two-bone IK for planted crouch/landing; forward knee pole in world -Y."""
    delta=ankle-hip;distance=delta.length
    if distance<max(1e-7,abs(upper_length-lower_length)) or distance>upper_length+lower_length+1e-6:
        raise ValueError('Authored jump requests an unreachable ankle.')
    axis=delta.normalized();pole=Vector((0,-1,0));pole-=axis*pole.dot(axis)
    pole.normalize()
    along=(upper_length**2-lower_length**2+distance**2)/(2*distance)
    height=math.sqrt(max(0.,upper_length**2-along**2))
    return hip+axis*along+pole*height
