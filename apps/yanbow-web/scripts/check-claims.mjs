#!/usr/bin/env node
/**
 * YBW18 — garde du registre des affirmations et des faits.
 *
 * Échoue si :
 *  - une preuve `chemin:ligne` citée n'existe pas (fichier absent ou trop court) ;
 *  - une affirmation non publiable n'a pas de raison, ou un identifiant est dupliqué ;
 *  - un dictionnaire (src/i18n/**) ou le code du site cite (`cite('ID')`) une
 *    affirmation inconnue ou non publiable ;
 *  - un chiffre avec unité apparaît dans un dictionnaire ou dans le texte d'une
 *    affirmation (sa place est `src/lib/facts.ts`).
 * `--stale` liste en plus les affirmations dont un fichier de preuve a changé
 * depuis `verifie_a_sha` (bloque le lancement, YBW85).
 *
 * Exécuté par `npm test` (tests/claims.test.ts) et en ligne de commande :
 *   node scripts/check-claims.mjs [--stale]
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

export const RACINE_SITE = fileURLToPath(new URL('../', import.meta.url));
export const RACINE_DEPOT = fileURLToPath(new URL('../../../', import.meta.url));

/** Nombre suivi d'une unité (monnaie, énergie, durée, quantité commerciale…). */
export const CHIFFRE_AVEC_UNITE =
  /\b\d+(?:[.,]\d+)?\s?(?:%|kWc|kWh|kW|MWh|€|MAD|DH|ans?|ann[ée]es?|years?|mois|months?|jours?|days?|heures?|hours?|h|min|minutes?|s|m²|m2|km|Mo|Go|clients?|installations?)(?![\p{L}\d])/u;

/**
 * Importe un module TypeScript du site sans dépendance de plus (transpilation
 * par `typescript`, import d'une data-URL). Réservé aux modules SANS import de
 * valeur (claims.ts, facts.ts).
 * @param {string} chemin
 */
export async function importerTs(chemin) {
  const js = ts.transpileModule(readFileSync(chemin, 'utf-8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
}

/**
 * @typedef {{ id: string, texte_fr: string, texte_en?: string, publiable: boolean,
 *   raison_non_publiable?: string, preuves: string[], verifie_a_sha: string }} Affirmation
 */

/**
 * @param {Affirmation[]} affirmations
 * @param {string} racineDepot
 * @returns {string[]}
 */
export function verifierRegistre(affirmations, racineDepot) {
  const erreurs = [];
  const vus = new Set();
  for (const a of affirmations) {
    if (vus.has(a.id)) erreurs.push(`${a.id} : identifiant dupliqué`);
    vus.add(a.id);
    if (!a.publiable && !a.raison_non_publiable) erreurs.push(`${a.id} : non publiable sans raison`);
    if (!/^[0-9a-f]{40}$/.test(a.verifie_a_sha)) erreurs.push(`${a.id} : verifie_a_sha invalide (${a.verifie_a_sha})`);
    if (!a.preuves.length) erreurs.push(`${a.id} : aucune preuve`);
    for (const p of a.preuves) {
      const m = /^(.+):(\d+)$/.exec(p);
      if (!m) {
        erreurs.push(`${a.id} : preuve mal formée « ${p} » (attendu chemin:ligne)`);
        continue;
      }
      const fichier = join(racineDepot, m[1]);
      if (!existsSync(fichier)) {
        erreurs.push(`${a.id} : preuve introuvable ${m[1]}`);
        continue;
      }
      const lignes = readFileSync(fichier, 'utf-8').split('\n').length;
      if (Number(m[2]) < 1 || Number(m[2]) > lignes) erreurs.push(`${a.id} : ${m[1]} n'a pas de ligne ${m[2]} (${lignes} lignes)`);
    }
    for (const texte of [a.texte_fr, a.texte_en ?? '']) {
      const hit = texte.match(CHIFFRE_AVEC_UNITE);
      if (hit) erreurs.push(`${a.id} : chiffre avec unité « ${hit[0]} » dans le texte (le mettre dans facts.ts)`);
    }
  }
  return erreurs;
}

/**
 * Retire les commentaires d'un source TS/Astro (les chiffres d'un commentaire ne sont pas publics).
 * @param {string} source
 */
function sansCommentaires(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
}

/**
 * @param {{ fichier: string, contenu: string }[]} sources
 * @param {Affirmation[]} affirmations
 * @returns {string[]}
 */
export function verifierCitations(sources, affirmations) {
  const parId = new Map(affirmations.map((a) => [a.id, a]));
  const erreurs = [];
  for (const { fichier, contenu } of sources) {
    for (const m of sansCommentaires(contenu).matchAll(/\bcite\(\s*['"]([^'"]+)['"]/g)) {
      const a = parId.get(m[1]);
      if (!a) erreurs.push(`${fichier} : cite une affirmation inconnue « ${m[1]} »`);
      else if (!a.publiable) erreurs.push(`${fichier} : cite une affirmation NON publiable « ${m[1]} » (${a.raison_non_publiable})`);
    }
  }
  return erreurs;
}

/**
 * @param {{ fichier: string, contenu: string }[]} dictionnaires
 * @returns {string[]}
 */
export function verifierChiffres(dictionnaires) {
  const erreurs = [];
  for (const { fichier, contenu } of dictionnaires) {
    if (/(^|\/)facts\.ts$/.test(fichier)) continue;
    const hit = sansCommentaires(contenu).match(CHIFFRE_AVEC_UNITE);
    if (hit) erreurs.push(`${fichier} : chiffre avec unité « ${hit[0]} » hors src/lib/facts.ts`);
  }
  return erreurs;
}

/**
 * Affirmations dont un fichier de preuve a changé depuis `verifie_a_sha`.
 * @param {Affirmation[]} affirmations
 * @param {(sha: string, fichier: string) => boolean} aChange
 * @returns {string[]}
 */
export function affirmationsPerimees(affirmations, aChange) {
  const out = [];
  for (const a of affirmations) {
    const fichiers = [...new Set(a.preuves.map((p) => p.replace(/:\d+$/, '')))];
    const changes = fichiers.filter((f) => aChange(a.verifie_a_sha, f));
    if (changes.length) out.push(`${a.id} : preuve modifiée depuis ${a.verifie_a_sha.slice(0, 9)} → ${changes.join(', ')}`);
  }
  return out;
}

/**
 * Différence git entre `sha` et l'arbre de travail pour `fichier` (vrai = changé).
 * @param {string} racineDepot
 * @returns {(sha: string, fichier: string) => boolean}
 */
export function gitAChange(racineDepot) {
  return (sha, fichier) => {
    try {
      execFileSync('git', ['diff', '--quiet', sha, '--', fichier], { cwd: racineDepot, stdio: 'ignore' });
      return false;
    } catch {
      return true; // différence, ou sha inconnu : à relire dans les deux cas
    }
  };
}

/**
 * @param {string} dir
 * @param {string[]} extensions
 * @returns {string[]}
 */
function lister(dir, extensions) {
  /** @type {string[]} */
  const out = [];
  if (!existsSync(dir)) return out;
  for (const nom of readdirSync(dir)) {
    const p = join(dir, nom);
    if (statSync(p).isDirectory()) out.push(...lister(p, extensions));
    else if (extensions.some((e) => nom.endsWith(e))) out.push(p);
  }
  return out;
}

/** @param {string} chemin */
const lire = (chemin) => ({ fichier: relative(RACINE_SITE, chemin).split(sep).join('/'), contenu: readFileSync(chemin, 'utf-8') });

/**
 * Exécute toute la garde sur le dépôt réel.
 * @param {{ stale?: boolean }} [options]
 * @returns {Promise<{ erreurs: string[], perimees: string[] }>}
 */
export async function executer(options = {}) {
  const { AFFIRMATIONS } = await importerTs(join(RACINE_SITE, 'src/lib/claims.ts'));
  const code = lister(join(RACINE_SITE, 'src'), ['.ts', '.astro', '.mjs']).filter((/** @type {string} */ f) => !f.endsWith(join('lib', 'claims.ts')));
  const dictionnaires = lister(join(RACINE_SITE, 'src/i18n'), ['.ts']);
  const erreurs = [
    ...verifierRegistre(AFFIRMATIONS, RACINE_DEPOT),
    ...verifierCitations(code.map(lire), AFFIRMATIONS),
    ...verifierChiffres(dictionnaires.map(lire)),
  ];
  const perimees = options.stale ? affirmationsPerimees(AFFIRMATIONS, gitAChange(RACINE_DEPOT)) : [];
  return { erreurs, perimees };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const stale = process.argv.includes('--stale');
  executer({ stale }).then(({ erreurs, perimees }) => {
    for (const e of erreurs) console.log(`ERREUR  ${e}`);
    for (const p of perimees) console.log(`PÉRIMÉE ${p}`);
    const ko = erreurs.length + perimees.length;
    console.log(ko ? `[check-claims] ${erreurs.length} erreur(s), ${perimees.length} affirmation(s) périmée(s)` : '[check-claims] OK');
    process.exit(ko ? 1 : 0);
  });
}
