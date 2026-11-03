// WAUD85 — `<lastmod>` du sitemap depuis les VRAIES dates du dépôt : date de revue des
// guides, date de l'article (updatedDate, sinon pubDate), date de relevé de la flotte.
// Les dates de commit git (T2_seo_site, 10/10) ne marchaient jamais en production : Workers
// Builds fait un clone superficiel → 0/190 URL datées. Une page sans date réelle n'a AUCUN
// lastmod : un sitemap sans date vaut mieux qu'un sitemap qui ment.
//
// Lecture du TEXTE des sources : astro.config.mjs ne charge pas de TypeScript.
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const LOCALES = ['', '/en', '/ar'];
const JOUR = /^\d{4}-\d{2}-\d{2}$/;

/** { slug: 'AAAA-MM-JJ' } depuis le texte de GUIDE_VERIFIED_DATES. */
export function datesGuides(texteGuideMeta) {
  const debut = texteGuideMeta.indexOf('GUIDE_VERIFIED_DATES');
  const bloc = texteGuideMeta.slice(debut, texteGuideMeta.indexOf('};', debut));
  return Object.fromEntries(
    [...bloc.matchAll(/'([^']+)':\s*new Date\('(\d{4}-\d{2}-\d{2})'\)/g)].map((m) => [m[1], m[2]]),
  );
}

/** Date d'un article depuis son en-tête ; null si brouillon ou sans date. */
export function dateArticle(texte) {
  const entete = texte.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? '';
  if (/^draft:\s*true/m.test(entete)) return null;
  const lire = (cle) => entete.match(new RegExp(`^${cle}:\\s*["']?(\\d{4}-\\d{2}-\\d{2})`, 'm'))?.[1] ?? null;
  return lire('updatedDate') ?? lire('pubDate');
}

/** Dernière date de relevé (texte de realisations.ts, bloc MEASURED_FLEET). */
export function dateReleveFlotte(texteRealisations) {
  const debut = texteRealisations.indexOf('export const MEASURED_FLEET');
  const bloc = texteRealisations.slice(debut, texteRealisations.indexOf('];', debut));
  return [...bloc.matchAll(/readAt:\s*'(\d{4}-\d{2}-\d{2})'/g)].map((m) => m[1]).sort().pop() ?? null;
}

/** Table chemin canonique (sans barre finale, décodé) → date, pour les 3 locales. */
export function tableDates({ guides, articles, releve }) {
  const table = new Map();
  const poser = (chemin, jour) => {
    if (!jour || !JOUR.test(jour)) return;
    for (const l of LOCALES) table.set(`${l}${chemin}`, jour);
  };
  for (const [slug, jour] of Object.entries(guides)) poser(`/guides/${slug}`, jour);
  for (const [slug, jour] of Object.entries(articles)) poser(`/blog/${slug}`, jour);
  poser('/production-mesuree', releve);
  return table;
}

/** Lit les sources réelles à partir de la racine d'apps/web. */
export function datesDuDepot(racine = fileURLToPath(new URL('..', import.meta.url))) {
  const lire = (rel) => readFileSync(join(racine, rel), 'utf-8');
  const dossier = 'src/content/blog';
  const articles = Object.fromEntries(
    readdirSync(join(racine, dossier))
      .filter((f) => f.endsWith('.md'))
      .map((f) => [f.replace(/\.md$/, ''), dateArticle(lire(`${dossier}/${f}`))]),
  );
  return tableDates({
    guides: datesGuides(lire('src/lib/guideMeta.ts')),
    articles,
    releve: dateReleveFlotte(lire('src/lib/realisations.ts')),
  });
}

/** Date d'une URL du sitemap, ou undefined. */
export function lastmodPour(table, urlTexte) {
  let chemin;
  try {
    chemin = decodeURI(new URL(urlTexte).pathname);
  } catch {
    return undefined;
  }
  return table.get(chemin.replace(/\/+$/, '') || '/');
}
