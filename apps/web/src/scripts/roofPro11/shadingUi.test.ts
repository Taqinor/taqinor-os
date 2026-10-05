// CAL60 — hauteur de bâtiment saisissable (repli AFFICHÉ comme hypothèse). Le calcul
// d'ombrage (hourlyShadeFactors, etc.) est déjà testé ailleurs (shadingWJ19.test.ts) ;
// ce fichier couvre uniquement la résolution PURE de la hauteur (le reste de
// `createShadingUi` a besoin d'une carte MapLibre + du DOM, hors de portée d'un test pur).
import { describe, expect, it } from 'vitest';
import {
  effectiveBuildingHeightM,
  filtrerEmplacementsSousSeuil,
  hauteurToitPourOmbrageM,
  heatmapAccessValues,
  HEATMAP_MONTH_LABELS,
  libelleBoutonOsm,
  moduleShadeReading,
  moduleShadeReadingsForPanels,
  type ModuleShadeReading,
  matriceOmbrageDesSources, // ACAL27
} from './shadingUi';
import {
  deserializeShadeObstructions,
  hydrateFromDevis,
  serializeLayout,
  serializeShadeObstructions,
  serializeShading,
} from './prefill'; // ACAL27
import { appliquerHydratationAuCtx } from './hydratation'; // ACAL27
import { type Ctx } from './context'; // ACAL27
import { propositionOsm, type Batiment, type BatimentOsmServeur } from './batiment';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';
import { fallbackPerKwc } from '../../lib/productionEngine';
import { hourlyShadeFactors, type ShadeObstructionENU } from '../../lib/shadingEngine';

describe('CAL60 — effectiveBuildingHeightM', () => {
  it('sans saisie (null/undefined) : repli historique FLOORS × FLOOR_HEIGHT_M', () => {
    expect(effectiveBuildingHeightM(null)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(undefined)).toBe(FLOORS * FLOOR_HEIGHT_M);
  });

  it('une hauteur saisie finie et positive prime sur le repli', () => {
    expect(effectiveBuildingHeightM(9.5)).toBe(9.5);
    expect(effectiveBuildingHeightM(3)).toBe(3);
  });

  it('une saisie aberrante (0, négative, non finie) retombe sur le repli', () => {
    expect(effectiveBuildingHeightM(0)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(-2)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(NaN)).toBe(FLOORS * FLOOR_HEIGHT_M);
  });

  it('changer la hauteur change visiblement le résultat (valeurs distinctes)', () => {
    const a = effectiveBuildingHeightM(4);
    const b = effectiveBuildingHeightM(12);
    expect(a).not.toBe(b);
  });
});

// CAL95 — carte d'accès solaire : alimentée par la source unifiée (CAL94) et lisible PAR
// MOIS en plus de la lecture annuelle. Calcul PUR, testable sans DOM ni WebGL.
describe('CAL95 — heatmapAccessValues : toutes les obstructions, et par mois', () => {
  const LAT = 33.5;
  const prod = fallbackPerKwc();
  const panels = [
    { cx: 0, cy: 0 }, // juste au nord de la cheminée : dans son ombre
    { cx: 40, cy: 0 }, // 40 m à l'est : hors de son ombre
  ];
  /** Cheminée 3 × 3 m, 5 m de haut, 3 m au sud du premier module. */
  const cheminee: ShadeObstructionENU = {
    x: 0,
    y: -3,
    effHeightM: 5,
    halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [
      [-1.5, -4.5],
      [1.5, -4.5],
      [1.5, -1.5],
      [-1.5, -1.5],
    ],
  };

  it('sans obstruction : tout à 1, en annuel comme au mois (aucun dérate inventé)', () => {
    expect(heatmapAccessValues(LAT, [], prod, panels, null)).toEqual([1, 1]);
    expect(heatmapAccessValues(LAT, [], prod, panels, 11)).toEqual([1, 1]);
  });

  it('poser une cheminée à hauteur fait varier la carte, et seulement derrière elle', () => {
    const access = heatmapAccessValues(LAT, [cheminee], prod, panels, null);
    expect(access[0]).toBeLessThan(1);
    expect(access[1]).toBeGreaterThan(access[0]);
  });

  it('décembre est plus rouge que juin sur le même module (soleil bas, ombres longues)', () => {
    const decembre = heatmapAccessValues(LAT, [cheminee], prod, panels, 11)[0];
    const juin = heatmapAccessValues(LAT, [cheminee], prod, panels, 5)[0];
    expect(decembre).toBeLessThan(juin);
  });

  it('un mois hors bornes retombe sur « aucun dérate » plutôt que sur une valeur inventée', () => {
    expect(heatmapAccessValues(LAT, [cheminee], prod, panels, 12)).toEqual([1, 1]);
    expect(heatmapAccessValues(LAT, [cheminee], prod, panels, -1)).toEqual([1, 1]);
  });

  it('les douze mois sont nommés, dans l’ordre', () => {
    expect(HEATMAP_MONTH_LABELS).toHaveLength(12);
    expect(HEATMAP_MONTH_LABELS[0]).toBe('janvier');
    expect(HEATMAP_MONTH_LABELS[11]).toBe('décembre');
  });
});

// CALX122 — lecture géométrique d'ombrage PAR MODULE : nombre d'heures représentatives
// masquées (sur les 288 = 12 mois × 24 h de la matrice déjà calculée par
// `hourlyShadeFactors`) et le premier mois concerné. Aucun kWh : lecture géométrique pure,
// testable sans DOM ni production (les fonctions ne prennent même pas de profil PVGIS).
describe('CALX122 — lecture géométrique d’ombrage par module (heures + premier mois)', () => {
  const LAT = 33.5;
  /** Même cheminée que CAL95 ci-dessus (3 × 3 m, 5 m de haut, 3 m au sud du module) —
   *  déjà prouvée « obstruction effective » par le test CAL95 (`access[0]` < 1). */
  const cheminee: ShadeObstructionENU = {
    x: 0,
    y: -3,
    effHeightM: 5,
    halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [
      [-1.5, -4.5],
      [1.5, -4.5],
      [1.5, -1.5],
      [-1.5, -1.5],
    ],
  };
  const panels = [
    { cx: 0, cy: 0 }, // juste au nord de la cheminée : dans son ombre
    { cx: 40, cy: 0 }, // 40 m à l'est : hors de son ombre
  ];

  it('sans AUCUNE source d’ombrage saisie (hasSource=false) : la lecture est ABSENTE (null), jamais « 0 heure »', () => {
    expect(moduleShadeReadingsForPanels(LAT, [cheminee], panels, false)).toBeNull();
    expect(moduleShadeReadingsForPanels(LAT, [], panels, false)).toBeNull();
  });

  it('une source saisie mais sans obstruction effective (enu vide) publie un VRAI zéro, jamais une omission', () => {
    const readings = moduleShadeReadingsForPanels(LAT, [], panels, true);
    expect(readings).toEqual([
      { maskedHours: 0, firstMonthIndex: null },
      { maskedHours: 0, firstMonthIndex: null },
    ]);
  });

  it('une obstruction saisie ⇒ le compte d’heures suit EXACTEMENT la matrice 12×24 existante', () => {
    const reading = moduleShadeReading(LAT, [cheminee], 0, 0);
    // Recalcul indépendant depuis la matrice déjà testée ailleurs (shadingWJ19.test.ts) :
    // la lecture géométrique ne doit rien inventer de plus que ce que hourlyShadeFactors dit.
    const matrix = hourlyShadeFactors(LAT, [cheminee], 0, 0);
    let expectedHours = 0;
    let expectedFirstMonth: number | null = null;
    matrix.forEach((row, m) => {
      const maskedInMonth = row.filter((v) => v < 1).length;
      if (maskedInMonth > 0) {
        expectedHours += maskedInMonth;
        if (expectedFirstMonth == null) expectedFirstMonth = m;
      }
    });
    expect(reading.maskedHours).toBe(expectedHours);
    expect(reading.firstMonthIndex).toBe(expectedFirstMonth);
    expect(reading.maskedHours).toBeGreaterThan(0);
  });

  it('le module plus loin (40 m à l’est) est nettement moins masqué — toujours depuis SA PROPRE matrice, jamais un chiffre par défaut', () => {
    const far = moduleShadeReading(LAT, [cheminee], 40, 0);
    const matrixFar = hourlyShadeFactors(LAT, [cheminee], 40, 0);
    let expectedFarHours = 0;
    matrixFar.forEach((row) => {
      for (const v of row) if (v < 1) expectedFarHours++;
    });
    expect(far.maskedHours).toBe(expectedFarHours);
    const near = moduleShadeReading(LAT, [cheminee], 0, 0);
    expect(far.maskedHours).toBeLessThan(near.maskedHours);
  });

  it('moduleShadeReadingsForPanels aligne un résultat par panneau, dans l’ordre (le plus proche masqué au moins autant que le plus loin)', () => {
    const readings = moduleShadeReadingsForPanels(LAT, [cheminee], panels, true) as ModuleShadeReading[];
    expect(readings).toHaveLength(2);
    expect(readings[0].maskedHours).toBeGreaterThan(0);
    expect(readings[0].firstMonthIndex).not.toBeNull();
    expect(readings[1].maskedHours).toBeLessThanOrEqual(readings[0].maskedHours);
    expect(readings[1].firstMonthIndex == null || typeof readings[1].firstMonthIndex === 'number').toBe(true);
  });
});

// CALX115 — un seuil d'accès solaire SAISI (`optimisation.seuilAccesSolaire`, contrat
// CALX88) écarte du posable les emplacements dont l'accès solaire CALCULÉ est sous le
// seuil, AVANT le pavage. Aucun seuil par défaut : la pose est celle d'aujourd'hui, et
// sans mesure d'ombrage le seuil est REFUSÉ en nommant sa raison — jamais « plein soleil ».
describe('CALX115 — filtrerEmplacementsSousSeuil : écarter des emplacements, jamais supposer du plein soleil', () => {
  const LAT = 33.5;
  const prod = fallbackPerKwc();
  /** Même cheminée que CAL95/CALX122 (3 × 3 m, 5 m de haut, 3 m au sud du module 0). */
  const cheminee: ShadeObstructionENU = {
    x: 0,
    y: -3,
    effHeightM: 5,
    halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [
      [-1.5, -4.5],
      [1.5, -4.5],
      [1.5, -1.5],
      [-1.5, -1.5],
    ],
  };
  const panels = [
    { cx: 0, cy: 0 }, // juste au nord de la cheminée : dans son ombre
    { cx: 40, cy: 0 }, // 40 m à l'est : hors de son ombre
  ];
  /** Le seuil qui coupe ENTRE les deux modules, dérivé des valeurs calculées — jamais
   *  un nombre choisi à la main (D-CALX 7). */
  function seuilEntreLesDeux(): number {
    const acces = heatmapAccessValues(LAT, [cheminee], prod, panels, null);
    return (acces[0] + acces[1]) / 2;
  }

  it('aucun seuil saisi (absent/null) : pose IDENTIQUE, et la phrase nomme le champ absent', () => {
    for (const saisi of [undefined, null, '']) {
      const r = filtrerEmplacementsSousSeuil(saisi, LAT, [cheminee], prod, panels, true);
      expect(r.retenus).toEqual([0, 1]);
      expect(r.ecartes).toEqual([]);
      expect(r.seuilApplique).toBeNull();
      expect(r.refuse).toBe(false);
      expect(r.motif).toContain('optimisation.seuilAccesSolaire');
      expect(r.motif).toContain('celle d’aujourd’hui');
    }
  });

  it('seuil à 0 : pose IDENTIQUE (aucun accès solaire ne peut lui être inférieur)', () => {
    const r = filtrerEmplacementsSousSeuil(0, LAT, [cheminee], prod, panels, true);
    expect(r.retenus).toEqual([0, 1]);
    expect(r.ecartes).toEqual([]);
    expect(r.seuilApplique).toBe(0);
    expect(r.refuse).toBe(false);
  });

  it('seuil relevé : le compte baisse EXACTEMENT du nombre annoncé, et le motif le publie', () => {
    const seuil = seuilEntreLesDeux();
    const r = filtrerEmplacementsSousSeuil(seuil, LAT, [cheminee], prod, panels, true);
    expect(r.refuse).toBe(false);
    expect(r.seuilApplique).toBe(seuil);
    expect(r.ecartes).toEqual([0]); // le module dans l'ombre de la cheminée
    expect(r.retenus).toEqual([1]);
    expect(r.retenus.length).toBe(panels.length - r.ecartes.length);
    expect(r.motif).toContain(`${r.ecartes.length} emplacement(s) sur ${panels.length}`);
  });

  it('seuil à 1 : tout ce qui est ombragé sort du posable, rien n’est inventé', () => {
    const r = filtrerEmplacementsSousSeuil(1, LAT, [cheminee], prod, panels, true);
    const acces = heatmapAccessValues(LAT, [cheminee], prod, panels, null);
    expect(r.ecartes).toEqual(acces.map((a, i) => (a < 1 ? i : -1)).filter((i) => i >= 0));
    expect(r.retenus.length + r.ecartes.length).toBe(panels.length);
  });

  it('AUCUN accès solaire calculé (aucune source saisie) : le seuil est REFUSÉ en nommant la raison, jamais du plein soleil', () => {
    const r = filtrerEmplacementsSousSeuil(0.7, LAT, [], prod, panels, false);
    expect(r.refuse).toBe(true);
    expect(r.champ).toBe('optimisation.seuilAccesSolaire');
    expect(r.seuilApplique).toBeNull();
    expect(r.retenus).toEqual([0, 1]);
    expect(r.ecartes).toEqual([]);
    expect(r.motif).toContain('ne vaut pas du plein soleil');
  });

  it('source saisie mais AUCUNE obstruction au-dessus du champ : refus distinct, avec sa propre raison', () => {
    const r = filtrerEmplacementsSousSeuil(0.7, LAT, [], prod, panels, true);
    expect(r.refuse).toBe(true);
    expect(r.champ).toBe('optimisation.seuilAccesSolaire');
    expect(r.ecartes).toEqual([]);
    expect(r.motif).toContain('ne dépasse le plan du champ');
  });

  it('un seuil hors contrat (texte, NaN, hors [0,1]) est REFUSÉ en le citant — jamais corrigé en douce', () => {
    for (const mauvais of ['beaucoup', Number.NaN, 1.4, -0.2]) {
      const r = filtrerEmplacementsSousSeuil(mauvais, LAT, [cheminee], prod, panels, true);
      expect(r.refuse).toBe(true);
      expect(r.champ).toBe('optimisation.seuilAccesSolaire');
      expect(r.seuilApplique).toBeNull();
      expect(r.retenus).toEqual([0, 1]);
      expect(r.motif).toContain(String(mauvais));
    }
  });

  it('aucun emplacement à évaluer : la réponse le dit, sans écarter ni inventer', () => {
    const r = filtrerEmplacementsSousSeuil(0.7, LAT, [cheminee], prod, [], true);
    expect(r.retenus).toEqual([]);
    expect(r.ecartes).toEqual([]);
    expect(r.refuse).toBe(false);
    expect(r.motif).toContain('aucun emplacement à évaluer');
  });
});

describe('CALX115 — hauteurToitPourOmbrageM : une seule règle de hauteur, partagée', () => {
  const MESURE: Batiment = { id: 'bat-1', hauteurM: 9, source: 'relevé chantier' };

  it('hauteur SAISIE du bâtiment du pan : elle prime', () => {
    expect(hauteurToitPourOmbrageM([MESURE], 'bat-1')).toBe(9);
  });

  it('aucun bâtiment décrit (ou pan sans bâtiment) : l’hypothèse affichée, jamais un zéro', () => {
    expect(hauteurToitPourOmbrageM([], 'bat-1')).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(hauteurToitPourOmbrageM(undefined, null)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(hauteurToitPourOmbrageM([MESURE], 'bat-2')).toBe(FLOORS * FLOOR_HEIGHT_M);
  });

  it('hauteur sans provenance : ce n’est pas une saisie exploitable → l’hypothèse', () => {
    expect(hauteurToitPourOmbrageM([{ id: 'bat-1', hauteurM: 9 }], 'bat-1')).toBe(FLOORS * FLOOR_HEIGHT_M);
  });
});

describe('CALX132 — libelleBoutonOsm : le texte du bouton de reprise, jamais un chiffre recalculé', () => {
  const AVEC_HAUTEUR: BatimentOsmServeur = {
    osm_way_id: 123456,
    height_m: 7.5,
    levels: 2,
    source: 'openstreetmap',
    provenance: { height_m: 'osm:height', levels: 'osm:building:levels' },
    non_renseignes: {},
  };

  it('cite la hauteur, la voie OSM — dérivées de la proposition, aucun recalcul', () => {
    const p = propositionOsm(AVEC_HAUTEUR)!;
    expect(libelleBoutonOsm(p)).toBe('Reprendre la hauteur OSM (7,5 m — openstreetmap, way 123456)');
  });

  it('niveaux seuls : le libellé parle de niveaux, jamais d’une hauteur inventée', () => {
    const p = propositionOsm({ ...AVEC_HAUTEUR, height_m: null, source: null })!;
    expect(libelleBoutonOsm(p)).toBe('Reprendre les niveaux OSM (2 — openstreetmap, way 123456)');
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL27 — les OMBRES TRACÉES voyagent avec le document : la matrice se recalcule à
// l'identique à la réouverture (C-ACAL-045). Le chemin est le VRAI : `serializeLayout` →
// `hydrateFromDevis` → `appliquerHydratationAuCtx` → `matriceOmbrageDesSources` (l'unique
// calcul, celui que `recomputeFactors` appelle).
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL27 — ombres tracées : sérialisées, relues, même matrice', () => {
  const RING: [number, number][] = [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002], [-7.6, 33.5002]];
  const ombre = {
    id: 'shade-1',
    base: [-7.5999, 33.49985] as [number, number], // pied au sud du toit
    tip: [-7.5999, 33.50005] as [number, number], // bout d'ombre vers le nord
    heightM: 40, // un immeuble de 40 m à ~28 m au sud : il masque le soleil d'hiver
    halfWidthM: 6,
  };
  function ctxAtelier(ombres: typeof ombre[]): Ctx {
    const zone = {
      id: 'z1', label: 'Pan', vertices: RING, obstacles: [], roofType: 'flat' as const, pitchDeg: 10,
      facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, result: null, renderPlan: null,
    };
    return {
      areas: [zone], activeAreaId: 'z1', vertices: RING, obstacles: [], roofType: 'flat', pitchDeg: 10,
      facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, layoutPlan: null,
      layoutOptimalCount: 0, shadeObstructions: ombres.map((o) => ({ ...o })), environment: [],
      shadeFactors: null, shadeAnnualFactor: 1, prodPerKwc: null, sunDay: Number.NaN, sunHour: Number.NaN,
      centroid: [-7.5999, 33.5001], centroidLat: 33.5001,
    } as unknown as Ctx;
  }

  it('ombre tracée → serializeLayout → hydrateFromDevis → appliquerHydratationAuCtx → recomputeFactors donne la même matrice et la même liste shadeObstructions', () => {
    const avant = ctxAtelier([ombre]);
    const calcul = matriceOmbrageDesSources(avant, 6);
    expect(calcul.factors).not.toBeNull();
    // L'ombre abaisse bien la matrice (sinon le test ne prouverait rien).
    expect(calcul.factors!.flat().some((v) => v < 1)).toBe(true);
    avant.shadeFactors = calcul.factors;
    const doc = serializeLayout(avant);
    expect(doc.shadeObstructions).toHaveLength(1);

    const h = hydrateFromDevis({ id: 3, geometrie: { roof_layout: doc }, cibleVendue: false });
    const apres = ctxAtelier([]);
    appliquerHydratationAuCtx(apres, h);
    expect(apres.shadeObstructions).toEqual(avant.shadeObstructions);
    const recalcul = matriceOmbrageDesSources(apres, 6);
    expect(serializeShading(recalcul.factors)).toEqual(doc.shading12x24);

    // Enregistrer à nouveau sans geste : les deux clés sont identiques.
    apres.shadeFactors = recalcul.factors;
    const doc2 = serializeLayout(apres);
    expect(doc2.shadeObstructions).toEqual(doc.shadeObstructions);
    expect(doc2.shading12x24).toEqual(doc.shading12x24);
  });

  it('sans shadeObstructions émises (le défaut d’avant), la matrice recalculée à la réouverture est nulle', () => {
    const avant = ctxAtelier([ombre]);
    avant.shadeFactors = matriceOmbrageDesSources(avant, 6).factors;
    const doc = serializeLayout(avant);
    delete (doc as { shadeObstructions?: unknown }).shadeObstructions;
    const apres = ctxAtelier([]);
    appliquerHydratationAuCtx(apres, hydrateFromDevis({ id: 3, geometrie: { roof_layout: doc } }));
    expect(matriceOmbrageDesSources(apres, 6).factors).toBeNull();
  });

  it('une ombre que l’atelier ne sait pas recalculer (contour, centre seul) est transmise telle quelle', () => {
    const exemple = [
      { id: 'sh-1', kind: 'mur', contour: [[-7.6003, 33.5001], [-7.6001, 33.5001], [-7.6001, 33.50015]], hauteurM: 3, source: 'saisie' },
      { id: 'sh-2', kind: 'arbre', centre: [-7.6004, 33.4999], rayonM: 2, hauteurM: 6, source: 'saisie' },
    ];
    const lu = deserializeShadeObstructions({ shadeObstructions: exemple });
    expect(lu.lues).toEqual([]);
    expect(serializeShadeObstructions(lu.lues, lu.nonLues)).toEqual({ shadeObstructions: exemple });
  });
});
