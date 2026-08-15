// VISIONNEUSE PLEINE (page publique /proposition) — la moitié TESTABLE.
//
// Le client doit voir le VRAI rendu du builder (scene3d.ts : verre, cadres,
// rails, châssis, ombres), figé, avec la carte complète. Le rendu WebGL lui-même
// n'est pas testable en CI ; TOUT ce qui peut donner un autre toit que celui
// vendu l'est, et c'est ce que ce fichier verrouille :
//   1. la traduction roof_layout → plans de rendu du builder (positions VERBATIM,
//      repère ENU, pose du module, pan actif) ;
//   2. le refus PROPRE d'un layout sans calepinage réel (anciens liens) ;
//   3. le cadrage caméra (centre + zoom) ;
//   4. le CONTRAT lecture seule du boot (aucun écouteur de geste d'édition,
//      aucun module d'édition importé) — garde de source, même convention que
//      mobilePerfWJ18.test.ts.
// Aucun DOM, aucun Three.js, aucun MapLibre : modules purs seulement.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseRoofLayout, type RoofLayout } from '../src/lib/proposition';
import { PANEL2_LONG_M, PANEL2_SHORT_M } from '../src/lib/roofPro2';
import { DEG2M } from '../src/scripts/roofPro11/constants';
import {
  buildViewerFullPlan,
  gridFromGeometry,
  ringENUFromVertices,
  viewerAreaRecords,
  zoomForSpanM,
  VIEWER_FULL_MAX_ZOOM,
  VIEWER_FULL_MIN_ZOOM,
} from '../src/scripts/roofPro11/viewerFullModel';

// ── Un toit carré réaliste au Maroc (Casablanca), convention x=Est / y=Nord ──
const LAT0 = 33.5;
const LNG0 = -7.6;
const COS = Math.cos((LAT0 * Math.PI) / 180);
function at(x: number, y: number): [number, number] {
  return [LNG0 + x / (DEG2M * COS), LAT0 + y / DEG2M];
}
function squareLngLat(half: number): Array<[number, number]> {
  return [at(-half, -half), at(half, -half), at(half, half), at(-half, half)];
}

/** Colonnes de panneaux au pas `pitch` le long de l'axe de rangée (az 180° → +x). */
function columns(pitch: number, n: number, y = 0): Array<Record<string, unknown>> {
  return Array.from({ length: n }, (_, i) => ({ cx: (i - (n - 1) / 2) * pitch, cy: y }));
}

const PORTRAIT_PITCH = PANEL2_SHORT_M + 0.02; // 1,323 m — pas de colonne portrait
const LANDSCAPE_PITCH = PANEL2_LONG_M + 0.02; // 2,404 m — pas de colonne paysage

function rawZone(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'zone-1',
    label: 'Pan principal',
    vertices: squareLngLat(12),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 0,
    facingAzimuthDeg: 180,
    neededPanels: 0,
    geometry: {
      azimuthDeg: 180,
      tiltDeg: 13,
      family: 'south',
      flush: false,
      count: 4,
      origin: [LNG0, LAT0],
      panels: columns(PORTRAIT_PITCH, 4),
    },
    ...over,
  };
}

function layoutOf(...zones: Array<Record<string, unknown>>): RoofLayout {
  const parsed = parseRoofLayout({ version: 2, zones });
  if (!parsed) throw new Error('fixture invalide');
  return parsed;
}

// ── 1. Refus PROPRE (l'appelant garde viewerOnly) ────────────────────────────

describe('visionneuse pleine — refus propre, jamais un throw', () => {
  it('layout absent / vide → null', () => {
    expect(buildViewerFullPlan(null)).toBeNull();
    expect(buildViewerFullPlan(undefined)).toBeNull();
    expect(buildViewerFullPlan({ version: 1, zones: [] })).toBeNull();
  });

  it('ancien lien (aucune zone ne porte de calepinage réel) → null', () => {
    const layout = layoutOf(rawZone({ geometry: undefined }));
    expect(layout.zones[0].geometry).toBeUndefined();
    expect(buildViewerFullPlan(layout)).toBeNull();
  });

  it('geometry présente mais sans panneau exploitable → null (parse la rejette déjà)', () => {
    const layout = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), panels: [] } }));
    expect(buildViewerFullPlan(layout)).toBeNull();
  });
});

// ── 2. Le calepinage RÉEL, recopié tel quel ──────────────────────────────────

describe('visionneuse pleine — les panneaux sont ceux de l’ERP, jamais un re-pavage', () => {
  it('chaque centre posé est repris VERBATIM (mêmes cx/cy, même face)', () => {
    const layout = layoutOf(
      rawZone({
        geometry: {
          azimuthDeg: 180,
          tiltDeg: 13,
          family: 'eastwest',
          flush: false,
          count: 3,
          origin: [LNG0, LAT0],
          panels: [
            { cx: -1.323, cy: 0, face: 'E' },
            { cx: 0, cy: 0, face: 'W' },
            { cx: 1.323, cy: 4.2 },
          ],
        },
      }),
    );
    const plan = buildViewerFullPlan(layout)!;
    const panels = plan.zones[0].plan!.grid.panels;
    expect(panels).toEqual([
      { cx: -1.323, cy: 0, face: 'E' },
      { cx: 0, cy: 0, face: 'W' },
      { cx: 1.323, cy: 4.2 },
    ]);
    expect(plan.totalPanels).toBe(3);
    // Le pack porte l'azimut/l'inclinaison/la famille RÉELS du pan vendu.
    expect(plan.zones[0].plan!.pack.azimuthDeg).toBe(180);
    expect(plan.zones[0].plan!.tiltDeg).toBe(13);
    expect(plan.zones[0].plan!.family).toBe('eastwest');
    expect(plan.zones[0].plan!.flush).toBe(false);
  });

  it('tous les panneaux posés sont dessinés (count = panels.length, jamais la cible)', () => {
    // `count` déclaré incohérent (2) alors que 4 cellules sont posées : on dessine
    // les 4 — le client doit voir ce qui est posé, pas un chiffre déclaré.
    const geo = { ...(rawZone().geometry as Record<string, unknown>), count: 2 };
    const plan = buildViewerFullPlan(layoutOf(rawZone({ geometry: geo })))!;
    expect(plan.zones[0].plan!.count).toBe(4);
    expect(plan.zones[0].plan!.grid.panels).toHaveLength(4);
  });

  it('le contour du pan passe dans le repère ENU des panneaux (origine geometry.origin)', () => {
    const layout = layoutOf(rawZone({ vertices: [at(-12, -12), at(12, -12), at(12, 12), at(-12, 12)] }));
    const ring = buildViewerFullPlan(layout)!.zones[0].plan!.pack.ringENU;
    expect(ring[0][0]).toBeCloseTo(-12, 6);
    expect(ring[0][1]).toBeCloseTo(-12, 6);
    expect(ring[2][0]).toBeCloseTo(12, 6);
    expect(ring[2][1]).toBeCloseTo(12, 6);
  });

  it('ringENUFromVertices : conversion identique à celle du builder (DEG2M/cos lat)', () => {
    const ring = ringENUFromVertices([at(7, -3)], [LNG0, LAT0]);
    expect(ring[0][0]).toBeCloseTo(7, 9);
    expect(ring[0][1]).toBeCloseTo(-3, 9);
  });

  it('les obstacles du pan suivent (boîtes 3D), avec un identifiant stable', () => {
    const layout = layoutOf(
      rawZone({ obstacles: [{ centerLng: LNG0, centerLat: LAT0, lengthM: 1.2, widthM: 0.8 }] }),
    );
    const obs = buildViewerFullPlan(layout)!.zones[0].plan!.obstacles;
    expect(obs).toHaveLength(1);
    expect(obs[0]).toMatchObject({ id: 'zone-1-obs-0', lengthM: 1.2, widthM: 0.8 });
  });
});

// ── 3. La POSE du module (le bug WJ130 : des rectangles tournés de 90°) ──────

describe('visionneuse pleine — pose du module déduite du pas RÉEL', () => {
  it('pas de colonne portrait → grand côté dans la pente', () => {
    const g = { ...(rawZone().geometry as Record<string, unknown>), panels: columns(PORTRAIT_PITCH, 3) };
    const grid = gridFromGeometry(g as never);
    expect(grid.panelOrientation).toBe('portrait');
    expect(grid.slopeLenM).toBeCloseTo(PANEL2_LONG_M, 6);
    expect(grid.rowWidthM).toBeCloseTo(PANEL2_SHORT_M, 6);
  });

  it('pas de colonne paysage → grand côté le long de la rangée', () => {
    const g = { ...(rawZone().geometry as Record<string, unknown>), panels: columns(LANDSCAPE_PITCH, 3) };
    const grid = gridFromGeometry(g as never);
    expect(grid.panelOrientation).toBe('landscape');
    expect(grid.slopeLenM).toBeCloseTo(PANEL2_SHORT_M, 6);
    expect(grid.rowWidthM).toBeCloseTo(PANEL2_LONG_M, 6);
  });

  it('mesure non concluante (un seul panneau) → repli : paysage à plat, portrait affleurant', () => {
    const base = rawZone().geometry as Record<string, unknown>;
    const flat = gridFromGeometry({ ...base, panels: [{ cx: 0, cy: 0 }] } as never);
    expect(flat.panelOrientation).toBe('landscape');
    const pitched = gridFromGeometry({ ...base, flush: true, panels: [{ cx: 0, cy: 0 }] } as never);
    expect(pitched.panelOrientation).toBe('portrait');
  });
});

// ── 4. Multi-pans : pan actif, pans nus, totaux ──────────────────────────────

describe('visionneuse pleine — plusieurs pans', () => {
  const zoneA = rawZone({ id: 'A', geometry: { ...(rawZone().geometry as object), panels: columns(PORTRAIT_PITCH, 3) } });
  const zoneB = rawZone({
    id: 'B',
    vertices: squareLngLat(9).map(([lng, lat]) => [lng + 0.001, lat] as [number, number]),
    geometry: {
      azimuthDeg: 180,
      tiltDeg: 13,
      family: 'south',
      flush: false,
      count: 7,
      origin: [LNG0 + 0.001, LAT0],
      panels: columns(PORTRAIT_PITCH, 7),
    },
  });

  it('le pan ACTIF est celui qui porte le plus de panneaux posés', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, zoneB))!;
    expect(plan.zones[plan.activeIndex].id).toBe('B');
    expect(plan.totalPanels).toBe(10);
  });

  it('un pan SANS calepinage réel ne fait pas échouer le reste (volume nu, comme l’ERP)', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, rawZone({ id: 'C', geometry: undefined })))!;
    expect(plan.zones.map((z) => z.id)).toEqual(['A', 'C']);
    expect(plan.zones[1].plan).toBeNull();
    expect(plan.zones[1].panelCount).toBe(0);
    expect(plan.zones[plan.activeIndex].id).toBe('A');
  });

  it('viewerAreaRecords : un enregistrement par pan, renderPlan porté, aucun chiffre', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, rawZone({ id: 'C', geometry: undefined })))!;
    const areas = viewerAreaRecords(plan);
    expect(areas.map((a) => a.id)).toEqual(['A', 'C']);
    expect(areas[0].renderPlan).not.toBeNull();
    expect(areas[1].renderPlan).toBeNull();
    for (const a of areas) expect(a.result).toBeNull();
  });

  it('le centre de la vue est le centroïde de TOUS les sommets', () => {
    const plan = buildViewerFullPlan(layoutOf(zoneA, zoneB))!;
    expect(plan.center[0]).toBeCloseTo(LNG0 + 0.0005, 9);
    expect(plan.center[1]).toBeCloseTo(LAT0, 9);
    expect(plan.spanM).toBeGreaterThan(24);
  });
});

// ── 5. Cadrage caméra ────────────────────────────────────────────────────────

describe('visionneuse pleine — zoom initial (Web Mercator, tuiles 512 px)', () => {
  it('cadre le toit dans la boîte : une emprise de 200 m sur 800 px ≈ zoom 17,5', () => {
    expect(zoomForSpanM(200, 800, LAT0)).toBeCloseTo(17.48, 1);
  });

  it('plus l’emprise est grande, plus on est dézoomé (échelle ville comprise)', () => {
    const toit = zoomForSpanM(200, 800, LAT0);
    const quartier = zoomForSpanM(1000, 800, LAT0);
    const ville = zoomForSpanM(5000, 800, LAT0);
    expect(quartier).toBeLessThan(toit);
    expect(ville).toBeLessThan(quartier);
    expect(ville).toBeGreaterThan(11); // ~12,8 : une ville entière tient à l’écran
  });

  it('borné, et jamais NaN sur une entrée aberrante', () => {
    expect(zoomForSpanM(1, 800, LAT0)).toBe(VIEWER_FULL_MAX_ZOOM);
    expect(zoomForSpanM(1e9, 800, LAT0)).toBe(VIEWER_FULL_MIN_ZOOM);
    expect(Number.isFinite(zoomForSpanM(NaN, 0, NaN))).toBe(true);
  });
});

// ── 6. Le CONTRAT lecture seule (garde de source) ────────────────────────────

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const BOOT = readFileSync(root('../src/scripts/roofPro11/viewerFullBoot.ts'), 'utf-8');
const SCENE = readFileSync(root('../src/scripts/roofPro11/scene3d.ts'), 'utf-8');

describe('visionneuse pleine — lecture seule STRICTE', () => {
  it('aucun module d’ÉDITION n’est importé (tracé, obstacles, disposition, optimiseur, matrice)', () => {
    for (const m of ['mapDraw', 'obstaclesUi', 'layoutEditor', 'optimizer', 'matrix', 'prefill', 'shadingUi', 'prodWindow', 'consumption', 'zones']) {
      expect(BOOT).not.toMatch(new RegExp(`from '\\./${m}'`));
    }
  });

  it('aucun écouteur de geste d’édition sur la carte (clic, double-clic, glissé)', () => {
    for (const ev of ['click', 'dblclick', 'mousedown', 'mousemove', 'mouseup', 'touchstart', 'touchmove', 'contextmenu']) {
      expect(BOOT).not.toContain(`map.on('${ev}'`);
      expect(BOOT).not.toContain(`map.once('${ev}'`);
    }
    // Les SEULS écouteurs carte : le boot de la scène et la panne d'imagerie.
    expect(BOOT).toContain("map.on('load'");
    expect(BOOT).toContain("map.on('error'");
  });

  it('la scène est celle de l’ERP (import de scene3d), en mode readOnly', () => {
    expect(BOOT).toContain("from './scene3d'");
    expect(BOOT).toContain('readOnly: true');
  });

  it('aucune borne de navigation : le client peut dézoomer jusqu’à la ville', () => {
    // Options MapLibre jamais posées (la mention en commentaire, elle, est permise).
    expect(BOOT).not.toContain('maxBounds:');
    expect(BOOT).not.toContain('minZoom:');
    expect(BOOT).not.toContain('.setMaxBounds(');
  });

  it('scene3d : `readOnly` est ADDITIF — absent (ERP) = comportement historique', () => {
    expect(SCENE).toContain('readOnly?: boolean;');
    expect(SCENE).toContain('const readOnly = deps.readOnly === true;');
    // Le pan « autre » reste identifié même quand il n'est plus atténué : la
    // valeur par défaut rend les deux appels historiques inchangés.
    expect(SCENE).toContain('isOtherZone: boolean = dim');
  });
});
