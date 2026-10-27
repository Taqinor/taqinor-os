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
  bandeauPreliminaireCi,
  lignePostesHorsTotalCi,
  CI_DEVIS_PRELIMINAIRE,
  chiffresEconomiePhare,
  savingsHeadline,
  type ProposalResponse,
} from '../src/lib/proposition';
import { lirePageProposition } from './astroBlocsHelper';

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
  const page = lirePageProposition();
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

// CPRW2 (27/10/2026) — « Tarif utilisé » : le texte CLIENT servi, jamais la note interne.
const SRC_AUTOCONSO = readFileSync(
  fileURLToPath(new URL('../src/components/proposition/ci/SectionAutoconso.astro', import.meta.url)),
  'utf-8',
).replace(/\r\n/g, '\n');
describe('CPRW2 — tarif utilisé = hypothèse servie', () => {
  it('lit synthese_ci.hypotheses[cle=tarif].textes, jamais tarif.mention / tarif.source', () => {
    expect(SRC_AUTOCONSO).toContain("h.cle === 'tarif'");
    expect(SRC_AUTOCONSO).not.toMatch(/tarif\.mention/);
    expect(SRC_AUTOCONSO).not.toMatch(/tarif\.source/);
  });
});

// CPRW3 (27/10/2026) — bandeau « devis préliminaire » = l'hypothèse `visite` servie (FR/EN/AR).
describe('CPRW3 — bandeau devis préliminaire', () => {
  it('rendu dès que le serveur sert l\'hypothèse visite ; plus de liste interne « à confirmer »', () => {
    expect(SRC_AUTOCONSO).toContain('bandeauPreliminaireCi(ci)');
    expect(SRC_AUTOCONSO).toContain('data-ci-preliminaire');
    expect(SRC_AUTOCONSO).not.toContain('Estimation sous réserve de la visite technique');
    expect(SRC_AUTOCONSO).not.toContain('aConfirmer');
  });
});

// CPRW3 — sur TOUT devis C&I (le PDF l'imprime toujours) : texte servi, sinon le MÊME que le PDF.
describe('CPRW3 — bandeau préliminaire toujours présent en C&I', () => {
  const base = { mode_installation: 'commercial', synthese_ci: { hypotheses: [] } } as unknown as ProposalResponse;
  it('sans hypothèse visite servie : le texte du PDF ; hors C&I : rien', () => {
    expect(bandeauPreliminaireCi(syntheseCi(base))).toEqual(CI_DEVIS_PRELIMINAIRE);
    expect(bandeauPreliminaireCi(null)).toBeNull();
  });
  it('avec hypothèse visite servie : le texte servi', () => {
    const servi = { fr: 'A', en: 'B', ar: 'C' };
    const p = { mode_installation: 'commercial', synthese_ci: { hypotheses: [{ cle: 'visite', textes: servi, source: null }] } } as unknown as ProposalResponse;
    expect(bandeauPreliminaireCi(syntheseCi(p))).toEqual(servi);
  });
  it('parité mot pour mot avec ci/mentions.py::TEXTES_VISITE', () => {
    const py = readFileSync(fileURLToPath(new URL('../../../backend/django_core/apps/ventes/quote_engine/ci/mentions.py', import.meta.url)), 'utf-8');
    const bloc = py.slice(py.indexOf('TEXTES_VISITE = {'), py.indexOf('}', py.indexOf('TEXTES_VISITE = {')));
    const joint = (lg: string) => [...bloc.split(`"${lg}":`)[1]!.split(/\s"(?:fr|en|ar)":/)[0]!.matchAll(/"([^"]*)"/g)].map((m) => m[1]).join('');
    expect(joint('fr')).toBe(CI_DEVIS_PRELIMINAIRE.fr);
    expect(joint('en')).toBe(CI_DEVIS_PRELIMINAIRE.en);
    expect(joint('ar')).toBe(CI_DEVIS_PRELIMINAIRE.ar);
  });
});

// CPRW4 (27/10/2026) — plus de badge « estimation » ni de motifs d'omission bruts côté client.
describe('CPRW4 — ni badge estimation ni « Ce qu\'il nous manque »', () => {
  it('le composant ne rend plus ces deux blocs', () => {
    expect(SRC_AUTOCONSO).not.toContain('data-ci-manque');
    expect(SRC_AUTOCONSO).not.toContain("Ce qu'il nous manque");
    expect(SRC_AUTOCONSO).not.toContain('ciEstimation');
    expect(SRC_AUTOCONSO).not.toMatch(/data-fr="estimation"/);
  });
});

// CPRW5 (27/10/2026) — suffixes TTC/HT trilingues, motif de la base servi sous la carte.
describe('CPRW5 — TTC/HT trilingues, motif de base interne non affiché', () => {
  it('plus de suffixe FR en dur ; libellés FR/EN/AR ; motif de base interne jamais affiché', () => {
    expect(SRC_AUTOCONSO).not.toContain("' TTC'");
    expect(SRC_AUTOCONSO).not.toContain("' HT'");
    expect(SRC_AUTOCONSO).toContain('incl. VAT');
    expect(SRC_AUTOCONSO).toContain('excl. VAT');
    expect(SRC_AUTOCONSO).toContain('شامل الضريبة');
    expect(SRC_AUTOCONSO).toContain('دون احتساب الضريبة');
    // `argent.motif_base` est une note interne FR (« … (D-CIQ-3) ») : JAMAIS affichée au client.
    expect(SRC_AUTOCONSO).not.toContain('motifBase');
  });
});

// CPRW13 (27/10/2026) — « À chiffrer après la visite technique (hors total) : <postes> » sous le bandeau, comme le PDF.
describe('CPRW13 — postes hors total sous le bandeau préliminaire', () => {
  const avec = (postes: unknown) =>
    ({ mode_installation: 'industriel', synthese_ci: { hypotheses: [], postes_hors_total: postes } }) as unknown as ProposalResponse;
  const py = readFileSync(
    fileURLToPath(new URL('../../../backend/django_core/apps/ventes/quote_engine/i18n_labels.py', import.meta.url)),
    'utf-8',
  );
  it('absent ou vide : aucune ligne (lecture défensive)', () => {
    expect(lignePostesHorsTotalCi(syntheseCi(avec(undefined)))).toBeNull();
    expect(lignePostesHorsTotalCi(syntheseCi(avec([])))).toBeNull();
    expect(lignePostesHorsTotalCi(syntheseCi(avec('x')))).toBeNull();
    expect(lignePostesHorsTotalCi(null)).toBeNull();
  });
  it('rôle en mots simples FR/EN/AR, article du catalogue après « — », sans doublon, jamais un montant', () => {
    const ligne = lignePostesHorsTotalCi(
      syntheseCi(
        avec([
          { role: 'cable_dc', designation: 'Câble solaire Nexans', quantite: 120, unite: 'm', catalogue: true },
          { role: 'structure_ci', designation: 'Structure C&I', quantite: 1, unite: 'ens', catalogue: false },
          { role: 'cable_ac', designation: 'Câble AC générique', quantite: 10, unite: 'm', catalogue: false },
          { role: 'cable_ac', designation: 'Câble AC générique 2', quantite: 5, unite: 'm', catalogue: false },
          { role: 'role_inconnu', designation: 'Poste libre', quantite: 1, unite: null, catalogue: false },
        ]),
      ),
    )!;
    expect(ligne.fr).toBe(
      'À chiffrer après la visite technique (hors total) : câble DC — Câble solaire Nexans, structure de fixation, câble AC, Poste libre',
    );
    expect(ligne.en).toBe(
      'To be priced after the site visit (not in the total): DC cable — Câble solaire Nexans, mounting structure, AC cable, Poste libre',
    );
    expect(ligne.ar).toContain('يُسعَّر بعد الزيارة التقنية (خارج المجموع): ');
    expect(ligne.ar).toContain('كابل التيار المستمر — Câble solaire Nexans');
    expect(ligne.fr).not.toMatch(/MAD|DH|\d/);
  });
  it('parité des mots avec i18n_labels.py (ci_a_chiffrer_hors_total, ci_role_*)', () => {
    const ligne = lignePostesHorsTotalCi(
      syntheseCi(avec([{ role: 'coffret_dc', designation: 'X', quantite: 1, unite: null, catalogue: false }])),
    )!;
    for (const lg of ['fr', 'en', 'ar'] as const) {
      const ligneTxt = ligne[lg].split(':')[0]!;
      expect(py).toContain(ligneTxt);
    }
    for (const mot of ['câble DC', 'DC cable', 'كابل التيار المستمر', 'structure de fixation', 'mounting structure', 'هيكل التثبيت', 'coffret DC', 'DC box', 'علبة التيار المستمر', 'protection AC', 'AC protection', 'حماية التيار المتردد', 'onduleur', 'inverter', 'العاكس']) {
      expect(py).toContain(mot);
    }
  });
  it('SectionAutoconso affiche la ligne sous le bandeau, en FR/EN/AR', () => {
    expect(SRC_AUTOCONSO).toContain('lignePostesHorsTotalCi(ci)');
    expect(SRC_AUTOCONSO).toContain('data-ci-postes-hors-total');
    expect(SRC_AUTOCONSO).toMatch(/data-fr=\{postesHorsTotal\.fr\} data-en=\{postesHorsTotal\.en\} data-ar=\{postesHorsTotal\.ar\}/);
  });
});

// ── CPRW15 — garanties servies en C&I ───────────────────────────────────────────────────────
import { garantiesCi, LBL_GARANTIES_CI, LEGENDE_GARANTIES_CI } from '../src/components/proposition/ci/blocsCi';
import { garantiesCodeesEnDurAffichees } from '../src/lib/propositionPage';

const PY_LABELS = readFileSync(fileURLToPath(new URL('../../../backend/django_core/apps/ventes/quote_engine/i18n_labels.py', import.meta.url)), 'utf-8');
function labelPy(cle: string): { fr: string; en: string; ar: string } {
  const i = PY_LABELS.indexOf(`'${cle}': {`);
  const bloc = PY_LABELS.slice(i, PY_LABELS.indexOf('},', i));
  const joint = (lg: string) => {
    const tranche = bloc.split(`'${lg}':`)[1]!.split(/\s'(?:fr|en|ar)':/)[0]!;
    return [...tranche.matchAll(/(["'])((?:(?!\1).)*)\1/g)].map((m) => m[2]).join('');
  };
  return { fr: joint('fr'), en: joint('en'), ar: joint('ar') };
}
const pCi = (services: unknown) =>
  ({ mode_installation: 'commercial', synthese_ci: { services } }) as unknown as ProposalResponse;

describe('CPRW15 — garanties C&I servies', () => {
  it('le bloc en dur (onduleur 10 ans…) n\'est plus affiché en commercial ni en industriel', () => {
    expect(garantiesCodeesEnDurAffichees('commercial')).toBe(false);
    expect(garantiesCodeesEnDurAffichees('industriel')).toBe(false);
    expect(garantiesCodeesEnDurAffichees('residentiel')).toBe(true);
  });
  it('« Onduleur : 10 ans » → 10 (jamais 30) ; ancien « Garantie constructeur 10 ans » accepté', () => {
    const g = syntheseCi(pCi({ garanties: [
      { composant: 'onduleur', texte: 'Onduleur : 10 ans', source: 'garantie du fabricant' },
      { composant: 'panneaux', texte: 'Garantie constructeur 12 ans', source: 'x' },
      { composant: 'panneaux_performance', texte: 'Performance : 30 ans', source: 'x' },
    ] }))!.services!.garanties;
    expect(g.map((x) => [x.composant, x.annees])).toEqual([['onduleur', 10], ['panneaux', 12], ['panneaux_performance', 30]]);
    expect(garantiesCi(syntheseCi(pCi({ garanties: [{ composant: 'onduleur', texte: 'Onduleur : 10 ans' }] })))).toEqual([
      { composant: 'onduleur', libelle: LBL_GARANTIES_CI.onduleur, annees: 10 },
    ]);
  });
  it('garanties vides, texte sans durée ou composant inconnu → aucune ligne (jamais un défaut)', () => {
    expect(garantiesCi(syntheseCi(pCi({ garanties: [] })))).toEqual([]);
    expect(garantiesCi(syntheseCi(pCi({})))).toEqual([]);
    expect(garantiesCi(syntheseCi(pCi({ garanties: [{ composant: 'onduleur', texte: 'Onduleur : n.c.' }, { composant: 'zzz', texte: 'Z : 5 ans' }] })))).toEqual([]);
    expect(garantiesCi(null)).toEqual([]);
  });
  it('parité des libellés et de la légende avec i18n_labels.py (ci_garantie_*, ci_legende_garanties)', () => {
    expect(LBL_GARANTIES_CI.onduleur).toEqual(labelPy('ci_garantie_onduleur'));
    expect(LBL_GARANTIES_CI.panneaux).toEqual(labelPy('ci_garantie_panneaux'));
    expect(LBL_GARANTIES_CI.panneaux_performance).toEqual(labelPy('ci_garantie_performance'));
    expect(LBL_GARANTIES_CI.batterie).toEqual(labelPy('ci_garantie_batterie'));
    expect(LBL_GARANTIES_CI.installation).toEqual(labelPy('ci_garantie_installation'));
    expect(LEGENDE_GARANTIES_CI).toEqual(labelPy('ci_legende_garanties'));
  });
  it('la page appelle GarantiesCi après GarantiesAgricoles ; la pose vient de INSTALL_WARRANTY_YEARS', () => {
    const page = lirePageProposition();
    expect(page).toContain('data-ci-garanties');
    expect(page.indexOf('data-agri-garanties')).toBeLessThan(page.indexOf('data-ci-garanties'));
    expect(readFileSync(fileURLToPath(new URL('../src/components/proposition/ci/GarantiesCi.astro', import.meta.url)), 'utf-8')).toContain('INSTALL_WARRANTY_YEARS');
  });
});

// ── CPRW23 — les postes à chiffrer sont lus dans a_confirmer[a_chiffrer_visite].postes ──────
describe('CPRW23 — postes à chiffrer après visite : lecture du payload public', () => {
  const poste = { role: 'cable_dc', designation: 'Câble solaire 6 mm²', quantite: 1, unite: null, catalogue: false };
  const p = (synthese: Record<string, unknown>) => ({ mode_installation: 'industriel', synthese_ci: { hypotheses: [], ...synthese } }) as unknown as ProposalResponse;
  it('lit a_confirmer[a_chiffrer_visite].postes ; les autres entrées ne sont jamais réaffichées', () => {
    const ci = syntheseCi(p({ a_confirmer: [{ cle: 'tension', libelle: 'Tension à confirmer' }, { cle: 'a_chiffrer_visite', postes: [poste] }] }))!;
    expect(ci.postesHorsTotal).toEqual([{ role: 'cable_dc', designation: 'Câble solaire 6 mm²', catalogue: false }]);
    expect(lignePostesHorsTotalCi(ci)!.fr).toContain('câble DC');
    expect(lignePostesHorsTotalCi(ci)!.fr).not.toContain('Tension');
  });
  it('repli sur postes_hors_total seulement s\'il est servi ; rien sinon', () => {
    expect(syntheseCi(p({ postes_hors_total: [poste] }))!.postesHorsTotal).toHaveLength(1);
    expect(syntheseCi(p({ a_confirmer: [{ cle: 'tension', libelle: 'T' }] }))!.postesHorsTotal).toEqual([]);
  });
});

// ── CPRW16 — échéancier de paiement servi ───────────────────────────────────────────────────
import { echeancierCi, JALONS_CI, TITRE_ECHEANCIER_CI } from '../src/components/proposition/ci/blocsCi';

describe('CPRW16 — échéancier C&I', () => {
  const ech = (echeancier: unknown) => syntheseCi(({ mode_installation: 'industriel', synthese_ci: { echeancier } }) as unknown as ProposalResponse);
  it('40/50/10 → 3 cartes, somme 100, jalons traduits, montants servis', () => {
    const lignes = echeancierCi(ech([
      { libelle: 'À la commande', pct: 40, montant_ttc: 40000, jalon: 'commande' },
      { libelle: 'À la livraison', pct: 50, montant_ttc: 50000, jalon: 'livraison' },
      { libelle: 'À la mise en service', pct: 10, montant_ttc: 10000, jalon: 'mise_en_service' },
    ]));
    expect(lignes).toHaveLength(3);
    expect(lignes.reduce((s, l) => s + l.pct, 0)).toBe(100);
    expect(lignes[0]!.libelle).toEqual(JALONS_CI.commande);
    expect(lignes.map((l) => l.montantTtc)).toEqual([40000, 50000, 10000]);
  });
  it('montant_ttc null ou 0 → aucun montant ; jalon inconnu → libellé servi ; absent → rien', () => {
    const l = echeancierCi(ech([{ libelle: 'Jalon X', pct: 100, montant_ttc: null, jalon: 'zzz' }, { libelle: 'Y', pct: 0, montant_ttc: 0, jalon: 'commande' }]));
    expect(l[0]).toMatchObject({ montantTtc: null, libelle: { fr: 'Jalon X', en: 'Jalon X', ar: 'Jalon X' } });
    expect(l[1]!.montantTtc).toBeNull();
    expect(echeancierCi(ech([]))).toEqual([]);
    expect(echeancierCi(null)).toEqual([]);
  });
  it('parité des libellés avec i18n_labels.py (ci_jalon_*, ci_echeancier)', () => {
    for (const j of ['commande', 'livraison', 'mise_en_service', 'reception_definitive']) expect(JALONS_CI[j]).toEqual(labelPy(`ci_jalon_${j}`));
    expect(TITRE_ECHEANCIER_CI).toEqual(labelPy('ci_echeancier'));
  });
  it('la page appelle EcheancierCi avant l\'ancre achats', () => {
    const page = lirePageProposition();
    expect(page.indexOf('data-ci-echeancier')).toBeGreaterThan(-1);
    expect(page.indexOf('data-ci-echeancier')).toBeLessThan(page.indexOf('id="achats"'));
  });
});

// ── CPRW17 — services servis (O&M, suivi de production, raccordement) ──────────────────────
import { servicesCi, LBL_SERVICES_CI } from '../src/components/proposition/ci/blocsCi';

describe('CPRW17 — services C&I', () => {
  const svc = (services: unknown) => syntheseCi(({ mode_installation: 'industriel', synthese_ci: { services } }) as unknown as ProposalResponse);
  const decode = (t: string) => t.replace(/&amp;/g, '&').replace(/&#160;/g, ' ');
  it('parité des mots avec i18n_labels.py', () => {
    for (const [cle, lbl] of Object.entries(LBL_SERVICES_CI)) {
      const py = labelPy(`ci_${cle}`);
      for (const lg of ['fr', 'en', 'ar'] as const) expect(lbl[lg]).toBe(decode(py[lg]));
    }
  });
  it('O&M proposé sans prix : « tarif sur demande » + « non inclus dans le total »', () => {
    const l = servicesCi(svc({ om_option: { statut: 'propose', libelle: 'Maintenance annuelle', lignes: [{ designation: 'Maintenance annuelle', total_ht: null, total_ttc: null }] } }))!;
    expect(l.lignes).toHaveLength(1);
    expect(l.lignes[0]!.fr).toBe('Maintenance (O&M) : Maintenance annuelle — tarif sur demande (proposé, non inclus dans le total)');
    expect(l.lignes[0]!.en).toContain('price on request');
    expect(l.lignes[0]!.ar).toContain('السعر عند الطلب');
  });
  it('O&M souscrit avec prix servi : prix HT, pas de « non inclus »', () => {
    const l = servicesCi(svc({ om_option: { statut: 'souscrit', libelle: 'X', lignes: [{ designation: 'X', total_ht: 12000, total_ttc: 14400 }] } }))!;
    expect(l.lignes[0]!.fr).toContain('12 000 MAD HT');
    expect(l.lignes[0]!.fr).not.toContain('non inclus');
  });
  it('suivi : « inclus » sans délai (jamais 0 h), délai seulement s\'il est servi', () => {
    expect(servicesCi(svc({ suivi_production: { delai_intervention: null } }))!.lignes[0]!.fr).toBe('Suivi de production inclus');
    expect(servicesCi(svc({ suivi_production: { delai_intervention: 0 } }))!.lignes[0]!.fr).toBe('Suivi de production inclus');
    expect(servicesCi(svc({ suivi_production: { delai_intervention: 48 } }))!.lignes[0]!.fr).toBe('Suivi de production : intervention sous 48 h');
  });
  it('raccordement : la phrase du PDF si un régime est servi ; rien sinon', () => {
    const l = servicesCi(svc({ raccordement: { regime: 'autoproduction' } }))!;
    expect(l.lignes[0]!.fr).toBe('Raccordement et autorisations du site : dossier monté et suivi par TAQINOR');
    expect(servicesCi(svc({ raccordement: {} }))).toBeNull();
    expect(servicesCi(svc({}))).toBeNull();
    expect(servicesCi(null)).toBeNull();
  });
  it('la page appelle ServicesCi avant l\'ancre exploitation', () => {
    const page = lirePageProposition();
    expect(page.indexOf('data-ci-services')).toBeGreaterThan(-1);
    expect(page.indexOf('data-ci-services')).toBeLessThan(page.indexOf('id="exploitation"'));
  });
});
