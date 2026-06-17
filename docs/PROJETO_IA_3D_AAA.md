# Projeto IA 3D AAA — Scanner 3D Cognitivo (v6 - Complex Garment Layers)

**Foco Atualizado (Junho 2026):**  
Fotorrealismo Extremo + **Simulação de Vestuário Complexo Multi-Camadas** no padrão **Stellar Blade: Blood Rain** e figurinos góticos vitorianos detalhados (ex: Alice Liddell - Faca de Cozinha).

A plataforma agora suporta **decomposição automática e reconstrução realista de figurinos complexos** com 8~12 camadas físicas independentes (forro interno → corset → saias internas → overskirt → mangas → acessórios), com simulação física realista entre camadas, colisão precisa e fidelidade de materiais/ bordados.

---

## 1. Visão Geral e Meta

**Entrada:** Uma ou mais imagens 2D de referência (corpo base + conceito completo do figurino + sheets de camadas opcionais).

**Saída:** Personagem 3D completo com:
- Anatomia realista (ossos SKEL/Z-Anatomy + músculos volumétricos + pele micro + SSS)
- **Figurino multi-camadas fisicamente simuladas** (hierarquia real de tecido)
- Cabelo fio a fio (DiffLocks ~100k strands)
- Rig anatômico completo + weights por camada
- Export GLB/FBX com hierarquia de layers nomeada corretamente

**Exemplo de Entrada:** As imagens de Alice Liddell (base body + full costume + stage breakdowns 1~10).

**Meta de Qualidade:** Cada camada deve ter drape, peso, colisão e movimento independentes, como em produção AAA de alto nível (Stellar Blade + figurinos de alta costura gótica).

---

## 2. Suporte a Figurinos Complexos Multi-Camadas (Novo)

### 2.1 Estrutura de Camadas Recomendada (inspirada em Alice Liddell)

O sistema agora trabalha com **costume_layers.json** estruturado:

```json
{
  "character_id": "alice_liddell_kitchen_knife",
  "base_body": "alice_base_bodysuit",
  "layers": [
    {
      "id": "layer_01_inner_base",
      "name": "Inner Base Layer / Chemise + Internal Corset",
      "type": "underwear",
      "parent": null,
      "order": 1,
      "physics": { "stiffness": 0.8, "damping": 0.4, "mass": 0.3, "collision_group": "body" },
      "material": { "base_color": "#F5F0E6", "roughness": 0.7, "sheen": 0.3 },
      "construction_notes": "Light cotton/linen blend with lace trim and cross embroidery"
    },
    {
      "id": "layer_02_corset",
      "name": "Outer Corset + Waist Belt System",
      "type": "corset",
      "parent": "layer_01_inner_base",
      "order": 2,
      "physics": { "stiffness": 0.95, "damping": 0.2, "mass": 0.6, "collision_group": "corset" },
      "material": { "base_color": "#1A1F2E", "metallic": 0.1, "roughness": 0.6 },
      "construction_notes": "Structured cotton coutil with steel boning, antique brass hardware, rose buckle"
    },
    {
      "id": "layer_03_underskirt",
      "name": "Underskirt + Petticoat Tiers",
      "type": "skirt",
      "parent": "layer_02_corset",
      "order": 3,
      "physics": { "stiffness": 0.6, "damping": 0.5, "mass": 0.4, "collision_group": "skirt_inner" },
      "layers_sub": ["waistband", "base_lining", "volume_petticoat", "lace_tier_1", "lace_tier_2", "lace_tier_3"]
    },
    {
      "id": "layer_04_overskirt",
      "name": "Outer Skirt Panels + Asymmetrical Overskirt + Front Apron",
      "type": "overskirt",
      "parent": "layer_03_underskirt",
      "order": 4,
      "physics": { "stiffness": 0.5, "damping": 0.6, "mass": 0.7, "collision_group": "skirt_outer" },
      "construction_notes": "Navy jacquard with gold metallic embroidery, rose appliqués, asymmetrical drapes"
    },
    {
      "id": "layer_05_sleeves",
      "name": "Puff Sleeves + Leather Bracers + Lace Cuffs",
      "type": "sleeves",
      "parent": "layer_02_corset",
      "order": 5
    },
    {
      "id": "layer_06_back_bow",
      "name": "Rear Bow / Bustle + Back Drape",
      "type": "back_detail",
      "parent": "layer_04_overskirt",
      "order": 6
    },
    {
      "id": "layer_07_accessories",
      "name": "Necklace, Choker, Hair Ornaments, Belt Charms, Knife Sheath",
      "type": "accessories",
      "parent": null,
      "order": 7,
      "rigid": true
    },
    {
      "id": "layer_08_legwear",
      "name": "Striped Stockings + Lace-up Victorian Boots",
      "type": "legwear",
      "parent": "layer_01_inner_base",
      "order": 8
    }
  ],
  "simulation_settings": {
    "gravity": -9.81,
    "wind_strength": 0.3,
    "air_damping": 0.15,
    "enable_self_collision": true,
    "solver_iterations": 12
  },
  "materials_palette": { ... }
}
```

### 2.2 Pipeline de Decomposição de Figurino (Atualizado)

1. **VLM + Florence-2** analisa a imagem de conceito completo e/ou sheets de stages.
2. Gera automaticamente `costume_layers.json` com hierarquia, ordem de montagem e propriedades físicas.
3. Para cada layer:
   - Gera ou importa malha base (GarmentCode / Marvelous Designer .zpac ou obj)
   - Aplica materiais PBR por layer (albedo, normal, roughness, metallic, sheen, displacement)
   - Adiciona modificadores Cloth + Collision com grupos corretos
   - Executa simulação física (bake) com vento/gravidade leve para drape natural
4. Hierarquia de parent no armature + skinning weights por layer
5. Export GLB com coleções nomeadas por layer (ex: `Layer_02_Corset`, `Layer_04_Overskirt`)

**Integração com Marvelous Designer (recomendado para qualidade AAA):**
- O sistema pode exportar patterns para MD ou importar `.zpac` + simulação.
- Para prototipagem rápida: GarmentCode gera base → refinamento manual ou VLM-guided no MD.

---

## 3. Atualizações no Pipeline de 8 Portões (veias removido)

O pipeline agora tem **portões expandidos para figurinos**:

1. Skeleton (Z-Anatomy/SKEL)
2. Muscles (volumetric)
3. Inner Base Layer (chemise/corset foundation)
4. Main Corset & Waist Structure
5. Skirt Understructure (petticoat tiers)
6. Outer Skirt & Overskirt Panels
7. Sleeves, Shoulders & Neckline
8. Back Assembly (bow, bustle, lacing)
9. Legwear & Footwear
10. Accessories & Small Components (jewelry, knife, hair ornaments)
11. Skin + Micro details + SSS
12. Hair (DiffLocks)
13. Final Assembly + Physics Validation

Cada portão de roupa agora gera **preview por sub-layer** e permite aprovação individual.

---

## 4. Human-in-the-Loop Aprimorado para Figurinos

- Após cada layer (ou grupo de layers relacionadas), pausa para aprovação.
- VLM Judge especializado em tecido: verifica colisão entre camadas, drape natural, sem interpenetração, peso visual correto, movimento independente.
- Feedback do usuário (aprovar/reprovar + nota + sugestão de prompt) → DPO dataset específico para "garment_quality".
- LoRA no Qwen3-VL treina preferências de estilo gótico vitoriano, densidade de bordado, brilho de metal antique, etc.

---

## 5. Stack Tecnológico Atualizado (Jun/2026)

| Camada                  | Tecnologia Principal                  | Alternativa / Refino          |
|-------------------------|---------------------------------------|-------------------------------|
| Base Body + Anatomy     | SKEL + Z-Anatomy + MPFB2             | SMPL-X (se licenciado)       |
| Inner Layers / Corset   | GarmentCode + Marvelous Designer     | ChatGarment                  |
| Multi-tier Skirts       | Marvelous Designer + Newton/Warp     | GarmentCode + Cloth sim      |
| Overskirt & Drapes      | MD sim + custom collision groups     | Blender Cloth + nCloth       |
| Sleeves & Details       | Procedural + MD                      | -                            |
| Accessories (rígidos)   | TRELLIS.2 / Hunyuan3D                | -                            |
| Hair                    | DiffLocks (~100k strands)            | -                            |
| Materiais PBR           | Material Anything + Mitsuba 3 SSS    | -                            |
| Decomposição de Layers  | Florence-2 fine-tuned + Qwen3-VL     | -                            |
| Simulação Física        | Marvelous Designer + Blender Cloth   | Nvidia Warp / Newton 1.0     |

---

## 6. Integrações Adicionais 2026 para Scanner e Fidelidade (NVlabs + Licon)

Adicionadas para elevar o "scanner" (análise precisa da imagem enviada) e a "fidelidade" (reconstrução 3D pixel-perfect com anatomia/movimento realistas):

### SOMA-X (NVlabs)
- **O que é**: Unificador de modelos paramétricos de corpo (SMPL/SMPL-X + MHR + Anny + GarmentMeasurements + SOMA-shape próprio). Topologia canônica + rig unificado + pose correctives automáticos. GPU (NVIDIA Warp), fully differentiable.
- **Como melhora o projeto**:
  - Substitui/aumenta o atual MPFB2 / cylinders manuais / SMPL fallback no gate de corpo, rig, músculos.
  - Fitting de shape/proporções mais preciso a partir da foto + VLM params (height, medidas, etc.).
  - Consistência perfeita para camadas de roupa (collision com body unificado) e export de rig.
  - Integração com GR00T (retargeting) e BONES-SEED motion data.
- **Arquivo de integração**: `python/soma_integration.py` (SOMALayer + fit + export OBJ/params para Blender).
- **Uso no pipeline**: No pre-scan ou gate "muscles/body", chame `fit_body_from_image_and_params`. No `build_character.py` (estágio body/skeleton): gere o mesh base com SOMA em vez de procedural puro. Exporta para GLB com rig unificado.
- **Instalação**: `pip install py-soma-x` (+ extras smpl/anny). Assets auto-download do HF. Para SMPL: baixe os .pkl/.npz oficiais separadamente.

### GR00T-WholeBodyControl + GEAR-SONIC + MotionBricks (NVlabs)
- **O que é**: Plataforma unificada para whole-body controllers de humanoides (Decoupled WBC, SONIC behavior foundation model treinado em motion tracking, kinematic planner, teleop VR, C++ inference real-time, MotionBricks latent motion).
- **Como melhora o projeto**:
  - Rig avançado + whole-body IK/control no lugar de IK manual simples.
  - Geração de animação/movimento natural e física-aware (respeitando layers de roupa, vento, gravidade).
  - Melhor export para UE/Unity + control direto (melhora o "rig pronto para heavy anims").
  - Validação de fidelidade de garment em movimento (simulação de camadas durante o planner).
  - MotionBricks para controle interativo no viewer (além das anims estáticas em data/anims).
- **Sinergia**: Funciona nativamente com SOMA (retargeting + body unificado). Eagle é backbone VLM em várias versões do GR00T.
- **Arquivo de integração**: `python/gr00t_control.py` (wrappers para controller, retarget via SOMA, generate motion, apply no rig Blender, export).
- **Uso**: Após criação do rig (skeleton + muscles), chame o controller/SONIC para gerar ou aplicar poses/motion. No garment: simule resposta das layers ao movimento. No final export + viewer: use MotionBricks/SONIC para previews animados de alta qualidade. Adicione como opção no launch do Blender GUI.

### Eagle (NVlabs)
- **O que é**: Família de frontier VLMs com estratégias data-centric. Forte em image/video understanding, long-context reasoning, generalist grounding (LocateAnything para detecção/ponteiros densos), embodied AI. Usado em GR00T N1.x, Cosmos, etc. Variantes: Eagle (mixture-of-encoders), Eagle 2/2.5 (SOTA), LocateAnything (grounding).
- **Como melhora o projeto**:
  - **Scanner melhorado**: Pre-scan muito mais preciso (medidas, proporções, camadas de roupa, materiais, pose, landmarks via grounding). Substitui ou ensemble com Qwen atual.
  - **Julgamento de gates com mais fidelidade**: Cada portão compara render vs foto enviada com muito mais detalhe (grounding de costuras, drape, poros, hair strands, etc.). Menos falsos positivos/negativos.
  - Long-context útil para múltiplas imagens (ref + várias previews ou Licon-MSR video frames).
  - Grounding (LocateAnything) para extração automática de medidas precisas ou segmentação de layers sem depender só de Florence/Qwen.
- **Arquivo de integração**: `python/eagle_vlm.py` (load via transformers, call_eagle_vlm, helpers eagle_scan + eagle_judge + eagle_locate_anything).
- **Uso no pipeline**: Em server.js `/scan` e no loop de VLM judge por gate: chame as funções Eagle quando `EAGLE_MODEL` configurado (ou sempre como backend preferencial). No garment/layer analysis: use para grounding de painéis específicos.
- **Instalação/Modelos**: HF `nvidia/Eagle2.5-8B` etc. (ou variantes LocateAnything). Roda com transformers/vLLM. Atualize `VLM_URL` ou adicione switch no server.

### ComfyUI-Licon-MSR (liconstudio)
- **O que é**: Custom node ComfyUI para LTX 2.3 MSR (Multiple-Subject-Reference) LoRA. Recebe até 4 imagens de sujeito + background e gera MP4 de referência com frames fixos (17/25/33/41 frames @24fps). Otimizado para workflows de consistent subject reference.
- **Como melhora o projeto**:
  - Quando o usuário envia **múltiplas imagens** (body base + full costume + stage sheets de camadas + diferentes ângulos/poses), gera vídeo de referência consistente.
  - Os frames viram input superior para:
    - Eagle VLM (análise multi-view + grounding).
    - SOMA body fit (melhor shape/pose a partir de várias vistas).
    - Decomposição de layers (análise mais precisa de corset/saia/ruffles etc.).
    - Reconstrução 3D / garment (condicionamento multi-ref para Hunyuan + ChatGarment + MD).
  - Aumenta dramaticamente fidelidade em figurinos complexos (ex: o Alice Liddell gothic de 8+ layers do update/).
- **Arquivo de integração**: `python/licon_msr_integration.py` (generate_reference_video + frames extraction). Workflows de exemplo no repo (MSR_Sample_workflow.json).
- **Uso**: No upload de job ou pre-scan: se len(sourceImages) > 1, chame o node (via ComfyUI API ou subprocess) para gerar o ref video. Extraia frames e injete no resto do pipeline (VLM, SOMA, garment).
- **Instalação**: `cd ComfyUI/custom_nodes && git clone https://github.com/liconstudio/ComfyUI-Licon-MSR`. Instale requirements. Rode ComfyUI. O projeto já tem vibe "ComfyUI-like" (gates como nodes) — integre como etapa de pré-processamento de imagem.

### Como Integrar no Código Atual (resumo prático)
- **python/**: Adicionados `soma_integration.py`, `eagle_vlm.py`, `gr00t_control.py`, `licon_msr_integration.py`. Chame-os condicionalmente (try/except + env flags como `USE_SOMA=1`, `EAGLE_MODEL=...`).
- **blender/build_character.py**: No gate de body/skeleton/muscles use SOMA para o mesh base. No garment use layers do costume + GR00T para motion sim. Render previews continuam para VLM.
- **server.js**: 
  - VLM: suporte a Eagle (além de Qwen).
  - Pre-scan e garment: chame analyze com Licon-MSR quando múltiplas imagens.
  - Body/rig: passe params SOMA.
  - No final do build (após GUI launch): chame GR00T para gerar motion de preview se desejado.
- **Docs**: Esta seção + atualizações na tabela de stack e arquitetura (Engine A agora pode usar SOMA + Eagle grounding; rig/control com GR00T; image preproc com Licon).
- **Training/VLM**: Eagle como backbone alternativo para os julgamentos. Use os julgamentos + imagens geradas por Licon para mais dados de fine-tune (a cada build já disparamos fine-tuning).
- **Custo/Opicional**: Tudo opcional (fallbacks mantidos para MPFB/manual/Qwen atual). Requer installs extras e models (HF para Eagle/SOMA/GR00T). Assets grandes — use cache.

Com essas integrações o scanner fica muito mais inteligente na análise da foto enviada (Eagle + Licon + grounding) e a fidelidade do output 3D sobe significativamente (SOMA body unificado + GR00T whole-body control + motion natural + layers físicas consistentes).

Teste com o fluxo atual (foto Alice ou similar + prompt) ativando as novas flags. Os portões continuam com VLM judgment (agora com Eagle) e o loop de fine-tuning por build continua.

Próximos: adicionar endpoints no server para "use_soma_body", "use_eagle_vlm", "generate_msr_ref_video", e opções no UI.

**Este documento reflete a visão v6 com foco em figurinos complexos de alta fidelidade.**

---

*Atualizado em 14 de Junho de 2026 por Grok (xAI) a pedido do mantenedor.*