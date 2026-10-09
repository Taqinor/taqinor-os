/**
 * Pages en français (YBW61-66), sur le HTML RENDU.
 * Règle commune : chaque phrase qui affirme un fait est une affirmation
 * PUBLIABLE du registre, rendue mot pour mot (`data-affirmation`) ; les appels
 * « Prendre rendez-vous » portent une valeur `produit` du contrat (YBW50).
 */
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import RendezVous from '../src/pages/rendez-vous.astro';
import Societe from '../src/pages/societe.astro';
import Solarbow from '../src/pages/solarbow.astro';
import { CLES_CHAMPS, POT_DE_MIEL } from '../src/lib/rdv/champs';
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

describe('YBW61 — Accueil', () => {
  const p = pageRendue(PAGES.accueil.fr);
  it('positionnement en une phrase, deux cartes produit du registre, sur mesure, société, appel', () => {
    expect(p.document.querySelector('h1')?.textContent).toBe(texteAffirmation('YB-METIER', 'fr'));
    expect(affirmationsDe(p)).toEqual([
      'YB-METIER',
      'YB-POSITIONNEMENT',
      'SB-POUR-QUI',
      'SB-CRM',
      'SB-CALEPINAGE-3D',
      'SB-PACKS-FR',
      'MB-POUR-QUI',
      'MB-CREATION-EN-PAUSE',
      'MB-PROPOSE-APPROUVE',
      'MB-COUPE-CIRCUIT',
      'SM-OFFRE',
      'YB-NOM-SOURCE',
      'YB-REPONSE-HUMAINE',
    ]);
    expect([...p.document.querySelectorAll('[data-produit] h3')].map((h) => h.textContent)).toEqual(['SolarBow', 'MarketingBow']);
  });

  it('aucune statistique (aucun chiffre hors « 3D »/« 2D »), aucun logo client, aucune personne (R13 « en service » : founderRules)', () => {
    expect(texte(p).replace(/[23]D/g, '')).not.toMatch(/\d/);
    expect(p.document.querySelectorAll('main img:not(figure[data-capture] img)')).toHaveLength(0);
  });

  it('la capture du héros est prioritaire et hors de toute animation ; le trait animé est à côté du titre', () => {
    expect(p.document.querySelector('.capture-hero[data-capture="crm-pipeline"]')).not.toBeNull();
    expect(p.document.querySelector('h1 .motif-anime')).toBeNull();
    expect(p.document.querySelectorAll('.hero-trajectoire .motif-anime').length).toBeGreaterThan(0);
  });

  it('la sonde « bonjour » est supprimée (FR et EN)', () => {
    expect(pagesRendues().map((x) => x.url)).not.toContain('/bonjour/');
  });
});

describe('liens internes : aucun lien mort', () => {
  const pages = pagesRendues();
  const urls = new Set(pages.map((x) => x.url));
  for (const p of pages) {
    it(p.url, () => {
      const ids = new Set([...p.document.querySelectorAll('[id]')].map((e) => e.id));
      for (const a of p.document.querySelectorAll('a[href]')) {
        const href = a.getAttribute('href')!;
        if (href.startsWith('#')) expect(ids.has(href.slice(1)), href).toBe(true);
        else if (href.startsWith('/')) {
          const u = new URL(href, 'https://x.test');
          expect(urls.has(u.pathname), href).toBe(true);
          if (u.hash) expect(pageRendue(u.pathname).document.getElementById(u.hash.slice(1)), href).not.toBeNull();
        }
      }
    });
  }
});

/** Modules affichés d'une page produit. */
const modulesDe = (doc: Document) => [...doc.querySelectorAll('[data-module]')].map((m) => m.getAttribute('data-module'));
/** Ce que la page produit ne doit JAMAIS dire (D-YBW-8, YBW92 GATED). */
const NON_PUBLIABLES_SB = /signature [ée]lectronique|factur-?x|paiement en ligne|monitoring|suivi de production|agent (sql|de requ)|s[ée]curit[ée]|h[ée]bergement|automatique|[ée]conomies|\btarifs?\b/i;

describe('YBW62 — SolarBow', () => {
  const p = pageRendue(PAGES.solarbow.fr);
  it('à qui c’est destiné, interface en français, phrase D-YBW-9, quatre modules depuis le registre', () => {
    expect(p.document.querySelector('h1')?.textContent).toBe(texteAffirmation('SB-POUR-QUI', 'fr'));
    expect(modulesDe(p.document)).toEqual(['prospects', 'calepinage', 'dossiers', 'devis']);
    expect(affirmationsDe(p)).toEqual([
      'SB-POUR-QUI',
      'SB-INTERFACE-FR',
      'SB-ENTREPRISE-REELLE',
      'SB-CRM',
      'SB-WHATSAPP-LIEN',
      'SB-CALEPINAGE-3D',
      'SB-PENTE-IGN',
      'SB-PACKS-FR',
      'SB-DEVIS-PDF',
      'YB-REPONSE-HUMAINE',
    ]);
  });

  it('jamais : signature électronique, Factur-X, paiement en ligne, suivi, agent, sécurité, hébergement, « automatique », économies', () => {
    expect(texte(p)).not.toMatch(NON_PUBLIABLES_SB);
    expect(NON_PUBLIABLES_SB.test('Relances WhatsApp automatiques')).toBe(true);
  });

  it('captures avec légende ; appels avec produit=solarbow', () => {
    expect([...p.document.querySelectorAll('figure[data-capture]')].map((f) => f.getAttribute('data-capture'))).toEqual([
      'crm-pipeline',
      'calepinage-3d',
      'packs-reglementaires',
      'proposition-pdf',
    ]);
    const liens = appels(p);
    expect(liens.length).toBeGreaterThanOrEqual(2);
    for (const l of liens) expect(l).toBe('/rendez-vous/?produit=solarbow');
  });

  it('un module sans affirmation publiable disparaît (fixture)', async () => {
    const registre = AFFIRMATIONS.map((a) => (a.id === 'SB-PACKS-FR' ? { ...a, publiable: false } : a));
    const container = await AstroContainer.create();
    const doc = new JSDOM(await container.renderToString(Solarbow, { props: { locale: 'fr', registre } })).window.document;
    expect(modulesDe(doc)).toEqual(['prospects', 'calepinage', 'devis']);
  });
});

/** Ce que la page MarketingBow ne doit JAMAIS dire (D-YBW-7, faits établis, YBW92). */
const NON_PUBLIABLES_MB =
  /veille|biblioth[èe]que|concurren|en service|en production|r[ée]sultats?|\bCPL\b|co[ûu]t par|\bIA\b|intelligence artificielle|images?\b|vid[ée]os?|partenaire (meta|officiel)|certifi[ée]|s[ée]curit[ée]|isolation|rempla(cer|ce)/i;

describe('YBW63 — MarketingBow', () => {
  const p = pageRendue(PAGES.marketingbow.fr);
  it('moteur de campagnes seulement, quatre modules et la procédure depuis le registre', () => {
    expect(p.document.querySelector('h1')?.textContent).toBe(texteAffirmation('MB-POUR-QUI', 'fr'));
    expect(modulesDe(p.document)).toEqual(['pause', 'approbation', 'garde-fous', 'textes']);
    expect(affirmationsDe(p)).toEqual([
      'MB-POUR-QUI',
      'MB-OPTION',
      'MB-CREATION-EN-PAUSE',
      'MB-PROPOSE-APPROUVE',
      'MB-PERMISSIONS',
      'MB-COUPE-CIRCUIT',
      'MB-CHIFFRES-CITES',
      'MB-PROPRIETE',
      'YB-REPONSE-HUMAINE',
    ]);
  });

  it('la propriété du compte est une PROCÉDURE (section « Notre façon de travailler »), pas un module logiciel', () => {
    const procedure = p.document.querySelector('[data-procedure]');
    expect(procedure?.querySelector('[data-affirmation="MB-PROPRIETE"]')).not.toBeNull();
    expect(p.document.querySelector('[data-module] [data-affirmation="MB-PROPRIETE"]')).toBeNull();
  });

  it('jamais : veille, « en service », résultats, CPL, IA, image/vidéo, « partenaire/certifié » Meta, sécurité, remplacer', () => {
    expect(texte(p)).not.toMatch(NON_PUBLIABLES_MB);
    expect(p.document.querySelectorAll('main img[alt*="Meta" i], main svg[aria-label*="Meta" i]')).toHaveLength(0);
    expect(NON_PUBLIABLES_MB.test('MarketingBow est en service')).toBe(true);
  });

  it('appels avec produit=marketingbow', () => {
    for (const l of appels(p)) expect(l).toBe('/rendez-vous/?produit=marketingbow');
    expect(appels(p).length).toBeGreaterThanOrEqual(2);
  });
});

describe('YBW66 — Rendez-vous', () => {
  const p = pageRendue(PAGES.rendezVous.fr);
  it('le formulaire YBW55, aucun champ hors registre', () => {
    const form = p.document.querySelector('main form[data-rendez-vous]');
    expect(form).not.toBeNull();
    const noms = [...form!.querySelectorAll('[name]')].map((e) => e.getAttribute('name')!);
    for (const n of noms) expect([...CLES_CHAMPS, POT_DE_MIEL] as string[], n).toContain(n);
  });

  it('ce qui se passe ensuite : une personne répond (registre), aucun délai promis', () => {
    expect(affirmationsDe(p)).toEqual(['YB-REPONSE-HUMAINE']);
    expect(texte(p)).not.toMatch(/\d+\s*(h|heures?|jours?|minutes?)\b|sous \d|dans les \d|immédiat|rapidement/i);
  });

  it('pas d’appel vers soi-même ; WhatsApp absent tant que le numéro manque, présent avec une fixture', async () => {
    expect(p.document.querySelector('header .bouton-entete')).toBeNull();
    expect(p.document.querySelector('[data-whatsapp-page]')).toBeNull();
    const container = await AstroContainer.create();
    const doc = new JSDOM(await container.renderToString(RendezVous, { props: { locale: 'fr', whatsapp: '33100000000' } })).window.document;
    expect(doc.querySelector('[data-whatsapp-page]')?.getAttribute('href')).toBe('https://wa.me/33100000000');
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
    expect(doc.querySelector('[data-entite="maroc"]')?.textContent).toContain("SARL d’associé unique");
  });
});
