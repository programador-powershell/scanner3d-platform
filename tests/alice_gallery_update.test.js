const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const { prepareGalleryUpdate } = require('../scripts/package_alice_gallery_update');

test('a layer extract or unreviewed render cannot overwrite the full gallery outfit', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'alice-gallery-test-'));
  try {
    execFileSync('git', ['init', '-q', root]);
    execFileSync('git', ['-C', root, 'remote', 'add', 'origin', 'https://github.com/programador-powershell/project-alice-game.git']);
    const generation = {variant:'alice_chapeleiro', studioModelId:'test', reusedGeometry:false,
      status:'generated_awaiting_visual_review', creditsConsumed:55, creditsDisplayedBeforeSubmission:55,
      parametersObserved:{generateParts:false, texture8K:false},
      sourcePhotoSha256:'layer-photo', generationPhotoSha256:'full-photo'};
    assert.throws(() => prepareGalleryUpdate(generation, {stageId:'alice_chapeleiro_stage_02'}, root), /full Chapeleiro/);
    assert.throws(() => prepareGalleryUpdate(generation, {stageId:'alice_chapeleiro_full'}, root), /layer extraction/);
    delete generation.generationPhotoSha256;
    assert.throws(() => prepareGalleryUpdate(generation, {stageId:'alice_chapeleiro_full', status:'awaiting_visual_review'}, root), /four views/);
    assert.equal(fs.existsSync(path.join(root,'Content')),false);
  } finally {
    const target = path.resolve(root), temporary = path.resolve(os.tmpdir());
    if (!target.startsWith(temporary + path.sep) || !path.basename(target).startsWith('alice-gallery-test-'))
      throw new Error('Unexpected test cleanup path');
    fs.rmSync(target, {recursive:true});
  }
});
