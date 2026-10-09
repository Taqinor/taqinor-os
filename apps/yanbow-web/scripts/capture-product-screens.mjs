#!/usr/bin/env node
/**
 * YBW41 — kit de captures d'écran produit sur une société FICTIVE locale (D-YBW-10).
 *
 * Mode d'emploi complet : `scripts/CAPTURE.md`. En bref :
 *   CAPTURE_IDENTIFIANT=… CAPTURE_MOT_DE_PASSE=… CAPTURE_ID_CALEPINAGE=… \
 *     node scripts/capture-product-screens.mjs [--ecran <id>]…
 *
 * Garanties (testées dans `tests/productScreens.test.ts`) :
 *  - pile LOCALE uniquement : le script s'arrête AVANT d'ouvrir un navigateur si
 *    l'adresse de l'ERP n'est pas localhost / 127.0.0.1 / [::1] / *.localhost ;
 *    chaque navigation est revérifiée (une redirection vers un autre hôte arrête tout) ;
 *  - la société affichée après connexion doit être la société de capture
 *    (`SOCIETE_CAPTURE`), sinon arrêt — jamais une vraie société ;
 *  - JAMAIS d'écran de veille (D-YBW-7) : une route qui en parle est refusée ;
 *  - le texte de la zone capturée est contrôlé AVANT écriture (aucun nom de
 *    l'entreprise d'installation, aucune devise, aucun prix d'achat ni marge,
 *    aucune veille) : une violation = aucun fichier écrit pour cet écran ;
 *  - captures 1440 et 390 px RECADRÉES sur le contenu (sélecteur de la zone
 *    utile, jamais le chrome de l'application), écrites en AVIF + WebP avec
 *    largeur/hauteur dans `src/assets/product/captures.json` ; le champ `revue`
 *    reste VIDE : la revue zoomée humaine y est consignée à la main, et le test
 *    refuse toute capture non revue.
 *
 * Identifiants : lus dans l'environnement SEULEMENT (jamais écrits sur disque ni
 * affichés). Aucune donnée n'est envoyée ailleurs que sur la pile locale.
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const RACINE_SITE = fileURLToPath(new URL('../', import.meta.url));
export const DOSSIER_SORTIE = join(RACINE_SITE, 'src/assets/product');
export const FICHIER_CAPTURES = join(DOSSIER_SORTIE, 'captures.json');

/** Nom exact de la société jetable de capture (D-YBW-10). */
export const SOCIETE_CAPTURE = 'YanBow — démo';

/** Largeurs de capture (bureau, mobile). */
export const LARGEURS = /** @type {const} */ ([1440, 390]);

/**
 * Écrans capturés. `route` peut contenir `{calepinage}` (identifiant lu dans
 * `CAPTURE_ID_CALEPINAGE`). `source: 'image'` = image fournie par l'opérateur
 * (la proposition PDF ne se rend pas dans un navigateur sans tête) : chemin dans
 * la variable `variable`, aucun contrôle de texte possible → revue zoomée seule.
 * Les identifiants DOIVENT être ceux de `src/data/productScreens.ts` (testé).
 *
 * @typedef {{ id: string, route?: string, selecteur?: string, source?: 'image', variable?: string }} Ecran
 * @type {readonly Ecran[]}
 */
export const ECRANS = [
  { id: 'crm-pipeline', route: '/crm/leads', selecteur: 'main' },
  { id: 'calepinage-3d', route: '/calepinage/{calepinage}', selecteur: 'main' },
  { id: 'packs-reglementaires', route: '/calepinage/{calepinage}?onglet=dossiers', selecteur: 'main' },
  { id: 'proposition-pdf', source: 'image', variable: 'CAPTURE_IMAGE_PROPOSITION' },
  { id: 'campagnes-en-pause', route: '/publicite/campagnes', selecteur: 'main' },
  { id: 'approbations', route: '/publicite/approbations', selecteur: 'main' },
  { id: 'garde-fous', route: '/publicite/regles', selecteur: 'main' },
];

const HOTES_LOCAUX = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);

/** `true` si l'URL désigne la machine locale (jamais la production). @param {string} url */
export function estHoteLocal(url) {
  let u;
  try {
    u = new URL(url);
  } catch {
    return false;
  }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
  const h = u.hostname.toLowerCase();
  return HOTES_LOCAUX.has(h) || h.endsWith('.localhost');
}

/** LÈVE si l'URL n'est pas locale. @param {string} url */
export function exigerHoteLocal(url) {
  if (!estHoteLocal(url)) {
    throw new Error(`refus : « ${url} » n'est pas une pile locale (localhost seulement, jamais la production)`);
  }
}

/** Veille / bibliothèque publicitaire : jamais montrée (D-YBW-7). */
const VEILLE = /veille|ad[\s_-]?library|biblioth[eè]que[\s_-]publicitaire/i;

/** LÈVE si la route mène à un écran de veille. @param {string} route */
export function exigerRouteSansVeille(route) {
  if (VEILLE.test(route)) throw new Error(`refus : écran de veille interdit (D-YBW-7) — ${route}`);
}

/** Contrôles du texte visible d'une zone capturée : `[nom, motif]`. */
export const INTERDITS_TEXTE = /** @type {const} */ ([
  ['entreprise d’installation nommée', /taqinor/i],
  ['devise', /€|\bEUR\b|\bMAD\b|\bDHS?\b|\bdirhams?\b/i],
  ['prix d’achat', /prix[\s_-]?d['’\s]?achat|prix_achat/i],
  ['marge', /\bmarges?\b/i],
  ['veille', VEILLE],
]);

/** Les noms des contrôles violés par `texte` (vide = conforme). @param {string} texte @returns {string[]} */
export function controlerTexte(texte) {
  return INTERDITS_TEXTE.filter(([, motif]) => motif.test(texte)).map(([nom]) => nom);
}

/**
 * Route concrète d'un écran (identifiants lus dans `env`) ; LÈVE si l'un manque.
 * @param {Ecran} ecran
 * @param {Record<string, string | undefined>} env
 */
export function routeDe(ecran, env) {
  if (!ecran.route) throw new Error(`écran sans route : ${ecran.id}`);
  const route = ecran.route.replace('{calepinage}', () => {
    const id = env.CAPTURE_ID_CALEPINAGE;
    if (!id || !/^\d+$/.test(id)) throw new Error(`CAPTURE_ID_CALEPINAGE requis (entier) pour ${ecran.id}`);
    return id;
  });
  exigerRouteSansVeille(route);
  return route;
}

/**
 * Lit le registre des captures (vide s'il n'existe pas).
 * @typedef {{ ecran: string, largeur: number, avif: string, webp: string, width: number | undefined, height: number | undefined, sha256_webp: string, capture_le: string, controle_texte: 'ok' | 'revue-seule', revue: string }} Entree
 * @returns {{ captures: Entree[] }}
 */
export function lireCaptures(fichier = FICHIER_CAPTURES) {
  if (!existsSync(fichier)) return { captures: [] };
  return JSON.parse(readFileSync(fichier, 'utf8'));
}

/**
 * Convertit un PNG en AVIF + WebP dans `dossier` et renvoie l'entrée du registre.
 * @param {Buffer} png
 * @param {string} ecranId
 * @param {number} largeur
 * @param {'ok' | 'revue-seule'} controle
 * @param {string} [dossier]
 * @returns {Promise<Entree>}
 */
export async function ecrireCapture(png, ecranId, largeur, controle, dossier = DOSSIER_SORTIE) {
  const sharp = (await import('sharp')).default;
  mkdirSync(dossier, { recursive: true });
  const base = `${ecranId}-${largeur}`;
  const avif = await sharp(png).avif({ quality: 55 }).toBuffer();
  const webp = await sharp(png).webp({ quality: 80 }).toBuffer();
  const meta = await sharp(webp).metadata();
  writeFileSync(join(dossier, `${base}.avif`), avif);
  writeFileSync(join(dossier, `${base}.webp`), webp);
  return {
    ecran: ecranId,
    largeur,
    avif: `${base}.avif`,
    webp: `${base}.webp`,
    width: meta.width,
    height: meta.height,
    sha256_webp: createHash('sha256').update(webp).digest('hex'),
    capture_le: new Date().toISOString().slice(0, 10),
    controle_texte: controle,
    revue: '',
  };
}

/**
 * Remplace (ou ajoute) les entrées et réécrit le registre.
 * @param {Entree[]} entrees
 */
export function enregistrer(entrees, fichier = FICHIER_CAPTURES) {
  const reg = lireCaptures(fichier);
  /** @param {Entree} e */
  const cle = (e) => `${e.ecran}@${e.largeur}`;
  const nouvelles = new Set(entrees.map(cle));
  reg.captures = [...reg.captures.filter((/** @type {Entree} */ e) => !nouvelles.has(cle(e))), ...entrees].sort((a, b) =>
    cle(a).localeCompare(cle(b)),
  );
  writeFileSync(fichier, `${JSON.stringify(reg, null, 2)}\n`);
}

/**
 * @param {string[]} argv
 * @param {Record<string, string | undefined>} env
 */
async function principal(argv, env) {
  const baseErp = env.CAPTURE_ERP_URL || 'http://localhost';
  exigerHoteLocal(baseErp);
  const voulus = argv.flatMap((/** @type {string} */ a, /** @type {number} */ i) => (a === '--ecran' ? [argv[i + 1]] : []));
  const ecrans = ECRANS.filter((e) => voulus.length === 0 || voulus.includes(e.id));
  for (const e of ecrans) if (e.route) routeDe(e, env); // erreurs de configuration AVANT le navigateur
  const identifiant = env.CAPTURE_IDENTIFIANT ?? '';
  const motDePasse = env.CAPTURE_MOT_DE_PASSE ?? '';
  if (ecrans.some((e) => e.route) && (!identifiant || !motDePasse)) {
    throw new Error('CAPTURE_IDENTIFIANT et CAPTURE_MOT_DE_PASSE requis (environnement seulement)');
  }

  const entrees = [];
  for (const e of ecrans.filter((x) => x.source === 'image')) {
    const chemin = e.variable ? env[e.variable] : undefined;
    if (!chemin) {
      console.warn(`ignoré : ${e.id} (variable ${e.variable} absente)`);
      continue;
    }
    const png = readFileSync(chemin);
    for (const largeur of LARGEURS) {
      const sharp = (await import('sharp')).default;
      const redim = await sharp(png).resize({ width: largeur, withoutEnlargement: true }).png().toBuffer();
      entrees.push(await ecrireCapture(redim, e.id, largeur, 'revue-seule'));
    }
  }

  const aNaviguer = ecrans.filter((x) => x.route);
  if (aNaviguer.length) {
    const { chromium } = await import('@playwright/test');
    const navigateur = await chromium.launch();
    try {
      for (const largeur of LARGEURS) {
        const contexte = await navigateur.newContext({ viewport: { width: largeur, height: 900 }, deviceScaleFactor: 1 });
        const page = await contexte.newPage();
        page.on('framenavigated', (f) => {
          if (f === page.mainFrame() && f.url() !== 'about:blank' && !estHoteLocal(f.url())) {
            console.error(`refus : navigation hors pile locale (${f.url()})`);
            process.exit(2);
          }
        });
        await page.goto(new URL('/login', baseErp).href);
        await page.getByPlaceholder('Entrez votre identifiant').fill(identifiant);
        await page.locator('input[type="password"]').fill(motDePasse);
        await page.getByRole('button', { name: /Se connecter/ }).click();
        await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 30_000 });
        await page.goto(new URL('/crm/leads', baseErp).href);
        await page.waitForLoadState('networkidle');
        const corps = await page.locator('body').innerText();
        if (!corps.includes(SOCIETE_CAPTURE)) {
          throw new Error(`refus : la société affichée n'est pas « ${SOCIETE_CAPTURE} » — jamais une vraie société`);
        }
        for (const e of aNaviguer) {
          await page.goto(new URL(routeDe(e, env), baseErp).href);
          await page.waitForLoadState('networkidle');
          const zone = page.locator(e.selecteur ?? 'main').first();
          await zone.waitFor({ state: 'visible', timeout: 30_000 });
          const violations = controlerTexte(await zone.innerText());
          if (violations.length) {
            console.error(`écran ${e.id} @${largeur} REFUSÉ (rien écrit) : ${violations.join(', ')}`);
            continue;
          }
          const png = await zone.screenshot({ type: 'png', animations: 'disabled' });
          entrees.push(await ecrireCapture(png, e.id, largeur, 'ok'));
          console.log(`capturé : ${e.id} @${largeur}`);
        }
        await contexte.close();
      }
    } finally {
      await navigateur.close();
    }
  }

  if (entrees.length) enregistrer(entrees);
  console.log(`${entrees.length} capture(s) écrite(s). Consigner la revue zoomée dans captures.json (champ « revue »).`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  principal(process.argv.slice(2), process.env).catch((err) => {
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  });
}
