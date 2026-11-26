// @vitest-environment jsdom
// VISIONNEUSE PLEINE (page publique /proposition) — la moitié TESTABLE.
// (LOT 6 — jsdom pour la barre de la visionneuse au soleil, section 7 ; les sections 1-6 restent pures.)
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
// Sections 1-6 : modules purs. Section 7 : jsdom (la barre au soleil). Sections 8-9 (lot 8) : le VRAI Three.js et
// la vraie scène `scene3d.ts`, sur une carte MapLibre et un WebGLRenderer FACTICES (déclarés plus bas).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
import { bornesCarte, degradeLegende, libelleInstant, libelleJournee, lireVisionneuseSoleil } from '../src/lib/visionneuseSoleil';
import { couleurAccesActive } from '../src/lib/shadingEngine';
import { attacherSoleil, bornesJournee, couleurParPanneau } from '../src/scripts/roofPro11/viewerSoleil';
import type { ViewerFullHandle } from '../src/scripts/roofPro11/viewerFullBoot';
import { ecrireTeintesPanneaux, GAIN_TEINTE_PANNEAU } from '../src/scripts/roofPro11/scene3d';
import { DELAIS_RELANCE_PHOTO_MS, ESSAIS_PHOTO_MAX } from '../src/scripts/roofPro11/relancePhoto';
import { TEINTES_PRESENTATION } from '../src/scripts/roofPro11/jeuPresentation';

// Section 8 — une carte MapLibre et un WebGLRenderer FACTICES (jsdom n'a ni GPU ni MapLibre) ; tout le
// reste (Three.js, scene3d, le contexte du boot) est le vrai code. Les sections 1-7 n'en dépendent pas.
const carteFactice = vi.hoisted(() => {
  const cartes: FakeMap[] = [];
  const rendus: unknown[] = [];
  type Ecouteur = (e?: unknown) => void;
  type Couche = { onAdd?: (m: unknown, gl: unknown) => void; onRemove?: (m: unknown, gl: unknown) => void; render: (gl: unknown, args: unknown) => void };
  class FakeMap {
    ecouteurs = new Map<string, Ecouteur[]>();
    couches: Couche[] = [];
    retiree = false;
    repeints = 0;
    canevas = document.createElement('canvas');
    constructor(public options: unknown) { cartes.push(this); }
    on(ev: string, fn: Ecouteur) { this.ecouteurs.set(ev, [...(this.ecouteurs.get(ev) ?? []), fn]); return this; }
    once(ev: string, fn: Ecouteur) { const w: Ecouteur = (e) => { this.off(ev, w); fn(e); }; return this.on(ev, w); }
    off(ev: string, fn: Ecouteur) { this.ecouteurs.set(ev, (this.ecouteurs.get(ev) ?? []).filter((f) => f !== fn)); return this; }
    fire(ev: string, e?: unknown) { for (const fn of [...(this.ecouteurs.get(ev) ?? [])]) fn(e); }
    addControl() { return this; }
    ajouts = 0;
    styleCharge = true;
    addLayer(c: Couche) { this.ajouts++; this.couches.push(c); c.onAdd?.(this, {}); return this; }
    isStyleLoaded() { return this.styleCharge; }
    /** Comme MapLibre à la perte du contexte : le style est détruit, couches personnalisées comprises ; à la
     *  restauration il revient SANS elles (ici : `styleCharge` faux jusqu'à `style.load`). */
    perdreContexte() { for (const c of this.couches) c.onRemove?.(this, {}); this.couches = []; this.styleCharge = false; this.fire('webglcontextlost'); }
    resize() { return this; }
    getZoom() { return 19; }
    getPitch() { return 58; }
    getBearing() { return 0; }
    getCanvas() { return this.canevas; }
    getLayer(id?: string) { return this.couches.find((c) => (c as { id?: string }).id === id); }
    triggerRepaint() { this.repeints++; }
    ciels: unknown[] = [];
    setSky(s: unknown) { this.ciels.push(s); }
    setMaxBounds() {}
    setMinZoom() {}
    setMaxPitch() {}
    remove() { this.retiree = true; for (const c of this.couches) c.onRemove?.(this, {}); this.couches = []; }
  }
  class FakeRenderer {
    shadowMap = { enabled: false, type: 0 };
    resetState() {}
    setViewport() {}
    render(scene: unknown) { rendus.push(scene); }
    dispose() {}
  }
  return { cartes, rendus, FakeMap, FakeRenderer, maillages: { n: 0 } };
});
vi.mock('maplibre-gl', () => {
  class NavigationControl {}
  const MercatorCoordinate = { fromLngLat: () => ({ x: 0, y: 0, z: 0, meterInMercatorCoordinateUnits: () => 1e-7 }) };
  const api = { Map: carteFactice.FakeMap, NavigationControl, MercatorCoordinate };
  return { default: api, ...api };
});
vi.mock('maplibre-gl/dist/maplibre-gl.css?url', () => ({ default: 'maplibre-gl.css' }));
vi.mock('three', async (origine) => {
  const t = await origine<typeof import('three')>();
  // Les maillages construits sont COMPTÉS (lot 8, B3 : un pas de soleil n'en construit aucun).
  class Mesh extends t.Mesh { constructor(...a: ConstructorParameters<typeof t.Mesh>) { super(...a); carteFactice.maillages.n++; } }
  class InstancedMesh extends t.InstancedMesh { constructor(...a: ConstructorParameters<typeof t.InstancedMesh>) { super(...a); carteFactice.maillages.n++; } }
  return { ...t, WebGLRenderer: carteFactice.FakeRenderer, Mesh, InstancedMesh };
});

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

  it('LOT 6 — poignée ADDITIVE : sans `instant` ni `environnement`, soleil et contexte d’aujourd’hui', () => {
    expect(BOOT).toContain('sunHour: opts.instant?.heure ?? DEFAULT_SUN_HOUR,');
    expect(BOOT).toContain('sunDay: opts.instant?.jour ?? WINTER_SOLSTICE_DAY,');
    expect(BOOT).toContain('...(opts.environnement?.length ? { environment: opts.environnement } : {}),');
    expect(BOOT).toContain('scene3d.setSolarAccessHeatmap(');
    // P1 — verre et œil de l'atelier SEULEMENT quand le pan actif sera teinté (drapeau absent sinon).
    expect(BOOT).toContain('const teinteAccesVisible = opts.indexTeintes?.includes(plan.activeIndex) === true;');
    expect(BOOT).toContain('reducedMotion, ...(teinteAccesVisible ? { teinteAccesVisible } : {}) };');
    expect(SCENE).toContain('materiauVerre(panelTexOf(rapport, jeu), verreEtOeilAtelier(opts))');
    expect(SCENE).toContain('if (!(verreEtOeilAtelier(opts) && poserOeil(threeCamera, m)))');
    // Les bornes de la visionneuse de confiance vivent dans viewerSoleil.ts, jamais ici.
    const SOLEIL = readFileSync(root('../src/scripts/roofPro11/viewerSoleil.ts'), 'utf-8');
    expect(SOLEIL).toContain('poignee.carte.setMaxBounds(');
    expect(SOLEIL).toContain('poignee.carte.setMinZoom(');
    expect(SOLEIL).toContain('poignee.carte.setMaxPitch(INCLINAISON_MAX)');
    expect(SOLEIL).not.toMatch(/\.on\('(click|dblclick|mousedown|touchstart)'/);
    for (const m of ['mapDraw', 'obstaclesUi', 'layoutEditor', 'optimizer', 'shadingUi', 'shadingEngine\\.ts']) {
      expect(SOLEIL).not.toMatch(new RegExp(`from '\\./${m}'`));
    }
  });
});

// ── 7. LOT 6 — la visionneuse au soleil des liens de confiance (D-ACAL-132 à 138) ──

const CONTRAT_SOLEIL = JSON.parse(readFileSync(root('../src/contract_samples/visionneuse_soleil.json'), 'utf-8')) as Record<string, any>;
const payloadSoleil = (cle: 'exemple' | 'exemple_sans_mesure' = 'exemple') => structuredClone(CONTRAT_SOLEIL[cle]) as Record<string, any>;
// Le pan du contrat : `zone-1`, six modules.
const LAYOUT_SOLEIL = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), count: 6, panels: columns(PORTRAIT_PITCH, 6) } }));

describe('lireVisionneuseSoleil — exemples du contrat', () => {
  it('exemple : accès servis tels quels, objets voisins en géométrie seule, instant choisi', () => {
    const v = lireVisionneuseSoleil(payloadSoleil(), LAYOUT_SOLEIL)!;
    expect(v.zones).toEqual([{ index: 0, id: 'zone-1', acces: [0.981, 0.979, 0.962, 0.874, null, 0.988] }]);
    expect(v.environnement).toHaveLength(2);
    expect(v.environnement[0]).toEqual({ id: 'voisin-0', kind: 'arbre', centerLng: -7.6195, centerLat: 33.5741, heightM: 7.5, crownDiameterM: 5, evergreen: true });
    expect(v.environnement[1].footprint).toHaveLength(4);
    expect(v.ouverture).toEqual({ jour: 355, heure: 16 });
  });

  it('l’exemple de `proposal_data.json` (lane B) se lit aussi, contre un pan de trois modules', () => {
    const proposal = JSON.parse(readFileSync(root('../src/contract_samples/proposal_data.json'), 'utf-8')) as Record<string, any>;
    const trois = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), count: 3, panels: columns(PORTRAIT_PITCH, 3) } }));
    const v = lireVisionneuseSoleil(proposal.exemple, trois)!;
    expect(v.zones).toEqual([{ index: 0, id: 'zone-1', acces: [0.981, 0.874, null] }]);
    expect(v.ouverture).toEqual({ jour: 172, heure: 12 });
  });

  it('exemple sans mesure : aucune zone, aucun objet, ouverture l’été à midi (D-ACAL-135)', () => {
    expect(lireVisionneuseSoleil(payloadSoleil('exemple_sans_mesure'), LAYOUT_SOLEIL)).toEqual({ zones: [], environnement: [], ouverture: { jour: 172, heure: 12 } });
  });
});

describe('lireVisionneuseSoleil — absent ou malformé → null, jamais un throw', () => {
  const sans = (cle: string) => {
    const p = payloadSoleil();
    delete p.visionneuse_soleil[cle];
    return p;
  };
  const piege = { get visionneuse_soleil(): unknown { throw new Error('piège'); } };
  const mauvais: unknown[] = [
    undefined, null, 0, 'x', [], {}, { visionneuse_soleil: null }, { visionneuse_soleil: [] }, { visionneuse_soleil: { version: 2, zones: [], environnement: [], instant_choisi: null } },
    sans('zones'), sans('environnement'), sans('instant_choisi'), sans('version'),
    { visionneuse_soleil: { version: 1, zones: {}, environnement: [], instant_choisi: null } },
    { visionneuse_soleil: { version: 1, zones: [], environnement: [], instant_choisi: { jour: 400, heure: 12 } } },
    piege,
  ];
  it.each(mauvais.map((m, i) => [i, m]))('entrée %s', (_i, m) => {
    expect(lireVisionneuseSoleil(m, LAYOUT_SOLEIL)).toBeNull();
  });

  it('sans layout lu → null', () => {
    expect(lireVisionneuseSoleil(payloadSoleil(), null)).toBeNull();
  });

  it('pan écarté EN BLOC : id différent, longueur différente, valeur hors [0 ; 1] ou non numérique, tout null', () => {
    const variantes: Array<(z: Record<string, any>) => void> = [
      (z) => { z.id = 'zone-2'; },
      (z) => { z.acces.pop(); },
      (z) => { z.acces[0] = 1.2; },
      (z) => { z.acces[1] = '0.5'; },
      (z) => { z.acces = z.acces.map(() => null); },
      (z) => { z.index = 3; },
    ];
    for (const casse of variantes) {
      const p = payloadSoleil();
      casse(p.visionneuse_soleil.zones[0]);
      expect(lireVisionneuseSoleil(p, LAYOUT_SOLEIL)!.zones).toEqual([]);
    }
  });

  it('objets voisins : jamais le libellé ni la hauteur future ; supposé coupé, sans hauteur ou genre inconnu → écarté', () => {
    const p = payloadSoleil();
    const arbre = p.visionneuse_soleil.environnement[0];
    Object.assign(arbre, { label: 'Chez M. Voisin', id: 'env-7', hauteurFutureM: 12, dansAns: 5 });
    p.visionneuse_soleil.environnement.push({ ...arbre, supposeCoupe: true }, { ...arbre, heightM: 0 }, { ...arbre, kind: 'piscine' });
    const v = lireVisionneuseSoleil(p, LAYOUT_SOLEIL)!;
    expect(v.environnement).toHaveLength(2);
    expect(JSON.stringify(v)).not.toMatch(/Voisin|env-7|hauteurFutureM|dansAns|label/);
  });
});

describe('visionneuse au soleil — libellé, bornes de carte, légende, teinte', () => {
  it('libellé de l’instant dans l’année de dessin 2028 de l’atelier, trois langues', () => {
    expect(libelleInstant(355, 12, 'fr')).toBe('20 décembre · 12 h (heure solaire)');
    expect(libelleInstant(172, 16, 'en')).toBe('20 June · 16:00 (solar time)');
    expect(libelleInstant(172, 16, 'ar')).toBe('20 يونيو · الساعة 16 (بالتوقيت الشمسي)');
  });

  it('les bornes du curseur disent aussi l’heure SOLAIRE, trois langues (jamais une heure de montre)', () => {
    expect(libelleJournee(7, 17, 'fr')).toBe('Lever 7 h · coucher 17 h (heure solaire)');
    expect(libelleJournee(7, 17, 'en')).toBe('Sunrise 7:00 · sunset 17:00 (solar time)');
    expect(libelleJournee(7, 17, 'ar')).toBe('الشروق الساعة 7 · الغروب الساعة 17 (بالتوقيت الشمسي)');
  });

  it('bornes : emprise des sommets + 150 m, zoom mini = zoom initial − 2 (D-ACAL-138)', () => {
    const b = bornesCarte(LAYOUT_SOLEIL, 19.2)!;
    expect(b.zoomMin).toBeCloseTo(17.2);
    const [[w, s], [e, n]] = b.bornes;
    for (const [lng, lat] of LAYOUT_SOLEIL.zones[0].vertices) {
      expect((lat - s) * DEG2M).toBeGreaterThan(149);
      expect((n - lat) * DEG2M).toBeGreaterThan(149);
      expect((lng - w) * DEG2M * COS).toBeGreaterThan(149);
      expect((e - lng) * DEG2M * COS).toBeGreaterThan(149);
    }
    expect((n - s) * DEG2M).toBeLessThan(24 + 301);
  });

  it('légende : les couleurs MÊMES que la teinte (palette atelier)', () => {
    const c0 = couleurAccesActive(0, 'atelier');
    expect(degradeLegende()).toContain(`rgb(${Math.round(c0.r * 255)},${Math.round(c0.g * 255)},${Math.round(c0.b * 255)}) 0%`);
    expect(degradeLegende()).toContain('rgb(245,158,11) 100%');
  });

  it('teinte du pan actif seulement ; module non calculé = null (la scène garde sa teinte d’origine), jamais un blanc', () => {
    const v = lireVisionneuseSoleil(payloadSoleil(), LAYOUT_SOLEIL)!;
    expect(couleurParPanneau(v, 1)).toBeNull();
    const f = couleurParPanneau(v, 0)!;
    expect(f(0)).toEqual(couleurAccesActive(0.981, 'atelier'));
    expect(f(4)).toBeNull();
    expect(f(99)).toBeNull();
    // Écrit par la scène : le module non calculé reste à 1,1,1 (neutre), le module mesuré est gainé.
    const rgb: number[][] = [];
    ecrireTeintesPanneaux({ needsUpdate: false, setXYZ: (i, r, g, b) => { rgb[i] = [r, g, b]; } }, [0, 4], f);
    expect(rgb[1]).toEqual([1, 1, 1]);
    expect(rgb[0][0]).toBeCloseTo(couleurAccesActive(0.981, 'atelier').r * GAIN_TEINTE_PANNEAU);
  });

  it('journée : lever et coucher en heures pleines, de la même formule que l’atelier', () => {
    const hiver = bornesJournee(LAT0, 355)!;
    const ete = bornesJournee(LAT0, 172)!;
    expect(Number.isInteger(hiver.riseHour) && Number.isInteger(hiver.setHour)).toBe(true);
    expect(ete.setHour - ete.riseHour).toBeGreaterThan(hiver.setHour - hiver.riseHour);
    expect(bornesJournee(89, 355)).toBeNull();
  });
});

describe('attacherSoleil — la barre pilote la poignée (jsdom)', () => {
  const BARRE = `<div id="roof3d-soleil" hidden><div data-soleil-legende></div>
    <button data-soleil-lecture disabled></button><strong data-soleil-quand></strong><p data-soleil-journee></p>
    <input type="range" data-soleil-heure disabled /><button data-soleil-saison="hiver" disabled></button><button data-soleil-saison="ete" disabled></button></div>`;
  function monter(over: Partial<Parameters<typeof attacherSoleil>[0]> = {}, payload = payloadSoleil()) {
    document.body.innerHTML = BARRE;
    const barre = document.getElementById('roof3d-soleil')!;
    const carte = { setMaxBounds: vi.fn(), setMinZoom: vi.fn(), setMaxPitch: vi.fn() };
    const poignee = { carte, zoomInitial: 19, indexActif: 0, panelCount: 6, destroy: vi.fn(), poserInstant: vi.fn(), teinter: vi.fn() };
    const soleil = lireVisionneuseSoleil(payload, LAYOUT_SOLEIL)!;
    const debrancher = attacherSoleil({ barre, poignee: poignee as unknown as ViewerFullHandle, soleil, layout: LAYOUT_SOLEIL, avecTeinte: true, reducedMotion: false, ...over });
    const q = <T extends HTMLElement>(s: string) => barre.querySelector<T>(s)!;
    return { barre, poignee, carte, debrancher, q };
  }
  afterEach(() => {
    vi.useRealTimers();
    document.documentElement.lang = 'fr';
  });

  it('C3 — rendue cachée, montrée au branchement ; débranchée : cachée, plus aucun reste de légende', () => {
    const { barre, q, debrancher } = monter();
    expect(barre.hidden).toBe(false);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(true);
    debrancher();
    expect(barre.hidden).toBe(true);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(false);
  });

  it('branchée : contrôles actifs, teinte posée, légende visible, carte bornée, instant affiché', () => {
    const { poignee, carte, q } = monter();
    expect(q<HTMLButtonElement>('[data-soleil-lecture]').disabled).toBe(false);
    expect(q<HTMLInputElement>('[data-soleil-heure]').disabled).toBe(false);
    expect(poignee.teinter).toHaveBeenCalledTimes(1);
    expect(q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(true);
    expect(carte.setMaxBounds).toHaveBeenCalledWith(bornesCarte(LAYOUT_SOLEIL, 19)!.bornes);
    expect(carte.setMinZoom).toHaveBeenCalledWith(17);
    expect(carte.setMaxPitch).toHaveBeenCalledWith(60);
    expect(q('[data-soleil-quand]').textContent).toBe('20 décembre · 16 h (heure solaire)');
    const b = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!;
    expect(q('[data-soleil-journee]').textContent).toBe(libelleJournee(b.riseHour, b.setHour, 'fr'));
    expect(q('[data-soleil-saison="hiver"]').getAttribute('aria-pressed')).toBe('true');
  });

  it('aucune valeur enregistrée, ou autre taille montrée : ni teinte ni légende (D-ACAL-136)', () => {
    const a = monter({}, payloadSoleil('exemple_sans_mesure'));
    expect(a.poignee.teinter).not.toHaveBeenCalled();
    expect(a.q('[data-soleil-legende]').hasAttribute('data-soleil-visible')).toBe(false);
    const b = monter({ avecTeinte: false });
    expect(b.poignee.teinter).not.toHaveBeenCalled();
  });

  it('lecture : un pas toutes les 700 ms depuis le lever ; second clic = pause', () => {
    vi.useFakeTimers();
    const { poignee, q } = monter();
    const lever = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!.riseHour;
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(q('[data-soleil-lecture]').getAttribute('aria-pressed')).toBe('true');
    vi.advanceTimersByTime(700);
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, lever);
    vi.advanceTimersByTime(700);
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, lever + 1);
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(q('[data-soleil-lecture]').getAttribute('aria-pressed')).toBe('false');
    vi.advanceTimersByTime(5000);
    expect(poignee.poserInstant).toHaveBeenCalledTimes(2);
  });

  it('reduced-motion : un seul pas (l’heure suivante), aucune boucle programmée', () => {
    vi.useFakeTimers();
    const { poignee, q } = monter({ reducedMotion: true });
    const b = bornesJournee(LAYOUT_SOLEIL.zones[0].vertices[0][1], 355)!;
    q<HTMLButtonElement>('[data-soleil-lecture]').click();
    expect(poignee.poserInstant).toHaveBeenCalledTimes(1);
    expect(poignee.poserInstant).toHaveBeenCalledWith(355, 16 + 1 <= b.setHour ? 17 : b.riseHour);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('curseur et saisons : l’instant suit, l’heure reste dans la journée', () => {
    const { poignee, q } = monter();
    const curseur = q<HTMLInputElement>('[data-soleil-heure]');
    curseur.value = '10';
    curseur.dispatchEvent(new Event('input'));
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(355, 10);
    q<HTMLButtonElement>('[data-soleil-saison="ete"]').click();
    expect(poignee.poserInstant).toHaveBeenLastCalledWith(172, 10);
    expect(q('[data-soleil-saison="ete"]').getAttribute('aria-pressed')).toBe('true');
    expect(q('[data-soleil-quand]').textContent).toBe('20 juin · 10 h (heure solaire)');
  });

  it('la langue de la page change : le libellé suit ; débranchée : contrôles inertes', async () => {
    const { q, debrancher, poignee } = monter();
    document.documentElement.lang = 'ar';
    await new Promise((r) => setTimeout(r, 0));
    expect(q('[data-soleil-quand]').textContent).toBe('20 دجنبر · الساعة 16 (بالتوقيت الشمسي)');
    debrancher();
    expect(q<HTMLButtonElement>('[data-soleil-lecture]').disabled).toBe(true);
    q<HTMLButtonElement>('[data-soleil-saison="ete"]').click();
    expect(poignee.poserInstant).not.toHaveBeenCalled();
  });
});

// ── 8. Premier rendu RÉEL : la scène de l'ERP + le contexte EXACT du boot (lot 8) ──
// Le constat du fondateur (26/11) : sur un lien de confiance, « lecture » ne changeait rien. Ce bloc
// rejoue le VRAI `bootViewerFull` (son contexte, sa scène `scene3d.ts`) sur la carte et le
// WebGLRenderer factices du haut du fichier : le premier rendu, puis un pas de soleil.

/** Toit plat réel : 35 modules (5 rangées × 7) sur châssis, aucun obstacle, soleil du 21 décembre 16 h 15. */
const RANGEES_PLAT = Array.from({ length: 5 }, (_, r) => columns(PORTRAIT_PITCH, 7, (r - 2) * 3.2)).flat();
const LAYOUT_PLAT_35 = layoutOf(rawZone({ geometry: { ...(rawZone().geometry as object), count: 35, panels: RANGEES_PLAT } }));
const INSTANT_REEL = { jour: 356, heure: 16.25 };
type CarteFactice = InstanceType<typeof carteFactice.FakeMap>;
type Position = { x: number; y: number; z: number };

/** Tout texte peint dans un canevas (étiquette de cote, numéro de module…) pendant la construction de la scène. */
const textesPeints: string[] = [];
function contexte2dFactice() {
  const degrade = { addColorStop() {} };
  return new Proxy({}, {
    get(_t, prop) {
      if (prop === 'fillText' || prop === 'strokeText') return (texte: unknown) => { textesPeints.push(String(texte)); };
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient' || prop === 'createPattern') return () => degrade;
      if (prop === 'getImageData') return () => ({ data: new Uint8ClampedArray(4) });
      if (prop === 'measureText') return () => ({ width: 0 });
      if (prop === 'canvas') return { width: 512, height: 280 };
      return () => undefined;
    },
    set() { return true; },
  });
}

/** Rend une image comme MapLibre le ferait, et renvoie la position du soleil (DirectionalLight) dessiné. */
function soleilDessine(carte: CarteFactice): Position | null {
  const identite = new Float64Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
  carte.couches[0]?.render({ drawingBufferWidth: 800, drawingBufferHeight: 600 }, { defaultProjectionData: { mainMatrix: identite } });
  const scene = carteFactice.rendus.at(-1) as { traverse: (f: (o: { isDirectionalLight?: boolean; position: Position }) => void) => void } | undefined;
  let soleil: Position | null = null;
  scene?.traverse((o) => { if (o.isDirectionalLight) soleil = { x: o.position.x, y: o.position.y, z: o.position.z }; });
  return soleil;
}

describe('visionneuse pleine — premier rendu réel (scene3d + contexte du boot)', () => {
  const getContextOrigine = HTMLCanvasElement.prototype.getContext;
  beforeEach(() => {
    carteFactice.cartes.length = 0;
    carteFactice.rendus.length = 0;
    textesPeints.length = 0;
    const c2d = contexte2dFactice();
    (HTMLCanvasElement.prototype as unknown as { getContext: () => unknown }).getContext = () => c2d;
  });
  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = getContextOrigine;
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  async function demarrer(opts: Record<string, unknown> = {}) {
    const { bootViewerFull } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const el = document.createElement('div');
    document.body.appendChild(el);
    const onReady = vi.fn();
    const onFail = vi.fn();
    const poignee = bootViewerFull(el, LAYOUT_PLAT_35, { maptilerKey: 'cle-test', reducedMotion: true, instant: INSTANT_REEL, onReady, onFail, ...opts });
    expect(poignee).not.toBeNull();
    return { poignee: poignee!, carte: carteFactice.cartes[0], onReady, onFail };
  }

  it('le premier rendu passe : onReady, aucun échec, la scène est dessinée avec ses 35 modules', async () => {
    const { poignee, carte, onReady, onFail } = await demarrer();
    expect(poignee.panelCount).toBe(35);
    carte.fire('load');
    expect(onFail).not.toHaveBeenCalled();
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(carte.retiree).toBe(false);
    expect(soleilDessine(carte)).not.toBeNull();
  });

  it('un pas de soleil rejoue la scène : la lumière bouge entre deux heures, un repeint est demandé', async () => {
    const { poignee, carte, onFail } = await demarrer();
    carte.fire('load');
    const avant = soleilDessine(carte)!;
    const repeints = carte.repeints;
    poignee.poserInstant(INSTANT_REEL.jour, 10);
    expect(onFail).not.toHaveBeenCalled();
    expect(carte.repeints).toBeGreaterThan(repeints);
    const apres = soleilDessine(carte)!;
    // 16 h 15 : soleil au sud-ouest ; 10 h : au sud-est — la lumière passe de l'autre côté du toit.
    expect(Math.sign(apres.x - avant.x)).toBe(1);
    expect(Math.hypot(apres.x - avant.x, apres.y - avant.y, apres.z - avant.z)).toBeGreaterThan(1);
  });

  it('toutes les branches lecture seule rendues sans jeter : second pan en pente, obstacle, voisins, teinte', async () => {
    const [lngC, latC] = at(0, 0);
    const pente = rawZone({ id: 'zone-2', vertices: squareLngLat(4).map(([x, y]) => [x + 0.0004, y] as [number, number]), roofType: 'pitched', pitchDeg: 25,
      geometry: { ...(rawZone().geometry as object), origin: [LNG0 + 0.0004, LAT0], count: 2, panels: columns(PORTRAIT_PITCH, 2) } });
    const actif = rawZone({ obstacles: [{ centerLng: lngC, centerLat: latC + 0.00008, lengthM: 1, widthM: 1 }], geometry: { ...(rawZone().geometry as object), count: 35, panels: RANGEES_PLAT } });
    const voisins = [
      { id: 'v-0', kind: 'arbre', centerLng: lngC, centerLat: latC - 0.0002, heightM: 7.5, crownDiameterM: 5, evergreen: true },
      { id: 'v-1', kind: 'batiment', centerLng: lngC + 0.0002, centerLat: latC, heightM: 9, lengthM: 8, widthM: 6 },
    ];
    const { bootViewerFull } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const el = document.body.appendChild(document.createElement('div'));
    const onReady = vi.fn();
    const onFail = vi.fn();
    const poignee = bootViewerFull(el, layoutOf(actif, pente), { maptilerKey: 'cle-test', instant: INSTANT_REEL, environnement: voisins as never, indexTeintes: [0], onReady, onFail })!;
    const carte = carteFactice.cartes[0];
    carte.fire('load');
    poignee.teinter(() => ({ r: 0.9, g: 0.2, b: 0.1 }));
    poignee.poserInstant(172, 9);
    expect(soleilDessine(carte)).not.toBeNull();
    const geometries = new Set<string>();
    (carteFactice.rendus.at(-1) as { traverse: (f: (o: { geometry?: { type: string } }) => void) => void }).traverse((o) => { if (o.geometry) geometries.add(o.geometry.type); });
    expect(geometries.has('CylinderGeometry')).toBe(true); // l'arbre voisin est bien dessiné
    expect(onFail).not.toHaveBeenCalled();
    expect(onReady).toHaveBeenCalledTimes(1);
    poignee.destroy();
    expect(carte.retiree).toBe(true);
  });

  it('lien de confiance : la teinte des accès enregistrés et l’obstacle servi sont dessinés', async () => {
    const [lngC, latC] = at(0, 0);
    const actif = rawZone({ obstacles: [{ centerLng: lngC + 0.00004, centerLat: latC + 0.00011, lengthM: 4, widthM: 1 }], geometry: { ...(rawZone().geometry as object), count: 35, panels: RANGEES_PLAT } });
    const layout = layoutOf(actif);
    const payload = { visionneuse_soleil: { version: 1, zones: [{ index: 0, id: 'zone-1', acces: RANGEES_PLAT.map((_, i) => 0.84 + i * 0.004) }], environnement: [], instant_choisi: { jour: 356, heure: 16.25 } } };
    const soleil = lireVisionneuseSoleil(payload, layout)!;
    const { bootViewerFull } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const el = document.body.appendChild(document.createElement('div'));
    const poignee = bootViewerFull(el, layout, { maptilerKey: 'cle-test', instant: soleil.ouverture, indexTeintes: [0] })!;
    const carte = carteFactice.cartes[0];
    carte.fire('load');
    poignee.teinter(couleurParPanneau(soleil, poignee.indexActif)!);
    poignee.poserInstant(356, 12);
    soleilDessine(carte);
    let teintes = 0;
    let obstacle = false;
    (carteFactice.rendus.at(-1) as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => {
      if (o.isInstancedMesh && o.instanceColor) teintes += Array.from(o.instanceColor.array as Float32Array).filter((v) => v !== 1).length;
      if (o.isMesh && !o.isInstancedMesh && o.material?.color?.getHex?.() === 0xff6b6b) obstacle = true;
    });
    expect(teintes).toBeGreaterThan(0); // les 35 modules portent la couleur de leur accès solaire
    expect(obstacle).toBe(true); // l'obstacle de 4 m du layout servi
  });

  it('B1 — lien de confiance : habit « Montrer au client » (murs clairs, ciel qui suit le soleil), teinte gardée ; standard : inchangé', async () => {
    const couleursDe = (scene: unknown) => {
      const c = new Set<number>();
      (scene as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => { const m = o.material; if (o.isMesh && m && !Array.isArray(m) && m.color) c.add(m.color.getHex()); });
      return c;
    };
    const confiance = await demarrer({ presentationClient: true, indexTeintes: [0] });
    confiance.carte.fire('load');
    confiance.poignee.teinter(() => ({ r: 0.9, g: 0.2, b: 0.1 }));
    soleilDessine(confiance.carte);
    const sceneConfiance = carteFactice.rendus.at(-1);
    expect(couleursDe(sceneConfiance).has(TEINTES_PRESENTATION.mur)).toBe(true);
    expect(couleursDe(sceneConfiance).has(TEINTES_PRESENTATION.beton)).toBe(true); // toit plat : dalle béton
    expect(confiance.carte.ciels.length).toBeGreaterThan(0);
    let teintes = 0;
    (sceneConfiance as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => {
      if (o.isInstancedMesh && o.instanceColor) teintes += Array.from(o.instanceColor.array as Float32Array).filter((v) => v !== 1).length;
    });
    expect(teintes).toBeGreaterThan(0);
    confiance.poignee.destroy();

    carteFactice.cartes.length = 0;
    const standard = await demarrer();
    standard.carte.fire('load');
    soleilDessine(standard.carte);
    expect(couleursDe(carteFactice.rendus.at(-1)).has(TEINTES_PRESENTATION.mur)).toBe(false);
    expect(standard.carte.ciels).toHaveLength(0);
  });

  it('B3 — un pas de soleil ne construit AUCUN maillage : même scène, lumière et ciel déplacés, teinte gardée', async () => {
    const { poignee, carte } = await demarrer({ presentationClient: true, indexTeintes: [0] });
    carte.fire('load');
    poignee.teinter(() => ({ r: 0.9, g: 0.2, b: 0.1 }));
    const avant = soleilDessine(carte)!;
    const scene = carteFactice.rendus.at(-1) as { traverse: (f: (o: Record<string, any>) => void) => void };
    const objets = (): unknown[] => { const l: unknown[] = []; scene.traverse((o) => l.push(o)); return l; };
    const objetsAvant = objets();
    const maillages = carteFactice.maillages.n;
    const ciels = carte.ciels.length;
    const repeints = carte.repeints;
    for (let h = 7; h < 17; h++) poignee.poserInstant(INSTANT_REEL.jour, h);
    expect(carteFactice.maillages.n).toBe(maillages); // aucun Mesh ni InstancedMesh construit en dix pas
    expect(objets()).toEqual(objetsAvant); // les mêmes objets, aucun retiré ni ajouté
    expect(carte.repeints - repeints).toBe(10); // un repeint par pas
    expect(carte.ciels.length - ciels).toBe(10); // le ciel suit chaque pas
    expect(soleilDessine(carte)).not.toEqual(avant);
    let teintes = 0;
    scene.traverse((o) => { if (o.isInstancedMesh && o.instanceColor) teintes += Array.from(o.instanceColor.array as Float32Array).filter((v) => v !== 1).length; });
    expect(teintes).toBeGreaterThan(0);
  });

  it('B2 — sol d’ombre sur le lien de confiance : l’ombre la plus longue de l’après-midi d’hiver n’est pas coupée', async () => {
    const { poignee, carte } = await demarrer({ presentationClient: true });
    carte.fire('load');
    const lever = bornesJournee(LAT0, INSTANT_REEL.jour)!;
    poignee.poserInstant(INSTANT_REEL.jour, lever.setHour); // dernière heure de la lecture : soleil le plus bas
    soleilDessine(carte);
    let sol: Record<string, any> | null = null;
    let lumiere: Record<string, any> | null = null;
    (carteFactice.rendus.at(-1) as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => {
      if (o.name === 'sol-ombre-client') sol = o;
      if (o.isDirectionalLight) lumiere = o;
    });
    expect(sol).not.toBeNull();
    const s = sol as unknown as Record<string, any>;
    const l = lumiere as unknown as Record<string, any>;
    expect(s.material.isShadowMaterial).toBe(true);
    // Le coin haut du bâtiment (6 m de dessin + châssis) projette son ombre à l'opposé du soleil.
    const d = { x: l.position.x - l.target.position.x, y: l.position.y - l.target.position.y, z: l.position.z - l.target.position.z };
    const n = Math.hypot(d.x, d.y, d.z);
    const h = Math.hypot(d.x, d.y);
    const elevation = Math.atan2(d.z, h);
    const longueur = (6 + 1.5) / Math.tan(elevation);
    const ring = buildViewerFullPlan(LAYOUT_PLAT_35)!.zones[0].plan!.pack.ringENU;
    const demiPlan = s.geometry.parameters.width / 2;
    const right = l.shadow.camera.right as number;
    for (const [x, y] of ring) {
      const bout = { x: x - (d.x / h) * longueur, y: y - (d.y / h) * longueur, z: 0 };
      expect(Math.max(Math.abs(bout.x - s.position.x), Math.abs(bout.y - s.position.y))).toBeLessThanOrEqual(demiPlan); // sur le sol
      const v = { x: bout.x - l.target.position.x, y: bout.y - l.target.position.y, z: bout.z - l.target.position.z };
      const p = (v.x * d.x + v.y * d.y + v.z * d.z) / n;
      expect(Math.hypot(v.x - (p * d.x) / n, v.y - (p * d.y) / n, v.z - (p * d.z) / n)).toBeLessThanOrEqual(right); // dans le cadre d'ombre
    }
    poignee.destroy();
    carteFactice.cartes.length = 0;
    const standard = await demarrer();
    standard.carte.fire('load');
    soleilDessine(standard.carte);
    let solStandard = false;
    (carteFactice.rendus.at(-1) as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => { if (o.name === 'sol-ombre-client') solStandard = true; });
    expect(solStandard).toBe(false);
  });

  it('B4 — scène de confiance RÉELLE (obstacle + voisins + teinte) : aucun objet porteur de texte, aucune commande, aucun montant', async () => {
    const [lngC, latC] = at(0, 0);
    const layout = layoutOf(rawZone({ obstacles: [{ centerLng: lngC, centerLat: latC + 0.0001, lengthM: 4, widthM: 1 }], geometry: { ...(rawZone().geometry as object), count: 35, panels: RANGEES_PLAT } }));
    const payload = { visionneuse_soleil: { version: 1, zones: [{ index: 0, id: 'zone-1', acces: RANGEES_PLAT.map(() => 0.9) }], instant_choisi: { jour: 356, heure: 16.25 },
      environnement: [{ kind: 'arbre', centerLng: lngC, centerLat: latC - 0.0002, heightM: 7.5, crownDiameterM: 5, evergreen: true }, { kind: 'batiment', centerLng: lngC + 0.0002, centerLat: latC, heightM: 9, lengthM: 8, widthM: 6 }] } };
    const soleil = lireVisionneuseSoleil(payload, layout)!;
    expect(soleil.environnement).toHaveLength(2);
    // Témoin : le détecteur de texte peint fonctionne.
    (document.createElement('canvas').getContext('2d') as CanvasRenderingContext2D).fillText('témoin', 0, 0);
    expect(textesPeints.splice(0)).toEqual(['témoin']);
    const { bootViewerFull } = await import('../src/scripts/roofPro11/viewerFullBoot');
    document.body.innerHTML = '<section id="roof3d"><div id="roof3d-stage"></div></section>';
    const poignee = bootViewerFull(document.getElementById('roof3d-stage'), layout, { maptilerKey: 'cle-test', instant: soleil.ouverture, environnement: soleil.environnement, indexTeintes: [0], presentationClient: true })!;
    const carte = carteFactice.cartes[0];
    carte.fire('load');
    poignee.teinter(couleurParPanneau(soleil, poignee.indexActif)!);
    for (let h = 8; h <= 16; h++) poignee.poserInstant(soleil.ouverture.jour, h);
    soleilDessine(carte);
    const porteurs: string[] = [];
    let arbre = false;
    let obstacle: Record<string, any> | null = null;
    (carteFactice.rendus.at(-1) as { traverse: (f: (o: Record<string, any>) => void) => void }).traverse((o) => {
      if (o.isSprite || o.isCSS2DObject || o.isCSS3DObject || o.element instanceof HTMLElement) porteurs.push(o.type);
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      for (const m of mats) if (m.isSpriteMaterial) porteurs.push('SpriteMaterial');
      if (o.geometry?.type === 'CylinderGeometry') arbre = true;
      if (o.isMesh && !o.isInstancedMesh && o.material?.color?.getHex?.() === TEINTES_PRESENTATION.cheminee) obstacle = o;
    });
    expect(arbre).toBe(true); // la scène construite porte bien les voisins
    expect(obstacle).not.toBeNull(); // et l'obstacle de 4 m, en brique (habit client)
    expect(porteurs).toEqual([]); // ni sprite (cote, numéro, poignée), ni surimpression HTML
    expect(textesPeints).toEqual([]); // aucun texte peint dans un canevas (étiquette en texture)
    // La page : rien de monté par la scène (contrôle de numérotation, note de pas inter-rangées), aucun champ, aucun montant.
    expect(document.getElementById('rp11-numerotation')).toBeNull();
    expect(document.getElementById('rp9-row-pitch')).toBeNull();
    expect(document.querySelector('input, select, textarea, button, [contenteditable]')).toBeNull();
    expect(document.body.textContent ?? '').toBe('');
  });

  it('les obstacles portent et reçoivent les ombres sur le lien de confiance ; lien standard : sans ombre, comme avant', async () => {
    const [lngC, latC] = at(0, 0);
    const layout = layoutOf(rawZone({ obstacles: [{ centerLng: lngC, centerLat: latC + 0.0001, lengthM: 4, widthM: 1 }], geometry: { ...(rawZone().geometry as object), count: 35, panels: RANGEES_PLAT } }));
    const { bootViewerFull } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const ombresObstacle = (opts: Record<string, unknown>, teinte: number) => {
      carteFactice.cartes.length = 0;
      const el = document.body.appendChild(document.createElement('div'));
      const p = bootViewerFull(el, layout, { maptilerKey: 'cle-test', instant: INSTANT_REEL, ...opts })!;
      carteFactice.cartes[0].fire('load');
      soleilDessine(carteFactice.cartes[0]);
      let o: Record<string, any> | null = null;
      (carteFactice.rendus.at(-1) as { traverse: (f: (x: Record<string, any>) => void) => void }).traverse((x) => { if (x.isMesh && !x.isInstancedMesh && x.material?.color?.getHex?.() === teinte) o = x; });
      p.destroy();
      const m = o as unknown as Record<string, any>;
      return [m.castShadow, m.receiveShadow];
    };
    expect(ombresObstacle({ presentationClient: true }, TEINTES_PRESENTATION.cheminee)).toEqual([true, true]);
    expect(ombresObstacle({}, 0xff6b6b)).toEqual([false, false]);
  });

  /** Démarre avec un token Mapbox et compte les demandes de la photo du toit ; `images` = les <img> demandées. */
  async function photoDuToit() {
    const images: HTMLImageElement[] = [];
    const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')!;
    vi.spyOn(HTMLImageElement.prototype, 'src', 'set').mockImplementation(function (this: HTMLImageElement, v: string) {
      if (v.includes('api.mapbox.com')) images.push(this);
      desc.set!.call(this, v);
    });
    const d = await demarrer({ mapboxToken: 'pk.test' });
    d.carte.fire('load');
    const dixPas = () => { for (let h = 7; h < 17; h++) d.poignee.poserInstant(INSTANT_REEL.jour, h); };
    return { ...d, images, dixPas };
  }

  it('photo du toit réussie : UNE demande sur dix pas de soleil', async () => {
    const { images, dixPas } = await photoDuToit();
    images[0].onload?.(new Event('load'));
    dixPas();
    expect(images).toHaveLength(1);
  });

  it('photo refusée une fois (429) : redemandée plus tard, pas à chaque pas ; réussie ensuite, plus rien', async () => {
    vi.useFakeTimers();
    try {
      const { images, dixPas } = await photoDuToit();
      images[0].onerror?.(new Event('error'));
      dixPas();
      expect(images).toHaveLength(1); // aucun pas ne relance
      vi.advanceTimersByTime(DELAIS_RELANCE_PHOTO_MS[0]);
      expect(images).toHaveLength(2); // un second essai, après le délai
      images[1].onload?.(new Event('load'));
      dixPas();
      vi.advanceTimersByTime(60_000);
      expect(images).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('photo toujours refusée : essais plafonnés, puis plus jamais', async () => {
    vi.useFakeTimers();
    try {
      const { images, dixPas } = await photoDuToit();
      for (let i = 0; i < 10; i++) {
        images.at(-1)!.onerror?.(new Event('error'));
        dixPas();
        vi.advanceTimersByTime(60_000);
      }
      expect(images).toHaveLength(ESSAIS_PHOTO_MAX);
    } finally {
      vi.useRealTimers();
    }
  });
});

// ── 9. Aucune commande morte : la barre n'apparaît qu'une fois la scène VRAIMENT rendue (lot 8) ──

describe('monterVisionneusePleine — barre au soleil branchée après le rendu, repli si la scène jette', () => {
  const BARRE = `<div id="roof3d-soleil" hidden><div data-soleil-legende></div>
    <button data-soleil-lecture disabled></button><strong data-soleil-quand></strong><p data-soleil-journee></p>
    <input type="range" data-soleil-heure disabled /><button data-soleil-saison="hiver" disabled></button><button data-soleil-saison="ete" disabled></button></div>`;
  // L'aide des gestes de la page (#roof3d-hint), telle que la visionneuse simplifiée la sert.
  const AIDE_SIMPLE = { fr: 'Faites glisser pour tourner', en: 'Drag to rotate', ar: 'اسحبوا للتدوير' };
  const AIDE = `<p id="aide" hidden data-i18n data-fr="${AIDE_SIMPLE.fr}" data-en="${AIDE_SIMPLE.en}" data-ar="${AIDE_SIMPLE.ar}">${AIDE_SIMPLE.fr}</p>`;
  const PAYLOAD_REEL = { visionneuse_soleil: { version: 1, zones: [], environnement: [], instant_choisi: { jour: 356, heure: 16.25 } } };
  const getContextOrigine = HTMLCanvasElement.prototype.getContext;
  beforeEach(() => {
    carteFactice.cartes.length = 0;
    carteFactice.rendus.length = 0;
    textesPeints.length = 0;
    const c2d = contexte2dFactice();
    (HTMLCanvasElement.prototype as unknown as { getContext: () => unknown }).getContext = () => c2d;
  });
  afterEach(() => {
    HTMLCanvasElement.prototype.getContext = getContextOrigine;
    vi.restoreAllMocks();
    document.body.innerHTML = '';
  });

  async function monter(extra: Record<string, unknown> = {}) {
    const { monterVisionneusePleine } = await import('../src/scripts/roofPro11/viewerFullBoot');
    document.body.innerHTML = `<div id="scene" class="roof3d-stage"></div>${BARRE}${AIDE}`;
    const barre = document.getElementById('roof3d-soleil')!;
    const soleil = lireVisionneuseSoleil(PAYLOAD_REEL, LAYOUT_PLAT_35)!;
    const onReady = vi.fn();
    const replier = vi.fn();
    const avertir = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const brancherSoleil = vi.fn(async (poignee: ViewerFullHandle) =>
      attacherSoleil({ barre, poignee, soleil, layout: LAYOUT_PLAT_35, avecTeinte: true, reducedMotion: true }));
    const vue = monterVisionneusePleine(document.getElementById('scene'), LAYOUT_PLAT_35, { maptilerKey: 'cle-test', reducedMotion: true, instant: soleil.ouverture, onReady, ...extra }, { barre, brancherSoleil, replier, scene: document.getElementById('scene'), aide: document.getElementById('aide') });
    const q = <T extends HTMLElement>(s: string) => barre.querySelector<T>(s)!;
    const scene = document.getElementById('scene')!;
    const aide = document.getElementById('aide')!;
    return { vue, barre, carte: carteFactice.cartes[0], onReady, replier, brancherSoleil, avertir, q, scene, aide };
  }
  const attendre = () => new Promise((r) => setTimeout(r, 0));

  it('scène rendue → barre montrée ; « lecture » fait un pas qui DÉPLACE la lumière, libellé en heure solaire', async () => {
    const { vue, barre, carte, onReady, replier, brancherSoleil, q } = await monter();
    expect(vue).not.toBeNull();
    expect(barre.hidden).toBe(true);
    expect(brancherSoleil).not.toHaveBeenCalled(); // rien de branché avant le premier rendu
    carte.fire('load');
    await attendre();
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(barre.hidden).toBe(false);
    expect(replier).not.toHaveBeenCalled();
    expect(q('[data-soleil-quand]').textContent).toBe('21 décembre · 16 h (heure solaire)');
    const avant = soleilDessine(carte)!;
    const repeints = carte.repeints;
    q<HTMLButtonElement>('[data-soleil-lecture]').click(); // reduced-motion : UN pas (16 h 15 → lever, après le coucher de 17 h)
    expect(carte.repeints).toBeGreaterThan(repeints);
    expect(q('[data-soleil-quand]').textContent).toMatch(/^21 décembre · [0-9]+ h \(heure solaire\)$/);
    const apres = soleilDessine(carte)!;
    expect(Math.hypot(apres.x - avant.x, apres.y - avant.y, apres.z - avant.z)).toBeGreaterThan(1);
    vue!.dispose();
    expect(barre.hidden).toBe(true);
  });

  it('le premier rendu jette → barre jamais montrée, carte démontée, repli monté, un seul avertissement', async () => {
    const { barre, carte, onReady, replier, brancherSoleil, avertir } = await monter();
    carte.getZoom = () => { throw new Error('rendu impossible'); }; // lu par buildZoneMeshes, au cœur du rendu
    expect(() => carte.fire('load')).not.toThrow();
    await attendre();
    expect(onReady).not.toHaveBeenCalled();
    expect(brancherSoleil).not.toHaveBeenCalled();
    expect(barre.hidden).toBe(true);
    expect(carte.retiree).toBe(true);
    expect(replier).toHaveBeenCalledTimes(1);
    expect(avertir).toHaveBeenCalledTimes(1);
  });

  it('un pas de soleil qui jette après coup → barre débranchée et cachée, cadre et aide rendus au repli', async () => {
    const { barre, carte, replier, q, scene, aide } = await monter();
    carte.fire('load');
    await attendre();
    expect(barre.hidden).toBe(false);
    // Habillé pour la carte au rendu : cadre « carte » (un doigt fait défiler la page) et aide des gestes carte.
    expect(scene.classList.contains('roof3d-stage--map')).toBe(true);
    expect(aide.hidden).toBe(false);
    expect(aide.dataset.fr).toMatch(/^Deux doigts/);
    carte.triggerRepaint = () => { throw new Error('rendu impossible'); }; // appelé par le pas de soleil (B3 : soleil seul)
    const curseur = q<HTMLInputElement>('[data-soleil-heure]');
    curseur.value = '10';
    curseur.dispatchEvent(new Event('input'));
    expect(barre.hidden).toBe(true);
    expect(curseur.disabled).toBe(true);
    expect(carte.retiree).toBe(true);
    expect(replier).toHaveBeenCalledTimes(1);
    // Le repli (visionneuse simplifiée) retrouve SON cadre et SON aide.
    expect(scene.classList.contains('roof3d-stage--map')).toBe(false);
    expect(scene.classList.contains('roof3d-stage--sky')).toBe(false);
    expect(scene.classList.contains('roof3d-stage')).toBe(true);
    expect(aide.hidden).toBe(true);
    expect([aide.dataset.fr, aide.dataset.en, aide.dataset.ar, aide.textContent]).toEqual([AIDE_SIMPLE.fr, AIDE_SIMPLE.en, AIDE_SIMPLE.ar, AIDE_SIMPLE.fr]);
  });

  it('B0 — une tuile refusée (429) ou une réponse HTTP ne retire pas la barre ; une panne de style, si (repli, carte démontée)', async () => {
    const onMapError = vi.fn();
    const { barre, carte, replier } = await monter({ onMapError });
    carte.fire('load');
    await attendre();
    carte.fire('error', { sourceId: 'satellite', tile: {}, error: { status: 429, message: 'Too Many Requests' } });
    carte.fire('error', { error: { status: 404, message: 'glyphes absents' } });
    expect(replier).not.toHaveBeenCalled();
    expect(barre.hidden).toBe(false);
    carte.fire('error', { error: new Error('Style is not done loading') });
    expect(replier).toHaveBeenCalledTimes(1);
    expect(barre.hidden).toBe(true);
    expect(carte.retiree).toBe(true); // plus de carte devant la photo ou la visionneuse simplifiée
    expect(onMapError).not.toHaveBeenCalled(); // avec onFail, la panne passe par le repli
  });

  it('B0 — contexte WebGL perdu puis restauré : la couche 3D est reposée UNE fois et la scène rejouée au même instant', async () => {
    vi.useFakeTimers();
    try {
      const { DELAI_RESTAURATION_GL_MS } = await import('../src/scripts/roofPro11/viewerFullBoot');
      const { carte, replier, barre, q } = await monter();
      carte.fire('load');
      await vi.advanceTimersByTimeAsync(1);
      const curseur = q<HTMLInputElement>('[data-soleil-heure]');
      curseur.value = '10';
      curseur.dispatchEvent(new Event('input'));
      const soleilAvant = soleilDessine(carte);
      expect(carte.ajouts).toBe(1);
      carte.perdreContexte(); // MapLibre détruit le style, couche 3D comprise
      expect(carte.couches).toHaveLength(0);
      carte.fire('webglcontextrestored'); // le style revient… plus tard
      expect(carte.ajouts).toBe(1);
      const repeints = carte.repeints;
      carte.styleCharge = true;
      carte.fire('style.load');
      expect(carte.ajouts).toBe(2); // reposée une fois
      expect(carte.couches).toHaveLength(1);
      expect(carte.repeints).toBeGreaterThan(repeints);
      expect(soleilDessine(carte)).toEqual(soleilAvant); // même instant (10 h) qu'avant la perte
      vi.advanceTimersByTime(DELAI_RESTAURATION_GL_MS * 3);
      expect(replier).not.toHaveBeenCalled();
      expect(barre.hidden).toBe(false);
      expect(carte.retiree).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('B0 — contexte restauré mais couche non reposée, style jamais revenu, ou contexte jamais restauré : repli, une fois', async () => {
    vi.useFakeTimers();
    try {
      const { DELAI_RESTAURATION_GL_MS } = await import('../src/scripts/roofPro11/viewerFullBoot');
      // a) la couche refuse de revenir
      const a = await monter();
      a.carte.fire('load');
      a.carte.perdreContexte();
      a.carte.addLayer = function () { this.ajouts++; return this; }; // ne pose rien
      a.carte.styleCharge = true;
      a.carte.fire('webglcontextrestored');
      expect(a.replier).toHaveBeenCalledTimes(1);
      expect(a.carte.retiree).toBe(true);
      expect(a.barre.hidden).toBe(true);
      vi.advanceTimersByTime(DELAI_RESTAURATION_GL_MS * 3);
      expect(a.replier).toHaveBeenCalledTimes(1);
      // b) le style ne revient jamais après la restauration
      carteFactice.cartes.length = 0;
      const b = await monter();
      b.carte.fire('load');
      b.carte.perdreContexte();
      b.carte.fire('webglcontextrestored');
      vi.advanceTimersByTime(DELAI_RESTAURATION_GL_MS + 1);
      expect(b.replier).toHaveBeenCalledTimes(1);
      expect(b.carte.retiree).toBe(true);
      // c) le contexte n'est jamais restauré
      carteFactice.cartes.length = 0;
      const c = await monter();
      c.carte.fire('load');
      c.carte.perdreContexte();
      vi.advanceTimersByTime(DELAI_RESTAURATION_GL_MS + 1);
      expect(c.replier).toHaveBeenCalledTimes(1);
      expect(c.carte.retiree).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('style de carte refusé (403) avant le chargement : repli IMMÉDIAT, carte démontée, barre jamais montrée, aucun rendu', async () => {
    const { erreurDeStyle } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const { barre, carte, replier, onReady, brancherSoleil, scene } = await monter();
    const style = (carte.options as { style: unknown }).style as string;
    expect(typeof style).toBe('string'); // clé MapTiler seule : le style est une adresse
    // Une tuile refusée avant le chargement n'est pas un refus de style : on attend encore.
    carte.fire('error', { sourceId: 'satellite', tile: {}, error: { status: 403, url: 'https://tuiles/1/2/3.jpg' } });
    expect(replier).not.toHaveBeenCalled();
    expect(erreurDeStyle({ error: { status: 403, url: style } }, style)).toBe(true);
    carte.fire('error', { error: { status: 403, message: 'Forbidden', url: style } });
    await attendre();
    expect(replier).toHaveBeenCalledTimes(1);
    expect(carte.retiree).toBe(true); // la boîte sombre de la carte quitte la scène : la photo ou la simplifiée se voient
    expect(onReady).not.toHaveBeenCalled();
    expect(brancherSoleil).not.toHaveBeenCalled();
    expect(barre.hidden).toBe(true);
    expect(scene.classList.contains('roof3d-stage--map')).toBe(false);
    carte.fire('load'); // une carte démontée ne rend plus rien
    expect(onReady).not.toHaveBeenCalled();
  });

  it('carte LENTE dont le style est arrivé : aucun repli au délai, la visionneuse pleine et la barre arrivent avec `load` (40 s)', async () => {
    vi.useFakeTimers();
    try {
      const { barre, carte, replier, onReady } = await monter({ loadTimeoutMs: 15_000 });
      carte.fire('styledata'); // le style est là ; les tuiles satellite traînent
      await vi.advanceTimersByTimeAsync(40_000);
      expect(replier).not.toHaveBeenCalled();
      expect(carte.retiree).toBe(false);
      carte.fire('load');
      await vi.advanceTimersByTimeAsync(1);
      expect(onReady).toHaveBeenCalledTimes(1);
      expect(barre.hidden).toBe(false);
      expect(replier).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('carte qui ne charge JAMAIS : au délai, repli (plus d’attente devant une boîte vide)', async () => {
    vi.useFakeTimers();
    try {
      const { barre, carte, replier, onReady } = await monter({ loadTimeoutMs: 15_000 });
      vi.advanceTimersByTime(14_999);
      expect(replier).not.toHaveBeenCalled();
      vi.advanceTimersByTime(2);
      expect(replier).toHaveBeenCalledTimes(1);
      expect(carte.retiree).toBe(true);
      expect(onReady).not.toHaveBeenCalled();
      expect(barre.hidden).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});

// ── 10. L'aide des gestes suit la langue de la page (lot 8) ──
// La page pose dans chaque nœud `data-i18n` trois portées fr / en / ar (son `prepareI18n`) puis son sélecteur ne fait que
// les montrer ou les cacher (`applyLang`). Ces deux fonctions vivent dans le script de la page : le fixture reproduit le
// DOM EXACT qu'elles produisent, et `habillerPourCarte` (la vraie) est jouée dessus.
describe('habillerPourCarte — l’aide des gestes suit la langue de la page, et revient telle quelle au repli', () => {
  const SIMPLE = { fr: 'Faites glisser pour tourner', en: 'Drag to rotate', ar: 'اسحبوا للتدوير' };
  const CARTE = { fr: /^Deux doigts/, en: /^Two fingers/, ar: /^إصبعان/ };
  /** Le nœud tel que `prepareI18n` le laisse, puis `applyLang(langue)`. */
  function aidePreparee(langue: 'fr' | 'en' | 'ar') {
    document.body.innerHTML = `<div id="scene"></div><p id="aide" hidden data-i18n data-fr="${SIMPLE.fr}" data-en="${SIMPLE.en}" data-ar="${SIMPLE.ar}"></p>`;
    const aide = document.getElementById('aide')!;
    const portees = (['fr', 'en', 'ar'] as const).map((l) => Object.assign(document.createElement('span'), { textContent: SIMPLE[l] }));
    aide.append(...portees);
    const appliquer = (l: 'fr' | 'en' | 'ar') => {
      portees.forEach((p, i) => { p.hidden = ['fr', 'en', 'ar'][i] !== l; });
      document.documentElement.lang = l;
    };
    appliquer(langue);
    const visible = () => portees.find((p) => !p.hidden)!.textContent;
    return { aide, portees, appliquer, visible, scene: document.getElementById('scene')! };
  }
  afterEach(() => {
    document.documentElement.lang = 'fr';
    document.body.innerHTML = '';
  });

  it.each(['fr', 'en', 'ar'] as const)('page en %s : l’aide carte est dans cette langue, puis suit chaque bascule', async (langue) => {
    const { habillerPourCarte } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const { aide, portees, appliquer, visible, scene } = aidePreparee(langue);
    habillerPourCarte(scene, aide);
    expect(aide.hidden).toBe(false);
    expect(visible()).toMatch(CARTE[langue]);
    expect([...aide.children]).toEqual(portees); // les MÊMES portées : le sélecteur les tient toujours
    for (const l of ['ar', 'en', 'fr'] as const) {
      appliquer(l);
      expect(visible()).toMatch(CARTE[l]);
    }
    expect(aide.dataset.en).toMatch(CARTE.en);
  });

  it('repli : l’aide simplifiée revient dans ses trois portées, et suit encore les bascules', async () => {
    const { habillerPourCarte } = await import('../src/scripts/roofPro11/viewerFullBoot');
    const { aide, portees, appliquer, visible, scene } = aidePreparee('ar');
    const defaire = habillerPourCarte(scene, aide);
    appliquer('en');
    defaire();
    expect(aide.hidden).toBe(true);
    expect([...aide.children]).toEqual(portees);
    expect(portees.map((p) => p.textContent)).toEqual([SIMPLE.fr, SIMPLE.en, SIMPLE.ar]);
    expect([aide.dataset.fr, aide.dataset.en, aide.dataset.ar]).toEqual([SIMPLE.fr, SIMPLE.en, SIMPLE.ar]);
    expect(visible()).toBe(SIMPLE.en);
    appliquer('ar');
    expect(visible()).toBe(SIMPLE.ar);
  });

  it('nœud non préparé : le texte de la langue de la page, et le texte d’origine au repli', async () => {
    const { habillerPourCarte } = await import('../src/scripts/roofPro11/viewerFullBoot');
    document.body.innerHTML = `<div id="scene"></div><p id="aide" hidden data-fr="${SIMPLE.fr}">${SIMPLE.fr}</p>`;
    document.documentElement.lang = 'ar';
    const aide = document.getElementById('aide')!;
    const defaire = habillerPourCarte(document.getElementById('scene'), aide);
    expect(aide.textContent).toMatch(CARTE.ar);
    defaire();
    expect(aide.textContent).toBe(SIMPLE.fr);
    expect(aide.dataset.en).toBeUndefined();
  });
});
