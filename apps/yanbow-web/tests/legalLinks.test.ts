/**
 * YBW30 — liens juridiques : même langue que la page, jamais vers une route
 * juridique fermée (incomplète), lien Confidentialité seul pour le formulaire.
 */
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import LegalLinks from '../src/components/LegalLinks.astro';
import Mentions from '../src/pages/mentions-legales.astro';
import { routesJuridiquesCompletes } from '../src/lib/legal';
import { pagesRendues } from './builtHtml';
import { LEGAL_COMPLET } from './fixtures/legal-complet';

async function rendre(composant: Parameters<AstroContainer['renderToString']>[0], props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(await container.renderToString(composant, { props })).window.document;
}
const liens = (doc: Document) => [...doc.querySelectorAll('[data-liens-juridiques] a')].map((a) => `${a.textContent}=${a.getAttribute('href')}`);
const TOUTES = ['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy'];

describe('YBW30 — routes complètes (fixture)', () => {
  it('FR : les deux liens, en français, vers les routes FR', async () => {
    const doc = await rendre(LegalLinks, { locale: 'fr', completes: TOUTES });
    expect(liens(doc)).toEqual(['Mentions légales=/mentions-legales/', 'Confidentialité=/confidentialite/']);
    expect(doc.querySelector('nav')?.getAttribute('aria-label')).toBe('Informations légales');
  });

  it('EN : les deux liens, en anglais, vers les routes EN', async () => {
    const doc = await rendre(LegalLinks, { locale: 'en', completes: TOUTES });
    expect(liens(doc)).toEqual(['Legal notice=/en/legal/', 'Privacy=/en/privacy/']);
  });

  it('formulaire : seulement la Confidentialité', async () => {
    const doc = await rendre(LegalLinks, { locale: 'fr', pages: ['confidentialite'], completes: TOUTES });
    expect(liens(doc)).toEqual(['Confidentialité=/confidentialite/']);
  });

  it('une route fermée n’est jamais liée (confidentialité incomplète)', async () => {
    const doc = await rendre(LegalLinks, { locale: 'fr', completes: ['/mentions-legales', '/en/legal'] });
    expect(liens(doc)).toEqual(['Mentions légales=/mentions-legales/']);
  });

  it('la page Mentions légales complète porte les liens dans son pied de page', async () => {
    const doc = await rendre(Mentions, { locale: 'fr', legal: LEGAL_COMPLET });
    expect(liens(doc)).toEqual(['Mentions légales=/mentions-legales/']);
  });
});

describe('YBW30 — état réel (site fermé, pages juridiques incomplètes)', () => {
  it('aucun lien rendu', async () => {
    expect(routesJuridiquesCompletes()).toEqual([]);
    const doc = await rendre(LegalLinks, { locale: 'fr' });
    expect(doc.querySelector('[data-liens-juridiques]')).toBeNull();
  });

  for (const p of pagesRendues()) {
    it(`${p.url} : aucun lien vers une route juridique fermée`, () => {
      const hrefs = [...p.document.querySelectorAll('a[href]')].map((a) => (a.getAttribute('href') ?? '').replace(/\/+$/, ''));
      for (const route of TOUTES) {
        if (!routesJuridiquesCompletes().includes(route)) expect(hrefs).not.toContain(route);
      }
    });
  }
});
