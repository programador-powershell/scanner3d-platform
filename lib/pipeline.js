const fs = require('fs');
const path = require('path');

// Os 9 portões de validação sequencial (seção 10.2 do PROJETO_IA_3D_AAA.md), na ordem.
// `model` = o motor real que plugaria aqui; `kind` = como o viewer three.js representa o preview.
// `structural: true` = mudanças nesse domínio disparam o recálculo em cascata (Músculos→Tecido).
const STAGES = [
  { id: 'skeleton', title: 'Esqueleto', icon: '🦴', model: 'Z-Anatomy (ossos reais) + MPFB2 rig', desc: 'Crânio, coluna, costelas, pélvis, ossos longos pareados (humano real).', kind: 'skeleton', structural: true },
  { id: 'veins', title: 'Veias', icon: '🩸', model: 'Z-Anatomy (vascular) + SSS 8K', desc: 'Rede venosa subdérmica retroiluminada com thickness map.', kind: 'veins' },
  { id: 'muscle', title: 'Músculos', icon: '💪', model: 'Z-Anatomy (muscular) + Chaos Flesh', desc: 'Volumes musculares nomeados, deformáveis e colisores físicos.', kind: 'muscle', structural: true },
  { id: 'garment', title: 'Tecido', icon: '🪡', model: 'GarmentCode → drape (Warp/Newton) sobre MPFB2', desc: 'Padrão de costura drapeado no corpo MPFB2; vento e gravidade reais.', kind: 'garment' },
  { id: 'skin', title: 'Pele', icon: '🧫', model: 'MPFB2 skin + texturas 8K CC0 + nvdiffrast', desc: 'PBR fotorrealista com poros reais (Polyhaven/FFHQ-UV).', kind: 'skin' },
  { id: 'nails', title: 'Unhas', icon: '💅', model: 'MPFB2 (dedos) + material PBR', desc: 'Formato, curvatura, cutícula, lúnula no template humano.', kind: 'nails' },
  { id: 'face', title: 'Rosto', icon: '👤', model: 'MPFB2 face + 52 ARKit blendshapes', desc: 'Topologia humana, loops de animação e linhas de expressão.', kind: 'face' },
  { id: 'eyes', title: 'Olhos', icon: '👁️', model: 'MPFB2 globos + shader córnea/íris', desc: 'Íris, córnea com refração, umidade lacrimal.', kind: 'eyes' },
  { id: 'hair', title: 'Cabelo', icon: '💇', model: 'Hair Curves Blender + Geometry Nodes (pelos)', desc: 'Strands reais + pelo corporal (sobrancelhas, cílios, barba).', kind: 'hair' },
];
const STAGE_IDS = STAGES.map((s) => s.id);
const STRUCTURAL_KEYS = ['height_m', 'hip', 'shoulder', 'bust', 'waist', 'muscle']; // disparam cascata

// Parâmetros editáveis por prompt ("mude altura para 1,70", "aumente 20% o quadril"...).
// Multiplicadores baseline 1.0; altura em metros baseline 1.70; pele em hex.
function defaultParams() {
  return { height_m: 1.7, hip: 1, shoulder: 1, bust: 1, waist: 1, muscle: 1, skin: '#c9a08a', wind: 0 };
}

function newJob(id, sourceImage) {
  const stages = {};
  for (const s of STAGES) {
    stages[s.id] = { status: 'pending', approach: 0, history: [] };
  }
  stages[STAGES[0].id].status = 'running';
  return {
    id,
    sourceImage, // relpath dentro de /uploads
    createdAt: new Date().toISOString(),
    currentStageIndex: 0,
    params: defaultParams(),
    edits: [], // histórico de comandos de prompt (sinal de condicionamento p/ a LLM)
    stages,
  };
}

// Aplica um comando em pt-BR aos parâmetros. Retorna {params, applied:[...descrições]}.
function applyPromptCommand(params, command) {
  const p = { ...defaultParams(), ...(params || {}) };
  const cmd = String(command || '').toLowerCase();
  const applied = [];

  // altura: "altura (para)? 1,70" / "1.70 m"
  let m = cmd.match(/altura[^0-9]*([0-9]+[.,][0-9]+|[0-9]{2,3})/);
  if (m) {
    let v = parseFloat(m[1].replace(',', '.'));
    if (v > 100) v = v / 100; // "170" → 1.70
    if (v >= 1.2 && v <= 2.3) { p.height_m = +v.toFixed(2); applied.push(`altura = ${p.height_m} m`); }
  }

  // percentuais por região, nas duas ordens:
  //   "aumente 20% (o) quadril"  e  "aumente (o) quadril em 20%"
  const regions = { quadril: 'hip', ombro: 'shoulder', ombros: 'shoulder', busto: 'bust', peito: 'bust', cintura: 'waist', 'músculo': 'muscle', musculo: 'muscle', musculatura: 'muscle', coxa: 'muscle', coxas: 'muscle', perna: 'muscle', pernas: 'muscle' };
  const REG = '(quadril|ombros?|busto|peito|cintura|m[úu]sculo|musculatura|coxas?|pernas?)';
  const DIR = '(aument\\w*|sobe|subir|maior|engros\\w*|alarg\\w*|diminu\\w*|reduz\\w*|menor|estreit\\w*|afin\\w*)';
  const applyPct = (dirWord, region, pctStr) => {
    const key = regions[region];
    if (!key) return;
    const dir = /aument|sobe|subir|maior|engros|alarg/.test(dirWord) ? 1 : -1;
    const pct = Math.min(80, parseInt(pctStr, 10)) / 100;
    p[key] = Math.max(0.4, Math.min(2.2, p[key] * (1 + dir * pct)));
    applied.push(`${region} ${dir > 0 ? '+' : '-'}${pctStr}%`);
  };
  let mm;
  const reA = new RegExp(`${DIR}[^%]*?(\\d{1,3})\\s*%[^%]*?${REG}`, 'g'); // dir % região
  while ((mm = reA.exec(cmd))) applyPct(mm[1], mm[3], mm[2]);
  const reB = new RegExp(`${DIR}[^0-9]*?${REG}[^0-9]*?(\\d{1,3})\\s*%`, 'g'); // dir região %
  while ((mm = reB.exec(cmd))) applyPct(mm[1], mm[2], mm[3]);

  // tom de pele
  const tones = {
    'muito clara': '#e9c9b0', clara: '#e0b89c', branca: '#e0b89c', morena: '#b07d5c',
    parda: '#a06a47', pardo: '#a06a47', oliva: '#9c7a55', negra: '#5e3c2a', escura: '#6b4630', preta: '#4d3122',
  };
  for (const [name, hex] of Object.entries(tones)) {
    if (cmd.includes('pele') && cmd.includes(name)) { p.skin = hex; applied.push(`tom de pele = ${name}`); break; }
  }

  // vento / queda (resposta real de tecido)
  m = cmd.match(/vento[^0-9]*(\d{1,3})/);
  if (/vento|queda|caind|levant\w* o vestido/.test(cmd)) {
    p.wind = m ? Math.min(100, parseInt(m[1], 10)) / 100 : 0.7;
    applied.push(`vento/queda = ${Math.round(p.wind * 100)}%`);
  }

  // Marca se algum parâmetro estrutural mudou (dispara o recálculo em cascata).
  const prev = { ...defaultParams(), ...(params || {}) };
  const structural = STRUCTURAL_KEYS.some((k) => Math.abs((p[k] || 0) - (prev[k] || 0)) > 1e-6);

  return { params: p, applied, structural };
}

// Recálculo síncrono em cascata: um ajuste estrutural num portão avançado reabre
// Músculos e Tecido para revalidação (volta o activeIndex ao primeiro afetado).
// As camadas de superfície já aprovadas (Pele/Unhas/Rosto/Olhos/Cabelo) são preservadas (estilo).
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
  if (reopened.length) {
    // Reset EXPLÍCITO da máquina de estados: o ponteiro retrocede ao Portão 3
    // (Músculos) e o avanço automático fica bloqueado até nova aprovação —
    // comportamento linear bloqueante garantido, não derivado.
    job.currentStageIndex = muscleIdx;
    job.cascadePending = [...reopened];
  }
  return { cascaded: reopened.length > 0, reopened };
}

// Índice da primeira etapa que ainda não foi aprovada.
function activeIndex(job) {
  for (let i = 0; i < STAGE_IDS.length; i++) {
    if (job.stages[STAGE_IDS[i]].status !== 'approved') return i;
  }
  return STAGE_IDS.length; // tudo aprovado
}

function publicStages(job) {
  return STAGES.map((meta, i) => {
    const st = job.stages[meta.id];
    return {
      index: i,
      id: meta.id,
      title: meta.title,
      icon: meta.icon || '',
      model: meta.model,
      desc: meta.desc,
      kind: meta.kind,
      structural: !!meta.structural,
      status: st.status,
      approach: st.approach,
      attempts: st.history.length,
      lastImage: st.history.length ? st.history[st.history.length - 1].image : null,
      history: st.history.map((h) => ({ approach: h.approach, approved: h.approved, note: h.note, image: h.image, ts: h.ts })),
    };
  });
}

function publicJob(job) {
  const idx = activeIndex(job);
  return {
    id: job.id,
    sourceImage: job.sourceImage,
    createdAt: job.createdAt,
    activeIndex: idx,
    currentStageIndex: typeof job.currentStageIndex === 'number' ? job.currentStageIndex : idx,
    cascadePending: job.cascadePending || [],
    done: idx >= STAGE_IDS.length,
    params: job.params || defaultParams(),
    edits: job.edits || [],
    stages: publicStages(job),
  };
}

module.exports = { STAGES, STAGE_IDS, newJob, activeIndex, publicJob, publicStages, defaultParams, applyPromptCommand, applyCascade };
