const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const express = require('express');
const sharp = require('sharp');
const { mountAliceStudio } = require('../lib/alice_studio');
let server, url, temp, model;
before(async () => {
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'alice-studio-test-'));
  const root = path.join(__dirname, '..');
  fs.mkdirSync(path.join(temp, 'data/references/alice'), { recursive: true });
  fs.mkdirSync(path.join(temp, 'data/assets'), { recursive: true });
  for (const name of ['profile.json', 'turnaround.jpg', 'alice-source.glb'])
    fs.copyFileSync(path.join(root, 'data/references/alice', name), path.join(temp, 'data/references/alice', name));
  fs.copyFileSync(path.join(root, 'data/assets/alice-detail.glb'), path.join(temp, 'data/assets/alice-detail.glb'));
  fs.copyFileSync(path.join(root, 'data/assets/alice-detail.report.json'), path.join(temp, 'data/assets/alice-detail.report.json'));
  const app = express(); mountAliceStudio(app, temp);
  app.use((error, req, res, next) => res.status(error.status || 500).json({error:error.message}));
  server = await new Promise(resolve => { const s = app.listen(0, '127.0.0.1', () => resolve(s)); });
  url = `http://127.0.0.1:${server.address().port}`;
  model = (await (await fetch(`${url}/api/alice`)).json()).models.find(m => m.id === 'detail');
});
after(async () => {
  await new Promise(resolve => server.close(resolve));
  const resolved = path.resolve(temp), tempRoot = path.resolve(os.tmpdir());
  if (!resolved.startsWith(tempRoot + path.sep) || !path.basename(resolved).startsWith('alice-studio-test-'))
    throw new Error('Unexpected test cleanup target');
  fs.rmSync(resolved, { recursive: true });
});

test('native detail is disclosed as imported and unverified', () => {
  assert.equal(model.triangles, 249975); assert.equal(model.joints, 0);
  assert.equal(model.importReport.geometryReconstructed, false);
});
test('the profile crop is a real image, and unavailable reconstruction returns 503', async () => {
  const image = await fetch(`${url}/api/alice/reference/side`);
  const meta = await sharp(Buffer.from(await image.arrayBuffer())).metadata();
  assert.deepEqual([meta.width,meta.height], [308,850]);
  const response = await fetch(`${url}/api/alice/reconstruct`, {method:'POST'});
  assert.equal(response.status, 503);
});
test('images renamed to GLB and stale evidence cannot pass', async () => {
  const form = new FormData(); form.append('model', new Blob(['not a mesh']), 'fake.glb');
  assert.equal((await fetch(`${url}/api/alice/import`, {method:'POST',body:form})).status, 400);
  const response = await fetch(`${url}/api/alice/evidence`, {method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({modelId:'detail',modelSha256:'wrong',renders:{}})});
  assert.equal(response.status, 409);
});
test('three evidence images record hashes but never claim visual fidelity', async () => {
  const png = await sharp({create:{width:440,height:850,channels:4,background:{r:0,g:0,b:0,alpha:0}}}).png().toBuffer();
  const image = `data:image/png;base64,${png.toString('base64')}`;
  const response = await fetch(`${url}/api/alice/evidence`, {method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({modelId:'detail',modelSha256:model.sha256,renders:{front:image,side:image,back:image}})});
  assert.equal(response.status, 200);
  const report = await response.json();
  assert.equal(report.fidelityVerified, false); assert.equal(report.status, 'awaiting_visual_review');
  assert.equal(Object.keys(report.views).length, 3);
  assert.equal((await fetch(url + report.reportUrl)).status, 200);
});
