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
  type PlanMoteurSurface,
} from './scene3d';
import { resnapEnMasse, resnapNaif } from './layoutEditor';

/** ~2 000 modules : 100 rangées × 10 tables, 2 modules par table. */
const RANGEES = 100;
const TABLES_PAR_RANGEE = 10;
const MODULES_PAR_TABLE = 2;
const LARGEUR_TABLE = 4.6;
const PROFONDEUR_TABLE = 2.3;
const PAS_RANGEE = 6;

function grandPlan(): PlanMoteurSurface {
  const tables = [];
  const rangees = [];
  for (let r = 0; r < RANGEES; r++) {
    const y0 = r * PAS_RANGEE;
    rangees.push({ y0, modules: TABLES_PAR_RANGEE * MODULES_PAR_TABLE });
    for (let c = 0; c < TABLES_PAR_RANGEE; c++) {
      const x0 = c * (LARGEUR_TABLE + 0.5);
      tables.push({ x0, x1: x0 + LARGEUR_TABLE, y0, y1: y0 + PROFONDEUR_TABLE, kit: 'terrain' });
    }
  }
  return {
    surface: 'GRAND-CHAMP',
    modules: RANGEES * TABLES_PAR_RANGEE * MODULES_PAR_TABLE,
    rangees,
    tables,
  };
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
