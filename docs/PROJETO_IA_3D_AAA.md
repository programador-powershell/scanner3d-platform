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

## 3. O Núcleo Anatômico e Colisão Física Real

O rig e a simulação física **não operam sobre uma casca vazia**. O sistema usa a **malha anatômica muscular real interna** para calcular colisões físicas complexas a cada quadro (*frame-by-frame muscle-cloth collision*), eliminando clipping (roupa atravessando a carne).

```
[ Estrutura Óssea ] ──► [ Sistema de Músculos (HIT / Chaos Flesh) ] ──► [ Colisão Física Síncrona ] ──► [ Malha de Tecido Real ]
```

1. **Esqueleto nativo paramétrico:** detecta pose e proporções em 2D e instancia o esqueleto baseado no template **ATLAS / MHR** (76 atributos esqueléticos independentes — ver 7.6). Serve de "cabide" para as roupas.
2. **Camada muscular tetraédrica:** usando **HIT** + **Chaos Flesh**, os volumes musculares reais reagem dinamicamente a cada quadro e servem de **barreira física** (rígida e elástica) para o caimento do tecido — a saia/vestido lê os limites do colisor muscular antes de drapear.

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
- A saia se move com as pernas mantendo volume flutuante, com suporte nativo a simulação de **vento e gravidade** (o tecido sobe/infla na queda como se houvesse vento real agindo sobre ele).

---

## 7. Stack de Modelos Open-Weights v2 (auditado em jun/2026)

> **Auditoria adversarial (jun/2026):** o stack v1 (FLUX.1-LoRA → Unique3D/SF3D → CraftsMan/MeshXL) foi reprovado em todos os estágios. Motivos verificados: (a) LoRA gera "personagem parecido" (~85–92% de consistência), não a SUA imagem — alucina costas e detalhes; (b) o paper do Unique3D confirma que o treino **excluiu** superfícies finas/abertas — roupa vira casca fechada inflada, exatamente o defeito do Meshy/Hunyuan; (c) nenhum modelo open de 2026 gera retopologia quad AAA; (d) "SMPL-X-like" tem 72 DoF falsos, não é esqueleto biomecânico; (e) faltavam por completo os estágios de cabelo fio a fio e rosto animável.

> **Verdade técnica do "pixel a pixel":** imagem 2D é projeção — costas, interior da saia e anatomia interna **não estão no sinal**. Todo sistema preenche o invisível com priors. A diferença real desta plataforma: (1) **fidelidade mensurável no visível** via loop de render-loss contra a foto original (seção 7.4); (2) **qualidade do prior no invisível** — anatômico (SKEL), físico (costura+drape), semântico (camadas).

### Tabela de substituições v1 → v2

| Estágio v1 | Problema verificado | Estágio v2 |
|---|---|---|
| FLUX.1-LoRA turnaround | Amostra distribuição aprendida, não reconstrói a foto | **PSHuman / MagicMan** (condicionados na foto) + gate métrico |
| PSHuman/MagicMan como reconstrução (v2) | Sem treino liberado; sem PBR separado; sem refino geométrico | **Hunyuan3D 2.1** (v3): treino liberado p/ fine-tune DPO, geometria+textura PBR separadas; PSHuman/MagicMan viram geradores de vistas opcionais |
| Unique3D por camada de roupa | Treino excluiu superfícies finas → casca inflada | **Sewing patterns** (ChatGarment/AIpparel → GarmentCode → drape) |
| Unique3D/SF3D geral | Superado por 2 gerações (2024 vs 2026) | **TRELLIS.2-4B** (rígidos) + **PSHuman/LHM++** (humano) |
| CraftsMan / MeshXL | Sem quad AAA; tri ~11–30k faces | High-poly + retopo clássico / registro em template de topologia fixa |
| Esqueleto "SMPL-X-like" | 72 DoF falsos, não-biomecânico | **SKEL** (46 DoF reais) via HSMR + **HIT** (tecidos volumétricos) |
| (sem estágio de cabelo) | Malha = capacete sólido | **DiffLocks** → ~100K strands → Alembic → UE5 Groom |
| (sem estágio facial) | Sem loops, sem boca interna, sem blendshapes | **FLAME** fitting → NRICP em **ICT-FaceKit** → 52 ARKit + wrinkle maps |

### 7.1 Reconstrução Inicial — Hunyuan3D 2.1 (v3; multi-view vira opcional)

- **Hunyuan3D 2.1** (Tencent, open-source com **treino liberado**): reconstrução inicial e refino geométrico. Gera **geometria e textura em modelos separados**, com PBR físico (metallic/SSS) pronto para Blender/UE5. Superioridade prática sobre TripoSR/single-shell para personagens complexos + fine-tune direto com o dataset DPO da plataforma. `Imagem → Hunyuan3D → Mesh → Texture`.
- **PSHuman** (CVPR 2025) e **MagicMan** (AAAI 2025) — rebaixados a **geradores opcionais de vistas humanas** (6–20 vistas condicionadas em SMPL-X, preservam identidade facial) que alimentam o Hunyuan em modo multi-view quando o rosto exigir fidelidade extra.
- **Enhancers** (nunca fonte de verdade): FLUX.2-dev (multi-reference, até 10 imagens), Qwen-Image-Edit (NVS preservando textura). LoRA via Kohya_ss permanece **só para estilo**, nunca para identidade.

### 7.2 Gate Métrico de Identidade (toda vista passa ou regera)

- **ArcFace cosine** no crop do rosto (render vs foto original) + **LPIPS** no corpo + IoU de silhueta.
- Vista reprovada nunca passa adiante — é regerada. Mesma filosofia do gate RTMW-133 keypoints já validado no projeto Alice.

### 7.3 Trilhos de Reconstrução por Tipo de Camada

Cada camada fatiada pelo Florence-2 segue o trilho do seu material — não existe motor único:

| Camada | Motor (open, jun/2026) | Saída |
|---|---|---|
| Corpo / anatomia **INSTANCIADA** (v4) | **SKEL** (esqueleto biomecânico 46 DoF, ancorado ao SMPL-X) + **TailorMe** (template volumétrico **instanciado**: pele+músculo+esqueleto, M/F) + **NDG** (Neural Deformation Gradients, CGF/Eurographics 2026 — deforma osso+músculo+pele com a pose, robusto a inversão/volume). **Z-Anatomy** = overlay de veias/nervos por cima. Fallback Blender: MuSkeMo / X-Muscle | Anatomia **instanciada, não inferida** — malhas reais registradas, editáveis |
| Rosto / caretas | **Pixel3DMM / VGGTFace** → parâmetros **FLAME** → registro NRICP em basemesh **ICT-FaceKit** (MIT) → **52 blendshapes ARKit** → wrinkle maps via **DECA** | Cabeça animável FACS, topologia fixa |
| Roupa de pano (v4) | **ChatGarment** (lê N imagens das etapas) → **GarmentCode** (sewing pattern) → **NvidiaWarp-GarmentCode** (costura/panels, já é Warp) → solver **Newton 1.0 (VBD)** com self-collision multicamada + colisor do corpo. **TailorNet aposentado** (rede de ~20 MLPs, overfit, sem colisão multicamada) | Vestido lolita multicamada (corset→saia→avental→renda) drapeado fisicamente |
| Rígidos (armadura, fivelas, joias, botas) | **TRELLIS.2** (MIT) condicionado multi-image | Malha PBR de alta fidelidade |
| Cabelo fio a fio | **DiffLocks** (1 foto → ~100K strands) → Alembic → **Hair Curves** + **Geometry Nodes** (pelos) → UE5 Groom | Strands reais, não "capacete" |

> **Ressalva de licença (v4, due diligence p/ produto comercial):** SKEL/OSSO/HIT/SMPL-X são **research-only MPI** — uso comercial exige contrato (ps-licensing@tue.mpg.de / Meshcapade). Z-Anatomy é **CC-BY-SA 4.0** (comercial OK, mas ShareAlike **viral** contamina derivados). TailorMe/NDG: verificar licença do template anatômico antes de shippar. Para AAA comercial, orçar licenciamento MPI; Z-Anatomy só como overlay respeitando ShareAlike.

- **Por que instanciar > inferir (tese do diretor confirmada):** **HIT** (CVPR 2024) é um campo **implícito** — prediz classe de tecido por ponto, malha só via marching cubes. Não dá controle artístico, normais/oclusão limpas nem edição. A anatomia AAA deve ser **malha instanciada** (TailorMe) deformada com a pose (NDG), não um campo amostrável.
- **Veias e poros = textura, não geometria:** displacement micro (<0,1 mm) + albedo + SSS. Só veia saliente que muda silhueta vira relevo.
- **Retopologia (v5): edge flow específico por tipo de superfície.**
  - **Orgânico (corpo/rosto/acessórios)** → high-poly + **QRemeshify** (QuadWild+Bi-MDF) ou **AutoRemesher** (GPL-3.0). Bom para forma orgânica geral.
  - **Roupa → retopo guiado pela costura, NÃO genérico.** QRemeshify/AutoRemesher ignoram as linhas de costura e dobras → durante a animação do esqueleto a malha **rasga / estica (skin-stretching)** e gera artefatos. Correção: o **GarmentCode já fornece o edge flow** — cada painel do sewing pattern (ChatGarment→GarmentCode) é uma **grade quad** com arestas **alinhadas às costuras e às dobras principais**. O retopo da roupa deve **preservar os loops dos painéis** (1 ilha UV por painel, arestas nas costuras), não passar pelo remesher orgânico. Dobras principais viram edge loops dedicados; QuadWild só refina dentro do painel respeitando as bordas de costura como hard constraints.

### 7.3.1 Material Intelligence — os mapas que fazem o realismo (v4/v5)

> Tese do diretor confirmada: **"Stellar Blade parece realista mais pelos materiais do que pela malha."** Conjunto AAA completo: **base color · normal · roughness · metallic · AO · height · SSS(thickness) · micro-normal · cavity(micro-AO) · anisotropy + tangent**.

Verdade honesta (auditada jun/2026): **nenhum modelo open gera todos os mapas**. Divisão real:
- **Os 4 que a IA cobre** — **Hunyuan3D 2.1** já entrega albedo + metallic + roughness + normal (não duplicar). Delight de **uma foto** de referência: **RGB↔X** (SIGGRAPH 2024). Repintar SVBRDF 3D-aware: **Material Anything** (CVPR 2025, **MIT**) — só se trocar o paint do Hunyuan.
- **Os que NÃO são IA** (bake geométrico + shader, não generativo):
  - **AO + Height + Thickness(p/ SSS)** → bake Cycles/Blender na malha (exato, grátis).
  - **Cavity / Micro-AO (v5)** → derivado do **normal de alta frequência** (high-pass do normal map → escurece poros profundos da pele e ranhuras do tecido, AO dinâmico de micro-relevo). Bake no Blender ou nó de cavity no material UE5.
  - **Anisotropy + Tangent (v5)** → **obrigatório para o cabelo** DiffLocks/Groom: o brilho precisa correr **ao longo do fio** (efeito *shimmer*). O **tangent map** vem da **direção das curvas de cabelo** (Hair Curves → tangente por strand → flow map); a anisotropia controla a forma do realce especular. Sem isso o cabelo fica com brilho plástico isotrópico. Aplica-se também a tecidos escovados (cetim, seda) e metais escovados dos acessórios.
  - **Micro-normal** → blend de detail-normal tileável do **MatSynth** (4000+ materiais 4K, **CC0/CC-BY**).
  - **SSS** → subsurface profile do UE5 alimentado pelo thickness bake.
- Só-pesquisa, evitar no produto: **IntrinsiX** (CC-BY-NC-SA). **VideoMatGen** (NVIDIA, mar/2026) modela height junto mas sem pesos públicos — monitorar.

### 7.3.2 UDIM — resolução por região (close-up de rosto sem perder nitidez)

Guardar rosto+corpo+roupa+acessórios num único 8K perde nitidez no **close-up do rosto**. Padrão de estúdio AAA: **UDIM** separa a textura em quadrantes por região, cada um com sua densidade de píxeis:

| Tile UDIM | Região | Densidade |
|---|---|---|
| **1001** | Rosto / cabeça | máxima (4K/8K — close-up) |
| **1002** | Corpo / pele | alta |
| **1003** | Roupas | média-alta |
| **1004** | Acessórios / cabelo cards | média |

> **Atenção dura (constraint real do formato):** **glTF/GLB NÃO suporta UDIM** — a spec exige UV em [0,1] e 1 textura por slot. Por isso o pipeline trata UDIM em **duas camadas**:
> - **Autoria/Blender/loop de refino**: trabalha em **UDIM real** (cada região no seu tile, densidade independente) — é onde a fidelidade é ganha.
> - **Export para engine**: ao exportar GLB, **divide por material/sub-malha** — cada região vira um **material separado** com sua própria textura (rosto 4K, corpo 2K, roupa 2K…). Para manter UDIM nativo, exportar **USD ou FBX** (UE5/Unity leem UDIM por material). O endpoint `/api/jobs/:id/artifact/:f` serve as texturas por tile (`character_1001.png`, `_1002`, …) e o builder Blender atribui um material por região.

### 7.4 Loop de Fechamento — Differentiable Rendering (v4: Mitsuba 3 + SSS)

**É este loop — não o gerador — que entrega o "pixel a pixel".** Expandido conforme o diretor: `Render → comparação pixel → gradiente → atualiza MALHA → atualiza TEXTURA → render`, até convergir.

> **Upgrade v4:** o `nvdiffrast` puro (rasterizador) não modela **SSS de pele**. Stack open superior verificada: **Mitsuba 3 + Dr.Jit** (BSD-3, comercial OK) como renderizador inverso path-traced, com o integrador **"Practical Inverse Rendering of Textured and Translucent Appearance"** (Google/EPFL, SIGGRAPH 2025, **Apache-2.0**) para refinar albedo+normal+**SSS** da pele contra a foto, e **Continuous Remeshing** (MIT) como remeshing dentro do loop de geometria. O `nvdiffrast` continua como caminho rápido/rasterização; Mitsuba entra no refino final de pele translúcida.

Snippet base (nvdiffrast — caminho rápido; o refino de SSS migra para Mitsuba 3):

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

**Passo de otimização AAA (v5)** — incorpora a trava de identidade facial (ArcFace) e a regularização Laplaciana da malha, conforme o diretor:

```python
# Extensão do método otimizar_passo (loop de fechamento AAA):
def otimizar_passo_aaa(self, foto_original, crop_rosto_original, mvp_matrix, optimizer):
    optimizer.zero_grad()

    # 1. Renderização diferenciada do modelo atual (4K)
    render_atual, coordenadas_raster = self.renderizar_modelo(mvp_matrix, resolucao=4096)

    # 2. Perda de cor e perceptual geral (Corpo e Roupa)
    loss_pixel = F.mse_loss(render_atual, foto_original)
    loss_perceptual = self.lpips_metric(render_atual, foto_original).mean()

    # 3. Trava de Identidade Facial (garante o nível Stellar Blade)
    crop_rosto_render = extrair_crop_rosto(render_atual, coordenadas_raster)
    loss_identidade = 1.0 - self.arcface_model(crop_rosto_render, crop_rosto_original)

    # 4. Regularização Laplaciana (impede que os vértices rasguem a malha anatômica)
    loss_mesh_reg = regularization_laplacian(self.mesh_base, self.vertices_offsets)

    # Peso AAA balanceado
    loss_total = loss_pixel + (0.7 * loss_perceptual) + (1.2 * loss_identidade) + (0.1 * loss_mesh_reg)

    loss_total.backward()
    optimizer.step()
    return loss_total.item()
```

- **Identidade (peso 1.2):** ArcFace cosine entre o crop do rosto renderizado e o da foto — domina a otimização (o rosto é o que o olho julga primeiro). É o que separa "parecido" de **a mesma pessoa**.
- **Regularização Laplaciana (peso 0.1):** penaliza variação alta dos `vertices_offsets` — os vértices se movem para casar a foto **sem rasgar** a topologia base SKEL/FLAME nem inverter triângulos.
- **Coarse-to-fine:** 512 → 1024 → 2048 → 4096; geometria congela nas resoluções altas (só textura/SSS refina). O refino de pele translúcida migra para o **Mitsuba 3** path-traced (integrador SSS), o `nvdiffrast` faz o passo rápido.

### 7.5 Sequência Unificada v3 (revisão do diretor, jun/2026)

> **Troca efetuada:** **Hunyuan3D 2.1** assume reconstrução inicial + refino geométrico — open-source, **treino liberado** (fine-tune direto com o nosso dataset DPO), geometria e textura **PBR geradas separadamente**, saída pronta para Blender/UE5. **PSHuman/MagicMan rebaixados** a geradores opcionais de vistas humanas alimentando o Hunyuan (multi-view) quando a identidade facial exigir — hibridização que a auditoria já recomendava.
>
> Atenções de produção: VRAM **10 GB (shape) / 21 GB (texture)** — shape roda local; texture vai para Colab A100 ou modo low-VRAM. Licença Tencent Community tem **exclusões regionais (UE/UK/Coreia)** — isolar o componente se a plataforma for global. Correção de nome: a "Qwen 3.6 VL" citada não existe — o pré-scan usa a **Qwen2.5-VL fine-tunada** (seção 7.8).

```
FOTO (turnaround, N imagens)
   │
   ▼
[ Qwen2.5-VL fine-tunada ]      pré-scan: identidade, medidas, materiais
   │
   ▼
[ Florence-2 fine-tuned ]       segmentação semântica em camadas
   │
   ├─ Reconstrução inicial → HUNYUAN3D 2.1 + SMPL-X + FLAME + multi-view (PSHuman/MagicMan opc.)
   │
   ├─ Corpo / ANATOMIA    → SKEL (rig biomec.) + TailorMe (instanciado: osso+músculo+pele)
   │  (instanciada,          + NDG (deforma com a pose) · Z-Anatomy = overlay veias/nervos
   │   não inferida)         A MUSCULATURA É INSTANCIADA, não um campo implícito (HIT)
   │
   ├─ Roupa       → ChatGarment (N imgs) → GarmentCode → NvidiaWarp-GarmentCode → Newton 1.0 (VBD)
   │                (TailorNet APOSENTADO — não cobre roupa multicamada complexa)
   │
   ├─ Cabelo      → DiffLocks (~100K strands) + Hair Curves + Geometry Nodes
   └─ Acessórios  → TRELLIS.2 (MIT)
   │
   ▼
[ Hunyuan3D 2.1 ]               refino geométrico + textura PBR (geometria/textura separadas)
   │
   ▼
[ MATERIAL INTELLIGENCE ]       albedo/normal/rough/metallic (Hunyuan/RGB↔X/MaterialAnything)
   │                            + AO/height/thickness (bake Cycles) + micro-normal (MatSynth CC0)
   ▼                            + SSS (subsurface profile). "Realismo vem do material" (Stellar Blade)
[ Blender ]
   ├─ Geometry Nodes            (GarmentGeo: subdiv+smooth; pelos corporais)
   ├─ Auto Retopo               (QRemeshify / AutoRemesher — quad limpo)
   ├─ PBR 8K                    (texturas CC0 + bake Hunyuan)
   ├─ Rig Humano                (SKEL / MPFB2 default)
   └─ ARKit 52                  (blendshapes via FLAME → ICT-FaceKit)
   │
   ▼
[ GATE: ArcFace + LPIPS + silhueta ]  reprovou → VLM sugere ajuste → regera
   │
   ▼
[ LOOP DIFERENCIÁVEL ]  nvdiffrast (rápido) + Mitsuba 3/Dr.Jit (refino SSS de pele,
   │   render→pixel→gradiente→ atualiza MALHA+TEXTURA →render até convergir) ← "pixel a pixel"
   ▼
[ .glb modular PBR + rig ] ──► UE5 (Groom + LiveLink + ARKit 52)
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

### 7.7 Stack Blender-nativa (humano 100% real, do osso ao pelo)

> Requisito do diretor: **o gerador entrega humano em tudo** — sem cilindros, sem stick-figure, sem placeholder. Cada portão usa um motor Blender-nativo open que produz geometria humana de verdade, e a LLM Vision (7.8) avalia automaticamente cada saída.

```
[Foto] → [Vision: identidade + medidas] → MPFB2 base → Z-Anatomy interno
   │                                            │
   │                                            ├─ Pele (8K CC0 + SSS)
   │                                            ├─ Gordura
   │                                            ├─ Músculos
   │                                            ├─ Ossos
   │                                            ├─ Veias
   │                                            ├─ Nervos
   │                                            └─ Órgãos
   │                                            │
   └─► Hair Curves (cabelo) + Geometry Nodes (pelos corporais)
```

| Portão | Motor open (Blender-nativo) | Saída |
|---|---|---|
| Esqueleto | **Z-Anatomy** (ossos reais: crânio + 24 vértebras + 12 pares de costelas + pélvis + ossos longos pareados) | Malha óssea anatômica navegável |
| Veias | **Z-Anatomy** (camada vascular) + texturas SSS 8K | Rede venosa visível com retroiluminação |
| Músculos | **Z-Anatomy** (camada muscular nomeada) + **MPFB2** rig + Chaos Flesh | Volumes musculares deformáveis |
| Tecido | **MPFB2** body como colisor + GarmentCode + drape Warp/Newton | Roupa drapeada no corpo MPFB2 |
| Pele | **MPFB2** skin + texturas **8K CC0** (Texturing.xyz CC0 / FaceScape / FFHQ-UV) + SSS | PBR com poros reais |
| Unhas | Template **MPFB2** (já inclui dedos) + material PBR | Cutícula/lúnula |
| Rosto | **MPFB2** face (modelo paramétrico) + 52 ARKit blendshapes | Cabeça animável FACS |
| Olhos | Material córnea/íris **MPFB2** + shader refração | Globos com umidade lacrimal |
| Cabelo | **Hair Curves do Blender** (DiffLocks como prior) + **Geometry Nodes** (sobrancelhas, pelos corporais, barba) | Strands reais + pelo corporal |

**Ferramentas plugadas:**
- **MakeHuman / MPFB2** (`makehumancommunity/mpfb2`, GPLv3) — gerador humano paramétrico open. Saída em malha quad limpa com rig (`Default`, `Game Engine`, `Rigify`), UVs, pele base, dentes, língua, cabelo procedural. **Substitui** o esqueleto procedural cilíndrico — entrega humano completo do nascimento.
- **Z-Anatomy** (CC-BY-4.0) — addon Blender com **anatomia humana real e nomeada**: 4500+ estruturas (ossos individuais, músculos, nervos, veias, órgãos). Camadas plugáveis nos portões 1/2/3.
- **Hair Curves nativo do Blender** (4.x) — sistema de strands com física, profissional.
- **Geometry Nodes** — distribuição procedural de pelos finos (corpo inteiro, sobrancelhas, cílios).
- **Texturas 8K CC0** — bancos livres (Polyhaven, AmbientCG, Texturing.xyz CC0 set, FFHQ-UV) para difuso/normal/roughness/displacement de pele.
- **SMPL-X** (`vchoutas/smplx`, pip) — corpo paramétrico betas/pose como prior numérico; `python/body_smplx.py` traduz os params do job (altura→β0, quadril→β1) e exporta `body_smplx.obj` (requer modelos MPI baixados).
- **TailorNet** (`chaitanya100100/TailorNet`) — roupa deformada por **pose+shape+style** com rugas previstas pela rede; `python/cloth_tailornet.py` gera `garments/cloth.obj`, que o portão Tecido importa e refina. Complementa o ChatGarment: este dá o *pattern* (o quê), o TailorNet dá a *deformação pose-dependente* (como veste).
- **Geometry Nodes "GarmentGeo"** — node tree (Subdivision Surface → Shade Smooth) aplicada a cada painel de roupa e ao cloth do TailorNet no `build_stage.py` (verificado no Blender 5.1 headless).

**Visualização por camada anatômica** (radial selector no viewer GLB): Pele · Gordura · Músculos · Ossos · Veias · Nervos · Órgãos.

### 7.8 LLM Vision no Loop — fim do "vou ter que pedir alteração toda hora"

A LLM do hub não é só símbolo — ela é uma **VLM (Vision-Language Model)** que avalia automaticamente cada portão antes de pedir aprovação humana. O usuário só vê o preview se a VLM já considerou correto.

```
[Portão gera preview 3D] ──► [VLM avalia: bate com a foto? humano? anatomicamente correto?]
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
   reprovação automática             passa para revisão humana
   (regenera com correção)
```

**Modelo escolhido (treino local, RTX 4060 8GB):** **Qwen2.5-VL-7B-Instruct 4-bit via Unsloth** — substitui o Qwen3-VL como alvo de treino: 7B em 4-bit cabe na 4060, e o LoRA treina **visão e linguagem juntas** (`finetune_vision_layers=True` + `finetune_language_layers=True`, atenção+MLP inclusos para preservar raciocínio). Alternativas só-inferência: InternVL3 (MIT), LLaVA-OneVision.

**Receita de treino (scripts em `training/`):**

1. `python training/ingest_knowledge.py` — **TUDO vira aprendizado** (dataset unificado, 400+ exemplos hoje):
   - **`D:\References` (img + previews 3D)** — 151 imagens → 2 exemplos cada: veredito positivo ("isto é o padrão AAA aprovado do projeto") + identificação de categoria/elemento.
   - **Texturas PBR** — 89 mapas → classificação `base_color / metallic_roughness / normal`; a VLM aprende o vocabulário de materiais.
   - **Repositórios GitHub registrados** (MPFB2, MakeHuman, QRemeshify, AutoRemesher, KIRI 3DGS) — README baixado e fatiado em pares de conhecimento; a VLM aprende **como construir corretamente** com as ferramentas do pipeline.
   - **Decisões dos 9 portões** (`finetune_dataset.jsonl`) — `[foto + render + prompt do avaliador] → veredito JSON`; aprovado = positivo (0,92), reprovado = negativo (0,35; a nota do diretor vira `defects`).
   - Imagens reduzidas a 640px em `training/cache_imgs/` (orçamento de tokens da 4060). Links YouTube/X entram via frames da seção 9 no próximo ingest.
   - (`prepare_dataset.py` continua disponível para converter só as decisões.)
2. `python training/train_vlm_unsloth.py` — fine-tuning LoRA:

```python
from unsloth import FastVisionModel
import torch

# RTX 4060 8GB
max_seq_length = 512

model, tokenizer = FastVisionModel.from_pretrained(
    model_name="unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
    max_seq_length=max_seq_length,
)

model = FastVisionModel.get_peft_model(
    model,
    # IMPORTANTE: treinar visão e linguagem juntos
    finetune_vision_layers=True,
    finetune_language_layers=True,
    # mantém capacidade de raciocínio
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    # RTX 4060 8GB
    r=8, lora_alpha=16, lora_dropout=0, bias="none",
    use_rslora=False, random_state=3407,
    target_modules="all-linear",
    modules_to_save=["lm_head", "embed_tokens"],
)
# TrainingArguments: batch 1 × grad_accum 8 · 3 épocas · lr 2e-4 · fp16 ·
# adamw_8bit · gradient_checkpointing · save_steps 100 · output ./qwen3d
```

3. **Servir a VLM treinada:** merge 16-bit (`save_pretrained_merged`) → `vllm serve ./qwen3d-merged --port 8000` → `VLM_URL=http://localhost:8000/v1/chat/completions`. O endpoint `vlm-judge` passa a usar a VLM fine-tunada automaticamente — cada novo ciclo de aprovações regenera o dataset e refina o modelo (loop de melhoria contínua).

**Prompt do avaliador (por portão):**
```
Você é diretor de arte AAA. Foto de referência: <img>. Render atual do {portão}: <img>.
1) O resultado é 100% humano (não placeholder, não cartoon, não cilindro)?
2) Anatomia do {portão} bate com referências humanas reais?
3) Identidade preserva a foto (rosto/proporções/pele)?
Responda JSON: {pass: bool, score: 0-1, defects: [...], suggested_prompt_fix: "..."}
```

- **Pass automático:** `score >= 0.8 && pass=true` → portão fica verde sem você clicar.
- **Reprovação automática:** VLM gera o `suggested_prompt_fix` e re-roda o portão. Você só vê o resultado **depois** de N iterações ou se a VLM travar.
- **Dataset DPO turbinado:** cada par `{render_rejeitado, render_aprovado, prompt_fix, justificativa_VLM}` vira sinal para fine-tune da própria VLM (ou de uma reward model menor).

**Resultado:** você **não precisa pedir "humano de verdade" toda hora** — a VLM aprende seu padrão e rejeita o que não está no nível, sozinha. Esse loop é o real "olho humano" que estava simbólico no hub LLM.

### 7.9 Licenças (atenção para uso comercial)

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
| **MakeHuman / MPFB2** | GPLv3 (código) + asset license | Distribuir como ferramenta externa OK. Output de personagem livre. Não linkar em código fechado. |
| **Z-Anatomy** | CC-BY-4.0 | Livre comercial com crédito. Atribuir nos créditos do produto. |
| **Texturas 8K CC0** (Polyhaven, AmbientCG, FFHQ-UV) | CC0 | Livre total ✓ |
| **Qwen2.5/3-VL** (LLM Vision) | Apache-2.0 | Livre comercial ✓ |
| **InternVL3** | MIT | Livre comercial ✓ |

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

Site local em `D:\scanner3d-platform` (`npm start` → http://localhost:3939). **UI única estilo Ollama** — uma página só (`/`), sem menus duplicados, sem visualizador/asset-pack separados.

### 10.1 Layout (3 colunas)

```
┌────┬──────────────────────────┬────────────────────────────┐
│ 💬 │ FOTO de origem           │                            │
│ 🕘 │ ┌─ 9 portões (grid)──┐   │      Viewer 3D principal   │
│ 🔍 │ │ 🦴 🩸 💪 🪡 🧫       │   │    (controle de mouse)     │
│ ⚙  │ │ 💅 👤 👁️ 💇          │   │                            │
│    │ └────────────────────┘   │   ⊙ PBR · ◐ Clay · ▦ Wire │
│    │ Parâmetros: altura/quad  │   ⨂ Anatomy · 🌍 Mundo     │
│    │ Portão atual + ações     │                            │
│    │ ─────────────            │   strip [1][2][3]…[9]      │
│    │ [prompt textarea]      ➤ │                            │
│ 👤 │ 📎 ⚡ 👁️                  │   [Visualizador Pro] [⤓ UE5]│
└────┴──────────────────────────┴────────────────────────────┘
```

- **Sidebar fininha (56px)** — 4 ícones: 💬 Conversa · 🕘 Histórico · 🔍 Re-escanear · ⚙ Configurações/Fontes. Sem "ver documento" como menu (link único no drawer).
- **Coluna do meio** — cards do job: foto, **grid dos 9 portões** com check verde quando aprovado, parâmetros humanos, portão atual com Aprovar/Reprovar/Regen/VLM-julgar, e **input estilo Ollama** na parte inferior (textarea + pills `📎 foto` `⚡ pipeline` `👁️ VLM auto`).
- **Viewer 3D principal** — preview interativo do portão ativo, modos PBR/Clay/Wireframe/Anatomy/Mundo via círculos coloridos centrais, strip horizontal embaixo com thumbnails dos 9 portões. Botões superiores: **Visualizador GLB Pro** (overlay sobre tudo, abre `/viewer.html` em iframe full-screen) e **Exportar UE5**.

### 10.2 Visão final — VLM aprende, depois Blender headless → UE5

> Esta UI é **treino**. O objetivo: assim que a VLM (seção 7.8) atingir o threshold (score ≥ 0.95 com taxa de rejeição < 5% em N jobs consecutivos), o pipeline roda sem revisão humana: foto entra → MPFB2/Z-Anatomy no Blender headless gera o humano completo (corpo/rosto/rig/pele/cabelo) → exporta GLB → importa direto em UE5 (LiveLink ARKit + Groom). O human-in-the-loop atual existe **só para criar o dataset DPO** que treina a VLM.

```
HOJE                                       FUTURO (após treino)
foto → 9 portões → revisão humana →        foto → VLM julga → Blender
       cria DPO → treina VLM →             headless → UE5 export
                                           ZERO revisão humana
```

### 10.3 Pipeline interativo — 9 portões de validação sequencial

Funciona como um **ComfyUI**, mas **estritamente linear e bloqueante**: nenhuma camada subsequente é calculada sem a aprovação explícita do portão atual. Cada portão é um **nó** no grafo (`three.js` para o preview 3D), e tudo passa por um nó central **LLM · Olho Humano** que orquestra, julga e é condicionado pela revisão humana.

**A esteira de validação (9 portões anatômicos):**

| # | Portão | Foco de validação na viewport 3D | Comportamento ao reprovar |
|:-:|---|---|---|
| 1 | 🦴 **Esqueleto** | Estrutura óssea osso a osso, proporções, falanges, articulações | Regera a estrutura paramétrica mudando a semente (`approach++`) |
| 2 | 🩸 **Veias** | Relevo vascular subdérmico, ramificações, espessura | Ajusta o mapa de displacement/SSS subdérmico via prompt |
| 3 | 💪 **Músculos** | Definição, massa corporal, volume anatômico e colisores físicos | Recalcula volumes via campo implícito HIT |
| 4 | 🪡 **Tecido** | Moldes 2D, caimento inicial e resposta à gravidade | Modifica padrões do `GarmentCode` e re-executa o drape |
| 5 | 🧫 **Pele** | Textura PBR, poros via micro-normais, especularidade | Ajusta geração difusa e mapas de rugosidade/SSS |
| 6 | 💅 **Unhas** | Formato, curvatura, cutícula, material especular de mãos/pés | Refina parâmetros locais do material PBR no template |
| 7 | 👤 **Rosto** | Topologia facial, loops de animação, linhas de expressão | Ajusta coeficientes FLAME e mapas de tensão |
| 8 | 👁️ **Olhos** | Posição da íris, refração da córnea, umidade lacrimal | Recalcula posicionamento ortóptico e shader de refração |
| 9 | 💇 **Cabelo** | Curvas-guia vetoriais, strand count, balanço físico final | Regera curvas-guia `DiffLocks` ou ajusta hair cards |

**Fluxo human-in-the-loop (fine-tuning interativo):** o sistema, em cada portão, **gera o resultado, renderiza em 3D e captura uma imagem** exibida para revisão. **Aprovar** → o nó fica verde e libera o próximo. **Reprovar** (com nota opcional) → o portão **entende que aquela abordagem não serve e regera com outra** (`approach++`), repetindo até aprovação. Cada decisão vira uma linha do **dataset de preferência** (`data/finetune_dataset.jsonl`): `{snapshot, source, label: approved|rejected, note, stage}` — material direto para **DPO** (aprovados = positivos; reprovados = negativos).

**Controle paramétrico por prompt** (linguagem natural, pt-BR) — cada comando ajusta o modelo e é registrado como sinal de condicionamento:
- `mude altura para 1,70` → escala antropométrica (baseline 1,70 m).
- `aumente 20% o quadril` / `diminua 10% o ombro` / `engrossar 30% a musculatura/coxa` → multiplicadores per-região (mapeiam aos 76 atributos do ATLAS, seção 7.6).
- `tom de pele pardo` (clara/morena/parda/oliva/negra…) → albedo/SSS.
- `simular vento na queda do vestido` → liga a **resposta real de tecido**.

> **Escopo honesto:** os motores reais de IA (PSHuman, ATLAS, HIT, DiffLocks, loop nvdiffrast) **não rodam neste protótipo** — cada nó usa um gerador de preview procedural em `three.js`, plugável, que muda visivelmente de abordagem ao reprovar e reage aos prompts. A **infraestrutura** (9 portões, grafo, revisão, dataset DPO, edição por prompt, cascata de recálculo) é real e funcional; basta plugar os modelos da seção 7 no lugar de cada gerador.

### 10.3.1 Recálculo síncrono em cascata

Se o usuário está num portão avançado (ex.: **5 — Pele**) e submete um ajuste **estrutural/volumétrico** (ex.: *"aumente o quadril 20%"*, *"engrosse a coxa"*), o sistema **não** quebra as camadas adjacentes nem gera anomalias. Executa um fluxo de **dependência retroativa automática**:

```
[Prompt de ajuste estrutural]
        │
        ▼
[Portão 3: Músculos] ──► reajusta a massa muscular interna (novos colisores)
        │
        ▼
[Portão 4: Tecido] ────► recalcula sincronamente o drape/caimento (Warp)
        │
        ▼
[Portão atual] ────────► renderiza a nova composição física unificada
        │
        ▼
[Pausa automática] ────► solicita nova aprovação para prosseguir
```

- **Garantia física:** a malha de tecido lê os novos limites do colisor muscular recalculado no mesmo passo, computando os impactos quadro a quadro de forma integrada.
- **Persistência de estilo:** modificações superficiais já validadas (texturas, micro-poros) são preservadas e reprojetadas sobre a nova superfície deformada.
- **No protótipo:** um prompt estrutural reabre **Músculos** e **Tecido** para re-validação (volta o `activeIndex` ao primeiro portão afetado, re-renderizado com os novos parâmetros) e exibe o aviso de cascata — o pipeline pausa até a nova aprovação.

### 10.4 Física de tecido real (não "cola", não rígido)

O requisito "se está de vestido e cai num lugar mais baixo, o vestido levanta como se o vento agisse de verdade" é **simulação de tecido diferenciável** (seção 7.6): NVIDIA **Warp / Newton 1.0** (VBD) para drape e resposta dinâmica; o vestido é malha **aberta** drapeada sobre o corpo (rota sewing-pattern), nunca casca fechada colada. No protótipo, o portão **Tecido** demonstra a barra do vestido subindo e inflando conforme a intensidade do vento. Objetivo de qualidade: corpo sem triangulação grosseira, mecânica corporal real (HIT + Chaos Flesh) e tecido com resposta real — padrão estúdio AAA.

### 10.5 Bridge Blender headless (construção real pós-aprovação)

**Acionada SOMENTE quando os 9 portões são aprovados** — aí o Blender replica toda a construção do zero, na ordem dos portões, e exporta o personagem real:

```
9/9 aprovados ──► blender.exe --background --python blender/build_character.py
                    │  01_Esqueleto   armature humana real (42 ossos c/ falanges)
                    │  02_Veias       strands bezier nos membros
                    │  03_Músculos    corpo orgânico (MPFB2 se instalado; senão
                    │                 cápsulas+remesh) RIGADO c/ automatic weights
                    │  04_Tecido      saia aberta + cloth modifier (pin cintura)
                    │                 + corpo como COLISOR (roupa não atravessa)
                    │  05-08          pele SSS · unhas · rosto · olhos c/ íris
                    │  09_Cabelo      160 strands → malha
                    ▼
                  character.glb (rig embutido) + character.blend
```

- Cada portão vira uma **Collection** nomeada (`01_Esqueleto` … `09_Cabelo`) — modular, espelhando o pipeline.
- Progresso em tempo real via SSE (`build:started/log/done/error`); ao concluir, botões **"Ver GLB no Visualizador Pro"** e **"Baixar .blend"**.
- Detecção automática do Blender (`D:\Blender Foundation\blender.exe` ou `BLENDER_PATH`); build manual via `POST /api/jobs/:id/build`.
- **Verificado de ponta a ponta:** build automático em ~20 s → GLB de 3,8 MB (112 k vértices / 199 k polígonos) carregado no Visualizador Pro.
- Upgrade do estágio de corpo: instalar **MPFB2** no Blender → o script usa automaticamente (hook `try_mpfb_body`). Próximo: import UE5 (Groom + LiveLink).

### 10.6 Visualizador GLB Pro (overlay full-screen)

Mantido como `viewer.html` mas **aberto dentro da home** (botão "🧊 Visualizador GLB Pro" superior → iframe over tudo). Drag-drop ou seletor de modelos enviados, **3 modos** (Render PBR · Sólido/Clay · **Topologia/Wireframe**), auto-rotação 360°, iluminação de estúdio (key/fill/rim + `RoomEnvironment`), chão com sombra, e **polycount** (vértices/polígonos). Wireframe = verificação visual de "sem triângulo grosseiro" (topologia limpa). Aceita deep-link `?model=` — é assim que o GLB construído pelo Blender abre.

**Endpoints:** `POST /api/jobs` (cria job), `GET /api/jobs/:id`, `POST /api/jobs/:id/stages/:stage/snapshot` (grava preview), `POST .../review` (aprova/reprova → dataset), `POST .../vlm-judge` (VLM julga, 7.8), `POST /api/jobs/:id/params` (edição por prompt + cascata), `GET /api/dataset[/export]` (DPO `.jsonl`), `GET /api/models` (GLBs).

---

## 11. Fontes de Treinamento (alimentado pelo site)

<!-- AUTO:SOURCES:START -->
### GitHub — ferramentas e código de referência (20)

- [KIRI Engine 3DGS Render - addon Blender p/ Gaussian Splatting (importa/edita/anima/renderiza .ply/.splat), Apache-2.0](https://github.com/Kiri-Innovation/3dgs-render-blender-addon) — adicionado em 2026-06-12T18:08:53.089Z
- [QRemeshify - addon Blender de retopologia quad (base QuadWild + Bi-MDF), GPL-3.0. Retopo classico da secao 7.6](https://github.com/ksami/QRemeshify) — adicionado em 2026-06-12T19:47:07.070Z
- [AutoRemesher - remesh quad automatico standalone (autor do Dust3D), GPL-3.0. Retopo classico da secao 7.6](https://github.com/huxingyi/autoremesher) — adicionado em 2026-06-12T19:47:07.107Z
- [MPFB2 - gerador humano open p/ Blender 4.2+ (corpo/rosto/rig/pele/poses), GPLv3. Motor base do trilho de Corpo + Rosto](https://github.com/makehumancommunity/mpfb2) — adicionado em 2026-06-12T20:19:24.938Z
- [MakeHuman - gerador parametrico humano standalone (Python), GPL. Origem do MPFB2](https://github.com/makehumancommunity/makehuman) — adicionado em 2026-06-12T20:19:24.968Z
- [ChatGarment (Apache-2.0) - VLM le N imagens de roupa -> sewing pattern GarmentCode JSON -> drape 3D. Trilho Tecido (portao 4) com leitura multi-imagem das 10 etapas do vestido](https://github.com/biansy000/ChatGarment) — adicionado em 2026-06-12T23:22:14.168Z
- [TailorNet - roupa deformada por pose+shape+style (MPI), prediz wrinkles; trilho Tecido junto com ChatGarment](https://github.com/chaitanya100100/TailorNet) — adicionado em 2026-06-12T23:30:09.796Z
- [SMPL-X oficial (python package smplx) - corpo parametrico betas/pose; prior do trilho Corpo](https://github.com/vchoutas/smplx) — adicionado em 2026-06-12T23:30:09.826Z
- [Hunyuan3D 2.1 - reconstrucao inicial + refino geometrico: geometria e textura PBR separadas, TREINO LIBERADO (fine-tune com dataset DPO). VRAM 10GB shape/21GB texture. Atencao licenca Tencent (exclusoes regionais)](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) — adicionado em 2026-06-13T00:05:56.776Z
- [TRELLIS/TRELLIS.2 (MIT) - geracao 3D de acessorios rigidos (armadura, joias, botas) no trilho Acessorios](https://github.com/microsoft/TRELLIS) — adicionado em 2026-06-13T00:05:56.788Z
- [DiffLocks (CVPR25) - 1 imagem -> ~100K strands de cabelo 3D; treino incluso + dataset 40K; export Blender/Alembic. Trilho Cabelo com Hair Curves + Geometry Nodes](https://github.com/Meshcapade/DiffLocks) — adicionado em 2026-06-13T00:05:56.793Z
- [Z-Anatomy (CC-BY-4.0) - atlas anatomico Blender 4500 estruturas (ossos/musculos/veias/nervos/orgaos). Etapa 3: musculatura INSTANCIADA (nao inferida) registrada no SMPL-X](https://github.com/LluisBP/Z-Anatomy) — adicionado em 2026-06-13T00:18:22.264Z
- [NVIDIA Warp - simulacao diferenciavel (cloth/soft-body). Etapa 4: drape de roupa complexa multicamada (substitui TailorNet)](https://github.com/NVIDIA/warp) — adicionado em 2026-06-13T00:18:22.294Z
- [Newton (Linux Foundation: NVIDIA+DeepMind+Disney) - solver fisico VBD sobre Warp. Etapa 4: cloth sim final do vestido](https://github.com/newton-physics/newton) — adicionado em 2026-06-13T00:18:22.299Z
- [TailorMe (Botsch, CGF2024) - template anatomico volumetrico INSTANCIADO (pele+musculo+esqueleto M/F). Etapa 3: anatomia instanciada (nao inferida) registrada ao SMPL-X](https://github.com/mbotsch/TailorMe) — adicionado em 2026-06-13T00:26:03.371Z
- [SKEL (SIGGRAPH Asia 2023) - rig biomecanico 46-DoF ancorado ao SMPL-X. Driver de pose da anatomia. LICENCA MPI nao-comercial (contrato p/ AAA)](https://github.com/MarilynKeller/SKEL) — adicionado em 2026-06-13T00:26:03.377Z
- [Material Anything (CVPR2025, MIT) - SVBRDF 3D-aware na malha (albedo/rough/metallic/normal). Etapa 6 Material AI se trocar o paint do Hunyuan](https://github.com/3DTopia/MaterialAnything) — adicionado em 2026-06-13T00:26:03.382Z
- [RGB-X (SIGGRAPH2024) - decompoe foto em albedo/rough/metallic/normal + delight. Extrai material limpo de 1 foto de referencia](https://github.com/zheng95z/rgbx) — adicionado em 2026-06-13T00:26:03.385Z
- [Mitsuba 3 + Dr.Jit (BSD-3) - renderizador diferenciavel. Etapa 7: loop inverso joint geometria+material+SSS (substitui nvdiffrast puro)](https://github.com/mitsuba-renderer/mitsuba3) — adicionado em 2026-06-13T00:26:03.389Z
- [Practical Inverse Rendering (Google/EPFL SIGGRAPH2025, Apache-2.0) - SSS path-traced diferenciavel. Refino de pele no loop Etapa 7](https://github.com/google/practical-inverse-rendering-of-textured-and-translucent-appearance) — adicionado em 2026-06-13T00:26:03.393Z
<!-- AUTO:SOURCES:END -->

## 12. Arquivos Enviados (upload via site)

<!-- AUTO:UPLOADS:START -->
*Nenhum arquivo enviado ainda.*
<!-- AUTO:UPLOADS:END -->

## 13. Arquivos de Referência (`D:\References`)

<!-- AUTO:REFERENCES:START -->
*Inventário gerado em 2026-06-13T01:44:06.417Z a partir de `D:\References`.*

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
