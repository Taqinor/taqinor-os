// ACAL257 — l'entrée MOTEUR applique les mêmes règles que le pavage de l'atelier : la forme
// RÉELLE de l'obstacle (`anneauObstacle`), son dégagement PROPRE (`degagementObstacle`), et
// l'allée du calepinage (sinon celle de la société). PURE : aucun DOM, aucune carte.
import { describe, expect, it } from 'vitest';
import { composerEntreeMoteur, type SceneMoteur } from './entreeMoteur';
import { anneauObstacle, type ObstacleEtendu } from './types';
import { uniformSetbacks } from '../../lib/roofPro2';
import { type LngLat } from '../../lib/roof';

const CARRE: LngLat[] = [[-7.6, 33.55], [-7.59987, 33.55], [-7.59987, 33.55011], [-7.6, 33.55011]];
const KIT = {
  code: 'ATELIER-720', libelle: 'Module', moduleLongM: 2.384, moduleCourtM: 1.303,
  puissanceModuleWc: 720, inclinaisonDeg: 13, orientation: 'PORTRAIT' as const, modulesParTable: 1,
};

function scene(obstacle: ObstacleEtendu, extra: Partial<SceneMoteur> = {}): SceneMoteur {
  return {
    repere: 'CAL-ESSAI',
    pans: [{ id: 'PAN-A', vertices: CARRE, obstacles: [obstacle], pitchDeg: 0, facingAzimuthDeg: 180 }],
    retraits: uniformSetbacks(),
    kit: KIT,
    ...extra,
  };
}

describe('ACAL257 — dégagement propre et forme réelle', () => {
  it('dégagement propre et forme réelle', () => {
    // Un obstacle ROND de 0,5 m de rayon portant son PROPRE dégagement (gabarit société 0,8).
    const rond = {
      id: 'obs-1', centerLng: -7.59993, centerLat: 33.55005, lengthM: 1, widthM: 1, type: 'cheminee',
      forme: 'cercle', rayonM: 0.5, degagementM: 0.8,
    } as unknown as ObstacleEtendu;
    const doc = composerEntreeMoteur(scene(rond))!;
    expect(doc.obstacles[0].degagement_m).toBe(0.8); // jamais le 0,3 du seul type
    // L'emprise est l'enveloppe du DISQUE réel, projeté dans le repère des rangées.
    const largeur = doc.obstacles[0].x1 - doc.obstacles[0].x0;
    expect(largeur).toBeGreaterThan(0.95);
    expect(largeur).toBeLessThanOrEqual(1.0 + 1e-6);
  });

  it('un obstacle en L : l’emprise vient du contour, jamais de la boîte lengthM × widthM', () => {
    const m = 1 / 111320;
    const cos = Math.cos((33.55 * Math.PI) / 180);
    const p = (x: number, y: number): LngLat => [-7.59995 + (x * m) / cos, 33.55003 + y * m];
    const contour = [p(0, 0), p(4, 0), p(4, 2), p(2, 2), p(2, 4), p(0, 4)];
    const enL = {
      id: 'obs-2', centerLng: -7.59995, centerLat: 33.55003, lengthM: 0.5, widthM: 0.5,
      forme: 'polygone', contour,
    } as unknown as ObstacleEtendu;
    const doc = composerEntreeMoteur(scene(enL))!;
    const o = doc.obstacles[0];
    // Boîte du contour : ~4 m × 4 m (la boîte « lengthM × widthM » aurait fait 0,5 m).
    expect(o.x1 - o.x0).toBeGreaterThan(3.9);
    expect(o.y1 - o.y0).toBeGreaterThan(3.9);
    // Et c'est bien l'anneau RÉEL du pavage (le même que l'atelier évite).
    expect(anneauObstacle(enL)).toEqual(contour);
  });
});

describe('ACAL257 — réglages société transmis au moteur', () => {
  const simple = { id: 'obs-1', centerLng: -7.59993, centerLat: 33.55005, lengthM: 1, widthM: 1 } as ObstacleEtendu;

  it('réglages société transmis au moteur', () => {
    const societe = { retrait_rive_m: 1.2, allee_technique_m: 1.0 };
    // L'allée du CALEPINAGE prime, puis celle de la société ; aucune ⇒ clé absente.
    expect(composerEntreeMoteur(scene(simple, { alleeTechniqueM: 0.8, degagementsSociete: societe }))!.parametres.allee_m).toBe(0.8);
    expect(composerEntreeMoteur(scene(simple, { degagementsSociete: societe }))!.parametres.allee_m).toBe(1.0);
    expect('allee_m' in composerEntreeMoteur(scene(simple))!.parametres).toBe(false);
    // Les rives sont celles que le pavage de l'atelier applique (retraits de la scène).
    expect(composerEntreeMoteur(scene(simple))!.parametres.rives.laterale_m).toBeCloseTo(uniformSetbacks().lateralM, 9);
  });
});

// ACAL1504 — le pavage d'un pan plat (solveur vivant ET balayage « Comparer les poses ») lit le retrait de CHAQUE
// arête posé par la table de la société (`retraitM`, `retraitOrigine: 'societe'`), pas seulement les retraits uniformes.
describe('ACAL1504 — retrait par arête dans le pavage plat', () => {
  async function poser(widthM: number, depthM: number, retraitM: number | null) {
    const { JSDOM } = await import('jsdom');
    const { createOptimizer } = await import('./optimizer');
    const { createMatrix } = await import('./matrix');
    const { rectRing } = await import('./harnaisAtelier');
    const g = globalThis as unknown as { document?: Document };
    const avant = g.document;
    g.document = new JSDOM('<!doctype html><body></body>').window.document;
    try {
      const vertices = rectRing(widthM, depthM);
      const edges = retraitM == null ? undefined : [0, 1, 2, 3].map((index) => ({ index, type: 'rive', retraitM, retraitOrigine: 'societe' }));
      const pan = { id: 'z1', label: 'Pan A', vertices, obstacles: [], roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, neededPanels: 0, neededAuto: true, edges };
      const ctx = {
        closed: true, vertices, roofType: 'flat', areas: [pan], activeAreaId: 'z1', activeArea: () => pan, opts: {}, dom: {},
        centroid: vertices[0], centroidLat: 33.5, pinned: new Set(), sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
        v4YieldCache: new Map(), overhangM: 0, documentRelu: null, batiments: [], environment: [], shadeObstructions: [], obstacles: [],
        neededAuto: true, neededPanels: 0, layoutPlan: null, matrixSort: { key: 'annualKwh', dir: 'desc' },
      } as unknown as Ctx;
      let pose = -1;
      const deps = {
        renderScene: (_p: unknown, _g: unknown, _t: unknown, _f: unknown, placed: number) => { pose = placed; },
        paintComparison: () => {}, highlightRow: () => {}, syncProductionWindow: () => {}, prefillLead: () => {}, syncChips: () => {},
        renderMatrixOptimumCard: () => {}, monthlyBill: () => 0, obstructionRings: () => [], setStatus: () => {},
      };
      const opt = createOptimizer(ctx, deps as unknown as Parameters<typeof createOptimizer>[1]);
      opt.liveResolveFlat();
      const maxDe = () => Math.max(0, ...((ctx as unknown as { matrixResult: { rows: { placedCount: number }[] } }).matrixResult.rows.map((r) => r.placedCount)));
      opt.buildMatrix([...vertices], 0);
      const balayage = maxDe();
      const matrice = createMatrix(ctx, { renderConfig: () => {}, monthlyBill: () => 0, obstructionRings: () => [] } as unknown as Parameters<typeof createMatrix>[1]);
      matrice.recomputeMatrix();
      return { pose, balayage, recompute: maxDe() };
    } finally {
      g.document = avant;
    }
  }

  it('4 rives à 0,80 m sur 3 × 1,5 m ⇒ 0 module (vivant, balayage, recalcul de la matrice)', async () => {
    const r = await poser(3, 1.5, 0.8);
    expect(r).toEqual({ pose: 0, balayage: 0, recompute: 0 });
  });

  it('un plat 10 × 7 garde des panneaux, moins qu’au seul retrait uniforme', async () => {
    const sans = await poser(10, 7, null);
    const avec = await poser(10, 7, 0.8);
    expect(avec.balayage).toBeGreaterThan(0);
    expect(avec.balayage).toBeLessThan(sans.balayage);
    expect(avec.recompute).toBeLessThan(sans.recompute);
  });
});
