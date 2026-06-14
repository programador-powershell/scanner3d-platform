#!/usr/bin/env node
// Escaneia a pasta de referências e alimenta a seção AUTO:REFERENCES do md.
const fs = require('fs');
const path = require('path');
const { scanReferences, manifestToMarkdown, updateMdSection, formatSize } = require('../lib/references');

// UNIFIED default inside project. Override with REFERENCES_DIR env for large external sets.
const REFERENCES_DIR = process.env.REFERENCES_DIR || path.join(__dirname, '..', 'data', 'references');
const MD_PATH = path.join(__dirname, '..', 'docs', 'PROJETO_IA_3D_AAA.md');
const MANIFEST_PATH = path.join(__dirname, '..', 'data', 'references_manifest.json');

function main() {
  if (!fs.existsSync(REFERENCES_DIR)) {
    console.error(`Pasta de referências não encontrada: ${REFERENCES_DIR}`);
    process.exit(1);
  }
  console.log(`Escaneando ${REFERENCES_DIR} ...`);
  const manifest = scanReferences(REFERENCES_DIR);
  fs.mkdirSync(path.dirname(MANIFEST_PATH), { recursive: true });
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2), 'utf8');
  updateMdSection(MD_PATH, 'REFERENCES', manifestToMarkdown(manifest));
  console.log(`OK: ${manifest.totalFiles} arquivos (${formatSize(manifest.totalBytes)}) alimentados em ${MD_PATH}`);
}

main();
