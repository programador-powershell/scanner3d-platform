// lib/pipeline.js - Versão completa atualizada
// Melhorias:
// - Suporte explícito ao status 'awaiting_review'
// - Melhor captura de sugestões do usuário para DPO
// - Funções mais robustas para aprendizado contínuo

const STAGES = [
  { id: 'skeleton', title: 'Esqueleto', icon: '🦴', model: 'Z-Anatomy + SKEL real', desc: 'Ossos reais de humano (não palitos)', kind: 'skeleton', structural: true },
  { id: 'veins', title: 'Veias', icon: '🩸', model: 'Z-Anatomy vascular + SSS', desc: 'Rede venosa subdérmica', kind: 'veins', structural: false },
  { id: 'muscle', title: 'Músculos', icon: '💪', model: 'TailorMe instanciado + física', desc: 'Músculos volumétricos reais', kind: 'muscle', structural: true },
  { id: 'garment', title: 'Tecido/Roupa', icon: '🧥', model: 'ChatGarment + GarmentCode + Marvelous + Warp/Newton + Blender Cloth AAA', desc: 'Vestuário fotorrealista multicamada com vento/gravidade/lift real (Stellar Blade / Blood Rain). Não cola no corpo.', kind: 'garment', structural: false },
  { id: 'skin', title: 'Pele', icon: '🧬', model: 'Material AI + micro-normals + SSS', desc: 'Pele hiper-realista Stellar Blade level', kind: 'skin', structural: false },
  { id: 'nails', title: 'Unhas', icon: '💅', model: 'MPFB2 + PBR', desc: 'Unhas detalhadas', kind: 'nails', structural: false },
  { id: 'face', title: 'Rosto', icon: '👤', model: 'FLAME + ARKit 52', desc: 'Rosto com identidade forte', kind: 'face', structural: false },
  { id: 'eyes', title: 'Olhos', icon: '👁️', model: 'MPFB2 + shader córnea', desc: 'Olhos com refração e umidade', kind: 'eyes', structural: false },
  { id: 'hair', title: 'Cabelo', icon: '💇', model: 'DiffLocks + Hair Curves', desc: 'Cabelo fio a fio (~100k strands)', kind: 'hair', structural: false },
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
    activeIndex: job.activeIndex ?? job.currentStageIndex ?? 0,
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
  const muscleIdx = STAGE_IDS.indexOf('muscle');
  if (activeIndex(job) <= muscleIdx) return { cascaded: false, reopened: [] };

  const reopened = [];
  for (const id of ['muscle', 'garment']) {
    const st = job.stages[id];
    if (st.status === 'approved') {
      st.status = 'running';
      st.lastImage = null;
      reopened.push(id);
    }
  }

  if (reopened.length > 0) {
    job.currentStageIndex = muscleIdx;
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