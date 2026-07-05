// W67 — EN/AR ports of the équipement, regularization-article-33 and the four
// guides pages (index + 3 articles). Source-level guards: each new page imports
// the shared Layout, is INDEXABLE (no noindex), never writes the French word
// "témoignage", routes its internal links through localizeNavHref (anti-dead-
// link, never a raw /en or /ar prefix), and carries a distinctive translated
// phrase (English under /en/, Arabic under /ar/). The three guide ARTICLES keep
// their Article JSON-LD in both languages. The FR sources are NOT read here:
// they stay byte-for-byte unchanged and are covered by their own suites.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// The 12 new pages, with a distinctive phrase that must appear verbatim in the
// translated copy (proves the visible French was actually translated, not left
// in place). `article` marks the pages whose JSON-LD must be '@type': 'Article'.
type Page = { rel: string; locale: 'en' | 'ar'; phrase: string; article: boolean };

const PAGES: Page[] = [
  // équipement
  { rel: '../src/pages/en/équipement.astro', locale: 'en', phrase: 'fast enough to keep a computer running', article: false },
  { rel: '../src/pages/ar/équipement.astro', locale: 'ar', phrase: 'العتاد يتبع الحساب', article: false },
  // regularization-article-33
  { rel: '../src/pages/en/regularization-article-33.astro', locale: 'en', phrase: 'Regularize it now', article: false },
  { rel: '../src/pages/ar/regularization-article-33.astro', locale: 'ar', phrase: 'سوّها الآن', article: false },
  // guides hub
  { rel: '../src/pages/en/guides/index.astro', locale: 'en', phrase: 'Understand before you sign', article: false },
  { rel: '../src/pages/ar/guides/index.astro', locale: 'ar', phrase: 'افهم قبل أن توقّع', article: false },
  // guide — faut-il-des-batteries
  { rel: '../src/pages/en/guides/faut-il-des-batteries.astro', locale: 'en', phrase: 'Do you need batteries?', article: true },
  { rel: '../src/pages/ar/guides/faut-il-des-batteries.astro', locale: 'ar', phrase: 'هل تحتاج بطاريات؟', article: true },
  // guide — loi-82-21-expliquee
  { rel: '../src/pages/en/guides/loi-82-21-expliquee.astro', locale: 'en', phrase: 'Law 82-21 explained simply', article: true },
  { rel: '../src/pages/ar/guides/loi-82-21-expliquee.astro', locale: 'ar', phrase: 'القانون 82-21 ببساطة', article: true },
  // guide — onduleur-hybride-ou-reseau
  { rel: '../src/pages/en/guides/onduleur-hybride-ou-reseau.astro', locale: 'en', phrase: 'Hybrid inverter or grid-tied inverter?', article: true },
  { rel: '../src/pages/ar/guides/onduleur-hybride-ou-reseau.astro', locale: 'ar', phrase: 'عاكس هجين أم عاكس شبكة؟', article: true },
];

describe('W67 — EN/AR équipement, article-33 & guides : contrat de page', () => {
  it.each(PAGES.map((p) => p.rel))('%s : importe le Layout partagé', (rel) => {
    const src = read(rel);
    expect(src).toMatch(/import\s+Layout\s+from\s+['"][^'"]*layouts\/Layout\.astro['"]/);
  });

  it.each(PAGES.map((p) => p.rel))('%s : INDEXABLE (aucun noindex)', (rel) => {
    expect(read(rel)).not.toContain('noindex');
  });

  it.each(PAGES.map((p) => p.rel))("%s : ne contient jamais le mot français « témoignage »", (rel) => {
    expect(read(rel).toLowerCase()).not.toContain('témoignage');
  });

  it.each(PAGES.map((p) => p.rel))('%s : route ses liens internes via localizeNavHref', (rel) => {
    const src = read(rel);
    // L'aide est importée ET appelée (jamais de préfixe /en /ar codé en dur).
    expect(src).toContain('localizeNavHref');
    expect(src).toMatch(/const\s+L\s*=\s*\(href[^)]*\)\s*=>\s*localizeNavHref/);
  });

  it.each(PAGES.map((p) => p.rel))('%s : pose un titre + une description traduits sur le Layout', (rel) => {
    const src = read(rel);
    expect(src).toMatch(/title=/);
    const m = src.match(/description="([^"]+)"/);
    expect(m, 'description Layout absente').toBeTruthy();
    expect((m![1] ?? '').length).toBeGreaterThan(10);
  });

  it.each(PAGES.map((p) => [p.rel, p.phrase] as const))(
    '%s : contient sa phrase traduite distinctive',
    (rel, phrase) => {
      expect(read(rel)).toContain(phrase);
    },
  );

  it.each(PAGES.filter((p) => p.locale === 'ar').map((p) => p.rel))(
    "%s : aucun attribut dir/lang codé en dur (le Layout pose lang=ar + dir=rtl)",
    (rel) => {
      const src = read(rel);
      // WC12 (2026-07-05) : `dir="ltr"` sur des tokens numériques latins (isolation
      // bidi, pour que les nombres ne s'affichent pas à l'envers en arabe) est
      // LÉGITIME ; on interdit seulement un dir="rtl" codé en dur au niveau page
      // (le Layout pose déjà dir=rtl sur <html>).
      expect(src).not.toMatch(/\sdir="rtl"/);
      // On ne réécrit pas non plus le <html lang> : c'est le Layout qui le gère.
      expect(src).not.toContain('lang="ar"');
    },
  );
});

describe('W67 — les 3 guides rédactionnels gardent leur JSON-LD Article (EN + AR)', () => {
  it.each(PAGES.filter((p) => p.article).map((p) => p.rel))(
    "%s : émet un bloc '@type': 'Article'",
    (rel) => {
      expect(read(rel)).toContain("'@type': 'Article'");
    },
  );

  it('exactement 6 fichiers Article (EN+AR des 3 guides)', () => {
    expect(PAGES.filter((p) => p.article)).toHaveLength(6);
  });
});
