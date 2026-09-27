"""Bind fields for actual Chapeleiro garments; no foreign character geometry.

These fields are an initial deformation study. Loose fabric requires physical
secondary response and collisions before approval, and hidden anatomy is inferred.
"""
import math
from collections import defaultdict
from mathutils import Vector
from mathutils.kdtree import KDTree
WEIGHT_QUANTIZATION=65536

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

def attachment_regions(pieces,objects):
    """Recover sewn torso/sleeve membership from the authored parent graph."""
    indexed={p['name']:p for p in pieces};sleeves={};regions={}
    for name,piece in indexed.items():
        if piece['role']!='foundation_puffed_sleeve':continue
        obj=objects[name];count=len(obj.data.vertices)
        if count%31:raise ValueError('Unexpected actual 30-row sewn sleeve loft.')
        root=[obj.matrix_world@v.co for v in obj.data.vertices[:count//31]]
        sleeves[name]={'kind':'sleeve','side':'Left' if sum(p.x for p in root)>0 else 'Right',
            'rootPoints':[list(p) for p in root],'rootHoldDistance':.0015,'transitionDistance':.033}
    torso_roles={'boned_foundation_corset','corset_structural_detail','foundation_gathered_blouse','foundation_neckline_frill'}
    for name,piece in indexed.items():
        role=piece['role']
        eligible=(role in torso_roles or role=='foundation_puffed_sleeve'
            or role.startswith(('foundation_corset','foundation_blouse'))
            or (role=='internal_photographic_lace' and name.startswith('01 / corset /')))
        if not eligible:continue
        current=name;seen=set()
        while current and current not in seen:
            seen.add(current)
            if current in sleeves:regions[name]=dict(sleeves[current]);break
            entry=indexed.get(current,{})
            if entry.get('role') in torso_roles or entry.get('role','').startswith('foundation_corset'):
                regions[name]={'kind':'torso'};break
            current=entry.get('parent')
    return regions

class GarmentFields:
    def __init__(self,rig,cloth_families,piece_families=None,piece_regions=None):
        self.bones={b.name:(b.head_local.copy(),b.tail_local.copy()) for b in rig.data.bones}
        self.cloth_families=cloth_families
        self.piece_families=piece_families or {}
        self.piece_regions=piece_regions or {};self.root_trees={}
        self.arm_names={side:[side+'Arm',side+'ForeArm',side+'Hand']+
            [n for n in self.bones if n.startswith(side+'Hand') and n!=side+'Hand'] for side in ['Left','Right']}
        for name,rule in self.piece_regions.items():
            if rule['kind']!='sleeve':continue
            tree=KDTree(len(rule['rootPoints']))
            for index,point in enumerate(rule['rootPoints']):tree.insert(Vector(point),index)
            tree.balance();self.root_trees[name]=tree

    def torso(self,p):
        # Torso garment anchors cannot inherit nearby arms across the air gap.
        names=['Hips','Spine','Spine1','Spine2','Neck']
        z=[self.bones[name][0].z for name in names]
        if p.z<=z[0]:return {names[0]:1.}
        for index in range(len(names)-1):
            if z[index]<=p.z<=z[index+1]:
                t=smooth((p.z-z[index])/(z[index+1]-z[index]))
                return normalized({names[index]:1-t,names[index+1]:t})
        return {names[-1]:1.}

    def near(self,p,names,minimum=.008):
        distances=[(name,segment_distance(p,*self.bones[name])) for name in names if name in self.bones]
        distances=sorted(distances,key=lambda row:row[1])[:3]
        # Compact support reduces unrelated torso/arm influences across gaps.
        best=distances[0][1]
        return normalized({name:(1-smooth((distance-best)/.040))/(distance+minimum)**4
            for name,distance in distances if distance<best+.040})

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
        return blend(self.torso(p),normalized(values),free)

    def weights(self,p,role,name):
        if name in self.piece_families:return self.cloth(p,self.piece_families[name])
        if name in self.piece_regions:
            rule=self.piece_regions[name]
            if rule['kind']=='torso':return self.torso(p)
            distance=self.root_trees[name].find(p)[2]
            t=smooth((distance-rule['rootHoldDistance'])/rule['transitionDistance'])
            return blend(self.torso(p),{rule['side']+'Arm':1.},t)
        if role=='whole_native':
            # The whole exterior stays a single unchanged mesh. Regions are
            # weighted, never cut into replacement layers.
            side='Left' if p.x>=0 else 'Right'
            # Arm surface membership is assigned per original connected
            # component in quantized_assign. A per-point capsule here would
            # steal adjacent skirt vertices and split their deformation field.
            leg_distance=min(segment_distance(p,*self.bones[n]) for n in [side+'UpLeg',side+'Leg',side+'Foot',side+'ToeBase'])
            if p.z<.45 and leg_distance<.045:return self.body(p)
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
            if 'sewn ivory button' in name:return {'Hips':1.}
            # Existing separate leg-opening trims must not inherit the other
            # thigh. Their actual bounds stay below z=.430 and on their own
            # side. Keep the continuous body/crotch's original blend: a narrow
            # lateral field across that shared surface regressed in v085.
            if name.startswith('01 / left bloomers /'):return {'LeftUpLeg':1.}
            if name.startswith('01 / right bloomers /'):return {'RightUpLeg':1.}
            legs=self.near(p,['Hips','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg'],.012)
            return blend({'Hips':1.},legs,smooth((.52-p.z)/.07))
        return self.body(p)

def quantized_assign(obj,rig,fields,role,name,preserve_other_groups=False,replace_skin=False):
    """Exact binary sums; enough weight precision for actual fine lace yarns."""
    native_arms=None;native_arm_audit=None
    if role=='whole_native':
        from chapeleiro_whole_arm_components import native_arm_components
        native_arms,native_arm_audit=native_arm_components(obj,fields.bones,fields.arm_names)
    if not preserve_other_groups:
        maximum=max((g.group for v in obj.data.vertices for g in v.groups),default=-1)
        while len(obj.vertex_groups)<=maximum:obj.vertex_groups.new(name='Discard inherited non-skin field')
        obj.vertex_groups.clear()
        if any(v.groups for v in obj.data.vertices):raise ValueError('Inherited deformation weights remain.')
    bone_names={b.name for b in rig.data.bones}
    if preserve_other_groups and replace_skin:
        for group in list(obj.vertex_groups):
            if group.name in bone_names:obj.vertex_groups.remove(group)
    if preserve_other_groups and any(g.name in bone_names for g in obj.vertex_groups):
        raise ValueError('The actual authoring cage was already skinned.')
    batches=defaultdict(list);used=set();error=0.
    for v in obj.data.vertices:
        point=obj.matrix_world@v.co
        if native_arms is not None and native_arms[v.index]:
            side='Left' if native_arms[v.index]==1 else 'Right'
            weights=fields.near(point,fields.arm_names[side],.005)
        else:weights=fields.weights(point,role,name)
        integers={bone:round(value*WEIGHT_QUANTIZATION) for bone,value in weights.items()}
        largest=max(weights,key=weights.get);integers[largest]+=WEIGHT_QUANTIZATION-sum(integers.values())
        for bone,value in integers.items():
            if value>0:batches[(bone,value)].append(v.index);used.add(bone)
    groups={name:obj.vertex_groups.new(name=name) for name in sorted(used)}
    for (name,weight),indices in batches.items():groups[name].add(indices,weight/WEIGHT_QUANTIZATION,'REPLACE')
    indices={group.index for group in groups.values()}
    unweighted=0;maximum_influences=0
    for v in obj.data.vertices:
        actual=[g.weight for g in v.groups if g.group in indices]
        if not actual:unweighted+=1
        error=max(error,abs(sum(actual)-1));maximum_influences=max(maximum_influences,len(actual))
    if unweighted or error>1e-7 or maximum_influences>4:raise ValueError('Invalid real shared-rig weights.')
    result={'mesh':obj.name,'role':role,'vertices':len(obj.data.vertices),'boneGroups':sorted(used),
        'unweightedVertices':unweighted,'maximumNormalizationError':error,'maximumInfluences':maximum_influences,
        'quantization':WEIGHT_QUANTIZATION,'preservedClothFields':preserve_other_groups,'motionVerified':False}
    if native_arm_audit:result['nativeArmComponents']=native_arm_audit
    return result

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
