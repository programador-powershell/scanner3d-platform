const fs = require('fs');
const path = require('path');

const IMG_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tga', '.exr']);
const MODEL_GLB = new Set(['.glb', '.gltf', '.obj']);

function walk(dir, base, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out; // diretório ilegível (EPERM/symlink quebrado): pula, não aborta o scan
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    let stat;
    try {
      stat = fs.statSync(full); // segue symlinks/junctions; lança se quebrado
    } catch {
      continue;
    }
    if (stat.isDirectory()) {
      walk(full, base, out);
    } else if (stat.isFile()) {
      out.push({ rel: path.relative(base, full), bytes: stat.size, ext: path.extname(entry.name).toLowerCase() });
    }
  }
  return out;
}

function categorize(file) {
  const rel = file.rel.toLowerCase();
  if (MODEL_GLB.has(file.ext)) return 'Modelos 3D (GLB/OBJ)';
  if (file.ext === '.fbx') {
    return rel.includes('anims') ? 'Animações (FBX)' : 'Modelos 3D / Rigs (FBX)';
  }
  if (IMG_EXTS.has(file.ext)) {
    if (/_tex[\\/]|\.fbm[\\/]/.test(rel)) return 'Texturas PBR';
    if (rel.startsWith('img\\') || rel.startsWith('img/')) return 'Imagens de conceito';
    return 'Imagens diversas';
  }
  if (file.ext === '.txt' || file.ext === '.md') return 'Documentos (roteiro/lore)';
  return 'Outros';
}

const CATEGORY_ORDER = [
  'Imagens de conceito',
  'Modelos 3D (GLB/OBJ)',
  'Modelos 3D / Rigs (FBX)',
  'Texturas PBR',
  'Animações (FBX)',
  'Documentos (roteiro/lore)',
  'Imagens diversas',
  'Outros',
];

function scanReferences(root) {
  const files = walk(root, root, []);
  const categories = {};
  for (const f of files) {
    const cat = categorize(f);
    if (!categories[cat]) categories[cat] = { count: 0, bytes: 0, files: [] };
    categories[cat].count++;
    categories[cat].bytes += f.bytes;
    categories[cat].files.push({ path: f.rel, bytes: f.bytes });
  }
  for (const cat of Object.values(categories)) {
    cat.files.sort((a, b) => a.path.localeCompare(b.path));
  }
  return {
    generatedAt: new Date().toISOString(),
    root,
    totalFiles: files.length,
    totalBytes: files.reduce((s, f) => s + f.bytes, 0),
    categories,
  };
}

function formatSize(bytes) {
  if (bytes >= 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return bytes + ' B';
}

// Texto vindo do usuário não pode quebrar sintaxe markdown nem injetar marcadores AUTO.
function sanitizeMdText(text) {
  return String(text || '')
    .replace(/<!--/g, '')
    .replace(/[\r\n]+/g, ' ')
    .replace(/([\[\]\\`|])/g, '\\$1');
}

// '(' e ')' quebram a sintaxe [texto](url); espaços também.
function encodeMdUrl(url) {
  return String(url || '')
    .replace(/<!--/g, '')
    .replace(/[\r\n]+/g, '')
    .replace(/\(/g, '%28')
    .replace(/\)/g, '%29')
    .replace(/ /g, '%20');
}

function mdLink(text, url) {
  return `[${sanitizeMdText(text) || encodeMdUrl(url)}](${encodeMdUrl(url)})`;
}

function manifestToMarkdown(manifest) {
  const lines = [];
  lines.push(`*Inventário gerado em ${manifest.generatedAt} a partir de \`${manifest.root}\`.*`);
  lines.push('');
  lines.push(`**Total: ${manifest.totalFiles} arquivos — ${formatSize(manifest.totalBytes)}**`);
  lines.push('');
  lines.push('| Categoria | Arquivos | Tamanho |');
  lines.push('|---|---|---|');
  const cats = CATEGORY_ORDER.filter((c) => manifest.categories[c]);
  for (const name of cats) {
    const c = manifest.categories[name];
    lines.push(`| ${name} | ${c.count} | ${formatSize(c.bytes)} |`);
  }
  lines.push('');
  for (const name of cats) {
    const c = manifest.categories[name];
    lines.push('<details>');
    lines.push(`<summary><strong>${name}</strong> — ${c.count} arquivos (${formatSize(c.bytes)})</summary>`);
    lines.push('');
    lines.push('| Arquivo | Tamanho |');
    lines.push('|---|---|');
    for (const f of c.files) {
      lines.push(`| \`${f.path.replace(/\\/g, '/').replace(/\|/g, '\\|')}\` | ${formatSize(f.bytes)} |`);
    }
    lines.push('');
    lines.push('</details>');
    lines.push('');
  }
  return lines.join('\n');
}

function assertMarkers(content, sections, mdPath) {
  for (const section of sections) {
    for (const marker of [`<!-- AUTO:${section}:START -->`, `<!-- AUTO:${section}:END -->`]) {
      const first = content.indexOf(marker);
      if (first === -1) throw new Error(`Marcador ausente em ${mdPath}: ${marker}`);
      if (content.indexOf(marker, first + marker.length) !== -1) {
        throw new Error(`Marcador duplicado em ${mdPath}: ${marker} — md corrompido, restaure de backup`);
      }
    }
  }
}

function updateMdSection(mdPath, section, body) {
  const start = `<!-- AUTO:${section}:START -->`;
  const end = `<!-- AUTO:${section}:END -->`;
  if (!fs.existsSync(mdPath)) {
    throw new Error(`Documento não encontrado: ${mdPath}`);
  }
  const content = fs.readFileSync(mdPath, 'utf8');
  assertMarkers(content, [section], mdPath);
  const startIdx = content.indexOf(start);
  const endIdx = content.indexOf(end);
  if (endIdx < startIdx) {
    throw new Error(`Marcadores AUTO:${section} fora de ordem em ${mdPath}`);
  }
  // Defesa contra injeção: corpo nunca pode conter marcadores AUTO.
  const safeBody = String(body).replace(/<!--\s*AUTO:/gi, '(removido)AUTO:');
  const updated = content.slice(0, startIdx + start.length) + '\n' + safeBody.trim() + '\n' + content.slice(endIdx);
  // Escrita atômica: tmp + rename (mesmo volume) — sem md meio-escrito em caso de crash.
  const tmp = mdPath + '.tmp';
  fs.writeFileSync(tmp, updated, 'utf8');
  fs.renameSync(tmp, mdPath);
}

module.exports = {
  scanReferences,
  manifestToMarkdown,
  updateMdSection,
  assertMarkers,
  formatSize,
  sanitizeMdText,
  encodeMdUrl,
  mdLink,
};
