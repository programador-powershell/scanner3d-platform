const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { inspectGlb } = require('./glb');

const running = new Map();
function startBuild({ job, stage, root, jobsDir, blender, saveJob, loadJob, emitJob, publicJob = j => j }) {
  if (running.has(job.id)) throw Object.assign(new Error('Este job já está construindo uma malha.'), { status: 409 });
  if (!blender || !fs.existsSync(blender)) throw Object.assign(new Error('Blender não encontrado. Configure BLENDER_PATH.'), { status: 503 });
  const dir = path.join(jobsDir, job.id);
  const source = path.join(dir, 'source.glb');
  if (!fs.existsSync(source)) throw Object.assign(new Error('Falta uma malha 3D real. Importe um GLB ou conecte um serviço de reconstrução; nenhuma geometria genérica será criada.'), { status: 422 });
  const sourceStats = inspectGlb(fs.readFileSync(source));
  const isFull = stage === 'full';
  const out = path.join(dir, `run_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  fs.mkdirSync(out, { recursive: true });
  job.build = { status: 'running', stage, startedAt: new Date().toISOString(), sourceSha256: sourceStats.sha256 };
  if (!isFull) job.stages[stage].status = 'building';
  saveJob(job);
  const args = ['--background', '--factory-startup', '--python-exit-code', '1', '--python',
    path.join(root, 'blender/build_character.py'), '--', '--job', path.join(dir, 'job.json'),
    '--out', out, '--stage', stage, '--base-mesh', source];
  const log = fs.createWriteStream(path.join(dir, isFull ? 'build.log' : `${stage}.log`));
  const child = spawn(blender, args, { windowsHide: true });
  running.set(job.id, child);
  emitJob(job.id, isFull ? 'build:started' : 'stage:build:start', { stage, job: publicJob(job) });
  let finished = false;
  const timeout = setTimeout(() => { child.kill(); finish(new Error('Build excedeu 10 minutos. Consulte o log.')); }, 600000);
  const onData = bytes => {
    log.write(bytes);
    for (const line of bytes.toString().split(/\r?\n/).filter(Boolean))
      if (/^\[build\]|Error|Traceback/.test(line)) emitJob(job.id, isFull ? 'build:log' : 'stage:build:log', { stage, line: line.slice(0, 500) });
  };
  child.stdout.on('data', onData); child.stderr.on('data', onData);
  child.on('error', error => finish(error));
  child.on('close', code => finish(code === 0 ? null : new Error(`Blender encerrou com código ${code}.`)));
  function finish(error) {
    if (finished) return; finished = true; clearTimeout(timeout); running.delete(job.id); log.end();
    const fresh = loadJob(job.id);
    if (!fresh) return;
    let stats;
    try {
      if (error) throw error;
      const glb = path.join(out, 'character.glb');
      if (!fs.existsSync(glb)) throw new Error('Blender não produziu o GLB desta execução.');
      stats = inspectGlb(fs.readFileSync(glb));
      const artifacts = ['character.glb', 'character.blend', 'character.fbx', 'build_report.json',
        'preview_front.png', 'preview_side.png', 'preview_back.png'];
      for (const artifact of artifacts) {
        const from = path.join(out, artifact);
        if (!fs.existsSync(from)) throw new Error(`Artefato obrigatório ausente: ${artifact}`);
      }
      for (const artifact of artifacts) fs.copyFileSync(path.join(out, artifact), path.join(dir, artifact));
      if (!isFull) {
        fs.copyFileSync(glb, path.join(dir, `${stage}.glb`));
        fs.copyFileSync(path.join(out, 'preview_front.png'), path.join(dir, `preview_${stage}.png`));
      }
      const url = file => `/api/jobs/${job.id}/artifact/${file}?v=${stats.sha256.slice(0, 12)}`;
      fresh.build = { status: 'done', stage, glb: url('character.glb'), blend: url('character.blend'),
        fbx: url('character.fbx'), report: url('build_report.json'), sha256: stats.sha256,
        completedAt: new Date().toISOString(), geometrySource: 'imported-mesh', fidelityStatus: 'awaiting_review' };
      if (!isFull) {
        fresh.stages[stage].status = 'awaiting_review';
        fresh.stages[stage].lastImage = url(`preview_${stage}.png`);
        fresh.stages[stage].glb = url(`${stage}.glb`);
        fresh.stages[stage].sha256 = stats.sha256;
        fresh.stages[stage].builtFromSourceSha256 = sourceStats.sha256;
        fresh.stages[stage].lastVerdict = null;
      }
      saveJob(fresh);
      emitJob(job.id, isFull ? 'build:done' : 'stage:build:done', { stage, glb: url(isFull ? 'character.glb' : `${stage}.glb`), job: publicJob(fresh) });
      emitJob(job.id, 'build:log', { line: 'GLB, FBX, .blend e três renders exportados da malha importada. Fidelidade e física continuam pendentes de avaliação.' });
    } catch (failure) {
      fresh.build = { ...fresh.build, status: 'error', error: failure.message };
      if (!isFull) fresh.stages[stage].status = 'error';
      saveJob(fresh);
      emitJob(job.id, isFull ? 'build:error' : 'stage:build:error', { stage, error: failure.message, job: publicJob(fresh) });
    }
  }
  return { started: true, sourceSha256: sourceStats.sha256 };
}

module.exports = { startBuild };
