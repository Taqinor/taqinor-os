// CIW300 — /proposition C&I : l'énergie et l'argent sont LUS dans `synthese_ci`
// (la même fonction que le PDF), sans aucun calcul dans la page ; plus de cashflow
// linéaire ni de « × 25 », plus de mention 82-21 écrite dans la page.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  syntheseCi,
  argentCiCalcule,
  economieCiHero,
  injectionCi,
  motifsManquantsCi,
  ciEstUneEstimation,
  ciSousReserveVisite,
  chiffresEconomiePhare,
  savingsHeadline,
  type ProposalResponse,
} from '../src/lib/proposition';

const MENTION = {
  fr: 'Tarif de surplus ANRE : mention servie.',
  en: 'ANRE surplus tariff: served mention.',
  ar: 'تعريفة الفائض: نص مقدم.',
};

function argent(over: Record<string, unknown> = {}) {
  return {
    statut: 'calcule',
    motifs_omission: [],
    base: 'deux',
    motif_base: 'TVA récupérable non déclarée',
    tarif: {
      origine: 'grille_officielle',
      tarifs_par_poste: [{ poste: 'tranche_2', source: 'grille ONEE BT patenté', releve_le: '2026-10-03' }],
      mention: 'Grille ONEE, repli : prix TTC tels que publiés.',
    },
    economie_annee1: { total_mad: 98933.48, total_mad_ttc: 118717.39 },
    indicateurs: { retour_ans: 3 },
    revente: { statut: 'absente_bt', kwh_an: null, valeur_mad_an: null },
    ...over,
  };
}

function payload(mode: string, over: Record<string, unknown> = {}): ProposalResponse {
  return {
    reference: 'DEV-2026-300',
    date: '07/10/2026',
    client_name: 'Hôtel Exemple',
    statut: 'envoye',
    mode_installation: mode,
    quote: {
      ref: 'DEV-2026-300',
      date: '07/10/2026',
      client_name: 'Hôtel Exemple',
      totaux_sans: { ht_brut: 247500, remise: 0, ht_net: 247500, tva: 49500, ttc: 297000 },
      display_total: 297000,
      nb_options: 1,
      eco_s_ann: 24000,
      eco_a_ann: 31000,
      roi_s: 5.2,
      roi_a: 6.1,
      eco_a_cumul: 24000,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 297000, avec_batterie: 0, display_total: 297000, nb_options: 1 },
    accepted: false,
    mode_kpis: { taux_autoconso: 72.8, taux_couverture: 46.6, economies_annuelles: 24000, payback: 5.2, injection_kwh_an: 1000, injection_dh_an: 900 },
    ...over,
  } as unknown as ProposalResponse;
}

const SYNTHESE = {
  version: 1,
  segment: 'commercial',
  statut_etude: 'estimation_sous_reserve_visite',
  a_confirmer: [{ cle: 'puissance_souscrite_kva', libelle: 'Puissance souscrite, à relever' }],
  systeme: { kwc: 55, nb_panneaux: 100, production_kwh_an: 95425 },
  energie: {
    taux_autoconso_pct: 72.8,
    taux_couverture_pct: 46.6,
    methode: 'archetype_estimation',
    definitions: { autoconso: 'part de la production consommée sur place', couverture: 'part de votre consommation couverte' },
  },
  hypotheses: [{ cle: 'revente', textes: MENTION, source: 'ANRE', date: '2026-04-01' }],
  omissions: [{ bloc: 'argent.indicateurs.van_mad', motif: "aucun taux d'actualisation déclaré" }],
};

describe('CIW300 — syntheseCi (extracteur pur, lecture défensive)', () => {
  it('lit systeme / energie / argent tels que servis', () => {
    const ci = syntheseCi(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent() } }))!;
    expect(ci.systeme).toEqual({ kwc: 55, nbPanneaux: 100, productionKwhAn: 95425 });
    expect(ci.energie?.autoconsoPct).toBe(72.8);
    expect(ci.energie?.couverturePct).toBe(46.6);
    expect(ci.energie?.definitions.couverture).toContain('couverte');
    expect(ci.argent?.economieAnnee1).toEqual({ ht: 98933.48, ttc: 118717.39 });
    expect(ci.argent?.retourAns).toBe(3);
    expect(ci.argent?.tarif?.source).toBe('grille ONEE BT patenté');
    expect(ci.aConfirmer).toHaveLength(1);
  });

  it('clé absente → null, jamais un 0 fabriqué', () => {
    expect(syntheseCi(payload('commercial'))).toBeNull();
    expect(syntheseCi(payload('commercial', { synthese_ci: {} }))).toBeNull();
    const vide = syntheseCi(payload('industriel', { synthese_ci: { version: 1 } }))!;
    expect(vide.systeme).toBeNull();
    expect(vide.energie).toBeNull();
    expect(vide.argent).toBeNull();
    const partiel = syntheseCi(payload('industriel', { synthese_ci: { systeme: { kwc: '55' } } }))!;
    expect(partiel.systeme?.kwc).toBeNull(); // une chaîne n'est jamais convertie
  });

  it('null hors commercial / industriel (zéro fuite inter-mode)', () => {
    for (const m of ['residentiel', 'agricole', '']) {
      expect(syntheseCi(payload(m, { synthese_ci: SYNTHESE }))).toBeNull();
    }
  });

  it('étiquette « estimation », réserve de visite et motifs manquants', () => {
    const ci = syntheseCi(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent() } }));
    expect(ciEstUneEstimation(ci)).toBe(true);
    expect(ciSousReserveVisite(ci)).toBe(true);
    expect(motifsManquantsCi(ci)).toEqual(["aucun taux d'actualisation déclaré"]);
    const ferme = syntheseCi(
      payload('commercial', { synthese_ci: { ...SYNTHESE, statut_etude: 'offre_ferme', energie: { ...SYNTHESE.energie, methode: 'horaire_declare' } } }),
    );
    expect(ciEstUneEstimation(ferme)).toBe(false);
    expect(ciSousReserveVisite(ferme)).toBe(false);
  });
});

describe('CIW300 — chiffresEconomiePhare lit synthese_ci en C&I', () => {
  it('quote.eco_s_ann rempli mais PAS de synthese_ci.argent → aucun chiffre d\'argent', () => {
    for (const m of ['commercial', 'industriel']) {
      for (const synth of [undefined, { ...SYNTHESE }, { ...SYNTHESE, argent: argent({ statut: 'omis', economie_annee1: undefined }) }]) {
        const r = chiffresEconomiePhare(payload(m, synth ? { synthese_ci: synth } : {}), 'sans_batterie');
        expect(r).toEqual({ ecoSans: null, ecoAvec: null, paybackSans: null, paybackAvec: null, ecoHero: null, paybackHero: null });
      }
    }
  });

  it('avec synthese_ci.argent → valeurs servies (HT quand la base est « deux », TTC quand « ttc »)', () => {
    const r = chiffresEconomiePhare(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent() } }), 'sans_batterie');
    expect(r.ecoHero).toBe(98933.48);
    expect(r.paybackHero).toBe(chiffresEconomiePhare(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent() } })).paybackSans);
    expect(r.paybackHero).toContain('3');
    const ttc = chiffresEconomiePhare(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent({ base: 'ttc' }) } }));
    expect(ttc.ecoHero).toBe(118717.39);
    // jamais la valeur résidentielle 24000
    expect(r.ecoHero).not.toBe(24000);
  });

  it('economieCiHero / argentCiCalcule : omis → null', () => {
    const ci = syntheseCi(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent({ statut: 'omis' }) } }));
    expect(argentCiCalcule(ci)).toBeNull();
    expect(economieCiHero(argentCiCalcule(ci))).toBeNull();
  });

  it('savingsHeadline ne sert plus le C&I (plus de « × 25 »)', () => {
    const h = savingsHeadline(payload('industriel'), 'sans_batterie');
    expect(h.cumulative).toBeNull();
    expect(h.annual).toBeNull();
    // le résidentiel est inchangé
    expect(savingsHeadline(payload('residentiel', { economies_cumul_25_ans: { sans_batterie: 512000 } }), 'sans_batterie').cumulative).toBe(512000);
  });
});

describe('CIW300 — bloc injection (loi 82-21) : seulement si la revente est SERVIE', () => {
  it('BT : mode_kpis.injection_dh_an rempli mais revente non servie → aucun bloc', () => {
    const ci = syntheseCi(payload('commercial', { synthese_ci: { ...SYNTHESE, argent: argent() } }));
    expect(injectionCi(ci)).toBeNull();
  });

  it('MT : revente calculée → valeurs servies et mention servie', () => {
    const ci = syntheseCi(
      payload('industriel', {
        synthese_ci: { ...SYNTHESE, argent: argent({ revente: { statut: 'calculee', kwh_an: 12000, valeur_mad_an: 8400 } }) },
      }),
    );
    const inj = injectionCi(ci)!;
    expect(inj.kwhAn).toBe(12000);
    expect(inj.valeurMadAn).toBe(8400);
    expect(inj.mention).toEqual(MENTION);
  });

  it('MT revente servie sans mention dans hypotheses → bloc omis (aucune mention de repli)', () => {
    const ci = syntheseCi(
      payload('industriel', {
        synthese_ci: { ...SYNTHESE, hypotheses: [], argent: argent({ revente: { statut: 'calculee', kwh_an: 1, valeur_mad_an: 1 } }) },
      }),
    );
    expect(injectionCi(ci)).toBeNull();
  });
});

describe('CIW300 — la page ne calcule plus, ne code plus de mention 82-21', () => {
  const page = readFileSync(
    fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
    'utf-8',
  );
  it('aucun « plafond en révision » ni cashflow codé dans la page', () => {
    expect(page).not.toMatch(/plafond en révision/);
    expect(page).not.toMatch(/autoconsoCashflow|autoCashflow|cashBreakEven/);
    expect(page).not.toMatch(/Votre trésorerie sur 10 ans/);
  });
  it('le bloc injection lit injectionCi et le headline × 25 ne sert pas le C&I', () => {
    expect(page).toContain('const ciInjection = injectionCi(ci);');
    expect(page).toContain('const headline = ok && !isAutoconso ?');
    expect(page).toContain('data-figure="economie_annuelle"');
  });
});
