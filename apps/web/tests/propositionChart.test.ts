// P1/P2/P3 — Nouvelles formes de la proposition (graphe + PDF) côté lib/proposition.
// On teste UNIQUEMENT la logique pure ajoutée : URL du devis PDF, lecture
// défensive des tableaux mensuels Q6, et la condition d'affichage du graphe.
import { describe, expect, it } from 'vitest';
import {
  proposalPdfEndpoint,
  monthlySeries,
  hasProductionSeries,
  type ProposalResponse,
} from '../src/lib/proposition';

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-001',
    date: '22/06/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-001',
      date: '22/06/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      totaux_sans: { ht_brut: 50000, remise: 0, ht_net: 50000, tva: 10000, ttc: 60000 },
    },
    roof_image_url: 'https://api.taqinor.ma/media/roof/abc.png',
    option_totals: { sans_batterie: 60000, avec_batterie: 0, display_total: 60000, nb_options: 1 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

const PROD = [800, 900, 1100, 1300, 1500, 1600, 1700, 1650, 1400, 1100, 850, 750];

describe('proposalPdfEndpoint (P3)', () => {
  it('construit l’URL /pdf/ avec le token encodé', () => {
    expect(proposalPdfEndpoint('https://api.taqinor.ma', 'abc123')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/abc123/pdf/',
    );
  });
  it('strip du slash final de la base + encode le token', () => {
    expect(proposalPdfEndpoint('https://api.taqinor.ma/', 'a b')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/a%20b/pdf/',
    );
  });
  it('base vide → défaut api.taqinor.ma', () => {
    expect(proposalPdfEndpoint('', 'tok')).toBe(
      'https://api.taqinor.ma/api/django/ventes/proposal/tok/pdf/',
    );
  });
});

describe('monthlySeries (P2)', () => {
  it('12 valeurs valides → tableau nettoyé', () => {
    expect(monthlySeries(PROD)).toHaveLength(12);
  });
  it('vide / mauvaise taille / null → null', () => {
    expect(monthlySeries([])).toBeNull();
    expect(monthlySeries([1, 2, 3])).toBeNull();
    expect(monthlySeries(undefined)).toBeNull();
    expect(monthlySeries(null)).toBeNull();
  });
  it('tout-zéro → null (rien à montrer)', () => {
    expect(monthlySeries(new Array(12).fill(0))).toBeNull();
  });
  it('valeurs non finies / négatives écrasées à 0', () => {
    const r = monthlySeries([NaN, -10, 500, ...new Array(9).fill(100)]);
    expect(r?.[0]).toBe(0);
    expect(r?.[1]).toBe(0);
    expect(r?.[2]).toBe(500);
  });
});

describe('hasProductionSeries (P2 — condition d’affichage du graphe)', () => {
  it('production présente → true', () => {
    expect(hasProductionSeries(makeProposal({ monthly_production: PROD }))).toBe(true);
  });
  it('production absente / vide → false (même si conso présente)', () => {
    expect(hasProductionSeries(makeProposal())).toBe(false);
    expect(hasProductionSeries(makeProposal({ monthly_production: [] }))).toBe(false);
    expect(
      hasProductionSeries(makeProposal({ monthly_production: [], monthly_consumption: PROD })),
    ).toBe(false);
  });
});
