const { sha256 } = require('./fidelity');

function inspectGlb(bytes) {
  if (!Buffer.isBuffer(bytes) || bytes.length < 28 || bytes.readUInt32LE(0) !== 0x46546c67 ||
      bytes.readUInt32LE(4) !== 2 || bytes.readUInt32LE(8) !== bytes.length)
    throw new Error('Arquivo não é um GLB 2.0 completo.');
  let doc, binary, cursor = 12;
  while (cursor < bytes.length) {
    if (cursor + 8 > bytes.length) throw new Error('Cabeçalho de chunk incompleto.');
    const size = bytes.readUInt32LE(cursor), kind = bytes.readUInt32LE(cursor + 4);
    if (size % 4 || cursor + 8 + size > bytes.length) throw new Error('Chunk GLB inválido.');
    if (cursor === 12 && kind !== 0x4e4f534a) throw new Error('JSON deve ser o primeiro chunk.');
    if (kind === 0x4e4f534a) {
      if (doc) throw new Error('JSON duplicado.');
      doc = JSON.parse(bytes.subarray(cursor + 8, cursor + 8 + size).toString('utf8'));
    }
    if (kind === 0x004e4942) {
      if (binary) throw new Error('Buffer binário duplicado.');
      binary = bytes.subarray(cursor + 8, cursor + 8 + size);
    }
    cursor += 8 + size;
  }
  if (doc?.asset?.version !== '2.0' || !binary) throw new Error('Geometria GLB incorporada ausente.');
  if (doc.buffers?.length !== 1 || doc.buffers[0].uri || doc.buffers[0].byteLength > binary.length)
    throw new Error('GLB precisa de um único buffer incorporado.');
  if (doc.images?.some(i => i.uri) || doc.extensionsRequired?.length)
    throw new Error('Recursos externos ou compressão requerida precisam ser convertidos para GLB independente.');
  const sizes = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
  const widths = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
  function access(index) {
    const a = doc.accessors?.[index], v = a && doc.bufferViews?.[a.bufferView];
    const item = a && sizes[a.componentType] * widths[a.type];
    if (!v || a.sparse || !item || !Number.isInteger(a.count) || a.count < 1 ||
        v.buffer !== 0 || !Number.isInteger(v.byteLength)) throw new Error('Accessor inválido.');
    const stride = v.byteStride || item, start = (v.byteOffset || 0) + (a.byteOffset || 0);
    const end = start + (a.count - 1) * stride + item;
    if (stride < item || start < 0 || end > (v.byteOffset || 0) + v.byteLength || end > binary.length)
      throw new Error('Accessor fora do buffer.');
    return { ...a, start, stride };
  }
  const activeMeshes = new Set(), visited = new Set(), stack = new Set();
  function visit(index) {
    if (stack.has(index)) throw new Error('Hierarquia GLB cíclica.');
    if (visited.has(index)) return;
    const node = doc.nodes?.[index];
    if (!node) throw new Error('Nó de cena ausente.');
    visited.add(index); stack.add(index);
    if (node.mesh !== undefined) {
      if (!doc.meshes?.[node.mesh]) throw new Error('Malha de cena ausente.');
      activeMeshes.add(node.mesh);
    }
    for (const child of node.children || []) visit(child);
    stack.delete(index);
  }
  const scene = doc.scenes?.[doc.scene || 0];
  if (!scene) throw new Error('Cena GLB ausente.');
  for (const node of scene.nodes || []) visit(node);
  let vertices = 0, triangles = 0, texturedPrimitives = 0;
  const sums = [0, 0, 0], products = [0, 0, 0, 0, 0, 0];
  const bounds = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  for (const meshId of activeMeshes) for (const p of doc.meshes[meshId].primitives || []) {
    if (p.mode !== undefined && p.mode !== 4) throw new Error('A inspeção exige malha triangular.');
    const position = access(p.attributes?.POSITION);
    if (position.type !== 'VEC3' || position.componentType !== 5126)
      throw new Error('Posições devem ser VEC3 float.');
    vertices += position.count;
    // Read the actual coordinates; accessor min/max are only author metadata.
    for (let i = 0; i < position.count; i++) {
      const xyz = [0, 1, 2].map(axis => binary.readFloatLE(position.start + i * position.stride + axis * 4));
      for (let axis = 0; axis < 3; axis++) {
        const value = xyz[axis];
        if (!Number.isFinite(value)) throw new Error('Geometria contém coordenada não finita.');
        bounds.min[axis] = Math.min(bounds.min[axis], value);
        bounds.max[axis] = Math.max(bounds.max[axis], value);
        sums[axis] += value;
      }
      products[0] += xyz[0] ** 2; products[1] += xyz[1] ** 2; products[2] += xyz[2] ** 2;
      products[3] += xyz[0] * xyz[1]; products[4] += xyz[0] * xyz[2]; products[5] += xyz[1] * xyz[2];
    }
    if (p.indices !== undefined) {
      const indices = access(p.indices);
      if (indices.type !== 'SCALAR' || ![5121, 5123, 5125].includes(indices.componentType))
        throw new Error('Índices inválidos.');
      for (let i = 0; i < indices.count; i++) {
        const offset = indices.start + i * indices.stride;
        const value = indices.componentType === 5121 ? binary.readUInt8(offset) :
          indices.componentType === 5123 ? binary.readUInt16LE(offset) : binary.readUInt32LE(offset);
        if (value >= position.count) throw new Error('Índice fora da malha.');
      }
      triangles += indices.count / 3;
      if (indices.count % 3) throw new Error('Triângulo incompleto.');
    } else {
      if (position.count % 3) throw new Error('Triângulo incompleto.');
      triangles += position.count / 3;
    }
    for (const attribute of Object.values(p.attributes || {})) access(attribute);
    if (doc.materials?.[p.material]?.pbrMetallicRoughness?.baseColorTexture) texturedPrimitives++;
  }
  const dimensions = bounds.max.map((max, i) => max - bounds.min[i]);
  if (!triangles || dimensions.some(d => !Number.isFinite(d) || d <= 1e-5))
    throw new Error('A malha não tem volume nas três dimensões. Uma imagem/plano não é uma personagem 3D.');
  // Bounding boxes alone accept a flat card rotated diagonally. Covariance
  // rank checks whether the actual points occupy three independent directions.
  const mean = sums.map(v => v / vertices);
  const [xx, yy, zz, xy, xz, yz] = products.map((v, i) => v / vertices -
    [mean[0] ** 2, mean[1] ** 2, mean[2] ** 2, mean[0] * mean[1], mean[0] * mean[2], mean[1] * mean[2]][i]);
  const det = xx * yy * zz + 2 * xy * xz * yz - xx * yz * yz - yy * xz * xz - zz * xy * xy;
  if (!Number.isFinite(det) || det <= (xx + yy + zz) ** 3 * 1e-12)
    throw new Error('Geometria planar: os pontos não formam volume 3D.');
  return { sha256: sha256(bytes), bytes: bytes.length, vertices, triangles,
    meshes: activeMeshes.size, unreferencedMeshes: doc.meshes.length - activeMeshes.size,
    materials: doc.materials?.length || 0, texturedPrimitives,
    joints: (doc.skins || []).reduce((n, s) => n + (s.joints?.length || 0), 0),
    animations: (doc.animations || []).map(a => a.name || 'Animação sem nome'),
    bounds, dimensions, boundsSpace: 'mesh-local-unposed',
    restoration: doc.extras?.aliceRestoration || null, fidelityStatus: 'unverified' };
}

module.exports = { inspectGlb };
