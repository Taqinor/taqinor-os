// CIW308 — /proposition industrielle : la rentabilité sur 25 ans du PDF, lue telle quelle
// (`synthese_ci.argent`), et des ancres par lecteur (direction, exploitation, achats).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { rentabiliteCi, syntheseCi, type ProposalResponse } from '../src/lib/proposition';

const JALONS = [
  { annee: 5, cumul_mad: 331750.0 },
  { annee: 10, cumul_mad: 1563500.0 },
  { annee: 15, cumul_mad: 2657750.01 },
  { annee: 20, cumul_mad: 3889500.01 },
  { annee: 25, cumul_mad: 5121250.01 },
];

function argent(over: Record<string, unknown> = {}) {
  return {
    statut: 'calcule',
    base: 'ht',
    economie_annee1: { total_mad: 400000 },
    indicateurs: {
      tri_pct: 27.0053,
      tri_horizon_ans: 25,
      retour_ans: 4,
      van_mad: 1670759.73,
      van_motif: null,
      lcoe_mad_kwh: 0.1221,
      lcoe_actualise: false,
      tarif_kwh_evite_moyen: 0.8407,
    },
    jalons: JALONS,
    sensibilites: [],
    flux_ht: { hypotheses: [{ cle: 'taux_actualisation_pct', valeur: 8 }] },
    ...over,
  };
}

function payload(mode: string, a: unknown, segment = mode): ProposalResponse {
  return {
    reference: 'DEV-2026-308',
    date: '07/10/2026',
    client_name: 'Usine Exemple',
    statut: 'envoye',
    mode_installation: mode,
    quote: {},
    synthese_ci: { segment, ...(a === undefined ? {} : { argent: a }) },
  } as unknown as ProposalResponse;
}

describe('CIW308 — rentabiliteCi (extracteur pur)', () => {
  it('jalons servis → 5 lignes (5/10/15/20/25), TRI sur N ans, LCOE face au tarif', () => {
    const r = rentabiliteCi(syntheseCi(payload('industriel', argent())))!;
    expect(r.jalons.map((j) => j.annee)).toEqual([5, 10, 15, 20, 25]);
    expect(r.jalons[4].cumul).toBe(5121250.01);
    expect(r.triPct).toBe(27.0053);
    expect(r.triHorizonAns).toBe(25);
    expect(r.lcoeMadKwh).toBe(0.1221);
    expect(r.tarifKwhEvite).toBe(0.8407);
  });

  it('VAN servie (taux déclaré) → reprise ; VAN absente → bloc omis (null)', () => {
    const avec = rentabiliteCi(syntheseCi(payload('industriel', argent())))!;
    expect(avec.vanMad).toBe(1670759.73);
    expect(avec.tauxActualisationPct).toBe(8);
    const sans = rentabiliteCi(
      syntheseCi(payload('industriel', argent({ indicateurs: { tri_pct: 27, tri_horizon_ans: 25, van_mad: null, van_motif: 'aucun taux déclaré' }, flux_ht: {} }))),
    )!;
    expect(sans.vanMad).toBeNull();
    expect(sans.tauxActualisationPct).toBeNull();
  });

  it('jamais un jalon inventé : seuls les jalons servis, parmi 5/10/15/20/25', () => {
    const r = rentabiliteCi(
      syntheseCi(payload('industriel', argent({ jalons: [{ annee: 5, cumul_mad: 1 }, { annee: 7, cumul_mad: 2 }, { annee: 25, cumul_mad: 3 }] }))),
    )!;
    expect(r.jalons.map((j) => j.annee)).toEqual([5, 25]);
  });

  it('base « ttc » → jalons TTC ; base « deux » → HT + colonne TTC', () => {
    const jTtc = [{ annee: 5, cumul_mad: 400000 }, { annee: 25, cumul_mad: 6000000 }];
    expect(rentabiliteCi(syntheseCi(payload('industriel', argent({ base: 'ttc', jalons_ttc: jTtc }))))!.jalons[1].cumul).toBe(6000000);
    const deux = rentabiliteCi(syntheseCi(payload('industriel', argent({ base: 'deux', jalons_ttc: jTtc }))))!;
    expect(deux.jalons[1].cumul).not.toBe(6000000);
    expect(deux.jalonsTtc.map((j) => j.cumul)).toEqual([400000, 6000000]);
  });

  it('sensibilités et financement seulement s\'ils sont servis', () => {
    const r0 = rentabiliteCi(syntheseCi(payload('industriel', argent())))!;
    expect(r0.sensibilites).toEqual([]);
    expect(r0.financement).toBeNull();
    const r1 = rentabiliteCi(
      syntheseCi(
        payload(
          'industriel',
          argent({
            sensibilites: [{ cle: 'tarif', variation_pct: -10, retour_ans: 4.6, tri_pct: 24.1 }],
            financement: { libelle_client: 'Offre de crédit', echeance_mad: 12000, duree_mois: 84, economie_mensuelle_moyenne_mad: 20529.17, ecart_mensuel_mad: 8529.17 },
          }),
        ),
      ),
    )!;
    expect(r1.sensibilites[0]).toMatchObject({ cle: 'tarif', variationPct: -10, retourAns: 4.6, triPct: 24.1 });
    expect(r1.financement?.echeanceMad).toBe(12000);
    expect(r1.financement?.dureeMois).toBe(84);
  });

  it('argent omis, absent ou hors industriel → null (section omise)', () => {
    expect(rentabiliteCi(syntheseCi(payload('industriel', argent({ statut: 'omis' }))))).toBeNull();
    expect(rentabiliteCi(syntheseCi(payload('industriel', undefined)))).toBeNull();
    expect(rentabiliteCi(syntheseCi(payload('commercial', argent())))).toBeNull();
    expect(rentabiliteCi(null)).toBeNull();
  });
});

describe('CIW308 — la page : ancres par lecteur et figures data-figure', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
  it('ancres #direction, #exploitation, #achats', () => {
    expect(page).toContain('id="direction"');
    expect(page).toContain('id="exploitation"');
    expect(page).toContain('id="achats"');
  });
  it('ancres data-figure tri_pct, cumul_net_25_ans_mad et lcoe_mad_kwh', () => {
    expect(page).toContain('data-figure="tri_pct"');
    expect(page).toContain("'cumul_net_25_ans_mad'");
    expect(page).toContain('data-figure="lcoe_mad_kwh"');
  });
  it('la section lit `rentabiliteCi` (aucun calcul dans la page) et n\'imprime aucune statistique de comité d\'achat', () => {
    expect(page).toContain("const ciRent = ok && installMode === 'industriel' ? rentabiliteCi(ci) : null;");
    expect(page).not.toMatch(/comités? d['’]achat/i);
  });
});
