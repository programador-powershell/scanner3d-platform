const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const express = require('express');
const sharp = require('sharp');
const { mountAliceStages } = require('../lib/alice_stages');
const { sha256 } = require('../lib/fidelity');
let root, url, server, plan, planFile, reference, display;
const save = () => fs.writeFileSync(planFile, JSON.stringify(plan));
before(async () => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), 'alice-stage-test-'));
  reference = path.join(root, 'shirt.png'); display = path.join(root, 'fixture.glb');
  const other = path.join(root, 'skirt.png');
  const board = path.join(root, 'comparison.jpg');
  await sharp({create:{width:64,height:48,channels:3,background:'grey'}}).jpeg().toFile(board);
  for (const [file, color] of [[reference, 'white'], [other, 'navy']])
    await sharp({create:{width:32,height:48,channels:3,background:color}}).png().toFile(file);
  // Imported fixture tests identity checks only; it is never counted as reconstructed Alice geometry.
  fs.copyFileSync(path.join(__dirname, '../data/assets/alice-detail.glb'), display);
  plan = { completed:false, stages:[
    {id:'alice_test_stage_01',variant:'alice_test',number:1,label:'Camisa',status:'needs_refinement',
      sourcePhoto:reference,sourcePhotoSha256:sha256(fs.readFileSync(reference)),
      comparison:{sourcePhotoSha256:sha256(fs.readFileSync(reference)),reusedGeometry:false,
        displayModel:{file:display,sha256:sha256(fs.readFileSync(display))},
        board:{file:board,sha256:sha256(fs.readFileSync(board))},frontAxis:'+x'}},
    {id:'alice_test_stage_02',variant:'alice_test',number:2,label:'Saia',status:'awaiting_fresh_geometry_and_comparison',
      sourcePhoto:other,sourcePhotoSha256:sha256(fs.readFileSync(other))}
  ]};
  planFile=path.join(root,'stage_comparisons.json');save();
  const app=express(); mountAliceStages(app,root,root);
  app.use((error,req,res,next)=>res.status(error.status||500).json({error:error.message}));
  server=await new Promise(resolve=>{const s=app.listen(0,'127.0.0.1',()=>resolve(s));});
  url=`http://127.0.0.1:${server.address().port}`;
});
after(async()=>{
  await new Promise(resolve=>server.close(resolve));
  const target=path.resolve(root), temp=path.resolve(os.tmpdir());
  if(!target.startsWith(temp+path.sep)||!path.basename(target).startsWith('alice-stage-test-'))throw new Error('Unexpected cleanup target');
  fs.rmSync(target,{recursive:true});
});
test('each stage exposes its own photo; pending geometry has no fallback',async()=>{
  const result=await(await fetch(`${url}/api/alice/stages`)).json();
  assert.equal(result.completed,false);assert.equal(result.stages[0].fidelityVerified,false);
  assert.equal(result.stages[1].model,null);
  const photos=await Promise.all(result.stages.map(async s=>Buffer.from(await(await fetch(url+s.referenceUrl)).arrayBuffer())));
  assert.notEqual(sha256(photos[0]),sha256(photos[1]));
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_02/model`)).status,404);
});
test('a full outfit study stays separate from unfinished photo layers',async()=>{
  const garment=plan.stages[0];
  const full={...garment,id:'alice_test_full',kind:'full-model',number:null,label:'Conjunto'};
  plan.stages.push(full);save();
  try {
    const result=await(await fetch(`${url}/api/alice/stages`)).json();
    const study=result.stages.find(s=>s.id===full.id);
    assert.equal(study.kind,'full-model');assert.equal(study.number,null);
    assert.ok(study.model);assert.equal(study.fidelityVerified,false);
    const pending=result.stages.find(s=>s.id==='alice_test_stage_02');
    assert.equal(pending.kind,'layer-stage');assert.equal(pending.model,null);
    assert.equal((await fetch(`${url}/api/alice/stages/${pending.id}/model`)).status,404);
    assert.equal((await fetch(url+study.referenceUrl)).status,200);
    assert.equal(result.completed,false);
  } finally {plan.stages.pop();save();}
});
test('a model associated with another stage photo is rejected',async()=>{
  const original=plan.stages[0].comparison.sourcePhotoSha256;
  plan.stages[0].comparison.sourcePhotoSha256=plan.stages[1].sourcePhotoSha256;save();
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/model`)).status,409);
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/comparison`)).status,409);
  plan.stages[0].comparison.sourcePhotoSha256=original;save();
});

test('portable stage files resolve against their own manifest directory',async()=>{
  const stage=plan.stages[0],original=JSON.parse(JSON.stringify(stage));
  stage.sourcePhoto=path.basename(stage.sourcePhoto);
  stage.comparison.displayModel.file=path.basename(stage.comparison.displayModel.file);
  stage.comparison.board.file=path.basename(stage.comparison.board.file);save();
  for(const asset of ['reference','model','comparison'])
    assert.equal((await fetch(`${url}/api/alice/stages/${stage.id}/${asset}`)).status,200);
  plan.stages[0]=original;save();
});
test('reused geometry cannot masquerade as a fresh stage reconstruction',async()=>{
  plan.stages[0].comparison.reusedGeometry=true;save();
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/model`)).status,409);
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/comparison`)).status,409);
  plan.stages[0].comparison.reusedGeometry=false;save();
});
test('changed photos and models invalidate the recorded comparison',async()=>{
  const original=fs.readFileSync(reference);fs.appendFileSync(reference,'changed');
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/reference`)).status,409);
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/comparison`)).status,409);
  fs.writeFileSync(reference,original);
  fs.appendFileSync(display,'changed');
  assert.equal((await fetch(`${url}/api/alice/stages/alice_test_stage_01/model`)).status,409);
});
