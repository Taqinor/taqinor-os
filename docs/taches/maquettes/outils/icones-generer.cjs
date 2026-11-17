// Régénère maquettes/icones.js : le SEUL sprite d'icônes des maquettes.
// Lit chaque `<use href="#i-NOM">` des maquettes et prend le tracé réel de lucide-react (NOM.mjs).
// Usage : node docs/taches/maquettes/outils/icones-generer.cjs
// À relancer dès qu'une maquette emploie une nouvelle icône ; verifier.cjs échoue sinon.
const fs = require('fs');
const path = require('path');
const LUCIDE = process.env.LUCIDE_DIR || 'C:/dev/taqinor-os/frontend/node_modules/lucide-react/dist/esm/icons';
const dossier = path.resolve(__dirname, '..');
const noms = new Set();
for (const f of fs.readdirSync(dossier)) {
  if (!f.endsWith('.html')) continue;
  const t = fs.readFileSync(path.join(dossier, f), 'utf8');
  for (const m of t.matchAll(/href="#i-([a-z0-9-]+)"/g)) noms.add(m[1]);
}
// icônes posées par coque.js (barre latérale, onglets)
for (const n of ['sun', 'inbox', 'folder', 'calendar', 'layout-grid', 'folder-plus']) noms.add(n);
const manquantes = [];
const symboles = [...noms].sort().map((n) => {
  const fichier = path.join(LUCIDE, n + '.mjs');
  if (!fs.existsSync(fichier)) { manquantes.push(n); return ''; }
  const src = fs.readFileSync(fichier, 'utf8');
  const bloc = src.match(/const __iconNode = \[([\s\S]*?)\];/)[1];
  const elements = [...bloc.matchAll(/\[\s*"(\w+)",\s*\{([^}]*)\}\s*\]/g)].map(([, tag, attrs]) => {
    const a = [...attrs.matchAll(/(\w+): "([^"]*)"/g)].filter(([, k]) => k !== 'key')
      .map(([, k, v]) => `${k}="${v}"`).join(' ');
    return `<${tag} ${a}/>`;
  }).join('');
  return `<symbol id="i-${n}" viewBox="0 0 24 24">${elements}</symbol>`;
}).join('');
if (manquantes.length) { console.error('Icônes absentes de lucide-react : ' + manquantes.join(', ')); process.exit(1); }
const sprite = `<svg xmlns="http://www.w3.org/2000/svg" id="sprite-taches" style="display:none" aria-hidden="true">${symboles}</svg>`;
const js = `// GÉNÉRÉ par outils/icones-generer.cjs (tracés de lucide-react) — ne pas éditer à la main.
// Chargé par toutes les maquettes : <script src="icones.js" defer></script> dans <head>.
(function () {
  var s = ${JSON.stringify(sprite)};
  function poser() { if (!document.getElementById('sprite-taches')) document.body.insertAdjacentHTML('afterbegin', s); }
  if (document.body) poser(); else document.addEventListener('DOMContentLoaded', poser);
})();
`;
fs.writeFileSync(path.join(dossier, 'icones.js'), js);
console.log(`icones.js : ${noms.size} icônes`);
