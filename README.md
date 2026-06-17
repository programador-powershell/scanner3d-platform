# Scanner 3D Cognitivo

Plataforma **autônoma** de geração **2D→3D** de humanos realistas (padrão AAA). Você solta uma foto, a IA conduz tudo sozinha — pré-scan, 9 portões anatômicos, julgamento, refino — e entrega um personagem 3D rigado pronto para Blender/UE5.

Documento técnico completo (arquitetura v5, stack open-source auditada): [`docs/PROJETO_IA_3D_AAA.md`](docs/PROJETO_IA_3D_AAA.md).

## Rodar

```bash
npm install
npm start          # http://localhost:3939
```

No boot, o servidor **auto-detecta e sobe a VLM local** (Qwen3-VL-4B no llama.cpp) — sem configurar nada.

## Como usar (zero fricção)

1. Abra `http://localhost:3939`.
2. **Arraste 1+ fotos** (turnaround do personagem) em qualquer lugar da home.
3. Mande no campo de texto (ou só envie a foto).
4. Escolha o modo:
   - **🤖 VLM-auto** + **👁️ qualidade** → a VLM julga cada portão, refina sozinha, avança. Treina o dataset DPO.
   - **🤖 VLM-auto** + **⚡ rápido** → constrói e aprova direto (~minutos para o personagem inteiro).
   - **⚡ pipeline humano** → você aprova/reprova cada portão.
5. No fim: **Visualizador GLB Pro**, **⤓ FBX (UE5)**, **⤓ .blend**.

## Pipeline (v5, auditado jun/2026)

```
FOTO → Qwen3-VL (pré-scan: medidas/pele/roupa) → Florence-2 (segmentação)
     → 8 portões: 🦴 Esqueleto · 💪 Músculos · 🪡 Tecido · 🧫 Pele
                  · 💅 Unhas · 👤 Rosto · 👁️ Olhos · 💇 Cabelo
       cada um: Blender headless (MPFB2) constrói o GLB real → VLM julga → refina → aprova
     → build final (rig + collections por portão) → GLB + FBX (UE5) + .blend
```

Motores open-source plugáveis (ver doc): **Hunyuan3D 2.1** (reconstrução+PBR), **MPFB2/MakeHuman** (corpo), **SMPL-X/SKEL/TailorMe** (anatomia instanciada), **ChatGarment→GarmentCode→Warp/Newton** (roupa), **DiffLocks** (cabelo), **TRELLIS.2** (rígidos), **Material Anything/RGB↔X** (PBR), **Mitsuba 3** (loop diferenciável SSS), **ICT-FaceKit** (ARKit-52), **QRemeshify/Parafashion** (retopo).

## Serviços opcionais (env)

| Variável | Para quê | Sem ela |
|---|---|---|
| (auto) | VLM Qwen3-VL local no llama.cpp | sobe sozinha; senão heurística |
| `HUNYUAN_URL` | reconstrução inicial Hunyuan3D 2.1 | fallback MPFB2 |
| `CHATGARMENT_URL` | sewing pattern do vestido | fallback MHCLO |
| `BLENDER_PATH` | Blender exe (configure se não achar auto; MPFB source is inside project blender/addons/mpfb now) | full pro AAA build |
| `AUTO_VLM=0` | desliga auto-start da VLM | — |

## Arquitetura

- **Backend**: Node + Express. Auto-start VLM, build Blender headless por portão (SSE ao vivo), VLM judge/refine, dataset DPO, cascata síncrona, robusto (try/catch + guarda global, nunca cai).
- **Frontend**: página única estilo Ollama (`public/index.html`) + Visualizador GLB Pro (`public/viewer.html`). three.js.
- **Blender**: `blender/build_stage.py` (1 portão), `blender/build_character.py` (final → GLB+FBX+blend).
- **Treino**: `training/` (Unsloth + Qwen3-VL LoRA, ingestor de conhecimento: References + repos + decisões DPO).
- **Fontes**: ~21 repos GitHub open-source registrados, alimentando o documento.

## Escopo honesto

A **infraestrutura é real e autônoma** (VLM local, build MPFB2/Blender, auto-piloto, FBX UE5). Os **motores pesados** (Hunyuan3D 10-21GB VRAM, TailorMe/Z-Anatomy, ChatGarment) são **plugáveis via env** — quando você tiver o serviço/hardware, conectam sem mudar código. Pesos research-only do MPI (SMPL-X/SKEL/FLAME) exigem licença comercial para produto; caminho livre documentado na seção 7.8.5.

## Stack

Node.js · Express · three.js · Blender 5.1 + MPFB2 · llama.cpp (Qwen3-VL GGUF) · Python (Unsloth/torch/smplx).
