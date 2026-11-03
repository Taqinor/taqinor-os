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
import { dateComparable, derniereRealisation, REALISATIONS } from '../src/lib/realisations';

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

describe('WAUD15 — règle B : jamais un compte de chantiers dérivé, dernière livrée = la plus récente', () => {
  const pages = ['index.astro', 'en/index.astro', 'ar/index.astro'].map((p) => read(join(pagesDir, p)));
  it('aucune dérivation de comptage rendue comme chiffre', () => {
    for (const code of pages) {
      expect(code).not.toMatch(/new Set\(REALISATIONS\.map\(\(r\) => r\.ville\)\)\.size/);
      expect(code).not.toMatch(/ChantiersVisitablesCount|chantiersVisitablesCount|visitableSitesCount/);
      expect(code).not.toMatch(/battersInstalls\.length/);
    }
  });
  it('« Dernière installation livrée » = max(date)', () => {
    const d = derniereRealisation();
    for (const r of REALISATIONS) expect(dateComparable(r.date)).toBeLessThanOrEqual(dateComparable(d.date));
    expect(dateComparable('juillet 2026')).toBeGreaterThan(dateComparable('avril 2026'));
    expect(dateComparable('inconnue')).toBe(-1);
  });
});

describe('WAUD18 — loi 82-21 : ni montant d’amende, ni menace, ni « à confirmer »', () => {
  const FICHIERS = [
    'pages/regularization-article-33.astro', 'pages/en/regularization-article-33.astro', 'pages/ar/regularization-article-33.astro',
    'pages/faq.astro', 'pages/en/faq.astro', 'pages/ar/faq.astro',
    'pages/guides/loi-82-21-expliquee.astro', 'pages/en/guides/loi-82-21-expliquee.astro', 'pages/ar/guides/loi-82-21-expliquee.astro',
    'pages/loi-82-21.astro', 'pages/en/loi-82-21.astro', 'pages/ar/loi-82-21.astro',
    'content/blog/loi-82-21-autoproduction-2026.md',
  ];
  const LIRE = (f: string) => {
    const s = readFileSync(fileURLToPath(new URL(`../src/${f}`, import.meta.url)), 'utf-8');
    return s.replace(/\/\*[\s\S]*?\*\//g, ''); // en-têtes de fichier hors rendu
  };
  it.each(FICHIERS)('%s', (f) => {
    const s = LIRE(f);
    expect(s).not.toMatch(/1[ .,\u00a0]000[ .,\u00a0]000/);
    expect(s).not.toMatch(/d[ée]cembre 2027|December 2027/i);
    // « point de départ à confirmer » reste sur /regularization et le guide : chaîne épinglée par
    // article33CIW413 et loi8221TarifCIW412 jusqu'à D-WAUD-4 (WAUD18-b) ; partout ailleurs, retirée.
    if (!/regularization-article-33|guides\/loi-82-21/.test(f)) expect(s).not.toMatch(/à confirmer|to be confirmed|يجب تأكيدها/);
    expect(s).not.toMatch(/d[ée]connexion|disconnection|فصلها عن الشبكة/i);
    // Garde : « MAD » ou « DH » accolé à une amende ou sanction.
    expect(s).not.toMatch(/(amende|sanction|fine|penalt|غرام|عقوب)[^.\n]{0,80}\b(MAD|DH|درهم)\b/i);
    expect(s).not.toMatch(/\b(MAD|DH)\b[^.\n]{0,40}(amende|sanction|fine|penalt)/i);
  });
});
