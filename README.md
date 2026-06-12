# Scanner 3D Cognitivo

Plataforma de geração **2D→3D por decomposição semântica e reconstrução por camadas** — objetivo: reconstrução humana fiel (não preenchimento tipo Meshy/Hunyuan), com rig anatômico nativo, texturas PBR, cabelo fio a fio e modelo modular padrão AAA.

Documento técnico completo: [`docs/PROJETO_IA_3D_AAA.md`](docs/PROJETO_IA_3D_AAA.md).

## Rodar

```bash
npm install
npm start          # http://localhost:3939
npm run feed       # escaneia D:\References e alimenta o .md
```

## Páginas

- **`/`** — ingestão de dataset: upload de arquivos, links YouTube/Twitter, inventário de referências.
- **`/pipeline.html`** — pipeline interativo estilo **ComfyUI**: grafo de nós (three.js), nó central **LLM · Olho Humano**, revisão aprovar/reprovar por etapa (human-in-the-loop → dataset de preferência DPO), e **edição paramétrica por prompt** (`mude altura para 1,70`, `aumente 20% o quadril`, `tom de pele pardo`, `vento na queda do vestido`).

## Stack v2 (auditado, jun/2026)

`Foto → PSHuman/MagicMan (vistas condicionadas) → gate ArcFace/LPIPS → Florence-2 (camadas) → trilhos: SKEL/ATLAS+HIT (corpo) · FLAME→ICT-FaceKit (rosto) · GarmentCode→drape Warp/Newton (roupa) · TRELLIS.2 (rígidos) · DiffLocks (cabelo) → loop nvdiffrast (pixel-fiel vs foto) → rig SKEL → GLB modular`

## Escopo do protótipo

A **infraestrutura** (grafo de nós, revisão human-in-the-loop, dataset de preferência, edição por prompt, loop de regeneração) é real e funcional. Os **motores de IA** (PSHuman, SKEL/ATLAS, HIT, DiffLocks, nvdiffrast) ainda não rodam — cada nó usa um gerador de preview procedural em three.js, plugável. Detalhes na seção 10.2 do documento técnico.

## Ferramentas externas (fontes)

Links registrados pela página de ingestão alimentam a seção *Fontes de Treinamento* do documento técnico. Ex.:

- [KIRI Engine — 3DGS Render Blender Addon](https://github.com/Kiri-Innovation/3dgs-render-blender-addon) (Apache-2.0) — importa/edita/anima/renderiza **3D Gaussian Splatting** (`.ply`/`.splat`) no Blender. Ponte para a saída Gaussian do LHM++ (seção 7.1) virar asset editável/baking dentro do pipeline.

## Stack

Node.js + Express + Multer · three.js (viewer) · documento em Markdown auto-alimentado.
