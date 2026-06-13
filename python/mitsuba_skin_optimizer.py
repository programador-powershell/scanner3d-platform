"""
Polimento final de PELE (SSS) com Mitsuba 3 — renderização inversa diferenciável.
Roda DEPOIS do nvdiffrast já ter colado a geometria à silhueta. Aqui a geometria
fica CONGELADA e só os mapas PBR (albedo) + o raio de espalhamento SSS são
esculpidos contra a foto original, até a pele ter a profundidade/refração real.

Pré-requisitos (uma vez, exige GPU CUDA):
  pip install mitsuba drjit lpips
  (torch com CUDA — a build CPU não roda a variante cuda_ad_rgb)

Uso:
  python python/mitsuba_skin_optimizer.py --scene cena.xml --photo ref.png --iters 50 --out ./tex
Saída: textura de pele refinada (albedo + sss) pronta para a engine.
"""
import argparse
import os
import sys

# ---------------------------------------------------------------
# 1. A Variante Computacional (O Motor do Dr.Jit) — código do diretor (verbatim)
# ---------------------------------------------------------------
try:
    import mitsuba as mi
    import drjit as dr
    # Define a variante: CUDA (GPU), Autodiff (Diferenciável), RGB (Cores)
    mi.set_variant('cuda_ad_rgb')
    _MITSUBA_OK = True
except Exception as _e:  # mitsuba/drjit ausentes ou sem CUDA
    _MITSUBA_OK = False
    _IMPORT_ERR = str(_e)


# ---------------------------------------------------------------
# 2. O Script de Otimização (O Loop AAA) — código do diretor (verbatim)
# ---------------------------------------------------------------
def build_optimizer_class():
    import torch
    import torch.nn.functional as F
    from lpips import LPIPS

    class MitsubaSkinOptimizer:
        def __init__(self, scene_file, foto_original_tensor):
            # 1. Carrega a cena do modelo base (com a câmera alinhada à foto)
            self.scene = mi.load_file(scene_file)
            self.foto_original = foto_original_tensor

            # 2. Avaliador Perceptual (PyTorch)
            self.lpips_metric = LPIPS(net='vgg').cuda()

            # 3. Mapeia os parâmetros que a IA pode alterar
            self.params = mi.traverse(self.scene)

            # Otimizador do Mitsuba (Dr.Jit)
            self.opt = mi.ad.Adam(lr=0.02)

            # Albedo (Cor) e distância de espalhamento SSS da pele
            self.opt['pele_albedo.data'] = self.params['pele_albedo.data']
            self.opt['pele_sss_radius.data'] = self.params['pele_sss_radius.data']  # oclusão de veias/cartilagem

        def passo_de_otimizacao(self):
            # Propaga os parâmetros atuais para a cena antes de renderizar
            self.opt.update()

            # spp baixo (4 a 16) = segredo para não estourar a VRAM;
            # o ruído do path tracer é mitigado pelo momentum do Adam
            render_atual = mi.render(self.scene, params=self.params, spp=16, seed=0)

            # Dr.Jit -> tensor PyTorch (permite ArcFace e LPIPS nativamente)
            render_torch = dr.ext.pytorch.to_pytorch(render_atual).permute(2, 0, 1).unsqueeze(0)

            # --- Perdas ---
            loss_pixel = F.l1_loss(render_torch, self.foto_original)             # cor exata
            loss_perceptual = self.lpips_metric(render_torch, self.foto_original).mean()  # poros/estrutura
            # (injetar aqui a perda de Identidade ArcFace)
            loss_total = loss_pixel + (0.8 * loss_perceptual)

            # --- Retropropagação diferenciável ---
            dr.backward(loss_total)
            self.opt.step()

            # Regra de ouro #3: clamp [0.01, 0.99] — evita violar conservação de energia
            # (pele "radioativa" que destrói os gradientes da próxima iteração)
            for k in ('pele_albedo.data', 'pele_sss_radius.data'):
                self.opt[k] = dr.clip(self.opt[k], 0.01, 0.99)

            return loss_total.item()

    return MitsubaSkinOptimizer


# ---------------------------------------------------------------
# Runner CLI (regras de produção: coarse-to-fine, spp baixo, clamp)
# ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', required=True, help='cena Mitsuba (.xml) com o modelo + câmera alinhada')
    ap.add_argument('--photo', required=True, help='foto de referência (PNG)')
    ap.add_argument('--iters', type=int, default=50)
    ap.add_argument('--out', default='.')
    args = ap.parse_args()

    if not _MITSUBA_OK:
        print(f"[mitsuba] INDISPONÍVEL: {_IMPORT_ERR}")
        print("[mitsuba] instale com GPU CUDA: pip install mitsuba drjit lpips (+ torch CUDA)")
        sys.exit(3)
    if not os.path.exists(args.scene):
        print(f"[mitsuba] cena não encontrada: {args.scene}"); sys.exit(2)

    import torch
    from PIL import Image
    import numpy as np
    foto = torch.from_numpy(np.asarray(Image.open(args.photo).convert('RGB'), dtype='float32') / 255.0)
    foto = foto.permute(2, 0, 1).unsqueeze(0).cuda()

    Optimizer = build_optimizer_class()
    opt = Optimizer(args.scene, foto)

    # Regra #1 (coarse-to-fine): geometria já congelada; aqui só PBR+SSS.
    # Regra #2 (spp baixo no loop, alto só na validação): loop a 16 spp.
    for i in range(args.iters):
        loss = opt.passo_de_otimizacao()
        if i % 5 == 0 or i == args.iters - 1:
            print(f"[mitsuba] iter {i+1}/{args.iters} loss={loss:.5f}")

    # validação final a 256 spp (sem ruído) — render limpo pro portão de revisão
    os.makedirs(args.out, exist_ok=True)
    final = mi.render(opt.scene, params=opt.params, spp=256, seed=0)
    mi.util.write_bitmap(os.path.join(args.out, 'skin_polished.png'), final)
    print(f"[mitsuba] OK -> {os.path.join(args.out, 'skin_polished.png')}")


if __name__ == '__main__':
    main()
