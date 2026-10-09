/**
 * Pages en français (YBW61-66), sur le HTML RENDU.
 * Règle commune : chaque phrase qui affirme un fait est une affirmation
 * PUBLIABLE du registre, rendue mot pour mot (`data-affirmation`) ; les appels
 * « Prendre rendez-vous » portent une valeur `produit` du contrat (YBW50).
 */
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import Societe from '../src/pages/societe.astro';
import { LEGAL_COMPLET } from './fixtures/legal-complet';
import { AFFIRMATIONS } from '../src/lib/claims';
import { publiables, texteAffirmation } from '../src/lib/affirmer';
import { VALEURS_PRODUIT } from '../src/lib/brand';
import { PAGES } from '../src/i18n/pages';
import { pageRendue, pagesRendues, type PageRendue } from './builtHtml';

const avecGabarit = () => pagesRendues().filter((p) => p.document.querySelector('header.entete'));
const affirmationsDe = (p: PageRendue) => [...p.document.querySelectorAll('[data-affirmation]')].map((e) => e.getAttribute('data-affirmation')!);
const appels = (p: PageRendue) => [...p.document.querySelectorAll('main a[href^="/rendez-vous/"]')].map((a) => a.getAttribute('href')!);
const texte = (p: PageRendue) => p.document.querySelector('main')?.textContent ?? '';

describe('affirmations (registre YBW18) — aides', () => {
  it('publiables() écarte les inconnues et les non publiables, garde l’ordre', () => {
    expect(publiables(['SB-CRM', 'SB-PRET-FRANCE', 'INCONNUE', 'SB-PENTE-IGN'])).toEqual(['SB-CRM', 'SB-PENTE-IGN']);
    const fixture = AFFIRMATIONS.map((a) => (a.id === 'SB-CRM' ? { ...a, publiable: false } : a));
    expect(publiables(['SB-CRM'], fixture)).toEqual([]);
  });

  it('texteAffirmation() lève sur une affirmation non publiable ou sans anglais approuvé', () => {
    expect(() => texteAffirmation('MB-EN-SERVICE', 'fr')).toThrow(/non publiable/);
    expect(() => texteAffirmation('SB-CRM', 'en')).toThrow(/anglaise/);
  });
});

describe('pages du gabarit : chaque affirmation rendue = registre, mot pour mot', () => {
  for (const p of avecGabarit()) {
    it(`${p.url}`, () => {
      const els = [...p.document.querySelectorAll('[data-affirmation]')];
      expect(els.length).toBeGreaterThan(0);
      for (const el of els) {
        const id = el.getAttribute('data-affirmation')!;
        expect(el.textContent, id).toBe(texteAffirmation(id, p.langueUrl));
      }
      for (const href of appels(p)) {
        const produit = new URL(href, 'https://x.test').searchParams.get('produit');
        if (produit !== null) expect(VALEURS_PRODUIT as readonly string[], href).toContain(produit);
      }
    });
  }
});

describe('YBW64 — Sur mesure', () => {
  const p = pageRendue(PAGES.surMesure.fr);
  it('démarche en quatre temps, offre et preuve depuis le registre', () => {
    expect(p.document.querySelectorAll('ol.etapes > li')).toHaveLength(4);
    expect(affirmationsDe(p)).toEqual(['SM-OFFRE', 'SM-DEMARCHE', 'YB-DEUX-PRODUITS', 'YB-REPONSE-HUMAINE']);
  });

  it('appel avec produit=sur_mesure', () => {
    expect(appels(p)).toContain('/rendez-vous/?produit=sur_mesure');
  });

  it('aucun client cité, aucun délai ni prix', () => {
    expect(texte(p)).not.toMatch(/\bclients?\b|\bdélais?\b|\bsemaines?\b|\bjours?\b|\bprix\b/i);
  });
});

describe('YBW65 — Société', () => {
  const p = pageRendue(PAGES.societe.fr);
  it('le métier, le sens du nom, la phrase D-YBW-9 depuis le registre', () => {
    expect(affirmationsDe(p)).toEqual(['YB-METIER', 'YB-NOM-SOURCE', 'YB-NOM-YAN', 'YB-SLOGAN', 'SB-ENTREPRISE-REELLE', 'YB-REPONSE-HUMAINE']);
    expect(p.document.querySelector('[data-affirmation="YB-SLOGAN"]')?.getAttribute('lang')).toBe('en');
  });

  it('texte seulement : aucune image, aucune date, aucun chiffre', () => {
    expect(p.document.querySelectorAll('main img, main picture, main figure')).toHaveLength(0);
    expect(texte(p).replace('1Bow', '')).not.toMatch(/\d/);
  });

  it('legal.ts nul (état réel) : aucune forme juridique ni société rendue', () => {
    expect(p.document.querySelector('[data-entites]')).toBeNull();
    expect(p.html).not.toMatch(/\bLtd\b|\bSARL\b|Limited|immatricul/i);
  });

  it('fixture complète : les deux sociétés citées avec leur forme', async () => {
    const container = await AstroContainer.create();
    const doc = new JSDOM(await container.renderToString(Societe, { props: { locale: 'fr', legal: LEGAL_COMPLET } })).window.document;
    expect(doc.querySelector('[data-entite="editeur"]')?.textContent).toContain('Fixture Test Ltd');
    expect(doc.querySelector('[data-entite="editeur"]')?.textContent).toContain('Angleterre et pays de Galles');
    expect(doc.querySelector('[data-entite="maroc"]')?.textContent).toContain("SARL d'associé unique");
  });
});
