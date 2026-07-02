// WJ32 — Complétude du contenu de la proposition : logique PURE (aucun DOM).
// Contrat central : chaque bloc dégrade proprement (null / tableau vide)
// quand sa donnée backend est absente — jamais un chiffre inventé.
import { describe, expect, it } from 'vitest';
import {
  backendFinancing,
  proposalVariants,
  nextSteps,
  proposalAssumptions,
  monitoringPoints,
  objectionFaq,
  SAVINGS_HORIZON_YEARS,
  type ProposalResponse,
  type ProposalFinancingBlock,
} from '../src/lib/proposition';

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-042',
    date: '22/06/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-042',
      date: '22/06/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      puissance_kwc: 6.48,
      nb_panneaux: 9,
      watt_par_panneau: 720,
      prod_kwh: 10000,
      eco_s_ann: 12000,
      eco_a_ann: 15000,
      recommended: 'avec_batterie',
      totaux_sans: { ht_brut: 50000, remise: 0, ht_net: 50000, tva: 10000, ttc: 60000 },
      totaux_avec: { ht_brut: 80000, remise: 0, ht_net: 80000, tva: 16000, ttc: 96000 },
      nb_options: 2,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 60000, avec_batterie: 96000, display_total: 96000, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

const VALID_FINANCING: ProposalFinancingBlock = {
  indicatif: true,
  cash: { montant_ttc: 96000, label: 'Paiement comptant (TTC)' },
  credit: {
    mensualite: 1450,
    duree_mois: 84,
    taux_annuel_pct: 6.5,
    programme_nom: 'tatwir',
    programme_label: 'Tatwir Croissance Verte',
  },
  onee_comparison: { show: true, message: 'La mensualité...', eco_mensuelle_sans: 1000, eco_mensuelle_avec: 1250 },
  guidance_text: 'Contactez votre banque.',
};

describe('WJ32 — backendFinancing (lecture défensive du bloc backend QJ12)', () => {
  it('bloc valide → renvoyé tel quel', () => {
    expect(backendFinancing({ financing: VALID_FINANCING })).toEqual(VALID_FINANCING);
  });

  it('absent → null (le bloc financement se masque)', () => {
    expect(backendFinancing({ financing: undefined })).toBeNull();
    expect(backendFinancing({ financing: null })).toBeNull();
  });

  it('malformé (cash/credit manquants) → null, jamais de throw', () => {
    // @ts-expect-error — entrée volontairement hors-contrat
    expect(backendFinancing({ financing: {} })).toBeNull();
    // @ts-expect-error
    expect(backendFinancing({ financing: { cash: {} } })).toBeNull();
  });
});

describe('WJ32 — proposalVariants (strip « autres tailles »)', () => {
  it('tableau backend présent → renvoyé tel quel', () => {
    const variants = [{ id: 2, reference: 'DEV-2026-043', version: 2, note: '', total_ttc: 110000 }];
    expect(proposalVariants({ variants })).toEqual(variants);
  });

  it('absent/non-tableau → tableau vide (devis isolé, jamais de crash)', () => {
    expect(proposalVariants({ variants: undefined })).toEqual([]);
    // @ts-expect-error
    expect(proposalVariants({ variants: 'x' })).toEqual([]);
  });
});

describe('WJ32 — nextSteps (« Et après ? »)', () => {
  it('toujours 4 étapes, dans l’ordre signature → mise en service', () => {
    const steps = nextSteps();
    expect(steps.map((s) => s.id)).toEqual(['signature', 'visite', 'installation', 'mise-en-service']);
    for (const s of steps) {
      expect(s.title.length).toBeGreaterThan(0);
      expect(s.titleAr.length).toBeGreaterThan(0);
      expect(s.body.length).toBeGreaterThan(0);
    }
  });

  it('délais annoncés comme indicatifs (jamais un engagement daté ferme)', () => {
    const visite = nextSteps().find((s) => s.id === 'visite')!;
    expect(visite.body).toMatch(/indicatif/i);
  });
});

describe('WJ32 — proposalAssumptions (« Nos hypothèses », jamais de valeur inventée)', () => {
  it('toujours au moins tarif + horizon (constantes du module, jamais absentes)', () => {
    const p = makeProposal({ quote: { inst_type: undefined } });
    const items = proposalAssumptions(p);
    expect(items.length).toBeGreaterThanOrEqual(2);
    expect(items.some((i) => i.value.includes('82-21'))).toBe(true);
    expect(items.some((i) => i.value.includes(String(SAVINGS_HORIZON_YEARS)))).toBe(true);
  });

  it('inst_type présent → hypothèse de type ajoutée', () => {
    const p = makeProposal({ quote: { inst_type: 'agricole' } });
    const items = proposalAssumptions(p);
    expect(items.some((i) => i.label === 'Type d\'installation')).toBe(true);
  });

  it('financement backend présent → hypothèse de programme ajoutée (sourcée, pas inventée)', () => {
    const p = makeProposal({ financing: VALID_FINANCING });
    const items = proposalAssumptions(p);
    const finItem = items.find((i) => i.label.includes('financement'));
    expect(finItem).toBeDefined();
    expect(finItem!.value).toContain('Tatwir Croissance Verte');
  });

  it('financement absent → pas d’hypothèse de programme fabriquée', () => {
    const p = makeProposal({ financing: undefined });
    const items = proposalAssumptions(p);
    expect(items.some((i) => i.label.includes('financement'))).toBe(false);
  });
});

describe('WJ32 — monitoringPoints (accompagnement post-installation)', () => {
  it('toujours au moins 2 points, contenu factuel (pas de dépendance backend)', () => {
    const points = monitoringPoints();
    expect(points.length).toBeGreaterThanOrEqual(2);
    for (const pt of points) {
      expect(pt.label.length).toBeGreaterThan(0);
      expect(pt.labelAr.length).toBeGreaterThan(0);
    }
  });
});

describe('WJ32 — objectionFaq (4–5 objections)', () => {
  it('entre 4 et 5 items, chacun avec question + réponse FR et AR', () => {
    const faq = objectionFaq();
    expect(faq.length).toBeGreaterThanOrEqual(4);
    expect(faq.length).toBeLessThanOrEqual(5);
    for (const item of faq) {
      expect(item.question.length).toBeGreaterThan(0);
      expect(item.questionAr.length).toBeGreaterThan(0);
      expect(item.answer.length).toBeGreaterThan(0);
      expect(item.answerAr.length).toBeGreaterThan(0);
    }
  });

  it('ids uniques (utilisables comme clé d’accordéon)', () => {
    const ids = objectionFaq().map((f) => f.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
