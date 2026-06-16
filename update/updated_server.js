// server.js - Scanner 3D Cognitivo v6 (Complex Multi-Layer Costumes)
// Atualizado para suportar decomposição e reconstrução de figurinos complexos
// como Alice Liddell (Faca de Cozinha) com hierarquia de camadas físicas reais.

const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const multer = require('multer');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3939;

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Diretórios
const JOBS_DIR = path.join(__dirname, 'data', 'jobs');
const UPLOADS_DIR = path.join(__dirname, 'data', 'uploads');
const DATASET_PATH = path.join(__dirname, 'data', 'dpo_dataset.jsonl');

const upload = multer({ dest: UPLOADS_DIR });

// Garantir pastas
async function ensureDirs() {
  await fs.mkdir(JOBS_DIR, { recursive: true });
  await fs.mkdir(UPLOADS_DIR, { recursive: true });
}
ensureDirs();

// ==================== JOB MANAGEMENT ====================

async function loadJob(jobId) {
  const jobPath = path.join(JOBS_DIR, `job_${jobId}`, 'job.json');
  try {
    const data = await fs.readFile(jobPath, 'utf8');
    return JSON.parse(data);
  } catch {
    return null;
  }
}

async function saveJob(job) {
  const jobDir = path.join(JOBS_DIR, `job_${job.id}`);
  await fs.mkdir(jobDir, { recursive: true });
  await fs.writeFile(path.join(jobDir, 'job.json'), JSON.stringify(job, null, 2));
}

function publicJob(job) {
  const { stages, ...rest } = job;
  return { ...rest, stages: stages || {} };
}

// ==================== SSE ====================

const clients = new Map();

function emitJob(jobId, event, data) {
  const resList = clients.get(jobId) || [];
  resList.forEach(res => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  });
}

// ==================== ROUTES ====================

app.get('/', (req, res) => {
  res.send('Scanner 3D Cognitivo v6 - Complex Garment Layers Ready');
});

// Criar job com suporte a múltiplas imagens + costume concept
app.post('/api/jobs', upload.array('images', 10), async (req, res) => {
  const jobId = Date.now().toString(36) + Math.random().toString(36).substr(2);
  const jobDir = path.join(JOBS_DIR, `job_${jobId}`);
  await fs.mkdir(jobDir, { recursive: true });

  const images = req.files.map(f => ({
    originalname: f.originalname,
    path: f.path,
    filename: f.filename
  }));

  const job = {
    id: jobId,
    createdAt: new Date().toISOString(),
    sourceImages: images,
    referenceLinks: req.body.referenceLinks || [],
    prompt: req.body.prompt || '',
    params: {},
    stages: {},
    costume: null,                    // Novo: costume_layers.json
    garment_pattern: null,            // Legado
    status: 'created',
    build: { currentStage: null, completed: [] }
  };

  await saveJob(job);
  res.json({ jobId, job: publicJob(job) });
});

// Análise de figurino complexa (NOVO - usa VLM para gerar costume_layers.json)
app.post('/api/jobs/:id/costume/analyze', async (req, res) => {
  const { id } = req.params;
  const job = await loadJob(id);
  if (!job) return res.status(404).json({ error: 'Job not found' });

  // Chama script Python que usa Qwen3-VL + Florence-2 para analisar as imagens
  // e gerar costume_layers.json estruturado (hierarquia, física, materiais)
  const pythonScript = path.join(__dirname, 'python', 'analyze_costume_layers.py');
  
  const args = [
    '--job', id,
    '--images', JSON.stringify(job.sourceImages.map(i => i.path)),
    '--out', path.join(JOBS_DIR, `job_${id}`, 'costume_layers.json')
  ];

  const proc = spawn('python3', [pythonScript, ...args]);
  
  let output = '';
  proc.stdout.on('data', d => output += d);
  proc.stderr.on('data', d => console.error(d.toString()));

  proc.on('close', async (code) => {
    if (code === 0) {
      try {
        const costumeData = JSON.parse(await fs.readFile(
          path.join(JOBS_DIR, `job_${id}`, 'costume_layers.json'), 'utf8'
        ));
        job.costume = costumeData;
        job.status = 'costume_analyzed';
        await saveJob(job);
        emitJob(id, 'costume_analyzed', { costume: costumeData });
        res.json({ success: true, costume: costumeData });
      } catch (e) {
        res.status(500).json({ error: 'Failed to parse costume layers' });
      }
    } else {
      res.status(500).json({ error: 'Costume analysis failed' });
    }
  });
});

// Atualizar / aceitar costume_layers.json manualmente (útil para sheets detalhados)
app.post('/api/jobs/:id/costume', async (req, res) => {
  const { id } = req.params;
  const job = await loadJob(id);
  if (!job) return res.status(404).json({ error: 'Job not found' });

  job.costume = req.body.costume_layers; // JSON completo
  await saveJob(job);
  res.json({ success: true });
});

// Build de stage específico (atualizado para suportar layers de figurino)
app.post('/api/jobs/:id/stages/:stage/build', async (req, res) => {
  const { id, stage } = req.params;
  const job = await loadJob(id);
  if (!job) return res.status(404).json({ error: 'Job not found' });

  job.build.currentStage = stage;
  job.stages[stage] = { status: 'running', startedAt: new Date().toISOString() };
  await saveJob(job);

  emitJob(id, 'stage_started', { stage });

  const jobDir = path.join(JOBS_DIR, `job_${id}`);
  const outDir = path.join(jobDir, 'build', stage);
  await fs.mkdir(outDir, { recursive: true });

  // Chama build_stage.py com suporte a --costume-layers
  const blenderArgs = [
    '--background',
    '--python', path.join(__dirname, 'blender', 'build_stage.py'),
    '--',
    '--job', id,
    '--stage', stage,
    '--out', outDir,
    '--ref-image', job.sourceImages[0]?.path || '',
  ];

  if (job.costume) {
    blenderArgs.push('--costume-layers', path.join(jobDir, 'costume_layers.json'));
  }
  if (job.garment_pattern) {
    blenderArgs.push('--garment-pattern', JSON.stringify(job.garment_pattern));
  }

  const proc = spawn('blender', blenderArgs, { cwd: __dirname });

  let log = '';
  proc.stdout.on('data', data => {
    log += data.toString();
    emitJob(id, 'build_log', { stage, message: data.toString() });
  });

  proc.stderr.on('data', data => {
    log += data.toString();
    emitJob(id, 'build_log', { stage, message: data.toString(), level: 'error' });
  });

  proc.on('close', async (code) => {
    const success = code === 0;
    
    // NOVO: Verificar julgamento do VLM e lógica de re-tentativa
    const judgmentPath = path.join(outDir, `${stage}_judgment.json`);
    let vlmResult = null;
    let shouldRetry = false;

    if (fs.existsSync(judgmentPath)) {
      try {
        vlmResult = JSON.parse(await fs.readFile(judgmentPath, 'utf8'));
        shouldRetry = vlmResult.should_retry === true;
        
        job.stages[stage].vlm_judgment = vlmResult;
        
        if (shouldRetry && (job.stages[stage].retry_count || 0) < 2) {
          console.log(`[Auto-Retry] VLM solicitou retry na etapa ${stage}. Tentativa ${ (job.stages[stage].retry_count || 0) + 1 }`);
          job.stages[stage].retry_count = (job.stages[stage].retry_count || 0) + 1;
          await saveJob(job);
          
          // Re-dispara o build da mesma etapa (simplificado)
          // Em produção: usar fila ou emitir evento para retry controlado
          emitJob(id, 'stage_retry_triggered', { stage, reason: vlmResult.suggestions });
        }
      } catch (e) {
        console.error("Erro ao ler judgment:", e);
      }
    }

    job.stages[stage] = {
      ...job.stages[stage],
      status: success ? (shouldRetry ? 'needs_retry' : 'awaiting_review') : 'error',
      finishedAt: new Date().toISOString(),
      log: log.slice(-5000),
      vlm_judgment: vlmResult
    };
    
    if (success && !shouldRetry) job.build.completed.push(stage);
    await saveJob(job);

    emitJob(id, 'stage_finished', { stage, status: job.stages[stage].status, vlm: vlmResult });
    res.json({ success, stage, status: job.stages[stage].status, vlm_judgment: vlmResult });
  });
});

// Review / Aprovação de stage (atualizado para registrar DPO de qualidade de tecido)
app.post('/api/jobs/:id/stages/:stage/review', async (req, res) => {
  const { id, stage } = req.params;
  const { approved, rating, feedback, suggested_prompt } = req.body;
  const job = await loadJob(id);
  if (!job) return res.status(404).json({ error: 'Job not found' });

  const stageData = job.stages[stage] || {};
  stageData.status = approved ? 'approved' : 'rejected';
  stageData.review = { rating, feedback, suggested_prompt, reviewedAt: new Date().toISOString() };

  // Registra no DPO dataset (especialmente útil para garment layers)
  if (stage.includes('garment') || stage.includes('corset') || stage.includes('skirt')) {
    const dpoEntry = {
      timestamp: new Date().toISOString(),
      job_id: id,
      stage,
      preferred: approved ? 'approved' : 'rejected',
      rating,
      feedback,
      suggested_prompt,
      costume_layer: job.costume?.layers?.find(l => l.id.includes(stage)) || null
    };
    await fs.appendFile(DATASET_PATH, JSON.stringify(dpoEntry) + '\n');
  }

  await saveJob(job);
  emitJob(id, 'stage_reviewed', { stage, approved, rating });

  // Auto-avança se aprovado e não for o último
  if (approved && job.build.currentStage) {
    // Lógica de próximo stage pode ser adicionada aqui ou no frontend
  }

  res.json({ success: true, stage: stageData });
});

// Pipeline completo atualizado (suporta costume)
app.post('/api/jobs/:id/build', async (req, res) => {
  const { id } = req.params;
  const job = await loadJob(id);
  if (!job) return res.status(404).json({ error: 'Job not found' });

  // Ordem expandida para figurinos complexos
  const fullStages = [
    'skeleton', 'muscles',
    'inner_base', 'corset', 'underskirt', 'overskirt',
    'sleeves', 'back_assembly', 'legwear', 'accessories',
    'skin', 'hair', 'final_assembly'
  ];

  job.build.fullPipeline = true;
  await saveJob(job);

  // Dispara stages sequencialmente (ou em paralelo controlado)
  // Por simplicidade, o frontend pode chamar um por um com aprovação.
  // Aqui apenas iniciamos o primeiro.
  res.json({ 
    message: 'Full pipeline started. Use /stages/:stage/build for each layer with human approval.',
    recommendedOrder: fullStages,
    costume: job.costume
  });
});

// SSE
app.get('/api/jobs/:id/events', (req, res) => {
  const { id } = req.params;
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  if (!clients.has(id)) clients.set(id, []);
  clients.get(id).push(res);

  req.on('close', () => {
    const list = clients.get(id) || [];
    clients.set(id, list.filter(r => r !== res));
  });
});

app.listen(PORT, () => {
  console.log(`Scanner 3D Cognitivo v6 rodando na porta ${PORT}`);
  console.log('Suporte a figurinos complexos multi-camadas ativado.');
});