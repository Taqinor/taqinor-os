import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import ts from 'typescript';
import { beforeAll, describe, expect, it } from 'vitest';
import Sonde from '../src/pages/_bonjour.astro';
import { LOCALES_ACTIVES } from '../src/i18n/config';
import { PAGES, toutesLesUrl } from '../src/i18n/pages';
import { alternates, L, t } from '../src/i18n/utils';

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(await container.renderToString(Sonde, { props })).window.document;
}
const hreflangs = (doc: Document) =>
  [...doc.querySelectorAll('link[rel="alternate"][hreflang]')].map((l) => `${l.getAttribute('hreflang')}=${l.getAttribute('href')}`);

describe('YBW13 — fixture LOCALES_ACTIVES = [fr, en] : sonde rendue', () => {
  it('FR : lang, hreflang fr/en/x-default, sélecteur vers /en/', async () => {
    const doc = await rendre({ locale: 'fr', locales: ['fr', 'en'] });
    expect(doc.documentElement.getAttribute('lang')).toBe('fr');
    expect(hreflangs(doc)).toEqual(['fr=/bonjour/', 'en=/en/bonjour/', 'x-default=/bonjour/']);
    const sel = [...doc.querySelectorAll('nav a')].map((a) => a.getAttribute('href'));
    expect(sel).toEqual(['/en/bonjour/']);
    expect(doc.querySelector('h1')?.textContent).toBe('Bonjour');
  });

  it('EN : lang, mêmes hreflang, sélecteur vers la page FR équivalente', async () => {
    const doc = await rendre({ locale: 'en', locales: ['fr', 'en'] });
    expect(doc.documentElement.getAttribute('lang')).toBe('en');
    expect(hreflangs(doc)).toEqual(['fr=/bonjour/', 'en=/en/bonjour/', 'x-default=/bonjour/']);
    expect([...doc.querySelectorAll('nav a')].map((a) => a.getAttribute('href'))).toEqual(['/bonjour/']);
    expect(doc.querySelector('h1')?.textContent).toBe('Hello');
  });
});

describe('YBW13 — état réel LOCALES_ACTIVES = [fr]', () => {
  it("l'anglais est inactif", () => {
    expect([...LOCALES_ACTIVES]).toEqual(['fr']);
  });

  it('aucun lien hreflang ni sélecteur vers /en/', async () => {
    const doc = await rendre({ locale: 'fr' });
    expect(hreflangs(doc)).toEqual([]);
    expect(doc.querySelector('a[href^="/en/"]')).toBeNull();
    expect(doc.documentElement.outerHTML).not.toContain('/en/');
  });

  it('build : aucune route /en/ publiée et la sonde FR ne lie pas /en/', () => {
    const client = fileURLToPath(new URL('../dist/client/', import.meta.url));
    if (!existsSync(client)) throw new Error('dist/ absent — lancer `npm run build` avant `npm test`');
    expect(existsSync(client + 'en')).toBe(false);
    const html = readFileSync(client + 'bonjour/index.html', 'utf-8');
    expect(html).not.toContain('/en/');
  });
});

describe('YBW13 — registre des pages', () => {
  it('liste les 16 URL du plan de site, uniques', () => {
    const urls = toutesLesUrl();
    expect(urls).toHaveLength(16);
    expect(new Set(urls).size).toBe(16);
    expect(urls).toEqual(
      expect.arrayContaining([
        '/', '/solarbow/', '/marketingbow/', '/sur-mesure/', '/societe/', '/rendez-vous/', '/confidentialite/', '/mentions-legales/',
        '/en/', '/en/solarbow/', '/en/marketingbow/', '/en/custom-software/', '/en/company/', '/en/book-a-meeting/', '/en/privacy/', '/en/legal/',
      ]),
    );
    for (const u of urls) expect(u).toMatch(/^[a-z0-9/-]+$/);
  });

  it('L() et alternates() suivent le registre', () => {
    expect(L('surMesure', 'en')).toBe('/en/custom-software/');
    expect(alternates(PAGES.societe, ['fr', 'en'])).toEqual([
      { hreflang: 'fr', href: '/societe/' },
      { hreflang: 'en', href: '/en/company/' },
      { hreflang: 'x-default', href: '/societe/' },
    ]);
    expect(alternates(PAGES.societe, ['fr'])).toEqual([]);
  });
});

describe('YBW13 — t() sans repli', () => {
  const dict = { a: { b: 'ok' }, vide: '' };
  it('lit une clé pointée', () => expect(t(dict, 'a.b')).toBe('ok'));
  it('lève sur une clé absente (jamais de retombée sur le FR ni sur la clé)', () => {
    expect(() => t(dict, 'a.c', 'en')).toThrow(/a\.c/);
  });
  it('lève sur une chaîne vide', () => expect(() => t(dict, 'vide')).toThrow());
});

describe('YBW13 — une clé EN manquante = erreur de type (npm run check)', () => {
  const FIXTURES = ['i18n-en-manquante.ts', 'i18n-en-complete.ts', 'i18n-en-inactive.ts'];
  const chemin = (f: string) => fileURLToPath(new URL(`./fixtures/${f}`, import.meta.url));
  let programme: ts.Program;
  // Un seul programme TypeScript pour les trois fixtures (le chargement des lib est lent).
  beforeAll(() => {
    programme = ts.createProgram(FIXTURES.map(chemin), {
      strict: true,
      noEmit: true,
      skipLibCheck: true,
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      target: ts.ScriptTarget.ES2022,
    });
  }, 60_000);
  function diagnostics(fichier: string): string[] {
    const source = programme.getSourceFile(chemin(fichier));
    return ts.getPreEmitDiagnostics(programme, source).map((d) => ts.flattenDiagnosticMessageText(d.messageText, ' '));
  }

  it('cas négatif : anglais actif, clé manquante → erreur', () => {
    const d = diagnostics('i18n-en-manquante.ts');
    expect(d.join('\n')).toMatch(/texte/);
  });
  it('anglais actif, dictionnaire complet → aucune erreur', () => {
    expect(diagnostics('i18n-en-complete.ts')).toEqual([]);
  });
  it('anglais inactif → squelette vide accepté', () => {
    expect(diagnostics('i18n-en-inactive.ts')).toEqual([]);
  });
});

describe('YBW13 — routes anglaises = enveloppes minces (aucun corps dupliqué)', () => {
  it('chaque src/pages/en/*.astro importe un gabarit et ne porte ni <html> ni <main>', () => {
    const dir = new URL('../src/pages/en/', import.meta.url);
    for (const f of readdirSync(dir).filter((x) => x.endsWith('.astro'))) {
      const src = readFileSync(new URL(f, dir), 'utf-8');
      expect(src, f).toMatch(/^import \w+ from '\.\.\//m);
      expect(src, f).not.toMatch(/<html|<main|<body/);
    }
  });
});
