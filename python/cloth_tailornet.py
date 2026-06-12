"""
TailorNet (repo chaitanya100100/TailorNet) — roupa deformada por pose+shape+style,
com rugas previstas pela rede. Complementa o ChatGarment: o ChatGarment dá o
pattern (o quê); o TailorNet dá a deformação pose-dependente (como veste).

Pré-requisitos (uma vez):
  pip install torch trimesh
  Baixar os pesos do TailorNet (repo oficial) para ./tailornet_model.pt
  (e os dados SMPL exigidos pelo repo)

Uso:
  python python/cloth_tailornet.py --job <job.json> --out <dir>
Saída:
  <dir>/garments/cloth.pt  +  <dir>/garments/cloth.obj
"""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--job")
ap.add_argument("--out", default=".")
ap.add_argument("--weights", default="tailornet_model.pt")
args = ap.parse_args()

if not os.path.exists(args.weights):
    print(f"ERRO: pesos do TailorNet ausentes ({args.weights}) — baixe no repo chaitanya100100/TailorNet")
    sys.exit(2)

job = json.load(open(args.job, encoding="utf-8")) if args.job else {}
P = {"height_m": 1.7, "hip": 1, "muscle": 1}
P.update(job.get("params") or {})

# vetores de condicionamento derivados do job
import torch
pose_vector = torch.zeros(1, 72)                       # A-pose
shape_vector = torch.zeros(1, 10)
shape_vector[0, 0] = (float(P["height_m"]) - 1.70) * 5.0
shape_vector[0, 1] = (float(P["hip"]) - 1.0) * 3.0
style_vector = torch.zeros(1, 4)                       # estilo do garment (gamma)

# ---- código-base do diretor (verbatim) ----
tailornet = torch.load(
    "tailornet_model.pt",
    map_location="cuda"
)

cloth = tailornet.forward(
    pose=pose_vector,
    shape=shape_vector,
    style=style_vector
)

torch.save(
    cloth,
    "garments/cloth.pt"
)
# ---- fim do bloco verbatim ----

# exporta OBJ para o Blender drapear/refinar
out_dir = os.path.join(args.out, "garments")
os.makedirs(out_dir, exist_ok=True)
try:
    import trimesh
    verts = cloth.vertices if hasattr(cloth, "vertices") else cloth
    faces = getattr(cloth, "faces", None)
    if faces is None:
        print("[tailornet] saída sem faces — salvando só o tensor (.pt)")
    else:
        mesh = trimesh.Trimesh(verts.detach().cpu().numpy(), faces, process=False)
        obj = os.path.join(out_dir, "cloth.obj")
        mesh.export(obj)
        print(f"[tailornet] OK -> {obj}")
except Exception as e:
    print(f"[tailornet] export OBJ falhou: {e}")
