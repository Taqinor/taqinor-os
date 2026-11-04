// CIW413 — page Article 33, FAQ et ruban (FR/EN/AR) : nommer l'art. 33 et le DÉCRET (pas « la loi »).
// Amendé par WAUD18-b selon D-WAUD-4=a (Reda, 03/11/2026) : 0 durée, 0 date, 0 amende hors
// citation sourcée sur /loi-82-21 — la citation « dix-huit (18) mois » et les dates du décret
// (9 juin / 9 mars 2026, BO non relu) quittent ces pages. Garde sur le HTML CONSTRUIT.
import { describe, expect, it } from 'vitest';
import { builtPage, visibleText } from './builtHtmlHelper';
import { ui } from '../src/i18n/ui';

const ART33: Array<[string, string, 'fr' | 'en' | 'ar']> = [
  ['FR', '/regularization-article-33', 'fr'],
  ['EN', '/en/regularization-article-33', 'en'],
  ['AR', '/ar/regularization-article-33', 'ar'],
];
const FAQ: Array<[string, string]> = [
  ['FR', '/faq'],
  ['EN', '/en/faq'],
  ['AR', '/ar/faq'],
];

const DUREE_OU_DATE = /18 mois|18 months|18 شهر|dix-huit|eighteen|ثمانية عشر|9 juin|9 June|9 يونيو|9 mars 2026|9 March 2026|9 مارس 2026/;

const INTERDITS = [
  // FR
  'loi 82-21 est en vigueur depuis', 'court depuis le 9 juin', 'ouverte le 9 juin', 'La loi 82-21 est en vigueur',
  // EN
  'Law 82-21 has been in force since', 'open since 9 June', 'opened on 9 June', 'This window has been open',
  // AR
  'القانون 82-21 ساري المفعول منذ', 'مفتوحة منذ', 'فُتحت في 9 يونيو',
];

describe('CIW413 + WAUD18-b — Article 33 nommé, décret (pas « la loi »), ni durée ni date (D-WAUD-4=a)', () => {
  for (const [label, route, lang] of ART33) {
    const html = builtPage(route);
    const txt = visibleText(html);
    // description / méta : lues dans le HTML brut (apostrophes d'attribut décodées)
    const brut = html.replace(/&#39;|&#x27;|&apos;/g, "'");

    it(`${label} — aucune formulation « la loi est en vigueur depuis » / « fenêtre ouverte le 9 juin », aucune échéance 2027`, () => {
      for (const bad of INTERDITS) expect(txt).not.toContain(bad);
      expect(txt).not.toContain('2027');
      expect(txt).not.toMatch(/échéance évoquée|timeline mentioned/);
    });

    it(`${label} — D-WAUD-4=a : ni durée ni date, l'art. 33 et le décret 2-25-100 nommés, texte exact renvoyé à /loi-82-21`, () => {
      expect(brut).not.toMatch(DUREE_OU_DATE);
      expect(txt).toContain('2-25-100');
      expect(html).toMatch(/href="\/(en\/|ar\/)?loi-82-21\/?"/);
      expect(txt).not.toMatch(/à confirmer|to be confirmed|يجب تأكيدها/);
    });

    it(`${label} — la phrase tarifaire suit CIW412 (tension MT/HT/THT, BT non ouverte, hors taxes)`, () => {
      expect(txt).toMatch(lang === 'en' ? /MV\/HV\/EHV/ : /MT\/HT\/THT/);
      expect(txt).toMatch(lang === 'fr' ? /hors taxes/ : lang === 'en' ? /excluding taxes/ : /دون احتساب الرسوم/);
      expect(txt).toContain('11 kW');
    });
  }

  for (const [label, route] of FAQ) {
    it(`${label} — la FAQ ne dit plus « fenêtre de 18 mois ouverte le 9 juin 2026 »`, () => {
      const txt = visibleText(builtPage(route));
      for (const bad of INTERDITS) expect(txt).not.toContain(bad);
      expect(txt).not.toMatch(/fenêtre de 18 mois, ouverte|18-month window, opened|نافذة من 18 شهراً، فُتحت/);
    });
  }

  it('FAQ — D-WAUD-4=a : ni durée ni date dans les 3 langues, l’art. 33 nommé', () => {
    for (const [, route] of FAQ) {
      const txt = visibleText(builtPage(route));
      expect(txt).not.toMatch(DUREE_OU_DATE);
      expect(txt).toMatch(/Article 33|المادة 33/);
    }
  });

  it('WAUD46-b (D-WAUD-7=a ; date retirée par D-WAUD-4=a) : ruban sur accueil, /loi-82-21, /regularization-article-33, /résidentiel seulement (3 langues)', () => {
    const avec = ['/', '/loi-82-21', '/regularization-article-33', '/résidentiel'];
    const sans = ['/garanties', '/faq', '/installation-solaire-casablanca', '/ressources/10-questions-avant-de-signer', '/contact', '/guides/loi-82-21-expliquee'];
    for (const pre of ['', '/en', '/ar']) {
      for (const r of avec) expect(builtPage(`${pre}${r}`), `${pre}${r}`).toContain('class="ribbon-link');
      for (const r of sans) {
        if (pre === '/en' && r.startsWith('/ressources')) continue; // pas de version EN
        expect(builtPage(`${pre}${r}`), `${pre}${r}`).not.toContain('class="ribbon-link');
      }
    }
  });

  it('le ruban nomme le décret 2-25-100 (3 langues)', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const t = (ui[lang] as Record<string, string>)['ribbon.text'];
      expect(t).toContain('2-25-100');
      expect(t).not.toMatch(DUREE_OU_DATE); // D-WAUD-4=a : le ruban ne date rien
    }
    expect(visibleText(builtPage('/'))).toContain('Décret 2-25-100 en vigueur');
    expect(visibleText(builtPage('/en'))).toContain('Decree 2-25-100 in force');
    expect(visibleText(builtPage('/ar'))).toContain('المرسوم 2-25-100 ساري المفعول');
    // aucune page n'affiche plus « la loi » comme en vigueur depuis le 9 juin
    for (const route of ['/', '/en', '/ar', '/professionnel']) {
      const txt = visibleText(builtPage(route));
      expect(txt).not.toContain('Régime en vigueur depuis le 9 juin 2026');
      expect(txt).not.toContain('In force since 9 June 2026');
    }
  });
});
