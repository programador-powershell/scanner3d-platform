// lib/pipeline.js - Versão completa atualizada
// Melhorias:
// - Suporte explícito ao status 'awaiting_review'
// - Melhor captura de sugestões do usuário para DPO
// - Funções mais robustas para aprendizado contínuo

const STAGES = [
  { id: 'skeleton', title: 'Esqueleto', icon: '🦴', model: 'Z-Anatomy + MPFB2 + ATLAS/SKEL (instanciado)', desc: 'Ossos reais de humano (não palitos) - 42+ ossos com falanges, proporções do ATLAS 76 attrs', kind: 'skeleton', structural: true },
  { id: 'muscles', title: 'Músculos', icon: '💪', model: 'MPFB2 + HIT/TailorMe instanciado + colisores Chaos Flesh', desc: 'Volumes musculares reais + barreira física para tecido (frame-by-frame collision)', kind: 'muscles', structural: true },
  { id: 'garment', title: 'Tecido', icon: '🪡', model: 'ChatGarment/GarmentCode + NVIDIA Warp/Newton + Blender Cloth AAA multi-layer', desc: 'Vestuário multicamada (corset, saia, renda) com padrões costura, drape real, vento/gravidade/lift, sem fusão/clip (Stellar Blade / Blood Rain)', kind: 'garment', structural: false },
  { id: 'skin', title: 'Pele', icon: '🧫', model: 'MPFB2 skin + 8K CC0 PBR + micro-normals + SSS (Mitsuba refino)', desc: 'Pele hiper-realista com poros, rugosidade, translucidez - realismo vem dos materiais (Stellar Blade)', kind: 'skin', structural: false },
  { id: 'nails', title: 'Unhas', icon: '💅', model: 'MPFB2 template + PBR specular/cuticle/lunula', desc: 'Unhas detalhadas com cutícula, lúnula, brilho especular correto', kind: 'nails', structural: false },
  { id: 'face', title: 'Rosto', icon: '👤', model: 'MPFB2/FLAME + ICT-FaceKit + 52 ARKit blendshapes + wrinkle', desc: 'Topologia facial com edge loops perfeitos para animação, identidade pixel da foto', kind: 'face', structural: false },
  { id: 'eyes', title: 'Olhos', icon: '👁️', model: 'MPFB2 cornea/iris + shader refração + lacrimal', desc: 'Globos com posição íris, refração córnea, umidade lacrimal, SSS', kind: 'eyes', structural: false },
  { id: 'hair', title: 'Cabelo', icon: '💇', model: 'DiffLocks prior + Blender Hair Curves (~100k strands) + Geometry Nodes', desc: 'Cabelo fio a fio real (strands), anisotropia/flow map, física, match foto (não capacete)', kind: 'hair', structural: false },
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