const fs = require('fs');
const path = require('path');
const express = require('express');
const multer = require('multer');
const sharp = require('sharp');
const { inspectGlb } = require('./glb');
const { sha256 } = require('./fidelity');

function mountAliceStudio(app, root) {
  require('./alice_stages').mountAliceStages(app, root);
  const refDir = path.join(root, 'data/references/alice');
  const runDir = path.join(root, 'data/alice-runs');
  fs.mkdirSync(runDir, { recursive: true });
  const profile = JSON.parse(fs.readFileSync(path.join(refDir, 'profile.json'), 'utf8'));
  const modelFiles = {
    detail: path.join(root, 'data/assets/alice-detail.glb'),
    source: path.join(refDir, 'alice-source.glb'),
    restored: path.join(root, 'data/assets/alice-restored.glb')
  };
  const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 100 * 1024 * 1024, files: 1 } });
  app.use('/vendor/three', express.static(path.join(root, 'node_modules/three')));
  app.get('/alice', (_, res) => res.sendFile(path.join(root, 'public/alice.html')));
  app.get('/api/alice', (_, res) => {
    const models = Object.entries(modelFiles).filter(([, file]) => fs.existsSync(file)).map(([id, file]) => ({
      id, label: id === 'detail' ? 'Alice · FBX detalhado (LOD3)' : id === 'restored' ? 'Alice · projeção multivista (rig)' : 'Alice · GLB original sem textura',
      url: `/api/alice/models/${id}`, ...inspectGlb(fs.readFileSync(file)),
      importReport: fs.existsSync(file.replace(/\.glb$/, '.report.json')) ? JSON.parse(fs.readFileSync(file.replace(/\.glb$/, '.report.json'), 'utf8')) : null
    }));
    res.json({ profile, models, reconstructionAvailable: !!process.env.ALICE_RECONSTRUCTION_URL,
      reconstructionContract: 'multipart front, side, back PNG → binary model/gltf-binary',
      trackEverything: { status: 'research-only', repository: 'https://github.com/ayushjain1144/trackeverything',
        note: 'Código do rastreador ainda não publicado; não há inferência TrackEverything nesta plataforma.' } });
  });
  app.get('/api/alice/reference/:view', async (req, res, next) => {
    try {
      const view = req.params.view;
      if (view === 'sheet') return res.sendFile(path.join(refDir, profile.reference));
      const calibration = profile.calibration.views[view];
      if (!calibration) return res.status(404).json({ error: 'Vista desconhecida.' });
      const [left, top, width, height] = calibration.crop;
      const bytes = await sharp(path.join(refDir, profile.reference)).extract({ left, top, width, height }).png().toBuffer();
      res.type('png').send(bytes);
    } catch (error) { next(error); }
  });
  app.get('/api/alice/models/:id', (req, res) => {
    const id = req.params.id;
    const file = modelFiles[id] || (/^import_[a-f0-9]{64}$/.test(id) ? path.join(runDir, `${id}.glb`) : null);
    if (!file || !fs.existsSync(file)) return res.status(404).json({ error: 'Malha não encontrada.' });
    res.type('model/gltf-binary');
    if (req.query.download) res.attachment(`alice-${id}.glb`);
    res.sendFile(file);
  });
  app.post('/api/alice/import', upload.single('model'), (req, res, next) => {
    try {
      if (!req.file || !/\.glb$/i.test(req.file.originalname)) return res.status(400).json({ error: 'Envie uma malha .glb.' });
      const stats = inspectGlb(req.file.buffer);
      const id = `import_${stats.sha256}`;
      fs.writeFileSync(path.join(runDir, `${id}.glb`), req.file.buffer);
      res.json({ id, label: req.file.originalname, url: `/api/alice/models/${id}`, ...stats });
    } catch (error) { error.status = 400; next(error); }
  });
  app.post('/api/alice/reconstruct', async (req, res, next) => {
    try {
      const url = process.env.ALICE_RECONSTRUCTION_URL;
      if (!url) return res.status(503).json({ error: 'Serviço de reconstrução multivista não configurado. A malha existente permanece identificada como importada.' });
      const form = new FormData();
      for (const [view, calibration] of Object.entries(profile.calibration.views)) {
        const [left, top, width, height] = calibration.crop;
        const bytes = await sharp(path.join(refDir, profile.reference)).extract({ left, top, width, height }).png().toBuffer();
        form.append(view, new Blob([bytes], { type: 'image/png' }), `${view}.png`);
      }
      form.append('profile', JSON.stringify(profile));
      const response = await fetch(url, { method: 'POST', body: form, signal: AbortSignal.timeout(300000) });
      if (!response.ok) throw new Error(`Reconstrução retornou HTTP ${response.status}.`);
      const maxBytes = 100 * 1024 * 1024;
      const chunks = []; let received = 0;
      for await (const chunk of response.body) {
        received += chunk.length;
        if (received > maxBytes) throw new Error('GLB excede 100 MB.');
        chunks.push(chunk);
      }
      const bytes = Buffer.concat(chunks), stats = inspectGlb(bytes), id = `import_${stats.sha256}`;
      fs.writeFileSync(path.join(runDir, `${id}.glb`), bytes);
      const provenance = { method: 'external-multiview-reconstruction', referenceSha256: sha256(fs.readFileSync(path.join(refDir, profile.reference))),
        modelSha256: stats.sha256, fidelityStatus: 'unverified', createdAt: new Date().toISOString() };
      fs.writeFileSync(path.join(runDir, `${id}.json`), JSON.stringify(provenance, null, 2));
      res.json({ id, label: 'Reconstrução multivista · a verificar', url: `/api/alice/models/${id}`, ...stats, provenance });
    } catch (error) { next(error); }
  });
  app.post('/api/alice/evidence', express.json({ limit: '16mb' }), async (req, res, next) => {
    try {
      const { modelId, modelSha256, renders } = req.body;
      const file = modelFiles[modelId] || (/^import_[a-f0-9]{64}$/.test(modelId) ? path.join(runDir, `${modelId}.glb`) : null);
      if (!file || !fs.existsSync(file)) return res.status(404).json({ error: 'Malha não encontrada.' });
      if (sha256(fs.readFileSync(file)) !== modelSha256) return res.status(409).json({ error: 'A evidência pertence a outra versão da malha.' });
      const evidence = {};
      const id = `evidence_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const dir = path.join(runDir, id);
      const buffers = {};
      for (const view of Object.keys(profile.calibration.views)) {
        const render = renders?.[view];
        if (typeof render !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(render))
          return res.status(400).json({ error: `Falta render PNG da vista ${view}.` });
        buffers[view] = Buffer.from(render.split(',')[1], 'base64');
        const meta = await sharp(buffers[view]).metadata();
        if (meta.format !== 'png' || meta.width !== 440 || meta.height !== 850 || !meta.hasAlpha)
          return res.status(400).json({ error: 'Renders precisam ter 440×850, fundo transparente e câmeras calibradas.' });
        evidence[view] = { sha256: sha256(buffers[view]), render: `${view}.png` };
      }
      fs.mkdirSync(dir);
      for (const [view, bytes] of Object.entries(buffers)) fs.writeFileSync(path.join(dir, `${view}.png`), bytes);
      const report = { modelSha256, referenceSha256: sha256(fs.readFileSync(path.join(refDir, profile.reference))),
        createdAt: new Date().toISOString(), views: evidence, calibration: profile.calibration,
        status: 'awaiting_visual_review', fidelityVerified: false,
        evidenceSource: 'browser-render; capture association checked, visual content requires review',
        limitations: profile.limitations };
      fs.writeFileSync(path.join(dir, 'report.json'), JSON.stringify(report, null, 2));
      res.json({ id, ...report, reportUrl: `/api/alice/evidence/${id}/report.json`,
        views: Object.fromEntries(Object.entries(evidence).map(([view, info]) => [view,
          { ...info, url: `/api/alice/evidence/${id}/${view}.png` }])) });
    } catch (error) { error.status = 400; next(error); }
  });
  app.get('/api/alice/evidence/:id/:file', (req, res) => {
    if (!/^evidence_\d+_[a-z0-9]{6}$/.test(req.params.id) ||
        !['front.png', 'side.png', 'back.png', 'report.json'].includes(req.params.file)) return res.sendStatus(404);
    const file = path.join(runDir, req.params.id, req.params.file);
    if (!fs.existsSync(file)) return res.sendStatus(404);
    res.sendFile(file);
  });
}

module.exports = { mountAliceStudio };
