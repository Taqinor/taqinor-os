// @vitest-environment jsdom
// CAL60 — hauteur de bâtiment saisissable (repli AFFICHÉ comme hypothèse). Le calcul
// d'ombrage (hourlyShadeFactors, etc.) est déjà testé ailleurs (shadingWJ19.test.ts) ;
// ce fichier couvre uniquement la résolution PURE de la hauteur (le reste de
// `createShadingUi` a besoin d'une carte MapLibre + du DOM, hors de portée d'un test pur).
import { sunDirection } from '../../lib/roofPro2'; // ACAL459
import { lignesSensDePose } from './orientationOmbre'; // ACAL552
import { annualShadeFactor, MID_MONTH_DAY_OF_YEAR, DIFFUSE_FRACTION_WHEN_SHADED } from '../../lib/shadingEngine'; // ACAL459
import { tableOmbrage, recomposerMatrice, ajouterTableOmbrage, garderTableRelue, signerSources } from './tableOmbrage'; // ACAL459
import { facteurVueCiel, vueCielDuPan, ajouterVueCiel, garderVueCielRelue } from './vueCiel'; // ACAL460
import { describe, expect, it } from 'vitest';
import { htmlLegendeAcces, phraseCouleursAcces, poserLegendeAcces } from './legendeAcces'; // ACAL441, ACAL1821
import { choisirPaletteAcces, solarAccessColorRGB } from '../../lib/shadingEngine'; // ACAL441, ACAL1821
import {
  effectiveBuildingHeightM,
  filtrerEmplacementsSousSeuil,
  hauteurToitPourOmbrageM,
  heatmapAccessValues,
  HEATMAP_MONTH_LABELS,
  libelleBoutonOsm,
  moduleShadeReading,
  moduleShadeReadingsForPanels,
  phraseOmbrageParModule, // item 14 (T4-U1-023)
  type ModuleShadeReading,
  matriceOmbrageDesSources, // ACAL27
  htmlProposition, // ACAL714
  seuilRetraitDesReglages, // ACAL714
  lireSeuilSaisi, // ACAL548
  phraseOrigineSeuil, // ACAL548
  executerAvecCarte, // ACAL726
  teteInfoBulleModule, // ACAL729
  libelleLigneOmbre, // ACAL497
  createShadingUi, // ACAL504
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
import { poserChoixOptimisation } from './optimizer'; // ACAL1532
import { propositionOsm, type Batiment, type BatimentOsmServeur } from './batiment';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';
import { phraseVerdictOmbrage } from './verdictOmbrage'; // ACAL715
import { libelleModuleAffecte } from './libellesAffectation'; // ACAL729
import { buildAffectationColoring } from './scene3d'; // ACAL729
import { registreAtelier } from './numerotation'; // R3 (visuel lot 7)
import { fallbackPerKwc } from '../../lib/productionEngine';
import { hourlyShadeFactors, proposeShadedRemoval, type ShadeObstructionENU } from '../../lib/shadingEngine';

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
/* Item 14 (T4-U1-023) — en Expert, la phrase comptait TOUTES les cellules du pavage (« 3 module(s) sur 6 ») alors que
   3 panneaux sont posés : elle compte les panneaux POSÉS (cellules rendues, sinon les `count` premières). */
describe('T4-U1-023 — phraseOmbrageParModule : sur les panneaux posés seulement', () => {
  const LAT = 33.5;
  const cheminee: ShadeObstructionENU = {
    x: 0, y: -3, effHeightM: 5, halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [[-1.5, -4.5], [1.5, -4.5], [1.5, -1.5], [-1.5, -1.5]],
  };
  // 6 cellules : les 3 premières à l'ombre de la cheminée, les 3 suivantes à 40 m ; 3 posées (0, 1, 4).
  const grille = [{ cx: 0, cy: 0 }, { cx: 0.5, cy: 0 }, { cx: -0.5, cy: 0 }, { cx: 40, cy: 0 }, { cx: 41, cy: 0 }, { cx: 42, cy: 0 }];
  it('3 posés (dont 2 à l’ombre) sur 6 cellules : « 2 module(s) sur 3 », jamais « sur 6 »', () => {
    const lectures = moduleShadeReadingsForPanels(LAT, [cheminee], grille, true) as ModuleShadeReading[];
    const phrase = phraseOmbrageParModule(lectures, [0, 1, 4], 6) as string;
    expect(phrase).toContain('2 module(s) sur 3 couvert(s)');
    expect(phrase).not.toContain('sur 6');
  });
  it('sans cellules rendues : les `count` premières cellules (règle du rendu 3D)', () => {
    const lectures = moduleShadeReadingsForPanels(LAT, [cheminee], grille, true) as ModuleShadeReading[];
    expect(phraseOmbrageParModule(lectures, [], 3)).toContain('3 module(s) sur 3 couvert(s)');
  });
});

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

// ═══ ACAL459 — table des facteurs d'ombrage DIRECT par direction du soleil ═══
describe('ACAL459 — table par direction', () => {
  // Une obstruction à 10 m au sud (y = −10), hauteur 5 m, demi-largeur 3 m, un module à l'origine :
  // elle coupe le soleil sous atan(5/10) = 26,57° (valeur dérivée à la main) dans son cône d'azimut.
  const mur: ShadeObstructionENU[] = [{ x: 0, y: -10, effHeightM: 5, halfWidthM: 3 }];
  const un = [{ x: 0, y: 0 }];
  const case_ = (t: NonNullable<ReturnType<typeof tableOmbrage>>, az: number, h: number) =>
    t.facteurs[t.hauteursDeg.indexOf(h)][t.azimutsDeg.indexOf(az)];

  it('case (sud, 20°) = 0, (sud, 30°) = 1 ; hors du cône d’azimut = 1', () => {
    const t = tableOmbrage(un, mur, 'sig')!;
    expect(case_(t, 180, 20)).toBe(0);
    expect(case_(t, 180, 30)).toBe(1);
    expect(case_(t, 0, 20)).toBe(1); // mutant « ignorer le cône d'azimut » ⇒ 0 ⇒ échec
    expect(t.methode).toBe('centres_de_modules');
    expect(t.signature).toBe('sig');
    expect(t.facteurs).toHaveLength(t.hauteursDeg.length);
    t.facteurs.forEach((l) => expect(l).toHaveLength(t.azimutsDeg.length));
  });

  it('chaque case = part des modules dont le rayon n’est pas coupé (jamais mêlée au diffus)', () => {
    // Deux modules : un derrière l'obstruction, un 12 m plus à l'ouest hors de son cône (y = 0).
    const t = tableOmbrage([{ x: 0, y: 0 }, { x: -12, y: 0 }], mur, 's')!;
    expect(case_(t, 180, 20)).toBe(0.5);
    expect(case_(t, 180, 30)).toBe(1);
  });

  it('sans obstruction ou sans module : aucune table (jamais « 1 partout »)', () => {
    expect(tableOmbrage(un, [], 's')).toBeNull();
    expect(tableOmbrage([], mur, 's')).toBeNull();
  });

  it('le pas de grille garde le facteur annuel recomposé à moins de 2 points de l’exact', () => {
    const lat = 33.6;
    const modules = Array.from({ length: 24 }, (_, i) => ({ x: (i % 8) * 1.15 - 4, y: Math.floor(i / 8) * 1.8 - 2 }));
    const scenarios: ShadeObstructionENU[][] = [
      [{ x: 0, y: -8, effHeightM: 6, halfWidthM: 3 }],
      [{ x: 0, y: -6, effHeightM: 10, halfWidthM: 14 }],
      [{ x: 0, y: -7, effHeightM: 5, halfWidthM: 6 }, { x: 12, y: 0, effHeightM: 7, halfWidthM: 4 }, { x: -12, y: 2, effHeightM: 7, halfWidthM: 4 }],
    ];
    const prod = fallbackPerKwc();
    const soleil = (m: number, h: number) => sunDirection(lat, MID_MONTH_DAY_OF_YEAR[m], h + 0.5);
    for (const obs of scenarios) {
      const mats = modules.map((p) => hourlyShadeFactors(lat, obs, p.x, p.y));
      const exact = mats[0].map((_r, m) => mats[0][m].map((_v, h) => mats.reduce((s, mt) => s + mt[m][h], 0) / mats.length));
      const recompose = recomposerMatrice(tableOmbrage(modules, obs, 's')!, soleil, DIFFUSE_FRACTION_WHEN_SHADED);
      expect(Math.abs(annualShadeFactor(prod, recompose, lat) - annualShadeFactor(prod, exact, lat))).toBeLessThan(0.02);
    }
  });

  it('sérialisation : la table est écrite par ajouterTableOmbrage, relue seulement à signature inchangée', () => {
    const t = tableOmbrage(un, mur, 'a')!;
    const g: { shadeTable?: typeof t } = {};
    ajouterTableOmbrage(g, t);
    expect(g.shadeTable).toStrictEqual(t);
    ajouterTableOmbrage(g, null); // rien à écrire : la clé reste ce qu'elle était (jamais un 1 écrit)
    garderTableRelue(g, 'a');
    expect(g.shadeTable).toBeDefined();
    garderTableRelue(g, 'b'); // sources déplacées ⇒ clé retirée
    expect(g.shadeTable).toBeUndefined();
    expect(signerSources('x')).toBe(signerSources('x'));
    expect(signerSources('x')).not.toBe(signerSources('y'));
  });
});

// ═══ ACAL460 — facteur de vue du ciel d'un pan ═══
describe('ACAL460 — facteur de vue du ciel', () => {
  // Le prédicat de blocage est injecté. Plan horizontal, ciel coupé sous la hauteur h : poids = sin a · cos a,
  // ∫ de h à 90° ÷ ∫ de 0 à 90° = cos²h (dérivation à la main) ; cos²20° = 0,8830.
  const mur: ShadeObstructionENU[] = [{ x: 0, y: -10, effHeightM: 5, halfWidthM: 3 }];
  const un = [{ x: 0, y: 0 }];
  const sousHauteur = (h: number) => (_x: number, _y: number, a: number) => a < h;

  it('coupé sous 20° partout ⇒ cos²(20°) à moins de 2 points ; mutant sans pesée par le cosinus ⇒ 0,658', () => {
    const f = facteurVueCiel(un, mur, 0, 180, sousHauteur(20))!;
    expect(Math.abs(f - Math.cos((20 * Math.PI) / 180) ** 2)).toBeLessThan(0.02);
    expect(f).toBeGreaterThan(0.85); // sans la pesée par le cosinus (1 − cos 70° = 0,658) ⇒ échec
  });

  it('jamais coupé ⇒ 1 (plat et incliné) ; sans obstruction ou sans module ⇒ aucune valeur', () => {
    expect(facteurVueCiel(un, mur, 0, 180, () => false)).toBe(1);
    expect(facteurVueCiel(un, mur, 30, 200, () => false)).toBe(1);
    expect(facteurVueCiel(un, [], 30, 180)).toBeNull();
    expect(facteurVueCiel([], mur, 30, 180)).toBeNull();
    expect(vueCielDuPan(null, 's')).toBeNull();
  });

  it('un mur réel au sud coupe moins que 1 un plan plein sud ; moyenne des modules', () => {
    const f = facteurVueCiel(un, mur, 30, 180)!;
    expect(f).toBeLessThan(1);
    expect(f).toBeGreaterThan(0.9); // un mur de 3 m de demi-largeur ne cache qu'une petite part du dôme
  });

  it('écriture : méthode isotrope sans horizon ; relue seulement à signature inchangée', () => {
    const v = vueCielDuPan(0.9, 'a')!;
    expect(v.methode).toEqual({ diffus: 'isotrope', horizon: false, resolution: 'centres_de_modules' });
    const g: { skyViewFactor?: typeof v } = {};
    ajouterVueCiel(g, { skyViewByZone: { z: v } }, 'z');
    ajouterVueCiel(g, { skyViewByZone: { z: null } }, 'z'); // rien à écrire : jamais un 1
    garderVueCielRelue(g, { signatureOmbrage: 'a' });
    expect(g.skyViewFactor).toStrictEqual(v);
    garderVueCielRelue(g, { signatureOmbrage: 'b' });
    expect(g.skyViewFactor).toBeUndefined();
  });
});

describe('ACAL441 : la légende reprend les couleurs de solarAccessColorRGB', () => {
  it('trois repères lus de la fonction, extrémités nommées, période affichée', () => {
    const html = htmlLegendeAcces('décembre');
    for (const a of [0, 0.5, 1]) {
      const c = solarAccessColorRGB(a);
      expect(html).toContain(`rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)})`);
    }
    expect(html).toContain('à l’ombre (0 %)');
    expect(html).toContain('plein soleil (100 %)');
    expect(html).toContain('Période évaluée : décembre');
  });
  it('sans note dans la page, rien n’est créé', () => {
    expect(() => poserLegendeAcces(null, 'année entière')).not.toThrow();
  });

  // ACAL1821 — la note ne nomme aucune couleur absente de la palette active (atelier : bleu nuit → or), le site garde
  // son texte ; la légende prend toute la largeur d'une rangée flex (bornes aux deux bouts). Mutant : « vert / rouge ».
  it('palette atelier : la note ne dit plus « vert / rouge » ; palette du site : texte inchangé ; légende pleine largeur', () => {
    try {
      choisirPaletteAcces('atelier');
      const phrase = phraseCouleursAcces('en décembre');
      expect(phrase).not.toMatch(/vert|rouge/);
      expect(phrase).toContain('de l’ombre (0 %) au plein soleil (100 %) en décembre');
    } finally { choisirPaletteAcces('site'); }
    expect(phraseCouleursAcces('toute l’année')).toBe('vert = plein soleil toute l’année, rouge = souvent à l’ombre');
    const rangee = document.createElement('div');
    rangee.innerHTML = '<p id="note"></p>';
    poserLegendeAcces(rangee.querySelector('#note') as HTMLElement, 'année entière');
    const legende = rangee.querySelector('#rp9-heatmap-legend') as HTMLElement;
    expect([legende.style.width, legende.style.flexBasis]).toEqual(['100%', '100%']);
  });
});

// ACAL552 — les deux poses chiffrées sous les puces Portrait / Paysage.
describe('ACAL552 — lignesSensDePose', () => {
  const pack = {
    portrait: { panels: [{ cx: 0, cy: 0 }, { cx: 1, cy: 0 }, { cx: 2, cy: 0 }] },
    landscape: { panels: [{ cx: 0, cy: 0 }, { cx: 1, cy: 0 }] },
  };
  it('deux lignes chiffrées, accès injecté moyenné sur les N premiers', () => {
    const lignes = lignesSensDePose(pack, (p) => p.map((_, i) => (i === 0 ? 1 : 0.5)), (g) => Math.min(2, g.panels.length));
    expect(lignes).toEqual([
      { sens: 'portrait', n: 2, acces: 0.75 },
      { sens: 'landscape', n: 2, acces: 0.75 },
    ]);
  });
  it('sans source (accès null) ⇒ null, jamais 100 %', () => {
    expect(lignesSensDePose(pack, () => null, (g) => g.panels.length)).toBeNull();
  });
});

// ACAL714 — le seuil de retrait est le RÉGLAGE société ; sans lui, aucune proposition et le dire.
describe('ACAL714 — seuil de retrait réglé par la société', () => {
  const reglage = (valeur: unknown) => ({ simulation: { seuil_acces_retrait: { valeur, source: 'societe', reference: 'essai' } } });
  it('seuilRetraitDesReglages : un nombre dans [0, 1], sinon null (jamais un repli)', () => {
    expect(seuilRetraitDesReglages(reglage(0.6))).toBe(0.6);
    expect(seuilRetraitDesReglages(reglage(0))).toBe(0);
    for (const v of [1.2, -0.1, '0.6', NaN, null, undefined]) expect(seuilRetraitDesReglages(reglage(v))).toBeNull();
    expect(seuilRetraitDesReglages(null)).toBeNull();
    expect(seuilRetraitDesReglages({})).toBeNull();
  });
  it('seuil null : aucun bouton « Retirer ces modules », la ligne dit où régler', () => {
    const html = htmlProposition(null, null, true, '');
    expect(html).not.toContain('Retirer ces modules');
    expect(html).toContain('Retrait proposé : aucun seuil réglé par votre société (Réglages › simulation)');
  });
  it('seuil 0,6 : la proposition vise les modules de 0,4 et 0,5, avec le bouton et « sous 60 % »', () => {
    const p = proposeShadedRemoval([0.9, 0.4, 0.9, 0.5, 0.9], 0.72, 0.6);
    const html = htmlProposition(p, 0.6, true, 'nº2, nº4');
    expect(html).toContain('Retirer ces modules');
    expect(html).toContain('sous 60 %');
    expect(html).toContain('nº2, nº4');
    expect(htmlProposition(p, 0.6, false, 'nº2').includes('Retirer ces modules')).toBe(false);
    expect(htmlProposition(null, 0.6, true, '')).toBe(''); // seuil réglé, rien sous le seuil
  });
});

// ACAL715 — la phrase de verdict d'ombrage : étiquette seulement si la société a saisi ses deux bornes.
describe('ACAL715 — phraseVerdictOmbrage', () => {
  const regl = (c?: unknown, i?: unknown) => ({ simulation: {
    ...(c !== undefined ? { ombrage_borne_courant_pct: { valeur: c } } : {}),
    ...(i !== undefined ? { ombrage_borne_importante_pct: { valeur: i } } : {}),
  } });
  const phrase = (moyenne: number, reglages: unknown, lowCount: number | null = null) =>
    phraseVerdictOmbrage({ average: moyenne, lowCount }, reglages as never);

  it('sans borne (ou une seule, ou inversées) : aucune étiquette', () => {
    for (const r of [null, {}, regl(), regl(5), regl(undefined, 10), regl(10, 5), regl(5, 5)]) {
      expect(phrase(0.93, r)).toBe('Ombrage du pan : 7 % de l’énergie perdue (estimation de l’atelier, année entière).');
    }
  });
  it('bornes 5 et 10 : 7 % courante, 12 % importante, 3 % faible', () => {
    expect(phrase(0.93, regl(5, 10))).toContain('lecture « courante »');
    expect(phrase(0.88, regl(5, 10))).toContain('lecture « importante »');
    expect(phrase(0.97, regl(5, 10))).toContain('lecture « faible »');
  });
  it('avec un seuil de retrait : « n modules sous le seuil de votre société » ; sans : rien à la place', () => {
    expect(phrase(0.93, null, 2)).toBe('Ombrage du pan : 7 % de l’énergie perdue (estimation de l’atelier, année entière) — 2 modules sous le seuil de votre société.');
    expect(phrase(0.93, null, 1)).toContain('1 module sous');
    expect(phrase(0.93, null, null)).not.toContain('seuil');
  });
  it('période mensuelle : le mois remplace « année entière »', () => {
    expect(phraseVerdictOmbrage({ average: 0.9, lowCount: null }, null, 'décembre')).toContain('estimation de l’atelier, décembre');
  });
});

// ACAL726 — la carte d'accès est allumée le temps de la capture puis remise dans son état.
describe('ACAL726 — executerAvecCarte', () => {
  const banc = (on: boolean, mois: number | null) => {
    const journal: string[] = [];
    const appliquer = (o: boolean, m: number | null) => { journal.push(`${o ? 'allumée' : 'éteinte'}:${m}`); };
    return { journal, appliquer, etat: { on, mois } };
  };
  it('éteinte : allumée en année entière pendant `fn`, puis remise éteinte avec son mois', async () => {
    const { journal, appliquer, etat } = banc(false, 5);
    let pendant = '';
    const r = await executerAvecCarte(etat, appliquer, true, async () => { pendant = journal.join(','); return 'png'; });
    expect(r).toBe('png');
    expect(pendant).toBe('allumée:null');
    expect(journal).toEqual(['allumée:null', 'éteinte:5']);
  });
  it('restaurée aussi quand `fn` échoue', async () => {
    const { journal, appliquer, etat } = banc(false, null);
    await expect(executerAvecCarte(etat, appliquer, true, async () => { throw new Error('rendu'); })).rejects.toThrow('rendu');
    expect(journal).toEqual(['allumée:null', 'éteinte:null']);
  });
  it('déjà allumée : rien n’est touché', async () => {
    const { journal, appliquer, etat } = banc(true, 2);
    expect(await executerAvecCarte(etat, appliquer, true, async () => 'png')).toBe('png');
    expect(journal).toEqual([]);
  });
  it('sans source d’ombrage : `null`, `fn` n’est pas appelée', async () => {
    const { journal, appliquer, etat } = banc(false, null);
    const fn = async () => 'png';
    let appelee = false;
    expect(await executerAvecCarte(etat, appliquer, false, async () => { appelee = true; return fn(); })).toBeNull();
    expect(appelee).toBe(false);
    expect(journal).toEqual([]);
  });
  // ACAL1621 — une source d'ombrage saisie mais AUCUN module à teinter (pas de plan pavé) : la carte ne peut pas être
  // teintée (`buildHeatmapColorFn` rend null) ; la capture n'a pas lieu (`null`), jamais la vue 3D ordinaire déposée
  // comme carte de chaleur. Avec des modules posés, la capture a lieu. Mutant : ne tester que la source ⇒ capture.
  it('source saisie mais aucun module posé : `null`, rien capturé ; modules posés : capturé', async () => {
    document.body.innerHTML = '';
    const ctx = {
      areas: [], activeAreaId: 'z1', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]], closed: true,
      obstacles: [{ id: 'o1', centerLng: -7.6001, centerLat: 33.5001, lengthM: 1, widthM: 1, heightM: 1 }],
      batiments: [], shadeObstructions: [], environment: [], activeArea: () => null, pushWorkshopHistory: () => {},
      centroid: [-7.6, 33.5], centroidLat: 33.5, prodPerKwc: null, shadeFactors: null, layoutPlan: null,
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    const teintes: unknown[] = [];
    const ui = createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: (f) => teintes.push(f) });
    let captures = 0;
    expect(await ui.avecCarteDAcces(async () => { captures += 1; return 'png'; })).toBeNull();
    expect(captures).toBe(0);
    expect(teintes).toEqual([]);
    (ctx as unknown as { layoutPlan: unknown }).layoutPlan = { grid: { panels: [{ cx: 0, cy: 0 }], kwc: 0.5 } };
    expect(await ui.avecCarteDAcces(async () => { captures += 1; return 'png'; })).toBe('png');
    expect(captures).toBe(1);
    expect(typeof teintes[0]).toBe('function'); // la carte est TEINTÉE pendant la capture
  });
});

// ACAL729 — l'info-bulle d'un module : accès annuel et chaîne en tête, jamais une valeur inventée.
describe('ACAL729 — tête d’info-bulle d’un module', () => {
  it('accès 0,82 + chaîne 2 ⇒ « Accès solaire 82 % (année entière) · chaîne 2 · »', () => {
    expect(teteInfoBulleModule(0.82, 'chaîne 2')).toBe('Accès solaire 82 % (année entière) · chaîne 2 · ');
  });
  it('sans table servie : pas de chaîne ; sans accès calculé : aucune valeur', () => {
    expect(teteInfoBulleModule(0.82, null)).toBe('Accès solaire 82 % (année entière) · ');
    expect(teteInfoBulleModule(null, 'chaîne 2')).toBe('chaîne 2 · ');
    expect(teteInfoBulleModule(null, null)).toBe('');
  });
  it('libellé d’affectation : seulement pour un module AFFECTÉ, et buildAffectationColoring le garde', () => {
    expect(libelleModuleAffecte({ module: 'a#1', chaine: 2, mppt: 1 }, 'chaine')).toBe('chaîne 2');
    expect(libelleModuleAffecte({ module: 'a#2', chaine: null, mppt: null }, 'chaine')).toBeNull();
    const c = buildAffectationColoring([{ module: 'a#1', chaine: 2, mppt: 1 }, { module: 'a#2', chaine: null, mppt: null }], 'chaine');
    expect([...c.labelByModule.entries()]).toEqual([['a#1', 'chaîne 2']]);
  });
});

// ACAL1947 — l'info-bulle d'un module lit la MÊME clé de pan que la coloration par chaîne (`clePanAffectation`,
// ACAL1516 : l'ID du pan) : un pan « Zone 1 » d'identifiant `z1` affiche sa chaîne. Mutant : `label || id` ⇒ rien.
describe('ACAL1947 — info-bulle d’un module d’un pan au libellé ≠ identifiant', () => {
  it('pan « Zone 1 » (id z1), module z1#1 en chaîne 2 ⇒ l’info-bulle dit « chaîne 2 »', () => {
    document.body.innerHTML = '';
    const zone = { id: 'z1', label: 'Zone 1', vertices: [], obstacles: [], buildingId: null };
    const ctx = {
      areas: [zone], activeAreaId: 'z1', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]], closed: true,
      // Un obstacle à hauteur saisie : une source d'ombrage, sans quoi l'info-bulle dit « non renseigné ».
      obstacles: [{ id: 'o1', centerLng: -7.6001, centerLat: 33.5001, lengthM: 1, widthM: 1, heightM: 1 }],
      batiments: [], shadeObstructions: [], environment: [], activeArea: () => zone, pushWorkshopHistory: () => {},
      centroid: [-7.6, 33.5], centroidLat: 33.5, prodPerKwc: null, shadeFactors: null,
      layoutPlan: { grid: { panels: [{ cx: 0, cy: 0 }], kwc: 0.5 } }, activePanelCellIndex: [0],
      affectationColoration: buildAffectationColoring([{ module: 'z1#1', chaine: 2, mppt: 1 }], 'chaine'),
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    const ui = createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
    expect(ui.moduleShadeTooltip(0)).toContain('chaîne 2');
  });

  // R3 (visuel lot 7) — le module porte n = 2236 au document : la ligne servie est `z1#2236`, pas `z1#1`.
  it('module numéroté 2236 au document, ligne servie z1#2236 en chaîne 3 ⇒ l’info-bulle dit « chaîne 3 »', () => {
    document.body.innerHTML = '';
    registreAtelier.absorberDocument({ zones: [{ id: 'z1', geometry: { panels: [{ cx: 0, cy: 0, n: 2236 }] } }] });
    const zone = { id: 'z1', label: 'Zone 1', vertices: [], obstacles: [], buildingId: null };
    const ctx = {
      areas: [zone], activeAreaId: 'z1', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]], closed: true,
      obstacles: [{ id: 'o1', centerLng: -7.6001, centerLat: 33.5001, lengthM: 1, widthM: 1, heightM: 1 }],
      batiments: [], shadeObstructions: [], environment: [], activeArea: () => zone, pushWorkshopHistory: () => {},
      centroid: [-7.6, 33.5], centroidLat: 33.5, prodPerKwc: null, shadeFactors: null,
      layoutPlan: { grid: { panels: [{ cx: 0, cy: 0 }], kwc: 0.5 } }, activePanelCellIndex: [0],
      affectationColoration: buildAffectationColoring([{ module: 'z1#2236', chaine: 3, mppt: 1 }], 'chaine'),
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    const ui = createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
    try {
      expect(ui.moduleShadeTooltip(0)).toContain('chaîne 3');
    } finally {
      registreAtelier.oublier();
    }
  });
});

// ACAL548 — le champ « Accès solaire minimal (%) » : lecture pure, jamais corrigée en silence.
describe('ACAL548 — lireSeuilSaisi et origine du seuil', () => {
  it('« 80 » ⇒ 0,8 ; « 80,5 » ⇒ 0,805 ; vide ⇒ retrait de la clé', () => {
    expect(lireSeuilSaisi('80')).toEqual({ ok: true, valeur: 0.8 });
    const r = lireSeuilSaisi('80,5');
    expect(r.ok && r.valeur).toBeCloseTo(0.805, 9);
    expect(lireSeuilSaisi('')).toEqual({ ok: true, valeur: null });
    expect(lireSeuilSaisi('  ')).toEqual({ ok: true, valeur: null });
  });
  it('« abc », « 120 » et « -5 » sont REFUSÉS en nommant la règle, jamais bornés', () => {
    for (const t of ['abc', '120', '-5', '80%']) {
      expect(lireSeuilSaisi(t)).toEqual({ ok: false, erreur: 'Saisissez un nombre entre 0 et 100' });
    }
    expect(lireSeuilSaisi('100')).toEqual({ ok: true, valeur: 1 });
  });
  it('seuil du dossier 80 % et réglage société 60 % ⇒ 80 % prime et le texte dit « de ce dossier »', () => {
    const reglages = { simulation: { seuil_acces_retrait: { valeur: 0.6 } } };
    expect(phraseOrigineSeuil(0.8, reglages)).toBe('valeur de ce dossier : 80 % — réglage de votre société : 60 %');
    expect(phraseOrigineSeuil(undefined, reglages)).toBe('réglage de votre société : 60 %');
    expect(phraseOrigineSeuil(0.8, null)).toBe('valeur de ce dossier : 80 %');
    expect(phraseOrigineSeuil(undefined, null)).toBe('');
    const p = proposeShadedRemoval([0.9, 0.4, 0.9, 0.7, 0.9], 0.72, 0.8);
    const html = htmlProposition(p, 0.8, true, 'nº2, nº4', 'dossier');
    expect(html).toContain('seuil de ce dossier (80 %)');
    expect(html).not.toContain('seuil de votre société');
    expect(htmlProposition(p, 0.8, true, 'nº2, nº4')).toContain('seuil de votre société');
  });
});

// ACAL497 — la ligne de la liste des ombres : une hauteur DÉDUITE se dit « à confirmer ».
describe('ACAL497 — libelleLigneOmbre', () => {
  it('10 m d’ombre, hauteur 10 m : « hauteur estimée … — à confirmer »', () => {
    expect(libelleLigneOmbre(1, 10, 10)).toBe(
      'Ombre 1 : ombre 10,0 m → hauteur estimée ~10,0 m — à confirmer (déduite de l’ombre et du soleil déclaré)');
  });
});

// ACAL1405 — le panneau « Bâtiment » est monté avant l'hydratation : il se relit après elle.
describe('ACAL1405 — bâtiment relu à la réouverture', () => {
  function monterPuisHydrater(appel: 'syncHeightUi' | 'recomputeHorizon') {
    document.body.innerHTML =
      '<div id="rp9-shade-batiment"><input id="rp9-shade-height"><p id="rp9-shade-height-note"></p></div>';
    const zone = { id: 'z1', label: 'Pan', vertices: [], obstacles: [], buildingId: null };
    const ctx = {
      areas: [zone], activeAreaId: 'z1', vertices: [], closed: false, obstacles: [], batiments: [],
      shadeObstructions: [], environment: [], activeArea: () => zone, pushWorkshopHistory: () => {},
      centroid: [-7.6, 33.5], centroidLat: 33.5, prodPerKwc: null, shadeFactors: null,
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    const ui = createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
    const doc = { buildings: [{ id: 'bat-sans-id', hauteurM: 6, source: 'mesurée au télémètre' }] };
    appliquerHydratationAuCtx(ctx, { documentRelu: doc } as never);
    ui[appel]();
    return ctx;
  }
  const val = (id: string) => (document.getElementById(id) as HTMLInputElement).value;

  it('hydratation d’un document à `buildings` : le champ hauteur et la provenance se relisent', () => {
    const ctx = monterPuisHydrater('syncHeightUi');
    expect(val('rp9-shade-height')).toBe('6,0');
    expect(val('rp11-bat-source')).toBe('mesurée au télémètre');
    expect(document.getElementById('rp9-shade-height-note')?.textContent).toBe('Hauteur saisie : 6,0 m (mesurée au télémètre).');
    expect(ctx.batiments).toMatchObject([{ id: 'bat-sans-id', hauteurM: 6, source: 'mesurée au télémètre' }]); // aucune écriture
  });

  it('la fermeture du pan relu (recomputeHorizon) relit aussi le panneau', () => {
    monterPuisHydrater('recomputeHorizon');
    expect(val('rp11-bat-source')).toBe('mesurée au télémètre');
  });
});

// ACAL1436 — « Heure solaire de l'image » accepte la virgule décimale comme le point.
describe('ACAL1436 — heure solaire « 10,5 »', () => {
  function saisir(texte: string): string {
    document.body.innerHTML = '<input id="rp9-shade-hour"><p id="rp9-shade-hour-value"></p>';
    const ctx = {
      areas: [], activeAreaId: '', vertices: [], closed: false, obstacles: [], batiments: [], shadeObstructions: [],
      environment: [], activeArea: () => null, pushWorkshopHistory: () => {},
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
    const champ = document.getElementById('rp9-shade-hour') as HTMLInputElement;
    champ.value = texte;
    champ.dispatchEvent(new Event('input'));
    return document.getElementById('rp9-shade-hour-value')?.textContent ?? '';
  }

  it('« 10,5 » donne « 10 h 30 » comme « 10.5 » ; « abc » reste refusé par le même message', () => {
    expect(saisir('10.5')).toBe('10 h 30');
    expect(saisir('10,5')).toBe('10 h 30');
    expect(saisir('abc')).toBe('Heure solaire illisible : un nombre entre 0 et 24.');
  });
});

// ACAL1921 (revue) — GARDE du chemin de relecture du seuil, pas une preuve de correctif : sur le boot d'un DOCUMENT,
// `hydrateFromDevis` rend `shadeObstructions` (tableau, vide compris) ⇒ l'entrée du constructeur appelle déjà
// `rafraichirOmbres` (`if (h.shadeObstructions !== undefined)`), et le champ relit le seuil semé par
// `deserializeLayout`. La cause du champ vide observé sur le calepinage 2051 est donc AILLEURS (à rejouer en direct).
describe('ACAL1921 — garde : le boot d’un document relit le seuil d’accès solaire', () => {
  it('document (seuil 98 %, aucune ombre tracée) : l’hydratation porte `shadeObstructions` et le rafraîchissement lit 98', async () => {
    const { semerOptimisationDepuisDocument } = await import('./optimisationDocument');
    const { exempleRoofLayoutV2, ouvrirAtelier } = await import('./harnaisDocument');
    document.body.innerHTML = '<input id="rp9-seuil-acces"><p id="rp9-seuil-acces-erreur"></p><p id="rp9-seuil-acces-note"></p>';
    const ctx = {
      areas: [], activeAreaId: '', vertices: [], closed: false, obstacles: [], batiments: [], shadeObstructions: [],
      environment: [], activeArea: () => null, pushWorkshopHistory: () => {},
    } as unknown as Ctx;
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    try {
      semerOptimisationDepuisDocument({});
      const ui = createShadingUi(ctx, { map, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
      const champ = document.getElementById('rp9-seuil-acces') as HTMLInputElement;
      expect(champ.value).toBe('');
      const doc = JSON.parse(JSON.stringify(exempleRoofLayoutV2())) as Record<string, unknown>;
      delete doc.shadeObstructions;
      doc.optimisation = { seuilAccesSolaire: 0.98 };
      const { h } = ouvrirAtelier({ id: null, geometrie: { roof_layout: doc as never }, cibleVendue: false });
      expect(h.shadeObstructions).toEqual([]); // défini ⇒ la ligne de l'entrée rafraîchit
      ui.rafraichirOmbres();
      expect(champ.value).toBe('98');
    } finally { semerOptimisationDepuisDocument({}); }
  });
});

// ACAL504 — la hauteur du bâtiment saisie SANS provenance est refusée sous le champ ET dans la barre d'état.
describe('ACAL504 — refus d’une hauteur sans provenance', () => {
  function monter() {
    document.body.innerHTML =
      '<div id="rp9-shade-batiment"><input id="rp9-shade-height"><p id="rp9-shade-height-note"></p></div>';
    const zone = { id: 'z1', label: 'Pan', vertices: [], obstacles: [], buildingId: null };
    const ctx = {
      areas: [zone], activeAreaId: 'z1', vertices: [], closed: false, obstacles: [], batiments: [],
      shadeObstructions: [], activeArea: () => zone, pushWorkshopHistory: () => {},
    } as unknown as Ctx;
    const statuts: string[] = [];
    const map = new Proxy({}, { get: () => () => undefined }) as never;
    createShadingUi(ctx, { map, setStatus: (m) => statuts.push(m), recalcDisplays: () => {}, applyHeatmap: () => {} });
    return { ctx, statuts };
  }

  it('6 m sans provenance : rien enregistré, message sous le champ et en barre d’état, focus sur la provenance', () => {
    const { ctx, statuts } = monter();
    const h = document.getElementById('rp9-shade-height') as HTMLInputElement;
    h.value = '6';
    h.dispatchEvent(new Event('change', { bubbles: true }));
    expect(document.getElementById('rp11-bat-erreur')?.textContent).toContain('Provenance obligatoire');
    expect(statuts).toContain('Hauteur non enregistrée — champ « Provenance de la hauteur » à renseigner.');
    expect(document.activeElement?.id).toBe('rp11-bat-source');
    expect(ctx.batiments.some((b) => (b as { hauteurM?: number }).hauteurM === 6)).toBe(false);
  });

  it('6 m + « mesurée au télémètre » : la hauteur est rangée avec sa source', () => {
    const { ctx } = monter();
    const src = document.getElementById('rp11-bat-source') as HTMLInputElement;
    src.value = 'mesurée au télémètre';
    const h = document.getElementById('rp9-shade-height') as HTMLInputElement;
    h.value = '6';
    h.dispatchEvent(new Event('change', { bubbles: true }));
    expect(document.getElementById('rp11-bat-erreur')?.textContent).toBe('');
    expect(hauteurToitPourOmbrageM(ctx.batiments, null)).toBe(6);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL1407 + ACAL1501 (D-ACAL-83, fondateur 23/11/2026) — l'ombre proche se mesure sur les
// panneaux POSÉS (moyenne de leurs matrices), et sans panneau sur une grille du pan. Avant :
// au seul centroïde — une cheminée posée au centre donnait −72 % quelle que soit sa hauteur.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL1407 + ACAL1501 — ombre proche mesurée sur les panneaux posés', () => {
  const LAT = 33.5;
  const CENTRE: [number, number] = [-7.6, LAT];
  const M_PAR_DEG = (Math.PI / 180) * 6378137; // rayon WGS84 de lib/geo.ts
  const COS = Math.cos((LAT * Math.PI) / 180);
  const versLngLat = (x: number, y: number): [number, number] => [CENTRE[0] + x / (M_PAR_DEG * COS), CENTRE[1] + y / M_PAR_DEG];
  // Toit plat 10 × 7 m centré sur le centroïde ; cheminée 1 × 1 m de 3 m.
  const RING = [versLngLat(-5, -3.5), versLngLat(5, -3.5), versLngLat(5, 3.5), versLngLat(-5, 3.5)];
  function cheminee(x: number, y: number) {
    const [lng, lat] = versLngLat(x, y);
    return { id: 'ch-1', centerLng: lng, centerLat: lat, lengthM: 1, widthM: 1, heightM: 3, type: 'cheminee' };
  }
  function ctxPan(obstacle: ReturnType<typeof cheminee>): Ctx {
    const zone = { id: 'z1', label: 'Pan', vertices: RING, obstacles: [obstacle], buildingId: null };
    return {
      areas: [zone], activeAreaId: 'z1', vertices: RING, closed: true, obstacles: [obstacle], batiments: [],
      roofType: 'flat', pitchDeg: 10, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true,
      layoutPlan: null, layoutOptimalCount: 0, shadeObstructions: [], environment: [], shadeFactors: null,
      shadeAnnualFactor: 1, prodPerKwc: null, sunDay: Number.NaN, sunHour: Number.NaN,
      centroid: CENTRE, centroidLat: LAT, activeArea: () => zone, pushWorkshopHistory: () => {},
    } as unknown as Ctx;
  }
  const rangee = (y: number) => [-3, -1.5, 0, 1.5, 3].map((x) => ({ x, y }));
  const perte = (m: number[][] | null) => 1 - annualShadeFactor(fallbackPerKwc(), m, LAT);
  // Oracle INDÉPENDANT : la moyenne, case par case, des matrices évaluées à chaque panneau.
  function moyenneDesPanneaux(ctx: Ctx, points: { x: number; y: number }[]): number[][] {
    const enu: ShadeObstructionENU[] = ctx.obstacles.map((o) => {
      const x = (o.centerLng - CENTRE[0]) * M_PAR_DEG * COS;
      const y = (o.centerLat - CENTRE[1]) * M_PAR_DEG;
      return { x, y, effHeightM: o.heightM as number, halfWidthM: Math.hypot(o.lengthM, o.widthM) / 2,
        footprint: [[x - 0.5, y - 0.5], [x + 0.5, y - 0.5], [x + 0.5, y + 0.5], [x - 0.5, y + 0.5]] };
    });
    const mats = points.map((p) => hourlyShadeFactors(LAT, enu, p.x, p.y));
    return mats[0].map((row, m) => row.map((_v, h) => mats.reduce((s, mat) => s + mat[m][h], 0) / mats.length));
  }
  const egales = (a: number[][] | null, b: number[][]) => a!.forEach((row, m) => row.forEach((v, h) => expect(v).toBeCloseTo(b[m][h], 9)));

  it('cheminée au centre, panneaux posés ailleurs (rangée 3 m au sud) : perte proche de 0, plus les −72 % du centroïde', () => {
    const ctx = ctxPan(cheminee(0, 0));
    const calcul = matriceOmbrageDesSources(ctx, 6, rangee(-3));
    expect(perte(calcul.factors)).toBeLessThan(0.02);
    egales(calcul.factors, moyenneDesPanneaux(ctx, rangee(-3)));
  });

  it('cheminée 1 m au sud de la rangée : les panneaux posés perdent, et la matrice est leur moyenne', () => {
    const ctx = ctxPan(cheminee(0, 0.5));
    const calcul = matriceOmbrageDesSources(ctx, 6, rangee(1.5));
    egales(calcul.factors, moyenneDesPanneaux(ctx, rangee(1.5)));
    expect(perte(calcul.factors)).toBeGreaterThan(0.005);
    expect(perte(calcul.factors)).toBeLessThan(0.5);
  });

  it('pan sans panneau : une grille du pan (empreinte de la cheminée exclue), jamais le seul centroïde', () => {
    const ctx = ctxPan(cheminee(0, 0));
    const grille = matriceOmbrageDesSources(ctx, 6, []);
    expect(matriceOmbrageDesSources(ctx, 6)).toEqual(grille);
    expect(perte(grille.factors)).toBeGreaterThan(0);
    expect(perte(grille.factors)).toBeLessThan(0.2);
  });

  it('ACAL1501 — un document rouvert avec obstacle haut rend le même facteur annuel que la session de pose', () => {
    const avant = ctxPan(cheminee(0, 0.5));
    const session = matriceOmbrageDesSources(avant, 6, rangee(1.5)).factors;
    avant.shadeFactors = session;
    const facteurSession = annualShadeFactor(fallbackPerKwc(), session, LAT);
    const doc = serializeLayout(avant);
    const apres = ctxPan(cheminee(0, 0.5));
    appliquerHydratationAuCtx(apres, hydrateFromDevis({ id: 7, geometrie: { roof_layout: doc }, cibleVendue: false }));
    expect(apres.shadeAnnualFactor).toBeCloseTo(facteurSession, 9);
    expect(apres.shadeAnnualFactor).toBeLessThan(1); // l'obstacle haut garde son ombre
    expect(apres.shadeAnnualFactor).toBeGreaterThan(0.5); // jamais la saturation du centroïde (≈ 0,28)
  });

  // ACAL2031 — figé SANS `opts.chiffrage` (site public ; l'aperçu `/preview/toiture-3d-pro-11` est retiré du build,
  // ACAL332) : la moyenne sur les panneaux POSÉS (D-ACAL-83) n'est pas réservée à l'ERP.
  it('sans chiffrage : l’ombrage recalculé est la moyenne des panneaux posés, pas la grille du pan', () => {
    const ctx = ctxPan(cheminee(0, 0.5));
    expect((ctx as unknown as { opts?: { chiffrage?: unknown } }).opts?.chiffrage).toBeUndefined();
    Object.assign(ctx, { layoutPlan: { grid: { panels: rangee(1.5).map((p) => ({ cx: p.x, cy: p.y })) } }, layoutOptimalCount: 5 });
    const ui = createShadingUi(ctx, {
      map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {},
    });
    ui.recomputeShading();
    expect(ctx.shadeFactors).toEqual(matriceOmbrageDesSources(ctx, 6, rangee(1.5)).factors);
    expect(ctx.shadeFactors).not.toEqual(matriceOmbrageDesSources(ctx, 6).factors);
  });

  it('« Effacer les ombres » recalcule sur les sources restantes : la cheminée garde son ombre', () => {
    const ctx = ctxPan(cheminee(0, 0));
    const ui = createShadingUi(ctx, {
      map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {},
    });
    ctx.shadeObstructions.push({ id: 's1', base: versLngLat(0, -30), tip: versLngLat(0, 10), heightM: 30, halfWidthM: 6 });
    ui.reset();
    expect(ctx.shadeObstructions).toHaveLength(0);
    expect(ctx.shadeFactors).toEqual(matriceOmbrageDesSources(ctx, 6).factors);
    expect(ctx.shadeAnnualFactor).toBeLessThan(1);
  });

  // ACAL1620 — T2-F2-RESU-b-006 : le calepinage rouvert (obstacle 3 × 3 × 8 m, accès enregistré, AUCUNE ombre tracée) disait
  // « non renseigné — aucune obstruction n'a été saisie » jusqu'à ce qu'on retouche la hauteur. Ordre réel d'un boot :
  // l'UI d'ombrage naît d'abord (rien à ombrer), puis le document est relu, le pan et sa pose arrivent, l'écran se redessine.
  it('ACAL1620 — document rouvert avec obstacle 3×3×8 m et sans shadeObstructions : l’accès est chiffré sans geste', () => {
    document.body.innerHTML = '<div id="parent"><div id="rp9-solar-access"></div></div>';
    const grand = { ...cheminee(0, 0.5), lengthM: 3, widthM: 3, heightM: 8 };
    const avant = ctxPan(grand);
    avant.shadeFactors = matriceOmbrageDesSources(avant, 6, rangee(4)).factors;
    const doc = serializeLayout(avant);
    delete (doc as { shadeObstructions?: unknown }).shadeObstructions; // document d'avant ACAL27 : aucune ombre tracée

    const ctx = ctxPan(grand);
    ctx.obstacles.length = 0; // le pan n'est pas encore rechargé
    const ui = createShadingUi(ctx, {
      map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {},
    });
    const bloc = document.getElementById('rp9-solar-access')!;
    expect(bloc.textContent).toContain('non renseigné'); // l'état de naissance, avant la relecture

    appliquerHydratationAuCtx(ctx, hydrateFromDevis({ id: 9, geometrie: { roof_layout: doc }, cibleVendue: false }));
    ctx.obstacles.push(grand); // le pan relu pose ses obstacles
    Object.assign(ctx, { layoutPlan: { grid: { panels: rangee(4).map((p) => ({ cx: p.x, cy: p.y })), kwc: 2.5 } }, layoutOptimalCount: 5 });
    ui.refreshHeatmap(); // ce que l'écran appelle après chaque re-rendu des panneaux (recalcDisplays)

    const attendu = ui.solarAccess()!;
    expect(attendu).not.toBeNull();
    expect(attendu.average).toBeLessThan(1);
    expect(bloc.textContent).not.toContain('non renseigné');
    expect(bloc.textContent).toContain(`${(attendu.average * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`);
    expect(ui.moduleShadeTooltip(0)).toContain('Accès solaire');
  });

  // ACAL1532 — l'écran Panneaux lit ces deux clés de `#rp9-solar-access` (jamais le texte) : le nom de l'obstacle (`data-ombre-de`)
  // et, SANS seuil réglé, la perte annuelle tirée de `shadeAnnualFactor` (`data-ombre-perte`) — aucun seuil inventé.
  function rouvert(seuil: number | null, avecBouton: boolean) {
    document.body.innerHTML = '<div id="parent"><div id="rp9-solar-access"></div></div>';
    const grand = { ...cheminee(0, 0.5), lengthM: 3, widthM: 3, heightM: 8 };
    const ctx = ctxPan(grand);
    const ui = createShadingUi(ctx, {
      map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {},
      ...(avecBouton ? { removePanels: () => 0 } : {}),
    });
    poserChoixOptimisation(seuil == null ? null : { seuilAccesSolaire: seuil });
    // Deux modules au sud de la cheminée (dégagés), trois juste au nord (dans son ombre) : une proposition de retrait existe.
    const poses = [...rangee(-3).slice(0, 2), ...rangee(1.5).slice(1, 4)];
    Object.assign(ctx, { layoutPlan: { grid: { panels: poses.map((p) => ({ cx: p.x, cy: p.y })), kwc: 2.5 } }, layoutOptimalCount: 5 });
    ui.recomputeShading();
    return { ctx, bloc: document.getElementById('rp9-solar-access')! };
  }

  it('ACAL1532 — seuil 95 % du dossier : la proposition de retrait et le nom « de la cheminée » sont publiés à l’ouverture', () => {
    try {
      const { bloc } = rouvert(0.95, true);
      expect(bloc.querySelector('#rp9-solar-access-apply')).not.toBeNull();
      expect(bloc.dataset.ombreDe).toBe('de la cheminée');
      expect(bloc.dataset.ombrePerte).toBeUndefined(); // un seuil est réglé : l'alerte parle de panneaux, pas de perte
    } finally { poserChoixOptimisation(null); }
  });

  it('ACAL1532 — sans seuil réglé : la perte annuelle publiée est celle de shadeAnnualFactor, arrondie, jamais un seuil', () => {
    try {
      const { ctx, bloc } = rouvert(null, true);
      expect(ctx.shadeAnnualFactor).toBeLessThan(1);
      expect(bloc.dataset.ombrePerte).toBe(String(Math.round((1 - ctx.shadeAnnualFactor) * 100)));
      expect(bloc.dataset.ombreDe).toBe('de la cheminée');
      expect(bloc.querySelector('#rp9-solar-access-apply')).toBeNull();
    } finally { poserChoixOptimisation(null); }
  });

  it('ACAL1532 (revue) — deux obstacles hauts dont une VMC qui n’ombre aucun module signalé : seule la cheminée est nommée', () => {
    try {
      document.body.innerHTML = '<div id="parent"><div id="rp9-solar-access"></div></div>';
      const grand = { ...cheminee(0, 0.5), lengthM: 3, widthM: 3, heightM: 8 };
      const vmc = { ...cheminee(-4.8, -3.4), id: 'vmc-1', type: 'ventilation', lengthM: 0.2, widthM: 0.2, heightM: 0.3 };
      const ctx = ctxPan(grand);
      ctx.obstacles.push(vmc);
      const ui = createShadingUi(ctx, {
        map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {},
        removePanels: () => 0,
      });
      poserChoixOptimisation({ seuilAccesSolaire: 0.95 });
      const poses = [...rangee(-3).slice(0, 2), ...rangee(1.5).slice(1, 4)];
      Object.assign(ctx, { layoutPlan: { grid: { panels: poses.map((p) => ({ cx: p.x, cy: p.y })), kwc: 2.5 } }, layoutOptimalCount: 5 });
      ui.recomputeShading();
      const bloc = document.getElementById('rp9-solar-access')!;
      expect(bloc.dataset.ombreDe).toBe('de la cheminée');
    } finally { poserChoixOptimisation(null); }
  });

  it('ACAL1532 — aucune obstruction : rien n’est publié', () => {
    document.body.innerHTML = '<div id="parent"><div id="rp9-solar-access"></div></div>';
    const ctx = ctxPan(cheminee(0, 0));
    ctx.obstacles.length = 0;
    const ui = createShadingUi(ctx, { map: new Proxy({}, { get: () => () => undefined }) as never, setStatus: () => {}, recalcDisplays: () => {}, applyHeatmap: () => {} });
    ui.refreshHeatmap();
    const bloc = document.getElementById('rp9-solar-access')!;
    expect(bloc.dataset.ombreDe).toBeUndefined();
    expect(bloc.dataset.ombrePerte).toBeUndefined();
  });
});
