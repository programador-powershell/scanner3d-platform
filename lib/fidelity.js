// A model score is an opinion on the supplied images, never proof of 3D fidelity.
const fs = require('fs');
const crypto = require('crypto');

const sha256 = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function unavailable(reason) {
  return { pass: false, verified: false, score: null, source: 'unavailable',
    defects: [reason], suggested_prompt_fix: '', param_adjustments: {} };
}

function normalizeVerdict(value, evidence) {
  if (!value || typeof value.pass !== 'boolean' || typeof value.score !== 'number' ||
      !Number.isFinite(value.score) || value.score < 0 || value.score > 1 ||
      !Array.isArray(value.defects) || value.defects.some(d => typeof d !== 'string')) {
    return unavailable('Resposta visual inválida; nenhuma aprovação foi inferida.');
  }
  const adjustments = {};
  for (const [key, val] of Object.entries(value.param_adjustments || {})) {
    if (['height_m', 'hip', 'shoulder', 'bust', 'waist', 'muscle', 'wind'].includes(key) &&
        typeof val === 'number' && Number.isFinite(val) && val >= 0 && val <= 3) adjustments[key] = val;
  }
  return { pass: value.pass && value.score >= 0.9 && value.defects.length === 0,
    verified: true, score: value.score, source: 'vision-model', evidence,
    defects: value.defects, suggested_prompt_fix: String(value.suggested_prompt_fix || ''),
    param_adjustments: adjustments };
}

function imagePayload(filepath) {
  const bytes = fs.readFileSync(filepath);
  const png = bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  const jpeg = bytes[0] === 255 && bytes[1] === 216;
  if (!png && !jpeg) throw new Error('Evidência visual deve ser PNG ou JPEG, não GLB.');
  return { hash: sha256(bytes), url: `data:image/${png ? 'png' : 'jpeg'};base64,${bytes.toString('base64')}` };
}

async function judgeWithVlm({ stage, references, preview, url, model, fetchImpl = fetch }) {
  if (!references.length || references.some(p => !fs.existsSync(p)) || !preview || !fs.existsSync(preview))
    return unavailable('Faltam referência original ou render real da etapa.');
  try {
    const images = [...references.map(imagePayload), imagePayload(preview)];
    const prompt = `Compare as primeiras ${references.length} imagens de referência com o ÚLTIMO render real da etapa ${stage}.
Descreva divergências visíveis de proporção, silhueta, cor, rosto, cabelo, roupa e detalhes.
Não presuma física, rig, topologia, identidade exata ou superfícies ocultas por uma imagem.
Se evidência for insuficiente, pass=false. Aprovar exige score>=0.9 e nenhuma divergência visível.
Responda somente JSON: {"pass":false,"score":0.0,"defects":[],"suggested_prompt_fix":"","param_adjustments":{}}.`;
    const response = await fetchImpl(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(90000), body: JSON.stringify({ model: model || 'Qwen3-VL-4B-Thinking',
        messages: [{ role: 'user', content: [{ type: 'text', text: prompt },
          ...images.map(i => ({ type: 'image_url', image_url: { url: i.url } }))] }],
        max_tokens: 1000, temperature: 0 }) });
    if (!response.ok) throw new Error(`Serviço visual retornou HTTP ${response.status}`);
    const data = await response.json();
    const text = data.choices?.[0]?.message?.content;
    if (typeof text !== 'string') throw new Error('Serviço visual não retornou uma avaliação.');
    const match = text.match(/\{[\s\S]*\}/);
    const value = match ? JSON.parse(match[0]) : null;
    return normalizeVerdict(value, { stage, references: images.slice(0, -1).map(i => i.hash),
      preview: images.at(-1).hash, evaluatedAt: new Date().toISOString(), scope: 'visible-image-comparison' });
  } catch (error) {
    return unavailable(`Análise visual indisponível: ${error.message}`);
  }
}

module.exports = { sha256, unavailable, normalizeVerdict, judgeWithVlm };
