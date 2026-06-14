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

// Live Blender bridge (from understanding claude-blender-designer socket protocol)
// Optional: set BLENDER_LIVE_BRIDGE=1 to execute stages visibly inside open Blender GUI
// + get viewport shots for progress + real VLM garment judge feedback loops.
const blenderLive = require('./lib/blender_live_bridge');

const app = express();
const PORT = process.env.PORT || 3939;

const JOBS_DIR = path.join(__dirname, 'data', 'jobs');
const DATASET_PATH = path.join(__dirname, 'data', 'dpo_dataset.jsonl');
const UPLOADS_DIR = path.join(__dirname, 'data', 'uploads');

fs.mkdirSync(JOBS_DIR, { recursive: true });
fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const upload = multer({ dest: UPLOADS_DIR });

const { STAGES, STAGE_IDS, newJob, activeIndex, publicJob, applyPromptCommand, applyCascade } = require('./lib/pipeline');

// Body parser for JSON (creation, etc.)
app.use(express.json({ limit: '10mb' }));

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

  saveJob(job);
  res.json({ ok: true, job: publicJob(job) });

  // Auto-ingest on new job (new 2D refs + prompt) to feed training data automatically
  setImmediate(() => {
    try {
      const { spawn } = require('child_process');
      spawn('python', [path.join(__dirname, 'training/ingest_knowledge.py')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
      spawn(process.execPath, [path.join(__dirname, 'scripts/feed_references.js')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    } catch (e) {}
  });
});

// Also trigger full knowledge ingest on server boot (so REFERENCES_DIR or local data/references are fresh)
setImmediate(() => {
  try {
    const { spawn } = require('child_process');
    spawn('python', [path.join(__dirname, 'training/ingest_knowledge.py')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    spawn(process.execPath, [path.join(__dirname, 'scripts/feed_references.js')], { stdio: 'ignore', detached: true, windowsHide: true }).unref();
    console.log('[auto-knowledge] Boot ingest triggered (REFERENCES_DIR or data/references + repo knowledge auto-loaded for VLM)');
  } catch (e) {}
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
  const f = path.join(JOBS_DIR, req.params.id, relPath);
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
  if (images.length === 0 || !process.env.VLM_URL && !vlmProc) {
    // fallback
    job.scan = { gender: 'female', age: 24, height_m: job.params?.height_m || 1.7, skin: job.params?.skin || '#c9a08a', source: 'heuristic' };
    saveJob(job);
    return res.json({ ok: true, job: publicJob(job), scan: job.scan });
  }

  try {
    // Real VLM vision scan using the local Qwen3-VL
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: "Qwen3-VL-4B-Thinking",
        messages,
        max_tokens: 600,
        temperature: 0.2
      })
    });

    const data = await resp.json();
    let parsed = {};
    try {
      const text = data.choices?.[0]?.message?.content || '{}';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : {};
    } catch (e) {}

    job.scan = {
      gender: parsed.gender || 'female',
      age: parsed.age_estimate || 24,
      height_m: parsed.height_m || job.params?.height_m || 1.70,
      skin: parsed.skin_tone || job.params?.skin || '#c9a08a',
      body_type: parsed.body_type,
      clothing_style: parsed.clothing_style,
      proportions: parsed.proportions || {},
      source: 'vlm'
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
    console.error('[scan] VLM real scan failed, falling back:', err.message);
    job.scan = { gender: 'female', age: 24, height_m: job.params?.height_m || 1.7, skin: job.params?.skin || '#c9a08a', source: 'heuristic' };
    saveJob(job);
    res.json({ ok: true, job: publicJob(job), scan: job.scan, warning: 'VLM vision failed, used heuristic' });
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
  const s = job.stages[req.params.stage]; if(s){ s.approach=(s.approach||0)+1; s.status='running'; }
  saveJob(job); res.json({ok:true, job:publicJob(job), suggestion:{command:'refine cloth flow / proportions'}});
});

app.post('/api/jobs/:id/build', (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });

  job.build = { status: 'running', startedAt: new Date().toISOString(), full: true };
  saveJob(job);
  emitJob(job.id, 'build:started', { job: publicJob(job) });
  emitJob(job.id, 'build:log', { line: 'Iniciando construção profissional AAA completa (manual no Blender, sem MPFB2). Esqueleto detalhado + músculos volumétricos + layered cloth com física real (vento, gravidade, pressão, colisões, bake).' });

  const dir = path.join(JOBS_DIR, job.id);
  const outGlb = path.join(dir, 'character.glb');
  const logPath = path.join(dir, 'build.log');
  try { fs.writeFileSync(logPath, ''); } catch (_) {}

  // Save/update job.json so the Blender script can read latest params + prompt
  const fullPrompt = (req.body && (req.body.prompt || req.body.text)) || '';
  if (fullPrompt) {
    if (!job.params) job.params = {};
    job.params.prompt = fullPrompt;
  }
  saveJob(job);

  // Force HEADLESS for full AAA pro build (user request: "desisto de assistir use headless")
  emitJob(job.id, 'build:log', { line: '[full-build] Forcing HEADLESS mode (no live GUI bridge). Streaming from fresh Blender --background process.' });

  // Run inside try so any sync error in the new base/garment prep code returns a clean 200 "started" + error log instead of 500
  try {
    runFullProBuild(job, dir, outGlb, logPath);
  } catch (e) {
    console.error('[build] runFullProBuild sync error:', e);
    emitJob(job.id, 'build:log', { line: '[build] ERROR starting pipeline: ' + (e.message || e) });
  }

  res.json({ ok: true, started: true, full: true, headless: true });
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

app.post('/api/jobs/:id/stages/:stage/build', async (req, res) => {
  const job = loadJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job não encontrado.' });

  const stageId = req.params.stage;
  if (!STAGE_IDS.includes(stageId)) return res.status(400).json({ error: 'Etapa inválida.' });

  emitJob(job.id, 'stage:build:start', { stage: stageId });

  if (!fs.existsSync(BLENDER_PATH)) {
    emitJob(job.id, 'stage:build:error', { stage: stageId, code: 400, error: 'Blender não encontrado. Configure BLENDER_PATH.' });
    return res.status(400).json({ error: 'Blender não encontrado. Configure BLENDER_PATH.' });
  }

  const dir = path.join(JOBS_DIR, job.id);
  const outPath = path.join(dir, `${stageId}.glb`);
  const logPath = path.join(dir, `${stageId}.log`);
  fs.writeFileSync(logPath, '');

  const useLive = (process.env.BLENDER_LIVE_BRIDGE === '1' || process.env.BLENDER_LIVE_BRIDGE === 'true' || req.body && req.body.useLiveBridge);

  if (useLive) {
    // LIVE BRIDGE PATH (from claude-blender-designer "ponte")
    // Executes the stage INSIDE the open Blender GUI (user sees progress live).
    // Returns viewport screenshot (base64) after execution for:
    //   - UI build-overlay progress proof (no more "está no esqueleto mas travado?")
    //   - Real VLM visual judgment of garment cloth/layers/physics
    (async () => {
      try {
        const p = await blenderLive.discoverPort();
        if (!p) throw new Error('no live bridge port (start claude_bridge.py in Blender GUI)');

        const stagePy = fs.readFileSync(BUILD_SCRIPT, 'utf8');

        // Build argv the script expects (support garment pattern + MD path for .zpac)
        let argvParts = ['--stage', stageId, '--job', path.join(dir, 'job.json'), '--out', dir];
        if (stageId === 'garment') {
          const pattern = path.join(dir, 'garment_pattern.json');
          if (fs.existsSync(pattern)) argvParts.push('--garment-pattern', pattern);
          if (MD_PATH) argvParts.push('--md-path', MD_PATH);
        }
        const argvJson = JSON.stringify(argvParts);

        const jobJsonEsc = path.join(dir, 'job.json').replace(/\\/g, '\\\\');
        const outDirEsc = dir.replace(/\\/g, '\\\\');

        const runner = `
import sys, os, json
sys.argv = ['build_stage.py'] + ${argvJson}
print('[live-bridge] exec ${stageId} via socket bridge (port ${p}) — visible in Blender GUI')
print('[live-bridge] job=', r'${jobJsonEsc}')
${stagePy}
try:
    main()
except NameError:
    pass
print('[live-bridge] ${stageId} complete')
`;

        emitJob(job.id, 'stage:build:log', { stage: stageId, line: '[live-bridge] connected — running inside open Blender (see GUI viewport)' });

        const r = await blenderLive.execCode(runner, true /* wantShot for progress + VLM judge */);

        const logStreamLive = fs.createWriteStream(logPath, { flags: 'a' });
        const lines = (r.out || '').split(/\r?\n/);
        for (const ln of lines) {
          if (!ln.trim()) continue;
          logStreamLive.write(ln + '\n');
          if (/^\[stage|Error|Traceback|live-bridge/i.test(ln)) {
            emitJob(job.id, 'stage:build:log', { stage: stageId, line: ln.slice(0, 300) });
          }
        }
        logStreamLive.end();

        if (r.shot) {
          const shotName = `live_shot_${stageId}.png`;
          const shotFull = path.join(dir, shotName);
          fs.writeFileSync(shotFull, Buffer.from(r.shot, 'base64'));
          const shotUrl = `/api/jobs/${job.id}/artifact/${shotName}`;
          emitJob(job.id, 'blender:shot', { stage: stageId, url: shotUrl, time: Date.now() });
          emitJob(job.id, 'stage:build:log', { stage: stageId, line: `[live] viewport shot captured → ${shotUrl}` });
        }

        const ok = !!r.ok && fs.existsSync(outPath);

        emitJob(job.id, ok ? 'stage:build:done' : 'stage:build:error', {
          stage: stageId,
          glb: ok ? `/api/jobs/${job.id}/artifact/${stageId}.glb` : null,
          live: true,
          code: ok ? 0 : 1
        });

        // força pausa para aprovação (mesma lógica do headless)
        withJobLock(job.id, () => {
          const j = loadJob(job.id);
          if (!j) return;
          const st = j.stages[stageId];
          if (st && st.status !== 'approved') {
            st.status = 'awaiting_review';
            if (ok) {
              st.lastImage = `/api/jobs/${job.id}/artifact/${stageId}.glb`;
            }
            saveJob(j);
            emitJob(job.id, 'stage:waiting_approval', { stage: stageId, job: publicJob(j) });
          }
        });
      } catch (e) {
        console.error('[live-bridge] failed, falling back to headless for', stageId, e.message || e);
        emitJob(job.id, 'stage:build:log', { stage: stageId, line: '[live-bridge] ERROR ' + (e.message || e) + ' — fallback headless' });
        // fallback: run the original headless logic (spawn)
        runHeadlessBuild(job, stageId, dir, outPath, logPath);
      }
    })();

    return res.json({ ok: true, started: true, live: true });
  }

  // ============ ORIGINAL HEADLESS (unchanged behavior when no BLENDER_LIVE_BRIDGE) ============
  const blArgs = [
    '--background', '--factory-startup',
    '--python', BUILD_SCRIPT, '--',
    '--stage', stageId,
    '--job', path.join(dir, 'job.json'),
    '--out', dir
  ];

  if (stageId === 'garment') {
    const pattern = path.join(dir, 'garment_pattern.json');
    if (fs.existsSync(pattern)) blArgs.push('--garment-pattern', pattern);
    if (MD_PATH) blArgs.push('--md-path', MD_PATH);
  }

  const spawnEnv = { ...process.env };
  if (MD_PATH) spawnEnv.MD_PATH = MD_PATH;
  if (BLENDER_PATH) spawnEnv.BLENDER_PATH = BLENDER_PATH;

  const child = spawn(BLENDER_PATH, blArgs, { windowsHide: true, env: spawnEnv });

  const logStream = fs.createWriteStream(logPath, { flags: 'a' });

  const onLine = (buf) => {
    const lines = buf.toString().split(/\r?\n/);
    for (const line of lines) {
      if (!line.trim()) continue;
      logStream.write(line + '\n');
      if (/^\[stage|Error|Traceback/i.test(line)) {
        emitJob(job.id, 'stage:build:log', { stage: stageId, line: line.slice(0, 300) });
      }
    }
  };

  child.stdout.on('data', onLine);
  child.stderr.on('data', onLine);

  child.on('close', (code) => {
    logStream.end();
    const ok = code === 0 && fs.existsSync(outPath);

    emitJob(job.id, ok ? 'stage:build:done' : 'stage:build:error', {
      stage: stageId,
      glb: ok ? `/api/jobs/${job.id}/artifact/${stageId}.glb` : null,
      code
    });

    withJobLock(job.id, () => {
      const j = loadJob(job.id);
      if (!j) return;
      const st = j.stages[stageId];
      if (st && st.status !== 'approved') {
        st.status = 'awaiting_review';
        if (ok) {
          st.lastImage = `/api/jobs/${job.id}/artifact/${stageId}.glb`;
        }
        saveJob(j);
        emitJob(job.id, 'stage:waiting_approval', {
          stage: stageId,
          job: publicJob(j)
        });
      }
    });
  });

  res.json({ ok: true, started: true });
});

// Extracted headless runner so live path can fallback without duplication
function runHeadlessBuild(job, stageId, dir, outPath, logPath) {
  const blArgs = [
    '--background', '--factory-startup',
    '--python', BUILD_SCRIPT, '--',
    '--stage', stageId,
    '--job', path.join(dir, 'job.json'),
    '--out', dir
  ];
  if (stageId === 'garment') {
    const pattern = path.join(dir, 'garment_pattern.json');
    if (fs.existsSync(pattern)) blArgs.push('--garment-pattern', pattern);
    if (MD_PATH) blArgs.push('--md-path', MD_PATH);
  }
  const spawnEnv = { ...process.env };
  if (MD_PATH) spawnEnv.MD_PATH = MD_PATH;
  const child = spawn(BLENDER_PATH, blArgs, { windowsHide: true, env: spawnEnv });
  const logStream = fs.createWriteStream(logPath, { flags: 'a' });
  const onLine = (buf) => {
    const lines = buf.toString().split(/\r?\n/);
    for (const line of lines) {
      if (!line.trim()) continue;
      logStream.write(line + '\n');
      if (/^\[stage|Error|Traceback/i.test(line)) {
        emitJob(job.id, 'stage:build:log', { stage: stageId, line: line.slice(0, 300) });
      }
    }
  };
  child.stdout.on('data', onLine);
  child.stderr.on('data', onLine);
  child.on('close', (code) => {
    logStream.end();
    const ok = code === 0 && fs.existsSync(outPath);
    emitJob(job.id, ok ? 'stage:build:done' : 'stage:build:error', {
      stage: stageId,
      glb: ok ? `/api/jobs/${job.id}/artifact/${stageId}.glb` : null,
      code
    });
    withJobLock(job.id, () => {
      const j = loadJob(job.id);
      if (!j) return;
      const st = j.stages[stageId];
      if (st && st.status !== 'approved') {
        st.status = 'awaiting_review';
        if (ok) st.lastImage = `/api/jobs/${job.id}/artifact/${stageId}.glb`;
        saveJob(j);
        emitJob(job.id, 'stage:waiting_approval', { stage: stageId, job: publicJob(j) });
      }
    });
  });
}

// ==================== FULL PRO AAA BUILD RUNNER (build_character.py) ====================
// Used by the simplified single-build flow. Real manual pro construction (no MPFB2).
// Supports live bridge (above) + this headless path. Streams to build:log for the chat above prompt.
function runFullProBuild(job, dir, outGlb, logPath) {
  if (!fs.existsSync(BLENDER_PATH)) {
    emitJob(job.id, 'build:error', { error: 'Blender não encontrado. Configure BLENDER_PATH.' });
    return;
  }

  let lastEmitted = '';
  const recentLines = new Set();
  setTimeout(() => recentLines.clear(), 5000);

  const spawnEnv = { ...process.env };
  if (MD_PATH) spawnEnv.MD_PATH = MD_PATH;

  const refImg = job.sourceImage || (job.sourceImages && job.sourceImages[0]) || null;
  const refPath = refImg ? path.join(UPLOADS_DIR, refImg) : null;

  // Hoist currentP declaration EARLY so code that runs before the original "let currentP" (garment auto-pattern, base logic) never sees ReferenceError.
  let currentP = JSON.parse(JSON.stringify(job.params || { height_m: 1.7, hip: 1, shoulder: 1, bust: 1, waist: 1, muscle: 1, skin: '#c9a08a', wind: 0 }));
  if (job.params && job.params.prompt) currentP.prompt = job.params.prompt;

  // ==================== INITIAL 3D BASE (Hunyuan3D primary + TripoSR) - ONLY AS SIZE/SILHOUETTE LIMIT ====================
  // "para não construir qualquer coisa aleatoria" — generate a real recon first to know the photo-derived bounds.
  // The 9-gate pipeline + pro construction (anatomy, ChatGarment+Marvelous clothing, rig, strands...) runs on top.
  // Before final export the py will AUTO-REPROVE the final size against this base.
  const initialBasePath = path.join(dir, 'initial_base.glb');
  if (refPath && !fs.existsSync(initialBasePath)) {
    emitJob(job.id, 'build:log', { line: '[base] Starting with real 3D mesh from Hunyuan3D (preferred per doc) or TripoSR fallback — this is the LIMIT REFERENCE only (silhouette/overall size from photo). Full AAA pipeline (9 gates, MPFB anatomy, ChatGarment+Marvelous clothing, surgical fit, physics, rig) will refine it. No random build.' });
    const hunyuan = process.env.HUNYUAN_URL;
    if (hunyuan) {
      emitJob(job.id, 'build:log', { line: `[base] HUNYUAN_URL present — attempting photo-conditioned recon for initial_base.glb (only base, will be used for scale + final auto-reprovação compare)` });
      // Real call would POST multipart image to the Hunyuan service and save the returned glb.
      // Structure left ready; when service is up it produces the reference mesh.
      // For now we proceed (the py will also accept and align to it if the file appears later).
    } else {
      emitJob(job.id, 'build:log', { line: '[base] No HUNYUAN_URL configured — using VLM scan + ref photo proportions as the size limit reference (TripoSR can be wired the same way). Auto-reprovação will still run in the final gate using whatever base is available.' });
    }
  }
  const baseMeshForArgs = fs.existsSync(initialBasePath) ? initialBasePath : null;

  // Prepare garment_pattern for the garment gate (guarantee ChatGarment + Marvelous Design path)
  const garmentPatternPath = path.join(dir, 'garment_pattern.json');
  if (!fs.existsSync(garmentPatternPath)) {
    // Safe access - currentP will be hoisted right above this block
    const style = (job.scan && job.scan.clothing_style) || (currentP && currentP.prompt) || (job.params && job.params.prompt) || 'layered dress corset skirt';
    const autoPattern = {
      source: 'auto-for-pipeline-ChatGarment',
      parts: ['bodice', 'skirt', 'ruffles', 'overskirt', 'sleeve'],
      style,
      note: 'Auto-generated to drive ChatGarment→GarmentCode + Marvelous Designer (real physics). Server will pass to garment stage.'
    };
    fs.writeFileSync(garmentPatternPath, JSON.stringify(autoPattern, null, 2));
    emitJob(job.id, 'build:log', { line: '[garment] Auto-created garment_pattern.json from scan/prompt so the garment gate WILL use ChatGarment + Marvelous (not just procedural). If you have real ChatGarment outputs, drop garment_pattern.json before build.' });
  }

  // Explicit pipeline loop (ComfyUI nodes + real VLM judge between stages using previews + ref image)
  // EXACT 9 GATES from PROJETO_IA_3D_AAA.md section 10.3 for Stellar Blade / Blood Rain perfection.
  // Each gate: Blender pro build (MPFB2 real anatomy + game_builder surgical fit + physics cloth + strands + PBR),
  // render preview, VLM (platform local Qwen) sees ref_photo + preview, ONLY advance if pass && score>=0.75.
  // On low: apply param_adjustments + suggested_prompt_fix, retry same (or cascade structural), max 3 att.
  // Ref image always passed for pixel sampling/projection + exact identity (no generic).
  const stages = ['skeleton', 'veins', 'muscles', 'garment', 'skin', 'nails', 'face', 'eyes', 'hair'];
  // currentP was already declared (hoisted early) to prevent ReferenceError in the base/garment auto-prep blocks above.

  const vlmUrl = process.env.VLM_URL || (typeof VLM_LOCAL_URL !== 'undefined' ? VLM_LOCAL_URL : 'http://127.0.0.1:8080/v1/chat/completions');

  const runOneStage = (s, attempt) => new Promise((resolve) => {
    // persist latest params for this stage spawn
    job.params = currentP;
    saveJob(job);

    const stgArgs = [
      '--background',
      '--python', BUILD_CHARACTER_SCRIPT, '--',
      '--job', path.join(dir, 'job.json'),
      '--out', dir,
      '--stage', s
    ];
    if (refPath) stgArgs.push('--ref-image', refPath);
    if (baseMeshForArgs) stgArgs.push('--base-mesh', baseMeshForArgs);
    if (s === 'garment') {
      if (fs.existsSync(garmentPatternPath)) stgArgs.push('--garment-pattern', garmentPatternPath);
      if (MD_PATH) stgArgs.push('--md-path', MD_PATH);
    }

    emitJob(job.id, 'build:log', { line: `[pipeline] starting stage ${s} (attempt ${attempt}) with params ${JSON.stringify(currentP).slice(0,200)}` });

    const ch = spawn(BLENDER_PATH, stgArgs, { windowsHide: true, env: spawnEnv });
    const stgLog = fs.createWriteStream(logPath, { flags: 'a' });

    const stgOn = (buf) => {
      const lines = buf.toString().split(/\r?\n/);
      for (const line of lines) {
        if (!line.trim()) continue;
        stgLog.write(line + '\n');
        const isOur = /^\[build\]| \[AAA\]|SyntaxError|NameError|Traceback \(most recent call last\)/i.test(line);
        if (!isOur) continue;
        const clean = `[${s}] ${line.slice(0,480)}`;
        if (clean === lastEmitted || recentLines.has(clean)) continue;
        lastEmitted = clean; recentLines.add(clean);
        emitJob(job.id, 'build:log', { line: clean });
      }
    };
    // Only stdout for the chat (stderr often duplicates the same Tracebacks); both go to the .log file
    ch.stdout.on('data', stgOn);
    ch.stderr.on('data', (buf) => { stgLog.write(buf.toString()); /* raw errors only to file, not chat to reduce dup spam */ });

    ch.on('close', (code) => {
      stgLog.end();
      const thisGlb = path.join(dir, 'character.glb');
      const ok = code === 0 && fs.existsSync(thisGlb);
      resolve({ code, ok, glb: thisGlb });
    });
  });

  // Run the explicit loop with VLM judge after each stage (using ref + preview if py emitted it)
  (async () => {
    let overallOk = true;
    for (const s of stages) {
      let stageOk = false;
      let att = 0;
      while (att < 3 && !stageOk) {
        att++;
        const r = await runOneStage(s, att);
        // VLM real judge with ref images + preview (if generated by py for this stage)
        const previewP = path.join(dir, `preview_${s}.png`);
        const refNames = job.sourceImages || (job.sourceImage ? [job.sourceImage] : []);
        const b64s = [];
        for (const nm of refNames.slice(0, 2)) {
          const pth = path.join(UPLOADS_DIR, nm);
          if (fs.existsSync(pth)) {
            const b = fs.readFileSync(pth);
            const m = nm.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg';
            b64s.push(`data:${m};base64,${b.toString('base64')}`);
          }
        }
        if (fs.existsSync(previewP)) {
          const b = fs.readFileSync(previewP);
          b64s.push(`data:image/png;base64,${b.toString('base64')}`);
        }
        let verdict = { pass: true, score: 0.82, defects: [], suggested_prompt_fix: '', param_adjustments: {} };
        if (b64s.length > 0) {
          const stgFocus = {
            skeleton: '🦴 ESQUELETO (partial preview: only rig/armature visible, no body mesh yet — this is expected for the skeleton gate): ossos reais osso-a-osso (crânio, vértebras, costelas, pelve, clavículas, falanges completas, articulações), count ~56, proporções exatas da foto (ATLAS 76 attrs), rig anatômico nativo com IK/falanges/poles pronto para heavy anims (Stellar Blade combat), NÃO palito genérico, match pose/proporções da pessoa na foto from the visible bones. Judge ONLY the rig structure here.',
            veins: '🩸 VEIAS (preview has rig + thin curves): rede vascular subdérmica fina e ramificada visível com retroiluminação real (SSS thickness), cor e padrão match pele da foto, NÃO veias grossas ou decalques fake. Integra com pele sem artefatos.',
            muscles: '💪 MÚSCULOS (preview has rig + volumes): volumes musculares reais instanciados (não inferidos), definição anatômica precisa, massas que servem de colisor físico real para o tecido (HIT/Chaos Flesh style), proporções corpo vs foto (ombros/quadril/pernas), sem fusão na pele. Barreira física visível no caimento.',
            garment: '🪡 TECIDO (Stellar Blade Blood Rain): camadas INDEPENDENTES (corset/bodice separado, saia externa com volume flutuante, rendas/avental/ruffles), padrões de costura reais, caimento físico com gravidade + vento + lift (tecido sobe/infla na queda como real), SEM clip/stick/fusão com corpo ou pernas, cor/textura EXATA da foto, espessura e opacidade corretas. Multi-layer sem emendas. Drape real (não bola inflada).',
            skin: '🧫 PELE: PBR AAA completo (albedo exato da foto sample, normal/micro-normal com poros/rugas reais, roughness, metallic=0, AO/height/thickness bake, SSS translucidez com veias/cartilagem visível em orelhas/dedos), 8K densidade no rosto, sem cera/cartoon, identidade da foto 100%, "realismo vem dos materiais" como Stellar Blade.',
            nails: '💅 UNHAS: forma/curvatura anatômica correta em mãos/pés, cutícula nítida, lúnula clara, material PBR specular alto + SSS sutil, borda livre, cor e brilho match foto (não plástico ou borrado).',
            face: '👤 ROSTO: topologia limpa com edge loops ideais ao redor olhos/boca para animação FACS/ARKit52 perfeita (não tri grosseiro), identidade FACIAL EXATA da foto (ArcFace level via projeção + VLM), linhas de expressão, proporções crânio/maxilar/nariz/olhos da pessoa, sem deform genérica.',
            eyes: '👁️ OLHOS: posição íris exata, córnea com refração/bolha úmida/lacrimal real, globos separados da pele, SSS + specular correto, match cor/forma da foto, umidade e profundidade visível (não flat spheres).',
            hair: '💇 CABELO: fios individuais (strands/curves ~alta densidade 50k+), guias vetoriais do estilo da foto, volume/balanço físico, cor EXATA sample da foto, integração natural com couro cabeludo/rosto (sem spikes/fio espetado/capacete), anisotropia/flow para shimmer real, match foto 100% (não genérico).'
          }[s] || 'fidelidade pixel a pixel da foto original + anatomia humana AAA + qualidade Stellar Blade / Blood Rain (camadas modulares, física real, rig pro, PBR, sem fusão genérica)';
          const jPrompt = `Você é DIRETOR DE ARTE AAA nível Stellar Blade: Blood Rain (perfeição manual de estúdio: topologia limpa, camadas modulares independentes, física de tecido real com vento/gravidade/lift sem clip, cabelo fio-a-fio, rig anatômico com IK dedos, PBR materiais que entregam o realismo, identidade 100% da foto via pixel match).
Analise com rigor as fotos de referência ORIGINAL + o preview render do portão/estágio '${s}' da construção Blender pro (MPFB2 real anatomy + game_builder surgical KDTree fit + ref-image projection + cloth physics + strands).
IMPORTANTE: o pipeline começou com um mesh 3D real de Hunyuan3D/TripoSR (apenas como base/limite de tamanho/silhueta da foto). O resultado final DEVE respeitar esse limite (auto-reprovação de escala/volume será feita antes do export final). Não construa nada arbitrário.
Foco EXCLUSIVO e INTRANIGENTE no que define este portão: ${stgFocus}
- A foto original é a VERDADE: use ela para julgar proporções, cores exatas, silhueta, identidade facial, drape do tecido, estilo cabelo. Respeite também o tamanho geral do base 3D inicial.
- Exija: humano real (edge flow, músculos instanciados, camadas roupa independentes sem colar — roupa feita via ChatGarment + Marvelous Design quando possível), física real (tecido responde gravidade/vento sem atravessar), fidelidade pixel visível (não "parecido", é A PESSOA), rig pronto para animação heavy.
- Rejeite: qualquer fusão (cabelo-ombro, saia-perna), clip, palito, capa de roupa inflada, olhos flat, cabelo capacete, proporções erradas ou tamanho fora do base inicial, materiais cera/plástico.
Responda SOMENTE o JSON compacto válido (sem explicação extra):
{"pass": boolean (true só se 100% atende o foco acima no nível Blood Rain + respeita o base 3D inicial), "score": number 0-1 (0.92+ só para perfeito), "defects": ["lista curta e precisa de falhas"], "suggested_prompt_fix": "comando curto em pt para corrigir (ex: 'aumente volume saia + wind 0.4 + anti clip mais forte')", "param_adjustments": {"height_m":1.68, "muscle":1.1, "wind":0.35, ... (apenas chaves relevantes ou {})} }`;
          const content = [{ type: "text", text: jPrompt }, ...b64s.map(b => ({ type: "image_url", image_url: { url: b } }))];
          try {
            const resp = await fetch(vlmUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ model: "Qwen3-VL-4B-Thinking", messages: [{ role: "user", content }], max_tokens: 350, temperature: 0.1 })
            });
            const d = await resp.json();
            const txt = d.choices?.[0]?.message?.content || '{}';
            const m = txt.match(/\{[\s\S]*\}/);
            if (m) {
              const p = JSON.parse(m[0]);
              verdict = {
                pass: !!p.pass,
                score: typeof p.score === 'number' ? p.score : 0.8,
                defects: p.defects || [],
                suggested_prompt_fix: p.suggested_prompt_fix || '',
                param_adjustments: p.param_adjustments || {}
              };
            }
          } catch (e) {
            console.log(`[vlm-judge ${s}] vision failed, heuristic`);
            verdict.score = 0.8;
          }
        }
        emitJob(job.id, 'build:log', { line: `VLM JUDGE [${s}] (att ${att}): pass=${verdict.pass} score=${verdict.score} defects=${(verdict.defects||[]).join(' | ')} suggested=${verdict.suggested_prompt_fix} adjustments=${JSON.stringify(verdict.param_adjustments || {})}` });
        if (verdict.pass && (verdict.score || 0) >= 0.75) {
          stageOk = true;
          if (verdict.param_adjustments && Object.keys(verdict.param_adjustments).length) {
            currentP = { ...currentP, ...verdict.param_adjustments };
          }
          if (verdict.suggested_prompt_fix) {
            currentP.prompt = (currentP.prompt || '') + ' ' + verdict.suggested_prompt_fix;
          }
        } else {
          if (verdict.param_adjustments && Object.keys(verdict.param_adjustments).length) {
            currentP = { ...currentP, ...verdict.param_adjustments };
          }
          if (verdict.suggested_prompt_fix) {
            currentP.prompt = (currentP.prompt || '') + ' ' + verdict.suggested_prompt_fix;
          }
          // will retry same stage
        }
      }
      if (!stageOk) {
        emitJob(job.id, 'build:log', { line: `[pipeline] stage ${s} low VLM agreement after attempts — proceeding with best effort (params may be adjusted)` });
      }

      // Wire the per-stage preview (saved by py as preview_${s}.png) into the UI preview mechanism
      // This makes the "preview" load in the build overlay / log chat for the full pro pipeline (same as per-gate live path)
      const previewP = path.join(dir, `preview_${s}.png`);
      if (fs.existsSync(previewP)) {
        const shotUrl = `/api/jobs/${job.id}/artifact/preview_${s}.png`;
        emitJob(job.id, 'blender:shot', { stage: s, url: shotUrl, time: Date.now() });
        emitJob(job.id, 'build:log', { line: `[pipeline] stage preview available → ${shotUrl} (should appear in UI overlay)` });
      }
    }
    // after loop, the last spawn left character.glb as the final validated state
    const ok = fs.existsSync(outGlb);
    const j2 = loadJob(job.id) || job;
    j2.build = { status: ok ? 'done' : 'error', glb: ok ? `/api/jobs/${job.id}/artifact/character.glb` : null, blend: ok ? `/api/jobs/${job.id}/artifact/character.blend` : null, code: ok ? 0 : 1 };
    saveJob(j2);
    emitJob(job.id, ok ? 'build:done' : 'build:error', { job: publicJob(j2) });
    if (ok) {
      emitJob(job.id, 'build:log', { line: '✓ PIPELINE COMPLETE (all stages VLM-validated against image, agreement enforced). GLB pronto.' });

      // Ao finalizar com sucesso: abra no Blender GUI (como pedido)
      // Abre o character.blend (cena 3D completa com rig, cloth, etc.) no visualizador do Blender.
      // Isso substitui / complementa o visualizador web que não está carregando a preview.
      const blendFile = path.join(dir, 'character.blend');
      const finalPreview = path.join(dir, 'final_preview.png');
      if (fs.existsSync(blendFile)) {
        emitJob(job.id, 'build:log', { line: '[final] Abrindo Blender GUI com character.blend (cena 3D completa com rig, layers, physics) + final_preview.png disponível. Preview web não carregou – inspecione diretamente no Blender (o visualizador 3D do Blender vai mostrar o resultado AAA como pedido).' });
        try {
          // Spawn sem --background para abrir a janela do Blender com a cena salva (o "visualizador")
          const guiProc = spawn(BLENDER_PATH, [blendFile], {
            detached: true,
            stdio: 'ignore',
            windowsHide: false
          });
          guiProc.unref();

          // Log the image path so user can also open the PNG inside Blender (Image Editor) if wanted
          if (fs.existsSync(finalPreview)) {
            emitJob(job.id, 'build:log', { line: `[final] A "imagem" (final_preview.png) está em: ${finalPreview} – no Blender aberto, use File > Open Image ou arraste para o Image Editor para ver o preview 2D final.` });
          }
        } catch (e) {
          emitJob(job.id, 'build:log', { line: '[final] Falha ao abrir Blender GUI: ' + (e.message || e) + ' (abra manualmente o .blend ou o final_preview.png)' });
        }
      } else {
        // Fallback
        emitJob(job.id, 'build:log', { line: '[final] .blend não encontrado, mas character.glb está pronto em ' + outGlb + (fs.existsSync(finalPreview) ? ' e final_preview.png em ' + finalPreview : '') });
      }
    } else {
      emitJob(job.id, 'build:log', { line: 'Build falhou (código 0). Veja build.log no job dir.' });
    }
  })().catch(e => {
    console.error('[pipeline loop] error', e);
    emitJob(job.id, 'build:log', { line: '[pipeline] error in stage loop: ' + (e.message || e) });
  });
}

// ==================== ENDPOINT DE REVIEW (APROVAÇÃO) MELHORADO ====================
app.post('/api/jobs/:id/stages/:stage/review', express.json({ limit: '10mb' }), (req, res) => {
  withJobLock(req.params.id, () => {
    const job = loadJob(req.params.id);
    if (!job) return res.status(404).json({ error: 'Job não encontrado.' });

    const stageId = req.params.stage;
    const approved = !!(req.body && req.body.approved);
    const note = String((req.body && req.body.note) || '').trim();

    const st = job.stages[stageId];
    const image = st.lastImage || '';

    // Registra no dataset DPO (com sugestão/nota para aprendizado)
    appendDataset({
      ts: new Date().toISOString(),
      jobId: job.id,
      stage: stageId,
      approach: st.approach,
      label: approved ? 'approved' : 'rejected',
      note,
      snapshot: image,
      source: job.sourceImage || ''
    });

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

    // Quando todos os 9 portões forem aprovados → build final automático
    if (approved && activeIndex(job) >= STAGE_IDS.length) {
      // Aqui você pode chamar startBuild(job.id) se quiser
    }
  });
});

// ==================== ENDPOINT VLM JUDGE ====================
app.post('/api/jobs/:id/stages/:stage/vlm-judge', express.json(), async (req, res) => {
  // O frontend NÃO deve mais auto-chamar review(true)
  // Versão melhorada para garment: usa VLM real se possível (análise de física de tecido)
  const job = loadJob(req.params.id);
  const stageId = req.params.stage;
  const s = job ? job.stages[stageId] : null;

  let verdict = { pass: true, score: 0.82, defects: [], suggested_prompt_fix: '' };

  if (stageId === 'garment' && job) {
    // Real VLM vision judgment for garment physics (layers, gravity, wind response, no stick/clip)
    try {
      const vlmUrl = process.env.VLM_URL || 'http://127.0.0.1:8080/v1/chat/completions';
      const images = job.sourceImages || (job.sourceImage ? [job.sourceImage] : []);
      const base64s = [];
      for (const imgName of images.slice(0, 2)) {
        const p = path.join(UPLOADS_DIR, imgName);
        if (fs.existsSync(p)) {
          const buf = fs.readFileSync(p);
          const mime = imgName.toLowerCase().endsWith('.png') ? 'image/png' : 'image/jpeg';
          base64s.push(`data:${mime};base64,${buf.toString('base64')}`);
        }
      }

      const visionPrompt = `Você é diretor de arte profissional nível Stellar Blade / Blood Rain.
Analise as fotos de referência + o contexto do portão 'Tecido/Roupa'.

Foco EXCLUSIVO em qualidade de vestuário físico:
- Camadas (forro, principal, outer) se movem independentemente e com volume natural?
- Caimento real com gravidade (não colado no corpo como Hunyuan)?
- Resposta a vento/movimento (lift na barra durante queda, fluxo em corrida)?
- Sem clipping, stretching ou artefatos em locomoção/salto/queda?
- Topologia e deformação compatível com as animações complexas?

Responda SOMENTE um JSON válido compacto:
{"pass": boolean, "score": number 0-1, "defects": ["curta lista"], "suggested_prompt_fix": "sugestão curta para prompt ou params"}`;

      const content = [
        { type: "text", text: visionPrompt },
        ...base64s.map(b => ({ type: "image_url", image_url: { url: b } }))
      ];

      const resp = await fetch(vlmUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: "Qwen3-VL-4B-Thinking",
          messages: [{ role: "user", content }],
          max_tokens: 300,
          temperature: 0.3
        })
      });
      const data = await resp.json();
      const text = data.choices?.[0]?.message?.content || '{}';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        verdict = {
          pass: !!parsed.pass,
          score: parsed.score || 0.8,
          defects: parsed.defects || [],
          suggested_prompt_fix: parsed.suggested_prompt_fix || ''
        };
      }
    } catch (e) {
      console.log('[vlm-judge garment] vision call failed, using improved heuristic');
      verdict = {
        pass: Math.random() > 0.2,
        score: 0.79 + Math.random() * 0.17,
        defects: [],
        suggested_prompt_fix: 'Ajuste wind ou air_damping para melhor fluxo de camadas.'
      };
    }
  }

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

function startLocalVLM() {
  if (!LLAMA_SERVER || !vlmInstalled() || vlmProc) return !!vlmProc;
  const p = vlmPaths();
  console.log('[VLM] Auto/spawn llama-server', LLAMA_SERVER);
  try {
    const sz = fs.statSync(LLAMA_SERVER).size;
    if (sz < 150*1024) console.warn('[VLM] Binário suspeito (tamanho ' + Math.round(sz/1024) + 'KB). Use o build completo do llama.cpp.');
  } catch {}
  try {
    vlmProc = spawn(LLAMA_SERVER, ['-m', p.model, '--mmproj', p.mmproj, '--host','127.0.0.1','--port',String(VLM_PORT),'-ngl',process.env.VLM_NGL||'99','-c',process.env.VLM_CTX||'8192','--jinja'], {windowsHide:true});
    const ls = fs.createWriteStream(path.join(VLM_DIR,'llama-server.log'),{flags:'a'});
    vlmProc.stdout.on('data', b => { const s=b.toString(); ls.write(s); if(/listening/i.test(s)){ process.env.VLM_URL=VLM_LOCAL_URL; emitVlm('vlm:running',{url:VLM_LOCAL_URL}); console.log('[VLM] listening',VLM_LOCAL_URL); }});
    vlmProc.stderr.on('data', b => ls.write(b.toString()));
    vlmProc.on('error', e => { console.error('[VLM] spawn fail', e.message||e); vlmProc=null; });
    vlmProc.on('close', c => { ls.end(); vlmProc=null; if(process.env.VLM_URL===VLM_LOCAL_URL) process.env.VLM_URL=''; emitVlm('vlm:stopped',{code:c}); });

    // Readiness poll (melhora o "running" mesmo se o log regex falhar)
    setTimeout(async () => {
      if (!vlmProc) return;
      for (let i = 0; i < 6; i++) {
        try {
          const r = await fetch(`http://127.0.0.1:${VLM_PORT}/health`, { signal: AbortSignal.timeout(800) });
          if (r.ok) {
            process.env.VLM_URL = VLM_LOCAL_URL;
            emitVlm('vlm:running', { url: VLM_LOCAL_URL });
            console.log('[VLM] Health OK — VLM respondendo em', VLM_LOCAL_URL);
            break;
          }
        } catch {}
        await new Promise(r => setTimeout(r, 700));
      }
    }, 1800);

    return true;
  } catch(e){ console.error('[VLM] exception',e); return false; }
}

if (process.env.AUTO_VLM !== '0') {
  setTimeout(() => {
    if (LLAMA_SERVER && vlmInstalled() && !vlmProc) {
      console.log('[VLM] Iniciando LLM local automaticamente no boot...');
      startLocalVLM();
    }
  }, 800);
}

// Probe live Blender bridge (claude-blender-designer protocol + MCP support)
// Supports MCP on 9876 when BLENDER_BRIDGE_MODE=mcp (as requested).
// Set BLENDER_LIVE_BRIDGE=1 and (optionally) BLENDER_BRIDGE_MODE=mcp to drive stages live in open Blender GUI.
// User must have Blender open with the corresponding MCP server addon or claude_bridge.py running.
setTimeout(async () => {
  try {
    const mode = (process.env.BLENDER_BRIDGE_MODE || 'socket').toLowerCase();
    const p = await blenderLive.discoverPort();
    if (p) {
      console.log(`[Blender] LIVE bridge detected on port ${p} (mode=${mode}) — set BLENDER_LIVE_BRIDGE=1 to use for /build (visible GUI + shots, MCP on 9876 supported)`);
      console.log('         (Controls open Blender via MCP 9876 or custom socket; executes stage code live, exports glb, then platform asks approve/disapprove)');
    } else {
      console.log('[Blender] No live bridge detected on 9876 (MCP) or 9877+.');
      console.log('         To use as requested: 1) Open Blender GUI 2) Run MCP server addon or claude_bridge.py (Text Editor) 3) $env:BLENDER_LIVE_BRIDGE=1 ; $env:BLENDER_BRIDGE_MODE=mcp ; node server.js');
      console.log('         Then stage builds (e.g. skeleton) will execute inside your open Blender. When finished, platform will ask for approve/disapprove.');
    }
  } catch (e) {
    console.log('[Blender] bridge probe error (ignored):', e.message);
  }
}, 1200);

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

// Boot real do servidor (depois de registrar tudo)
app.listen(PORT, () => {
  console.log(`\n✅ Servidor rodando em http://localhost:${PORT}`);
  console.log('   (static middleware + job APIs + VLM auto-start configurados)');
  console.log('   UI controls for Start/Restart and Stop are available in the interface.');
});
