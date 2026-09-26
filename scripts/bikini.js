#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const runtime = require('../lib/bikini_runtime');
const root = path.resolve(__dirname, '..');

async function main(argv = process.argv.slice(2)) {
  const [command, ...args] = argv;
  if (command === 'check') {
    const info = runtime.inspectInstallation();
    console.log(JSON.stringify({ ...info, status: 'files_verified_not_executed', next: 'npm run bikini:probe' }, null, 2));
    return;
  }
  if (command === 'probe') {
    console.log(JSON.stringify(await runtime.probe(), null, 2));
    return;
  }
  if (command === 'start') {
    const env = { ...process.env, BLENDER_BACKEND: 'bikini' };
    const info = runtime.resolveRuntime({ env, root });
    process.env.BLENDER_BACKEND = 'bikini';
    process.env.BLENDER_PATH = info.executable;
    console.log('[BIKINI] Backend experimental verificado. Não é uma aprovação de fidelidade.');
    console.log('Painel: /alice/bikini | camadas existentes: /alice/layers');
    require('../server');
    return;
  }
  if (command === 'bake') {
    if (args.length !== 3) throw new Error('Uso: npm run bikini:bake -- <entrada.blend> <collection> <pasta-nova-de-saida>');
    const [inputArg, collection, outputArg] = args;
    const source = path.resolve(inputArg), output = path.resolve(outputArg);
    if (!collection.trim() || collection.includes('\0')) throw new Error('Collection inválida.');
    if (path.extname(source).toLowerCase() !== '.blend' || !fs.existsSync(source) || !fs.statSync(source).isFile()) throw new Error('Informe um arquivo .blend existente.');
    if (fs.existsSync(output)) throw new Error('A pasta de saída deve ser nova; não haverá sobrescrita.');
    const info = runtime.resolveRuntime({ root, env: { ...process.env, BLENDER_BACKEND: 'bikini' } });
    const sourceHash = runtime.fileHash(source);
    fs.mkdirSync(output, { recursive: true });
    try {
      const result = await runtime.runProcess(info.executable, ['--background', '--factory-startup', '--disable-autoexec',
        '--python-exit-code', '1', '--python', path.join(root, 'blender/bikini_bake.py'), '--',
        '--input', source, '--collection', collection, '--out', output],
      { cwd: path.dirname(info.executable), timeoutMs: 600000 });
      fs.writeFileSync(path.join(output, 'process.log'), result.output);
      const report = JSON.parse(fs.readFileSync(path.join(output, 'bake_report.json'), 'utf8'));
      if (report.status !== 'candidate_exported_not_approved' || report.sourceSha256 !== sourceHash ||
          runtime.fileHash(source) !== sourceHash || !Array.isArray(report.objects) || !report.objects.length ||
          report.fidelityVerified !== false || report.unrealVerified !== false) throw new Error('Relatório de bake inválido.');
      for (const name of ['candidate.glb', 'candidate.fbx', 'candidate.blend']) {
        if (!fs.statSync(path.join(output, name)).size || runtime.fileHash(path.join(output, name)) !== report.artifacts?.[name])
          throw new Error('Artefato inválido: ' + name);
      }
      // Reuse the studio's independent GLB geometry validator, not only file existence.
      const stats = require('../lib/glb').inspectGlb(fs.readFileSync(path.join(output, 'candidate.glb')));
      const provenance = { id: crypto.randomUUID(), createdAt: new Date().toISOString(), engine: info,
        sourceSha256: sourceHash, candidate: stats, status: 'awaiting_visual_review', automaticallyApproved: false };
      fs.writeFileSync(path.join(output, 'engine_provenance.json'), JSON.stringify(provenance, null, 2));
      console.log(JSON.stringify({ output, ...provenance }, null, 2));
    } catch (error) {
      fs.writeFileSync(path.join(output, 'FAILED.txt'), `${error.message}\n${error.output || ''}`);
      throw error;
    }
    return;
  }
  if (!command || command === '--help') {
    console.log('BIKINI: check | probe | start | bake <entrada.blend> <collection> <pasta-nova>');
    console.log('Requer Windows x64, BIKINI_PATH e BIKINI_ALLOW_UNOFFICIAL=1. Não baixa/executa binários automaticamente.');
    return;
  }
  throw new Error('Comando BIKINI desconhecido: ' + command);
}
if (require.main === module) main().catch(error => { console.error(`${error.code || 'BIKINI_ERROR'}: ${error.message}`); process.exitCode = 1; });
module.exports = { main };
