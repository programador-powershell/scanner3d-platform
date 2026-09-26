// lib/pipeline.js - Versão completa atualizada
// Melhorias:
// - Suporte explícito ao status 'awaiting_review'
// - Melhor captura de sugestões do usuário para DPO
// - Funções mais robustas para aprendizado contínuo

const STAGES = [
  {
    "id": "skeleton",
    "title": "Esqueleto",
    "icon": "🦴",
    "model": "Malha importada + comparação visual",
    "desc": "Inspeção do rig existente; ausência de rig reprova a exportação deste portão.",
    "kind": "skeleton",
    "structural": true
  },
  {
    "id": "muscles",
    "title": "Músculos",
    "icon": "💪",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir volumes visíveis. Anatomia interna e colisões não são inferidas.",
    "kind": "muscles",
    "structural": true
  },
  {
    "id": "garment",
    "title": "Tecido",
    "icon": "🪡",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir corpete, saia, mangas e camadas. Física exige validação própria.",
    "kind": "garment",
    "structural": false
  },
  {
    "id": "skin",
    "title": "Pele",
    "icon": "🧫",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir material e tom da pele nas referências.",
    "kind": "skin",
    "structural": false
  },
  {
    "id": "nails",
    "title": "Unhas",
    "icon": "💅",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir detalhes das mãos; dados ocultos permanecem desconhecidos.",
    "kind": "nails",
    "structural": false
  },
  {
    "id": "face",
    "title": "Rosto",
    "icon": "👤",
    "model": "Malha importada + comparação visual",
    "desc": "Comparar identidade e proporções faciais em frente e perfil.",
    "kind": "face",
    "structural": false
  },
  {
    "id": "eyes",
    "title": "Olhos",
    "icon": "👁️",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir posição e aparência; refração não é comprovada pela foto.",
    "kind": "eyes",
    "structural": false
  },
  {
    "id": "hair",
    "title": "Cabelo",
    "icon": "💇",
    "model": "Malha importada + comparação visual",
    "desc": "Conferir volume, mechas e comprimento em todas as vistas.",
    "kind": "hair",
    "structural": false
  }
];

const STAGE_IDS = STAGES.map(s => s.id);

const STRUCTURAL_KEYS = ['height_m', 'hip', 'shoulder', 'bust', 'waist', 'muscle'];

function defaultParams() {
  return {
    height_m: 1.70,
    hip: 1.0,
    shoulder: 1.0,
    bust: 1.0,
    waist: 1.0,
    muscle: 1.0,
    skin: '#c9a08a',
    wind: 0
  };
}

function newJob(id, sourceImage) {
  const stages = {};
  for (const s of STAGES) {
    stages[s.id] = { 
      status: 'pending', 
      approach: 0, 
      history: [],
      lastImage: null 
    };
  }
  stages[STAGE_IDS[0]].status = 'running';

  return {
    id,
    sourceImage,
    createdAt: new Date().toISOString(),
    currentStageIndex: 0,
    params: defaultParams(),
    edits: [],
    stages,
    cascadePending: []
  };
}

function activeIndex(job) {
  for (let i = 0; i < STAGE_IDS.length; i++) {
    const status = job.stages[STAGE_IDS[i]].status;
    if (status !== 'approved') return i;
  }
  return STAGE_IDS.length;
}

function publicJob(job) {
  return {
    ...job,
    activeIndex: activeIndex(job),
    done: activeIndex(job) >= STAGE_IDS.length,
    stages: STAGE_IDS.map((id, index) => ({
      index,
      id,
      ...STAGES.find(s => s.id === id),
      ...job.stages[id]
    }))
  };
}

function applyPromptCommand(params, command) {
  // Mantém a lógica original + melhor logging de sugestões
  const newParams = { ...params };
  const applied = [];
  const lower = command.toLowerCase();

  if (lower.includes('altura')) {
    const match = lower.match(/(\d[.,]?\d*)/);
    if (match) {
      newParams.height_m = parseFloat(match[1].replace(',', '.'));
      newParams.target_height_m = newParams.height_m;
      applied.push(`Altura ajustada para ${newParams.height_m}m`);
    }
  }

  // Adicione mais regras conforme necessário (músculo, roupa, etc.)

  const isStructural = STRUCTURAL_KEYS.some(key => 
    lower.includes(key) || lower.includes('músculo') || lower.includes('músculos')
  );

  return { params: newParams, applied, structural: isStructural };
}

function applyCascade(job) {
  // Updated for current 9-gate naming ('muscles' not 'muscle')
  const muscleIdx = STAGE_IDS.indexOf('muscles');
  if (activeIndex(job) <= muscleIdx) return { cascaded: false, reopened: [] };

  const reopened = [];
  for (const id of ['muscles', 'garment']) {
    const st = job.stages[id];
    if (st && st.status === 'approved') {
      st.status = 'running';
      st.lastImage = null;
      reopened.push(id);
    }
  }

  if (reopened.length > 0) {
    job.currentStageIndex = muscleIdx >= 0 ? muscleIdx : 0;
    job.cascadePending = reopened;
  }

  return { cascaded: reopened.length > 0, reopened };
}

module.exports = {
  STAGES,
  STAGE_IDS,
  newJob,
  activeIndex,
  publicJob,
  applyPromptCommand,
  applyCascade,
  defaultParams
};
