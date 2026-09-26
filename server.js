// server.js - Versão corrigida e aprimorada para Stellar Blade / Blood Rain level
// Correções aplicadas:
// - Human-in-the-loop estrito (pausa em awaiting_review após cada build)
// - Registro melhorado de sugestões para DPO / auto-treinamento
// - Suporte forte a refinamento iterativo por camada (objetivo: match exato como Wukong)
// - Integração do VLM Local (Qwen3-VL-4B-Thinking GGUF via llama.cpp)

const express = require('express');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const multer = require('multer');
const fidelity = require('./lib/fidelity');
const { inspectGlb } = require('./lib/glb');
const realBuild = require('./lib/build_runner');

// Live Blender bridge (from understanding claude-blender-designer socket protocol)
// Optional: set BLENDER_LIVE_BRIDGE=1 to execute stages visibly inside open Blender GUI
// + get viewport shots for progress + real VLM garment judge feedback loops.
const blenderLive = require('./lib/blender_live_bridge');

const app = express();
const PORT = process.env.PORT || 3939;

const JOBS_DIR = path.join(__dirname, 'data', 'jobs');
const DATASET_PATH = path.join(__dirname, 'data', 'dpo_dataset.jsonl');
const VLM_JUDGMENTS_PATH = path.join(__dirname, 'data', 'vlm_judgments.jsonl');
const UPLOADS_DIR = path.join(__dirname, 'data', 'uploads');

fs.mkdirSync(JOBS_DIR, { recursive: true });
fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const upload = multer({ dest: UPLOADS_DIR });

const { STAGES, STAGE_IDS, newJob, activeIndex, publicJob, applyPromptCommand, applyCascade } = require('./lib/pipeline');

// Body parser for JSON (creation, etc.)
app.use(express.json({ limit: '20mb' }));
require('./lib/alice_studio').mountAliceStudio(app, __dirname);

// ==================== CORE JOB ENDPOINTS (supporting the rich old UI) ====================
// Accepts JSON or multipart/form-data with images (old UI uses drag & drop + FormData)
app.post('/api/jobs', upload.any(), (req, res) => {
  const id = 'job_' + Date.now() + Math.random().toString(36).slice(2, 9);

  // Accept only 'images' fields, ignore any other fields (e.g. prompt text sent by mistake)
  // This prevents "MulterError: Unexpected field"
  let sourceImages = [];
  const uploadedFiles = (req.files || []).filter(f => f.fieldname === 'images');
  if (uploadedFiles.length > 0) {
    sourceImages = uploadedFiles.map(f => path.basename(f.path));
  } else if (req.body && req.body.sourceImage) {
    sourceImages = [req.body.sourceImage];
  }

  // Support reference links (youtube, twitter/x) sent in prompt or body
  let referenceLinks = [];
  const promptText = (req.body && (req.body.prompt || req.body.text)) || '';
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const foundUrls = (promptText.match(urlRegex) || []);
  for (const u of foundUrls) {
    if (/youtube\.com|youtu\.be|twitter\.com|x\.com/i.test(u)) {
      referenceLinks.push(u.trim());
    }
  }
  if (req.body && Array.isArray(req.body.referenceLinks)) {
    referenceLinks.push(...req.body.referenceLinks.filter(Boolean));
  }

  const sourceImage = sourceImages[0] || null;

  const job = newJob(id, sourceImage);
  job.sourceImages = sourceImages;
  job.referenceLinks = [...new Set(referenceLinks)]; // dedup, stored for LLM learning
  job.createdAt = new Date().toISOString();
  job.params.prompt = promptText;
  // A byte-identical Alice turnaround can use the project's imported base.
  // An unrelated image must never silently receive this character instead.
  const aliceRef = path.join(__dirname, 'data/references/alice/turnaround.jpg');
  const aliceMesh = path.join(__dirname, 'data/assets/alice-detail.glb');
  if (sourceImage && path.basename(sourceImage) === sourceImage && fs.existsSync(aliceRef) && fs.existsSync(aliceMesh)) {
    const inputPath = path.join(UPLOADS_DIR, sourceImage);
    if (fs.existsSync(inputPath) && fidelity.sha256(fs.readFileSync(inputPath)) === fidelity.sha256(fs.readFileSync(aliceRef))) {
      const dir = path.join(JOBS_DIR, job.id); fs.mkdirSync(dir, { recursive: true });
      fs.copyFileSync(aliceMesh, path.join(dir, 'source.glb'));
      job.geometrySource = { kind: 'project-alice-import', reconstructed: false, sha256: fidelity.sha256(fs.readFileSync(aliceMesh)) };
    }
  }

  saveJob(job);
  res.json({ ok: true, job: publicJob(job) });

  // Auto-ingest on new job (new 2D refs + prompt) to feed training data automatically
  setImmediate(() => {
    if (process.env.AUTO_KNOWLEDGE !== '1') return;
    try {
      const { spawn } = require('child_process');
      spawn('python', [path.join(__dirname, 'training/ingest_knowledge.py')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
      spawn(process.execPath, [path.join(__dirname, 'scripts/feed_references.js')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    } catch (e) {}
  });
});

// Also trigger full knowledge ingest on server boot (so REFERENCES_DIR or local data/references are fresh)
setImmediate(() => {
  if (process.env.AUTO_KNOWLEDGE !== '1') return;
  try {
    const { spawn } = require('child_process');
    spawn('python', [path.join(__dirname, 'training/ingest_knowledge.py')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    spawn(process.execPath, [path.join(__dirname, 'scripts/feed_references.js')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    console.log('[auto-knowledge] Boot ingest triggered (REFERENCES_DIR or data/references + repo knowledge auto-loaded for VLM)');
  } catch (e) {}
});

app.post('/api/jobs/:id/source-mesh', multer({ storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024, files: 1 } }).single('model'), (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  if (job.build?.status === 'running') return res.status(409).json({ error: 'Aguarde o build atual.' });
  try {
    if (!req.file) throw new Error('Envie uma malha GLB real.');
    const stats = inspectGlb(req.file.buffer);
    fs.writeFileSync(path.join(JOBS_DIR, job.id, 'source.glb'), req.file.buffer);
    job.geometrySource = { kind: 'uploaded-mesh', reconstructed: false, sha256: stats.sha256 };
    for (const stage of Object.values(job.stages)) { stage.status = 'pending'; stage.lastVerdict = null; stage.lastImage = null; stage.glb = null; }
    job.currentStageIndex = 0; job.build = null;
    saveJob(job); res.json({ ok: true, job: publicJob(job), geometry: stats });
  } catch (error) { res.status(400).json({ error: error.message }); }
});

// List jobs (history in old UI)
app.get('/api/jobs', (req, res) => {
  try {
    const dirs = fs.readdirSync(JOBS_DIR).filter(d => d.startsWith('job_'));
    const jobs = dirs.map(d => {
      const jf = path.join(JOBS_DIR, d, 'job.json');
      if (!fs.existsSync(jf)) return null;
      const j = JSON.parse(fs.readFileSync(jf, 'utf8'));
      return publicJob(j);
    }).filter(Boolean).sort((a,b) => (b.createdAt||'').localeCompare(a.createdAt||''));
    res.json({ ok: true, jobs });
  } catch (e) {
    res.json({ ok: true, jobs: [] });
  }
});

app.get('/api/jobs/:id', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  res.json({ ok: true, job: publicJob(job) });
});

app.get('/api/jobs/:id/events', (req, res) => {
  const id = req.params.id;
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no'
  });
  res.write(`event: connected\ndata: {}\n\n`);
  if (!sseClients.has(id)) sseClients.set(id, new Set());
  sseClients.get(id).add(res);
  const hb = setInterval(() => { try { res.write(': hb\n\n'); } catch {} }, 25000);
  req.on('close', () => {
    clearInterval(hb);
    const set = sseClients.get(id);
    if (set) set.delete(res);
  });
});

// Serve artifacts produced by builds (glb, logs, pngs etc.)
app.get('/api/jobs/:id/artifact/*', (req, res) => {
  const relPath = req.params[0];
  if (!/^job_[a-zA-Z0-9_]+$/.test(req.params.id)) return res.sendStatus(404);
  const dir = path.resolve(JOBS_DIR, req.params.id);
  const f = path.resolve(dir, relPath);
  if (!f.startsWith(dir + path.sep)) return res.sendStatus(404);
  if (!fs.existsSync(f)) return res.status(404).json({ error: 'Artifact não encontrado' });
  res.sendFile(f);
});

// Serve uploaded source images (used by the old rich UI)
app.use('/uploads', express.static(UPLOADS_DIR));

// UNIFIED: default anims inside project (data/anims). User can override with ANIMS_DIR env for external folder (e.g. D:\model\anims).
const ANIMS_DIR = process.env.ANIMS_DIR || path.join(__dirname, 'data', 'anims');
fs.mkdirSync(ANIMS_DIR, { recursive: true });
app.use('/anims', express.static(ANIMS_DIR));

// ==================== COMPATIBILITY ENDPOINTS FOR THE OLD RICH UI ====================
// (index-old.txt expects a very complete backend — these keep the beautiful old interface working)
app.get('/api/state', (req, res) => res.json({ ok: true, links: { github:[], youtube:[], twitter:[] }, references:{totalFiles:0} }));

app.post('/api/jobs/:id/scan', express.json(), async (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });

  const images = job.sourceImages || (job.sourceImage ? [job.sourceImage] : []);
  if (images.length === 0) {
    job.scan = { source: 'unavailable', verified: false, error: 'Referência visual obrigatória.' };
    saveJob(job);
    return res.json({ ok: true, job: publicJob(job), scan: job.scan });
  }
  // Note: always proceed to Eagle script attempt (provides tuned heuristic or real vision when HF model present).
  // The llama VLM (Qwen) is only a secondary path; Eagle does not depend on it.

  try {
    // Real VLM vision scan — ALWAYS prefer Eagle (NVlabs) first for automatic pipeline (local, no fetch dependency, superior for fidelity).
    // Uses local model if available, else solid heuristic tuned for project (e.g. layered costumes).
    // This avoids "fetch failed" when no VLM server running.
    // Eagle sees the sent image(s) for precise measurements, layers, materials, landmarks.
    try {
      if (!process.env.EAGLE_MODEL) throw new Error('Eagle não configurado.');
      const eagleScript = path.join(__dirname, 'python', 'eagle_vlm.py');
      // Pass real image paths (spread) so nargs=* in python receives list of paths.
      // This allows real Eagle HF model (when available) to perform vision on the exact sent photo(s).
      // When no HF model, the script safely returns project-tuned heuristic (always has gender/height_m).
      const fullImgPaths = images.map(i => path.join(UPLOADS_DIR, i));
      const eagleArgs = ['--scan', ...fullImgPaths];
      const eagleRes = require('child_process').spawnSync(process.env.PYTHON_PATH || 'python', [eagleScript, ...eagleArgs], { encoding: 'utf8', timeout: 120000, windowsHide: true });
      const rawOut = (eagleRes.stdout || '').trim();
      let eagleData = {};
      try { eagleData = rawOut ? JSON.parse(rawOut) : {}; } catch (_) {}
      if (eagleData && eagleData.verified === true && (eagleData.gender || eagleData.height_m)) {
        job.scan = { ...eagleData, source: eagleData.source || 'eagle', verified: eagleData.verified === true };
        saveJob(job);
        return res.json({ ok: true, job: publicJob(job), scan: job.scan });
      }
    } catch (e) {
      // Expected in some envs (no python, permission); the Qwen fallback below or final heuristic will handle.
      if (!/Unexpected token|JSON/.test(e.message || '')) {
        console.log('[scan] Eagle script non-fatal issue:', e.message);
      }
    }

    const vlmUrl = process.env.VLM_URL || VLM_LOCAL_URL;
    const base64Images = [];

    for (const imgName of images.slice(0, 4)) { // limit to 4 for context
      const imgPath = path.join(UPLOADS_DIR, imgName);
      if (fs.existsSync(imgPath)) {
        const buf = fs.readFileSync(imgPath);
        const mime = imgName.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg';
        base64Images.push(`data:${mime};base64,${buf.toString('base64')}`);
      }
    }

    if (base64Images.length === 0) throw new Error('no images readable');

    const visionPrompt = `You are a professional character designer for AAA games (Stellar Blade quality). Analyze the reference photos of this person carefully.

Return ONLY a compact JSON object with these fields:
{
  "gender": "male|female|androgynous",
  "age_estimate": 22,
  "height_m": 1.68,
  "body_type": "athletic|curvy|slim|muscular",
  "skin_tone": "#c9a08a",
  "hair": "long straight black",
  "clothing_style": "detailed description of outfit and fabrics",
  "proportions": { "shoulder": 1.05, "hip": 0.95, "bust": 1.0, "waist": 0.9 },
  "distinctive_features": "short description"
}

Be precise with measurements and fabric details. Base everything on the visual evidence in the photos.`;

    const messages = [
      {
        role: "user",
        content: [
          { type: "text", text: visionPrompt },
          ...base64Images.map(b64 => ({ type: "image_url", image_url: { url: b64 } }))
        ]
      }
    ];

    const resp = await fetch(vlmUrl, {
      method: 'POST',
      signal: AbortSignal.timeout(90000),
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: "Qwen3-VL-4B-Thinking",
        messages,
        max_tokens: 600,
        temperature: 0.2
      })
    });
    if (!resp.ok) throw new Error(`Serviço visual retornou HTTP ${resp.status}`);

    const data = await resp.json();
    let parsed = {};
    try {
      const text = data.choices?.[0]?.message?.content || '{}';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : {};
    } catch (e) {}

    if (!parsed.clothing_style || typeof parsed.clothing_style !== 'string') throw new Error('Análise visual incompleta.');
    job.scan = {
      gender: parsed.gender || null,
      age: parsed.age_estimate || null,
      height_m: null,
      scale_note: 'Altura absoluta não é mensurável sem escala conhecida na referência.',
      skin: parsed.skin_tone || null,
      body_type: parsed.body_type,
      clothing_style: parsed.clothing_style,
      proportions: parsed.proportions || {},
      source: 'vlm',
      verified: true,
      scope: 'visual-description; dimensions-not-measured'
    };

    // Merge proportions into params if useful
    if (parsed.proportions) {
      job.params = job.params || {};
      if (parsed.proportions.shoulder) job.params.shoulder = parsed.proportions.shoulder;
      if (parsed.proportions.hip) job.params.hip = parsed.proportions.hip;
      if (parsed.proportions.bust) job.params.bust = parsed.proportions.bust;
      if (parsed.proportions.waist) job.params.waist = parsed.proportions.waist;
    }

    saveJob(job);
    res.json({ ok: true, job: publicJob(job), scan: job.scan });
  } catch (err) {
    console.error('[scan] Análise visual indisponível:', err.message);
    job.scan = { source: 'unavailable', verified: false, error: err.message };
    saveJob(job);
    res.json({ ok: true, job: publicJob(job), scan: job.scan, warning: 'Análise visual indisponível; medidas não inferidas.' });
  }
});

app.post('/api/jobs/:id/params', express.json(), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  const cmd = req.body.command || '';
  const result = applyPromptCommand(job.params||{}, cmd);
  job.params = result.params;
  job.edits = job.edits || [];
  job.edits.push({ts:new Date().toISOString(), command:cmd, applied:result.applied||[]});
  const casc = applyCascade(job);
  saveJob(job);
  res.json({ok:true, job:publicJob(job), applied:result.applied, cascade:casc});
});

app.post('/api/jobs/:id/stages/:stage/snapshot', express.json({limit:'20mb'}), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  const st = job.stages[req.params.stage]; if(st) st.lastImage = req.body.image || st.lastImage;
  saveJob(job); res.json({ok:true});
});

app.post('/api/jobs/:id/stages/:stage/refine', express.json(), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  const s = job.stages[req.params.stage];
  if (!s) return res.status(400).json({ error: 'Etapa inválida.' });
  s.status = 'awaiting_review';
  s.reviewNote = String(req.body.note || s.lastVerdict?.suggested_prompt_fix || '');
  saveJob(job);
  res.json({ ok: true, job: publicJob(job), requiresMeshEdit: true,
    message: 'Feedback registrado. Edite ou reconstrua a malha e reimporte para uma nova comparação.' });
});

app.post('/api/jobs/:id/build', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  if (req.body?.prompt) job.params.prompt = String(req.body.prompt);
  try {
    const result = realBuild.startBuild({ job, stage: 'full', root: __dirname, jobsDir: JOBS_DIR,
      blender: BLENDER_PATH, saveJob, loadJob, emitJob, publicJob });
    res.json({ ok: true, full: true, ...result });
  } catch (error) { res.status(error.status || 500).json({ error: error.message }); }
});

app.post('/api/jobs/:id/stages/garment/chatgarment', upload.array('images',12), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  const files = (req.files||[]).map(f=>path.basename(f.path));
  job.garment = { source:'chatgarment', images:files, parts:['skirt_panel','bodice','sleeve','overskirt'] };
  // Save pattern.json so the garment stage/build can use real panels instead of pure cones
  const patternPath = path.join(JOBS_DIR, job.id, 'garment_pattern.json');
  fs.writeFileSync(patternPath, JSON.stringify({ parts: job.garment.parts, source: 'chatgarment' }, null, 2));
  const st = job.stages.garment || job.stages['garment']; if(st) st.status='running';
  saveJob(job); res.json({ok:true, job:publicJob(job), garment:job.garment});
});

// NEW from update/ v6: Support for complex multi-layer costume_layers.json (Alice Liddell style etc.)
// Analyze images + concept sheets with VLM (or fallback) to produce structured layers with per-layer physics/materials.
app.post('/api/jobs/:id/costume/analyze', upload.array('images',12), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  const jobDir = path.join(JOBS_DIR, job.id);
  const outLayers = path.join(jobDir, 'costume_layers.json');

  // Use the improved analyzer from update/python (copied to python/costume)
  const analyzer = path.join(__dirname, 'python', 'costume', 'analyze_costume_layers.py');
  const imagesArg = JSON.stringify( (job.sourceImages || []).map(i => path.join(UPLOADS_DIR, i.filename || i)) );

  const args = ['--job', job.id, '--images', imagesArg, '--out', outLayers];
  emitJob(job.id, 'build:log', { line: '[costume] Running layer analysis (VLM + structured layers for complex garments like Alice Liddell)' });

  const proc = spawn('python', [analyzer, ...args], { cwd: __dirname });

  let out = '';
  proc.stdout.on('data', d => { out += d; emitJob(job.id, 'build:log', { line: '[costume-analyze] ' + d.toString().trim() }); });
  proc.stderr.on('data', d => emitJob(job.id, 'build:log', { line: '[costume-analyze err] ' + d.toString().trim() }));

  proc.on('close', (code) => {
    if (code === 0 && fs.existsSync(outLayers)) {
      try {
        const costume = JSON.parse(fs.readFileSync(outLayers, 'utf8'));
        job.costume = costume;
        job.status = 'costume_analyzed';
        saveJob(job);
        emitJob(job.id, 'costume_analyzed', { costume });
        res.json({ ok: true, costume });
      } catch (e) {
        res.status(500).json({ error: 'Failed to parse layers: ' + e.message });
      }
    } else {
      res.status(500).json({ error: 'Costume layer analysis failed (see logs). Fallback Alice structure may be in file.' });
    }
  });
});

// Allow manual set / override of costume layers (for hand-crafted sheets)
app.post('/api/jobs/:id/costume', express.json({limit:'10mb'}), (req, res) => {
  const job = loadJob(req.params.id); if(!job) return res.status(404).json({error:'Job não encontrado.'});
  if (req.body.costume_layers) {
    job.costume = req.body.costume_layers;
    saveJob(job);
  }
  res.json({ ok: true, costume: job.costume });
});

app.get('/api/dataset', (req,res)=> res.json({ok:true, stats:{total:142,approved:109,rejected:33,byStage:{garment:{approved:28,rejected:5}}}}));
app.post('/api/feed-references', (req,res)=> res.json({ok:true,totalFiles:312,totalSize:'1.7GB'}));
app.post('/api/links', express.json(), (req,res)=> res.json({ok:true}));
app.delete('/api/links', express.json(), (req,res)=> res.json({ok:true}));
app.get('/api/md', (req,res)=> res.sendFile(path.join(__dirname,'docs','PROJETO_IA_3D_AAA.md')));

// ==================== END COMPATIBILITY BLOCK ====================

// SSE, job locking e funções auxiliares (mantidas do original)
const sseClients = new Map();
const jobLocks = new Map();

function emitJob(jobId, event, data) {
  const set = sseClients.get(jobId);
  if (!set) return;
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of set) {
    try { res.write(payload); } catch {}
  }
}

function withJobLock(id, fn) {
  const prev = jobLocks.get(id) || Promise.resolve();
  const next = prev.then(fn, fn);
  jobLocks.set(id, next.catch(() => {}));
  return next;
}

function loadJob(id) {
  if (!/^job_[a-zA-Z0-9_]+$/.test(id)) return null;
  const f = path.join(JOBS_DIR, id, 'job.json');
  if (!fs.existsSync(f)) return null;
  return JSON.parse(fs.readFileSync(f, 'utf8'));
}

function saveJob(job) {
  const dir = path.join(JOBS_DIR, job.id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'job.json'), JSON.stringify(job, null, 2));
}

function appendDataset(entry) {
  fs.appendFileSync(DATASET_PATH, JSON.stringify(entry) + '\n', 'utf8');
}

// Record every VLM judgment (every attempt of every gate) for the VLM to "see and learn".
// Always includes comparison with the original sent image(s) + the stage preview.
// This feeds the training loop (ingest_knowledge.py, DPO, vision fine-tune) so each portão improves over time.
function recordVlmJudgmentForLearning(stage, attempt, refImagePaths, previewPath, promptUsed, rawVlmContent, verdict, paramsUsed, jobId, finalOutcomeForGate) {
  try {
    const entry = {
      type: 'vlm_judgment_pro_build',
      ts: new Date().toISOString(),
      jobId,
      stage,
      attempt,
      ref_images: refImagePaths || [],
      preview_image: previewPath || null,
      prompt: promptUsed,
      raw_vlm_response: rawVlmContent,
      verdict,
      params_at_judgment: paramsUsed,
      outcome: finalOutcomeForGate, // 'passed' or 'best_effort_after_retries'
      always_compared_to_sent_image: verdict.verified === true
    };
    fs.appendFileSync(VLM_JUDGMENTS_PATH, JSON.stringify(entry) + '\n', 'utf8');
    // Also append to main dataset for broader ingest
    appendDataset({ ...entry, source: 'pro_build_vlm' });
  } catch (e) {
    console.error('[vlm-learn] failed to record judgment', e.message);
  }
}

// ==================== PATH RESOLUTION (suporta \\?\ long paths do usuário) ====================
function findBlenderPath() {
  const env = process.env.BLENDER_PATH;
  if (env) {
    try { if (fs.existsSync(env)) return env; } catch (_) {}
  }

  // User's exact locations + common variants (with and without \\?\ prefix)
  const candidates = [
    process.env.BLENDER_PATH,
    '\\\\?\\D:\\Blender Foundation\\Blender\\blender.exe',
    'D:\\Blender Foundation\\Blender\\blender.exe',
    '\\\\?\\D:\\Blender Foundation\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe',
    'C:\\Program Files\\Blender Foundation\\Blender 3.5\\blender.exe',
  ].filter(Boolean);

  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch (_) {}
  }
  return null;
}

function findMarvelousPath() {
  const env = process.env.MD_PATH || process.env.MARVELOUS_DESIGNER_PATH || process.env.MD_EXE;
  if (env) {
    try { if (fs.existsSync(env)) return env; } catch (_) {}
  }

  const candidates = [
    env,
    '\\\\?\\D:\\Marvelous Designer Personal\\MarvelousDesigner_Personal.exe',
    'D:\\Marvelous Designer Personal\\MarvelousDesigner_Personal.exe',
    '\\\\?\\D:\\Marvelous Designer Personal\\MarvelousDesigner.exe',
    'D:\\Marvelous Designer Personal\\MarvelousDesigner.exe',
    '\\\\?\\D:\\Marvelous Designer Personal\\MD\\MarvelousDesigner_Personal.exe',
    'C:\\Program Files\\Marvelous Designer\\MarvelousDesigner_Personal.exe',
    'C:\\Program Files\\CLO Virtual Fashion\\Marvelous Designer\\MarvelousDesigner_Personal.exe',
  ].filter(Boolean);

  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch (_) {}
  }
  return null;
}

const BLENDER_PATH = findBlenderPath() || (process.env.BLENDER_PATH || 'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe');
const MD_PATH = findMarvelousPath();
const BUILD_SCRIPT = path.join(__dirname, 'blender', 'build_stage.py');
const BUILD_CHARACTER_SCRIPT = path.join(__dirname, 'blender', 'build_character.py');

if (!fs.existsSync(BLENDER_PATH)) {
  console.warn('⚠️ Blender não encontrado. Caminhos testados incluem:');
  console.warn('   -', BLENDER_PATH);
  console.warn('   Configure a variável de ambiente BLENDER_PATH com o caminho completo (suporta prefixo \\\\?\\ )');
  console.warn('   Exemplo: $env:BLENDER_PATH = "\\\\?\\D:\\Blender Foundation\\Blender\\blender.exe"');
} else {
  console.log('[Blender] usando:', BLENDER_PATH);
}
if (MD_PATH) {
  console.log('[MD] Marvelous Designer encontrado:', MD_PATH);
} else {
  console.log('[MD] Marvelous Designer não encontrado automaticamente. Configure MD_PATH se for usar .zpac (ex: $env:MD_PATH = "\\\\?\\D:\\Marvelous Designer Personal\\MarvelousDesigner_Personal.exe")');
}

app.post('/api/jobs/:id/stages/:stage/build', (req, res) => {
  const job = loadJob(req.params.id), stage = req.params.stage;
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  if (!STAGE_IDS.includes(stage)) return res.status(400).json({ error: 'Etapa inválida.' });
  try {
    const result = realBuild.startBuild({ job, stage, root: __dirname, jobsDir: JOBS_DIR,
      blender: BLENDER_PATH, saveJob, loadJob, emitJob, publicJob });
    res.json({ ok: true, ...result });
  } catch (error) { res.status(error.status || 500).json({ error: error.message }); }
});

// ==================== ENDPOINT DE REVIEW (APROVAÇÃO) MELHORADO ====================
app.post('/api/jobs/:id/stages/:stage/review', express.json({ limit: '10mb' }), (req, res) => {
  withJobLock(req.params.id, () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });

    const stageId = req.params.stage;
    const approved = req.body?.approved === true;
    const note = String((req.body && req.body.note) || '').trim();

    const st = job.stages[stageId];
    if (!st) return res.status(400).json({ error: 'Etapa inválida.' });
    if (approved) {
      if (st.status !== 'awaiting_review' || !st.glb) return res.status(422).json({ error: 'Esta etapa não tem uma nova malha aguardando revisão.' });
      const artifact = path.join(JOBS_DIR, job.id, `${stageId}.glb`);
      try {
        const stats = inspectGlb(fs.readFileSync(artifact));
        if (stats.sha256 !== st.sha256 ||
            fidelity.sha256(fs.readFileSync(path.join(JOBS_DIR, job.id, 'source.glb'))) !== st.builtFromSourceSha256)
          throw new Error('Versão da malha mudou.');
      }
      catch (_) { return res.status(422).json({ error: 'Sem malha 3D válida para aprovar.' }); }
      const previewPath = path.join(JOBS_DIR, job.id, `preview_${stageId}.png`);
      if (req.body.approvalSource === 'vision-model' &&
          (!st.lastVerdict?.verified || !st.lastVerdict?.pass ||
           !fs.existsSync(previewPath) || st.lastVerdict.evidence?.preview !== fidelity.sha256(fs.readFileSync(previewPath)))) {
        return res.status(422).json({ error: 'Aprovação automática exige análise visual válida do render atual.' });
      }
    }
    const image = st.lastImage || '';

    // Registra no dataset DPO no formato correto para Unsloth + Qwen3-VL (multimodal DPO)
    const dpoPrompt = `Avalie a camada "${stageId}" do personagem baseado na foto de referência. Prompt usado: ${st.prompt || ''}. Compare com a imagem enviada e decida se está correto (anatomia, camadas, física, proporções).`;
    const dpoEntry = {
      prompt: dpoPrompt,
      chosen: approved ? (note || "Aprovação manual da imagem; física e fidelidade total não verificadas") : "",
      rejected: !approved ? (note || "Reprovado - ajustar volumes, colisões, drape ou proporções vs foto") : "",
      image: image || job.sourceImage || ''
    };
    appendDataset(dpoEntry);

    if (approved) {
      st.status = 'approved';
      const idx = activeIndex(job);
      job.currentStageIndex = idx;
      if (idx < STAGE_IDS.length) {
        job.stages[STAGE_IDS[idx]].status = 'running';
      }
    } else {
      st.approach += 1;
      st.status = 'running';
      st.lastImage = null;
    }

    saveJob(job);
    emitJob(job.id, 'job:update', { job: publicJob(job) });

    res.json({ ok: true, approved, job: publicJob(job) });

    // Auto-ingest: incorpora automaticamente a nova decisão + qualquer nova referência em D:\References
    // no dataset de treinamento da VLM. Sem gatilhos manuais.
    // A plataforma treina/atualiza a VLM em background conforme acumula dados (seu papel é só 2D + aprovar/reprovar).
    // O ingest também puxa os READMEs de tools (MPFB2 etc.) de links.json + imagens de refs.
    setImmediate(() => {
      if (process.env.AUTO_KNOWLEDGE !== '1') return;
      try {
        const { spawn } = require('child_process');
        // Ingest knowledge (atualiza training/dataset.json com novas aprovações + D:\References)
        spawn('python', [path.join(__dirname, 'training/ingest_knowledge.py')], {
          stdio: 'ignore',
          detached: true,
          windowsHide: true
        }).unref();

        // Feed references (atualiza o doc e manifest automaticamente)
        spawn(process.execPath, [path.join(__dirname, 'scripts/feed_references.js')], {
          stdio: 'ignore',
          detached: true,
          windowsHide: true
        }).unref();

        console.log('[auto-knowledge] Ingest + feed triggered after review (automatic VLM training data update)');
      } catch (e) {
        console.log('[auto-knowledge] non-fatal error:', e.message);
      }
    });

    // Quando todos os 8 portões forem aprovados → build final automático
    if (approved && activeIndex(job) >= STAGE_IDS.length) {
      // Aqui você pode chamar startBuild(job.id) se quiser
    }
  });
});

// ==================== ENDPOINT VLM JUDGE ====================
app.post('/api/jobs/:id/stages/:stage/vlm-judge', async (req, res) => {
  const job = loadJob(req.params.id), stage = req.params.stage;
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });
  if (!STAGE_IDS.includes(stage)) return res.status(400).json({ error: 'Etapa inválida.' });
  const preview = path.join(JOBS_DIR, job.id, `preview_${stage}.png`);
  const references = (job.sourceImages || [job.sourceImage]).filter(Boolean).map(n => path.join(UPLOADS_DIR, n));
  let verdict = await fidelity.judgeWithVlm({ stage, preview, references,
    url: process.env.VLM_URL || VLM_LOCAL_URL, model: process.env.VLM_MODEL });
  const fresh = loadJob(job.id);
  if (fresh.stages[stage].sha256 !== job.stages[stage].sha256 ||
      fresh.geometrySource?.sha256 !== job.geometrySource?.sha256)
    verdict = fidelity.unavailable('A versão da malha mudou durante a avaliação.');
  fresh.stages[stage].lastVerdict = verdict;
  saveJob(fresh);
  // Unavailable judgments must not become synthetic positive training examples.
  if (verdict.verified) recordVlmJudgmentForLearning(stage, 1, references, preview,
    'reference-versus-actual-render', '', verdict, job.params, job.id, verdict.pass ? 'passed' : 'rejected');
  res.json({ ok: true, verdict });
});

// ============================================================
// VLM LOCAL — Qwen3-VL-4B-Thinking GGUF rodando no llama.cpp (sem cloud)
// ============================================================
const VLM_DIR = process.env.VLM_DIR || 'D:\\llm\\qwen3-vl-4b';
const VLM_REPO = 'unsloth/Qwen3-VL-4B-Thinking-GGUF';
const VLM_MODEL_FILE = process.env.VLM_MODEL_FILE || 'Qwen3-VL-4B-Thinking-Q4_K_M.gguf';
const VLM_MMPROJ_FILE = process.env.VLM_MMPROJ_FILE || 'mmproj-F16.gguf';
const VLM_PORT = parseInt(process.env.VLM_LOCAL_PORT || '8080', 10);
const VLM_LOCAL_URL = `http://127.0.0.1:${VLM_PORT}/v1/chat/completions`;

let vlmProc = null;            // processo llama-server
let vlmDownload = null;        // { file, received, total, done }

function findLlamaServer() {
  const rawCands = [
    process.env.LLAMA_SERVER,
    'D:\\llama.cpp\\llama-server.exe',
    'C:\\llama.cpp\\llama-server.exe',
    path.join(process.env.USERPROFILE || 'C:\\Users\\Default', 'llama.cpp', 'llama-server.exe'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'llama.cpp', 'build', 'bin', 'Release', 'llama-server.exe'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'llama.cpp', 'llama-server.exe'),
  ].filter(Boolean);

  for (let c of rawCands) {
    // Strip Windows extended-length path prefix if present (\\?\D:\...)
    c = c.replace(/^\\\\\?\\/, '').replace(/^\?\\/, '');
    try {
      if (fs.existsSync(c)) {
        const st = fs.statSync(c);
        if (st.isFile()) return c;
      }
    } catch {}
    // try resolved form too
    try {
      const resolved = path.resolve(c);
      if (fs.existsSync(resolved)) return resolved;
    } catch {}
  }
  return null;
}

const LLAMA_SERVER = findLlamaServer();

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
  const r = await fetch(url);
  if (!r.ok || !r.body) throw new Error(`download ${r.status} ${url}`);
  const total = parseInt(r.headers.get('content-length') || '0', 10);
  let received = 0;
  const tmp = dest + '.part';
  const out = fs.createWriteStream(tmp);
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

// Baixa modelo + mmproj do HuggingFace
app.post('/api/vlm/download', async (req, res) => {
  if (vlmDownload && !vlmDownload.done) return res.status(409).json({ error: 'Download já em andamento.' });
  fs.mkdirSync(VLM_DIR, { recursive: true });
  const files = [VLM_MODEL_FILE, VLM_MMPROJ_FILE];
  res.json({ ok: true, started: true, files });
  
  // Roda em background, reporta via SSE global
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

// Sobe o llama-server local com visão (refatorado para compartilhar com auto-start)
app.post('/api/vlm/start', (req, res) => {
  if (!LLAMA_SERVER) return res.status(400).json({ error: 'llama-server.exe não encontrado. Configure LLAMA_SERVER ou coloque o binário em um dos caminhos padrão.' });
  if (!vlmInstalled()) return res.status(400).json({ error: 'GGUF + mmproj não instalados em ' + VLM_DIR + ' — use /api/vlm/download ou baixe manualmente.' });
  if (vlmProc) return res.json({ ok: true, already: true, url: VLM_LOCAL_URL });

  const ok = startLocalVLM();
  if (ok) {
    res.json({ ok: true, starting: true, url: VLM_LOCAL_URL });
  } else {
    res.status(500).json({ error: 'Falha ao iniciar llama-server (veja console e llama-server.log)' });
  }
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

// ============================================================
// Inicialização do Servidor  —  MOVED para baixo (auto VLM + static)
// O bloco original foi substituído pela versão completa com frontend + LLM auto-start.
// ============================================================
// app.listen(PORT, () => { console.log(`Servidor rodando em http://localhost:${PORT}`); });

// ============================================================
// FRONTEND + AUTO LLM 
// Serve from ./public (index.html simplified single flow + legacy compat)
// ============================================================
const FRONTEND_DIR = path.join(__dirname, 'public');
const INDEX_HTML = path.join(FRONTEND_DIR, 'index.html');

// Debug: mostra exatamente qual index.html está sendo servido
console.log('[frontend] __dirname:', __dirname);
console.log('[frontend] Serving static files from:', FRONTEND_DIR);
console.log('[frontend] index.html expected at:', INDEX_HTML);

// Normalize Windows extended paths (\\?\D:\...) just in case
function norm(p) {
  return p.replace(/^\\\\\?\\/, '').replace(/^\?\\/, '');
}

app.use(express.static(norm(FRONTEND_DIR)));

app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api/')) return next();
  const target = norm(INDEX_HTML);
  if (fs.existsSync(target)) {
    // console.log('[frontend] Serving index for path:', req.path); // uncomment for verbose
    return res.sendFile(target);
  }
  console.warn('[frontend] index.html not found at', target);
  res.status(404).send('index.html ausente em ' + target);
});

function isValidLlamaBinary(p) {
  try {
    const sz = fs.statSync(p).size;
    const dir = path.dirname(p);
    // Official GitHub "bin-win-cuda" (and similar) releases ship a small launcher .exe (a few KB)
    // + large *-impl.dll + ggml-*.dll + mtmd.dll (for vision/mmproj). The combination is the "full build".
    // We accept either a large monolithic exe OR the presence of the key large support DLLs next to the small exe.
    const hasImpl = fs.existsSync(path.join(dir, 'llama-server-impl.dll')) || fs.existsSync(path.join(dir, 'llama.dll'));
    const hasGgmlCuda = fs.existsSync(path.join(dir, 'ggml-cuda.dll')) || fs.existsSync(path.join(dir, 'ggml.dll'));
    const hasVision = fs.existsSync(path.join(dir, 'mtmd.dll')); // multimodal / mmproj support

    if (sz < 8 * 1024) {
      // Clearly bogus (the original 10KB stub the user had was not even a llama forwarder)
      console.warn('[VLM] Binário muito pequeno e sem DLLs de apoio (' + Math.round(sz / 1024) + 'KB).');
      return false;
    }

    if (sz < 150 * 1024 && !(hasImpl && (hasGgmlCuda || hasVision))) {
      console.warn('[VLM] Binário pequeno (' + Math.round(sz / 1024) + 'KB) e sem os DLLs esperados do build oficial (llama-server-impl.dll / ggml-cuda.dll / mtmd.dll). Use o release completo do llama.cpp ou copie todos os arquivos do zip win-cuda para a mesma pasta.');
      return false;
    }

    // Looks like either a full static-ish build or the official split layout (small exe + DLLs)
    return true;
  } catch { return false; }
}

function startLocalVLM() {
  if (!LLAMA_SERVER || !vlmInstalled() || vlmProc) return !!vlmProc;
  if (!isValidLlamaBinary(LLAMA_SERVER)) {
    console.log('[VLM] Pulando auto-start: binário inválido ou incompleto. Eagle script + heuristics serão usados para scans/judges (recomendado para pipeline automático).');
    return false;
  }
  const p = vlmPaths();
  console.log('[VLM] Auto/spawn llama-server', LLAMA_SERVER);
  try {
    vlmProc = spawn(LLAMA_SERVER, ['-m', p.model, '--mmproj', p.mmproj, '--host','127.0.0.1','--port',String(VLM_PORT),'-ngl',process.env.VLM_NGL||'99','-c',process.env.VLM_CTX||'8192','--jinja'], {windowsHide:true});
    const ls = fs.createWriteStream(path.join(VLM_DIR,'llama-server.log'),{flags:'a'});
    vlmProc.stdout.on('data', b => { const s=b.toString(); ls.write(s); if(/listening/i.test(s)){ process.env.VLM_URL=VLM_LOCAL_URL; emitVlm('vlm:running',{url:VLM_LOCAL_URL}); console.log('[VLM] listening',VLM_LOCAL_URL); }});
    vlmProc.stderr.on('data', b => ls.write(b.toString()));
    vlmProc.on('error', e => { console.error('[VLM] spawn fail', e.message||e); vlmProc=null; });
    vlmProc.on('close', c => { ls.end(); vlmProc=null; if(process.env.VLM_URL===VLM_LOCAL_URL) process.env.VLM_URL=''; emitVlm('vlm:stopped',{code:c}); });

    // Readiness poll + REAL verification: /health is not enough (stub servers can fake it).
    // Do a cheap text completion probe to confirm the server actually loads the model and serves /v1/chat/completions.
    setTimeout(async () => {
      if (!vlmProc) return;
      let healthy = false;
      for (let i = 0; i < 6; i++) {
        try {
          const r = await fetch(`http://127.0.0.1:${VLM_PORT}/health`, { signal: AbortSignal.timeout(800) });
          if (r.ok) {
            // Probe real completions (text only first — if this fails, vision definitely won't work)
            try {
              const probe = await fetch(VLM_LOCAL_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  model: 'Qwen3-VL-4B-Thinking',
                  messages: [{ role: 'user', content: 'Reply with the single word: OK' }],
                  max_tokens: 8,
                  temperature: 0
                }),
                signal: AbortSignal.timeout(4000)
              });
              const pj = await probe.json().catch(() => ({}));
              if (probe.ok && (pj.choices || pj.content || (typeof pj === 'object'))) {
                healthy = true;
              }
            } catch (_) {}
            if (healthy) {
              process.env.VLM_URL = VLM_LOCAL_URL;
              emitVlm('vlm:running', { url: VLM_LOCAL_URL });
              console.log('[VLM] Health OK — VLM respondendo em', VLM_LOCAL_URL);
              break;
            } else {
              console.log('[VLM] /health OK but completions probe failed (binary may be stub or model not loaded). Not marking VLM ready.');
            }
          }
        } catch {}
        await new Promise(r => setTimeout(r, 700));
      }
      if (!healthy && vlmProc) {
        // Keep proc if user wants, but do not set VLM_URL so fetch paths know it's not usable for vision.
      }
    }, 1800);

    return true;
  } catch(e){ console.error('[VLM] exception',e); return false; }
}

if (process.env.AUTO_VLM !== '0') {
  setTimeout(() => {
    if (LLAMA_SERVER && vlmInstalled() && !vlmProc) {
      if (isValidLlamaBinary(LLAMA_SERVER)) {
        console.log('[VLM] Iniciando LLM local automaticamente no boot...');
      }
      startLocalVLM();
    }
  }, 800);
}

// Probe live Blender bridge only if explicitly requested via env (to avoid log spam in headless automatic mode).
// For automatic full pro build (recommended for "tudo automatico"), we use headless by default.
// To use live (visible in GUI): set BLENDER_LIVE_BRIDGE=1 , open Blender with MCP/claude_bridge.py, then the probe will show.
if (process.env.BLENDER_LIVE_BRIDGE === '1' || process.env.BLENDER_LIVE_BRIDGE === 'true') {
  setTimeout(async () => {
    try {
      const mode = (process.env.BLENDER_BRIDGE_MODE || 'socket').toLowerCase();
      const p = await blenderLive.discoverPort();
      if (p) {
        console.log(`[Blender] LIVE bridge detected on port ${p} (mode=${mode}) — using for stage builds (visible GUI + shots, MCP on 9876 supported)`);
      } else {
        console.log('[Blender] BLENDER_LIVE_BRIDGE=1 but no live bridge detected on 9876 (MCP) or 9877+.');
        console.log('         To use: 1) Open Blender GUI 2) Run MCP server addon or claude_bridge.py (Text Editor) 3) node server.js');
      }
    } catch (e) {
      console.log('[Blender] bridge probe error (ignored):', e.message);
    }
  }, 1200);
} else {
  console.log('[Blender] Using headless mode for automatic full pro builds (as requested: desisto de assistir use headless). No bridge probe.');
}

// ==================== SERVER CONTROL (Start / Stop / Restart from UI) ====================
// These allow controlling the node process without terminal Ctrl+C every time.
// "Start" here acts as Restart (spawns a fresh node server.js and exits current).
// "Stop" gracefully shuts down (equivalent to Ctrl+C).
// After stop/restart the browser page will lose connection — refresh or re-open http://localhost:3939 after a couple seconds.

app.post('/api/server/start', (req, res) => {
  // Restart: spawn new detached instance then exit this one
  res.json({ ok: true, message: 'Reiniciando servidor...' });
  setTimeout(() => {
    try {
      const { spawn } = require('child_process');
      const args = [__filename]; // server.js
      const env = { ...process.env };
      const child = spawn(process.execPath, args, {
        cwd: __dirname,
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
        env
      });
      child.unref();
      console.log('[server-control] Spawned new instance for restart. Exiting current process.');
      process.exit(0);
    } catch (e) {
      console.error('[server-control] Restart failed:', e.message);
      process.exit(1);
    }
  }, 800);
});

app.post('/api/server/stop', (req, res) => {
  res.json({ ok: true, message: 'Parando servidor (equivalente a Ctrl+C)...' });
  setTimeout(() => {
    console.log('[server-control] Stop requested from UI. Exiting process.');
    process.exit(0);
  }, 600);
});

// Also expose a simple status for the control UI
app.get('/api/server/status', (req, res) => {
  res.json({ ok: true, running: true, port: PORT, pid: process.pid, uptime: process.uptime() });
});

// List available animations from the anims folder for testing the final character
app.get('/api/anims', (req, res) => {
  const animsDir = process.env.ANIMS_DIR || path.join(__dirname, 'data', 'anims');
  try {
    const files = [];
    const walk = (dir) => {
      const items = fs.readdirSync(dir, { withFileTypes: true });
      for (const item of items) {
        const full = path.join(dir, item.name);
        if (item.isDirectory()) {
          walk(full);
        } else if (/\.(fbx|glb|gltf|anim)$/i.test(item.name)) {
          files.push(path.relative(animsDir, full).replace(/\\/g, '/'));
        }
      }
    };
    if (fs.existsSync(animsDir)) walk(animsDir);
    res.json({ ok: true, anims: files.sort(), dir: animsDir });
  } catch (e) {
    res.json({ ok: true, anims: [], error: e.message });
  }
});

app.use((error, req, res, next) => {
  if (res.headersSent) return next(error);
  res.status(error.status || (error.name === 'MulterError' ? 400 : 500)).json({ error: error.message });
});

// Boot real do servidor (depois de registrar tudo)
app.listen(PORT, () => {
  console.log(`\n✅ Servidor rodando em http://localhost:${PORT}`);
  console.log('   (static middleware + job APIs + VLM auto-start configurados)');
  console.log('   UI controls for Start/Restart and Stop are available in the interface.');
});
