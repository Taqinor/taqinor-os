// P18 (ordre fondateur du 18/08/2026) — « LA PAGE NE MONTRE QUE CE QUI EST DANS
// LE DEVIS, ET SES CHIFFRES SONT CEUX DU MOTEUR ».
//
// Deux exigences, une seule discipline :
//   A. Retirer une ligne du devis doit retirer ce qu'elle promettait sur la page
//      — le simulateur de batterie, les garanties panneaux/onduleur, le suivi
//      par l'application de l'onduleur. Rien de tout cela ne peut plus dépendre
//      du MODE d'installation ou d'un repli catalogue : tout est lu sur les
//      LIGNES réelles du devis.
//   B. Les montants du chapitre « Vos économies » sont ceux SERVIS par le
//      backend (moteur de devis), jamais un second modèle calculé ici : quand
//      le moteur est corrigé, la page est corrigée sans être retouchée.
//
// Modules purs + garde de SOURCE sur la page (même convention que
// propositionChaptersPV80.test.ts) : la page Astro n'est pas rendue en CI, mais
// tout ce qui décide de son contenu l'est.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  couvertureSolaire,
  monitoringPoints,
  savingsHeadline,
  syntheseEconomies,
  formatPayback,
  type ProposalItem,
  type ProposalResponse,
} from '../src/lib/proposition';
import { equipmentPresence } from '../src/lib/propositionPage';
import { resolveOfferBattery } from '../src/lib/batterySim';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const PAGE = read('../src/pages/proposition/[...token].astro');

/** Source privée de ses commentaires : on scanne ce que la page FAIT. */
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

// ── Fabriques de lignes de devis ────────────────────────────────────────────

function item(designation: string, quantite = 1): ProposalItem {
  return {
    designation,
    quantite,
    prix_unit_ht: 1000,
    prix_unit_ttc: 1200,
    remise: 0,
    marque: '',
    taux_tva: 20,
  };
}

/** Résidentiel typique : panneaux + onduleur hybride + coffret + pose. */
const RESIDENTIEL: ProposalItem[] = [
  item('Panneau photovoltaïque monocristallin 550 Wc', 12),
  item('Onduleur hybride 5 kW'),
  item('Coffret de protection DC pour onduleur'),
  item('Structure de fixation toiture tuile'),
  item('Pose et mise en service'),
];

/** Le même devis, option « avec batterie » : une VRAIE ligne batterie. */
const RESIDENTIEL_BATTERIE: ProposalItem[] = [
  ...RESIDENTIEL,
  item('Batterie lithium BAT-DEY-10 10 kWh', 2),
];

/** Pompage agricole : pompe + variateur, AUCUN onduleur, AUCUN panneau ici. */
const POMPAGE: ProposalItem[] = [
  item('Pompe immergée OSP 30-12 4 CV'),
  item('Variateur VEICHI SI23 5,5 kW 380 V'),
  item('Afficheur SI22'),
  item('Coffret de protection'),
  item('Câble immergé 4G4'),
];

// ── A1. Simulateur batterie : gaté sur la LIGNE, jamais sur le mode ─────────

describe('P18 — le simulateur de batterie suit la ligne du devis', () => {
  it('devis SANS ligne batterie → aucune batterie détectée (donc aucun simulateur)', () => {
    const found = resolveOfferBattery(RESIDENTIEL);
    expect(found.present).toBe(false);
    expect(found.units).toBe(0);
  });

  it('devis AVEC ligne batterie → détectée, avec la capacité et la quantité de la ligne', () => {
    const found = resolveOfferBattery(RESIDENTIEL_BATTERIE);
    expect(found.present).toBe(true);
    expect(found.capacityKwhPerUnit).toBe(10); // réf catalogue BAT-DEY-10
    expect(found.units).toBe(2);
  });

  it('pompage → aucune batterie (CLAUDE.md : jamais de batterie en pompage)', () => {
    expect(resolveOfferBattery(POMPAGE).present).toBe(false);
  });

  it('la page conditionne showBatterySim à la présence RÉELLE de la batterie', () => {
    // Le simulateur ne peut plus exister sur la seule foi du mode d'installation.
    expect(CODE).toMatch(/const showBatterySim = batterySimEligible && offerBattery\.present/);
    // La ligne est cherchée dans les DEUX options du devis, jamais inventée.
    expect(CODE).toContain('resolveOfferBattery(ok ? (q?.avec_items ?? null) : null)');
    expect(CODE).toContain('resolveOfferBattery(ok ? (q?.sans_items ?? null) : null)');
    // Tout le bloc (markup + config sérialisée) reste sous ce même drapeau.
    expect(CODE).toContain('{showBatterySim && batteryInitial && (');
    expect(CODE).toContain('const batterySimConfig = showBatterySim');
  });

  it('la capacité du curseur reste celle de la ligne (le repli catalogue n’est qu’un secours)', () => {
    expect(CODE).toContain('offerBattery.capacityKwhPerUnit ?? DEFAULT_UNIT_CAPACITY_KWH');
  });
});

// ── A2. Garanties : une promesse par ligne réellement devisée ───────────────

describe('P18 — equipmentPresence lit les lignes, pas le mode', () => {
  it('résidentiel panneaux + onduleur → les deux promesses sont légitimes', () => {
    expect(equipmentPresence(RESIDENTIEL)).toEqual({ panneaux: true, onduleur: true });
  });

  it('pompage (pompe + variateur) → ni panneau ni onduleur', () => {
    expect(equipmentPresence(POMPAGE)).toEqual({ panneaux: false, onduleur: false });
  });

  it('un variateur/VFD n’est PAS un onduleur', () => {
    expect(equipmentPresence([item('Variateur VEICHI 7,5 kW')]).onduleur).toBe(false);
    expect(equipmentPresence([item('VFD 11 kW 380V')]).onduleur).toBe(false);
  });

  it('pompage AVEC son champ PV → le panneau est promis, l’onduleur non', () => {
    const pompageAvecPv = [...POMPAGE, item('Panneau photovoltaïque 550 Wc', 8)];
    expect(equipmentPresence(pompageAvecPv)).toEqual({ panneaux: true, onduleur: false });
  });

  it('un « coffret DC pour onduleur » ne fabrique pas une garantie onduleur', () => {
    // La ligne tombe dans « protection » (classement déjà line-driven) : elle
    // n'entre jamais dans la lecture panneau/onduleur.
    expect(equipmentPresence([item('Coffret de protection DC pour onduleur')]).onduleur).toBe(false);
  });

  it('un « câble batterie » ne fabrique pas une garantie panneau/onduleur', () => {
    expect(equipmentPresence([item('Câble batterie 25 mm²')])).toEqual({ panneaux: false, onduleur: false });
  });

  it('une ligne à quantité nulle ou sans désignation ne promet rien', () => {
    expect(equipmentPresence([item('Panneau photovoltaïque 550 Wc', 0)]).panneaux).toBe(false);
    expect(equipmentPresence([])).toEqual({ panneaux: false, onduleur: false });
    expect(equipmentPresence(null)).toEqual({ panneaux: false, onduleur: false });
  });

  it('micro-onduleur compte bien comme onduleur', () => {
    expect(equipmentPresence([item('Micro-onduleur 800 W')]).onduleur).toBe(true);
  });
});

describe('P18 — la page gate la phrase de garantie ET les badges', () => {
  it('la présence est lue sur les lignes des DEUX options du devis', () => {
    expect(CODE).toContain('const equipPresence = equipmentPresence(');
    expect(CODE).toContain("optionItems(data!, 'sans_batterie'), ...optionItems(data!, 'avec_batterie')");
  });

  it('la garantie panneaux et la garantie onduleur sont chacune sous condition', () => {
    expect(CODE).toContain('{equipPresence.panneaux && (');
    expect(CODE).toContain('{equipPresence.onduleur && (');
    // Les durées elles-mêmes restent la source unique warranty.ts.
    expect(CODE).toContain('PANEL_PERFORMANCE_WARRANTY_YEARS');
    expect(CODE).toContain('INVERTER_WARRANTY_YEARS');
  });

  it('les badges « panneaux » / « onduleur » ne sont plus poussés inconditionnellement', () => {
    expect(CODE).not.toMatch(/'panneaux' as const,\s*\n\s*'onduleur' as const,/);
    expect(CODE).toContain("...(equipPresence.panneaux ? ['panneaux' as const] : [])");
    expect(CODE).toContain("...(equipPresence.onduleur ? ['onduleur' as const] : [])");
  });

  it('la garantie de POSE Taqinor reste inconditionnelle (c’est notre engagement)', () => {
    expect(CODE).toContain('INSTALL_WARRANTY_YEARS');
    expect(CODE).toContain('de pose Taqinor');
  });
});

// ── A3. Suivi post-installation : l'application de l'onduleur ───────────────

describe('P18 — monitoringPoints ne promet une application que s’il y a un onduleur', () => {
  it('sans onduleur : aucun point « application de votre onduleur »', () => {
    const pts = monitoringPoints({ onduleur: false });
    expect(pts.some((p) => p.label.includes('onduleur'))).toBe(false);
    expect(pts.some((p) => p.labelEn.includes('inverter'))).toBe(false);
    // Les points génériques (SAV, garanties) restent : la page n'est pas vide.
    expect(pts.length).toBeGreaterThanOrEqual(2);
  });

  it('avec onduleur : le point de suivi revient, en FR/EN/AR', () => {
    const pts = monitoringPoints({ onduleur: true });
    const suivi = pts.find((p) => p.label.includes('onduleur'));
    expect(suivi).toBeTruthy();
    expect(suivi!.labelEn.length).toBeGreaterThan(0);
    expect(suivi!.labelAr.length).toBeGreaterThan(0);
    expect(pts.length).toBe(monitoringPoints({ onduleur: false }).length + 1);
  });

  it('appel sans argument : aucune promesse par défaut', () => {
    expect(monitoringPoints().some((p) => p.label.includes('onduleur'))).toBe(false);
  });

  it('la page passe la présence réelle', () => {
    expect(CODE).toContain('monitoringPoints(equipPresence)');
  });
});

// ── B. Les chiffres d'argent sont ceux SERVIS par le moteur ────────────────

function proposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  return {
    reference: 'DV-2026-08-001',
    date: '18/08/2026',
    client_name: 'Client Test',
    statut: 'envoye',
    quote: {
      ref: 'DV-2026-08-001',
      date: '18/08/2026',
      client_name: 'Client Test',
      prod_kwh: 9200,
      puissance_kwc: 6.6,
      eco_s_ann: 11400,
      eco_a_ann: 13250,
      eco_a_cumul: 13250,
      roi_s: 5.4,
      roi_a: 6.1,
      sans_items: RESIDENTIEL,
      avec_items: RESIDENTIEL_BATTERIE,
      ...((over.quote ?? {}) as Record<string, unknown>),
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 62000, avec_batterie: 94000, display_total: 62000, nb_options: 2 },
    accepted: false,
    // PVCOV — la synthèse SERVIE : exactement les valeurs de la page 1 du PDF.
    pct_cut: 56,
    annual_before: 21400,
    annual_after: 9404,
    coverage_pct: 67,
    coverage_estimated: false,
    ...over,
  } as ProposalResponse;
}

describe('P18 — savingsHeadline rend EXACTEMENT les champs servis', () => {
  it('économie annuelle, payback et cumul viennent du payload, sans second modèle', () => {
    const p = proposal();
    const h = savingsHeadline(p, 'avec_batterie');
    // Égalité STRICTE avec le champ servi — aucune correction locale.
    expect(h.annual).toBe(p.quote.eco_a_ann);
    expect(h.payback).toBe(formatPayback(p.quote.roi_a));
    // Le cumul est le TAUX backend × horizon (même multiplication que le PDF).
    expect(h.cumulative).toBe((p.quote.eco_a_cumul as number) * h.years);
    expect(h.cumulativeFromBackend).toBe(true);
    // Le cadrage mensuel n'est qu'un changement d'unité de l'annuel servi.
    expect(h.monthly).toBe(Math.round((p.quote.eco_a_ann as number) / 12));
  });

  it('option sans batterie → l’autre champ servi, jamais un mélange', () => {
    const p = proposal();
    const h = savingsHeadline(p, 'sans_batterie');
    expect(h.annual).toBe(p.quote.eco_s_ann);
    expect(h.payback).toBe(formatPayback(p.quote.roi_s));
  });

  it('backend sans économie → rien d’inventé', () => {
    const p = proposal({
      quote: { ...proposal().quote, eco_s_ann: undefined, eco_a_ann: undefined, eco_a_cumul: undefined },
    });
    const h = savingsHeadline(p, 'avec_batterie');
    expect(h.annual).toBeNull();
    expect(h.cumulative).toBeNull();
    expect(h.monthly).toBeNull();
  });
});

describe('P18 — syntheseEconomies : le « −N % » et l’avant/après SERVIS', () => {
  it('rend EXACTEMENT pct_cut / annual_before / annual_after, sans retouche', () => {
    const p = proposal();
    const s = syntheseEconomies(p)!;
    expect(s.pctCut).toBe(p.pct_cut);
    expect(s.annuelAvant).toBe(p.annual_before);
    expect(s.annuelApres).toBe(p.annual_after);
    // La SEULE arithmétique autorisée : le passage au mois.
    expect(s.mensuelAvant).toBe(Math.round((p.annual_before as number) / 12));
    expect(s.mensuelApres).toBe(Math.round((p.annual_after as number) / 12));
  });

  it('le pourcentage n’est JAMAIS re-dérivé des deux factures', () => {
    // Backend volontairement en désaccord avec un recalcul local : la page doit
    // afficher le `pct_cut` SERVI (42), pas le 56 % qu'un calcul local tirerait
    // de 21 400 → 9 404. C'est tout l'objet de la règle « le moteur décide ».
    expect(syntheseEconomies(proposal({ pct_cut: 42 }))!.pctCut).toBe(42);
  });

  it('un seul champ manquant → bloc masqué (null), jamais un chiffre partiel', () => {
    expect(syntheseEconomies(proposal({ pct_cut: null }))).toBeNull();
    expect(syntheseEconomies(proposal({ annual_before: null }))).toBeNull();
    expect(syntheseEconomies(proposal({ annual_after: null }))).toBeNull();
    expect(syntheseEconomies(proposal({ pct_cut: undefined }))).toBeNull();
  });

  it('devis hors forme résidentielle (les cinq champs None) → rien du tout', () => {
    const p = proposal({
      pct_cut: null, annual_before: null, annual_after: null,
      coverage_pct: null, coverage_estimated: null,
    });
    expect(syntheseEconomies(p)).toBeNull();
    expect(couvertureSolaire(p)).toBeNull();
  });

  it('payload incohérent (après > avant, ou avant ≤ 0) → null', () => {
    expect(syntheseEconomies(proposal({ annual_after: 30000 }))).toBeNull();
    expect(syntheseEconomies(proposal({ annual_before: 0 }))).toBeNull();
  });

  it('facture « après » nulle (autoconsommation totale) reste un cas valide', () => {
    const s = syntheseEconomies(proposal({ annual_after: 0, pct_cut: 100 }))!;
    expect(s.annuelApres).toBe(0);
    expect(s.mensuelApres).toBe(0);
    expect(s.pctCut).toBe(100);
  });
});

describe('P18 — couvertureSolaire : la donut lit coverage_pct, point', () => {
  it('rend EXACTEMENT coverage_pct et coverage_estimated', () => {
    const p = proposal();
    const c = couvertureSolaire(p)!;
    expect(c.pct).toBe(p.coverage_pct);
    expect(c.estimated).toBe(false);
  });

  it('coverage_estimated pilote SEUL le libellé « (estimation) »', () => {
    expect(couvertureSolaire(proposal({ coverage_estimated: true }))!.estimated).toBe(true);
    expect(couvertureSolaire(proposal({ coverage_estimated: null }))!.estimated).toBe(false);
  });

  it('couverture absente → donut masquée (null)', () => {
    expect(couvertureSolaire(proposal({ coverage_pct: null }))).toBeNull();
    expect(couvertureSolaire(proposal({ coverage_pct: undefined }))).toBeNull();
  });

  it('100 % n’est affiché que si le backend sert 100 (borne moteur : prod ≥ conso)', () => {
    expect(couvertureSolaire(proposal({ coverage_pct: 100 }))!.pct).toBe(100);
    // Hors de la plage servie 1..100 : on se tait, on ne ramène jamais à 100.
    expect(couvertureSolaire(proposal({ coverage_pct: 140 }))).toBeNull();
    expect(couvertureSolaire(proposal({ coverage_pct: 0 }))).toBeNull();
  });
});

describe('P18 — la page n’a aucun modèle d’économies à elle', () => {
  it('elle lit la synthèse servie au lieu de la reconstruire', () => {
    expect(CODE).toContain('const synthese = ok ? syntheseEconomies(data!) : null');
    expect(CODE).toContain('const couverture = ok ? couvertureSolaire(data!) : null');
    expect(CODE).toContain('{(synthese || showCouvertureDonut) && (');
    for (const bound of [
      'synthese.pctCut', 'synthese.mensuelAvant', 'synthese.mensuelApres',
      'synthese.annuelAvant', 'synthese.annuelApres',
      'couverture.pct', 'couverture.estimated',
    ]) {
      expect(CODE).toContain(bound);
    }
  });

  it('le « −N % » est rendu tel quel, jamais dérivé de l’avant/après', () => {
    expect(CODE).toContain('−{formatNumber(synthese.pctCut, 0)} %');
    expect(CODE).not.toMatch(/1\s*-\s*synthese\.annuelApres/);
    expect(CODE).not.toMatch(/annuelApres\s*\/\s*synthese\.annuelAvant/);
  });

  it('la donut résidentielle n’existe que sur une couverture servie', () => {
    expect(CODE).toContain("const showCouvertureDonut = installMode === 'residentiel' && !!couverture");
    // L'anneau ne fait que DESSINER : une longueur d'arc, pas un pourcentage.
    expect(CODE).toContain('const donutDash = couverture ? (donutCirc * couverture.pct) / 100 : 0');
    expect(CODE).toContain('stroke-dasharray');
  });

  it('aucun barème / tarif kWh / taux d’autoconsommation n’est codé dans la page', () => {
    // Ces notions appartiennent au moteur de devis, jamais à la page publique.
    expect(CODE).not.toContain('ONEE_TRANCHES');
    expect(CODE).not.toMatch(/const\s+TARIF_KWH/);
    expect(CODE).not.toMatch(/const\s+AUTOCONSO_/);
    expect(CODE).not.toMatch(/const\s+BILL_INFLATION/);
  });

  it('le taux de couverture industriel/commercial reste celui servi (mode_kpis)', () => {
    // Deux chemins distincts, jamais deux couvertures sur la même page :
    // résidentiel → donut `coverage_pct` ; autoconso → KPI `taux_couverture`.
    expect(CODE).toContain('auto.taux_couverture');
    expect(CODE).not.toMatch(/couverture\s*=\s*.*prodKwh\s*\//);
  });
});
