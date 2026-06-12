const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
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
const upload = multer({ storage, limits: { fileSize: 2 * 1024 * 1024 * 1024 } });

// ---------- app ----------
const app = express();
// 32mb: snapshots PNG do viewer three.js chegam como dataURL no corpo JSON.
app.use(express.json({ limit: '32mb' }));
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
const jsonBig = express.json({ limit: '32mb' }); // snapshots PNG em dataURL

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

// Cliente renderizou a etapa no three.js e capturou um snapshot PNG (dataURL).
// Salva como artefato da tentativa atual e marca a etapa para revisão.
app.post('/api/jobs/:id/stages/:stage/snapshot', jsonBig, (req, res) => {
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
  res.json({ ok: true, image: st.lastImage });
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
app.post('/api/jobs/:id/stages/:stage/review', jsonBig, (req, res) => {
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
    const idx = activeIndex(job);
    if (idx < STAGE_IDS.length) job.stages[STAGE_IDS[idx]].status = 'running';
  } else {
    // O modelo "aprende" que esta abordagem não serve e tenta outra (approach incrementa).
    st.approach += 1;
    st.status = 'running';
    st.lastImage = null;
  }
  saveJob(job);
  res.json({ ok: true, approved, nextApproach: st.approach, job: publicJob(job) });
});

// Edição paramétrica por prompt ("mude altura para 1,70", "aumente 20% o quadril", "tom de pele pardo").
// O comando é parseado, aplicado aos params do job e registrado no dataset como sinal de condicionamento.
app.post('/api/jobs/:id/params', jsonBig, (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  const command = String((req.body && req.body.command) || '').trim().slice(0, 500);
  if (!command) return res.status(400).json({ error: 'Comando vazio.' });
  const { params, applied, structural } = applyPromptCommand(job.params, command);
  job.params = params;
  job.edits = job.edits || [];
  // Recálculo síncrono em cascata: ajuste estrutural reabre Músculos+Tecido (seção 10.2.1).
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
  res.json({ ok: true, params, applied, structural, cascade, job: publicJob(job) });
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
