// CIW301 — « Nos hypothèses » d'un devis C&I : les hypothèses SERVIES par `synthese_ci`
// (textes FR/EN/AR, source, date), et plus de « basse tension / tarif ONEE » sur un site MT.
import { describe, expect, it } from 'vitest';
import { proposalAssumptions, type ProposalResponse } from '../src/lib/proposition';

function proposal(mode: string, synthese?: Record<string, unknown>): ProposalResponse {
  return {
    reference: 'DEV-2026-301',
    date: '07/10/2026',
    client_name: 'Usine Exemple',
    statut: 'envoye',
    mode_installation: mode,
    quote: {
      ref: 'DEV-2026-301',
      date: '07/10/2026',
      client_name: 'Usine Exemple',
      totaux_sans: { ht_brut: 900000, remise: 0, ht_net: 900000, tva: 180000, ttc: 1080000 },
      display_total: 1080000,
      nb_options: 1,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 1080000, avec_batterie: 0, display_total: 1080000, nb_options: 1 },
    accepted: false,
    ...(synthese ? { synthese_ci: synthese } : {}),
  } as unknown as ProposalResponse;
}

const tout = (items: ReturnType<typeof proposalAssumptions>) =>
  items.map((i) => `${i.label} ${i.value} ${i.valueEn} ${i.valueAr}`).join(' | ');

const H_MT = [
  {
    cle: 'revente',
    textes: {
      fr: 'Surplus injecté : tarif ANRE servi.',
      en: 'Injected surplus: served ANRE tariff.',
      ar: 'الفائض المحقون: تعريفة الهيئة.',
    },
    source: 'décision ANRE 04/26',
    date: '2026-04-01',
  },
  {
    cle: 'puissance_souscrite',
    textes: {
      fr: 'La puissance souscrite et la prime fixe restent inchangées.',
      en: 'Subscribed power and fixed fee are unchanged.',
      ar: 'القدرة المكتتبة والإتاوة الثابتة دون تغيير.',
    },
    source: 'convention',
    date: null,
  },
];
const H_BT = [
  {
    cle: 'revente_bt',
    textes: {
      fr: 'Revente non ouverte en basse tension à ce jour.',
      en: 'Resale not open on low voltage to date.',
      ar: 'بيع الفائض غير مفتوح في الجهد المنخفض.',
    },
    source: 'décision ANRE 04/26',
    date: '2026-04-01',
  },
];

describe('CIW301 — hypothèses C&I servies', () => {
  it('payload MT → aucune « basse tension », la ligne 82-21 servie, et rien du texte résidentiel', () => {
    for (const mode of ['industriel', 'commercial']) {
      const items = proposalAssumptions(proposal(mode, { hypotheses: H_MT }));
      const t = tout(items);
      expect(t).not.toMatch(/basse tension/i);
      expect(t).not.toMatch(/low voltage/i);
      expect(t).not.toMatch(/tarif ONEE supposé/i);
      expect(t).not.toContain('Cadre tarifaire');
      expect(t).not.toContain("Horizon d'analyse");
      expect(t).toContain('Surplus injecté : tarif ANRE servi.');
      expect(t).toContain('Injected surplus: served ANRE tariff.');
      expect(t).toContain('الفائض المحقون');
      expect(t).toContain('décision ANRE 04/26, 01/04/2026');
    }
  });

  it('payload BT → la ligne servie « non ouverte en basse tension »', () => {
    const t = tout(proposalAssumptions(proposal('commercial', { hypotheses: H_BT })));
    expect(t).toContain('Revente non ouverte en basse tension à ce jour.');
    expect(t).not.toContain('Autoconsommation basse tension');
  });

  it('payload sans hypothèses servies → bloc C&I vide, jamais le texte résidentiel', () => {
    for (const synthese of [undefined, { version: 1 }, { hypotheses: [] }]) {
      const items = proposalAssumptions(proposal('industriel', synthese as Record<string, unknown> | undefined));
      const t = tout(items);
      expect(t).not.toMatch(/basse tension|ONEE|25 ans|Cadre tarifaire/i);
      // seule la ligne « Type d'installation » peut rester (libellé du mode, pas un chiffre)
      expect(items.every((i) => i.label === "Type d'installation")).toBe(true);
    }
  });

  it('le résidentiel garde sa propre branche', () => {
    const t = tout(proposalAssumptions(proposal('residentiel')));
    expect(t).toContain('Cadre tarifaire');
    expect(t).toContain("Horizon d'analyse");
  });
});
