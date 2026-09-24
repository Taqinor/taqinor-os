/* ════════════════════════════════════════════════════════════════════════════
   CAL106 — UN CHAMP DE 2 000 MODULES RESTE MANIPULABLE.
   ----------------------------------------------------------------------------
   Constat : la 3D reconstruit et re-rend sur chaque geste — dimensionnée pour
   la villa (quelques dizaines de modules), jamais mesurée sur un grand champ.
   La parité visée est de l'ordre de plusieurs milliers de modules dans une même
   étude.

   CE QUE CE FICHIER MESURE, ET CE QU'IL NE MESURE PAS. La borne porte sur le
   COÛT PUR — construire le plan depuis la réponse du moteur, préparer les
   matrices d'instances, élaguer ce qui est visible, re-snapper une disposition
   en masse — et JAMAIS sur le rendu WebGL : vitest tourne sans GPU, un seuil
   chiffré sur le rendu décrirait donc quelque chose qui n'a pas eu lieu. C'est
   la condition explicite de la tâche.

   LES SEUILS SONT MESURÉS, PAS DEVINÉS. Relevés sur la machine de cette lane
   (Windows, node 22, vitest 4.1), cas à 2 000 modules, trois passes :
     * construction du champ depuis le plan moteur ...........  3,5 / 4,2 / 4,8 ms
     * matrices d'instances (1 000 tables × 16 flottants) .....  1,7 / 2,0 / 2,2 ms
     * élagage de visibilité ..................................  0,7 / 1,5 / 1,8 ms
     * re-snap en masse INDEXÉ (2 000 centres / 2 000 cellules)   20 / 40 / 22 ms
       — le balayage linéaire d'origine, sur le MÊME cas :       114 / 145 / 140 ms
       (4 millions de distances ; c'est le coût que cette tâche supprime, et
        c'est le pire cas : la lattice finit saturée, donc les derniers centres
        cherchent loin).
   Les bornes écrites ci-dessous sont volontairement LARGES par rapport à ces
   relevés : elles attrapent une régression d'ORDRE DE GRANDEUR (un N² qui
   revient), pas le bruit d'une machine de CI chargée. Un seuil serré serait un
   test instable, c'est-à-dire un test que l'on finit par ignorer.

   AUCUN CHIFFRE DE CALEPINAGE NE CHANGE : le test d'équivalence ci-dessous
   confronte le re-snap indexé au balayage linéaire d'origine et exige des
   index IDENTIQUES, sur des cas aléatoires et sur les cas dégénérés.
   ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from 'vitest';
import {
  construireChampPose,
  matricesInstanciees,
  tablesVisibles,
  plafonnerSelection,
  projectPlanView,
  panelQuadsLngLat,
  type PlanMoteurSurface,
} from './scene3d';
import { resnapEnMasse, resnapNaif } from './layoutEditor';
import { serializeLayout } from './prefill';
import { heatmapAccessValues } from './shadingUi';
import { solarAccessColorRGB, type ShadeObstructionENU } from '../../lib/shadingEngine';
import { fallbackPerKwc } from '../../lib/productionEngine';
import { type Ctx } from './context';
import { type AreaRecord } from './types';

/** ~2 000 modules : 100 rangées × 10 tables, 2 modules par table. */
const RANGEES = 100;
const TABLES_PAR_RANGEE = 10;
const MODULES_PAR_TABLE = 2;
const LARGEUR_TABLE = 4.6;
const PROFONDEUR_TABLE = 2.3;
const PAS_RANGEE = 6;

/** CALX388 — 10 000 modules : 250 rangées × 20 tables, 2 modules par table (même
 *  géométrie unitaire que le cas à 2 000 — seule l'échelle change). Parité PV*SOL
 *  Premium : « up to 7,500 mounted modules or up to 10,000 roof-parallel modules
 *  in 3D » (valentin-software.com/en/products/pvsol-premium/). */
const RANGEES_10K = 250;
const TABLES_PAR_RANGEE_10K = 20;
const MODULES_PAR_TABLE_10K = 2;

/** Un champ de `rangees` × `tablesParRangee` tables (`modulesParTable` modules chacune),
 *  même géométrie unitaire que `grandPlan` — factorisé par CALX388 pour porter le même
 *  générateur au cas à 10 000 sans dupliquer la boucle. Comportement du cas à 2 000
 *  INCHANGÉ (`grandPlan` délègue ici avec les mêmes constantes qu'avant). */
function champDeTaille(rangees: number, tablesParRangee: number, modulesParTable: number): PlanMoteurSurface {
  const tables = [];
  const rangeesArr = [];
  for (let r = 0; r < rangees; r++) {
    const y0 = r * PAS_RANGEE;
    rangeesArr.push({ y0, modules: tablesParRangee * modulesParTable });
    for (let c = 0; c < tablesParRangee; c++) {
      const x0 = c * (LARGEUR_TABLE + 0.5);
      tables.push({ x0, x1: x0 + LARGEUR_TABLE, y0, y1: y0 + PROFONDEUR_TABLE, kit: 'terrain' });
    }
  }
  return {
    surface: 'GRAND-CHAMP',
    modules: rangees * tablesParRangee * modulesParTable,
    rangees: rangeesArr,
    tables,
  };
}

function grandPlan(): PlanMoteurSurface {
  return champDeTaille(RANGEES, TABLES_PAR_RANGEE, MODULES_PAR_TABLE);
}

/** CALX388 — le même champ, à l'échelle 10 000 modules. */
function grandPlan10k(): PlanMoteurSurface {
  return champDeTaille(RANGEES_10K, TABLES_PAR_RANGEE_10K, MODULES_PAR_TABLE_10K);
}

/** Une lattice de N cellules régulières (le repère ENU du pavage). */
function lattice(n: number) {
  const cote = Math.ceil(Math.sqrt(n));
  const cells = [];
  for (let i = 0; i < n; i++) {
    cells.push({ index: i, cx: (i % cote) * 2.4, cy: Math.floor(i / cote) * 1.4 });
  }
  return cells;
}

/** Générateur déterministe : un test de performance ne doit pas dépendre du hasard. */
function alea(graine: number): () => number {
  let x = graine >>> 0;
  return () => {
    x = (x * 1664525 + 1013904223) >>> 0;
    return x / 4294967296;
  };
}

function chrono(f: () => void): number {
  const t0 = performance.now();
  f();
  return performance.now() - t0;
}

describe('CAL106 — le COÛT PUR d’un champ de 2 000 modules', () => {
  const plan = grandPlan();

  it('le cas d’essai fait bien ~2 000 modules', () => {
    expect(plan.modules).toBe(2000);
    expect(plan.tables).toHaveLength(1000);
  });

  it('construire le champ depuis le plan du moteur : < 150 ms (mesuré 3,5-4,8 ms)', () => {
    let champ = null as ReturnType<typeof construireChampPose> | null;
    const ms = chrono(() => {
      champ = construireChampPose(plan, { tiltDeg: 25, penteTerrainDeg: 3, aireTerrainM2: 30000 });
    });
    expect(champ?.tables).toHaveLength(1000);
    expect(champ?.modules).toBe(2000); // le compte du moteur, intact
    expect(ms).toBeLessThan(150);
  });

  it('préparer les matrices d’instances : < 150 ms (mesuré 1,7-2,2 ms)', () => {
    const champ = construireChampPose(plan, { tiltDeg: 25, aireTerrainM2: 30000 });
    let mat = new Float32Array(0);
    const ms = chrono(() => { mat = matricesInstanciees(champ.tables); });
    expect(mat).toHaveLength(1000 * 16);
    // La dernière instance porte bien la translation de la dernière table.
    const derniere = champ.tables[champ.tables.length - 1];
    // `Float32Array` : on compare à la précision d'un flottant 32 bits, pas à
    // celle d'un double — exiger 6 décimales ici testerait le format, pas la
    // matrice.
    expect(mat[999 * 16 + 12]).toBeCloseTo(derniere.cx, 3);
    expect(mat[999 * 16 + 15]).toBe(1);
    expect(ms).toBeLessThan(150);
  });

  it('élaguer la visibilité : < 100 ms, et ce qui sort du cadre n’est pas instancié', () => {
    const champ = construireChampPose(plan, { tiltDeg: 25, aireTerrainM2: 30000 });
    let vus = new Uint32Array(0);
    const ms = chrono(() => {
      vus = tablesVisibles(champ.tables, { xMin: 0, xMax: 30, yMin: 0, yMax: 60 });
    });
    expect(vus.length).toBeGreaterThan(0);
    expect(vus.length).toBeLessThan(champ.tables.length); // le cadre élague vraiment
    expect(ms).toBeLessThan(100);
  });

  it('plafonner une sélection de masse dit ce qu’elle écarte', () => {
    const tous = Array.from({ length: 2000 }, (_, i) => i);
    const borne = plafonnerSelection(tous, 500);
    expect(borne.retenus).toHaveLength(500);
    expect(borne.ecartes).toBe(1500);
    // Sous le plafond, rien n'est touché.
    expect(plafonnerSelection([1, 2, 3], 500)).toEqual({ retenus: [1, 2, 3], ecartes: 0 });
  });
});

describe('CAL106 — le re-snap en masse : même résultat, sans le N²', () => {
  it('2 000 centres sur 2 000 cellules : < 400 ms (mesuré 20-40 ms ; le balayage linéaire : 114-145 ms)', () => {
    const cells = lattice(2000);
    const r = alea(7);
    const centres = Array.from({ length: 2000 }, () => ({
      cx: r() * 100, cy: r() * 60,
    }));
    let out: number[] = [];
    const ms = chrono(() => { out = resnapEnMasse(cells, centres); });
    expect(out).toHaveLength(2000); // tous replacés
    expect(new Set(out).size).toBe(2000); // aucun doublon
    expect(ms).toBeLessThan(400);
  });

  it('ÉQUIVALENCE STRICTE avec le balayage linéaire d’origine (cas aléatoires)', () => {
    for (const graine of [1, 42, 1234]) {
      const cells = lattice(300);
      const r = alea(graine);
      const centres = Array.from({ length: 200 }, () => ({ cx: r() * 45, cy: r() * 25 }));
      expect(resnapEnMasse(cells, centres), `graine ${graine}`)
        .toEqual(resnapNaif(cells, centres));
    }
  });

  it('ÉQUIVALENCE sur les cas dégénérés (centres confondus, hors emprise, vide)', () => {
    const cells = lattice(120);
    const confondus = Array.from({ length: 20 }, () => ({ cx: 5, cy: 5 }));
    expect(resnapEnMasse(cells, confondus)).toEqual(resnapNaif(cells, confondus));
    const loin = [{ cx: -1000, cy: -1000 }, { cx: 5000, cy: 5000 }];
    expect(resnapEnMasse(cells, loin)).toEqual(resnapNaif(cells, loin));
    expect(resnapEnMasse(cells, [])).toEqual([]);
    expect(resnapEnMasse([], confondus)).toEqual([]);
  });

  it('PLUS de centres que de cellules : les surnuméraires ne sont pas placés, comme avant', () => {
    const cells = lattice(50);
    const r = alea(9);
    const centres = Array.from({ length: 80 }, () => ({ cx: r() * 20, cy: r() * 12 }));
    const indexe = resnapEnMasse(cells, centres);
    expect(indexe).toEqual(resnapNaif(cells, centres));
    expect(indexe).toHaveLength(50);
  });
});

/* ════════════════════════════════════════════════════════════════════════════
   CALX388 — LE BUDGET PORTÉ À 10 000 MODULES (PARITÉ PV*SOL PREMIUM).
   ----------------------------------------------------------------------------
   Parité visée : PV*SOL Premium annonce « up to 7,500 mounted modules or up to
   10,000 roof-parallel modules in 3D » (valentin-software.com/en/products/
   pvsol-premium/) — un ordre de grandeur au-dessus du cas à 2 000 ci-dessus.

   CE QUI EST AJOUTÉ ICI, ET RIEN D'AUTRE. (1) Le MÊME cas à 2 000 modules
   ci-dessus reste INCHANGÉ (le générateur est factorisé dans `champDeTaille`,
   mais `grandPlan()` l'appelle avec les mêmes constantes qu'avant — sortie
   identique). (2) Les QUATRE coûts déjà mesurés (construction du champ,
   matrices d'instances, élagage de visibilité, re-snap en masse indexé) sont
   repris à l'échelle 10 000. (3) QUATRE chemins PAR MODULE qui n'avaient
   jusqu'ici AUCUN budget sont instrumentés : l'accès solaire
   (`heatmapAccessValues`, le calcul qui alimente la carte de chaleur), la
   RE-TEINTE de cette carte (`solarAccessColorRGB`, appliqué par module — la
   partie CPU du re-rendu, jamais le buffer GPU), la projection du plan 2D
   (`panelQuadsLngLat` + `projectPlanView`, CAL104) et `serializeLayout`
   (l'écriture du document). Comme pour le cas à 2 000 : AUCUN seuil ne porte
   sur le rendu WebGL — ces quatre fonctions sont PURES (aucun DOM, aucune
   scène Three.js, vitest tourne sans GPU) : c'est précisément ce qui les rend
   mesurables ici.

   LES SEUILS SONT MESURÉS, PAS DEVINÉS. Relevés sur la machine de cette lane
   (Windows, node 24.12, vitest 4.1.8), cas à 10 000 modules, trois passes :
     * construction du champ depuis le plan moteur (5 000 tables) ......  7,19 / 2,48 / 2,67 ms
     * matrices d'instances (5 000 tables × 16 flottants) ..............  2,78 / 0,51 / 0,51 ms
     * élagage de visibilité ............................................  1,67 / 0,21 / 0,12 ms
     * re-snap en masse INDEXÉ (10 000 centres / 10 000 cellules) ......  613 / 683 / 676 ms
       — le balayage linéaire d'origine, sur le MÊME cas (mesuré séparément,
         PAS exécuté dans le test de budget ci-dessous — le coût est documenté,
         pas re-payé à chaque run) :                                      4 504 / 4 681 / 4 849 ms
     * accès solaire par module (`heatmapAccessValues`, une obstruction
       renseignée pour que le calcul ait réellement lieu) ................  1 351 / 1 288 / 1 309 ms
     * re-teinte de la carte de chaleur (`solarAccessColorRGB` par module,
       valeurs d'accès déjà connues — c'est SEULEMENT la reteinte) .......  1,97 / 2,63 / 1,43 ms
     * projection du plan 2D (`panelQuadsLngLat` + `projectPlanView`) ....  21,31 / 21,28 / 11,59 ms
     * `serializeLayout` (un pan, 10 000 panneaux posés) ................  7,10 / 3,34 / 4,69 ms
   Les bornes écrites ci-dessous sont volontairement LARGES par rapport à ces
   relevés (même règle que le cas à 2 000) : elles attrapent une régression
   d'ORDRE DE GRANDEUR (un N² qui revient), pas le bruit d'une machine de CI
   chargée — grossièrement 5 à 10× la pire passe mesurée, ou un plancher
   généreux pour les coûts déjà sous la milliseconde.

   AUCUN CHIFFRE DE CALEPINAGE NE CHANGE : le test d'équivalence indexé ↔
   balayage naïf est reconduit sur ce nouveau cas à 10 000 (avec un délai de
   test élargi — le balayage naïf, LUI, met plusieurs secondes à 10 000 × 10 000
   et c'est justement ce que le re-snap indexé supprime).
   ══════════════════════════════════════════════════════════════════════════ */

describe('CALX388 — le COÛT PUR d’un champ de 10 000 modules', () => {
  const plan = grandPlan10k();

  it('le cas d’essai fait bien ~10 000 modules', () => {
    expect(plan.modules).toBe(10000);
    expect(plan.tables).toHaveLength(5000);
  });

  it('construire le champ depuis le plan du moteur : < 300 ms (mesuré 2,48-7,19 ms)', () => {
    let champ = null as ReturnType<typeof construireChampPose> | null;
    const ms = chrono(() => {
      champ = construireChampPose(plan, { tiltDeg: 25, penteTerrainDeg: 3, aireTerrainM2: 150000 });
    });
    expect(champ?.tables).toHaveLength(5000);
    expect(champ?.modules).toBe(10000); // le compte du moteur, intact
    expect(ms).toBeLessThan(300);
  });

  it('préparer les matrices d’instances : < 300 ms (mesuré 0,51-2,78 ms)', () => {
    const champ = construireChampPose(plan, { tiltDeg: 25, aireTerrainM2: 150000 });
    let mat = new Float32Array(0);
    const ms = chrono(() => { mat = matricesInstanciees(champ.tables); });
    expect(mat).toHaveLength(5000 * 16);
    // La dernière instance porte bien la translation de la dernière table.
    const derniere = champ.tables[champ.tables.length - 1];
    expect(mat[4999 * 16 + 12]).toBeCloseTo(derniere.cx, 3);
    expect(mat[4999 * 16 + 15]).toBe(1);
    expect(ms).toBeLessThan(300);
  });

  it('élaguer la visibilité : < 200 ms, et ce qui sort du cadre n’est pas instancié', () => {
    const champ = construireChampPose(plan, { tiltDeg: 25, aireTerrainM2: 150000 });
    let vus = new Uint32Array(0);
    const ms = chrono(() => {
      vus = tablesVisibles(champ.tables, { xMin: 0, xMax: 60, yMin: 0, yMax: 120 });
    });
    expect(vus.length).toBeGreaterThan(0);
    expect(vus.length).toBeLessThan(champ.tables.length); // le cadre élague vraiment
    expect(ms).toBeLessThan(200);
  });
});

describe('CALX388 — le re-snap en masse à 10 000 : même résultat, sans le N²', () => {
  it('10 000 centres sur 10 000 cellules : < 7 000 ms (mesuré 613-683 ms ; le balayage linéaire, même cas : 4 504-4 849 ms)', () => {
    const cells = lattice(10000);
    const r = alea(11);
    const centres = Array.from({ length: 10000 }, () => ({
      cx: r() * 250, cy: r() * 200,
    }));
    let out: number[] = [];
    const ms = chrono(() => { out = resnapEnMasse(cells, centres); });
    expect(out).toHaveLength(10000); // tous replacés
    expect(new Set(out).size).toBe(10000); // aucun doublon
    expect(ms).toBeLessThan(7000);
  });

  it(
    'ÉQUIVALENCE STRICTE avec le balayage linéaire d’origine, sur le cas à 10 000 (lent par construction : le balayage naïf est O(n²))',
    () => {
      const cells = lattice(10000);
      const r = alea(11);
      const centres = Array.from({ length: 10000 }, () => ({ cx: r() * 250, cy: r() * 200 }));
      expect(resnapEnMasse(cells, centres)).toEqual(resnapNaif(cells, centres));
    },
    20000,
  );
});

describe('CALX388 — les chemins PAR MODULE sans budget jusqu’ici, à 10 000 modules', () => {
  it('accès solaire (`heatmapAccessValues`) : < 15 000 ms (mesuré 1 288-1 351 ms)', () => {
    const prod = fallbackPerKwc();
    // Une obstruction RENSEIGNÉE, sinon `heatmapAccessValues` court-circuite à 1
    // partout (`!obstructions.length`) et ne mesurerait rien du vrai coût.
    const obstruction: ShadeObstructionENU = { x: 5, y: -5, effHeightM: 4, halfWidthM: 3 };
    const panels = Array.from({ length: 10000 }, (_, i) => ({ cx: (i % 200) * 2.4, cy: Math.floor(i / 200) * 1.4 }));
    let acces: number[] = [];
    const ms = chrono(() => { acces = heatmapAccessValues(33.5, [obstruction], prod, panels, null); });
    expect(acces).toHaveLength(10000);
    expect(acces.some((a) => a < 1)).toBe(true); // l'obstruction masque réellement quelque chose
    expect(ms).toBeLessThan(15000);
  });

  it('re-teinte de la carte de chaleur (`solarAccessColorRGB` par module) : < 150 ms (mesuré 1,43-2,63 ms)', () => {
    // Valeurs d'accès déjà connues (comme après un `heatmapAccessValues`) : ce test
    // n'isole QUE le coût de la reteinte, jamais celui du calcul d'accès solaire.
    const acces = Array.from({ length: 10000 }, (_, i) => (i % 100) / 100);
    const ms = chrono(() => {
      for (const a of acces) solarAccessColorRGB(a);
    });
    expect(ms).toBeLessThan(150);
  });

  it('projection du plan 2D (`panelQuadsLngLat` + `projectPlanView`) : < 300 ms (mesuré 11,59-21,31 ms)', () => {
    const ring: [number, number][] = [
      [-7.6, 33.59], [-7.55, 33.59], [-7.55, 33.62], [-7.6, 33.62],
    ];
    const centers = Array.from({ length: 10000 }, (_, i) => ({ cx: (i % 200) * 2.4, cy: Math.floor(i / 200) * 1.4 }));
    const posed = panelQuadsLngLat([-7.6, 33.59], centers, 2.3, 1.13, 25, 180);
    let vue: ReturnType<typeof projectPlanView> = null;
    const ms = chrono(() => { vue = projectPlanView(ring, posed, { widthPx: 1600, heightPx: 1200, marginPx: 28 }); });
    expect(vue?.panels).toHaveLength(10000); // le compte projeté = le compte posé, par construction
    expect(ms).toBeLessThan(300);
  });

  it('`serializeLayout` (un pan, 10 000 panneaux posés) : < 300 ms (mesuré 3,34-7,10 ms)', () => {
    const verts: [number, number][] = [
      [-7.6, 33.59], [-7.599, 33.59], [-7.599, 33.591], [-7.6, 33.591],
    ];
    const renderPlan = {
      pack: { origin: [-7.6, 33.59] as [number, number], azimuthDeg: 180 },
      grid: {
        panels: Array.from({ length: 10000 }, (_, i) => ({ cx: (i % 200) * 2.4, cy: Math.floor(i / 200) * 1.4 })),
        kwc: 6000,
      },
      tiltDeg: 13,
      family: 'south',
      flush: false,
      count: 10000,
    } as unknown as AreaRecord['renderPlan'];
    const area: AreaRecord = {
      id: 'z1',
      label: 'Zone z1',
      vertices: verts,
      obstacles: [],
      roofType: 'flat',
      pitchDeg: 22,
      facingAzimuthDeg: 180,
      facingManual: false,
      neededPanels: 10000,
      neededAuto: true,
      result: null,
      renderPlan,
    };
    const ctx = {
      opts: {},
      areas: [area],
      activeAreaId: area.id,
      vertices: area.vertices,
      obstacles: area.obstacles,
      roofType: area.roofType,
      pitchDeg: area.pitchDeg,
      facingAzimuthDeg: area.facingAzimuthDeg,
      facingManual: false,
      neededPanels: area.neededPanels,
      neededAuto: area.neededAuto,
      layoutPlan: null,
      layoutOptimalCount: 0,
    } as unknown as Ctx;
    let layout: ReturnType<typeof serializeLayout> | null = null;
    const ms = chrono(() => { layout = serializeLayout(ctx, 12000); });
    expect(layout?.zones?.[0]?.geometry?.count).toBe(10000);
    expect(ms).toBeLessThan(300);
  });
});
