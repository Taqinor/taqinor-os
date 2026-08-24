// L-PROP CJ2b-bis (lot 4, 24/08) — /proposition/<token> gagne trois blocs
// client-safe : falaise tarifaire (tranche actuelle/visée + résiduel),
// régime batterie (remplissage moyen + couverture des glitchs) et la
// décomposition mensuelle de l'estimation de consommation, PLUS le graphe
// « une journée type » (TASK2) et les 3 silhouettes d'occupation superposées
// (TASK3). Ces cinq clés (`tranche_tarifaire`, `batterie_regime`,
// `estimation_conso`, `jours_types`, l'existant `courbes_journalieres.
// occupation`) sont [HANDOFF public payload] : pas encore servies par
// `apps/ventes/public_views.py` au moment de cette lane (apps/web uniquement,
// aucun accès au backend Django depuis ce worktree). Ces tests pincent la
// DISCIPLINE « zéro chiffre inventé » : chaque parseur renvoie `null` sur une
// clé absente/malformée (jamais un défaut fabriqué), et la page source ne
// rend RIEN pour un devis pré-lot-4 (aucun crash, byte-identique au rendu
// d'avant).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  tarifBracketStory,
  batteryRegimeInfo,
  estimationConsoAffichable,
  proposalJoursTypes,
  PROPOSAL_JOUR_TYPE_MONTH_IDS,
  type ProposalResponse,
} from '../src/lib/proposition';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
// mon-toit.astro / proposition sources are CRLF (Windows-authored) — normalize
// before pinning multi-line source snippets, same discipline as L-WEBT.
const PAGE = read('../src/pages/proposition/[...token].astro').replace(/\r\n/g, '\n');

// Même discipline que CJ2b/P18/PV80 : le code réel, commentaires retirés — un
// commentaire qui mentionne une clause ne doit jamais faire passer un test.
const CODE = PAGE
  .replace(/<!--[\s\S]*?-->/g, ' ')
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
  .replace(/\/\*[\s\S]*?\*\//g, ' ')
  .replace(/^[ \t]*\/\/.*$/gm, ' ');

function fakeHourly24(peakHours: number[], base: number, peak: number): number[] {
  return Array.from({ length: 24 }, (_, h) => (peakHours.includes(h) ? peak : base));
}

// ════════════════════════════════════════════════════════════════════════════
// A. tarifBracketStory — falaise tarifaire client-safe
// ════════════════════════════════════════════════════════════════════════════

describe('tarifBracketStory', () => {
  it('null quand `tranche_tarifaire` est absent (devis pré-lot-4)', () => {
    expect(tarifBracketStory({})).toBeNull();
    expect(tarifBracketStory({ tranche_tarifaire: null })).toBeNull();
  });

  it('null quand les quatre sous-champs sont vides (objet vide servi)', () => {
    expect(tarifBracketStory({ tranche_tarifaire: {} })).toBeNull();
  });

  it('lit les quatre sous-champs quand tous sont présents', () => {
    const story = tarifBracketStory({
      tranche_tarifaire: {
        tranche_actuelle: { libelle: 'Tranche 3 (301-500 kWh)' },
        tranche_visee: { libelle: 'Tranche 2 (101-300 kWh)' },
        cible_kwh_mois: 500,
        residuel_kwh_mois: 187.4,
      },
    });
    expect(story).toEqual({
      trancheActuelleLibelle: 'Tranche 3 (301-500 kWh)',
      trancheViseeLibelle: 'Tranche 2 (101-300 kWh)',
      cibleKwhMois: 500,
      residuelKwhMois: 187.4,
    });
  });

  it('un seul sous-champ présent reste affichable (les autres à null, pas de repli)', () => {
    const story = tarifBracketStory({ tranche_tarifaire: { residuel_kwh_mois: 42 } });
    expect(story).toEqual({
      trancheActuelleLibelle: null,
      trancheViseeLibelle: null,
      cibleKwhMois: null,
      residuelKwhMois: 42,
    });
  });

  it('un libellé chaîne vide est traité comme absent', () => {
    const story = tarifBracketStory({
      tranche_tarifaire: { tranche_actuelle: { libelle: '' }, residuel_kwh_mois: 10 },
    });
    expect(story!.trancheActuelleLibelle).toBeNull();
  });

  it('un nombre non-fini (NaN, chaîne) devient null plutôt qu’un chiffre inventé', () => {
    const story = tarifBracketStory({
      tranche_tarifaire: { residuel_kwh_mois: Number.NaN, cible_kwh_mois: '500' as unknown as number },
    });
    expect(story).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// B. batteryRegimeInfo — remplissage moyen + couverture des glitchs
// ════════════════════════════════════════════════════════════════════════════

describe('batteryRegimeInfo', () => {
  it('null quand `batterie_regime` est absent', () => {
    expect(batteryRegimeInfo({})).toBeNull();
    expect(batteryRegimeInfo({ batterie_regime: null })).toBeNull();
  });

  it('null quand les deux champs sont illisibles', () => {
    expect(batteryRegimeInfo({ batterie_regime: {} })).toBeNull();
  });

  it('lit remplissage + couverture quand les deux sont servis', () => {
    expect(batteryRegimeInfo({
      batterie_regime: { remplissage_moyen_pct: 78.3, couverture_glitch_pct: 62.1 },
    })).toEqual({ remplissageMoyenPct: 78.3, couvertureGlitchPct: 62.1 });
  });

  it('un seul champ présent reste affichable', () => {
    expect(batteryRegimeInfo({ batterie_regime: { remplissage_moyen_pct: 55 } }))
      .toEqual({ remplissageMoyenPct: 55, couvertureGlitchPct: null });
  });
});

// ════════════════════════════════════════════════════════════════════════════
// C. estimationConsoAffichable — décomposition mensuelle, MÊME contrat que le
//    moteur horaire interne (base_mensuelle/ajouts/totale_mensuelle, 12 valeurs)
// ════════════════════════════════════════════════════════════════════════════

const BASE12 = Array.from({ length: 12 }, (_, i) => 100 + i);
const TOTAL12 = Array.from({ length: 12 }, (_, i) => 120 + i);
const VE12 = Array.from({ length: 12 }, () => 20);

describe('estimationConsoAffichable', () => {
  it('null quand `estimation_conso` est absent', () => {
    expect(estimationConsoAffichable({})).toBeNull();
    expect(estimationConsoAffichable({ estimation_conso: null })).toBeNull();
  });

  it('null quand base_mensuelle ou totale_mensuelle n’a pas exactement 12 valeurs finies', () => {
    expect(estimationConsoAffichable({
      estimation_conso: { base_mensuelle: BASE12.slice(0, 11), totale_mensuelle: TOTAL12 },
    })).toBeNull();
    expect(estimationConsoAffichable({
      estimation_conso: { base_mensuelle: BASE12, totale_mensuelle: [...TOTAL12.slice(0, 11), Number.NaN] },
    })).toBeNull();
  });

  it('lit base + total sans ajout quand `ajouts` est absent', () => {
    const r = estimationConsoAffichable({ estimation_conso: { base_mensuelle: BASE12, totale_mensuelle: TOTAL12 } });
    expect(r).toEqual({ base: BASE12, total: TOTAL12, ajouts: [] });
  });

  it('un ajout dont la série n’a pas 12 valeurs est omis (jamais complété par des zéros)', () => {
    const r = estimationConsoAffichable({
      estimation_conso: {
        base_mensuelle: BASE12,
        totale_mensuelle: TOTAL12,
        ajouts: { ve: VE12, clim: [1, 2, 3] },
      },
    });
    expect(r!.ajouts).toEqual([{ cle: 've', libelle: 'Véhicule électrique', valeurs: VE12 }]);
  });

  it('une clé d’ajout inconnue garde son nom brut comme libellé (jamais un crash)', () => {
    const r = estimationConsoAffichable({
      estimation_conso: { base_mensuelle: BASE12, totale_mensuelle: TOTAL12, ajouts: { pompe_piscine_2: VE12 } },
    });
    expect(r!.ajouts[0]).toEqual({ cle: 'pompe_piscine_2', libelle: 'pompe_piscine_2', valeurs: VE12 });
  });
});

// ════════════════════════════════════════════════════════════════════════════
// D. proposalJoursTypes — TOUT ou RIEN sur les 4 mois (jamais un jeu partiel)
// ════════════════════════════════════════════════════════════════════════════

function fakeMonthPayload() {
  return {
    prod_kw: fakeHourly24([10, 11, 12, 13], 0, 2),
    conso_kw: fakeHourly24([19, 20], 0.4, 1.1),
    conso_jour_kwh: 12.5,
    prod_jour_kwh: 18.2,
    autoconsomme_kwh: 9.1,
    surplus_kwh: 9.1,
  };
}

describe('proposalJoursTypes', () => {
  it('null quand `jours_types` est absent', () => {
    expect(proposalJoursTypes({})).toBeNull();
    expect(proposalJoursTypes({ jours_types: null })).toBeNull();
  });

  it('null quand un seul des quatre mois manque (jamais un jeu partiel affiché)', () => {
    const partial = { '1': fakeMonthPayload(), '4': fakeMonthPayload(), '7': fakeMonthPayload() };
    expect(proposalJoursTypes({ jours_types: partial })).toBeNull();
  });

  it('null quand un mois porte une forme malformée (longueur ≠ 24, négatif, non-fini)', () => {
    const bad = {
      '1': fakeMonthPayload(), '4': fakeMonthPayload(), '7': fakeMonthPayload(),
      '11': { ...fakeMonthPayload(), prod_kw: fakeMonthPayload().prod_kw.slice(0, 23) },
    };
    expect(proposalJoursTypes({ jours_types: bad })).toBeNull();
  });

  it('renvoie les quatre mois quand tous sont valides', () => {
    const all = {
      '1': fakeMonthPayload(), '4': fakeMonthPayload(), '7': fakeMonthPayload(), '11': fakeMonthPayload(),
    };
    const r = proposalJoursTypes({ jours_types: all });
    expect(r).not.toBeNull();
    for (const m of PROPOSAL_JOUR_TYPE_MONTH_IDS) {
      expect(r![m].prodKw).toHaveLength(24);
      expect(r![m].consoKw).toHaveLength(24);
      expect(r![m].consoJourKwh).toBe(12.5);
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════
// E. Aucun crash sur un payload legacy minimal (devis généré avant le lot 4)
// ════════════════════════════════════════════════════════════════════════════

describe('un devis pré-lot-4 (aucune des cinq clés) reste sans crash', () => {
  const legacy: Pick<
    ProposalResponse,
    'tranche_tarifaire' | 'batterie_regime' | 'estimation_conso' | 'jours_types'
  > = {};

  it('les quatre parseurs renvoient null', () => {
    expect(tarifBracketStory(legacy)).toBeNull();
    expect(batteryRegimeInfo(legacy)).toBeNull();
    expect(estimationConsoAffichable(legacy)).toBeNull();
    expect(proposalJoursTypes(legacy)).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// F. Source de la page — blocs masqués (guards) + couleurs PINNED (source pin)
// ════════════════════════════════════════════════════════════════════════════

describe('[...token].astro — les trois nouveaux blocs se masquent quand rien n’est servi', () => {
  it('la carte falaise/batterie/estimation ne rend rien tant que les trois sont absents', () => {
    expect(CODE).toContain("showFalaiseBlock && (");
    expect(CODE).toContain(
      "const showFalaiseBlock = installMode === 'residentiel' && !!(tarifStory || battRegime || estimConso);",
    );
  });

  it('les 3 silhouettes ne rendent rien sans occupation client connue', () => {
    expect(CODE).toContain("curveMode === 'residentiel' && clientOccupancyChoice && (");
  });

  it('« Une journée type » ne rend rien tant que `jours_types` est absent', () => {
    expect(CODE).toContain("curveMode === 'residentiel' && joursTypes && (");
  });
});

describe('[...token].astro — couleurs VALIDÉES fondateur, PINNED', () => {
  it('jour-type : production dorée (18 % de fond) vs consommation bleue pointillée [6,3]', () => {
    expect(CODE).toContain('fill="rgba(237,161,0,0.18)"');
    expect(CODE).toContain('stroke="#eda100"');
    expect(CODE).toContain('stroke="#2a78d6" stroke-width="2" stroke-dasharray="6,3"');
  });

  it('silhouettes : présent plein bleu (fond 10 %), absent pointillé orange [6,3], partiel pointillé vert [2,3]', () => {
    expect(CODE).toContain("presence_jour: { stroke: '#2a78d6', dash: null, fill: 'rgba(42,120,214,0.10)' }");
    expect(CODE).toContain("absence_jour: { stroke: '#eb6834', dash: '6,3' }");
    expect(CODE).toContain("presence_partielle: { stroke: '#1baf7a', dash: '2,3' }");
  });

  it('la silhouette du client porte le libellé « CHOISIE pour ce client »', () => {
    expect(CODE).toContain('CHOISIE pour ce client');
  });

  it('l’axe des silhouettes porte le libellé « poids de forme (sans unité) »', () => {
    expect(CODE).toContain('poids de forme (sans unité)');
  });
});
