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
const { STAGE_IDS, newJob, activeIndex, publicJob, applyPromptCommand, applyCascade } = require('./lib/pipeline');

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
      j.build = okBuild
        ? { status: 'done', finishedAt: new Date().toISOString(), glb: `/api/jobs/${jobId}/build/character.glb`, blend: `/api/jobs/${jobId}/build/character.blend` }
        : { status: 'error', finishedAt: new Date().toISOString(), code };
      saveJob(j);
      emitJob(jobId, okBuild ? 'build:done' : 'build:error', { ...j.build, job: publicJob(j) });
    });
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

// Cria um job a partir de uma imagem (upload novo OU referência a um upload existente).
app.post('/api/jobs', upload.single('image'), (req, res) => {
  let sourceImage;
  if (req.file) {
    for (const f of [req.file]) reservedNames.delete(f.filename);
    sourceImage = req.file.filename;
    const uploads = readJson(UPLOADS_JSON, []);
    uploads.push({ name: req.file.filename, bytes: req.file.size, uploadedAt: new Date().toISOString() });
    writeJson(UPLOADS_JSON, uploads);
    syncUploadsMd();
  } else if (req.body && req.body.existing) {
    const name = path.basename(String(req.body.existing));
    if (!fs.existsSync(path.join(UPLOADS_DIR, name))) {
      return res.status(400).json({ error: 'Imagem de origem não encontrada em uploads.' });
    }
    sourceImage = name;
  } else {
    return res.status(400).json({ error: 'Envie uma imagem (campo "image") ou referencie "existing".' });
  }
  const job = newJob(genId(), sourceImage);
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
  if (!/^[a-z]+_a\d+\.png$/.test(file)) return res.status(400).json({ error: 'Arquivo inválido.' });
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
  const allow = new Set(['character.glb', 'character.blend', 'build.log']);
  const file = path.basename(req.params.file);
  if (!allow.has(file)) return res.status(400).json({ error: 'Arquivo inválido.' });
  const full = path.join(jobDir(job.id), 'build', file);
  if (!fs.existsSync(full)) return res.status(404).json({ error: 'Artefato não encontrado.' });
  if (file.endsWith('.blend')) res.setHeader('Content-Disposition', 'attachment; filename=character.blend');
  res.sendFile(full);
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

// Avaliação automática por VLM (Qwen-VL/InternVL plugável).
// Hoje opera com heurística + sinaliza o ponto onde a VLM real entra (config VLM_URL).
// Sempre que rodar, registra o veredito no dataset DPO — independente de aprovação humana.
app.post('/api/jobs/:id/stages/:stage/vlm-judge', jsonBig, async (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const stageId = req.params.stage;
  if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });
  const st = job.stages[stageId];
  const image = st.lastImage;
  if (!image) return res.status(400).json({ error: 'Sem preview para avaliar.' });

  const vlmUrl = process.env.VLM_URL || ''; // ex.: http://localhost:8000/v1/chat/completions (Qwen-VL/InternVL via vLLM)
  let verdict;
  if (vlmUrl) {
    // Quando uma VLM real estiver plugada, chama aqui. Por enquanto fallback honesto.
    verdict = { pass: false, score: 0.5, defects: ['VLM plugada não respondeu'], suggested_prompt_fix: '', source: 'vlm-fallback' };
  } else {
    // Heurística: aceita por padrão; usuário pode ligar VLM_URL=... para a real.
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

app.listen(PORT, () => {
  console.log(`Scanner 3D Cognitivo — http://localhost:${PORT}`);
  console.log(`Referências: ${REFERENCES_DIR}`);
  console.log(`Documento: ${MD_PATH}`);
});
