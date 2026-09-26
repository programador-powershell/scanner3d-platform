// Download the existing source asset; this does not generate or approve a model.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { Readable } = require('stream');
const { pipeline } = require('stream/promises');

const commit = 'f6e534865a7b3432b6c7b374e8e10921905b4e4c';
const expected = '707db04639e87b74d21b298bc8c32033e2fb144c2c22c38f11acf8092d05b248';
const output = path.resolve(__dirname, '../data/source/alice.fbx');
async function main() {
  if (fs.existsSync(output)) {
    const hash = crypto.createHash('sha256');
    for await (const bytes of fs.createReadStream(output)) hash.update(bytes);
    if (hash.digest('hex') === expected) { console.log('FBX original já presente e verificado.'); return; }
    throw new Error('FBX local não corresponde à origem fixada. Arquivo preservado para inspeção.');
  }
  const url = `https://media.githubusercontent.com/media/programador-powershell/project-alice-game/${commit}/Content/Assets/3D/personagens/alice.fbx`;
  const response = await fetch(url, { signal: AbortSignal.timeout(300000) });
  if (!response.ok) throw new Error(`GitHub retornou HTTP ${response.status}`);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const temp = `${output}.download`;
  await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(temp));
  const hash = crypto.createHash('sha256');
  for await (const bytes of fs.createReadStream(temp)) hash.update(bytes);
  if (hash.digest('hex') !== expected) throw new Error('Hash do download divergente; arquivo temporário preservado.');
  fs.renameSync(temp, output);
  console.log(`FBX existente do Project Alice baixado e verificado: ${output}`);
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
