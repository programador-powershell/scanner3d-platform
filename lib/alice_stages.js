const fs = require('fs');
const path = require('path');
const { inspectGlb } = require('./glb');
const { sha256 } = require('./fidelity');

function mountAliceStages(app, root, stageRoot = process.env.ALICE_STAGE_ROOT || path.join(root, 'data/alice-stages')) {
  const manifest = path.join(stageRoot, 'stage_comparisons.json');
  function read() {
    if (!fs.existsSync(manifest)) return { stages: [], completed: false };
    const plan = JSON.parse(fs.readFileSync(manifest, 'utf8'));
    if (!Array.isArray(plan.stages)) throw new Error('Índice de etapas inválido.');
    return plan;
  }
  function stage(id) { return read().stages.find(s => s.id === id); }
  function assetFile(file) { return path.isAbsolute(file) ? file : path.resolve(stageRoot, file); }
  function checked(file, hash) {
    if (!file || !/^[a-f0-9]{64}$/.test(hash || '') || !fs.existsSync(assetFile(file)))
      throw Object.assign(new Error('Arquivo da etapa indisponível.'), { status: 404 });
    const bytes = fs.readFileSync(assetFile(file));
    if (sha256(bytes) !== hash) throw Object.assign(new Error('O arquivo mudou desde a comparação.'), { status: 409 });
    return bytes;
  }
  function model(s) {
    const evidence = s.comparison;
    if (!evidence) return null;
    if (evidence.sourcePhotoSha256 !== s.sourcePhotoSha256 || evidence.reusedGeometry !== false)
      throw Object.assign(new Error('A malha não pertence à foto desta etapa.'), { status: 409 });
    checked(s.sourcePhoto, s.sourcePhotoSha256);
    const file = evidence.displayModel?.file;
    const bytes = checked(file, evidence.displayModel?.sha256);
    return { file: assetFile(file), stats: inspectGlb(bytes) };
  }
  app.get('/alice/layers', (_, res) => res.sendFile(path.join(root, 'public/alice_layers.html')));
  app.get('/api/alice/stages', (_, res, next) => {
    try {
      const plan = read();
      res.json({ completed: false, comparisonPolicy: plan.comparisonPolicy, motionPolicy:plan.motionPolicy,
        stages: plan.stages.map(s => {
          const m = model(s);
          return { id: s.id, variant: s.variant, number: s.number, kind:s.kind || 'layer-stage', label: s.label, status: s.status,
            sourcePhotoSha256: s.sourcePhotoSha256, referenceUrl: `/api/alice/stages/${s.id}/reference`,
            model: m ? { url: `/api/alice/stages/${s.id}/model`, frontAxis:s.comparison.frontAxis, ...m.stats } : null,
            fidelityVerified: false, review: s.review, motionRequirements:s.motionRequirements,
            comparisonUrl: s.comparison?.board ? `/api/alice/stages/${s.id}/comparison` : null };
        }) });
    } catch (error) { next(error); }
  });
  app.get('/api/alice/stages/:id/:asset', (req, res, next) => {
    try {
      const s = stage(req.params.id);
      if (!s) return res.status(404).json({ error: 'Etapa desconhecida.' });
      if (req.params.asset === 'reference') {
        if (!/\.(png|jpe?g)$/i.test(s.sourcePhoto)) return res.sendStatus(404);
        checked(s.sourcePhoto, s.sourcePhotoSha256);
        return res.sendFile(assetFile(s.sourcePhoto));
      }
      if (req.params.asset === 'model') {
        const m = model(s);
        if (!m) return res.status(404).json({ error: 'Esta etapa ainda não tem malha nova.' });
        res.type('model/gltf-binary'); return res.sendFile(path.resolve(m.file));
      }
      if (req.params.asset === 'comparison' && s.comparison?.board) {
        model(s); // The board must have the same current photo/model binding as the viewer.
        checked(s.comparison.board.file, s.comparison.board.sha256);
        res.type('jpeg'); return res.sendFile(assetFile(s.comparison.board.file));
      }
      res.sendStatus(404);
    } catch (error) { next(error); }
  });
}

module.exports = { mountAliceStages };
