# Projeto IA 3D AAA — Scanner 3D Cognitivo

> Plataforma de geração 2D→3D por **Decomposição Semântica e Reconstrução por Camadas** (Layer-Aware 3D Generation). Objetivo: superar Hunyuan3D, Meshy, Tripo e Yvo3D entregando GLB/OBJ modular, com rig anatômico nativo, texturas PBR e fidelidade pixel a pixel — padrão Stellar Blade / Blood Rain.

---

## 1. O Problema das Plataformas Atuais

Ferramentas como Hunyuan3D, Meshy ou Tripo tratam a geração 3D como reconstrução de "casca única" (*single-shell surface projection*). O resultado é uma massa única onde o cabelo funde no ombro, a saia funde na perna e o rigging se torna inutilizável para animação ou jogos.

| Recurso | Plataformas Atuais (Hunyuan, Meshy) | Esta Plataforma |
|---|---|---|
| Estrutura do Mesh | Casca única fundida (Blob-mesh) | Modular (malhas separadas por camadas) |
| Esqueleto (Rigging) | Inexistente ou estimativa volumétrica ruim | Base anatômica humana nativa com Weight Paint preciso |
| Oclusão (partes ocultas) | Textura borrada ou geometria colada | Geração preditiva de peças completas por trás da roupa |
| Cabelo | Malha densa com textura borrada | Sistema de curvas "fio a fio" (Groom Strands) |
| Qualidade de Textura | Vertex color projetado (borrado de perto) | Mapas PBR (Normal, Metallic, Roughness) em alta resolução |

---

## 2. Arquitetura do Sistema: Dupla Engine AAA

```
               [ Imagem 2D de Entrada ]
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
   [ Engine A: Biométrica ]  [ Engine B: Têxtil/Hard-Surface ]
   (Face, Poros, Cabelo)     (Roupas, Camadas, Metais)
            │                         │
            └────────────┬────────────┘
                         ▼
             [ Rig Anatômico Nativo ]
                         ▼
               [ Arquivo GLB Final ]
```

### Engine A: Fidelidade Facial e Micro-Pele (Hiper-realismo)

- **Topologia limpa (Edge Flow):** deformação baseada em modelo humano padrão com loops ideais ao redor de olhos e boca para animação facial perfeita.
- **Decodificador de Micro-Normais:** rede neural secundária (*Generative Displacement Network*) prevê e gera mapas de relevo (Normal/Displacement) em 8K — poros, micro-linhas de expressão, rugosidade real da pele. Elimina o aspecto cartunesco / "efeito de cera".
- **Grooming de Cabelo Baseado em Curvas:** o sombreamento 2D do cabelo é convertido em curvas de interpolação 3D (*Groom Strands*). Cabelo gerado fio a fio (ex.: 50.000 curvas), pronto para reagir à luz individualmente no motor de jogo.

### Engine B: Decomposição de Vestuário e Hard-Surface (Florence-2)

- **Desconstrução Semântica (fine-tuning do Florence-2):** ao receber a imagem 2D, a IA separa os elementos em camadas alpha independentes: Corpo Base (pele), Cabelo, Roupa Íntima/Corset, Saia Externa, Botas, Acessórios (relógios, cartas, cartola).
- **Mapas PBR independentes por material:**
  - *Metais:* Metallic alto, Roughness baixo (correntes, fivelas, relógios).
  - *Tecidos:* Roughness alto, mapas de opacidade (Alpha) para rendas e meias.
- **Geração preditiva de oclusão:** a IA reconstrói o que está oculto (costas do casaco, bota sob a saia) de forma independente, sem emendas ou buracos na malha.

---

## 3. O Núcleo Anatômico (Esqueleto Primeiro)

O rig **não** é gerado depois do mesh — ele vem primeiro.

```
       [ Malha da Roupa (Gerada) ]
                  │
  (Auto-Skinning baseado em Proximidade)
                  ▼
 [ Rig Humano Nativo (Spine/Neck/Pelvis) ] ──► Peso de Deformação Perfeito
```

1. **Esqueleto nativo paramétrico:** o sistema detecta pose e proporções em 2D e instancia um modelo humano paramétrico (evolução de SMPL-X / MetaHuman) com ossos reais (Spine, Neck, Clavicles, Limbs) e Weight Painting calibrado nativamente. Serve de "cabide" para as roupas.
2. **Weight Painting dinâmico automatizado:** espartilho rígido recebe peso travado à espinha; saia volumosa recebe pesos suaves para física de tecido em tempo real (Unreal/Unity).

---

## 4. Geração Multi-View Inpaint por Camada

Para criar o que o olho não vê (costas do espartilho, interior da saia):

- O motor multi-vista é **condicionado na foto original** — PSHuman / MagicMan (seção 7.1) com gate de identidade ArcFace+LPIPS (seção 7.2) — não um gerador de "personagem parecido".
- A IA gera vistas ortográficas (Frente, Costas, Perfis) **por peça**, removendo oclusões. Se a saia cobre a bota, a bota inteira é gerada por baixo, independente.

## 5. Reconstrução de Malha e Mapas PBR

- Conversão das vistas em geometria pelos **trilhos por tipo de camada** (seção 7.3): SKEL+HIT para corpo, FLAME para rosto, padrões de costura para roupa, TRELLIS.2 para rígidos, DiffLocks para cabelo — não NeRF/Gaussian denso e disforme.
- **Traços e linhas:** codificador de contornos (Edge-Detection) força a malha a seguir linhas rígidas em costuras e cortes de tecido; pune desvio da silhueta original (fidelidade pixel a pixel).
- **Texturização PBR:** difusão latente gera Diffuse (Albedo), Normal, Roughness, Metallic.
- **Upscaling:** super-resolutor de texturas 4K/8K especializado em costuras, couro, metais e poros de pele.

## 6. Skinning e Vestimenta Automática

- Auto-skinning projeta pesos de deformação do esqueleto base para as camadas de roupa, respeitando distância da pele.
- A saia se move com as pernas mantendo volume flutuante (peso azul/verde como nas referências de Weight Paint do Blender).

---

## 7. Stack de Modelos Open-Weights v2 (auditado em jun/2026)

> **Auditoria adversarial (jun/2026):** o stack v1 (FLUX.1-LoRA → Unique3D/SF3D → CraftsMan/MeshXL) foi reprovado em todos os estágios. Motivos verificados: (a) LoRA gera "personagem parecido" (~85–92% de consistência), não a SUA imagem — alucina costas e detalhes; (b) o paper do Unique3D confirma que o treino **excluiu** superfícies finas/abertas — roupa vira casca fechada inflada, exatamente o defeito do Meshy/Hunyuan; (c) nenhum modelo open de 2026 gera retopologia quad AAA; (d) "SMPL-X-like" tem 72 DoF falsos, não é esqueleto biomecânico; (e) faltavam por completo os estágios de cabelo fio a fio e rosto animável.

> **Verdade técnica do "pixel a pixel":** imagem 2D é projeção — costas, interior da saia e anatomia interna **não estão no sinal**. Todo sistema preenche o invisível com priors. A diferença real desta plataforma: (1) **fidelidade mensurável no visível** via loop de render-loss contra a foto original (seção 7.4); (2) **qualidade do prior no invisível** — anatômico (SKEL), físico (costura+drape), semântico (camadas).

### Tabela de substituições v1 → v2

| Estágio v1 | Problema verificado | Estágio v2 |
|---|---|---|
| FLUX.1-LoRA turnaround | Amostra distribuição aprendida, não reconstrói a foto | **PSHuman / MagicMan** (condicionados na foto) + gate métrico |
| Unique3D por camada de roupa | Treino excluiu superfícies finas → casca inflada | **Sewing patterns** (ChatGarment/AIpparel → GarmentCode → drape) |
| Unique3D/SF3D geral | Superado por 2 gerações (2024 vs 2026) | **TRELLIS.2-4B** (rígidos) + **PSHuman/LHM++** (humano) |
| CraftsMan / MeshXL | Sem quad AAA; tri ~11–30k faces | High-poly + retopo clássico / registro em template de topologia fixa |
| Esqueleto "SMPL-X-like" | 72 DoF falsos, não-biomecânico | **SKEL** (46 DoF reais) via HSMR + **HIT** (tecidos volumétricos) |
| (sem estágio de cabelo) | Malha = capacete sólido | **DiffLocks** → ~100K strands → Alembic → UE5 Groom |
| (sem estágio facial) | Sem loops, sem boca interna, sem blendshapes | **FLAME** fitting → NRICP em **ICT-FaceKit** → 52 ARKit + wrinkle maps |

### 7.1 Geração Multi-View Condicionada (substitui FLUX.1-LoRA como fonte de verdade)

- **PSHuman** (CVPR 2025): 1 foto → 6 vistas globais + close-up de rosto, condicionado em SMPL-X, difusão cross-scale corpo+face — preserva identidade onde MVDs genéricos mais distorcem.
- **MagicMan** (AAAI 2025): 20 vistas densas RGB+normal com **refinamento iterativo** do SMPL-X contra a referência — mais sinal para reconstrução do que 4 vistas de turnaround.
- **Enhancers** (nunca fonte de verdade): FLUX.2-dev (multi-reference nativo, até 10 imagens), Qwen-Image-Edit (NVS com via de aparência que preserva textura). LoRA via Kohya_ss permanece **só para estilo**, nunca para identidade.

### 7.2 Gate Métrico de Identidade (toda vista passa ou regera)

- **ArcFace cosine** no crop do rosto (render vs foto original) + **LPIPS** no corpo + IoU de silhueta.
- Vista reprovada nunca passa adiante — é regerada. Mesma filosofia do gate RTMW-133 keypoints já validado no projeto Alice.

### 7.3 Trilhos de Reconstrução por Tipo de Camada

Cada camada fatiada pelo Florence-2 segue o trilho do seu material — não existe motor único:

| Camada | Motor (open, jun/2026) | Saída |
|---|---|---|
| Corpo / anatomia | **SKEL** (esqueleto biomecânico 46 DoF) via **HSMR/SKEL-CF**, ou **ATLAS/MHR** para controle per-bone real (ver 7.6); **HIT** preenche músculo/gordura/osso; **Chaos Flesh** (UE5.6/5.7) anima o tecido mole | Humano com ossos reais "desde o esqueleto" |
| Rosto / caretas | **Pixel3DMM / VGGTFace** → parâmetros **FLAME** → registro NRICP em basemesh **ICT-FaceKit** (MIT, loops de boca/olhos, interior bucal, dentes) → transferência das **52 blendshapes ARKit** → wrinkle maps dinâmicos via **DECA** + tension masks | Cabeça animável FACS, topologia fixa |
| Roupa de pano | **ChatGarment / AIpparel** (CVPR 2025) → padrão de costura **GarmentCode** → drape físico (PyGarment/XPBD) sobre o corpo SKEL → otimização do padrão contra as vistas validadas | Malha aberta simulável, UV por painel, costuras reais |
| Rígidos (armadura, fivelas, joias, botas) | **TRELLIS.2-4B** (MIT) condicionado multi-image | Malha PBR de alta fidelidade |
| Cabelo fio a fio | **DiffLocks** (1 foto → ~100K strands, Meshcapade/MPI) → Alembic `.abc` → **UE5 Groom** (binding ao skeletal mesh) → hair cards como LOD de gameplay | Strands reais, não "capacete" |

- **Veias e poros = textura, não geometria:** displacement micro (<0,1 mm) + albedo + subsurface scattering (veias em nariz/orelhas/bochechas). Só veia saliente que muda silhueta vira relevo.
- **Retopologia:** high-poly dos trilhos + retopo clássico ou registro em template de topologia fixa — nenhum gerador open de 2026 entrega quad AAA direto. Ferramentas open de quad remesh para esse passo: **QRemeshify** (addon Blender, base QuadWild + Bi-MDF) e **AutoRemesher** (standalone, autor do Dust3D) — ambas GPL-3.0 (uso como ferramenta externa ok; não linkar em código proprietário).

### 7.4 Loop de Fechamento — Differentiable Rendering (nvdiffrast)

**É este loop — não o gerador — que entrega o "pixel a pixel".** A malha é renderizada nas câmeras conhecidas e textura + offsets de geometria são otimizados por gradiente contra a **foto original**, até LPIPS/ArcFace baterem (coarse-to-fine 512→4096):

```python
import torch
import nvdiffrast.torch as dr
import torch.nn.functional as F
from lpips import LPIPS

class AAAOptimizationPipeline(torch.nn.Module):
    def __init__(self, mesh_base, textura_inicial):
        super().__init__()
        # Definimos os parâmetros que o nvdiffrast vai esculpir matematicamente
        self.vertices_offsets = torch.nn.Parameter(torch.zeros_like(mesh_base.vertices))
        self.mapa_textura = torch.nn.Parameter(textura_inicial.clone())
        self.mesh_base = mesh_base
        
        # Carrega o avaliador perceptual perceptual AAA
        self.lpips_metric = LPIPS(net='vgg').cuda()
        self.glctx = dr.RasterizeGLContext() # Inicializa o contexto de renderização na GPU
        
    def renderizar_modelo(self, mvp_matrix, resolucao):
        # Aplica os offsets esculpidos pela IA nos vértices originais (SKEL/FLAME)
        vertices_otimizados = self.mesh_base.vertices + self.vertices_offsets
        
        # Transforma os vértices para o espaço de clipagem
        vertices_clip = transform_vertices(vertices_otimizados, mvp_matrix)
        
        # Rasterização Diferenciável Ultra-Rápida da NVIDIA
        rast_out, _ = dr.rasterize(self.glctx, vertices_clip, self.mesh_base.faces, resolution=[resolucao, resolucao])
        
        # Interpolação de texturas PBR pixel a pixel
        tex_coords = interpolate_texture(rast_out, self.mesh_base.uvs)
        render_final = dr.texture(self.mapa_textura, tex_coords)
        
        return render_final

    def otimizar_passo(self, foto_original, mvp_matrix, optimizer):
        optimizer.zero_grad()
        
        # 1. Renderiza o modelo atual
        render_atual = self.renderizar_modelo(mvp_matrix, resolucao=2048)
        
        # 2. Calcula as perdas estritas contra a foto original
        loss_pixel = F.mse_loss(render_atual, foto_original)
        loss_perceptual = self.lpips_metric(render_atual, foto_original).mean()
        
        loss_total = loss_pixel + (0.8 * loss_perceptual)
        
        # 3. Retropropagação dos gradientes diretamente na geometria e textura
        loss_total.backward()
        optimizer.step()
        
        return loss_total.item()
```

Extensões do loop para o caso humano:
- **Termo de identidade facial:** `loss_total += w_id * (1 - arcface_cosine(crop_rosto(render), crop_rosto(foto)))` — trava o rosto.
- **Regularização de offsets:** penalizar `vertices_offsets` por Laplacian smoothing para não rasgar a malha base SKEL/FLAME.
- **Coarse-to-fine:** otimizar textura em 512 → 1024 → 2048 → 4096, congelando geometria nas resoluções altas.

### 7.5 Sequência Unificada v2

```
[ Foto 2D ]
   │
   ▼
[ PSHuman / MagicMan ]  vistas CONDICIONADAS na foto (6–20)
   │
   ▼
[ GATE: ArcFace + LPIPS + silhueta ]  reprovou → regera
   │
   ▼
[ Florence-2 ]  fatiamento semântico em camadas
   ├─ corpo/rosto → SKEL+HIT / FLAME+blendshapes (topologia fixa)
   ├─ roupa pano  → padrão de costura → drape físico → otimiza vs vistas
   ├─ rígidos     → TRELLIS.2-4B
   └─ cabelo      → DiffLocks strands → Groom UE5
   │
   ▼
[ LOOP nvdiffrast ]  render vs FOTO ORIGINAL até métricas baterem  ← "pixel a pixel" real
   │
   ▼
[ Rig SKEL + blendshapes ARKit ] ──► [ .glb modular PBR ]
```

### 7.6 Camadas Anatômicas: do Osso à Pele (revisado em jun/2026)

> **Veredito da verificação adversarial:** as 4 propostas de anatomia estão **parcialmente corretas** — a intenção é boa, mas várias ferramentas citadas estão erradas ou já cobertas pelo v2. Correções abaixo, com a melhor solução open real de cada camada.

**💀 Esqueleto e Ossos** — proposta: "SKEL/SMPL-X com ajuste de comprimento/espessura/escala per-bone".
- ❌ **Erro:** SKEL **não** tem knob per-bone. Sua geometria é determinada por só 2 vetores — shape β (10-dim, ~altura/peso) e pose q (46-dim). O ajuste de proporções é **global** (otimiza os 10 β), não per-osso. SMPL-X é pior (eixos entrelaçados: mexer ombro afeta o corpo todo).
- ⚠️ **Redundância:** o v2 já recupera SKEL de 1 foto via HSMR — subir para **SKEL-CF** (nov/2025, ~19% MPJPE / ~35% PA-MPJPE melhor).
- ✅ **Melhor solução para o controle per-bone que a proposta pede:** **ATLAS** (ICCV 2025), open-source dentro do **Meta MHR** — desacopla esqueleto de shape: **76 atributos esqueléticos (15 escalas + 61 comprimentos de osso)** independentes, + dedos + correctives de pose. Inclui fitting multi-stage de 1 imagem (esqueleto por keypoints/depth, forma por silhueta — separados), batendo SMPLify-X. Para proporções precisas padrão Stellar Blade, migrar o trilho de corpo de SKEL→**ATLAS/MHR**.

**💪 Músculos e Veias** — proposta: "Anatomical NeRF / MedNeRF para volume muscular + SSS/displacement para veias".
- ❌ **Erro de categoria:** MedNeRF reconstrói **CT a partir de raio-X** — domínio de atenuação de raios-X, não RGB. **Não existe** caminho "foto RGB → músculo via MedNeRF" (exigiria CT do sujeito). Inviável como descrito.
- ⚠️ **Redundância:** volume muscular interno a partir da superfície **já é o HIT** (CVPR 2024, no v2) — prediz músculo/osso/gordura como campo implícito parametrizado por SMPL.
- ✅ **Melhor solução:** **HIT** (envelope anatômico) + **Chaos Flesh** (UE5.6/5.7, simulação tetraédrica soft-body real-time, grátis com a engine, sucessor de fato do Ziva) para o músculo inchar/deslizar sob a pele. **Veias = material, não geometria:** Subsurface Profile + mapa subdérmico/vascular + **thickness map** alimentando transmission/backscatter (efeito retroiluminado em orelhas/dedos). Displacement de veia só em antebraço/dorso muito proeminentes. **Cortar MedNeRF.**

**👗 Tecido** — proposta: "Taichi / PhysX Differentiable Simulator + difusão para micro-PBR".
- ❌ **Erro:** **"PhysX Differentiable Simulator" não existe** — PhysX 5 é open mas não diferenciável.
- ⚠️ **Redundância:** o drape v2 (PyGarment/GarmentCode) **já roda sobre NVIDIA Warp**, que **é** auto-diferenciável (forward+backward, gradiente via PyTorch/JAX) com self-collision custom. Trocar por Taichi+PhysX é piorar.
- ✅ **Melhor solução:** consolidar no **NVIDIA Warp** e migrar o solver para **Newton 1.0** (GA mar/2026, Linux Foundation — NVIDIA+DeepMind+Disney, solver VBD para cloth, auto-diff nativo). A parte **realmente nova** é o micro-PBR: **FabricGen** (yarn-level: normal/tangent/height de fios, flyaway fibers, close-up AAA) + **FabricDiffusion** (SVBRDF tileable a partir de foto in-the-wild, casa com o trilho ChatGarment).

**🪞 Pele e Unhas** — proposta: "Generative Displacement Network (GDN) + nvdiffrast esculpe poros pixel a pixel; unhas refinadas por IA".
- ❌ **"GDN" não é um modelo real** — termo genérico/alucinado. Reais: **Texture2Disp** (CVPR 2018) e o paper **SIGGRAPH 2025** de microestrutura facial.
- ❌ **Erro físico:** esculpir poro (~0,05–0,2 mm) como **geometria de vértice** via nvdiffrast é inviável (>10M vértices na face, estoura o rasterizador com aliasing).
- ✅ **Melhor solução:** poro/ruga como **displacement map de alta frequência** (+ normal derivado), otimizado por gradiente **dentro do loop nvdiffrast que já existe** (7.4), com bootstrap via Texture2Disp/FFHQ-UV. Tessellation adaptativa só onde a silhueta exige; o resto vira normal map. **Unhas:** geometria fica no template (low-poly só p/ silhueta e borda livre); brilho especular, cutícula e transição de cor (lúnula) são **material** (normal + specular/roughness + SSS), não otimização de vértice.

### 7.7 Licenças (atenção para uso comercial)

| Componente | Licença | Ação |
|---|---|---|
| TRELLIS.2-4B | MIT | Livre ✓ |
| ICT-FaceKit | MIT | Livre ✓ |
| NVIDIA Warp / Newton 1.0 | Apache-2.0 / Linux Foundation | Livre ✓ |
| Chaos Flesh (UE5.6/5.7) | Epic EULA | Grátis com a engine; royalty Epic padrão |
| ATLAS / MHR | Meta (checar termos) | Verificar uso comercial no repo facebookresearch/MHR |
| FabricGen / FabricDiffusion | Checar paper (2026) | Verificar release de pesos/licença |
| DiffLocks / Im2Haircut / dataset Perm | Não-comercial (MPI/3DGS) | Licenciar com Meshcapade ou retreinar em dataset sintético próprio (pipeline Blender do DiffLocks gera 40K penteados) |
| FLUX.2-dev | Transformer non-commercial | Avaliar; usar só como enhancer opcional |
| Hunyuan3D-2.x/3.x | Exclui UE/UK/Coreia | Isolar componente se a plataforma for global |
| SKEL / HIT / FLAME / SMPL-X | Licenças MPI (pesquisa) | Checar termos comerciais com Meshcapade/MPI |

---

## 8. Estratégia de Treinamento (Google Colab)

Florence-2 é leve (Base ~232M, Large ~770M parâmetros) — fine-tuning viável em T4/L4/A100 do Colab. Treinamento modular, checkpoints no Google Drive/Hugging Face.

### Dataset Semente (engenharia reversa de modelos AAA)

Script em lote (Python/Blender) por personagem:
1. **Render 2D principal:** print HD do personagem completo (Frente, Costas, Diagonal).
2. **Isolamento de camadas:** exporta corpo base sozinho; depois cada peça de roupa isolada com fundo transparente.
3. **Mapeamento de texto:** descrição por camada (ex.: "Camada_1: Espartilho de couro marrom com fivelas de prata").

### Notebooks

| Notebook | Função | Técnica |
|---|---|---|
| 0 — Multi-View condicionado | Vistas fiéis à foto + gate de identidade (seções 7.1/7.2) | **PSHuman / MagicMan** + ArcFace/LPIPS; LoRA Kohya_ss (100 imagens AAA + frames YouTube) **só para estilo** |
| 1 — Florence-2 | Segmentação e identificação de camadas | Fine-tuning supervisionado + **QLoRA 4-bit** |
| 2 — Trilhos 3D | Reconstrução por tipo de camada (seção 7.3) | TRELLIS.2-4B, ChatGarment→GarmentCode, SKEL via HSMR, DiffLocks; checkpoints no Drive a cada 500 passos |
| 3 — Gerador PBR | Albedo/Normal/Roughness/Metallic a partir de sombreamento 2D | ControlNet adaptado para mapas PBR |
| 4 — Loop nvdiffrast | Otimização inversa textura+geometria contra a foto original (seção 7.4) | MSE + LPIPS + ArcFace, coarse-to-fine 512→4096, A100 |

### Otimização de VRAM

```python
import torch
# 1. Gradient Checkpointing (economiza até 30% de VRAM)
model.gradient_checkpointing_enable()
# 2. Precisão mista (AMP/FP16) — dobra a velocidade nas GPUs do Colab
scaler = torch.cuda.amp.GradScaler()
# 3. Limpeza de memória
torch.cuda.empty_cache()
```

### Formato de treino do Florence-2

```python
prompt_entrada = "<CORE_ANATOMY_DETECTION>"  # tarefa personalizada
# Ground truth: "espartilho [x1,y1,x2,y2] pele_base [x3,y3,x4,y4] botas [x5,y5,x6,y6]"
```

---

## 9. Ingestão de Vídeos do YouTube (Renderização)

Vídeos (turnarounds 360°, showcases, gameplay 4K de Stellar Blade / Blood Rain) trazem **consistência temporal** e comportamento de luz em movimento.

```
[ Link do YouTube ] ──► (yt-dlp + FFmpeg) ──► [ Quadros Isolados ]
                                                     │
                                                     ▼
[ Mapas PBR + Rig ] ◄── (Inverse Rendering) ◄── [ Rastreamento Florence-2 ]
```

1. **Captura (yt-dlp + FFmpeg):** download em resolução máxima; amostragem espaçada de frames (ex.: 1 a cada 15) para evitar redundância/overfit.
2. **Rastreamento temporal (CoTracker / DEVA):** o Florence-2 mantém a identificação dos mesmos elementos ("jaqueta de couro") enquanto o personagem gira — aprende volumetria 3D contínua.
3. **Renderização Inversa (Inverse Rendering):** separa matematicamente a cor real do tecido (Albedo) dos reflexos/iluminação do vídeo (Roughness/Metallic) — texturas limpas, prontas para reiluminação na engine.
4. **Física por vídeo:** correlaciona movimento do esqueleto com deformação de tecido (Cloth Simulation) → Weight Painting dinâmico aprendido de cinemática real.

### Script de ingestão (Colab)

```python
# Instalação
# !pip install -q yt-dlp opencv-python-headless pillow accelerate transformers
# !apt-get install -y ffmpeg -q

import yt_dlp, cv2, os, shutil
from PIL import Image

def baixar_e_extrair_frames(url_youtube, pasta_destino, pular_frames=15):
    """Baixa vídeo do YouTube em qualidade máxima e extrai frames espaçados."""
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
        'outtmpl': f'{pasta_destino}/video_temp.mp4',
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url_youtube])
    cap = cv2.VideoCapture(f'{pasta_destino}/video_temp.mp4')
    frame_count = saved_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % pular_frames == 0:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            Image.fromarray(frame_rgb).save(f"{pasta_destino}/yt_frame_{saved_count:04d}.png")
            saved_count += 1
        frame_count += 1
    cap.release()
    os.remove(f'{pasta_destino}/video_temp.mp4')
    print(f"✅ {saved_count} frames extraídos.")

def unificar_dataset(origem, destino):
    """Une imagens locais (dataset semente) com frames do YouTube."""
    arquivos = [f for f in os.listdir(origem) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    for i, arq in enumerate(arquivos):
        shutil.copy(os.path.join(origem, arq), os.path.join(destino, f"local_image_{i:04d}.png"))
    print(f"📦 {len(arquivos)} imagens locais unificadas.")

# Uso:
# PASTA_DATASET = "/content/dataset_treinamento"
# baixar_e_extrair_frames("LINK_DO_YOUTUBE", PASTA_DATASET, pular_frames=15)
# unificar_dataset("/content/suas_100_imagens", PASTA_DATASET)
```

---

## 10. Plataforma Web (este repositório)

Site local em `D:\scanner3d-platform` (`npm start` → http://localhost:3939). Duas páginas:

### 10.1 Ingestão de dataset (`/`)

- **Upload de arquivos** (imagens, GLB/FBX, texturas) → `data/uploads/` + registrados abaixo.
- **Links do Twitter/X e YouTube** (vídeos de aprendizado/renderização) → registrados abaixo, viram fila de ingestão para o pipeline do Colab (seção 9).
- **Inventário de referências** de `D:\References` alimentado automaticamente (seção 13).

### 10.2 Pipeline interativo — grafo de nós + LLM no loop (`/pipeline.html`)

Funciona como um **ComfyUI**: cada etapa do pipeline v2 (seção 7.5) é um **nó** no grafo (`three.js` para o preview 3D no navegador), e tudo passa por um nó central **LLM · Olho Humano** que orquestra, julga e é condicionado pela revisão humana.

**Fluxo human-in-the-loop (fine-tuning interativo):**
1. Usuário envia a imagem 2D → cria um *job* com 9 nós/etapas.
2. A cada etapa, o sistema **gera o resultado, renderiza em 3D e captura uma imagem** ("cria uma imagem do que foi feito") exibida para revisão.
3. **Aprovar** → o nó fica verde e libera a próxima etapa.
4. **Reprovar** (com nota opcional) → a etapa **entende que aquela abordagem não serve e regera com outra abordagem** (incrementa `approach`), repetindo até aprovação. Ex.: reprovou o esqueleto → gera um esqueleto diferente.
5. Cada decisão vira uma linha do **dataset de preferência** (`data/finetune_dataset.jsonl`): par `{snapshot, source, label: approved|rejected, note, stage}` — material direto para **DPO / reward model** por etapa. Aprovados = positivos; reprovados = negativos.

**Controle paramétrico por prompt** (linguagem natural, pt-BR) — cada comando ajusta o modelo e é registrado como sinal de condicionamento:
- `mude altura para 1,70` → escala antropométrica (baseline 1,70 m).
- `aumente 20% o quadril` / `diminua 10% o ombro` / `engrossar 30% a musculatura` → multiplicadores per-região (mapeiam aos 76 atributos do ATLAS, seção 7.6).
- `tom de pele pardo` (clara/morena/parda/oliva/negra…) → albedo/SSS.
- `simular vento na queda do vestido` → liga a **resposta real de tecido**.

> **Escopo honesto:** os motores reais de IA (PSHuman, SKEL/ATLAS, HIT, DiffLocks, loop nvdiffrast) **não rodam neste protótipo** — cada nó usa um gerador de preview procedural em `three.js`, plugável, que muda visivelmente de abordagem ao reprovar e reage aos prompts. A **infraestrutura** (grafo de nós, revisão, dataset de preferência, edição por prompt, loop de regeneração) é real e funcional; basta plugar os modelos da seção 7 no lugar de cada gerador procedural.

### 10.3 Física de tecido real (não "cola", não rígido)

O requisito "se está de vestido e cai num lugar mais baixo, o vestido levanta como se o vento agisse de verdade" é **simulação de tecido diferenciável** (seção 7.6): NVIDIA **Warp / Newton 1.0** (VBD) para drape e resposta dinâmica; o vestido é malha **aberta** drapeada sobre o corpo (rota sewing-pattern), nunca casca fechada colada. No protótipo, o nó **Física / Vento** demonstra a barra do vestido subindo e inflando conforme a intensidade do vento. Objetivo de qualidade: corpo sem triangulação grosseira, mecânica corporal real (HIT + Chaos Flesh) e tecido com resposta real — padrão estúdio AAA.

### 10.4 Asset Pack e Visualizador GLB

- **`/assetpack.html`** — gerador de pacote no estilo *Mint*: 1 prompt → N assets 3D exibidos como cards arredondados flutuantes (board claro, render `three.js` por card, pop-in, mesmo prompt = mesmo pacote). Clique abre viewer 3D vivo. (Assets procedurais plugáveis; o gerador real entra no lugar de `renderAsset`.)
- **`/viewer.html`** — inspetor GLB padrão AAA: drag-drop ou seletor de modelos enviados, **3 modos** (Render PBR · Sólido/Clay · **Topologia/Wireframe**), auto-rotação 360°, iluminação de estúdio (key/fill/rim + `RoomEnvironment`), chão com sombra, e **polycount** (vértices/polígonos). O modo Wireframe é a verificação visual de "sem triângulo grosseiro" — topologia limpa exigida na seção 7.

**Endpoints novos:** `POST /api/jobs` (cria job), `GET /api/jobs/:id`, `POST /api/jobs/:id/stages/:stage/snapshot` (grava preview), `POST .../review` (aprova/reprova → dataset), `POST /api/jobs/:id/params` (edição por prompt), `GET /api/dataset[/export]` (estatísticas / `.jsonl`), `GET /api/models` (GLBs enviados para o visualizador).

---

## 11. Fontes de Treinamento (alimentado pelo site)

<!-- AUTO:SOURCES:START -->
### GitHub — ferramentas e código de referência (3)

- [KIRI Engine 3DGS Render - addon Blender p/ Gaussian Splatting (importa/edita/anima/renderiza .ply/.splat), Apache-2.0](https://github.com/Kiri-Innovation/3dgs-render-blender-addon) — adicionado em 2026-06-12T18:08:53.089Z
- [QRemeshify - addon Blender de retopologia quad (base QuadWild + Bi-MDF), GPL-3.0. Retopo classico da secao 7.6](https://github.com/ksami/QRemeshify) — adicionado em 2026-06-12T19:47:07.070Z
- [AutoRemesher - remesh quad automatico standalone (autor do Dust3D), GPL-3.0. Retopo classico da secao 7.6](https://github.com/huxingyi/autoremesher) — adicionado em 2026-06-12T19:47:07.107Z
<!-- AUTO:SOURCES:END -->

## 12. Arquivos Enviados (upload via site)

<!-- AUTO:UPLOADS:START -->
*Nenhum arquivo enviado ainda.*
<!-- AUTO:UPLOADS:END -->

## 13. Arquivos de Referência (`D:\References`)

<!-- AUTO:REFERENCES:START -->
*Inventário gerado em 2026-06-11T21:00:34.366Z a partir de `D:\References`.*

**Total: 501 arquivos — 4.03 GB**

| Categoria | Arquivos | Tamanho |
|---|---|---|
| Imagens de conceito | 145 | 291.7 MB |
| Modelos 3D (GLB/OBJ) | 29 | 2.27 GB |
| Modelos 3D / Rigs (FBX) | 34 | 303.0 MB |
| Texturas PBR | 114 | 1.07 GB |
| Animações (FBX) | 169 | 116.7 MB |
| Documentos (roteiro/lore) | 2 | 999.2 KB |
| Imagens diversas | 8 | 2.4 MB |

<details>
<summary><strong>Imagens de conceito</strong> — 145 arquivos (291.7 MB)</summary>

| Arquivo | Tamanho |
|---|---|
| `img/cenarios das mesas.png` | 2.5 MB |
| `img/cenas/cena1.png` | 2.2 MB |
| `img/cenas/cena10.png` | 2.3 MB |
| `img/cenas/cena11.png` | 2.3 MB |
| `img/cenas/cena12.png` | 2.6 MB |
| `img/cenas/cena13.png` | 2.2 MB |
| `img/cenas/cena14.png` | 2.2 MB |
| `img/cenas/cena15.png` | 2.4 MB |
| `img/cenas/cena17.png` | 2.4 MB |
| `img/cenas/cena18.png` | 1.6 MB |
| `img/cenas/cena2.png` | 2.1 MB |
| `img/cenas/cena3.png` | 2.2 MB |
| `img/cenas/cena4.png` | 2.2 MB |
| `img/cenas/cena6.png` | 2.2 MB |
| `img/cenas/cena7.png` | 2.4 MB |
| `img/cenas/cena8.png` | 2.0 MB |
| `img/cenas/cena9.png` | 2.3 MB |
| `img/cenas/lidia-boss.png` | 2.5 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_46 (1).png` | 2.4 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_46 (2).png` | 2.2 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_47 (3).png` | 2.3 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_47 (4).png` | 2.3 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_47 (5).png` | 2.4 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_47 (6).png` | 2.4 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_48 (7).png` | 2.4 MB |
| `img/color/ChatGPT Image 25 de mai. de 2026, 02_36_48 (8).png` | 2.4 MB |
| `img/efeitos/debuff-skill.png` | 2.3 MB |
| `img/efeitos/obter-skill.png` | 2.1 MB |
| `img/efeitos/rose-drift.png` | 2.1 MB |
| `img/efeitos/transformação-vestido.png` | 2.2 MB |
| `img/irmã.png` | 2.0 MB |
| `img/lidia-boss.png` | 2.5 MB |
| `img/menu.png` | 725.3 KB |
| `img/Model 3D/Alice-3D.png` | 2.2 MB |
| `img/Model 3D/alice-chapeleiro.png` | 2.0 MB |
| `img/Model 3D/alice-coelho.png` | 2.0 MB |
| `img/Model 3D/alice-faca-cozinha.png` | 2.1 MB |
| `img/Model 3D/alice-gato.png` | 2.0 MB |
| `img/Model 3D/alice-lagarta.png` | 2.2 MB |
| `img/Model 3D/alice-rainha.png` | 2.0 MB |
| `img/Model 3D/armas.png` | 2.0 MB |
| `img/Model 3D/BASE/alice base/alice-faca-cozinha.png` | 2.1 MB |
| `img/Model 3D/BASE/alice base/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_16 (1).png` | 2.1 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_16 (2).png` | 2.1 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_17 (3).png` | 2.3 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_17 (4).png` | 2.2 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_17 (5).png` | 2.2 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_18 (6).png` | 2.3 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_18 (7).png` | 2.3 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_19 (8).png` | 2.0 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_19 (9).png` | 2.1 MB |
| `img/Model 3D/BASE/alice base/ChatGPT Image 7 de jun. de 2026, 11_25_20 (10).png` | 2.5 MB |
| `img/Model 3D/BASE/Alice chapeleiro/alice-chapeleiro.png` | 2.0 MB |
| `img/Model 3D/BASE/Alice chapeleiro/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_53 (1).png` | 2.2 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_53 (2).png` | 2.2 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_53 (3).png` | 2.3 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_53 (4).png` | 2.3 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_54 (5).png` | 2.3 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_54 (6).png` | 2.3 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_54 (7).png` | 2.1 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_55 (8).png` | 2.0 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_55 (9).png` | 2.6 MB |
| `img/Model 3D/BASE/Alice chapeleiro/ChatGPT Image 7 de jun. de 2026, 11_05_56 (10).png` | 2.2 MB |
| `img/Model 3D/BASE/alice cheshire/alice-gato.png` | 2.0 MB |
| `img/Model 3D/BASE/alice cheshire/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_47 (1).png` | 2.3 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_48 (2).png` | 1.9 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_48 (3).png` | 2.2 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_48 (4).png` | 2.0 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_49 (5).png` | 2.0 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_49 (6).png` | 2.2 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_49 (7).png` | 2.2 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_50 (8).png` | 2.2 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_53 (10).png` | 2.3 MB |
| `img/Model 3D/BASE/alice cheshire/ChatGPT Image 7 de jun. de 2026, 13_36_53 (9).png` | 2.1 MB |
| `img/Model 3D/BASE/alice coelho/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_39 (1).png` | 2.5 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_40 (2).png` | 2.3 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_40 (3).png` | 2.4 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_40 (4).png` | 2.4 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_40 (5).png` | 2.4 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_41 (6).png` | 2.3 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_42 (7).png` | 2.6 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_42 (8).png` | 2.4 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_45 (9).png` | 2.3 MB |
| `img/Model 3D/BASE/alice coelho/ChatGPT Image 7 de jun. de 2026, 13_26_46 (10).png` | 2.7 MB |
| `img/Model 3D/BASE/alice lagarta/alice-lagarta.png` | 2.2 MB |
| `img/Model 3D/BASE/alice lagarta/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_17 (1).png` | 2.5 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_18 (2).png` | 2.4 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_18 (3).png` | 2.2 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_18 (4).png` | 1.9 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_18 (5).png` | 2.4 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_19 (6).png` | 2.4 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_20 (7).png` | 2.4 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_20 (8).png` | 2.1 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_23 (10).png` | 2.3 MB |
| `img/Model 3D/BASE/alice lagarta/ChatGPT Image 7 de jun. de 2026, 13_44_23 (9).png` | 2.4 MB |
| `img/Model 3D/BASE/alice rainha/alice-rainha.png` | 2.0 MB |
| `img/Model 3D/BASE/alice rainha/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (1).png` | 2.2 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (2).png` | 2.0 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (3).png` | 2.2 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (4).png` | 2.3 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (5).png` | 2.1 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_24 (6).png` | 2.3 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_25 (10).png` | 2.3 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_25 (7).png` | 2.3 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_25 (8).png` | 2.3 MB |
| `img/Model 3D/BASE/alice rainha/ChatGPT Image 7 de jun. de 2026, 13_51_25 (9).png` | 2.2 MB |
| `img/Model 3D/BASE/alice.jpg` | 44.0 KB |
| `img/Model 3D/BASE/cavaleiro.jpg` | 30.7 KB |
| `img/Model 3D/BASE/chapeleiro.jpg` | 33.5 KB |
| `img/Model 3D/BASE/coelho.jpg` | 35.7 KB |
| `img/Model 3D/BASE/lidia.jpg` | 41.6 KB |
| `img/Model 3D/BASE/rainha.jpg` | 44.2 KB |
| `img/Model 3D/boss-soldado.png` | 2.1 MB |
| `img/Model 3D/chapeleiro.png` | 2.2 MB |
| `img/Model 3D/coelho-boss.png` | 2.0 MB |
| `img/Model 3D/coelho.png` | 1.8 MB |
| `img/Model 3D/faca-lidia-boss.png` | 2.2 MB |
| `img/Model 3D/lagarta-boss.png` | 2.2 MB |
| `img/Model 3D/Lidia_Boss.png` | 2.5 MB |
| `img/Model 3D/Lidia-3D.png` | 2.0 MB |
| `img/Model 3D/mob-biscoito.png` | 1.9 MB |
| `img/Model 3D/mob-bule.png` | 1.8 MB |
| `img/Model 3D/mob-carta.png` | 1.3 MB |
| `img/Model 3D/mob-soldado.png` | 2.0 MB |
| `img/Model 3D/odachi-lidia-boss.png` | 2.1 MB |
| `img/Model 3D/rainha-boss.png` | 2.3 MB |
| `img/Model 3D/weapon-bengala-cha-eterno.png` | 2.3 MB |
| `img/Model 3D/weapon-foice-lagarta-azul.png` | 2.2 MB |
| `img/Model 3D/weapon-guillotine-heartbreaker.png` | 2.3 MB |
| `img/Model 3D/weapon-relogio-coelho-branco.png` | 2.3 MB |
| `img/Model 3D/weapon-sorriso-cheshire.png` | 2.3 MB |
| `img/Model 3D/xicara-boss.png` | 1.6 MB |
| `img/Perfil/alice.png` | 2.4 MB |
| `img/Perfil/arma-inicial.png` | 1.8 MB |
| `img/Perfil/armas.png` | 2.2 MB |
| `img/Perfil/boss-mennores.png` | 2.5 MB |
| `img/Perfil/lidia-boss.png` | 220.1 KB |
| `img/Perfil/lidia.png` | 2.0 MB |
| `img/trailer geral.png` | 2.6 MB |

</details>

<details>
<summary><strong>Modelos 3D (GLB/OBJ)</strong> — 29 arquivos (2.27 GB)</summary>

| Arquivo | Tamanho |
|---|---|
| `3D/adaga.glb` | 80.4 MB |
| `3D/alice-chapepeiro.glb` | 80.0 MB |
| `3D/alice-cheshire.glb` | 82.9 MB |
| `3D/alice-coelho.glb` | 84.1 MB |
| `3D/alice-lagarta.glb` | 86.1 MB |
| `3D/alice-rainha.glb` | 80.4 MB |
| `3D/alice-vestido.glb` | 81.8 MB |
| `3D/alice.glb` | 69.4 MB |
| `3D/biscoito-mob.glb` | 88.7 MB |
| `3D/bule.glb` | 86.7 MB |
| `3D/cajado.glb` | 78.3 MB |
| `3D/carta.glb` | 87.7 MB |
| `3D/cavaleiro-vestido.glb` | 79.0 MB |
| `3D/cavaleiro.glb` | 64.6 MB |
| `3D/chapeleiro.glb` | 78.5 MB |
| `3D/cheshire.glb` | 93.5 MB |
| `3D/coelho-vestido.glb` | 79.6 MB |
| `3D/coelho.glb` | 67.9 MB |
| `3D/espadao.glb` | 82.8 MB |
| `3D/faca.glb` | 81.8 MB |
| `3D/foice.glb` | 80.1 MB |
| `3D/lagarta.glb` | 80.8 MB |
| `3D/lidia-boss-vestido.glb` | 78.3 MB |
| `3D/lidia-vestido.glb` | 76.4 MB |
| `3D/lidia.glb` | 66.0 MB |
| `3D/odachi.glb` | 83.4 MB |
| `3D/punhal.glb` | 75.2 MB |
| `3D/rainha.glb` | 73.3 MB |
| `3D/soldado.glb` | 92.0 MB |

</details>

<details>
<summary><strong>Modelos 3D / Rigs (FBX)</strong> — 34 arquivos (303.0 MB)</summary>

| Arquivo | Tamanho |
|---|---|
| `3D/alice_mixamo.fbx` | 3.6 MB |
| `3D/Alice-T-Pose.fbx` | 208.1 KB |
| `3D/cavaleiro_mixamo.fbx` | 3.7 MB |
| `3D/cavaleiro-T-Pose.fbx` | 5.0 MB |
| `3D/chapeleiro_mixamo.fbx` | 4.0 MB |
| `3D/chapeleiro-T-Pose.fbx` | 5.7 MB |
| `3D/cheshire_mixamo.fbx` | 4.1 MB |
| `3D/coelho_mixamo.fbx` | 4.0 MB |
| `3D/Coelho-T-Pose.fbx` | 5.5 MB |
| `3D/coelho-vestido_mixamo.fbx` | 4.1 MB |
| `3D/coelho-vestidoT-Pose.fbx` | 5.7 MB |
| `3D/lagarta_mixamo.fbx` | 4.1 MB |
| `3D/lidia_mixamo.fbx` | 3.7 MB |
| `3D/Lidia-T-Pose.fbx` | 4.9 MB |
| `3D/lidia.fbx` | 111.1 MB |
| `3D/rainha_mixamo.fbx` | 4.2 MB |
| `3D/SK_Alice_Chapeleiro.fbx` | 9.9 MB |
| `3D/SK_Alice_Cheshire.fbx` | 9.9 MB |
| `3D/SK_Alice_Coelho.fbx` | 9.8 MB |
| `3D/SK_Alice_Lagarta.fbx` | 9.9 MB |
| `3D/SK_Alice_Rainha.fbx` | 9.8 MB |
| `3D/SK_Alice.fbx` | 3.8 MB |
| `3D/SK_AliceDress.fbx` | 9.8 MB |
| `3D/SK_CavaleiroDress.fbx` | 9.7 MB |
| `3D/SK_Coelho.fbx` | 4.2 MB |
| `3D/SK_Lidia.fbx` | 6.9 MB |
| `3D/SK_LidiaBoss.fbx` | 10.6 MB |
| `3D/SK_LidiaDress.fbx` | 9.8 MB |
| `3D/SK_RainhaDress.fbx` | 4.3 MB |
| `model/Alice_for_mixamo.fbx` | 1.5 MB |
| `model/Alice_Tpose.fbx` | 1.5 MB |
| `model/Eve.fbx` | 14.6 MB |
| `model/SK_Alice.fbx` | 1.6 MB |
| `model/Y Bot.fbx` | 1.9 MB |

</details>

<details>
<summary><strong>Texturas PBR</strong> — 114 arquivos (1.07 GB)</summary>

| Arquivo | Tamanho |
|---|---|
| `3D/alice_chapeleiro_tex/achap_base.png` | 16.5 MB |
| `3D/alice_chapeleiro_tex/achap_mr.png` | 10.3 MB |
| `3D/alice_chapeleiro_tex/achap_normal.png` | 9.1 MB |
| `3D/alice_cheshire_tex/acheshire_base.png` | 18.7 MB |
| `3D/alice_cheshire_tex/acheshire_mr.png` | 9.0 MB |
| `3D/alice_cheshire_tex/acheshire_normal.png` | 10.2 MB |
| `3D/alice_coelho_tex/acoelho_base.png` | 17.7 MB |
| `3D/alice_coelho_tex/acoelho_mr.png` | 11.2 MB |
| `3D/alice_coelho_tex/acoelho_normal.png` | 11.2 MB |
| `3D/alice_lagarta_tex/alagarta_base.png` | 19.0 MB |
| `3D/alice_lagarta_tex/alagarta_mr.png` | 13.0 MB |
| `3D/alice_lagarta_tex/alagarta_normal.png` | 9.9 MB |
| `3D/alice_mixamo.fbm/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/alice_mixamo.fbm/texture_pbr_20250901.png` | 13.2 MB |
| `3D/alice_rainha_tex/arainha_base.png` | 17.6 MB |
| `3D/alice_rainha_tex/arainha_mr.png` | 8.6 MB |
| `3D/alice_rainha_tex/arainha_normal.png` | 11.1 MB |
| `3D/alice_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.png` | 8.1 MB |
| `3D/alice_tex/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/alice_tex/texture_pbr_20250901.png` | 13.2 MB |
| `3D/alice_vestido_tex/adress_base.png` | 17.1 MB |
| `3D/alice_vestido_tex/adress_mr.png` | 11.3 MB |
| `3D/alice_vestido_tex/adress_normal.png` | 10.7 MB |
| `3D/cavaleiro_mixamo.fbm/texture_pbr_20250901_normal.004.png` | 5.3 MB |
| `3D/cavaleiro_mixamo.fbm/texture_pbr_20250901.004.png` | 11.6 MB |
| `3D/cavaleiro_tex/cav_base.png` | 11.6 MB |
| `3D/cavaleiro_tex/cav_mr.png` | 7.7 MB |
| `3D/cavaleiro_tex/cav_normal.png` | 5.3 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.001.png` | 8.6 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.002.png` | 8.3 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.003.png` | 7.7 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.png` | 8.1 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic.png.001.png` | 3.3 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_metallic.png.png` | 3.3 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.001.png` | 6.0 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.002.png` | 5.9 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.003.png` | 6.9 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.004.png` | 5.3 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.png.001.png` | 6.0 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_normal.png.png` | 6.0 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_roughness.png.001.png` | 4.2 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901_roughness.png.png` | 4.2 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.001.png` | 13.2 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.002.png` | 11.7 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.003.png` | 11.9 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.004.png` | 11.6 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.png` | 13.2 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.png.001.png` | 13.2 MB |
| `3D/cavaleiro_tex/texture_pbr_20250901.png.png` | 13.2 MB |
| `3D/cavaleiro_vestido_tex/cavdress_base.png` | 15.9 MB |
| `3D/cavaleiro_vestido_tex/cavdress_mr.png` | 10.8 MB |
| `3D/cavaleiro_vestido_tex/cavdress_normal.png` | 9.0 MB |
| `3D/chapeleiro_tex/chap_base.png` | 15.4 MB |
| `3D/chapeleiro_tex/chap_mr.png` | 11.6 MB |
| `3D/chapeleiro_tex/chap_normal.png` | 9.7 MB |
| `3D/cheshire_tex/chesh_base.png` | 21.9 MB |
| `3D/cheshire_tex/chesh_mr.png` | 10.1 MB |
| `3D/cheshire_tex/chesh_normal.png` | 17.5 MB |
| `3D/coelho_tex/coelho_base.png` | 11.9 MB |
| `3D/coelho_tex/coelho_mr.png` | 8.3 MB |
| `3D/coelho_tex/coelho_normal.png` | 6.9 MB |
| `3D/coelho_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.001.png` | 8.6 MB |
| `3D/coelho_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.002.png` | 8.3 MB |
| `3D/coelho_tex/texture_pbr_20250901_metallic_texture_pbr_20250901_roughness.png` | 8.1 MB |
| `3D/coelho_tex/texture_pbr_20250901_metallic.png.001.png` | 3.3 MB |
| `3D/coelho_tex/texture_pbr_20250901_metallic.png.png` | 3.3 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.001.png` | 6.0 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.002.png` | 5.9 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.003.png` | 6.9 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.png.001.png` | 6.0 MB |
| `3D/coelho_tex/texture_pbr_20250901_normal.png.png` | 6.0 MB |
| `3D/coelho_tex/texture_pbr_20250901_roughness.png.001.png` | 4.2 MB |
| `3D/coelho_tex/texture_pbr_20250901_roughness.png.png` | 4.2 MB |
| `3D/coelho_tex/texture_pbr_20250901.001.png` | 13.2 MB |
| `3D/coelho_tex/texture_pbr_20250901.002.png` | 11.7 MB |
| `3D/coelho_tex/texture_pbr_20250901.003.png` | 11.9 MB |
| `3D/coelho_tex/texture_pbr_20250901.png` | 13.2 MB |
| `3D/coelho_tex/texture_pbr_20250901.png.001.png` | 13.2 MB |
| `3D/coelho_tex/texture_pbr_20250901.png.png` | 13.2 MB |
| `3D/coelho_vestido_tex/coelhov_base.png` | 15.6 MB |
| `3D/coelho_vestido_tex/coelhov_mr.png` | 10.8 MB |
| `3D/coelho_vestido_tex/coelhov_normal.png` | 10.7 MB |
| `3D/lagarta_tex/lag_base.png` | 18.2 MB |
| `3D/lagarta_tex/lag_mr.png` | 7.7 MB |
| `3D/lagarta_tex/lag_normal.png` | 11.7 MB |
| `3D/lidia_boss_tex/lboss_base.png` | 17.6 MB |
| `3D/lidia_boss_tex/lboss_mr.png` | 7.9 MB |
| `3D/lidia_boss_tex/lboss_normal.png` | 9.8 MB |
| `3D/lidia_tex/texture_pbr_20250901_metallic.png` | 3.3 MB |
| `3D/lidia_tex/texture_pbr_20250901_normal.png` | 5.9 MB |
| `3D/lidia_tex/texture_pbr_20250901_roughness.png` | 4.2 MB |
| `3D/lidia_tex/texture_pbr_20250901.png` | 12.4 MB |
| `3D/lidia_vestido_tex/ldress_base.png` | 16.5 MB |
| `3D/lidia_vestido_tex/ldress_mr.png` | 7.9 MB |
| `3D/lidia_vestido_tex/ldress_normal.png` | 6.7 MB |
| `3D/rainha_tex/rainha_base.png` | 15.3 MB |
| `3D/rainha_tex/rainha_mr.png` | 7.4 MB |
| `3D/rainha_tex/rainha_normal.png` | 9.0 MB |
| `3D/SK_Alice.fbm/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/SK_Alice.fbm/texture_pbr_20250901.png` | 13.2 MB |
| `3D/SK_Lidia.fbm/texture_pbr_20250901_metallic.png` | 3.3 MB |
| `3D/SK_Lidia.fbm/texture_pbr_20250901_normal.png` | 6.0 MB |
| `3D/SK_Lidia.fbm/texture_pbr_20250901_roughness.png` | 4.2 MB |
| `3D/SK_Lidia.fbm/texture_pbr_20250901.png` | 13.2 MB |
| `3D/SK_RainhaDress.fbm/rainha_base.png` | 15.3 MB |
| `3D/SK_RainhaDress.fbm/rainha_normal.png` | 9.0 MB |
| `model/anims/Pro Sword and Shield Pack/Eve By J.Gonzales.fbm/SpacePirate_diffuse.png` | 4.6 MB |
| `model/anims/Pro Sword and Shield Pack/Eve By J.Gonzales.fbm/SpacePirate_normal.png` | 4.7 MB |
| `model/anims/Pro Sword and Shield Pack/Eve By J.Gonzales.fbm/SpacePirate_specular.png` | 4.1 MB |
| `model/Eve.fbm/SpacePirate_diffuse.png` | 4.6 MB |
| `model/Eve.fbm/SpacePirate_normal.png` | 4.7 MB |
| `model/Eve.fbm/SpacePirate_specular.png` | 4.1 MB |

</details>

<details>
<summary><strong>Animações (FBX)</strong> — 169 arquivos (116.7 MB)</summary>

| Arquivo | Tamanho |
|---|---|
| `model/anims/Brutal Assassination.fbx` | 990.0 KB |
| `model/anims/Convulsing.fbx` | 636.6 KB |
| `model/anims/Dual Weapon Combo.fbx` | 701.0 KB |
| `model/anims/Eve_Attack.fbx` | 1021.3 KB |
| `model/anims/Eve_Death.fbx` | 1021.0 KB |
| `model/anims/Eve_Dodge.fbx` | 1021.3 KB |
| `model/anims/Eve_Hit.fbx` | 1021.3 KB |
| `model/anims/Eve_Idle.fbx` | 1021.2 KB |
| `model/anims/Eve_Run.fbx` | 1021.2 KB |
| `model/anims/Eve_Skel.fbx` | 1021.1 KB |
| `model/anims/Eve_Walk.fbx` | 1021.5 KB |
| `model/anims/Fast Run.fbx` | 337.6 KB |
| `model/anims/Great Sword Pack/draw a great sword 1.fbx` | 398.6 KB |
| `model/anims/Great Sword Pack/draw a great sword 2.fbx` | 342.5 KB |
| `model/anims/Great Sword Pack/Eve By J.Gonzales.fbx` | 14.6 MB |
| `model/anims/Great Sword Pack/great sword 180 turn (2).fbx` | 308.2 KB |
| `model/anims/Great Sword Pack/great sword 180 turn.fbx` | 325.9 KB |
| `model/anims/Great Sword Pack/great sword attack.fbx` | 355.1 KB |
| `model/anims/Great Sword Pack/great sword blocking (2).fbx` | 335.7 KB |
| `model/anims/Great Sword Pack/great sword blocking (3).fbx` | 394.1 KB |
| `model/anims/Great Sword Pack/great sword blocking.fbx` | 397.8 KB |
| `model/anims/Great Sword Pack/great sword casting.fbx` | 555.7 KB |
| `model/anims/Great Sword Pack/great sword crouching (2).fbx` | 324.0 KB |
| `model/anims/Great Sword Pack/great sword crouching (3).fbx` | 382.5 KB |
| `model/anims/Great Sword Pack/great sword crouching (4).fbx` | 363.4 KB |
| `model/anims/Great Sword Pack/great sword crouching (5).fbx` | 358.8 KB |
| `model/anims/Great Sword Pack/great sword crouching (6).fbx` | 380.5 KB |
| `model/anims/Great Sword Pack/great sword crouching.fbx` | 324.5 KB |
| `model/anims/Great Sword Pack/great sword high spin attack.fbx` | 453.8 KB |
| `model/anims/Great Sword Pack/great sword idle (2).fbx` | 489.2 KB |
| `model/anims/Great Sword Pack/great sword idle (3).fbx` | 543.8 KB |
| `model/anims/Great Sword Pack/great sword idle (4).fbx` | 560.7 KB |
| `model/anims/Great Sword Pack/great sword idle (5).fbx` | 708.9 KB |
| `model/anims/Great Sword Pack/great sword idle.fbx` | 391.7 KB |
| `model/anims/Great Sword Pack/great sword impact (2).fbx` | 351.9 KB |
| `model/anims/Great Sword Pack/great sword impact (3).fbx` | 374.0 KB |
| `model/anims/Great Sword Pack/great sword impact (4).fbx` | 314.6 KB |
| `model/anims/Great Sword Pack/great sword impact (5).fbx` | 335.0 KB |
| `model/anims/Great Sword Pack/great sword impact.fbx` | 330.5 KB |
| `model/anims/Great Sword Pack/great sword jump (2).fbx` | 333.0 KB |
| `model/anims/Great Sword Pack/great sword jump attack.fbx` | 483.6 KB |
| `model/anims/Great Sword Pack/great sword jump.fbx` | 314.2 KB |
| `model/anims/Great Sword Pack/great sword kick (2).fbx` | 405.8 KB |
| `model/anims/Great Sword Pack/great sword kick.fbx` | 379.1 KB |
| `model/anims/Great Sword Pack/great sword power up.fbx` | 533.0 KB |
| `model/anims/Great Sword Pack/great sword run (2).fbx` | 310.9 KB |
| `model/anims/Great Sword Pack/great sword run.fbx` | 320.6 KB |
| `model/anims/Great Sword Pack/great sword slash (2).fbx` | 541.3 KB |
| `model/anims/Great Sword Pack/great sword slash (3).fbx` | 407.5 KB |
| `model/anims/Great Sword Pack/great sword slash (4).fbx` | 415.9 KB |
| `model/anims/Great Sword Pack/great sword slash (5).fbx` | 374.1 KB |
| `model/anims/Great Sword Pack/great sword slash.fbx` | 368.8 KB |
| `model/anims/Great Sword Pack/great sword slide attack.fbx` | 478.1 KB |
| `model/anims/Great Sword Pack/great sword strafe (2).fbx` | 350.0 KB |
| `model/anims/Great Sword Pack/great sword strafe (3).fbx` | 308.2 KB |
| `model/anims/Great Sword Pack/great sword strafe (4).fbx` | 313.5 KB |
| `model/anims/Great Sword Pack/great sword strafe.fbx` | 346.4 KB |
| `model/anims/Great Sword Pack/great sword turn (2).fbx` | 326.9 KB |
| `model/anims/Great Sword Pack/great sword turn.fbx` | 319.8 KB |
| `model/anims/Great Sword Pack/great sword walk (2).fbx` | 361.4 KB |
| `model/anims/Great Sword Pack/great sword walk.fbx` | 365.8 KB |
| `model/anims/Great Sword Pack/spell cast.fbx` | 373.0 KB |
| `model/anims/Great Sword Pack/two handed sword death (2).fbx` | 503.7 KB |
| `model/anims/Great Sword Pack/two handed sword death.fbx` | 466.0 KB |
| `model/anims/Injured Run.fbx` | 386.0 KB |
| `model/anims/One Hand Sword Combo.fbx` | 864.2 KB |
| `model/anims/Pro Longbow Pack/Eve By J.Gonzales.fbx` | 14.6 MB |
| `model/anims/Pro Longbow Pack/fall a land to run forward.fbx` | 358.3 KB |
| `model/anims/Pro Longbow Pack/fall a land to standing idle 01.fbx` | 343.6 KB |
| `model/anims/Pro Longbow Pack/fall a loop.fbx` | 346.1 KB |
| `model/anims/Pro Longbow Pack/standing aim overdraw.fbx` | 499.1 KB |
| `model/anims/Pro Longbow Pack/standing aim recoil.fbx` | 324.2 KB |
| `model/anims/Pro Longbow Pack/standing aim walk back.fbx` | 372.1 KB |
| `model/anims/Pro Longbow Pack/standing aim walk forward.fbx` | 351.0 KB |
| `model/anims/Pro Longbow Pack/standing aim walk left.fbx` | 352.7 KB |
| `model/anims/Pro Longbow Pack/standing aim walk right.fbx` | 360.6 KB |
| `model/anims/Pro Longbow Pack/standing block.fbx` | 431.1 KB |
| `model/anims/Pro Longbow Pack/standing death backward 01.fbx` | 541.1 KB |
| `model/anims/Pro Longbow Pack/standing death forward 01.fbx` | 544.8 KB |
| `model/anims/Pro Longbow Pack/standing disarm bow.fbx` | 374.8 KB |
| `model/anims/Pro Longbow Pack/standing dive forward.fbx` | 414.7 KB |
| `model/anims/Pro Longbow Pack/standing dodge backward.fbx` | 396.5 KB |
| `model/anims/Pro Longbow Pack/standing dodge forward.fbx` | 355.1 KB |
| `model/anims/Pro Longbow Pack/standing dodge left.fbx` | 352.0 KB |
| `model/anims/Pro Longbow Pack/standing dodge right.fbx` | 349.3 KB |
| `model/anims/Pro Longbow Pack/standing draw arrow.fbx` | 352.5 KB |
| `model/anims/Pro Longbow Pack/standing equip bow.fbx` | 359.3 KB |
| `model/anims/Pro Longbow Pack/standing idle 01.fbx` | 558.4 KB |
| `model/anims/Pro Longbow Pack/standing idle 02 looking.fbx` | 498.3 KB |
| `model/anims/Pro Longbow Pack/standing idle 03 examine.fbx` | 559.3 KB |
| `model/anims/Pro Longbow Pack/standing melee kick.fbx` | 394.9 KB |
| `model/anims/Pro Longbow Pack/standing melee punch.fbx` | 351.6 KB |
| `model/anims/Pro Longbow Pack/standing react small from front.fbx` | 371.4 KB |
| `model/anims/Pro Longbow Pack/standing react small from headshot.fbx` | 343.3 KB |
| `model/anims/Pro Longbow Pack/standing run back.fbx` | 324.8 KB |
| `model/anims/Pro Longbow Pack/standing run forward stop.fbx` | 343.0 KB |
| `model/anims/Pro Longbow Pack/standing run forward.fbx` | 341.7 KB |
| `model/anims/Pro Longbow Pack/standing run left.fbx` | 324.8 KB |
| `model/anims/Pro Longbow Pack/standing run right.fbx` | 332.8 KB |
| `model/anims/Pro Longbow Pack/standing turn 90 left.fbx` | 373.8 KB |
| `model/anims/Pro Longbow Pack/standing turn 90 right.fbx` | 357.9 KB |
| `model/anims/Pro Longbow Pack/standing walk back.fbx` | 380.3 KB |
| `model/anims/Pro Longbow Pack/standing walk forward.fbx` | 359.6 KB |
| `model/anims/Pro Longbow Pack/standing walk left.fbx` | 363.3 KB |
| `model/anims/Pro Longbow Pack/standing walk right.fbx` | 363.3 KB |
| `model/anims/Pro Longbow Pack/unarmed idle 01.fbx` | 588.1 KB |
| `model/anims/Pro Sword and Shield Pack/draw sword 1.fbx` | 419.1 KB |
| `model/anims/Pro Sword and Shield Pack/draw sword 2.fbx` | 330.3 KB |
| `model/anims/Pro Sword and Shield Pack/Eve By J.Gonzales.fbx` | 14.6 MB |
| `model/anims/Pro Sword and Shield Pack/sheath sword 1.fbx` | 369.7 KB |
| `model/anims/Pro Sword and Shield Pack/sheath sword 2.fbx` | 339.7 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield 180 turn (2).fbx` | 328.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield 180 turn.fbx` | 325.9 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield attack (2).fbx` | 379.3 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield attack (3).fbx` | 419.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield attack (4).fbx` | 341.4 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield attack.fbx` | 472.3 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield block (2).fbx` | 316.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield block idle.fbx` | 370.7 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield block.fbx` | 308.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield casting (2).fbx` | 345.6 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield casting.fbx` | 472.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouch block (2).fbx` | 321.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouch block idle.fbx` | 371.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouch block.fbx` | 404.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouch idle.fbx` | 416.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouch.fbx` | 311.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouching (2).fbx` | 328.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouching (3).fbx` | 316.7 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield crouching.fbx` | 375.6 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield death (2).fbx` | 536.6 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield death.fbx` | 429.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield idle (2).fbx` | 667.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield idle (3).fbx` | 662.9 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield idle (4).fbx` | 447.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield idle.fbx` | 506.7 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield impact (2).fbx` | 335.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield impact (3).fbx` | 319.1 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield impact.fbx` | 339.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield jump (2).fbx` | 351.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield jump.fbx` | 328.5 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield kick.fbx` | 372.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield power up.fbx` | 432.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield run (2).fbx` | 308.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield run.fbx` | 318.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield slash (2).fbx` | 584.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield slash (3).fbx` | 389.6 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield slash (4).fbx` | 487.7 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield slash (5).fbx` | 368.4 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield slash.fbx` | 380.9 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield strafe (2).fbx` | 359.8 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield strafe (3).fbx` | 328.6 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield strafe (4).fbx` | 317.3 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield strafe.fbx` | 348.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield turn (2).fbx` | 333.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield turn.fbx` | 333.2 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield walk (2).fbx` | 359.0 KB |
| `model/anims/Pro Sword and Shield Pack/sword and shield walk.fbx` | 357.9 KB |
| `model/anims/Slow Run.fbx` | 414.6 KB |
| `model/anims/Sprinting Forward Roll.fbx` | 489.7 KB |
| `model/anims/Stable Sword Outward Slash.fbx` | 573.3 KB |
| `model/anims/Standing Idle.fbx` | 1.0 MB |
| `model/anims/Standing Melee Attack Backhand.fbx` | 716.9 KB |
| `model/anims/Standing Melee Attack Downward.fbx` | 593.7 KB |
| `model/anims/Standing Melee Attack Horizontal.fbx` | 610.1 KB |
| `model/anims/Standing Melee Combo Attack Ver. 2.fbx` | 866.9 KB |
| `model/anims/Standing Melee Combo Attack Ver. 3.fbx` | 662.6 KB |
| `model/anims/Standing React Death Forward.fbx` | 882.2 KB |
| `model/anims/Walking.fbx` | 486.5 KB |

</details>

<details>
<summary><strong>Documentos (roteiro/lore)</strong> — 2 arquivos (999.2 KB)</summary>

| Arquivo | Tamanho |
|---|---|
| `roteiro_apenas_historia.txt` | 158.0 KB |
| `roteiro.txt` | 841.1 KB |

</details>

<details>
<summary><strong>Imagens diversas</strong> — 8 arquivos (2.4 MB)</summary>

| Arquivo | Tamanho |
|---|---|
| `3D/alice.jpg` | 44.0 KB |
| `3D/cavaleiro.jpg` | 30.7 KB |
| `3D/chapeleiro.jpg` | 33.5 KB |
| `3D/coelho.jpg` | 35.7 KB |
| `3D/lidia.jpg` | 41.6 KB |
| `3D/rainha.jpg` | 32.7 KB |
| `logo-gg.png` | 2.0 MB |
| `wolrd-map.jpg` | 260.7 KB |

</details>
<!-- AUTO:REFERENCES:END -->
