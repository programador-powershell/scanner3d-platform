const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('path');
const fs = require('fs');
const { normalizeVerdict, judgeWithVlm, sha256 } = require('../lib/fidelity');
const { inspectGlb } = require('../lib/glb');
const { newJob, publicJob, STAGE_IDS } = require('../lib/pipeline');
const root = path.join(__dirname, '..');
const reference = path.join(root, 'data/references/alice/turnaround.jpg');

test('missing vision never becomes a passing score', async () => {
  const noImages = await judgeWithVlm({ stage: 'hair', references: [], preview: null });
  assert.equal(noImages.pass, false); assert.equal(noImages.verified, false); assert.equal(noImages.score, null);
  const noService = await judgeWithVlm({ stage: 'face', references: [reference], preview: reference,
    url: 'http://invalid.local', fetchImpl: async () => { throw new Error('offline'); } });
  assert.equal(noService.pass, false); assert.equal(noService.score, null);
});

test('zero, low, invalid and defective verdicts cannot auto-approve', () => {
  for (const value of [null, {}, {pass:'true',score:0.99,defects:[]}, {pass:true,score:NaN,defects:[]},
    {pass:true,score:1.2,defects:[]}, {pass:true,score:0.99,defects:['wrong face']}])
    assert.equal(normalizeVerdict(value, {}).pass, false);
  assert.equal(normalizeVerdict({pass:true,score:0,defects:[]}, {}).score, 0);
});

test('the vision request includes the actual last render and hash provenance', async () => {
  const bytes = fs.readFileSync(reference);
  let payload;
  const verdict = await judgeWithVlm({ stage: 'garment', references: [reference], preview: reference, url: 'http://vision.local',
    fetchImpl: async (url, request) => { payload = JSON.parse(request.body); return {ok:true, json:async()=>({choices:[{message:{content:'{"pass":true,"score":0.95,"defects":[]}'}}]})}; } });
  const content = payload.messages[0].content;
  assert.equal(content.length, 3);
  assert.equal(content.at(-1).image_url.url, `data:image/jpeg;base64,${bytes.toString('base64')}`);
  assert.equal(verdict.evidence.preview, sha256(bytes));
  assert.equal(verdict.evidence.scope, 'visible-image-comparison');
  assert.equal(verdict.verified, true);
});

test('real Alice assets contain volume, texture and disclosed rig state', () => {
  const original = inspectGlb(fs.readFileSync(path.join(root, 'data/references/alice/alice-source.glb')));
  const detailed = inspectGlb(fs.readFileSync(path.join(root, 'data/assets/alice-detail.glb')));
  const restored = inspectGlb(fs.readFileSync(path.join(root, 'data/assets/alice-restored.glb')));
  assert.equal(detailed.triangles, 249975);
  assert.equal(detailed.joints, 0);
  assert.equal(detailed.texturedPrimitives, 1);
  assert.equal(detailed.fidelityStatus, 'unverified');
  assert.ok(detailed.dimensions[2] > 0.5);
  assert.equal(restored.triangles, 34135);
  assert.equal(restored.restoration.geometryReconstructed, false);
  assert.equal(restored.joints, original.joints);
  assert.deepEqual(restored.animations, original.animations);
});

test('GLB truncation, lying bounds and non-finite positions are rejected', () => {
  const original = fs.readFileSync(path.join(root, 'data/assets/alice-detail.glb'));
  assert.throws(() => inspectGlb(original.subarray(0, original.length - 4)));
  const malformed = Buffer.from(original);
  const length = malformed.readUInt32LE(12);
  const doc = JSON.parse(malformed.subarray(20, 20 + length).toString());
  const a = doc.accessors[doc.meshes[0].primitives[0].attributes.POSITION];
  const v = doc.bufferViews[a.bufferView];
  malformed.writeFloatLE(NaN, 28 + length + (v.byteOffset || 0) + (a.byteOffset || 0));
  assert.throws(() => inspectGlb(malformed), /não finita/);
});

test('a diagonally rotated photograph plane is still rejected as planar', () => {
  const positions = new Float32Array([0,0,0, 1,1,0, 0,1,1]);
  const binary = Buffer.from(positions.buffer);
  const doc = {asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],nodes:[{mesh:0}],
    meshes:[{primitives:[{attributes:{POSITION:0}}]}],buffers:[{byteLength:binary.length}],
    bufferViews:[{buffer:0,byteOffset:0,byteLength:binary.length}],
    accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[0,0,0],max:[1,1,1]}]};
  let json = Buffer.from(JSON.stringify(doc));
  json = Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);
  const header = Buffer.alloc(20); header.writeUInt32LE(0x46546c67,0); header.writeUInt32LE(2,4);
  header.writeUInt32LE(28+json.length+binary.length,8); header.writeUInt32LE(json.length,12); header.writeUInt32LE(0x4e4f534a,16);
  const binHeader = Buffer.alloc(8); binHeader.writeUInt32LE(binary.length,0); binHeader.writeUInt32LE(0x004e4942,4);
  assert.throws(()=>inspectGlb(Buffer.concat([header,json,binHeader,binary])),/planar/);
});

test('both viewer modules and legacy inline module remain syntactically valid', () => {
  const { execFileSync } = require('child_process');
  execFileSync(process.execPath, ['--check', path.join(root, 'public/alice.js')]);
  const html = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
  const module = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  execFileSync(process.execPath, ['--check', '--input-type=module'], { input: module });
});

test('pipeline derives its active gate from statuses, including completion', () => {
  const job = newJob('job_test', null);
  job.activeIndex = 7;
  assert.equal(publicJob(job).activeIndex, 0);
  for (const id of STAGE_IDS) job.stages[id].status = 'approved';
  assert.equal(publicJob(job).activeIndex, 8); assert.equal(publicJob(job).done, true);
});
