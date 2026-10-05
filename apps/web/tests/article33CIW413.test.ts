// CIW413 — page Article 33, FAQ et ruban (FR/EN/AR) : citer l'art. 33, dire que le
// point de départ des 18 mois reste à confirmer, et « le DÉCRET est en vigueur
// depuis le 9 juin 2026 » au lieu de « la loi ». Garde sur le HTML CONSTRUIT.
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

const INTERDITS = [
  // FR
  'loi 82-21 est en vigueur depuis', 'court depuis le 9 juin', 'ouverte le 9 juin', 'La loi 82-21 est en vigueur',
  // EN
  'Law 82-21 has been in force since', 'open since 9 June', 'opened on 9 June', 'This window has been open',
  // AR
  'القانون 82-21 ساري المفعول منذ', 'مفتوحة منذ', 'فُتحت في 9 يونيو',
];

describe('CIW413 — Article 33 : citation, point de départ à confirmer, décret (pas « la loi »)', () => {
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

    it(`${label} — l'art. 33 est cité et le point de départ « à confirmer »`, () => {
      if (lang === 'fr') {
        expect(txt).toContain("dans un délai de dix-huit (18) mois à compter de la date d'entrée en vigueur de la présente loi");
        expect(txt).toContain('à confirmer auprès des services de l\'énergie');
        expect(brut).toContain("Le décret d'application 2-25-100 est en vigueur depuis le 9 juin 2026");
      } else if (lang === 'en') {
        expect(txt).toContain('within eighteen (18) months from the date of entry into force of this law');
        expect(txt).toContain('to be confirmed with the energy authorities');
        expect(brut).toContain('Implementing decree 2-25-100 has been in force since 9 June 2026');
      } else {
        expect(txt).toMatch(/ثمانية عشر \(\s*18\s*\) شهراً ابتداءً من تاريخ دخول هذا القانون حيّز التنفيذ/);
        expect(txt).toContain('يجب تأكيدها لدى مصالح الطاقة');
        expect(brut).toContain('المرسوم التطبيقي 2-25-100 ساري المفعول منذ 9 يونيو 2026');
      }
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

  it('FAQ — la même citation dans les 3 langues', () => {
    expect(visibleText(builtPage('/faq'))).toContain("dix-huit (18) mois à compter de la date d'entrée en vigueur de la présente loi");
    expect(visibleText(builtPage('/en/faq'))).toContain('eighteen (18) months from the date of entry into force of this law');
    expect(visibleText(builtPage('/ar/faq'))).toMatch(/ثمانية عشر \(\s*18\s*\) شهراً ابتداءً من تاريخ دخول هذا القانون حيّز التنفيذ/);
  });

  it('le ruban affiché sur tout le site nomme le décret 2-25-100 (3 langues)', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const t = (ui[lang] as Record<string, string>)['ribbon.text'];
      expect(t).toContain('2-25-100');
      expect(t).toContain('9');
    }
    expect(visibleText(builtPage('/'))).toContain('Décret 2-25-100 en vigueur depuis le 9 juin 2026');
    expect(visibleText(builtPage('/en'))).toContain('Decree 2-25-100 in force since 9 June 2026');
    expect(visibleText(builtPage('/ar'))).toContain('المرسوم 2-25-100 ساري منذ 9 يونيو 2026');
    // aucune page n'affiche plus « la loi » comme en vigueur depuis le 9 juin
    for (const route of ['/', '/en', '/ar', '/professionnel']) {
      const txt = visibleText(builtPage(route));
      expect(txt).not.toContain('Régime en vigueur depuis le 9 juin 2026');
      expect(txt).not.toContain('In force since 9 June 2026');
    }
  });
});
