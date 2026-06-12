"""
Corpo paramétrico SMPL-X (repo vchoutas/smplx) — gera os vértices do corpo
a partir dos params do job e exporta OBJ para o Blender consumir.

Pré-requisitos (uma vez):
  pip install smplx torch trimesh
  Baixar os modelos SMPL-X (smplx.is.tue.mpg.de, licença MPI) para ./smpl_models/smplx/

Uso:
  python python/body_smplx.py --job <job.json> --out <dir>
Saída:
  <dir>/body_smplx.obj
"""
import argparse
import json
import os
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--job")
ap.add_argument("--out", default=".")
ap.add_argument("--models", default="smpl_models")
args = ap.parse_args()

if not os.path.isdir(os.path.join(args.models, "smplx")):
    print(f"ERRO: modelos SMPL-X ausentes em {args.models}/smplx — baixe em smplx.is.tue.mpg.de")
    sys.exit(2)

job = json.load(open(args.job, encoding="utf-8")) if args.job else {}
P = {"height_m": 1.7, "hip": 1, "shoulder": 1, "muscle": 1}
P.update(job.get("params") or {})

# ---- código-base do diretor (verbatim) ----
import smplx
import torch

model = smplx.create(
    "smpl_models",
    model_type="smplx",
    gender="neutral"
)

body = model(
    betas=torch.zeros(1,10),
    body_pose=torch.zeros(1,63),
    global_orient=torch.zeros(1,3)
)

vertices = body.vertices
# ---- fim do bloco verbatim ----

# Params do job → betas (aprox.: beta0 ~ altura, beta1 ~ peso/quadril)
betas = torch.zeros(1, 10)
betas[0, 0] = (float(P["height_m"]) - 1.70) * 5.0   # ± altura
betas[0, 1] = (float(P["hip"]) - 1.0) * 3.0          # ± massa/quadril
body = model(betas=betas, body_pose=torch.zeros(1, 63), global_orient=torch.zeros(1, 3))
vertices = body.vertices

# exporta OBJ
import trimesh
mesh = trimesh.Trimesh(vertices[0].detach().cpu().numpy(), model.faces, process=False)
os.makedirs(args.out, exist_ok=True)
out = os.path.join(args.out, "body_smplx.obj")
mesh.export(out)
print(f"[smplx] {vertices.shape[1]} vértices -> {out}")
