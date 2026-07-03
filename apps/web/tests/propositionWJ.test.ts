// WJ9–WJ16 — Logique pure de l'ÉLÉVATION de la proposition client.
//
// Discipline « zéro chiffre inventé » : chaque test prouve qu'une valeur vient
// du payload backend OU d'une règle documentée à partir de valeurs présentes, et
// qu'un repli libellé (jamais fabriqué) apparaît quand la donnée manque.
import { describe, expect, it } from 'vitest';
import {
  resolveValidity,
  parseBackendDate,
  formatFrenchDate,
  savingsHeadline,
  environmentalImpact,
  financingComparison,
  loanMonthlyPayment,
  whatsappLink,
  whatsappLinkForIntent,
  buildAcceptBodyRich,
  buildAcceptBody,
  CO2_KG_PER_KWH,
  CO2_KG_PER_TREE_YEAR,
  SAVINGS_HORIZON_YEARS,
  TAQINOR_WHATSAPP,
  type ProposalResponse,
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
      roi_s: 6.5,
      roi_a: 7.2,
      recommended: 'avec_batterie',
      totaux_sans: { ht_brut: 50000, remise: 5000, ht_net: 45000, tva: 9000, ttc: 54000 },
      totaux_avec: { ht_brut: 80000, remise: 8000, ht_net: 72000, tva: 14400, ttc: 86400 },
      display_total: 86400,
      nb_options: 2,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 54000, avec_batterie: 86400, display_total: 86400, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

// ── WJ15 · Fenêtre de validité honnête ───────────────────────────────────────

describe('WJ15 — fenêtre de validité (jamais inventée, jamais de compte-à-rebours)', () => {
  it('parseBackendDate — accepte ISO et FR, rejette le reste', () => {
    expect(formatFrenchDate(parseBackendDate('2026-07-15')!)).toBe('15 juillet 2026');
    expect(formatFrenchDate(parseBackendDate('15/07/2026')!)).toBe('15 juillet 2026');
    expect(parseBackendDate('')).toBeNull();
    expect(parseBackendDate(null)).toBeNull();
    expect(parseBackendDate('bientôt')).toBeNull();
    expect(parseBackendDate('2026-13-40')).toBeNull();
  });

  it('utilise la date backend (racine) quand présente', () => {
    const p = makeProposal({ date_validite: '2026-07-15' });
    const v = resolveValidity(p, new Date(Date.UTC(2026, 5, 22)));
    expect(v.fromBackend).toBe(true);
    expect(v.label).toBe('15 juillet 2026');
    expect(v.expired).toBe(false);
  });

  it('lit aussi date_validite dans quote', () => {
    const p = makeProposal({ quote: { date_validite: '30/09/2026' } });
    const v = resolveValidity(p, new Date(Date.UTC(2026, 5, 22)));
    expect(v.fromBackend).toBe(true);
    expect(v.label).toBe('30 septembre 2026');
  });

  it('signale une échéance déjà passée', () => {
    const p = makeProposal({ date_validite: '2026-01-01' });
    const v = resolveValidity(p, new Date(Date.UTC(2026, 5, 22)));
    expect(v.expired).toBe(true);
  });

  it('repli HONNÊTE sans date backend : aucun label fabriqué', () => {
    const v = resolveValidity(makeProposal(), new Date(Date.UTC(2026, 5, 22)));
    expect(v.fromBackend).toBe(false);
    expect(v.label).toBeNull();
    expect(v.expired).toBe(false);
  });
});

// ── WJ9 · Argent dans le temps ───────────────────────────────────────────────

describe('WJ9 — économies cumulées + cadrage mensuel (depuis le backend)', () => {
  it('WJ75 — eco_a_cumul backend est un TAUX PAR AN (comme le moteur PDF), multiplié par years — jamais affiché tel quel', () => {
    // Le backend réel (apps/ventes/quote_engine/pricing.py) fixe
    // eco_a_cumul = economie_opt2 (= eco_a_ann) — PAS un total déjà cumulé — et
    // generate_devis_premium.py bâtit sa courbe par `eco_a_cumul * y`. Un fixture
    // à 16000 (légèrement différent de eco_a_ann=15000, pour prouver qu'on lit
    // BIEN eco_a_cumul et pas eco_a_ann) doit donc ressortir en `16000 × 25`, PAS
    // en `16000` brut (l'ancien bug affichait le taux annuel comme s'il s'agissait
    // déjà du cumul sur 25 ans — une sous-estimation ≈25× du chiffre le plus
    // visible de la page).
    const p = makeProposal({ quote: { eco_a_cumul: 16000 } });
    const h = savingsHeadline(p, 'avec_batterie', 25);
    expect(h.cumulative).toBe(16000 * 25);
    expect(h.cumulativeFromBackend).toBe(true);
    expect(h.annual).toBe(15000); // eco_a_ann, inchangé — distinct de eco_a_cumul
    expect(h.monthly).toBe(1250); // 15000 / 12
    expect(h.payback).toBe('7,2 ans');
  });

  it('cumul calculé depuis l’annuel × horizon quand eco_a_cumul absent', () => {
    const p = makeProposal();
    const h = savingsHeadline(p, 'avec_batterie', SAVINGS_HORIZON_YEARS);
    // inflation 0 % par défaut → 15000 × 25
    expect(h.cumulative).toBe(15000 * 25);
    expect(h.cumulativeFromBackend).toBe(false);
    expect(h.years).toBe(25);
  });

  it('option sans batterie utilise eco_s_ann / roi_s', () => {
    const h = savingsHeadline(makeProposal(), 'sans_batterie');
    expect(h.annual).toBe(12000);
    expect(h.monthly).toBe(1000);
    expect(h.payback).toBe('6,5 ans');
  });

  it('sans économie annuelle → aucun cumul fabriqué (null)', () => {
    const p = makeProposal({ quote: { eco_a_ann: undefined, eco_a_cumul: undefined } });
    const h = savingsHeadline(p, 'avec_batterie');
    expect(h.annual).toBeNull();
    expect(h.cumulative).toBeNull();
    expect(h.monthly).toBeNull();
  });
});

// ── WJ14 · Impact environnemental ────────────────────────────────────────────

describe('WJ14 — CO₂ évité ≈ arbres (calculé depuis la production, jamais inventé)', () => {
  it('calcule depuis prod_kwh avec les constantes affichées', () => {
    const impact = environmentalImpact(10000);
    expect(impact).not.toBeNull();
    // 10000 kWh × 0,81 kg = 8100 kg/an
    expect(impact!.co2KgPerYear).toBe(Math.round(10000 * CO2_KG_PER_KWH));
    expect(impact!.co2TonnesPerYear).toBe(8.1);
    // 8100 / 22 ≈ 368 arbres
    expect(impact!.trees).toBe(Math.round((10000 * CO2_KG_PER_KWH) / CO2_KG_PER_TREE_YEAR));
    expect(impact!.kgPerKwh).toBe(CO2_KG_PER_KWH);
    expect(impact!.kgPerTreeYear).toBe(CO2_KG_PER_TREE_YEAR);
  });

  it('production absente/nulle → null (repli libellé côté page)', () => {
    expect(environmentalImpact(undefined)).toBeNull();
    expect(environmentalImpact(0)).toBeNull();
    expect(environmentalImpact(-5)).toBeNull();
    expect(environmentalImpact(NaN)).toBeNull();
  });
});

// ── WJ10 · Financement ───────────────────────────────────────────────────────

describe('WJ10 — comparatif financement (cash backend + mensualité indicative)', () => {
  it('loanMonthlyPayment — formule amortissable, taux 0 = division', () => {
    expect(loanMonthlyPayment(84000, 0, 84)).toBe(1000);
    // 86400 @ 9 % sur 84 mois > paiement linéaire
    const m = loanMonthlyPayment(86400, 0.09, 84);
    expect(m).toBeGreaterThan(Math.round(86400 / 84));
  });

  it('cash vient du backend (TTC option) ; mensualités basse < haute', () => {
    const f = financingComparison(makeProposal(), 'avec_batterie');
    expect(f).not.toBeNull();
    expect(f!.cash).toBe(86400);
    expect(f!.monthlyLow).toBeLessThan(f!.monthlyHigh);
    expect(f!.months).toBe(84);
  });

  it('compare à la facture actuelle quand factures_mensuelles présent', () => {
    const p = makeProposal({ quote: { factures_mensuelles: Array(12).fill(2000) } });
    const f = financingComparison(p, 'sans_batterie');
    expect(f!.currentBillMonthly).toBe(2000);
    expect(typeof f!.beatsBill).toBe('boolean');
  });

  it('sans factures backend → accroche comparative masquée (null)', () => {
    const f = financingComparison(makeProposal(), 'avec_batterie');
    expect(f!.currentBillMonthly).toBeNull();
    expect(f!.beatsBill).toBe(false);
  });
});

// ── WJ12 · WhatsApp prérempli avec la réf devis ──────────────────────────────

describe('WJ12 — deep-link WhatsApp porte la référence du devis', () => {
  it('cite la référence dans le message', () => {
    const url = whatsappLink('DEV-2026-042');
    expect(url.startsWith(`https://wa.me/${TAQINOR_WHATSAPP}?text=`)).toBe(true);
    expect(decodeURIComponent(url)).toContain('DEV-2026-042');
  });

  it('numéro par défaut = numéro réel TAQINOR (jamais inventé)', () => {
    expect(TAQINOR_WHATSAPP).toBe('212661850410');
    expect(whatsappLink('DEV-1', '+212 661 850 410')).toContain('wa.me/212661850410');
  });

  it('sans référence → message générique valide', () => {
    const url = whatsappLink('');
    expect(url).toContain('wa.me/');
    expect(decodeURIComponent(url)).toContain('Taqinor');
  });
});

// ── WJ85 · Prérempli DISTINCT par intention (discuss/question/voice) ────────

describe('WJ85 — whatsappLinkForIntent : un message différent par intention, jamais le même lien', () => {
  it('discuss / question / voice produisent trois messages distincts', () => {
    const discuss = whatsappLinkForIntent('DEV-2026-042', 'discuss');
    const question = whatsappLinkForIntent('DEV-2026-042', 'question');
    const voice = whatsappLinkForIntent('DEV-2026-042', 'voice');
    expect(discuss).not.toBe(question);
    expect(discuss).not.toBe(voice);
    expect(question).not.toBe(voice);
    expect(decodeURIComponent(discuss)).toMatch(/discuter/i);
    expect(decodeURIComponent(question)).toMatch(/question précise/i);
    expect(decodeURIComponent(voice)).toMatch(/note vocale/i);
  });

  it('cite toujours la référence quand présente, pour les trois intentions', () => {
    for (const intent of ['discuss', 'question', 'voice'] as const) {
      const url = whatsappLinkForIntent('DEV-2026-042', intent);
      expect(decodeURIComponent(url)).toContain('DEV-2026-042');
    }
  });

  it('numéro par défaut = numéro réel TAQINOR (même garantie que whatsappLink)', () => {
    expect(whatsappLinkForIntent('DEV-1', 'question')).toContain(`wa.me/${TAQINOR_WHATSAPP}`);
  });

  it('sans référence → message générique valide (pas de "(réf. )" vide)', () => {
    const url = whatsappLinkForIntent('', 'discuss');
    expect(decodeURIComponent(url)).not.toContain('(réf.');
    expect(decodeURIComponent(url)).toContain('Taqinor');
  });
});

// ── WJ11 · Payload d'acceptation enrichi (rétro-compatible) ──────────────────

describe('WJ11 — payload e-signature enrichi reste rétro-compatible', () => {
  it('base inchangée (nom + option) quand aucune meta', () => {
    expect(buildAcceptBodyRich({ nom: ' Reda ', option: 'avec_batterie' }, true)).toEqual(
      buildAcceptBody({ nom: ' Reda ', option: 'avec_batterie' }, true),
    );
  });

  it('ajoute UNIQUEMENT des champs optionnels que le backend peut ignorer', () => {
    const body = buildAcceptBodyRich(
      { nom: 'Reda', option: 'avec_batterie' },
      true,
      { signature_data_url: 'data:image/png;base64,AAAA', consent_esign: true, signed_at_client: '2026-06-24T10:00:00Z' },
    );
    expect(body.nom).toBe('Reda');
    expect(body.option).toBe('avec_batterie');
    expect(body.signature_data_url).toBe('data:image/png;base64,AAAA');
    expect(body.consent_esign).toBe(true);
    expect(body.signed_at_client).toBe('2026-06-24T10:00:00Z');
  });

  it('omet les champs vides/false (corps minimal préservé)', () => {
    const body = buildAcceptBodyRich(
      { nom: 'Reda', option: null },
      false,
      { signature_data_url: '', consent_esign: false },
    );
    expect(body).toEqual({ nom: 'Reda' });
  });

  it('consentement non explicite → champ absent', () => {
    const body = buildAcceptBodyRich({ nom: 'Reda', option: null }, false, { consent_esign: undefined });
    expect('consent_esign' in body).toBe(false);
  });
});
