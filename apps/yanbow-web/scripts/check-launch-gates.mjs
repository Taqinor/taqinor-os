#!/usr/bin/env node
/**
 * YBW85 — contrôle de lancement automatique.
 *
 * Lit `docs/LAUNCH_GATES.md` et échoue (code 1) tant qu'une porte reste
 * ouverte. Une ligne en français clair par porte ouverte. Portes contrôlées :
 *  - chaque porte manuelle `- [ ] ID — …` du fichier (YBWM) non cochée ;
 *  - un champ requis de `src/lib/legal.ts` est `null` : tout le bloc éditeur
 *    YanBow Ltd + directeur de la publication + e-mail ; le bloc SARLAU complet
 *    dès qu'une page la cite (= elle est désignée responsable du traitement, ou
 *    un de ses champs est déjà renseigné) ;
 *  - `check-claims --stale` n'est pas vide (ou le registre est en erreur) ;
 *  - une page juridique (Mentions légales, Confidentialité, FR et EN) n'est
 *    pas routable (`routesJuridiquesCompletes`) ;
 *  - le domaine canonique n'est pas posé (`src/lib/site.ts`).
 *
 *   node scripts/check-launch-gates.mjs
 */
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import { RACINE_SITE, executer } from './check-claims.mjs';

const FICHIER_PORTES = join(RACINE_SITE, 'docs/LAUNCH_GATES.md');
const ROUTES_JURIDIQUES = ['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy'];

/**
 * Lit les portes manuelles : lignes `- [ ] ID — description` / `- [x] …`.
 * @param {string} markdown
 * @returns {{ id: string, coche: boolean, description: string }[]}
 */
export function lirePortes(markdown) {
  const portes = [];
  for (const ligne of markdown.split(/\r?\n/)) {
    const m = /^- \[( |x|X)\] ([A-Z0-9-]+) — (.*)$/.exec(ligne);
    if (m) portes.push({ id: m[2], coche: m[1] !== ' ', description: m[3].trim() });
  }
  return portes;
}

const plein = (/** @type {unknown} */ v) => typeof v === 'string' && v.trim() !== '';

/**
 * Champs requis non renseignés de legal.ts (noms lisibles).
 * @param {any} legal
 * @returns {string[]}
 */
export function champsLegauxManquants(legal) {
  const manquants = [];
  const e = legal.editeur;
  for (const [cle, nom] of [
    ['nomExact', 'nom exact'],
    ['partie', 'partie du Royaume-Uni'],
    ['numero', "numéro d'immatriculation"],
    ['siege', 'siège'],
  ]) {
    if (!plein(e[cle])) manquants.push(`éditeur YanBow Ltd : ${nom}`);
  }
  if (!plein(legal.commun.directeurPublication)) manquants.push('directeur de la publication');
  if (!plein(legal.commun.email)) manquants.push('e-mail de contact');
  const m = legal.maroc;
  const cite = legal.commun.responsableTraitement === 'maroc' || Object.values(m).some((v) => v !== null);
  if (cite) {
    for (const [cle, nom] of [
      ['denomination', 'dénomination'],
      ['capital', 'capital'],
      ['siege', 'siège'],
      ['rc', 'RC'],
      ['ice', 'ICE'],
      ['identifiantFiscal', 'identifiant fiscal'],
      ['gerant', 'gérant'],
    ]) {
      if (!plein(m[cle])) manquants.push(`SARLAU marocaine : ${nom}`);
    }
  }
  return manquants;
}

/**
 * Évalue toutes les portes ; retourne une ligne française par porte ouverte.
 * @param {{ portes: { id: string, coche: boolean, description: string }[], legal: any, routesCompletes: string[],
 *   origine: string | null, perimees: string[], erreursClaims: string[] }} etat
 * @returns {string[]}
 */
export function portesOuvertes(etat) {
  const lignes = [];
  for (const nom of champsLegauxManquants(etat.legal)) lignes.push(`Champ légal manquant (legal.ts) : ${nom}.`);
  for (const route of ROUTES_JURIDIQUES) {
    if (!etat.routesCompletes.includes(route)) lignes.push(`Page juridique non routable : ${route}.`);
  }
  if (!etat.origine) lignes.push('Domaine canonique non posé (src/lib/site.ts, ORIGINE_CANONIQUE).');
  for (const p of etat.perimees) lignes.push(`Affirmation périmée (check-claims --stale) : ${p}.`);
  for (const e of etat.erreursClaims) lignes.push(`Registre des affirmations en erreur : ${e}.`);
  for (const p of etat.portes) {
    if (!p.coche) lignes.push(`Porte manuelle ${p.id} non cochée : ${p.description}`);
  }
  return lignes;
}

/**
 * Importe legal.ts, brand.ts et site.ts (TypeScript) en les transpilant dans un
 * dossier temporaire — sans dépendance de plus.
 */
async function chargerModules() {
  const dossier = mkdtempSync(join(tmpdir(), 'yanbow-gates-'));
  /** @param {string} nom */
  const transpiler = (nom) => {
    const src = readFileSync(join(RACINE_SITE, 'src/lib', `${nom}.ts`), 'utf-8');
    const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
    writeFileSync(join(dossier, `${nom}.mjs`), js.replace(/from ['"]\.\/(\w+)['"]/g, "from './$1.mjs'"));
  };
  for (const nom of ['brand', 'legal', 'site']) transpiler(nom);
  const legal = await import(pathToFileURL(join(dossier, 'legal.mjs')).href);
  const site = await import(pathToFileURL(join(dossier, 'site.mjs')).href);
  return { legal, site };
}

export async function etatReel() {
  const { legal, site } = await chargerModules();
  const { erreurs, perimees } = await executer({ stale: true });
  return {
    portes: lirePortes(readFileSync(FICHIER_PORTES, 'utf-8')),
    legal: legal.LEGAL,
    routesCompletes: legal.routesJuridiquesCompletes(),
    origine: site.ORIGINE_CANONIQUE,
    perimees,
    erreursClaims: erreurs,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  etatReel().then((etat) => {
    const lignes = portesOuvertes(etat);
    for (const l of lignes) console.log(`PORTE OUVERTE  ${l}`);
    console.log(lignes.length ? `[check-launch-gates] ${lignes.length} porte(s) ouverte(s) — ne pas ouvrir le site` : '[check-launch-gates] OK — toutes les portes sont franchies');
    process.exit(lignes.length ? 1 : 0);
  });
}

