// Prepare a reviewed full-model checkpoint for the game's existing gallery slug.
// Git commits/pushes remain explicit; numbered layer extracts cannot replace it.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { inspectGlb } = require('../lib/glb');
const { sha256 } = require('../lib/fidelity');

function prepareGalleryUpdate(generation, comparison, gameRoot) {
  const root = path.resolve(gameRoot);
  const remote = execFileSync('git', ['-C', root, 'remote', 'get-url', 'origin'], { encoding:'utf8' }).trim();
  if (remote !== 'https://github.com/programador-powershell/project-alice-game.git')
    throw new Error('Expected the Project Alice game repository.');
  if (generation.variant !== 'alice_chapeleiro' || comparison.stageId !== 'alice_chapeleiro_full')
    throw new Error('Only the current full Chapeleiro checkpoint may update this gallery item.');
  if (!generation.studioModelId || generation.reusedGeometry !== false ||
      generation.status !== 'generated_awaiting_visual_review' ||
      generation.generationPhotoSha256 && generation.generationPhotoSha256 !== generation.sourcePhotoSha256)
    throw new Error('A new full Tripo model is required; a numbered layer extraction cannot replace the outfit.');
  const options = generation.parametersObserved;
  if (!options || options.generateParts !== false || options.texture8K !== false ||
      generation.creditsConsumed > generation.creditsDisplayedBeforeSubmission)
    throw new Error('Missing non-premium generation/cost provenance.');
  if (!['needs_refinement', 'rejected_fidelity'].includes(comparison.status))
    throw new Error('Review the actual four views before publishing a checkpoint.');
  function checked(file, digest) {
    const bytes = fs.readFileSync(file);
    if (!/^[a-f0-9]{64}$/.test(digest || '') || sha256(bytes) !== digest)
      throw new Error('Changed checkpoint evidence: ' + path.basename(file));
    return bytes;
  }
  checked(generation.sourcePhoto, generation.sourcePhotoSha256);
  checked(generation.model, generation.modelSha256);
  if (comparison.sourcePhotoSha256 !== generation.sourcePhotoSha256 || comparison.modelSha256 !== generation.modelSha256)
    throw new Error('Comparison belongs to a different photo or model.');
  const model = checked(comparison.displayModel.file, comparison.displayModel.sha256);
  if (model.length >= 100 * 1024 * 1024) throw new Error('Gallery GLB exceeds GitHub file limit.');
  const stats = inspectGlb(model);
  const artifacts = [['source_photo' + path.extname(generation.sourcePhoto), generation.sourcePhoto, generation.sourcePhotoSha256],
                     ['photo_vs_geometry.jpg', comparison.comparisonBoard.file, comparison.comparisonBoard.sha256]];
  for (const view of ['front','side','back','threequarter']) {
    const render = comparison.renders[view];
    if (!render) throw new Error('Missing actual geometry view: ' + view);
    artifacts.push([view + '.png', render.file, render.sha256]);
  }
  // Validate every artifact before any destination mutation.
  const payloads = artifacts.map(([name, file, digest]) => [name, checked(file, digest), digest]);
  const modelRelative = 'Content/Assets/3D/personagens/alice-vestido-chapeleiro.glb';
  const evidenceRelative = 'Docs/alice-variants/chapeleiro';
  fs.mkdirSync(path.dirname(path.join(root, modelRelative)), { recursive:true });
  fs.mkdirSync(path.join(root, evidenceRelative), { recursive:true });
  fs.writeFileSync(path.join(root, modelRelative), model);
  for (const [name, bytes] of payloads) fs.writeFileSync(path.join(root, evidenceRelative, name), bytes);
  const record = {
    project:'Project Alice — Challenge', originalAuthor:'programador-powershell',
    variant:generation.variant, status:'refinement_in_progress', studioModelId:generation.studioModelId,
    sourcePhotoSha256:generation.sourcePhotoSha256,
    originalDownloadedGlbSha256:generation.originalDownloadedModelSha256 || generation.geometryParentSha256 || generation.modelSha256,
    galleryModel:{file:modelRelative, sha256:stats.sha256, bytes:stats.bytes, triangles:stats.triangles,
                  joints:stats.joints, animations:stats.animations, dimensions:stats.dimensions},
    parametersObserved:options, creditsConsumed:generation.creditsConsumed,
    additionalCreditsConsumed:generation.additionalCreditsConsumed || 0,
    exteriorPolicy:'Keep the complete Tripo outfit. Numbered photos describe internal layers and detail references; do not cut the exterior into photo-based garment slices.',
    optimizationAudit:generation.optimizationAudit || null,
    bakeSettings:generation.bakeSettings || null,
    bakeMasterSha256:generation.bakeMasterSha256 || null,
    bakedTextureHashes:generation.bakedTextures ? Object.fromEntries(Object.entries(generation.bakedTextures).map(([name, item]) => [name, item.sha256])) : null,
    premiumFeaturesUsed:false, actualFourViewReview:comparison.visibleDifferences,
    comparisonArtifacts:payloads.map(([name,,digest])=>({file:evidenceRelative+'/'+name, sha256:digest})),
    allLayersFinished:false, fidelityVerified:false, motionVerified:false, clothCollisionVerified:false,
    nextVariantMayStart:false, approvedAliceBasePreserved:true,
    updatePolicy:'Preserve and polish the whole exterior, reduce/retopologize and bake PBR locally; build missing internal garments from their own photos. Publish further commits to this same gallery slug. Finish all Chapeleiro layers and rig before the next Tripo generation.'
  };
  fs.writeFileSync(path.join(root, evidenceRelative, 'checkpoint.json'), JSON.stringify(record, null, 2) + '\n');
  return record;
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const value = flag => args[args.indexOf(flag) + 1];
  for (const flag of ['--generation','--comparison','--game-root'])
    if (!args.includes(flag) || !value(flag)) throw new Error('Required: ' + flag);
  const result = prepareGalleryUpdate(JSON.parse(fs.readFileSync(value('--generation'),'utf8')),
    JSON.parse(fs.readFileSync(value('--comparison'),'utf8')), value('--game-root'));
  console.log(JSON.stringify({model:result.galleryModel, status:result.status, nextVariantMayStart:false}));
}
module.exports = { prepareGalleryUpdate };
