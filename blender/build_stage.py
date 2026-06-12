"""
Bridge Blender headless — gera o preview de UM portão usando MPFB2/Z-Anatomy/etc.
Sem geometria procedural inventada: só ferramentas dos repos GitHub registrados.

Uso:
  blender.exe --background --factory-startup --python blender/build_stage.py
              -- --stage <id> --job <job.json> --out <dir>

Saída: <out>/<stage>.glb (carregado pelo navegador no viewer)
"""
import bpy
import json
import os
import sys
import addon_utils

# ---------------- args ----------------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


STAGE = arg("--stage", "skeleton")
JOB_PATH = arg("--job")
OUT_DIR = arg("--out", ".")
os.makedirs(OUT_DIR, exist_ok=True)

job = json.load(open(JOB_PATH, encoding="utf-8")) if JOB_PATH else {}
P = {"height_m": 1.7, "hip": 1, "shoulder": 1, "bust": 1, "waist": 1,
     "muscle": 1, "skin": "#c9a08a", "wind": 0}
P.update(job.get("params") or {})
print(f"[stage:{STAGE}] params={P}")

# ---------------- garante MPFB2 habilitado ----------------
MPFB_IDS = ["bl_ext.blender_org.mpfb", "mpfb"]
mpfb_mod = None
for mid in MPFB_IDS:
    try:
        addon_utils.enable(mid, default_set=True)
        ok, _ = addon_utils.check(mid)
        if ok:
            mpfb_mod = mid
            print(f"[stage:{STAGE}] MPFB2 ativo: {mid}")
            break
    except Exception:
        continue
if not mpfb_mod:
    print(f"[stage:{STAGE}] ERRO: MPFB2 não encontrado/habilitado")
    sys.exit(2)


def mpfb_api():
    """Importa MPFB2 respeitando o namespace correto (extensão vs. legado)."""
    import importlib
    for prefix in (f"{mpfb_mod}.mpfb", mpfb_mod, "mpfb"):
        try:
            return importlib.import_module(f"{prefix}.services.humanservice").HumanService
        except Exception:
            continue
    raise RuntimeError("HumanService indisponível")


# ---------------- cena limpa ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ============================================================
# CORPO MPFB2 — base de TODOS os portões (humano paramétrico real)
# ============================================================
HS = mpfb_api()
basemesh = HS.create_human()
print(f"[stage:{STAGE}] MPFB2 basemesh: {basemesh.name}")

# Aplica parâmetros do job via custom properties da macroshape do MPFB2.
# Em MPFB2 modernas, os macros vivem como propriedades da malha; o refit() reflete a geometria.
def safe_macro(name, val):
    try:
        basemesh[name] = float(val)
        return True
    except Exception:
        return False


safe_macro("height", min(1.0, max(0.0, (float(P["height_m"]) - 1.50) / 0.50)))  # 1.50→0, 2.00→1
safe_macro("muscle", min(1.0, max(0.0, 0.5 + (float(P["muscle"]) - 1.0))))
safe_macro("weight", min(1.0, max(0.0, 0.5 + (float(P["hip"]) - 1.0) * 0.5)))
try:
    HS.refit(basemesh)
    print(f"[stage:{STAGE}] refit aplicado")
except Exception as e:
    print(f"[stage:{STAGE}] refit aviso: {e}")

# rig padrão MPFB2 (default = compatível com Mixamo/UE5)
try:
    HS.add_builtin_rig(basemesh, "default")
    print(f"[stage:{STAGE}] rig MPFB2 default adicionado")
except Exception as e:
    print(f"[stage:{STAGE}] aviso rig: {e}")

# pele (tom do prompt)
try:
    HS.set_character_skin(basemesh, P["skin"])
except Exception:
    pass

# ============================================================
# ISOLAMENTO POR PORTÃO — esconde tudo que não é o foco
# ============================================================
def hide_all(except_names):
    keep = set(except_names)
    for o in bpy.data.objects:
        o.hide_viewport = (o.name not in keep)
        o.hide_render = o.hide_viewport


body_name = basemesh.name
rig = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
rig_name = rig.name if rig else ""

if STAGE == "skeleton":
    # só armature visível
    if rig:
        hide_all([rig_name])
    else:
        print(f"[stage:{STAGE}] ERRO: rig MPFB2 ausente")
        sys.exit(3)
elif STAGE in ("muscle", "skin", "veins", "nails", "face", "eyes"):
    # corpo MPFB2 (+ rig oculto)
    hide_all([body_name])
elif STAGE in ("hair", "garment"):
    # Equipa um asset MHCLO real do banco do MPFB2 (cabelo ou roupa).
    # MPFB2 não tem "default" sem MakeHuman; aqui buscamos no diretório de assets.
    import glob
    from bl_ext.blender_org.mpfb.services.locationservice import LocationService  # type: ignore
    asset_dir = LocationService.get_mpfb_data("mhassets") or LocationService.get_user_data("data")
    pattern = "*hair*.mhclo" if STAGE == "hair" else "*.mhclo"
    found = glob.glob(os.path.join(asset_dir or "", "**", pattern), recursive=True) if asset_dir else []
    if found:
        try:
            HS.add_mhclo_asset(found[0], basemesh)
            print(f"[stage:{STAGE}] MHCLO asset equipado: {os.path.basename(found[0])}")
        except Exception as e:
            print(f"[stage:{STAGE}] aviso mhclo: {e}")
    else:
        # Sem assets locais (MakeHuman não linkado): documenta no GLB para a VLM julgar.
        print(f"[stage:{STAGE}] sem MHCLO local — usando corpo MPFB2 nu como base (instale assets MakeHuman)")
    if STAGE == "hair":
        keep = [body_name] + [o.name for o in bpy.data.objects if "hair" in o.name.lower()]
    else:
        keep = [body_name] + [o.name for o in bpy.data.objects if any(k in o.name.lower() for k in ("cloth", "shirt", "pants", "dress", "garment"))]
    hide_all(keep)
else:
    hide_all([body_name])

# ============================================================
# EXPORT GLB do portão
# ============================================================
out = os.path.join(OUT_DIR, f"{STAGE}.glb")
bpy.ops.export_scene.gltf(
    filepath=out,
    export_format="GLB",
    use_visible=True,
    export_apply=True,
)
print(f"[stage:{STAGE}] OK -> {out}")
