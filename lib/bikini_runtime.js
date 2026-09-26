'use strict';
// Optional external Blender fork. No downloads, shell commands or cloud provisioning.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn } = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const LOCK = require('../config/bikini.lock.json');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const failure = (message, code = 'BIKINI_NOT_READY') => Object.assign(new Error(message), { code, status: 503 });

function fileHash(file) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(file, 'r');
  try {
    const buffer = Buffer.alloc(1024 * 1024);
    let n;
    while ((n = fs.readSync(fd, buffer, 0, buffer.length, null)) > 0) hash.update(buffer.subarray(0, n));
  } finally { fs.closeSync(fd); }
  return hash.digest('hex');
}

function fileHeader(file) {
  const fd = fs.openSync(file, 'r');
  try { const b = Buffer.alloc(160); return b.subarray(0, fs.readSync(fd, b, 0, b.length, 0)); }
  finally { fs.closeSync(fd); }
}

function inspectInstallation({ env = process.env, platform = process.platform, arch = process.arch, lock = LOCK } = {}) {
  if (env.BIKINI_ALLOW_UNOFFICIAL !== '1') throw failure('BIKINI é não oficial. Defina BIKINI_ALLOW_UNOFFICIAL=1 somente após revisar a origem.', 'BIKINI_OPT_IN_REQUIRED');
  if (platform !== lock.platform || arch !== lock.arch) throw failure('Este pacote BIKINI exige Windows x64. O Blender normal permanece disponível.', 'BIKINI_PLATFORM');
  const requested = env.BIKINI_PATH;
  if (!requested || !path.isAbsolute(requested)) throw failure('Configure BIKINI_PATH com o caminho absoluto de blender.exe.', 'BIKINI_PATH');
  if (!fs.existsSync(requested) || !fs.statSync(requested).isFile()) throw failure('Executável BIKINI não encontrado.', 'BIKINI_PATH');
  const executable = fs.realpathSync(requested);
  if (path.basename(executable).toLowerCase() !== lock.executable.name) throw failure('BIKINI_PATH deve apontar para blender.exe, não um launcher.', 'BIKINI_PATH');
  const header = fileHeader(executable);
  if (header.toString().startsWith('version https://git-lfs.github.com/spec/v1')) throw failure('blender.exe ainda é um ponteiro Git LFS. Execute git lfs pull na pasta BIKINI.', 'BIKINI_LFS_POINTER');
  if (header.subarray(0, 2).toString() !== 'MZ' || fs.statSync(executable).size !== lock.executable.size || fileHash(executable) !== lock.executable.sha256)
    throw failure('Executável não corresponde à revisão fixada em config/bikini.lock.json. Não foi executado.', 'BIKINI_DIGEST');
  const directory = path.dirname(executable);
  for (const rel of lock.requiredDirectories) {
    const p = path.join(directory, rel);
    if (!fs.existsSync(p) || !fs.statSync(p).isDirectory()) throw failure(`Pacote incompleto: falta ${rel}/. Extraia a distribuição inteira.`, 'BIKINI_PACKAGE');
  }
  const files = {};
  for (const rel of lock.requiredFiles) {
    const p = path.join(directory, rel);
    if (!fs.existsSync(p) || !fs.statSync(p).isFile() || !fs.statSync(p).size) throw failure(`Pacote incompleto: falta ${rel}.`, 'BIKINI_PACKAGE');
    const head = fileHeader(p);
    if (head.toString().startsWith('version https://git-lfs.github.com/spec/v1')) throw failure(`Git LFS não hidratado: ${rel}.`, 'BIKINI_LFS_POINTER');
    if (rel.endsWith('.dll') && head.subarray(0, 2).toString() !== 'MZ') throw failure(`DLL inválida: ${rel}.`, 'BIKINI_PACKAGE');
    files[rel] = fileHash(p);
  }
  // Records essential files, not a signature/certification of every resource in the package.
  return { backend: 'bikini', executable, executableSha256: lock.executable.sha256,
    revision: lock.revision, official: false, requiredFileHashes: files,
    packageFingerprint: sha(JSON.stringify({ revision: lock.revision, exe: lock.executable.sha256, files })) };
}

function stateDir(root = ROOT) { return path.join(root, 'data', 'bikini-runtime'); }
function readProbe(root = ROOT) {
  const file = path.join(stateDir(root), 'latest.json');
  if (!fs.existsSync(file)) throw failure('Execute npm run bikini:probe antes de usar BIKINI.', 'BIKINI_PROBE_REQUIRED');
  const st = fs.lstatSync(file);
  if (!st.isFile() || st.isSymbolicLink() || st.size > 8 * 1024 * 1024) throw failure('Relatório BIKINI inválido.', 'BIKINI_PROBE_INVALID');
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch { throw failure('Relatório BIKINI inválido.', 'BIKINI_PROBE_INVALID'); }
}

function validateProbe(report, runtime, root = ROOT) {
  if (report.schemaVersion !== 1 || report.status !== 'export_smoke_passed' ||
      report.executableSha256 !== runtime.executableSha256 || report.packageFingerprint !== runtime.packageFingerprint ||
      report.revision !== runtime.revision || report.probeScriptSha256 !== fileHash(path.join(root, 'blender/bikini_probe.py')) ||
      !/^run_[a-f0-9]{32}$/.test(report.runId || '')) throw failure('Probe ausente ou desatualizado; execute npm run bikini:probe.', 'BIKINI_PROBE_STALE');
  const folder = path.join(stateDir(root), report.runId);
  for (const name of ['probe.json', 'calibration.glb', 'calibration.fbx', 'calibration.blend']) {
    const p = path.join(folder, name);
    if (!report.artifactHashes?.[name] || !fs.existsSync(p) || fs.lstatSync(p).isSymbolicLink() || fileHash(p) !== report.artifactHashes[name])
      throw failure('Evidência do probe ausente ou alterada. Execute novamente.', 'BIKINI_PROBE_STALE');
  }
  let native;
  try { native = JSON.parse(fs.readFileSync(path.join(folder, 'probe.json'), 'utf8')); }
  catch { throw failure('Evidência JSON do probe inválida.', 'BIKINI_PROBE_INVALID'); }
  validateNativeProbe(native, report.runId.slice(4));
  if (JSON.stringify(native) !== JSON.stringify(report.native)) throw failure('Resumo diverge da evidência do probe.', 'BIKINI_PROBE_STALE');
  return report;
}

function resolveRuntime({ preferredPath, env = process.env, root = ROOT, platform = process.platform, arch = process.arch } = {}) {
  const backend = env.BLENDER_BACKEND || 'blender';
  if (!['blender', 'bikini'].includes(backend)) throw failure('BLENDER_BACKEND deve ser blender ou bikini.', 'BLENDER_BACKEND');
  if (backend === 'bikini') {
    const runtime = inspectInstallation({ env, platform, arch });
    const report = validateProbe(readProbe(root), runtime, root);
    return { ...runtime, probeRunId: report.runId, version: report.native.version,
      buildHash: report.native.buildHash, probeScope: 'calibration-export-only; not-character-or-Unreal' };
  }
  const executable = env.BLENDER_PATH || preferredPath;
  if (!executable || !fs.existsSync(executable) || !fs.statSync(executable).isFile()) throw failure('Blender não encontrado. Configure BLENDER_PATH.', 'BLENDER_PATH');
  return { backend: 'blender', executable: fs.realpathSync(executable), official: null, executableSha256: fileHash(executable) };
}

function runProcess(executable, args, { timeoutMs = 180000, cwd, env = process.env, maxOutput = 4 * 1024 * 1024 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { shell: false, windowsHide: true, cwd, env });
    const chunks = []; let count = 0, reason = null;
    const stop = error => {
      if (reason) return;
      reason = error;
      if (process.platform === 'win32' && child.pid) {
        const killer = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { shell: false, windowsHide: true, stdio: 'ignore' });
        killer.on('error', () => child.kill());
        killer.on('close', code => { if (code !== 0) child.kill(); });
      } else child.kill('SIGKILL');
    };
    const timer = setTimeout(() => stop(failure('BIKINI excedeu o tempo máximo.', 'BIKINI_TIMEOUT')), timeoutMs);
    const collect = b => {
      count += b.length;
      if (count > maxOutput) { stop(failure('BIKINI excedeu o limite de log.', 'BIKINI_LOG_LIMIT')); return; }
      chunks.push(b);
    };
    child.stdout.on('data', collect); child.stderr.on('data', collect);
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      const output = Buffer.concat(chunks).toString('utf8');
      if (reason || code !== 0) {
        const error = reason || failure(`BIKINI encerrou com código ${code}, sinal ${signal || 'nenhum'}.`, 'BIKINI_PROCESS');
        error.output = output; reject(error);
      } else resolve({ code, output });
    });
  });
}

function validateNativeProbe(native, nonce, lock = LOCK) {
  if (native.schemaVersion !== 1 || native.nonce !== nonce || native.status !== 'export_smoke_passed' ||
      !Array.isArray(native.version) || native.version.slice(0, 2).join('.') !== lock.expectedBlenderMajorMinor.join('.') ||
      !native.exporters?.glb || !native.exporters?.fbx || !native.smoke?.roundtripOk ||
      native.scope !== 'technical_fixture_not_game_content' || !Array.isArray(native.nodes))
    throw failure('O processo não comprovou o contrato mínimo de exportação.', 'BIKINI_PROBE_INVALID');
  return native;
}

async function probe({ root = ROOT, env = process.env } = {}) {
  const runtime = inspectInstallation({ env });
  const nonce = crypto.randomBytes(16).toString('hex'), runId = `run_${nonce}`;
  const out = path.join(stateDir(root), runId);
  fs.mkdirSync(out, { recursive: true });
  const script = path.join(root, 'blender/bikini_probe.py');
  try {
    const result = await runProcess(runtime.executable, ['--background', '--factory-startup', '--disable-autoexec',
      '--python-exit-code', '1', '--python', script, '--', '--out', out, '--nonce', nonce], { cwd: path.dirname(runtime.executable) });
    fs.writeFileSync(path.join(out, 'process.log'), result.output);
    const native = validateNativeProbe(JSON.parse(fs.readFileSync(path.join(out, 'probe.json'), 'utf8')), nonce);
    const artifactHashes = {};
    for (const name of ['probe.json', 'calibration.glb', 'calibration.fbx', 'calibration.blend']) {
      const file = path.join(out, name);
      if (!fs.existsSync(file) || !fs.statSync(file).size) throw failure(`Probe sem ${name}.`, 'BIKINI_PROBE_INVALID');
      artifactHashes[name] = fileHash(file);
    }
    const report = { schemaVersion: 1, status: 'export_smoke_passed', runId, checkedAt: new Date().toISOString(),
      revision: runtime.revision, executableSha256: runtime.executableSha256,
      packageFingerprint: runtime.packageFingerprint, requiredFileHashes: runtime.requiredFileHashes,
      probeScriptSha256: fileHash(script), artifactHashes, native, characterFidelity: 'not_tested', unreal: 'not_tested' };
    const target = path.join(stateDir(root), 'latest.json');
    fs.writeFileSync(`${target}.${nonce}.tmp`, JSON.stringify(report, null, 2));
    fs.renameSync(`${target}.${nonce}.tmp`, target);
    return report;
  } catch (error) {
    fs.writeFileSync(path.join(out, 'error.log'), `${error.message}\n${error.output || ''}`);
    throw error;
  }
}

function publicStatus({ root = ROOT, env = process.env, platform = process.platform } = {}) {
  let report = null;
  try { report = readProbe(root); } catch { /* No inference or executable launched by a GET. */ }
  return { product: 'BIKINI', selected: env.BLENDER_BACKEND === 'bikini', configured: !!env.BIKINI_PATH,
    supportedHost: platform === 'win32' && process.arch === 'x64', optIn: env.BIKINI_ALLOW_UNOFFICIAL === '1',
    revision: LOCK.revision, officialBlender: false, page: '/alice/bikini',
    status: report ? 'recorded_probe_requires_runtime_recheck' : 'not_probed',
    checkedAt: report?.checkedAt || null, version: report?.native?.versionString || null,
    nodes: report?.native?.nodes || [], characterFidelity: 'not_tested', unreal: 'not_tested',
    note: 'Inventário do último probe; a instalação é verificada novamente antes de cada build. Não é aprovação artística.' };
}

function mountBikini(app, root) {
  app.get('/alice/bikini', (_, res) => res.sendFile(path.join(root, 'public/bikini.html')));
  app.get('/api/integrations/bikini', (_, res) => res.json(publicStatus({ root })));
}

module.exports = { LOCK, fileHash, inspectInstallation, resolveRuntime, runProcess, probe,
  validateNativeProbe, validateProbe, readProbe, publicStatus, mountBikini };
