// Contrôle des maquettes Tâches : ouvre CHAQUE maquette en iPhone (390×844) et bureau (1440×900), clair et sombre,
// et ÉCHOUE (code 1) si :
//   icone     un <use> vise un symbole absent, ou une icône rend une boîte vide ;
//   contraste un texte visible est sous 4,5:1 (fond composité à travers les ancêtres, opacités comprises) ;
//   cible     une cible interactive visible fait moins de 44 px de côté (::after d'élargissement compris) ;
//   recouvert une cible est sous le bouton flottant, ou sous la barre d'onglets hors d'une zone qui défile ;
//   lexique   un libellé interdit apparaît (liste ci-dessous, tirée de textes.md §1 et des décisions du L3 n°8).
// Il imprime aussi la ligne de base du titre de page au bureau (même y attendu partout).
// Usage : node verifier.cjs [fichier.html …]   (sans argument : toutes les maquettes du dossier parent)
// Playwright vient du checkout principal (les worktrees n'ont pas de node_modules).
const path = require('path');
const fs = require('fs');
const pw = require(process.env.PLAYWRIGHT_DIR || 'C:/dev/taqinor-os/frontend/node_modules/playwright');

// Interdits : textes.md §1 (colonne « Interdits ») réduits aux formes qui ne peuvent pas être un mot légitime
// ailleurs, + décisions de l'orchestrateur (« Passer à N »).
const INTERDITS = [
  'jour prévu', 'plan proposé', 'valider le plan(?! de)', 'plan tenu', 'décharger',
  'boîte de réception', 'inbox', 'à décider', 'en retard', '(?<!Choisir )un jour(?=\\s*$)', '(?<=^|· )plus tard(?=\\s*$|\\s*·)',
  'peut-être', 'bloquée', 'épingler', 'cadrage', 'planifiée le', 'deadline', 'repousser', 'replanifier', 'urgent',
  'corbeille', 'clôture', 'coach', 'palier', 'score', 'série', 'journée réussie', 'journée ratée', 'jour ouvré',
  'jours ouvrés', 'capacité', 'estimation', 'Après…', 'tâche ERP', 'focus', 'domaine', 'important', 'importante',
  'Passer à \\d',
];
const INTERDITS_MOTS = ['IA', 'agent', 'Mes tâches', 'Ma journée', 'Privée']; // sensibles à la casse, mot entier
const reInterdit = new RegExp('(^|[^\\p{L}])(' + INTERDITS.join('|') + ')(?=$|[^\\p{L}])', 'iu');
const reMots = new RegExp('(^|[^\\p{L}])(' + INTERDITS_MOTS.join('|') + ')(?=$|[^\\p{L}])', 'u');

const dossier = path.resolve(__dirname, '..');
const fichiers = (process.argv.slice(2).length ? process.argv.slice(2).map((f) => path.resolve(f))
  : fs.readdirSync(dossier).filter((f) => f.endsWith('.html')).map((f) => path.join(dossier, f)));
const VUES = [
  { cle: 'iphone', width: 390, height: 844, deviceScaleFactor: 1, isMobile: true, hasTouch: true },
  { cle: 'bureau', width: 1440, height: 900, deviceScaleFactor: 1 },
];

function analyser(args) {
  const { reSrc, reMotsSrc, planche } = args;
  const reI = new RegExp(reSrc, 'iu'); const reM = new RegExp(reMotsSrc, 'u');
  const out = [];
  const nom = (e) => { const t = (e.getAttribute('aria-label') || e.textContent || '').trim().replace(/\s+/g, ' ');
    return (e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : '') + ' « ' + t.slice(0, 40) + ' »'); };
  const cache = new Map(); const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  function rgba(c) {
    if (cache.has(c)) return cache.get(c);
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; const r = [d[0], d[1], d[2], d[3] / 255];
    cache.set(c, r); return r;
  }
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const melange = (haut, bas) => { const a = haut[3]; return [0, 1, 2].map((i) => haut[i] * a + bas[i] * (1 - a)).concat(1); };
  function fond(e) {
    const pile = [];
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n); const c = rgba(s.backgroundColor);
      if (c[3] > 0) pile.push(c);
      if (c[3] >= 1) break;
    }
    let f = rgba(getComputedStyle(document.body).backgroundColor); if (f[3] < 1) f = [255, 255, 255, 1];
    for (let i = pile.length - 1; i >= 0; i--) f = melange(pile[i], f);
    return f;
  }
  const visible = (e) => { const s = getComputedStyle(e); if (s.visibility === 'hidden' || s.display === 'none') return false;
    const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const cache2 = new WeakMap();
  const cache2Get = (e) => { if (!cache2.has(e)) cache2.set(e, !!e.closest('[aria-hidden="true"], [inert], .note, .planche-titre, .texte-note, [data-hors-controle]')); return cache2.get(e); };
  const dessus = (e) => { const r = e.getBoundingClientRect(); const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
    const y = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1); const h = document.elementFromPoint(x, y);
    return h; };
  const estVu = (e) => { const h = dessus(e); return h && (h === e || e.contains(h) || h.contains(e)); };

  // 1. icônes
  document.querySelectorAll('use').forEach((u) => {
    const href = u.getAttribute('href') || u.getAttribute('xlink:href') || '';
    if (!href.startsWith('#')) return;
    const s = document.getElementById(href.slice(1));
    if (!s || !s.firstElementChild) { out.push(['icone', 'symbole absent ' + href]); return; }
    const svg = u.closest('svg'); if (!svg || !visible(svg)) return;
    const b = u.getBBox(); if (!b.width && !b.height) out.push(['icone', 'boîte vide ' + href]);
  });
  // 2. contraste + 5. lexique
  const lexique = new Set();
  const marche = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const vus = new Set();
  for (let t = marche.nextNode(); t; t = marche.nextNode()) {
    const txt = t.nodeValue.trim(); if (!txt) continue; const e = t.parentElement; if (!e || vus.has(e)) continue; vus.add(e);
    if (['SCRIPT', 'STYLE', 'TITLE'].includes(e.tagName)) continue;
    const plein = e.textContent.replace(/\s+/g, ' ').trim();
    if (!planche && !cache2Get(e)) { const m = plein.match(reI) || plein.match(reM); if (m) lexique.add(m[2] + ' ← « ' + plein.slice(0, 60) + ' »'); }
    if (cache2Get(e) || !visible(e)) continue;
    const s = getComputedStyle(e); if (parseFloat(s.fontSize) < 1) continue;
    if (e.closest('[aria-disabled="true"], :disabled')) continue;
    if (!estVu(e)) continue;
    let c = rgba(s.color); let op = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) op *= parseFloat(getComputedStyle(n).opacity);
    c = [c[0], c[1], c[2], c[3] * op];
    const f = fond(e); const r = ratio(melange(c, f), f);
    if (r < 4.5) out.push(['contraste', r.toFixed(2) + ':1 ' + nom(e)]);
  }
  document.querySelectorAll('[aria-label], [placeholder]').forEach((e) => { if (cache2Get(e) || planche) return;
    const v = (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('placeholder') || ''); const m = v.match(reI) || v.match(reM);
    if (m) lexique.add(m[2] + ' ← [' + v.trim().slice(0, 60) + ']'); });
  lexique.forEach((l) => out.push(['lexique', l]));
  // 3. cibles + 4. recouvrement
  const fab = [...document.querySelectorAll('.fab')].filter(visible).filter((f) => getComputedStyle(f).opacity !== '0');
  const ong = [...document.querySelectorAll('.onglets')].filter(visible);
  // contenu dans le flux d'une page : il défile sous la barre d'onglets (normal) ; une surcouche (barre, toast,
  // feuille, bouton posé en absolu) ne défile pas : recouverte, elle est perdue.
  const surcouche = (e) => { for (let n = e; n && n !== document.body; n = n.parentElement) {
    if (n.classList.contains('ecran') || n.classList.contains('page')) return false;
    if (/(fixed|absolute|sticky)/.test(getComputedStyle(n).position)) return true; } return false; };
  const cibles = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="checkbox"], [role="switch"], [role="tab"], [role="radio"], [role="option"], [role="menuitem"], [tabindex]:not([tabindex="-1"])');
  cibles.forEach((e) => {
    if (cache2Get(e) || !visible(e)) return;
    { let o = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) { const s = getComputedStyle(n); o *= parseFloat(s.opacity); if (s.pointerEvents === 'none') o = 0; } if (o === 0) return; }
    if (e.closest('p, li > span, .phrase') && e.tagName === 'A' && !e.className) return; // lien dans une phrase (exception WCAG)
    const r = e.getBoundingClientRect(); let w = r.width, h = r.height;
    const a = getComputedStyle(e, '::after');
    if (a.content && a.content !== 'none' && a.position === 'absolute') {
      const px = (v) => (v.endsWith('px') ? parseFloat(v) : NaN);
      let aw = px(a.width), ah = px(a.height);
      if (isNaN(aw)) aw = w - (px(a.left) || 0) - (px(a.right) || 0);
      if (isNaN(ah)) ah = h - (px(a.top) || 0) - (px(a.bottom) || 0);
      w = Math.max(w, aw); h = Math.max(h, ah);
    }
    if (Math.round(w) < 44 || Math.round(h) < 44) out.push(['cible', Math.round(w) + '×' + Math.round(h) + ' ' + nom(e)]);
    const hit = dessus(e); if (!hit) return;
    if (fab.some((f) => f.contains(hit) && !f.contains(e) && !e.contains(f))) out.push(['recouvert', 'bouton flottant sur ' + nom(e)]);
    if (ong.some((o) => o.contains(hit) && !o.contains(e)) && surcouche(e)) out.push(['recouvert', 'onglets sur ' + nom(e)]);
  });
  const h1 = [...document.querySelectorAll('h1')].find(visible);
  return { defauts: out, titre: h1 ? Math.round(h1.getBoundingClientRect().bottom) : null };
}

(async () => {
  const navigateur = await pw.chromium.launch();
  let total = 0; const titres = [];
  const taches = [];
  for (const fichier of fichiers) for (const vue of VUES) for (const theme of ['clair', 'sombre']) taches.push({ fichier, vue, theme });
  const resultats = new Array(taches.length);
  let i = 0;
  async function travailleur() {
    while (i < taches.length) {
      const k = i++; const { fichier, vue, theme } = taches[k];
      const { cle, ...v } = vue;
      const ctx = await navigateur.newContext({ viewport: { width: v.width, height: v.height }, deviceScaleFactor: 1,
        isMobile: !!v.isMobile, hasTouch: !!v.hasTouch, colorScheme: theme === 'sombre' ? 'dark' : 'light' });
      const page = await ctx.newPage();
      const erreurs = [];
      page.on('pageerror', (e) => erreurs.push(['script', e.message]));
      await page.goto('file:///' + fichier.split(path.sep).join('/') + '?vue=' + cle + '&theme=' + theme);
      await page.evaluate((t) => document.documentElement.classList.toggle('dark', t === 'sombre'), theme);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(150);
      const planche = /composants|tuile/.test(path.basename(fichier));
      const r = await page.evaluate(analyser, { reSrc: reInterdit.source, reMotsSrc: reMots.source, planche });
      resultats[k] = { nom: path.basename(fichier, '.html'), vue: cle, theme, defauts: erreurs.concat(r.defauts), titre: r.titre };
      await ctx.close();
    }
  }
  await Promise.all([1, 2, 3, 4].map(travailleur));
  for (const r of resultats) {
    const vus = new Set();
    for (const [type, detail] of r.defauts) {
      const cle = type + detail; if (vus.has(cle)) continue; vus.add(cle);
      console.log(`ÉCHEC ${r.nom} ${r.vue}-${r.theme} ${type} : ${detail}`); total++;
    }
    if (r.vue === 'bureau' && r.theme === 'clair' && r.titre !== null) titres.push(`${r.titre}\t${r.nom}`);
  }
  const groupes = {}; titres.forEach((l) => { const [y, n] = l.split('\t'); (groupes[y] = groupes[y] || []).push(n); });
  console.log('\nBas du titre de page au bureau (y) :');
  Object.keys(groupes).sort((a, b) => a - b).forEach((y) => console.log(`  ${y} px : ${groupes[y].join(', ')}`));
  console.log(`\n${fichiers.length} maquettes × 4 vues : ${total} échec(s).`);
  await navigateur.close();
  process.exit(total ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
