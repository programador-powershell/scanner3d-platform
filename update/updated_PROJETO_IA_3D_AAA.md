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

## 3. Atualizações no Pipeline de 9+ Portões

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

## 6. Próximos Passos Recomendados

1. Implementar `costume_layers.json` parser no `server.js` e `build_stage.py`.
2. Adicionar endpoint `/api/jobs/:id/costume/analyze` que usa VLM para gerar o JSON a partir de imagem de conceito.
3. Expandir `build_stage.py` com lógica real de Cloth simulation por layer + collision groups.
4. Criar preset de materiais e embroidery para estilo "Dark Romantic Victorian Gothic".
5. Testar com o set completo de imagens Alice Liddell fornecido.

**Este documento reflete a visão v6 com foco em figurinos complexos de alta fidelidade.**

---

*Atualizado em 14 de Junho de 2026 por Grok (xAI) a pedido do mantenedor.*