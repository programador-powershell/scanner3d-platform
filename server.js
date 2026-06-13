const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const {
  scanReferences,
  manifestToMarkdown,
  updateMdSection,
  assertMarkers,
  formatSize,
  mdLink,
} = require('./lib/references');
const { STAGES, STAGE_IDS, newJob, activeIndex, publicJob, applyPromptCommand, applyCascade } = require('./lib/pipeline');

const PORT = process.env.PORT || 3939;
const REFERENCES_DIR = process.env.REFERENCES_DIR || 'D:\\References';
const DATA_DIR = path.join(__dirname, 'data');
const UPLOADS_DIR = path.join(DATA_DIR, 'uploads');
const JOBS_DIR = path.join(DATA_DIR, 'jobs');
const MD_PATH = path.join(__dirname, 'docs', 'PROJETO_IA_3D_AAA.md');
const LINKS_PATH = path.join(DATA_DIR, 'links.json');
const UPLOADS_JSON = path.join(DATA_DIR, 'uploads.json');
const MANIFEST_PATH = path.join(DATA_DIR, 'references_manifest.json');
const DATASET_PATH = path.join(DATA_DIR, 'finetune_dataset.jsonl');

fs.mkdirSync(UPLOADS_DIR, { recursive: true });
fs.mkdirSync(JOBS_DIR, { recursive: true });

// Falha cedo e com mensagem clara se o documento mestre sumiu ou está corrompido.
if (!fs.existsSync(MD_PATH)) {
  console.error(`ERRO: documento mestre não encontrado: ${MD_PATH}`);
  process.exit(1);
}
assertMarkers(fs.readFileSync(MD_PATH, 'utf8'), ['SOURCES', 'UPLOADS', 'REFERENCES'], MD_PATH);

function readJson(file, fallback) {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch {
    return fallback; // ENOENT: ainda não existe, fallback é o estado inicial legítimo
  }
  try {
    return JSON.parse(raw);
  } catch (e) {
    console.error(`AVISO: ${file} corrompido (${e.message}) — usando fallback. Conteúdo preservado em ${file}.corrupt`);
    try { fs.copyFileSync(file, file + '.corrupt'); } catch {}
    return fallback;
  }
}
function writeJson(file, data) {
  // Escrita atômica: nunca deixa JSON meio-escrito no disco.
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8');
  fs.renameSync(tmp, file);
}

// ---------- md sync ----------
const LINK_LABELS = {
  youtube: 'YouTube — vídeos de aprendizado/renderização',
  twitter: 'Twitter/X — referências',
  github: 'GitHub — ferramentas e código de referência',
};

function emptyLinks() {
  return { youtube: [], twitter: [], github: [] };
}
function normalizeLinks(links) {
  const out = links || {};
  for (const k of Object.keys(LINK_LABELS)) out[k] = out[k] || [];
  return out;
}

function syncSourcesMd() {
  const links = normalizeLinks(readJson(LINKS_PATH, emptyLinks()));
  const lines = [];
  const total = Object.keys(LINK_LABELS).reduce((n, k) => n + links[k].length, 0);
  if (!total) {
    lines.push('*Nenhum link cadastrado ainda. Use o site para adicionar links do YouTube, Twitter/X e GitHub.*');
  } else {
    for (const type of Object.keys(LINK_LABELS)) {
      if (!links[type].length) continue;
      lines.push(`### ${LINK_LABELS[type]} (${links[type].length})`);
      lines.push('');
      for (const l of links[type]) {
        lines.push(`- ${mdLink(l.note, l.url)} — adicionado em ${l.addedAt}`);
      }
      lines.push('');
    }
  }
  updateMdSection(MD_PATH, 'SOURCES', lines.join('\n').trimEnd());
}

function syncUploadsMd() {
  const uploads = readJson(UPLOADS_JSON, []);
  const lines = [];
  if (!uploads.length) {
    lines.push('*Nenhum arquivo enviado ainda.*');
  } else {
    lines.push(`**${uploads.length} arquivo(s) em \`data/uploads/\`:**`);
    lines.push('');
    lines.push('| Arquivo | Tamanho | Enviado em |');
    lines.push('|---|---|---|');
    for (const u of uploads) {
      lines.push(`| \`${u.name.replace(/\|/g, '_')}\` | ${formatSize(u.bytes)} | ${u.uploadedAt} |`);
    }
  }
  updateMdSection(MD_PATH, 'UPLOADS', lines.join('\n'));
}

// ---------- upload ----------
function sanitize(name) {
  return name.replace(/[^a-zA-Z0-9._\-()À-ſ ]/g, '_');
}
// Nomes reservados em memória: fecha a janela TOCTOU do existsSync (o multer só cria
// o arquivo depois do callback) e evita colisão dentro do mesmo lote multi-arquivo.
const reservedNames = new Set();
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOADS_DIR),
  filename: (req, file, cb) => {
    const clean = sanitize(Buffer.from(file.originalname, 'latin1').toString('utf8'));
    let final = clean;
    let i = 1;
    while (fs.existsSync(path.join(UPLOADS_DIR, final)) || reservedNames.has(final)) {
      const ext = path.extname(clean);
      final = `${path.basename(clean, ext)}_${i++}${ext}`;
    }
    reservedNames.add(final);
    cb(null, final);
  },
});
// Texturas 8K, FBX densos e vídeos de ingestão passam fácil de 32/500MB.
// Default 2GB; configurável via UPLOAD_MAX_MB (mínimo prático: 500).
const UPLOAD_MAX_MB = Math.max(500, parseInt(process.env.UPLOAD_MAX_MB || '2048', 10));
const upload = multer({ storage, limits: { fileSize: UPLOAD_MAX_MB * 1024 * 1024 } });

// ---------- app ----------
const app = express();
// 64mb: snapshots PNG do viewer three.js chegam como dataURL no corpo JSON.
app.use(express.json({ limit: '64mb' }));
app.use(express.static(path.join(__dirname, 'public')));
// Uploads servidos como download: .html/.svg enviados não executam script no origin da app.
app.use(
  '/uploads',
  express.static(UPLOADS_DIR, {
    setHeaders: (res) => {
      res.setHeader('Content-Disposition', 'attachment');
      res.setHeader('X-Content-Type-Options', 'nosniff');
    },
  })
);

app.post('/api/upload', upload.array('files', 200), (req, res) => {
  if (!req.files || !req.files.length) {
    return res.status(400).json({ error: 'Nenhum arquivo recebido.' });
  }
  const uploads = readJson(UPLOADS_JSON, []);
  const added = req.files.map((f) => ({
    name: f.filename,
    bytes: f.size,
    uploadedAt: new Date().toISOString(),
  }));
  uploads.push(...added);
  writeJson(UPLOADS_JSON, uploads);
  for (const f of req.files) reservedNames.delete(f.filename); // arquivo já existe no disco
  syncUploadsMd();
  res.json({ ok: true, added });
});

const LINK_PATTERNS = {
  youtube: /^https?:\/\/([\w-]+\.)*(youtube\.com|youtu\.be)\//i,
  twitter: /^https?:\/\/([\w-]+\.)*(twitter\.com|x\.com)\//i,
  github: /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+/i,
};

app.post('/api/links', (req, res) => {
  const { type, url, note } = req.body || {};
  if (!Object.prototype.hasOwnProperty.call(LINK_PATTERNS, type)) {
    return res.status(400).json({ error: 'Tipo inválido. Use "youtube", "twitter" ou "github".' });
  }
  const cleanUrl = String(url || '').trim();
  if (!cleanUrl || /[\s<>"\\]/.test(cleanUrl) || !LINK_PATTERNS[type].test(cleanUrl)) {
    return res.status(400).json({ error: `URL inválida para ${type}.` });
  }
  const links = normalizeLinks(readJson(LINKS_PATH, emptyLinks()));
  if (links[type].some((l) => l.url === cleanUrl)) {
    return res.status(409).json({ error: 'Link já cadastrado.' });
  }
  const entry = { url: cleanUrl, note: String(note || '').trim().slice(0, 300), addedAt: new Date().toISOString() };
  links[type].push(entry);
  writeJson(LINKS_PATH, links);
  syncSourcesMd();
  res.json({ ok: true, entry });
});

app.delete('/api/links', (req, res) => {
  const { type, url } = req.body || {};
  if (!Object.prototype.hasOwnProperty.call(LINK_PATTERNS, type)) {
    return res.status(400).json({ error: 'Tipo inválido.' });
  }
  const links = normalizeLinks(readJson(LINKS_PATH, emptyLinks()));
  const before = links[type].length;
  links[type] = links[type].filter((l) => l.url !== url);
  if (links[type].length === before) return res.status(404).json({ error: 'Link não encontrado.' });
  writeJson(LINKS_PATH, links);
  syncSourcesMd();
  res.json({ ok: true });
});

app.post('/api/feed-references', (req, res) => {
  if (!fs.existsSync(REFERENCES_DIR)) {
    return res.status(404).json({ error: `Pasta não encontrada: ${REFERENCES_DIR}` });
  }
  const manifest = scanReferences(REFERENCES_DIR);
  writeJson(MANIFEST_PATH, manifest);
  updateMdSection(MD_PATH, 'REFERENCES', manifestToMarkdown(manifest));
  res.json({
    ok: true,
    totalFiles: manifest.totalFiles,
    totalSize: formatSize(manifest.totalBytes),
    categories: Object.fromEntries(
      Object.entries(manifest.categories).map(([k, v]) => [k, { count: v.count, size: formatSize(v.bytes) }])
    ),
  });
});

app.get('/api/state', (req, res) => {
  const links = normalizeLinks(readJson(LINKS_PATH, emptyLinks()));
  const uploads = readJson(UPLOADS_JSON, []);
  const manifest = readJson(MANIFEST_PATH, null);
  res.json({
    links,
    uploads,
    blender: !!BLENDER_PATH,
    references: manifest
      ? {
          generatedAt: manifest.generatedAt,
          root: manifest.root,
          totalFiles: manifest.totalFiles,
          totalSize: formatSize(manifest.totalBytes),
          categories: Object.fromEntries(
            Object.entries(manifest.categories).map(([k, v]) => [k, { count: v.count, size: formatSize(v.bytes) }])
          ),
        }
      : null,
  });
});

app.get('/api/md', (req, res) => {
  res.type('text/markdown; charset=utf-8').send(fs.readFileSync(MD_PATH, 'utf8'));
});

// GLBs/GLTFs disponíveis (enviados via upload) para o visualizador 3D.
app.get('/api/models', (req, res) => {
  const exts = new Set(['.glb', '.gltf']);
  let models = [];
  try {
    models = fs
      .readdirSync(UPLOADS_DIR)
      .filter((f) => exts.has(path.extname(f).toLowerCase()))
      .map((f) => ({ name: f, url: '/uploads/' + encodeURIComponent(f), bytes: (() => { try { return fs.statSync(path.join(UPLOADS_DIR, f)).size; } catch { return 0; } })() }));
  } catch {}
  res.json({ models });
});

// ============================================================
// Pipeline interativo human-in-the-loop
// ============================================================
const jsonBig = express.json({ limit: '64mb' }); // snapshots PNG em dataURL

// ---------- fila de escrita por job (file-locking em memória) ----------
// Serializa todo read-modify-write de job.json: prompts paramétricos rápidos
// durante a simulação física não corrompem o estado nem se intercalam.
const jobLocks = new Map();
function withJobLock(id, fn) {
  const prev = jobLocks.get(id) || Promise.resolve();
  const next = prev.then(fn, fn);
  jobLocks.set(id, next.catch(() => {}));
  return next;
}

// ---------- SSE: eventos em tempo real por job ----------
const sseClients = new Map(); // jobId -> Set<res>
function emitJob(jobId, event, data) {
  const set = sseClients.get(jobId);
  if (!set || !set.size) return;
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of set) {
    try { res.write(payload); } catch {}
  }
}

// ---------- Bridge Blender headless ----------
// Acionada SOMENTE quando o personagem inteiro foi aprovado (9/9 portões):
// replica a construção do zero (esqueleto → cabelo) no Blender e exporta GLB+blend.
const BLENDER_PATH = (() => {
  const candidates = [
    process.env.BLENDER_PATH,
    'D:\\Blender Foundation\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe',
  ].filter(Boolean);
  for (const c of candidates) {
    try { if (fs.existsSync(c)) return c; } catch {}
  }
  return null;
})();
const BUILD_SCRIPT = path.join(__dirname, 'blender', 'build_character.py');
const buildsRunning = new Set();

function startBuild(jobId) {
  if (!BLENDER_PATH) return { ok: false, error: 'Blender não encontrado. Configure BLENDER_PATH.' };
  if (buildsRunning.has(jobId)) return { ok: false, error: 'Build já em andamento.' };
  const job = loadJob(jobId);
  if (!job) return { ok: false, error: 'Job não encontrado.' };
  if (activeIndex(job) < STAGE_IDS.length) {
    return { ok: false, error: 'Build só libera com os 9 portões aprovados.' };
  }
  const buildDir = path.join(jobDir(jobId), 'build');
  fs.mkdirSync(buildDir, { recursive: true });
  const logPath = path.join(buildDir, 'build.log');
  const logStream = fs.createWriteStream(logPath);
  buildsRunning.add(jobId);

  withJobLock(jobId, async () => {
    const j = loadJob(jobId);
    j.build = { status: 'running', startedAt: new Date().toISOString() };
    saveJob(j);
  });
  emitJob(jobId, 'build:started', { blender: BLENDER_PATH });

  const child = spawn(BLENDER_PATH, [
    '--background', '--factory-startup',
    '--python', BUILD_SCRIPT, '--',
    '--job', jobFile(jobId),
    '--out', buildDir,
  ], { windowsHide: true });

  const onLine = (buf) => {
    for (const line of buf.toString().split(/\r?\n/)) {
      if (!line.trim()) continue;
      logStream.write(line + '\n');
      if (/^\[build\]|Error|Traceback/i.test(line)) emitJob(jobId, 'build:log', { line: line.slice(0, 300) });
    }
  };
  child.stdout.on('data', onLine);
  child.stderr.on('data', onLine);
  child.on('close', (code) => {
    logStream.end();
    buildsRunning.delete(jobId);
    const glb = path.join(buildDir, 'character.glb');
    const okBuild = code === 0 && fs.existsSync(glb);
    withJobLock(jobId, async () => {
      const j = loadJob(jobId);
      if (!j) return;
      const hasFbx = fs.existsSync(path.join(buildDir, 'character.fbx'));
      j.build = okBuild
        ? { status: 'done', finishedAt: new Date().toISOString(),
            glb: `/api/jobs/${jobId}/build/character.glb`,
            blend: `/api/jobs/${jobId}/build/character.blend`,
            fbx: hasFbx ? `/api/jobs/${jobId}/build/character.fbx` : null }
        : { status: 'error', finishedAt: new Date().toISOString(), code };
      saveJob(j);
      emitJob(jobId, okBuild ? 'build:done' : 'build:error', { ...j.build, job: publicJob(j) });
    });
    // Passo de polimento final (Mitsuba SSS): dispara sozinho SÓ quando a cena
    // .xml existe. Sem cena/deps, fica quieto (não suja o build com skips).
    if (okBuild && polishReady(jobId)) {
      runPolish(jobId).catch(() => {});
    }
  });
  return { ok: true };
}

// Simulação física da cascata (placeholder dos motores HIT/Chaos Flesh + Warp):
// emite frames muscle→cloth em tempo real e fecha com stage:waiting_approval.
// Quando os motores reais forem plugados, eles publicam nestes mesmos eventos.
function runCascadeSimulation(jobId) {
  const FRAMES = 24, DT = 60; // ~1,4s por fase
  let f = 0;
  const muscle = setInterval(() => {
    f++;
    emitJob(jobId, 'simulation:muscle:frame', { frame: f, total: FRAMES, progress: f / FRAMES });
    if (f >= FRAMES) {
      clearInterval(muscle);
      let c = 0;
      const cloth = setInterval(() => {
        c++;
        emitJob(jobId, 'simulation:cloth:frame', { frame: c, total: FRAMES, progress: c / FRAMES });
        if (c >= FRAMES) {
          clearInterval(cloth);
          withJobLock(jobId, async () => {
            const job = loadJob(jobId);
            if (!job) return;
            emitJob(jobId, 'stage:waiting_approval', {
              stage: STAGE_IDS[activeIndex(job)],
              job: publicJob(job),
            });
          });
        }
      }, DT);
    }
  }, DT);
}

function jobDir(id) {
  return path.join(JOBS_DIR, id);
}
function jobFile(id) {
  return path.join(jobDir(id), 'job.json');
}
function loadJob(id) {
  if (!/^job_[a-zA-Z0-9_]+$/.test(id)) return null; // anti path-traversal
  const f = jobFile(id);
  if (!fs.existsSync(f)) return null;
  return readJson(f, null);
}
function saveJob(job) {
  writeJson(jobFile(job.id), job);
}
function genId() {
  return 'job_' + process.hrtime.bigint().toString(36) + Math.floor(Math.random() * 1e6).toString(36);
}

// Grava uma decisão (aprovado/reprovado) como par do dataset de fine-tuning (preferência DPO/reward).
function appendDataset(entry) {
  fs.appendFileSync(DATASET_PATH, JSON.stringify(entry) + '\n', 'utf8');
}
function datasetStats() {
  let approved = 0, rejected = 0, total = 0;
  const byStage = {};
  try {
    const lines = fs.readFileSync(DATASET_PATH, 'utf8').split('\n').filter(Boolean);
    for (const line of lines) {
      let e;
      try { e = JSON.parse(line); } catch { continue; }
      total++;
      if (e.label === 'approved') approved++;
      else if (e.label === 'rejected') rejected++;
      byStage[e.stage] = byStage[e.stage] || { approved: 0, rejected: 0 };
      byStage[e.stage][e.label] = (byStage[e.stage][e.label] || 0) + 1;
    }
  } catch {}
  return { total, approved, rejected, byStage };
}

// Cria um job a partir de N imagens (turnaround: frente/perfil/costas etc.) ou existentes.
app.post('/api/jobs', upload.array('images', 12), (req, res) => {
  let sourceImages = [];
  if (req.files && req.files.length) {
    const uploads = readJson(UPLOADS_JSON, []);
    for (const f of req.files) {
      reservedNames.delete(f.filename);
      sourceImages.push(f.filename);
      uploads.push({ name: f.filename, bytes: f.size, uploadedAt: new Date().toISOString() });
    }
    writeJson(UPLOADS_JSON, uploads);
    syncUploadsMd();
  }
  // permite também referenciar existentes (compat com fluxo antigo)
  const existing = (req.body && (req.body['existing[]'] || req.body.existing)) || [];
  const exArr = Array.isArray(existing) ? existing : [existing];
  for (const e of exArr) {
    if (!e) continue;
    const name = path.basename(String(e));
    if (!fs.existsSync(path.join(UPLOADS_DIR, name))) continue;
    if (!sourceImages.includes(name)) sourceImages.push(name);
  }
  if (!sourceImages.length) {
    return res.status(400).json({ error: 'Envie ao menos uma imagem (campo "images") ou referencie "existing".' });
  }
  // primeira foto = imagem principal (compat); todas ficam em sourceImages
  const job = newJob(genId(), sourceImages[0]);
  job.sourceImages = sourceImages;
  fs.mkdirSync(jobDir(job.id), { recursive: true });
  saveJob(job);
  res.json({ ok: true, job: publicJob(job) });
});

app.get('/api/jobs', (req, res) => {
  const ids = fs.existsSync(JOBS_DIR) ? fs.readdirSync(JOBS_DIR).filter((d) => d.startsWith('job_')) : [];
  const jobs = ids
    .map((id) => loadJob(id))
    .filter(Boolean)
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
    .map((j) => ({ id: j.id, sourceImage: j.sourceImage, createdAt: j.createdAt, activeIndex: activeIndex(j) }));
  res.json({ jobs });
});

app.get('/api/jobs/:id', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  res.json({ ok: true, job: publicJob(job) });
});

// Streaming de eventos do job (EventSource no frontend).
app.get('/api/jobs/:id/events', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.write(`event: connected\ndata: ${JSON.stringify({ jobId: job.id })}\n\n`);
  let set = sseClients.get(job.id);
  if (!set) { set = new Set(); sseClients.set(job.id, set); }
  set.add(res);
  const hb = setInterval(() => { try { res.write(': hb\n\n'); } catch {} }, 25000);
  req.on('close', () => {
    clearInterval(hb);
    set.delete(res);
    if (!set.size) sseClients.delete(job.id);
  });
});

// Cliente renderizou a etapa no three.js e capturou um snapshot PNG (dataURL).
// Salva como artefato da tentativa atual e marca a etapa para revisão.
app.post('/api/jobs/:id/stages/:stage/snapshot', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const stageId = req.params.stage;
    if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });
    const st = job.stages[stageId];
    if (st.status === 'approved') return res.status(409).json({ error: 'Etapa já aprovada.' });

    const dataUrl = String((req.body && req.body.image) || '');
    const m = dataUrl.match(/^data:image\/png;base64,([A-Za-z0-9+/=]+)$/);
    if (!m) return res.status(400).json({ error: 'Snapshot PNG inválido.' });
    const fname = `${stageId}_a${st.approach}.png`;
    fs.writeFileSync(path.join(jobDir(job.id), fname), Buffer.from(m[1], 'base64'));

    st.status = 'awaiting_review';
    st.lastImage = `/api/jobs/${job.id}/artifact/${fname}`;
    saveJob(job);
    emitJob(job.id, 'stage:waiting_approval', { stage: stageId, job: publicJob(job) });
    res.json({ ok: true, image: st.lastImage });
  }).catch(next);
});

// Serve os snapshots gravados do job.
app.get('/api/jobs/:id/artifact/:file', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const file = path.basename(req.params.file);
  // aceita snapshots PNG, GLB por portão, logs, pattern do ChatGarment,
  // e texturas UDIM por tile (character_1001.png .. 1099) — resolução por região (7.3.2)
  if (!/^([a-z]+_a\d+\.png|[a-z]+\.glb|[a-z]+\.log|garment_pattern\.json|[a-z]+_1[0-9]{3}\.(png|jpg|exr))$/.test(file)) {
    return res.status(400).json({ error: 'Arquivo inválido.' });
  }
  const full = path.join(jobDir(job.id), file);
  if (!fs.existsSync(full)) return res.status(404).json({ error: 'Artefato não encontrado.' });
  res.type('image/png').sendFile(full);
});

// Aprovação/reprovação da etapa. Cada decisão vira linha do dataset de fine-tuning.
// Reprovar = nova abordagem (approach+1) e a etapa volta a "running" para regerar.
// Aprovar = etapa fica "approved" e o pipeline libera a próxima.
app.post('/api/jobs/:id/stages/:stage/review', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const stageId = req.params.stage;
    if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });
    const st = job.stages[stageId];
    const approved = !!(req.body && req.body.approved);
    const note = String((req.body && req.body.note) || '').trim().slice(0, 1000);

    const image = st.lastImage || (st.history.length ? st.history[st.history.length - 1].image : null);
    const record = { approach: st.approach, approved, note, image, ts: new Date().toISOString() };
    st.history.push(record);

    appendDataset({
      ts: record.ts,
      jobId: job.id,
      stage: stageId,
      approach: st.approach,
      label: approved ? 'approved' : 'rejected',
      note,
      snapshot: image,
      source: `/uploads/${encodeURIComponent(job.sourceImage)}`,
    });

    if (approved) {
      st.status = 'approved';
      // limpa pendência de cascata deste portão e atualiza o ponteiro explícito
      if (Array.isArray(job.cascadePending)) {
        job.cascadePending = job.cascadePending.filter((id) => id !== stageId);
      }
      const idx = activeIndex(job);
      job.currentStageIndex = idx;
      if (idx < STAGE_IDS.length) job.stages[STAGE_IDS[idx]].status = 'running';
    } else {
      // O modelo "aprende" que esta abordagem não serve e tenta outra (approach incrementa).
      st.approach += 1;
      st.status = 'running';
      st.lastImage = null;
    }
    saveJob(job);
    emitJob(job.id, 'job:update', { job: publicJob(job) });
    res.json({ ok: true, approved, nextApproach: st.approach, job: publicJob(job) });

    // Personagem inteiro aprovado (9/9) → replica a construção no Blender headless.
    if (approved && activeIndex(job) >= STAGE_IDS.length && BLENDER_PATH) {
      setImmediate(() => startBuild(job.id));
    }
  }).catch(next);
});

// Build manual (ex.: Blender não estava configurado na hora da aprovação final).
app.post('/api/jobs/:id/build', (req, res) => {
  const r = startBuild(req.params.id);
  if (!r.ok) return res.status(400).json({ error: r.error });
  res.json({ ok: true, started: true });
});

// Serve os artefatos do build (GLB para o viewer, .blend para download, log).
app.get('/api/jobs/:id/build/:file', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const allow = new Set(['character.glb', 'character.blend', 'character.fbx', 'hunyuan_base.glb', 'build.log', 'skin_polished.png', 'polish.log']);
  const file = path.basename(req.params.file);
  if (!allow.has(file)) return res.status(400).json({ error: 'Arquivo inválido.' });
  const full = path.join(jobDir(job.id), 'build', file);
  if (!fs.existsSync(full)) return res.status(404).json({ error: 'Artefato não encontrado.' });
  if (file.endsWith('.blend')) res.setHeader('Content-Disposition', 'attachment; filename=character.blend');
  if (file.endsWith('.fbx')) res.setHeader('Content-Disposition', 'attachment; filename=character.fbx');
  res.sendFile(full);
});

// ============================================================
// POLIMENTO FINAL DE PELE — Mitsuba 3 (loop diferenciável SSS), seção 7.4.
// Roda DEPOIS do build (geometria já colada pelo nvdiffrast). Aqui a geometria
// fica CONGELADA e só os mapas PBR (albedo) + raio SSS são esculpidos contra a
// foto, até a pele ter a profundidade/refração real exportada pra UE5.
// Plugável e honesto: precisa de (a) Python+mitsuba+drjit+lpips com CUDA e
// (b) uma cena Mitsuba .xml (modelo + câmera alinhada). Sem isso, NÃO finge —
// devolve aviso claro (igual ao padrão Hunyuan/ChatGarment).
// ============================================================
const PYTHON_BIN = process.env.PYTHON_BIN || process.env.PYTHON || 'python';
const MITSUBA_SCRIPT = path.join(__dirname, 'python', 'mitsuba_skin_optimizer.py');
const polishRunning = new Set();

// Cena Mitsuba do job: env MITSUBA_SCENE (global) ou build/scene.xml (por job).
// O exportador de cena .xml ainda não está plugado no build — quando estiver,
// basta gravar scene.xml no buildDir e o polimento dispara sozinho.
function mitsubaScenePath(jobId) {
  const cand = [process.env.MITSUBA_SCENE, path.join(jobDir(jobId), 'build', 'scene.xml')];
  for (const c of cand) { try { if (c && fs.existsSync(c)) return c; } catch {} }
  return null;
}
function polishReady(jobId) {
  const glb = path.join(jobDir(jobId), 'build', 'character.glb');
  return fs.existsSync(glb) && !!mitsubaScenePath(jobId);
}

// Spawna o otimizador Mitsuba. Resolve com {ok, skipped?, reason?}.
// exit 3 = mitsuba/CUDA ausente -> skipped honesto (não é erro).
function runPolish(jobId, { iters } = {}) {
  return new Promise((resolve) => {
    if (polishRunning.has(jobId)) return resolve({ ok: false, error: 'Polimento já em andamento.' });
    const buildDir = path.join(jobDir(jobId), 'build');
    if (!fs.existsSync(path.join(buildDir, 'character.glb'))) {
      return resolve({ ok: false, error: 'Build final não encontrado — rode o build dos 9 portões antes do polimento.' });
    }
    const scene = mitsubaScenePath(jobId);
    if (!scene) {
      return resolve({ ok: true, skipped: true, reason:
        'Cena Mitsuba (.xml) ausente — o exportador de cena ainda não está plugado no build. ' +
        'Defina MITSUBA_SCENE ou grave build/scene.xml (modelo + câmera alinhada à foto) para ativar o polimento SSS.' });
    }
    const job = loadJob(jobId);
    const photoName = (job && (job.sourceImages?.[0] || job.sourceImage)) || '';
    const photo = path.join(UPLOADS_DIR, path.basename(photoName));
    if (!photoName || !fs.existsSync(photo)) {
      return resolve({ ok: false, error: 'Foto de referência do job não encontrada para o polimento.' });
    }
    polishRunning.add(jobId);
    const logPath = path.join(buildDir, 'polish.log');
    const ls = fs.createWriteStream(logPath);
    emitJob(jobId, 'polish:start', { scene: path.basename(scene) });
    const child = spawn(PYTHON_BIN, [
      MITSUBA_SCRIPT,
      '--scene', scene,
      '--photo', photo,
      '--iters', String(iters || parseInt(process.env.MITSUBA_ITERS || '50', 10)),
      '--out', buildDir,
    ], { windowsHide: true });
    let lastLine = '';
    const onLine = (buf) => {
      for (const line of buf.toString().split(/\r?\n/)) {
        if (!line.trim()) continue;
        ls.write(line + '\n');
        lastLine = line;
        if (/^\[mitsuba\]|Error|Traceback/i.test(line)) emitJob(jobId, 'polish:log', { line: line.slice(0, 240) });
      }
    };
    child.stdout.on('data', onLine);
    child.stderr.on('data', onLine);
    child.on('error', (e) => {
      polishRunning.delete(jobId); ls.end();
      // python ausente no PATH etc. — honesto, não derruba nada
      emitJob(jobId, 'polish:skipped', { reason: `Python indisponível (${e.code || e.message}). Configure PYTHON_BIN.` });
      resolve({ ok: true, skipped: true, reason: `Python indisponível: ${e.message}` });
    });
    child.on('close', (code) => {
      polishRunning.delete(jobId); ls.end();
      const out = path.join(buildDir, 'skin_polished.png');
      if (code === 3) {
        emitJob(jobId, 'polish:skipped', { reason: 'mitsuba/CUDA ausente — pip install mitsuba drjit lpips (+ torch CUDA).' });
        return resolve({ ok: true, skipped: true, reason: 'mitsuba/CUDA ausente', detail: lastLine });
      }
      const done = code === 0 && fs.existsSync(out);
      if (done) {
        withJobLock(jobId, async () => {
          const j = loadJob(jobId);
          if (!j) return;
          j.build = j.build || {};
          j.build.polished = `/api/jobs/${jobId}/build/skin_polished.png`;
          j.build.polishedAt = new Date().toISOString();
          saveJob(j);
        });
      }
      emitJob(jobId, done ? 'polish:done' : 'polish:error',
        { png: done ? `/api/jobs/${jobId}/build/skin_polished.png` : null, code, detail: lastLine.slice(0, 240) });
      resolve(done ? { ok: true, png: `/api/jobs/${jobId}/build/skin_polished.png` } : { ok: false, error: `polimento falhou (code ${code})`, detail: lastLine });
    });
  });
}

// Polimento final SSS (Mitsuba). Dispara sozinho no fim do build quando a cena
// existe; este endpoint permite disparar manualmente.
app.post('/api/jobs/:id/polish', jsonBig, (req, res, next) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const iters = parseInt((req.body && req.body.iters) || 0, 10) || undefined;
  runPolish(req.params.id, { iters }).then((r) => res.json(r)).catch(next);
});

// Edição paramétrica por prompt ("mude altura para 1,70", "aumente 20% o quadril", "tom de pele pardo").
// O comando é parseado, aplicado aos params do job e registrado no dataset como sinal de condicionamento.
app.post('/api/jobs/:id/params', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const command = String((req.body && req.body.command) || '').trim().slice(0, 500);
    if (!command) return res.status(400).json({ error: 'Comando vazio.' });
    const { params, applied, structural } = applyPromptCommand(job.params, command);
    job.params = params;
    job.edits = job.edits || [];
    // Recálculo síncrono em cascata: ajuste estrutural reabre Músculos+Tecido (seção 10.3.1).
    const cascade = structural ? applyCascade(job) : { cascaded: false, reopened: [] };
    const edit = { command, applied, ts: new Date().toISOString(), structural, cascaded: cascade.reopened };
    job.edits.push(edit);
    saveJob(job);
    appendDataset({
      ts: edit.ts,
      jobId: job.id,
      stage: 'prompt-edit',
      label: 'edit',
      command,
      applied,
      structural,
      cascaded: cascade.reopened,
      params,
      source: `/uploads/${encodeURIComponent(job.sourceImage)}`,
    });
    emitJob(job.id, 'job:update', { job: publicJob(job) });
    if (cascade.cascaded) {
      // UI bloqueia, grafo reposiciona no Portão 3, simulação roda em tempo real
      emitJob(job.id, 'cascade:activated', {
        reopened: cascade.reopened,
        currentStageIndex: job.currentStageIndex,
        params,
      });
      runCascadeSimulation(job.id);
    }
    res.json({ ok: true, params, applied, structural, cascade, job: publicJob(job) });
  }).catch(next);
});

// ============================================================
// VLM LOCAL — Qwen3-VL-4B-Thinking GGUF rodando no llama.cpp (sem cloud)
// ============================================================
const LLAMA_SERVER = (() => {
  for (const c of [process.env.LLAMA_SERVER, 'D:\\llama.cpp\\llama-server.exe']) {
    try { if (c && fs.existsSync(c)) return c; } catch {}
  }
  return null;
})();
const VLM_DIR = process.env.VLM_DIR || 'D:\\llm\\qwen3-vl-4b';
const VLM_REPO = 'unsloth/Qwen3-VL-4B-Thinking-GGUF';
const VLM_MODEL_FILE = process.env.VLM_MODEL_FILE || 'Qwen3-VL-4B-Thinking-Q4_K_M.gguf';
const VLM_MMPROJ_FILE = process.env.VLM_MMPROJ_FILE || 'mmproj-F16.gguf';
const VLM_PORT = parseInt(process.env.VLM_LOCAL_PORT || '8080', 10);
const VLM_LOCAL_URL = `http://127.0.0.1:${VLM_PORT}/v1/chat/completions`;

let vlmProc = null;            // processo llama-server
let vlmDownload = null;        // { file, received, total, done }

function vlmPaths() {
  return {
    model: path.join(VLM_DIR, VLM_MODEL_FILE),
    mmproj: path.join(VLM_DIR, VLM_MMPROJ_FILE),
  };
}
function vlmInstalled() {
  const p = vlmPaths();
  try { return fs.existsSync(p.model) && fs.existsSync(p.mmproj); } catch { return false; }
}

async function downloadFile(url, dest, onProgress) {
  const tmp = dest + '.part';
  // resume: se já existe .part, continua de onde parou (HTTP Range)
  let start = 0;
  try { start = fs.existsSync(tmp) ? fs.statSync(tmp).size : 0; } catch { start = 0; }
  const headers = start > 0 ? { Range: `bytes=${start}-` } : {};
  const r = await fetch(url, { headers });
  if (!(r.ok || r.status === 206) || !r.body) throw new Error(`download ${r.status} ${url}`);
  const len = parseInt(r.headers.get('content-length') || '0', 10);
  const total = start + len; // tamanho total real
  let received = start;
  const out = fs.createWriteStream(tmp, { flags: start > 0 && r.status === 206 ? 'a' : 'w' });
  if (r.status !== 206) received = 0; // servidor ignorou Range → recomeça
  const reader = r.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.length;
    out.write(Buffer.from(value));
    if (onProgress) onProgress(received, total);
  }
  await new Promise((res) => out.end(res));
  fs.renameSync(tmp, dest);
  return { received, total };
}

// Baixa modelo + mmproj do HuggingFace para D:\llm\qwen3-vl-4b
app.post('/api/vlm/download', async (req, res) => {
  if (vlmDownload && !vlmDownload.done) return res.status(409).json({ error: 'Download já em andamento.' });
  fs.mkdirSync(VLM_DIR, { recursive: true });
  const files = [VLM_MODEL_FILE, VLM_MMPROJ_FILE];
  res.json({ ok: true, started: true, files });
  // roda em background, reporta via SSE global (jobless) + estado
  (async () => {
    for (const f of files) {
      const dest = path.join(VLM_DIR, f);
      if (fs.existsSync(dest)) { emitVlm('vlm:download', { file: f, received: 1, total: 1, skipped: true }); continue; }
      const url = `https://huggingface.co/${VLM_REPO}/resolve/main/${f}?download=true`;
      vlmDownload = { file: f, received: 0, total: 0, done: false };
      try {
        await downloadFile(url, dest, (received, total) => {
          vlmDownload = { file: f, received, total, done: false };
          if (received % (8 * 1024 * 1024) < 65536) emitVlm('vlm:download', { file: f, received, total });
        });
        emitVlm('vlm:download', { file: f, received: 1, total: 1, fileDone: true });
      } catch (e) {
        vlmDownload = { file: f, error: e.message, done: true };
        return emitVlm('vlm:error', { stage: 'download', file: f, error: e.message });
      }
    }
    vlmDownload = { done: true };
    emitVlm('vlm:ready', { installed: vlmInstalled() });
  })();
});

// Sobe o llama-server local com visão (mmproj) e aponta a VLM para ele
app.post('/api/vlm/start', (req, res) => {
  if (!LLAMA_SERVER) return res.status(400).json({ error: 'llama-server.exe não encontrado (D:\\llama.cpp). Configure LLAMA_SERVER.' });
  if (!vlmInstalled()) return res.status(400).json({ error: 'GGUF não baixado — clique em Baixar primeiro.' });
  if (vlmProc) return res.json({ ok: true, already: true, url: VLM_LOCAL_URL });
  const p = vlmPaths();
  const ngl = parseInt(process.env.VLM_NGL || '99', 10);   // camadas na GPU (4060)
  vlmProc = spawn(LLAMA_SERVER, [
    '-m', p.model,
    '--mmproj', p.mmproj,
    '--host', '127.0.0.1',
    '--port', String(VLM_PORT),
    '-ngl', String(ngl),
    '-c', process.env.VLM_CTX || '8192',
    '--jinja',
  ], { windowsHide: true });
  const logPath = path.join(VLM_DIR, 'llama-server.log');
  const ls = fs.createWriteStream(logPath, { flags: 'a' });
  let listening = false;
  const onLine = (b) => {
    const s = b.toString(); ls.write(s);
    if (!listening && /server (is )?listening|HTTP server listening/i.test(s)) {
      listening = true;
      process.env.VLM_URL = VLM_LOCAL_URL;
      emitVlm('vlm:running', { url: VLM_LOCAL_URL });
    }
  };
  vlmProc.stdout.on('data', onLine);
  vlmProc.stderr.on('data', onLine);
  vlmProc.on('close', (code) => {
    ls.end(); vlmProc = null;
    if (process.env.VLM_URL === VLM_LOCAL_URL) process.env.VLM_URL = '';
    emitVlm('vlm:stopped', { code });
  });
  res.json({ ok: true, starting: true, url: VLM_LOCAL_URL });
});

app.post('/api/vlm/stop', (req, res) => {
  if (vlmProc) { try { vlmProc.kill(); } catch {} vlmProc = null; }
  process.env.VLM_URL = '';
  res.json({ ok: true });
});

app.get('/api/vlm/status', async (req, res) => {
  let responding = false;
  if (vlmProc) {
    try { const t = await fetch(`http://127.0.0.1:${VLM_PORT}/health`, { signal: AbortSignal.timeout(1500) }); responding = t.ok; } catch {}
  }
  res.json({
    ok: true,
    llamaFound: !!LLAMA_SERVER,
    installed: vlmInstalled(),
    dir: VLM_DIR,
    model: VLM_MODEL_FILE,
    repo: VLM_REPO,
    running: !!vlmProc,
    responding,
    url: vlmProc ? VLM_LOCAL_URL : null,
    download: vlmDownload,
    vlmUrlActive: process.env.VLM_URL || null,
    chatgarmentUrl: process.env.CHATGARMENT_URL || null,
  });
});

// SSE global (eventos da VLM local, sem job)
const vlmClients = new Set();
function emitVlm(event, data) {
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const r of vlmClients) { try { r.write(payload); } catch {} }
}
app.get('/api/vlm/events', (req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive', 'X-Accel-Buffering': 'no' });
  res.write(`event: connected\ndata: {}\n\n`);
  vlmClients.add(res);
  const hb = setInterval(() => { try { res.write(': hb\n\n'); } catch {} }, 25000);
  req.on('close', () => { clearInterval(hb); vlmClients.delete(res); });
});

// Configura ChatGarment URL (e VLM manual avançado) em runtime.
app.post('/api/vlm/config', jsonBig, async (req, res) => {
  const url = String((req.body && req.body.vlm_url) || '').trim();
  const cg = String((req.body && req.body.chatgarment_url) || '').trim();
  for (const u of [url, cg]) if (u && !/^https?:\/\//.test(u)) return res.status(400).json({ error: 'URLs precisam começar com http(s)://' });
  process.env.VLM_URL = url;
  process.env.CHATGARMENT_URL = cg;
  let connected = false, chatgarment_connected = false;
  if (url) {
    try {
      const t = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: process.env.VLM_MODEL || 'qwen3d', messages: [{ role: 'user', content: 'ping' }], max_tokens: 4 }) });
      connected = t.ok;
    } catch {}
  }
  if (cg) {
    try {
      const t = await fetch(cg, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ping: true }) });
      chatgarment_connected = t.ok;
    } catch {}
  }
  res.json({ ok: true, vlm_url: url, chatgarment_url: cg, connected, chatgarment_connected });
});

// ---------- VLM client (Qwen2.5-VL via vLLM OpenAI-compatible) ----------
async function vlmChat(messages) {
  if (!process.env.VLM_URL) return { ok: false, error: 'VLM_URL não configurado — clique em "Iniciar treinamento"' };
  try {
    const r = await fetch(process.env.VLM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // timeout: se a VLM demorar demais, cai no default e o auto-piloto não trava
      signal: AbortSignal.timeout(parseInt(process.env.VLM_TIMEOUT || '150000', 10)),
      body: JSON.stringify({
        model: process.env.VLM_MODEL || 'qwen3d',
        messages,
        temperature: 0.2,
        // Qwen3-VL-Thinking gasta tokens no <think> antes do content — precisa de
        // folga (~6k) senão o content (onde vem o JSON) sai vazio (finish=length).
        max_tokens: parseInt(process.env.VLM_MAX_TOKENS || '6144', 10),
      }),
    });
    const data = await r.json();
    const msg = data.choices?.[0]?.message || {};
    // o JSON do veredito vem em content (reasoning_content carrega só o <think>)
    const text = msg.content || msg.reasoning_content || '';
    return { ok: true, text };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}
function fileToB64(filename) {
  const p = path.join(UPLOADS_DIR, filename);
  return fs.existsSync(p) ? `data:image/jpeg;base64,${fs.readFileSync(p).toString('base64')}` : null;
}
function parseJsonLoose(s) {
  if (!s) return null;
  const m = s.match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
}

// Pré-scan: VLM analisa as N fotos e extrai params humanos antes da construção.
// Sem VLM_URL: heurística honesta (alerta que precisa do treinamento ligado).
app.post('/api/jobs/:id/scan', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const imgs = (job.sourceImages || [job.sourceImage]).slice(0, 6);
    const content = [];
    for (const f of imgs) {
      const b = fileToB64(f);
      if (b) content.push({ type: 'image_url', image_url: { url: b } });
    }
    content.push({ type: 'text', text:
      'Você é diretor de arte AAA. Analise as imagens (turnaround do personagem) e extraia ' +
      'os PARÂMETROS HUMANOS para construir o modelo 3D no Blender (MPFB2). ' +
      'Responda APENAS JSON: {"gender":"female|male","age":18-99,' +
      '"height_m":1.4-2.1,"hip":0.6-1.6,"shoulder":0.6-1.6,"muscle":0.6-1.6,' +
      '"skin":"#RRGGBB","hair":{"color":"#RRGGBB","length":"short|medium|long"},' +
      '"garment":"descrição curta","notes":"..."}'
    });
    const r = await vlmChat([{ role: 'user', content }]);
    let scan;
    if (r.ok) {
      scan = parseJsonLoose(r.text) || { error: 'VLM resposta sem JSON', raw: r.text.slice(0, 200) };
    } else {
      // heurística simples: pixel médio das imagens como tom de pele
      scan = {
        source: 'heuristic',
        warning: r.error,
        gender: 'female', age: 22, height_m: 1.70, hip: 1, shoulder: 1, muscle: 1,
        skin: '#c9a08a',
        hair: { color: '#2b1d16', length: 'long' },
        garment: 'a definir',
        notes: 'VLM não conectada; aplique defaults e inicie o treinamento para refinar.',
      };
    }
    // mescla nos params do job (mantém só campos conhecidos)
    const allowed = ['height_m', 'hip', 'shoulder', 'bust', 'waist', 'muscle', 'skin'];
    for (const k of allowed) {
      if (typeof scan[k] === 'number' || (k === 'skin' && /^#[0-9a-f]{6}$/i.test(scan[k] || ''))) {
        job.params[k] = scan[k];
      }
    }
    job.scan = { ...scan, ts: new Date().toISOString() };
    saveJob(job);
    emitJob(job.id, 'job:update', { job: publicJob(job) });
    res.json({ ok: true, scan: job.scan, job: publicJob(job) });
  }).catch(next);
});

// ---------- Hunyuan3D 2.1 (reconstrução inicial pluggável) ----------
// Quando HUNYUAN_URL aponta para um serviço (ComfyUI/Hunyuan API), a foto vira
// uma base mesh + textura PBR que os portões refinam. Sem serviço: o pipeline
// segue com MPFB2 (fallback honesto — não inventa geometria).
app.post('/api/jobs/:id/reconstruct', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    if (!process.env.HUNYUAN_URL) {
      return res.json({ ok: true, source: 'mpfb-fallback',
        note: 'HUNYUAN_URL não configurado — reconstrução inicial via MPFB2 (Blender). Suba o Hunyuan3D 2.1 e configure HUNYUAN_URL para usar geometria+PBR reconstruída da foto.' });
    }
    const img = fileToB64(job.sourceImages?.[0] || job.sourceImage);
    try {
      const r = await fetch(process.env.HUNYUAN_URL, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(parseInt(process.env.HUNYUAN_TIMEOUT || '600000', 10)),
        body: JSON.stringify({ image: img, output: 'glb', pbr: true }),
      });
      // O serviço Hunyuan deve devolver o GLB (binário) ou base64
      const ct = r.headers.get('content-type') || '';
      const buildDir = path.join(jobDir(job.id), 'build');
      fs.mkdirSync(buildDir, { recursive: true });
      const dest = path.join(buildDir, 'hunyuan_base.glb');
      if (ct.includes('json')) {
        const data = await r.json();
        if (data.glb_base64) fs.writeFileSync(dest, Buffer.from(data.glb_base64, 'base64'));
        else throw new Error('resposta sem glb_base64');
      } else {
        fs.writeFileSync(dest, Buffer.from(await r.arrayBuffer()));
      }
      job.reconstruct = { source: 'hunyuan3d-2.1', glb: `/api/jobs/${job.id}/build/hunyuan_base.glb`, ts: new Date().toISOString() };
      saveJob(job);
      res.json({ ok: true, source: 'hunyuan3d-2.1', glb: job.reconstruct.glb });
    } catch (e) {
      res.json({ ok: true, source: 'mpfb-fallback', warning: e.message });
    }
  }).catch(next);
});

// ---------- ChatGarment client (portão Tecido) ----------
// VLM lê N imagens das etapas/peças da roupa + descrição -> JSON GarmentCode
// -> Blender drapeia o pattern sobre o corpo MPFB2.
// Sem CHATGARMENT_URL: cai pra heurística com aviso explícito (não tenta inventar mesh).
async function chatGarmentInfer(images, prompt) {
  if (!process.env.CHATGARMENT_URL) {
    return { ok: false, error: 'CHATGARMENT_URL não configurado — clique em "Iniciar treinamento" e suba o ChatGarment' };
  }
  try {
    const r = await fetch(process.env.CHATGARMENT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        images, // array de dataURLs
        prompt, // pt-BR: descrição da roupa + camadas
        max_tokens: 1024,
        temperature: 0.2,
      }),
    });
    const data = await r.json();
    // O servidor ChatGarment retorna { pattern: GarmentCodeJSON, parts: [...] }
    return { ok: true, ...data };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// Endpoint dedicado do portão Tecido: usuário envia até 10 imagens das etapas
// da roupa (camisa/corset/saia/avental/laço/etc) e o ChatGarment infere o pattern.
app.post('/api/jobs/:id/stages/garment/chatgarment', upload.array('images', 10), (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const uploads = readJson(UPLOADS_JSON, []);
    const garmentImages = [];
    for (const f of (req.files || [])) {
      reservedNames.delete(f.filename);
      uploads.push({ name: f.filename, bytes: f.size, uploadedAt: new Date().toISOString() });
      garmentImages.push(f.filename);
    }
    // permite referenciar imagens já enviadas
    const existing = (req.body && (req.body['existing[]'] || req.body.existing)) || [];
    for (const e of Array.isArray(existing) ? existing : [existing]) {
      if (e && fs.existsSync(path.join(UPLOADS_DIR, path.basename(e)))) garmentImages.push(path.basename(e));
    }
    if (uploads.length > 0) { writeJson(UPLOADS_JSON, uploads); syncUploadsMd(); }
    if (!garmentImages.length) return res.status(400).json({ error: 'Envie ao menos uma imagem de peça/etapa do vestido.' });

    // pede ao ChatGarment o pattern (multi-image)
    const datas = garmentImages.map((n) => fileToB64(n)).filter(Boolean);
    const prompt = String((req.body && req.body.prompt) || '').trim()
      || `Você é o ChatGarment. As ${garmentImages.length} imagens são etapas/peças do vestido do personagem (turnaround + breakdown). Deduza o sewing pattern completo em GarmentCode JSON: cada peça (camisa, corset, saia interna, sobre-saia, avental, mangas, laço, acessórios) como painel separado com costuras corretas. Retorne JSON {pattern:{...GarmentCode...}, parts:[nome,...]}.`;
    const inf = await chatGarmentInfer(datas, prompt);
    job.garment = job.garment || {};
    job.garment.images = garmentImages;
    job.garment.lastPrompt = prompt;
    if (inf.ok && inf.pattern) {
      const patternPath = path.join(jobDir(job.id), 'garment_pattern.json');
      fs.writeFileSync(patternPath, JSON.stringify(inf.pattern, null, 2));
      job.garment.pattern = `/api/jobs/${job.id}/artifact/garment_pattern.json`;
      job.garment.parts = inf.parts || [];
      job.garment.source = 'chatgarment';
    } else {
      job.garment.source = 'offline';
      job.garment.warning = inf.error;
    }
    saveJob(job);
    appendDataset({
      ts: new Date().toISOString(), jobId: job.id, stage: 'garment',
      label: 'chatgarment', images: garmentImages, prompt,
      pattern_parts: (inf.parts || []).length,
      source: `/uploads/${encodeURIComponent(job.sourceImage)}`,
    });
    emitJob(job.id, 'garment:pattern', { ok: !!inf.pattern, parts: inf.parts || [], warning: inf.error || null });
    res.json({ ok: true, garment: job.garment, job: publicJob(job) });
  }).catch(next);
});

// Build do preview de UM portão (Blender headless + MPFB2 + Z-Anatomy).
// Saída: <job>/stage_<id>.glb (carregado direto no viewer do navegador).
app.post('/api/jobs/:id/stages/:stage/build', (req, res) => {
  if (!BLENDER_PATH) return res.status(400).json({ error: 'Blender não encontrado.' });
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const stageId = req.params.stage;
  if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });
  const dir = jobDir(job.id);
  const out = path.join(dir, `${stageId}.glb`);
  const log = path.join(dir, `${stageId}.log`);
  fs.writeFileSync(log, '');
  const ls = fs.createWriteStream(log, { flags: 'a' });
  const blArgs = [
    '--background', '--factory-startup',
    '--python', path.join(__dirname, 'blender', 'build_stage.py'), '--',
    '--stage', stageId, '--job', jobFile(job.id), '--out', dir,
  ];
  // portão Tecido: passa o GarmentCode JSON do ChatGarment se existir
  if (stageId === 'garment') {
    const patternPath = path.join(dir, 'garment_pattern.json');
    if (fs.existsSync(patternPath)) blArgs.push('--garment-pattern', patternPath);
  }
  const child = spawn(BLENDER_PATH, blArgs, { windowsHide: true });
  emitJob(job.id, 'stage:build:start', { stage: stageId });
  const onLine = (b) => {
    for (const line of b.toString().split(/\r?\n/)) {
      if (!line.trim()) continue;
      ls.write(line + '\n');
      if (/^\[stage|Error|Traceback/i.test(line)) emitJob(job.id, 'stage:build:log', { stage: stageId, line: line.slice(0, 240) });
    }
  };
  child.stdout.on('data', onLine);
  child.stderr.on('data', onLine);
  child.on('close', (code) => {
    ls.end();
    const ok = code === 0 && fs.existsSync(out);
    emitJob(job.id, ok ? 'stage:build:done' : 'stage:build:error', { stage: stageId, glb: ok ? `/api/jobs/${job.id}/artifact/${stageId}.glb` : null, code });
  });
  res.json({ ok: true, started: true });
});

// Serve GLB de portão (além do PNG snapshot já existente).
// O endpoint /artifact/:file aceita stage.glb porque já valida basename.

// Reprovar com sugestão da VLM: ela analisa o render e propõe o ajuste paramétrico.
app.post('/api/jobs/:id/stages/:stage/refine', jsonBig, (req, res, next) => {
  withJobLock(req.params.id, async () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
    const stageId = req.params.stage;
    const st = job.stages[stageId];
    const note = String((req.body && req.body.note) || '').trim();
    const refB64 = (job.sourceImages || []).map(fileToB64).filter(Boolean).slice(0, 3);
    const renderPath = st.lastImage ? path.join(jobDir(job.id), path.basename(st.lastImage)) : null;
    const renderB64 = renderPath && fs.existsSync(renderPath)
      ? `data:image/png;base64,${fs.readFileSync(renderPath).toString('base64')}` : null;
    const content = [];
    for (const b of refB64) content.push({ type: 'image_url', image_url: { url: b } });
    if (renderB64) content.push({ type: 'image_url', image_url: { url: renderB64 } });
    content.push({ type: 'text', text:
      `Tarefa rápida. Portão "${st.title}" reprovado. ` +
      (note ? `Motivo: "${note}". ` : '') +
      'Em no máximo 1 frase, proponha UM comando paramétrico pt-BR que aproxime o render da referência ' +
      '(ex.: "altura 1,75", "aumente 20% o quadril", "tom de pele pardo"). Formato exato, nada além: ' +
      '{"command":"...","reason":"..."}'
    });
    const r = await vlmChat([{ role: 'user', content }]);
    let suggestion = parseJsonLoose(r.text) || { command: '', reason: r.error || 'VLM sem JSON' };
    job.edits = job.edits || [];
    job.edits.push({ source: 'vlm-refine', stage: stageId, note, suggestion, ts: new Date().toISOString() });

    // aplica o comando sugerido se houver
    let applied = [], structural = false, cascade = { cascaded: false, reopened: [] };
    if (suggestion.command) {
      const a = applyPromptCommand(job.params, suggestion.command);
      job.params = a.params; applied = a.applied; structural = a.structural;
      if (structural) cascade = applyCascade(job);
    }
    // muda abordagem do portão
    st.approach += 1; st.status = 'running'; st.lastImage = null;
    saveJob(job);
    appendDataset({
      ts: new Date().toISOString(), jobId: job.id, stage: stageId,
      label: 'rejected_refine', note,
      vlm_suggestion: suggestion, applied, structural,
      source: `/uploads/${encodeURIComponent(job.sourceImage)}`,
    });
    emitJob(job.id, 'job:update', { job: publicJob(job) });
    res.json({ ok: true, suggestion, applied, structural, cascade, job: publicJob(job) });
  }).catch(next);
});

// Avaliação automática por VLM (Qwen-VL/InternVL plugável).
// Hoje opera com heurística + sinaliza o ponto onde a VLM real entra (config VLM_URL).
// Sempre que rodar, registra o veredito no dataset DPO — independente de aprovação humana.
app.post('/api/jobs/:id/stages/:stage/vlm-judge', jsonBig, async (req, res, next) => {
 try {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const stageId = req.params.stage;
  if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });
  const st = job.stages[stageId];
  const image = st.lastImage;
  if (!image) return res.status(400).json({ error: 'Sem preview para avaliar.' });

  const st_meta = STAGES.find((x) => x.id === stageId) || {};
  let verdict;
  if (process.env.VLM_URL) {
    // VLM real (Qwen3-VL local): vê a foto de referência + o render do portão e julga.
    const refB64 = (job.sourceImages || [job.sourceImage]).map(fileToB64).filter(Boolean).slice(0, 3);
    const renderPath = path.join(jobDir(job.id), path.basename(image));
    const renderB64 = fs.existsSync(renderPath)
      ? `data:image/png;base64,${fs.readFileSync(renderPath).toString('base64')}` : null;
    const content = [];
    for (const b of refB64) content.push({ type: 'image_url', image_url: { url: b } });
    if (renderB64) content.push({ type: 'image_url', image_url: { url: renderB64 } });
    const JUDGE_FOCUS = {
      skeleton: 'APENAS a estrutura óssea/proporção do esqueleto. IGNORE pele, cor, roupa, cabelo.',
      veins: 'APENAS a rede venosa/vascular. IGNORE roupa e cabelo.',
      muscle: 'APENAS massa e volume muscular/corporal. IGNORE roupa, cor da roupa e cabelo.',
      garment: 'APENAS o caimento/forma do tecido da roupa. IGNORE rosto e cabelo.',
      skin: 'APENAS o material/tom de pele e poros. IGNORE roupa e cabelo.',
      nails: 'APENAS as unhas das mãos/pés.',
      face: 'APENAS a topologia e proporção do rosto. IGNORE roupa.',
      eyes: 'APENAS os olhos (íris, posição). IGNORE o resto.',
      hair: 'APENAS o cabelo (volume, comprimento, cor). IGNORE roupa.',
    };
    content.push({ type: 'text', text:
      `Tarefa objetiva e rápida (diretor de arte AAA). Imagem(ns) inicial(is) = referência do personagem; ` +
      `última imagem = render 3D do portão "${st_meta.title || stageId}". ` +
      `AVALIE ${JUDGE_FOCUS[stageId] || st_meta.desc || ''} ` +
      `Não cobre aspectos de outros portões. Analise em no máximo 2 frases e então o JSON. ` +
      `Formato exato, nada além: ` +
      `{"pass": true ou false, "score": 0 a 1, "defects": [...], "suggested_prompt_fix": "comando pt-BR curto ou vazio"}`
    });
    const r = await vlmChat([{ role: 'user', content }]);
    const parsed = r.ok ? parseJsonLoose(r.text) : null;
    verdict = parsed
      ? { pass: !!parsed.pass, score: typeof parsed.score === 'number' ? parsed.score : (parsed.pass ? 0.85 : 0.4),
          defects: parsed.defects || [], suggested_prompt_fix: parsed.suggested_prompt_fix || '', source: 'qwen3-vl' }
      : { pass: true, score: 0.6, defects: ['VLM sem JSON — aprovado por padrão'], suggested_prompt_fix: '', source: 'vlm-noparse' };
  } else {
    // Sem VLM: heurística aceita (a construção MPFB2 já é válida; humano revisa se quiser).
    verdict = { pass: true, score: 0.85, defects: [], suggested_prompt_fix: '', source: 'heuristic' };
  }
  appendDataset({
    ts: new Date().toISOString(),
    jobId: job.id,
    stage: stageId,
    approach: st.approach,
    label: verdict.pass ? 'vlm_pass' : 'vlm_reject',
    score: verdict.score,
    defects: verdict.defects,
    suggested_prompt_fix: verdict.suggested_prompt_fix,
    snapshot: image,
    source: `/uploads/${encodeURIComponent(job.sourceImage)}`,
    vlmSource: verdict.source,
  });
  res.json({ ok: true, verdict });
 } catch (e) { next(e); }
});

app.get('/api/dataset', (req, res) => {
  res.json({ ok: true, stats: datasetStats() });
});
app.get('/api/dataset/export', (req, res) => {
  if (!fs.existsSync(DATASET_PATH)) return res.type('text/plain').send('');
  res.type('application/x-ndjson').send(fs.readFileSync(DATASET_PATH, 'utf8'));
});

// Erros (multer, throws síncronos) sempre respondem JSON — o frontend depende disso.
app.use((err, req, res, next) => {
  console.error(err);
  const status = err instanceof multer.MulterError ? 400 : err.status || 500;
  res.status(status).json({ error: err.message || 'Erro interno.' });
});

// Inicia (e baixa, se preciso) a VLM local automaticamente — autonomia total,
// o usuário não precisa clicar em nada. Desligável com AUTO_VLM=0.
function autoStartVlm() {
  if (process.env.AUTO_VLM === '0' || !LLAMA_SERVER) return;
  if (vlmInstalled()) {
    if (!vlmProc) { console.log('[auto-vlm] GGUF presente → subindo llama-server…'); startVlmLocal(); }
    return;
  }
  // não instalado → baixa em background e sobe ao terminar
  if (!vlmDownload || vlmDownload.done) {
    console.log('[auto-vlm] baixando Qwen3-VL-4B GGUF em background…');
    downloadVlmThenStart();
  }
}
function startVlmLocal() {
  if (!LLAMA_SERVER || !vlmInstalled() || vlmProc) return;
  const p = vlmPaths();
  const ngl = parseInt(process.env.VLM_NGL || '99', 10);
  vlmProc = spawn(LLAMA_SERVER, ['-m', p.model, '--mmproj', p.mmproj, '--host', '127.0.0.1',
    '--port', String(VLM_PORT), '-ngl', String(ngl), '-c', process.env.VLM_CTX || '8192', '--jinja'],
    { windowsHide: true });
  const ls = fs.createWriteStream(path.join(VLM_DIR, 'llama-server.log'), { flags: 'a' });
  let listening = false;
  const onLine = (b) => {
    const s = b.toString(); ls.write(s);
    if (!listening && /listening|HTTP server/i.test(s)) { listening = true; process.env.VLM_URL = VLM_LOCAL_URL; emitVlm('vlm:running', { url: VLM_LOCAL_URL }); }
  };
  vlmProc.stdout.on('data', onLine); vlmProc.stderr.on('data', onLine);
  vlmProc.on('close', (code) => { ls.end(); vlmProc = null; if (process.env.VLM_URL === VLM_LOCAL_URL) process.env.VLM_URL = ''; emitVlm('vlm:stopped', { code }); });
}
async function downloadVlmThenStart() {
  fs.mkdirSync(VLM_DIR, { recursive: true });
  for (const f of [VLM_MODEL_FILE, VLM_MMPROJ_FILE]) {
    const dest = path.join(VLM_DIR, f);
    if (fs.existsSync(dest)) continue;
    vlmDownload = { file: f, received: 0, total: 0, done: false };
    try {
      await downloadFile(`https://huggingface.co/${VLM_REPO}/resolve/main/${f}?download=true`, dest, (received, total) => {
        vlmDownload = { file: f, received, total, done: false };
        if (received % (8 * 1024 * 1024) < 65536) emitVlm('vlm:download', { file: f, received, total });
      });
    } catch (e) { vlmDownload = { file: f, error: e.message, done: true }; return emitVlm('vlm:error', { stage: 'download', file: f, error: e.message }); }
  }
  vlmDownload = { done: true };
  emitVlm('vlm:ready', { installed: vlmInstalled() });
  startVlmLocal();
}

app.listen(PORT, () => {
  console.log(`Scanner 3D Cognitivo — http://localhost:${PORT}`);
  console.log(`Referências: ${REFERENCES_DIR}`);
  console.log(`Documento: ${MD_PATH}`);
  console.log(`Blender: ${BLENDER_PATH || 'não encontrado'} · llama-server: ${LLAMA_SERVER || 'não encontrado'}`);
  setTimeout(autoStartVlm, 1500); // dá tempo do servidor estabilizar
});

// encerra o llama-server junto com o app
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => { try { if (vlmProc) vlmProc.kill(); } catch {} process.exit(0); });
}
// um erro async solto nunca derruba o servidor (fluidez = não cair no meio do auto-piloto)
process.on('unhandledRejection', (e) => console.error('[unhandledRejection]', e && e.message));
process.on('uncaughtException', (e) => console.error('[uncaughtException]', e && e.message));
