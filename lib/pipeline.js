const fs = require('fs');
const path = require('path');

// Etapas do pipeline v2 (seção 7.5 do PROJETO_IA_3D_AAA.md), na ordem de execução.
// `model` = o motor real que plugaria aqui; `kind` = como o viewer three.js representa o preview.
const STAGES = [
  { id: 'multiview', title: 'Vistas Multi-View', model: 'PSHuman / MagicMan', desc: 'Vistas ortográficas condicionadas na foto.', kind: 'views' },
  { id: 'gate', title: 'Gate de Identidade', model: 'ArcFace + LPIPS', desc: 'Compara render vs foto. Reprova = regera vistas.', kind: 'metric' },
  { id: 'segment', title: 'Segmentação de Camadas', model: 'Florence-2', desc: 'Separa pele / roupa / cabelo / acessórios.', kind: 'layers' },
  { id: 'skeleton', title: 'Esqueleto / Ossos', model: 'SKEL · ATLAS/MHR (via HSMR)', desc: 'Ossos biomecânicos ajustados à silhueta.', kind: 'skeleton' },
  { id: 'muscle', title: 'Músculo & Volume', model: 'HIT + Chaos Flesh', desc: 'Tecido implícito (músculo/gordura/osso).', kind: 'mesh' },
  { id: 'garment', title: 'Roupa (camadas)', model: 'GarmentCode → drape (Warp/Newton)', desc: 'Padrão de costura drapeado sobre o corpo.', kind: 'garment' },
  { id: 'hair', title: 'Cabelo (fio a fio)', model: 'DiffLocks → Groom', desc: 'Strands reais ancorados no scalp.', kind: 'hair' },
  { id: 'skin', title: 'Pele (displacement)', model: 'loop nvdiffrast', desc: 'Poros/rugas como displacement, otimizado vs foto.', kind: 'mesh' },
  { id: 'final', title: 'Modelo Final', model: 'Rig SKEL + GLB PBR', desc: 'Malhas + rig + blendshapes ARKit, modular.', kind: 'final' },
];
const STAGE_IDS = STAGES.map((s) => s.id);

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
  const regions = { quadril: 'hip', ombro: 'shoulder', ombros: 'shoulder', busto: 'bust', peito: 'bust', cintura: 'waist', 'músculo': 'muscle', musculo: 'muscle', musculatura: 'muscle' };
  const REG = '(quadril|ombros?|busto|peito|cintura|m[úu]sculo|musculatura)';
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

  return { params: p, applied };
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
      model: meta.model,
      desc: meta.desc,
      kind: meta.kind,
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
    done: idx >= STAGE_IDS.length,
    params: job.params || defaultParams(),
    edits: job.edits || [],
    stages: publicStages(job),
  };
}

module.exports = { STAGES, STAGE_IDS, newJob, activeIndex, publicJob, publicStages, defaultParams, applyPromptCommand };
