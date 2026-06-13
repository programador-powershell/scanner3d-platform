"""
Bridge Blender headless — replica a construção aprovada nos 9 portões, do zero,
dentro do Blender, usando os parâmetros do job (altura/quadril/ombro/músculo/pele).

Acionado pelo servidor SOMENTE depois que o personagem inteiro foi aprovado:
  blender.exe --background --factory-startup --python blender/build_character.py
              -- --job <job.json> --out <dir_saida>

Saída: <dir>/character.glb + <dir>/character.blend
Cada portão vira uma Collection ("01_Esqueleto" ... "09_Cabelo") — modular.

Quando o MPFB2 estiver instalado no Blender, o estágio de corpo tenta usá-lo;
sem ele, usa o corpo procedural (cápsulas + remesh + weights automáticos).
"""
import bpy
import json
import math
import sys
import os

# ---------------- args ----------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default

JOB_PATH = arg("--job")
OUT_DIR = arg("--out", ".")
os.makedirs(OUT_DIR, exist_ok=True)

job = json.load(open(JOB_PATH, encoding="utf-8")) if JOB_PATH else {}
P = {"height_m": 1.7, "hip": 1, "shoulder": 1, "bust": 1, "waist": 1, "muscle": 1, "skin": "#c9a08a", "wind": 0}
P.update(job.get("params") or {})
print(f"[build] params: {P}")

H = float(P["height_m"]) / 1.7  # fator de altura (baseline 1,70 m)

# ---------------- limpeza ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

def link_to(obj, coll):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)

def material(name, color, rough=0.6, metal=0.0, subsurface=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    rgb = tuple(int(color.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
    bsdf.inputs["Base Color"].default_value = rgb
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    for key in ("Subsurface Weight", "Subsurface"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = subsurface
            break
    return m

MAT_BONE = material("Osso", "#eae1cd", rough=0.55)
MAT_SKIN = material("Pele", P["skin"], rough=0.5, subsurface=0.08)
MAT_CLOTH = material("Tecido", "#27314f", rough=0.85)
MAT_HAIR = material("Cabelo", "#2b1d16", rough=0.7)
MAT_EYE = material("Olho", "#f5f5f5", rough=0.15)
MAT_IRIS = material("Iris", "#5a3a22", rough=0.25)
MAT_VEIN = material("Veia", "#46527e", rough=0.6)

def set_active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

# ============================================================
# 01 — ESQUELETO (armature humana real: coluna, costelas via corpo,
#       clavículas, braços com rádio implícito, falanges, pernas, pés)
# ============================================================
coll_skel = collection("01_Esqueleto")
arm_data = bpy.data.armatures.new("AliceRig")
rig = bpy.data.objects.new("AliceRig", arm_data)
coll_skel.objects.link(rig)
set_active(rig)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones

def bone(name, head, tail, parent=None, connect=False):
    b = eb.new(name)
    b.head = [c * H for c in head]
    b.tail = [c * H for c in tail]
    if parent is not None:
        b.parent = eb[parent]
        b.use_connect = connect
    return b

shoulderW = 0.18 * float(P["shoulder"])
hipW = 0.10 * float(P["hip"])

# pélvis + coluna (5 lombares→3 ossos, 12 torácicas→3 ossos, cervical, cabeça)
bone("pelvis", (0, 0, 0.95), (0, 0, 1.02))
bone("spine.01", (0, 0, 1.02), (0, 0, 1.12), "pelvis", True)
bone("spine.02", (0, 0, 1.12), (0, 0, 1.24), "spine.01", True)
bone("spine.03", (0, 0, 1.24), (0, 0, 1.38), "spine.02", True)
bone("neck", (0, 0, 1.38), (0, 0, 1.47), "spine.03", True)
bone("head", (0, 0, 1.47), (0, 0, 1.65), "neck", True)

for s, side in ((-1, "L"), (1, "R")):
    bone(f"clavicle.{side}", (s * 0.02, 0.02, 1.36), (s * shoulderW, 0, 1.36), "spine.03")
    bone(f"upper_arm.{side}", (s * shoulderW, 0, 1.36), (s * (shoulderW + 0.05), 0.01, 1.08), f"clavicle.{side}")
    bone(f"forearm.{side}", (s * (shoulderW + 0.05), 0.01, 1.08), (s * (shoulderW + 0.07), 0.03, 0.84), f"upper_arm.{side}", True)
    bone(f"hand.{side}", (s * (shoulderW + 0.07), 0.03, 0.84), (s * (shoulderW + 0.075), 0.04, 0.78), f"forearm.{side}", True)
    # falanges: 5 dedos × 2 ossos
    for f in range(5):
        fx = s * (shoulderW + 0.055 + f * 0.009)
        fl = 0.035 + (0.008 if f == 2 else 0) - (0.012 if f == 0 else 0)
        z0 = 0.78
        bone(f"finger{f}.01.{side}", (fx, 0.045, z0), (fx, 0.05, z0 - fl), f"hand.{side}")
        bone(f"finger{f}.02.{side}", (fx, 0.05, z0 - fl), (fx, 0.052, z0 - 2 * fl), f"finger{f}.01.{side}", True)
    # perna
    bone(f"thigh.{side}", (s * hipW, 0, 0.95), (s * hipW * 0.9, 0.01, 0.52), "pelvis")
    bone(f"shin.{side}", (s * hipW * 0.9, 0.01, 0.52), (s * hipW * 0.85, 0.02, 0.10), f"thigh.{side}", True)
    bone(f"foot.{side}", (s * hipW * 0.85, 0.02, 0.10), (s * hipW * 0.85, -0.10, 0.02), f"shin.{side}", True)
    bone(f"toe.{side}", (s * hipW * 0.85, -0.10, 0.02), (s * hipW * 0.85, -0.16, 0.02), f"foot.{side}", True)

bpy.ops.object.mode_set(mode="OBJECT")
print(f"[build] esqueleto: {len(arm_data.bones)} ossos")

# ============================================================
# 03 — MÚSCULOS / CORPO (tenta MPFB2; fallback procedural rigado)
# ============================================================
coll_body = collection("03_Musculos_Corpo")

def try_mpfb_body():
    try:
        import addon_utils
        ok = any(m.__name__.startswith(("mpfb", "bl_ext")) and "mpfb" in m.__name__ for m in addon_utils.modules())
        if not ok:
            return None
        addon_utils.enable("mpfb", default_set=True)
        from mpfb.services.humanservice import HumanService  # type: ignore
        basemesh = HumanService.create_human()
        return basemesh
    except Exception as e:
        print(f"[build] MPFB2 indisponível ({e}); usando corpo procedural")
        return None

def capsule(name, p0, p1, radius, coll, mat):
    """cápsula = cilindro entre p0..p1 + esferas nas pontas"""
    import mathutils
    v0 = mathutils.Vector([c * H for c in p0])
    v1 = mathutils.Vector([c * H for c in p1])
    mid = (v0 + v1) / 2
    d = v1 - v0
    length = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=radius * H, depth=length, location=mid)
    cyl = bpy.context.active_object
    cyl.rotation_mode = "QUATERNION"
    cyl.rotation_quaternion = d.to_track_quat("Z", "Y")
    objs = [cyl]
    for v in (v0, v1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * H, location=v, segments=16, ring_count=12)
        objs.append(bpy.context.active_object)
    for o in objs:
        link_to(o, coll)
    return objs

body = try_mpfb_body()
if body is None:
    mu = float(P["muscle"])
    parts = []
    parts += capsule("torso", (0, 0, 1.05), (0, 0, 1.34), 0.13 * mu * float(P["bust"]), coll_body, MAT_SKIN)
    parts += capsule("hip", (0, 0, 0.92), (0, 0, 1.02), 0.115 * mu * float(P["hip"]), coll_body, MAT_SKIN)
    parts += capsule("head_s", (0, 0, 1.50), (0, 0, 1.60), 0.085, coll_body, MAT_SKIN)
    parts += capsule("neck_s", (0, 0, 1.38), (0, 0, 1.49), 0.045, coll_body, MAT_SKIN)
    for s in (-1, 1):
        parts += capsule(f"uparm{s}", (s * shoulderW, 0.0, 1.34), (s * (shoulderW + 0.05), 0.01, 1.08), 0.040 * mu, coll_body, MAT_SKIN)
        parts += capsule(f"forearm{s}", (s * (shoulderW + 0.05), 0.01, 1.08), (s * (shoulderW + 0.07), 0.03, 0.80), 0.032 * mu, coll_body, MAT_SKIN)
        parts += capsule(f"thigh{s}", (s * hipW, 0, 0.93), (s * hipW * 0.9, 0.01, 0.52), 0.062 * mu, coll_body, MAT_SKIN)
        parts += capsule(f"shin{s}", (s * hipW * 0.9, 0.01, 0.52), (s * hipW * 0.85, 0.01, 0.08), 0.045 * mu, coll_body, MAT_SKIN)
        parts += capsule(f"foot{s}", (s * hipW * 0.85, -0.02, 0.04), (s * hipW * 0.85, -0.14, 0.035), 0.032, coll_body, MAT_SKIN)
    # une e suaviza em malha orgânica única
    set_active(parts[0])
    for o in parts:
        o.select_set(True)
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.name = "Corpo"
    rm = body.modifiers.new("Remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = 0.022
    bpy.ops.object.modifier_apply(modifier=rm.name)
    bpy.ops.object.shade_smooth()
    body.data.materials.clear()
    body.data.materials.append(MAT_SKIN)
link_to(body, coll_body)

# rig de verdade: automatic weights (esqueleto → corpo)
set_active(rig)
body.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
try:
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    print("[build] corpo rigado com automatic weights")
except Exception as e:
    print(f"[build] aviso: automatic weights falhou ({e}); parent simples")
    body.parent = rig

# ============================================================
# 02 — VEIAS (curvas finas nos membros, convertidas em malha)
# ============================================================
coll_veins = collection("02_Veias")
def strand(name, points, depth, coll, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = depth
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for i, p in enumerate(points):
        bp = sp.bezier_points[i]
        bp.co = [c * H for c in p]
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, cu)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

vein_objs = []
for s in (-1, 1):
    for k in range(3):
        off = (k - 1) * 0.008
        vein_objs.append(strand(
            f"veia_braco{s}_{k}",
            [(s * (shoulderW + 0.02) + off, 0.035, 1.30), (s * (shoulderW + 0.06) + off, 0.04, 1.05),
             (s * (shoulderW + 0.075) + off, 0.05, 0.85)],
            0.0016, coll_veins, MAT_VEIN))
for v in vein_objs:
    set_active(v)
    bpy.ops.object.convert(target="MESH")
    v.parent = rig

# ============================================================
# 04 — TECIDO (saia aberta com solidify + cloth configurado, pin na cintura)
# ============================================================
coll_cloth = collection("04_Tecido")
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.42 * float(P["hip"]) * H, radius2=0.16 * H,
                                depth=0.5 * H, location=(0, 0, 0.75 * H), end_fill_type="NOTHING")
skirt = bpy.context.active_object
skirt.name = "Saia"
link_to(skirt, coll_cloth)
skirt.data.materials.append(MAT_CLOTH)
# subdivide para drape decente
sub = skirt.modifiers.new("Subd", "SUBSURF")
sub.levels = 2
bpy.ops.object.modifier_apply(modifier=sub.name)
# vertex group de pin (anel superior)
vg = skirt.vertex_groups.new(name="pin")
top = [v.index for v in skirt.data.vertices if v.co.z > 0.2 * H]
vg.add(top, 1.0, "REPLACE")
cloth = skirt.modifiers.new("Cloth", "CLOTH")
cloth.settings.vertex_group_mass = "pin"
cloth.settings.quality = 6
cloth.collision_settings.use_self_collision = True
skirt.parent = rig

# corpo como colisor (a roupa NUNCA atravessa a carne — seção 3 do doc)
set_active(body)
body.modifiers.new("Collision", "COLLISION")

# ============================================================
# 05 — PELE / 06 — UNHAS (materiais dedicados)
# ============================================================
collection("05_Pele")   # material MAT_SKIN já no corpo (SSS)
coll_nails = collection("06_Unhas")
MAT_NAIL = material("Unha", "#f3d9d9", rough=0.18)
for s in (-1, 1):
    for f in range(5):
        fx = s * (shoulderW + 0.055 + f * 0.009)
        bpy.ops.mesh.primitive_cube_add(size=0.012 * H, location=(fx * H, 0.055 * H, 0.71 * H))
        nail = bpy.context.active_object
        nail.scale = (1, 0.6, 1.4)
        nail.name = f"unha{f}.{'L' if s < 0 else 'R'}"
        link_to(nail, coll_nails)
        nail.data.materials.append(MAT_NAIL)
        nail.parent = rig

# ============================================================
# 07 — ROSTO (marcadores de loops p/ retopo facial) / 08 — OLHOS
# ============================================================
collection("07_Rosto")  # a cabeça já está no corpo; loops virão do template ICT no trilho real
coll_eyes = collection("08_Olhos")
for s in (-1, 1):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018 * H, location=(s * 0.032 * H, -0.062 * H, 1.56 * H),
                                         segments=20, ring_count=14)
    eye = bpy.context.active_object
    eye.name = f"olho.{'L' if s < 0 else 'R'}"
    link_to(eye, coll_eyes)
    eye.data.materials.append(MAT_EYE)
    bpy.ops.mesh.primitive_circle_add(radius=0.008 * H, fill_type="NGON",
                                      location=(s * 0.032 * H, -0.0795 * H, 1.56 * H), rotation=(math.pi / 2, 0, 0))
    iris = bpy.context.active_object
    iris.name = f"iris.{'L' if s < 0 else 'R'}"
    link_to(iris, coll_eyes)
    iris.data.materials.append(MAT_IRIS)
    eye.parent = rig
    iris.parent = rig

# ============================================================
# 09 — CABELO (strands bezier do couro cabeludo → malha)
# ============================================================
coll_hair = collection("09_Cabelo")
import random
random.seed(int(job.get("id", "0")[-6:].encode().hex(), 16) % (2**31) if job.get("id") else 7)
hair_objs = []
N_STRANDS = 160
for i in range(N_STRANDS):
    a = random.uniform(0, 2 * math.pi)
    r = 0.075 * math.sqrt(random.random())
    x, y = math.cos(a) * r, math.sin(a) * r * 0.8
    pts = []
    length = random.uniform(0.35, 0.55)
    for j in range(5):
        t = j / 4
        pts.append((x + math.sin(t * 5 + i) * 0.015,
                    y + 0.01 + math.cos(t * 4 + i) * 0.012,
                    1.62 - t * length))
    hair_objs.append(strand(f"fio{i}", pts, 0.0011, coll_hair, MAT_HAIR))
for hobj in hair_objs:
    set_active(hobj)
    bpy.ops.object.convert(target="MESH")
    hobj.parent = rig
print(f"[build] cabelo: {N_STRANDS} fios")

# ============================================================
# EXPORT
# ============================================================
blend_path = os.path.join(OUT_DIR, "character.blend")
glb_path = os.path.join(OUT_DIR, "character.glb")
fbx_path = os.path.join(OUT_DIR, "character.fbx")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB")
print(f"[build] OK -> {glb_path}")
print(f"[build] OK -> {blend_path}")

# Export FBX para UE5: malha + armature, eixo Y-up, escala UE (rig pronto p/ retarget).
try:
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=False,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',
        object_types={'ARMATURE', 'MESH'},
        add_leaf_bones=False,            # UE5 não gosta de leaf bones
        primary_bone_axis='Y',
        secondary_bone_axis='X',
        bake_anim=False,
        mesh_smooth_type='FACE',
        path_mode='COPY',
        embed_textures=True,
    )
    print(f"[build] OK -> {fbx_path} (UE5)")
except Exception as e:
    print(f"[build] aviso FBX: {e}")
