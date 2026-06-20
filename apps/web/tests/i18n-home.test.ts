// W67 — Gardes des PORTS EN/AR de la page d'accueil. Vérifie (sur le SOURCE,
// sans navigateur) que chaque port : importe le Layout partagé, localise TOUS
// ses liens internes via localizeNavHref (jamais de lien mort), réutilise le
// MÊME composant <Faq> que le FR mais SANS JSON-LD FAQPage (schema={false}),
// porte chaque slug de réalisation RÉELLE (lien galerie /realisations/<slug>),
// reste indexable (aucun noindex), ne contient jamais le mot « témoignage », et
// affiche bien une phrase traduite distinctive (anglais pour en/, arabe pour
// ar/). Le rendu FR à la racine n'est jamais touché par ces ports additifs.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { REALISATIONS } from '../src/lib/realisations';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const en = read('../src/pages/en/index.astro');
const ar = read('../src/pages/ar/index.astro');

describe.each([
  ['EN', en],
  ['AR', ar],
])('accueil %s — contrat i18n', (_label, src) => {
  it('importe le Layout partagé', () => {
    expect(src).toContain("import Layout from '../../layouts/Layout.astro'");
  });

  it('localise les liens internes via localizeNavHref', () => {
    expect(src).toContain("import { localizeNavHref } from '../../i18n/pages'");
    expect(src).toContain('localizeNavHref');
    // Le helper L() est appliqué aux liens internes du port.
    expect(src).toContain('const L = (href: string) => localizeNavHref(href, locale)');
  });

  it('monte <Faq> SANS FAQPage (schema={false}) — pas de doublon FAQPage', () => {
    expect(src).toContain('<Faq items={faq} schema={false}');
  });

  it('porte chaque slug de réalisation réelle (lien galerie)', () => {
    for (const r of REALISATIONS) {
      expect(src, `slug manquant : ${r.slug}`).toContain(`slug: '${r.slug}'`);
    }
    // Les liens galerie passent par le template /realisations/${g.slug}.
    expect(src).toContain('/realisations/${g.slug}');
  });

  it('reste indexable (aucun noindex)', () => {
    expect(src).not.toContain('noindex');
  });

  it("ne contient jamais le mot « témoignage »", () => {
    expect(src.toLowerCase()).not.toContain('témoignage');
  });
});

describe('phrases traduites distinctives', () => {
  it('EN : une phrase anglaise propre à l’accueil', () => {
    expect(en).toContain('The rest happens on WhatsApp');
    expect(en).toContain('60-second diagnostic');
  });

  it('AR : une phrase arabe propre à l’accueil', () => {
    expect(ar).toContain('البقية تجري على WhatsApp');
    expect(ar).toContain('تشخيص في 60 ثانية');
  });
});
