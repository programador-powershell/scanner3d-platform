'use strict';
// These tests exercise the integration contract, NOT a real BIKINI installation.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const runtime = require('../lib/bikini_runtime');
const { main } = require('../scripts/bikini');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const temp = t => { const d = fs.mkdtempSync(path.join(os.tmpdir(), 'bikini-test-')); t.after(() => fs.rmSync(d, { recursive: true, force: true })); return d; };
const hasCode = code => e => e.code === code;
function installation(t) {
  const directory = temp(t), bytes = Buffer.from('MZ_TEST_FIXTURE_NOT_EXECUTABLE');
  const lock = structuredClone(runtime.LOCK);
  lock.executable = { name: 'blender.exe', size: bytes.length, sha256: hash(bytes) };
  const executable = path.join(directory, 'blender.exe'); fs.writeFileSync(executable, bytes);
  for (const p of lock.requiredDirectories) fs.mkdirSync(path.join(directory, p), { recursive: true });
  for (const p of lock.requiredFiles) fs.writeFileSync(path.join(directory, p), p.endsWith('.dll') ? Buffer.from('MZ_TEST_DLL') : 'test metadata');
  const options = { env: { BIKINI_PATH: executable, BIKINI_ALLOW_UNOFFICIAL: '1' }, platform: 'win32', arch: 'x64', lock };
  return { directory, executable, lock, options };
}
function validNative(nonce = 'a'.repeat(32)) {
  return { schemaVersion: 1, nonce, status: 'export_smoke_passed', scope: 'technical_fixture_not_game_content',
    version: [5, 3, 0], exporters: { glb: true, fbx: true }, smoke: { roundtripOk: true }, nodes: [] };
}
function probeEvidence(t) {
  const root = temp(t), runId = 'run_' + 'c'.repeat(32);
  fs.mkdirSync(path.join(root, 'blender'));
  fs.writeFileSync(path.join(root, 'blender/bikini_probe.py'), '# test script');
  const folder = path.join(root, 'data/bikini-runtime', runId); fs.mkdirSync(folder, { recursive: true });
  const artifactHashes = {};
  for (const name of ['probe.json', 'calibration.glb', 'calibration.fbx', 'calibration.blend']) {
    const p = path.join(folder, name); fs.writeFileSync(p, name === 'probe.json' ? JSON.stringify(validNative('c'.repeat(32))) : 'TEST EVIDENCE ' + name); artifactHashes[name] = runtime.fileHash(p);
  }
  const engine = { executableSha256: 'exe', packageFingerprint: 'package', revision: 'revision' };
  const report = { schemaVersion: 1, status: 'export_smoke_passed', runId, ...engine,
    probeScriptSha256: runtime.fileHash(path.join(root, 'blender/bikini_probe.py')), artifactHashes, native: validNative('c'.repeat(32)) };
  return { root, folder, engine, report };
}

test('lock records exact upstream revision and LFS binary, not stale build date', () => {
  assert.equal(runtime.LOCK.revision, 'b007d4e4f2cdb80074852900d9ed8429d228b65d');
  assert.equal(runtime.LOCK.executable.sha256, 'aeb517ef7d2643024c19e9ddf1b749487c534ed4b890218eed4f35753d71c20d');
  assert.equal(runtime.LOCK.executable.size, 133306880);
  assert.equal(runtime.LOCK.officialBlender, false);
});
test('fileHash reads actual bytes', t => { const f = path.join(temp(t), 'data'); fs.writeFileSync(f, 'actual'); assert.equal(runtime.fileHash(f), hash('actual')); });
test('explicit opt-in is mandatory', () => assert.throws(() => runtime.inspectInstallation({ env: {} }), hasCode('BIKINI_OPT_IN_REQUIRED')));
test('Windows binary is not launched on Linux', () => assert.throws(() => runtime.inspectInstallation({ env: { BIKINI_ALLOW_UNOFFICIAL: '1' }, platform: 'linux' }), hasCode('BIKINI_PLATFORM')));
test('ARM host is not silently treated as x64', () => assert.throws(() => runtime.inspectInstallation({ env: { BIKINI_ALLOW_UNOFFICIAL: '1' }, platform: 'win32', arch: 'arm64' }), hasCode('BIKINI_PLATFORM')));
test('relative executable paths are rejected', t => { const { options } = installation(t); options.env.BIKINI_PATH = 'blender.exe'; assert.throws(() => runtime.inspectInstallation(options), hasCode('BIKINI_PATH')); });
test('LFS pointer is not accepted as executable', t => { const x = installation(t); fs.writeFileSync(x.executable, 'version https://git-lfs.github.com/spec/v1\noid sha256:123\n'); assert.throws(() => runtime.inspectInstallation(x.options), hasCode('BIKINI_LFS_POINTER')); });
test('changed executable is refused before execution', t => { const x = installation(t); fs.appendFileSync(x.executable, 'modified'); assert.throws(() => runtime.inspectInstallation(x.options), hasCode('BIKINI_DIGEST')); });
test('portable directory is mandatory', t => { const x = installation(t); fs.rmSync(path.join(x.directory, 'blender.shared'), { recursive: true }); assert.throws(() => runtime.inspectInstallation(x.options), hasCode('BIKINI_PACKAGE')); });
test('runtime library is mandatory', t => { const x = installation(t); fs.unlinkSync(path.join(x.directory, 'python313.dll')); assert.throws(() => runtime.inspectInstallation(x.options), hasCode('BIKINI_PACKAGE')); });
test('DLL LFS pointer fails independently of exe', t => { const x = installation(t); fs.writeFileSync(path.join(x.directory, 'python3.dll'), 'version https://git-lfs.github.com/spec/v1'); assert.throws(() => runtime.inspectInstallation(x.options), hasCode('BIKINI_LFS_POINTER')); });
test('fixture package hashes are reproducible without running fixture bytes', t => { const x = installation(t); const a = runtime.inspectInstallation(x.options), b = runtime.inspectInstallation(x.options); assert.equal(a.packageFingerprint, b.packageFingerprint); assert.equal(a.backend, 'bikini'); });
test('changing a DLL changes the probe identity', t => { const x = installation(t); const a = runtime.inspectInstallation(x.options); fs.appendFileSync(path.join(x.directory, 'python313.dll'), 'change'); const b = runtime.inspectInstallation(x.options); assert.notEqual(a.packageFingerprint, b.packageFingerprint); });
test('unknown backend is rejected', () => assert.throws(() => runtime.resolveRuntime({ env: { BLENDER_BACKEND: 'unknown' } }), hasCode('BLENDER_BACKEND')));
test('default backend preserves the existing executable selection', () => { const r = runtime.resolveRuntime({ env: {}, preferredPath: process.execPath }); assert.equal(r.backend, 'blender'); assert.equal(r.executable, fs.realpathSync(process.execPath)); });
test('selected BIKINI never silently falls back to an existing binary', () => assert.throws(() => runtime.resolveRuntime({ env: { BLENDER_BACKEND: 'bikini' }, preferredPath: process.execPath }), hasCode('BIKINI_OPT_IN_REQUIRED')));
test('missing probe blocks usage', t => assert.throws(() => runtime.readProbe(temp(t)), hasCode('BIKINI_PROBE_REQUIRED')));
test('matching probe evidence passes contract check only', t => { const x = probeEvidence(t); assert.equal(runtime.validateProbe(x.report, x.engine, x.root).runId, x.report.runId); });
test('package change invalidates old probe', t => { const x = probeEvidence(t); assert.throws(() => runtime.validateProbe(x.report, { ...x.engine, packageFingerprint: 'other' }, x.root), hasCode('BIKINI_PROBE_STALE')); });
test('probe script change invalidates old probe', t => { const x = probeEvidence(t); fs.appendFileSync(path.join(x.root, 'blender/bikini_probe.py'), '#changed'); assert.throws(() => runtime.validateProbe(x.report, x.engine, x.root), hasCode('BIKINI_PROBE_STALE')); });
test('artifact tampering invalidates probe', t => { const x = probeEvidence(t); fs.appendFileSync(path.join(x.folder, 'calibration.glb'), 'changed'); assert.throws(() => runtime.validateProbe(x.report, x.engine, x.root), hasCode('BIKINI_PROBE_STALE')); });
test('probe path traversal is rejected', t => { const x = probeEvidence(t); x.report.runId = '../../secret'; assert.throws(() => runtime.validateProbe(x.report, x.engine, x.root), hasCode('BIKINI_PROBE_STALE')); });
test('native probe nonce must match current request', () => assert.throws(() => runtime.validateNativeProbe(validNative(), 'b'.repeat(32)), hasCode('BIKINI_PROBE_INVALID')));
test('wrong Blender version fails native probe', () => { const n = validNative(); n.version = [4, 5, 0]; assert.throws(() => runtime.validateNativeProbe(n, n.nonce), hasCode('BIKINI_PROBE_INVALID')); });
test('missing FBX exporter fails native probe', () => { const n = validNative(); n.exporters.fbx = false; assert.throws(() => runtime.validateNativeProbe(n, n.nonce), hasCode('BIKINI_PROBE_INVALID')); });
test('probe cannot call a calibration character content', () => { const n = validNative(); n.scope = 'approved_character'; assert.throws(() => runtime.validateNativeProbe(n, n.nonce), hasCode('BIKINI_PROBE_INVALID')); });
test('valid native probe is only export evidence', () => { const n = validNative(); assert.equal(runtime.validateNativeProbe(n, n.nonce).status, 'export_smoke_passed'); });
test('subprocess success is captured from a real Node child', async () => { const r = await runtime.runProcess(process.execPath, ['-e', 'process.stdout.write("executed")']); assert.equal(r.output, 'executed'); });
test('subprocess failure includes logs, not a fake success', async () => { await assert.rejects(runtime.runProcess(process.execPath, ['-e', 'console.error("failed");process.exit(7)']), e => e.code === 'BIKINI_PROCESS' && e.output.includes('failed')); });
test('subprocess timeout stops a real child', async () => { await assert.rejects(runtime.runProcess(process.execPath, ['-e', 'setTimeout(()=>{},30000)'], { timeoutMs: 100 }), hasCode('BIKINI_TIMEOUT')); });
test('subprocess output cap is enforced', async () => { await assert.rejects(runtime.runProcess(process.execPath, ['-e', 'console.log("x".repeat(65536))'], { maxOutput: 512 }), hasCode('BIKINI_LOG_LIMIT')); });
test('no installation is reported as not_probed, not ready', t => { const r = runtime.publicStatus({ env: {}, root: temp(t), platform: 'linux' }); assert.equal(r.status, 'not_probed'); assert.equal(r.characterFidelity, 'not_tested'); assert.equal(r.configured, false); });
test('read-only HTTP route responds without launching BIKINI', async t => {
  const root = temp(t), routes = new Map(); runtime.mountBikini({ get: (url, fn) => routes.set(url, fn) }, root);
  const server = http.createServer((req, res) => {
    const fn = routes.get(req.url); if (!fn) { res.writeHead(404); res.end(); return; }
    fn(req, { json: value => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(value)); } });
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); t.after(() => new Promise(resolve => server.close(resolve)));
  const r = await fetch(`http://127.0.0.1:${server.address().port}/api/integrations/bikini`);
  assert.equal(r.status, 200); const d = await r.json(); assert.equal(d.officialBlender, false); assert.equal(d.unreal, 'not_tested'); assert.equal('executable' in d, false);
});
test('CLI bake refuses existing output folders without running Blender', async t => {
  const root = temp(t), input = path.join(root, 'input.blend'), out = path.join(root, 'out'); fs.writeFileSync(input, 'TEST'); fs.mkdirSync(out);
  await assert.rejects(main(['bake', input, 'Layer', out]), /pasta de saída deve ser nova/);
});
test('CLI rejects incomplete bake parameters', async () => assert.rejects(main(['bake']), /Uso:/));
test('build runner uses backend selection and preserves review status', () => {
  const src = fs.readFileSync(path.join(__dirname, '../lib/build_runner.js'), 'utf8');
  assert.match(src, /resolveRuntime\(\{ preferredPath: blender, root \}\)/);
  assert.match(src, /engine_provenance\.json/); assert.match(src, /fidelityStatus: 'awaiting_review'/);
});
test('studio mounts BIKINI without replacing existing Alice stages', () => {
  const src = fs.readFileSync(path.join(__dirname, '../lib/alice_studio.js'), 'utf8');
  assert.match(src, /mountAliceStages\(app, root\)/); assert.match(src, /mountBikini\(app, root\)/);
});

test('host summary cannot override recorded Blender version', t => { const x = probeEvidence(t); x.report.native.version = [9, 9, 9]; assert.throws(() => runtime.validateProbe(x.report, x.engine, x.root), hasCode('BIKINI_PROBE_STALE')); });
