// WJ122 — Panneau questions COMMERCIAL par catégorie (/devis/mon-toit).
// Le day-share par archétype (commercialDayShare) fait qu'un HÔTEL ≠ un BUREAU
// à facture égale. Parité des valeurs portées de solar.js QX44 ; questions par
// catégorie ; le payload (categorieCommerciale + réponses) traverse validateLead.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  COMMERCIAL_CATEGORIES,
  COMMERCIAL_CATEGORY_IDS,
  COMMERCIAL_DAY_SHARE,
  COMMERCIAL_DAY_SHARE_DEFAUT,
  COMMERCIAL_CATEGORY_QUESTIONS,
  COMMERCIAL_QUESTION_WEBHOOK_KEY,
  commercialDayShare,
} from '../src/lib/commercialCategories';
import { estimatePro } from '../src/lib/estimatorPro';
import { validateLead } from '../src/lib/lead';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const LOCALES: Array<[string, string]> = [
  ['FR', '../src/pages/devis/mon-toit.astro'],
  ['EN', '../src/pages/en/devis/mon-toit.astro'],
  ['AR', '../src/pages/ar/devis/mon-toit.astro'],
];

// SOURCE: frontend/src/features/ventes/solar.js:87-186 (QX44) — valeurs de
// référence dupliquées ici comme garde de parité (toute divergence casse le test).
const SOLAR_JS_DAY_SHARE: Record<string, number> = {
  bureau: 80, ecole: 85, commerce: 75, sante: 70, restaurant: 70,
  hammam: 65, hotel: 55, froid: 50, boulangerie: 45, autre: 80,
};
const SOLAR_JS_CATEGORY_VALUES = [
  'hotel', 'restaurant', 'commerce', 'bureau', 'sante',
  'ecole', 'hammam', 'boulangerie', 'froid', 'autre',
];

describe('WJ122 — parité des catégories/day-share vs solar.js (QX44)', () => {
  it('les 10 catégories (dont autre) sont présentes, dans le bon ordre', () => {
    expect(COMMERCIAL_CATEGORIES.map((c) => c.value)).toEqual(SOLAR_JS_CATEGORY_VALUES);
    expect(COMMERCIAL_CATEGORY_IDS).toEqual(SOLAR_JS_CATEGORY_VALUES);
  });

  it('la table day-share est byte-identique à solar.js', () => {
    expect(COMMERCIAL_DAY_SHARE).toEqual(SOLAR_JS_DAY_SHARE);
    expect(COMMERCIAL_DAY_SHARE_DEFAUT).toBe(80);
  });

  it('chaque catégorie porte un picto emoji (parité METADATA backend)', () => {
    for (const c of COMMERCIAL_CATEGORIES) {
      expect(c.icon.length).toBeGreaterThan(0);
      expect(c.label.length).toBeGreaterThan(0);
    }
  });
});

describe('WJ122 — commercialDayShare : hôtel < bureau (le cœur du besoin)', () => {
  it('hôtel (55) a une part diurne STRICTEMENT plus basse que bureau (80)', () => {
    expect(commercialDayShare('hotel')).toBe(55);
    expect(commercialDayShare('bureau')).toBe(80);
    expect(commercialDayShare('hotel')).toBeLessThan(commercialDayShare('bureau'));
  });

  it('une catégorie inconnue retombe sur le défaut (80), jamais une erreur', () => {
    expect(commercialDayShare('inexistant')).toBe(COMMERCIAL_DAY_SHARE_DEFAUT);
  });

  it('un override société valide est borné 10-100 et prioritaire', () => {
    expect(commercialDayShare('hotel', { override: { hotel: 42 } })).toBe(42);
    expect(commercialDayShare('hotel', { override: { hotel: 999 } })).toBe(100);
    expect(commercialDayShare('hotel', { override: { hotel: 1 } })).toBe(10);
  });
});

describe('WJ122 — questions PAR catégorie présentes (2-4 chacune)', () => {
  it('hôtel : chambres / occupation / piscine', () => {
    const keys = COMMERCIAL_CATEGORY_QUESTIONS.hotel.map((q) => q.key);
    expect(keys).toEqual(['chambres', 'occupation_pct', 'piscine']);
  });
  it('restaurant : chambres froides / horaires / cuisson (select à options)', () => {
    const qs = COMMERCIAL_CATEGORY_QUESTIONS.restaurant;
    expect(qs.map((q) => q.key)).toEqual(['chambres_froides', 'horaires', 'cuisson']);
    const horaires = qs.find((q) => q.key === 'horaires');
    expect(horaires?.type).toBe('select');
    expect(horaires?.options?.map((o) => o.value)).toEqual(['midi', 'soir', 'continu']);
  });
  it('froid : température de consigne (nombre, peut être négatif) / volume / saisonnalité', () => {
    const keys = COMMERCIAL_CATEGORY_QUESTIONS.froid.map((q) => q.key);
    expect(keys).toContain('temperature_consigne');
    expect(keys).toContain('volume_m3');
    expect(keys).toContain('saisonnalite_recolte');
  });
  it('autre : aucune question (repli)', () => {
    expect(COMMERCIAL_CATEGORY_QUESTIONS.autre).toEqual([]);
  });
  it('chaque catégorie non-« autre » a 2 à 4 questions', () => {
    for (const c of COMMERCIAL_CATEGORIES) {
      if (c.value === 'autre') continue;
      const n = COMMERCIAL_CATEGORY_QUESTIONS[c.value].length;
      expect(n).toBeGreaterThanOrEqual(2);
      expect(n).toBeLessThanOrEqual(4);
    }
  });
});

describe('WJ122 — mapping clé→webhook : snake_case → camelCase QX51', () => {
  it('les clés camelCase attendues par le webhook sont couvertes', () => {
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.occupation_pct).toBe('occupationPct');
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.chambres_froides).toBe('chambresFroides');
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.temperature_consigne).toBe('temperatureConsigne');
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.garde_nuit).toBe('gardeNuit');
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.saisonnalite_recolte).toBe('saisonnaliteRecolte');
  });
  it('surface_m2 (hammam) n’a PAS de destination webhook (jamais transmise)', () => {
    expect(COMMERCIAL_QUESTION_WEBHOOK_KEY.surface_m2).toBeUndefined();
  });
});

describe('WJ122 — estimatePro : hôtel ≠ bureau à facture ÉGALE', () => {
  const bill = { monthlyMad: 25_000, raccordement: 'bt' as const };

  it('un hôtel produit une couverture PLUS BASSE qu’un bureau (part diurne moindre)', () => {
    const hotel = estimatePro({ ...bill, categorieCommerciale: 'hotel' });
    const bureau = estimatePro({ ...bill, categorieCommerciale: 'bureau' });
    expect(hotel.ok && bureau.ok).toBe(true);
    if (hotel.ok && bureau.ok) {
      expect(hotel.tauxCouverture).toBeLessThan(bureau.tauxCouverture);
      // Un hôtel se dimensionne plus petit (moins de conso diurne à couvrir).
      expect(hotel.kwc).toBeLessThan(bureau.kwc);
      expect(hotel.hypotheses.dayShare).toBeCloseTo(0.55, 5);
      expect(bureau.hypotheses.dayShare).toBeCloseTo(0.8, 5);
    }
  });

  it('sans catégorie, le comportement historique (défaut 0.80) est inchangé', () => {
    const noCat = estimatePro({ ...bill });
    const bureau = estimatePro({ ...bill, categorieCommerciale: 'bureau' });
    expect(noCat.ok && bureau.ok).toBe(true);
    if (noCat.ok && bureau.ok) {
      expect(noCat.hypotheses.dayShare).toBeCloseTo(0.8, 5);
      expect(noCat.kwc).toBe(bureau.kwc);
    }
  });
});

describe('WJ122 — validateLead : categorieCommerciale + réponses traversent la liste blanche', () => {
  const base = {
    fullName: 'Reda K.', phone: '0612345678', city: 'Casablanca',
    roofType: 'autre', billRange: '5000-10000', consent: true, mode: 'commercial',
  };

  it('une catégorie valide + un échantillon de réponses survivent', () => {
    const r = validateLead({
      ...base, categorieCommerciale: 'hotel',
      chambres: 40, occupationPct: 70, piscine: true,
    });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.lead.categorieCommerciale).toBe('hotel');
      expect(r.lead.chambres).toBe(40);
      expect(r.lead.occupationPct).toBe(70);
      expect(r.lead.piscine).toBe(true);
    }
  });

  it('la température de consigne NÉGATIVE (froid) est conservée', () => {
    const r = validateLead({ ...base, categorieCommerciale: 'froid', temperatureConsigne: -18, volumeM3: 500 });
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.lead.temperatureConsigne).toBe(-18);
      expect(r.lead.volumeM3).toBe(500);
    }
  });

  it('une catégorie inconnue est ÉCARTÉE en silence (jamais bloquante)', () => {
    const r = validateLead({ ...base, categorieCommerciale: 'casino' });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.lead.categorieCommerciale).toBeUndefined();
  });
});

describe.each(LOCALES)('WJ122 — sous-panneau commercial dans mon-toit.astro (%s)', (_locale, rel) => {
  const src = read(rel);

  it('a un sous-panneau commercial DÉDIÉ + cartes catégorie', () => {
    expect(src).toContain('id="mt-sub-commercial"');
    expect(src).toContain('mt-commercial-cat');
    expect(src).toContain('mt-cc-bill');
  });

  it('syncStep2Panels bascule le panneau commercial séparément du pro', () => {
    expect(src).toContain("commercial.hidden = m !== 'commercial';");
    expect(src).toContain("pro.hidden = !(m === 'industriel' || m === 'professionnel');");
  });

  it('le payload envoie categorieCommerciale + les réponses whitelistées', () => {
    expect(src).toContain('function readCommercialAnswers(');
    expect(src).toContain('COMMERCIAL_QUESTION_WEBHOOK_KEY');
    expect(src).toContain("categorieCommerciale: mode === 'commercial'");
  });

  it("l'estimateur reçoit la catégorie (hôtel ≠ bureau)", () => {
    expect(src).toContain('categorieCommerciale: mode === \'commercial\' && commercialCategory');
  });
});
