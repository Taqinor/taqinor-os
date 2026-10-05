// CIW412 — pages 82-21 et guide (FR/EN/AR) : le tarif d'excédent ANRE vise la
// TENSION (MT/HT/THT), pas un régime ; plus d'« échéance 2027 » sans source ;
// « hors taxes » à côté de 0,18–0,21 ; l'Article 33 sans date de départ
// affirmée. Garde sur le HTML CONSTRUIT des 6 pages (astro build).
import { describe, expect, it } from 'vitest';
import { builtPage, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string, 'fr' | 'en' | 'ar']> = [
  ['FR loi', '/loi-82-21', 'fr'],
  ['EN loi', '/en/loi-82-21', 'en'],
  ['AR loi', '/ar/loi-82-21', 'ar'],
  ['FR guide', '/guides/loi-82-21-expliquee', 'fr'],
  ['EN guide', '/en/guides/loi-82-21-expliquee', 'en'],
  ['AR guide', '/ar/guides/loi-82-21-expliquee', 'ar'],
];

const INTERDITS = [
  'Cela couvre les régimes', 'seulement pour les régimes accord',
  'This covers the connection-agreement', 'but only for the connection-agreement',
  'يشمل هذا نظامَي', 'لكن فقط لنظامَي',
  'échéance évoquée', 'timeline mentioned', 'يُتداوَل أجل',
];

const HORS_TAXES = { fr: /hors taxes/, en: /excluding taxes/, ar: /دون احتساب الرسوم/ };
const PAS_ENCORE = { fr: 'Pas encore publié', en: 'Not yet published', ar: 'لم يُنشَر بعد' };
const DATE_DECRET = /9 juin 2026|9 June 2026|9 يونيو 2026/;

describe('CIW412 — tarif d\'excédent = TENSION MT/HT/THT, Article 33 sans date affirmée', () => {
  for (const [label, route, lang] of PAGES) {
    const txt = visibleText(builtPage(route));

    it(`${label} — plus de formulation « régime », plus d'échéance évoquée ni de « 2027 »`, () => {
      for (const bad of INTERDITS) expect(txt).not.toContain(bad);
      expect(txt).not.toContain('2027');
    });

    it(`${label} — chaque « 0,18–0,21 » est accompagné de « hors taxes » (ou ne figure plus)`, () => {
      for (const m of txt.matchAll(/0[.,]18\s*[–-]\s*0[.,]21/g)) {
        const suite = txt.slice(m.index!, m.index! + 160);
        expect(suite).toMatch(HORS_TAXES[lang]);
      }
      // le tarif est dit en tension, jamais en régime : « MT/HT/THT » (MV/HV/EHV en EN) est là
      expect(txt).toMatch(lang === 'en' ? /MV\/HV\/EHV/ : /MT\/HT\/THT/);
      expect(txt).toMatch(HORS_TAXES[lang]);
    });

    it(`${label} — « 11 kW » figure dans le bloc « Pas encore publié » (basse tension, quel que soit le régime)`, () => {
      const i = txt.indexOf(PAS_ENCORE[lang]);
      expect(i).toBeGreaterThan(-1);
      expect(txt.slice(i, i + 450)).toContain('11 kW');
    });

    it(`${label} — aucune date de départ ni d'échéance accolée à l'Article 33`, () => {
      const re = lang === 'ar' ? /(المادة|مادته|الفصل)\s*33[^.؟!]{0,260}/g : /Article 33[^.?!]{0,260}/g;
      for (const m of txt.matchAll(re)) expect(m[0]).not.toMatch(DATE_DECRET);
    });
  }

  it('la date du DÉCRET (en vigueur le 9 juin 2026) reste sur les pages loi', () => {
    expect(visibleText(builtPage('/loi-82-21'))).toContain('9 juin 2026');
    expect(visibleText(builtPage('/en/loi-82-21'))).toContain('9 June 2026');
    expect(visibleText(builtPage('/ar/loi-82-21'))).toContain('9 يونيو 2026');
  });

  it('la date « vérifié le » de l\'encadré est mise à jour (plus le 3 juillet)', () => {
    expect(visibleText(builtPage('/loi-82-21'))).toContain('vérifié le 5 octobre 2026');
    expect(visibleText(builtPage('/en/loi-82-21'))).toContain('verified on 5 October 2026');
    expect(visibleText(builtPage('/ar/loi-82-21'))).toContain('5 أكتوبر 2026');
    for (const [, route] of PAGES) {
      expect(visibleText(builtPage(route))).not.toMatch(/3 juillet 2026|3 July 2026|3 يوليوز 2026/);
    }
  });

  it('le guide cite l\'Article 33 mot pour mot et dit que le point de départ est à confirmer', () => {
    const fr = visibleText(builtPage('/guides/loi-82-21-expliquee'));
    expect(fr).toContain("« dans un délai de dix-huit (18) mois à compter de la date d'entrée en vigueur de la présente loi »");
    expect(fr).toContain("point de départ de ce délai est à confirmer auprès des services de l'énergie");
    const en = visibleText(builtPage('/en/guides/loi-82-21-expliquee'));
    expect(en).toContain('within eighteen (18) months from the date of entry into force of this law');
    expect(en).toContain('to be confirmed with the energy authorities');
    const ar = visibleText(builtPage('/ar/guides/loi-82-21-expliquee'));
    expect(ar).toMatch(/ثمانية عشر \(\s*18\s*\) شهراً ابتداءً من تاريخ دخول هذا القانون حيّز التنفيذ/);
  });
});
