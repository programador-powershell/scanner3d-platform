# blender/build_stage.py
# Versão corrigida para estágios (skeleton agora usa o código detalhado real do Blender,
# igual ao build_character.py - não "modelo qualquer").
# Evita crashes (code 2) com try/except + traceback nos logs.
# Export sempre roda para que o .glb seja produzido e o viewer GLB Pro consiga carregar.

import bpy
import sys
import argparse
import json
import traceback
from pathlib import Path

def hide_all(except_names=None):
    if except_names is None:
        except_names = []
    for obj in bpy.data.objects:
        obj.hide_viewport = obj.name not in except_names
        obj.hide_render = obj.name not in except_names

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--garment-pattern', default=None)
    parser.add_argument('--md-path', default=None)
    args = parser.parse_args()

    with open(args.job, 'r', encoding='utf-8') as f:
        job = json.load(f)

    params = job.get('params', {})
    stage = args.stage.lower()

    H = float(params.get("height_m", 1.7)) / 1.7

    try:
        if stage == 'skeleton':
            print("[stage] Construindo esqueleto FORÇADO com MPFB2 (sem fallback manual - falha se não tiver)")
            import addon_utils
            import bpy
            print("[stage][mpfb-debug] preferences.addons keys:", list(bpy.context.preferences.addons.keys())[:10])
            if "mpfb" not in bpy.context.preferences.addons:
                print("[stage] Habilitando MPFB2 addon explicitamente...")
                bpy.ops.preferences.addon_enable(module="mpfb")
            ok = any(m.__name__.startswith(("mpfb", "bl_ext")) and "mpfb" in m.__name__ for m in addon_utils.modules())
            print("[stage][mpfb-debug] mpfb module detected in addon_utils:", ok)
            if not ok:
                print("[stage] ERRO: MPFB2 não encontrado no Blender. Instale e habilite o addon (deve aparecer no N). Falhando o build como pedido.")
                raise RuntimeError("MPFB2 não disponível para estágio skeleton - instale o addon")
            from mpfb.services.humanservice import HumanService
            print("[stage][mpfb-debug] importing HumanService OK, calling create_human()...")
            human = HumanService.create_human()
            if hasattr(HumanService, "apply_macro_details"):
                HumanService.apply_macro_details(human, params)
            print("[stage] Humano MPFB2 criado com sucesso. Name:", getattr(human, 'name', 'unknown'))
            if human:
                for child in human.children:
                    print("[stage][mpfb-debug] child of human:", child.name, child.type)

            # Isolar só o rig do MPFB2 (remover o corpo/mesh, ficar só com o armature do MPFB2)
            arm = None
            for child in human.children:
                if child.type == 'ARMATURE':
                    arm = child
                    break
            if arm:
                # Remover meshes do humano (o corpo)
                to_remove = []
                for obj in list(bpy.data.objects):
                    if obj.type == 'MESH' and (obj == human or obj.parent == human or obj in [c for c in human.children if c.type == 'MESH']):
                        to_remove.append(obj)
                for obj in to_remove:
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except:
                        pass
                arm.name = "SkeletonRig_MPFB2"
                # Tornar visível e exportar só o rig
                hide_all(except_names=[arm.name])
                print("[stage] Isolado o rig do MPFB2 (esqueleto real do MPFB2, sem corpo)")
            else:
                print("[stage] AVISO: não encontrou armature no humano MPFB2, exportando o que estiver visível")
                hide_all(except_names=[human.name])
            print("[stage] Esqueleto do MPFB2 pronto para export")

        elif stage == 'muscle':
            print("[stage] Músculos (stub por enquanto)")
            hide_all(except_names=['body', 'muscles'])

        elif stage == 'garment':
            print("[stage] Roupa (código completo de cones + cloth + wind preservado no histórico)")
            # Para builds de garment o código full anterior funciona. Stub temporário só para não quebrar indent.
            hide_all(except_names=['Vestido_Inner', 'Vestido_Main', 'Vestido_Outer'])

        else:
            hide_all(except_names=[stage])

        # Export sempre (para que o .glb exista e o GLB Pro viewer carregue)
        output_path = str(Path(args.out) / f"{stage}.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_apply=True,
            use_visible=True,
            export_materials='EXPORT'
        )
        print(f"[stage] {stage} exportado -> {output_path}")

    except Exception:
        print(f"[stage] ERRO no estágio {stage}:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()