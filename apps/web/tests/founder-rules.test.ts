// Garde-fou des RÈGLES FONDATEUR A & B (WA6) :
//  A — aucune page d'accueil (toutes locales) n'importe ni ne rend FounderPortrait
//      (le portrait / la signature du fondateur ne vivent que sur /à-propos).
//  B — aucune copie visible ne met en avant le NOMBRE BRUT d'installations
//      (REALISATIONS.length / installCount étiqueté « installations / chantiers /
//      réalisations » comme statistique vedette). On mène par kWc / kWh mesurés / CO₂.
// Ces deux règles ont déjà été violées par des tâches bien intentionnées
// (W266 / W279 / W284) ; ce garde-fou empêche la prochaine passe de les réintroduire.
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const pagesDir = fileURLToPath(new URL('../src/pages', import.meta.url));
const read = (abs: string) => readFileSync(abs, 'utf-8');

function walkAstro(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walkAstro(p));
    else if (e.name.endsWith('.astro')) out.push(p);
  }
  return out;
}

describe('RÈGLE A — pas de portrait/signature fondateur sur l’accueil', () => {
  for (const rel of ['index.astro', 'en/index.astro', 'ar/index.astro']) {
    it(`${rel} n’importe ni ne rend FounderPortrait`, () => {
      const src = read(fileURLToPath(new URL(`../src/pages/${rel}`, import.meta.url)));
      expect(src).not.toMatch(/FounderPortrait/);
    });
  }
});

describe('RÈGLE B — le nombre brut d’installations n’est pas une stat vedette', () => {
  // Allowlist : les pages /realisations affichent « X chantiers / projects / أوراش »
  // comme DÉNOMINATEUR DE LA GALERIE juste en dessous (contexte de liste, pas une
  // statistique marketing vedette) — usage intentionnel autorisé (cf. correction WA6).
  const ALLOW = new Set([
    'realisations/index.astro',
    'en/realisations/index.astro',
    'ar/realisations/index.astro',
  ]);
  const LABEL = /(installation|chantier|réalisation|projet|project|تركيب|ورش|أوراش)/i;

  const files = walkAstro(pagesDir);

  it('couvre l’ensemble des pages .astro', () => {
    expect(files.length).toBeGreaterThan(50);
  });

  for (const abs of files) {
    const rel = abs.slice(pagesDir.length + 1).replace(/\\/g, '/');
    if (ALLOW.has(rel)) continue;
    it(`${rel} ne met pas en avant un décompte brut d’installations`, () => {
      const offenders = read(abs)
        .split('\n')
        .filter((ln) => {
          const t = ln.trim();
          // ignore les commentaires (JSDoc / ligne / bloc) — non rendus
          if (t.startsWith('*') || t.startsWith('//') || t.startsWith('/*')) return false;
          return /REALISATIONS\.length|installCount/.test(ln) && LABEL.test(ln);
        })
        .map((ln) => ln.trim());
      expect(
        offenders,
        `stat brute d’installations détectée dans ${rel} :\n${offenders.join('\n')}`,
      ).toEqual([]);
    });
  }
});
