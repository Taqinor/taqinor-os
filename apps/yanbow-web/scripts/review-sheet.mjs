#!/usr/bin/env node
/**
 * Fiche de relecture FR (YBW67) — GÉNÉRÉE depuis le RENDU, jamais à la main.
 *
 * Lit chaque page française construite du registre (`dist/client/`, après
 * `npm run build`) et produit `REVIEW_FR.md` :
 *  - chaque phrase publique, dans l'ordre de la page ;
 *  - pour une phrase qui affirme un fait (`data-affirmation`) : son
 *    identifiant, son statut et ses preuves (`src/lib/claims.ts`) ;
 *  - les autres phrases (titres, navigation, appels) marquées « interface » ;
 *  - l'état `check-claims --stale` et les décisions ouvertes ;
 *  - les captures 375 px et 1440 px de chaque page (`--captures` : build servi
 *    par `astro preview`, vrai Worker, mouvement réduit) dans `review/`.
 *
 * Usage : npm run build && node scripts/review-sheet.mjs [--captures]
 */
import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { JSDOM } from 'jsdom';
import { executer, importerTs } from './check-claims.mjs';
import { lireRegistreTs } from './generate-og.mjs';

const RACINE = fileURLToPath(new URL('../', import.meta.url));
const DIST = join(RACINE, 'dist', 'client');
const SORTIE = join(RACINE, 'REVIEW_FR.md');
const DOSSIER_CAPTURES = join(RACINE, 'review');
export const LARGEURS = [375, 1440];
const PORT = 4331;

/** Décisions ouvertes à rappeler à Reda (plan, section MANUEL). */
const DECISIONS_OUVERTES = [
  'YBWM13 — approuver ce texte français avant toute traduction (YBW70).',
  'YBWM11 — coloration du slogan (A ou B) : le logo du pied de page reste en version actuelle.',
  'YBWM4 — numéro WhatsApp et e-mail de YanBow : tant qu’ils manquent, aucun bouton WhatsApp.',
  'YBWM5 / YBWM6 — sociétés à créer : tant que legal.ts est vide, aucune forme juridique n’est rendue (page Société, pages juridiques fermées).',
  'YBW41 — captures réelles du kit (société fictive locale) : en attendant, un cadre neutre « Capture d’écran en préparation » avec la légende « Données fictives ».',
];

/** Pages françaises construites du registre : `{ id, url, fichier }`. */
export function pagesFr() {
  return Object.entries(lireRegistreTs())
    .map(([id, chemins]) => ({ id, url: chemins.fr, fichier: join(DIST, ...chemins.fr.split('/').filter(Boolean), 'index.html') }))
    .filter((p) => existsSync(p.fichier));
}

/**
 * Phrases publiques d'un document, dans l'ordre : `{ texte, affirmation | null, zone }`.
 * Un bloc `data-affirmation` est UNE phrase liée à son identifiant ; les autres
 * blocs feuilles (titres, paragraphes, liens, libellés) sont « interface ».
 * @param {Document} doc
 */
export function phrasesPubliques(doc) {
  const out = [];
  const vus = new Set();
  const BLOCS = 'h1, h2, h3, p, li, a, button, label, figcaption, dt, dd, span.etape-titre, span.etape-detail, span.capture-emplacement-titre, span.capture-emplacement-note, option';
  for (const el of doc.querySelectorAll(`[data-affirmation], ${BLOCS}`)) {
    if ([...vus].some((v) => v.contains(el))) continue;
    if (el.closest('[hidden], .rdv-pot, .logo-texte, script, style')) continue;
    const propre = (/** @type {Element} */ e) => (e.textContent ?? '').replace(/\s+/g, ' ').trim();
    // Affirmation : le bloc lui-même, un ancêtre, ou un enfant qui porte TOUT son texte (h1 > span).
    const interne = el.querySelector('[data-affirmation]');
    const aff = el.closest('[data-affirmation]') ?? (interne && propre(interne) === propre(el) ? interne : null);
    const cible = el.closest('[data-affirmation]') ?? el;
    if (vus.has(cible)) continue;
    // Un bloc qui contient d'autres blocs listés est lu par ses enfants.
    if (!aff && cible.querySelector(BLOCS)) continue;
    const texte = propre(cible);
    if (!texte) continue;
    vus.add(cible);
    const zone = cible.closest('header.entete, .lien-evitement') ? 'en-tête' : cible.closest('footer.pied') ? 'pied' : 'contenu';
    out.push({ texte, affirmation: aff ? aff.getAttribute('data-affirmation') : null, zone });
  }
  return out;
}

/** @param {string} s */
const md = (s) => s.replace(/\|/g, '\\|');

/**
 * @param {{ id: string, url: string }[]} pages
 * @returns {Promise<Record<string, { largeur: number, nom: string }[]>>}
 */
async function captures(pages) {
  rmSync(DOSSIER_CAPTURES, { recursive: true, force: true });
  mkdirSync(DOSSIER_CAPTURES, { recursive: true });
  const serveur = spawn(`npx astro preview --host 127.0.0.1 --port ${PORT}`, { cwd: RACINE, shell: true, stdio: 'ignore' });
  const base = `http://127.0.0.1:${PORT}`;
  try {
    for (let i = 0; i < 120; i++) {
      try {
        if ((await fetch(`${base}/robots.txt`)).ok) break;
      } catch {
        /* pas encore prêt */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    const { chromium } = await import('@playwright/test');
    const navigateur = await chromium.launch();
    const contexte = await navigateur.newContext({ reducedMotion: 'reduce', colorScheme: 'light' });
    const page = await contexte.newPage();
    /** @type {Record<string, { largeur: number, nom: string }[]>} */
    const fichiers = {};
    for (const p of pages) {
      fichiers[p.id] = [];
      for (const largeur of LARGEURS) {
        await page.setViewportSize({ width: largeur, height: 900 });
        await page.goto(base + p.url, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts.ready);
        const nom = `${p.id}-fr-${largeur}.jpg`;
        await page.screenshot({ path: join(DOSSIER_CAPTURES, nom), fullPage: true, type: 'jpeg', quality: 72 });
        fichiers[p.id].push({ largeur, nom });
      }
    }
    await navigateur.close();
    return fichiers;
  } finally {
    // Arrête SEULEMENT le serveur lancé ici (et ses enfants).
    if (process.platform === 'win32' && serveur.pid) {
      try {
        execFileSync('taskkill', ['/pid', String(serveur.pid), '/T', '/F'], { stdio: 'ignore' });
      } catch {
        /* déjà arrêté */
      }
    } else serveur.kill('SIGTERM');
  }
}

async function principal() {
  const avecCaptures = process.argv.includes('--captures');
  const pages = pagesFr();
  if (!pages.length) throw new Error('aucune page FR construite — lancer `npm run build` d’abord');
  const { AFFIRMATIONS } = await importerTs(join(RACINE, 'src/lib/claims.ts'));
  const parId = new Map(AFFIRMATIONS.map((/** @type {{ id: string }} */ a) => [a.id, a]));
  const { erreurs, perimees } = await executer({ stale: true });
  const images = avecCaptures ? await captures(pages) : null;

  const l = [
    '# Fiche de relecture — texte français (YBW67)',
    '',
    '> GÉNÉRÉE par `node scripts/review-sheet.mjs --captures` depuis les pages CONSTRUITES — ne pas éditer à la main.',
    '> Chaque phrase publique, dans l’ordre de la page. Une phrase qui affirme un fait porte l’identifiant de son',
    '> affirmation (`src/lib/claims.ts`), son statut et ses preuves ; les autres sont du texte d’interface',
    '> (titres, navigation, appels). Question à Reda : YBWM13 — approuver ce texte avant toute traduction.',
    '',
    '## État des gardes',
    '',
    `- \`check-claims\` : ${erreurs.length ? `${erreurs.length} erreur(s)` : 'OK'}`,
    `- \`check-claims --stale\` : ${perimees.length ? `${perimees.length} affirmation(s) dont une preuve a changé depuis sa relecture (à relire avant le lancement, YBW85)` : 'vide'}`,
    ...perimees.map((p) => `  - ${md(p)}`),
    '',
    '## Décisions ouvertes',
    '',
    ...DECISIONS_OUVERTES.map((d) => `- ${d}`),
    '',
  ];
  const vuesGlobales = new Set();
  for (const p of pages) {
    const doc = new JSDOM(readFileSync(p.fichier, 'utf-8')).window.document;
    l.push(`## ${md(doc.title)} — \`${p.url}\``, '');
    if (images) l.push((images[p.id] ?? []).map((i) => `[${i.largeur} px](review/${i.nom})`).join(' · '), '');
    l.push('| # | Phrase | Affirmation | Statut | Preuves |', '| --- | --- | --- | --- | --- |');
    let n = 0;
    for (const ph of phrasesPubliques(doc)) {
      if (ph.zone !== 'contenu') {
        // En-tête et pied : listés une seule fois pour tout le site.
        const cle = `${ph.zone}:${ph.texte}`;
        if (vuesGlobales.has(cle)) continue;
        vuesGlobales.add(cle);
      }
      n++;
      const a = ph.affirmation ? parId.get(ph.affirmation) : null;
      const statut = a ? `${a.statut}${a.publiable ? '' : ' — NON PUBLIABLE'}` : 'interface';
      const preuves = a ? a.preuves.map((/** @type {string} */ x) => `\`${x}\``).join('<br>') : '';
      l.push(`| ${n} | ${md(ph.texte)}${ph.zone === 'contenu' ? '' : ` _(${ph.zone})_`} | ${a ? `\`${a.id}\`` : '—'} | ${statut} | ${preuves} |`);
    }
    l.push('');
  }
  writeFileSync(SORTIE, l.join('\n'));
  console.log(`[review-sheet] ${pages.length} page(s) → ${SORTIE}${images ? ` + captures dans ${DOSSIER_CAPTURES}` : ''}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  principal().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
