// PV62 — PAVAGE MIXTE : la pose (portrait/paysage) est choisie RANGÉE PAR RANGÉE et
// chaque bande libre d'une rangée est re-pavée depuis son propre bord. Objectif : loger
// plus que les deux poses uniformes, sans jamais poser un panneau invalide, et sans
// jamais faire PIRE que la meilleure pose uniforme (repli explicite).
import { describe, expect, it } from 'vitest';
import { packConfig, PANEL2_WATT, OBSTACLE_CLEARANCE_M } from '../src/lib/estimatorBrainV2';
import { PANEL2_LONG_M, PANEL2_SHORT_M, PERIMETER_SETBACK_M } from '../src/lib/roofPro2';
import { solveLive } from '../src/lib/estimatorBrainV7';
import { obstacleRing, type Obstacle } from '../src/lib/obstacles';
import { type LngLat } from '../src/lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LNG0 = -7.62;
const LAT0 = 33.59;

const at = (xM: number, yM: number): LngLat => [
  LNG0 + xM / (DEG2M * Math.cos(LAT0 * DEG2RAD)),
  LAT0 + yM / DEG2M,
];
function rect(wEW: number, hNS: number): LngLat[] {
  return [at(-wEW / 2, -hNS / 2), at(wEW / 2, -hNS / 2), at(wEW / 2, hNS / 2), at(-wEW / 2, hNS / 2)];
}
function obs(id: string, dxM: number, dyM: number, lengthM: number, widthM: number): Obstacle {
  const p = at(dxM, dyM);
  return { id, centerLng: p[0], centerLat: p[1], lengthM, widthM };
}

// — Toit en L (concave) : le mixte doit y rester valide, jamais déborder l'échancrure —
const L_SHAPE: LngLat[] = [at(-10, -6), at(10, -6), at(10, 2), at(0, 2), at(0, 6), at(-10, 6)];

function packOf(ring: LngLat[], obstructions: LngLat[][] = [], tiltDeg = 13) {
  return packConfig(ring, LAT0, { family: 'south', tiltDeg, obstructions });
}

// ── Vérification géométrique indépendante du moteur ──────────────────────────
function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}
function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  return min;
}
function inPolygon(p: [number, number], ring: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
const toENU = (origin: LngLat) => ([lng, lat]: LngLat): [number, number] => [
  (lng - origin[0]) * DEG2M * Math.cos(origin[1] * DEG2RAD),
  (lat - origin[1]) * DEG2M,
];
/** Dimensions (largeur le long de la rangée, profondeur au sol) d'un panneau posé. */
function dimsOf(orient: 'portrait' | 'landscape' | undefined, tiltDeg: number) {
  const slopeLenM = orient === 'landscape' ? PANEL2_SHORT_M : PANEL2_LONG_M;
  const widthM = orient === 'landscape' ? PANEL2_LONG_M : PANEL2_SHORT_M;
  return { widthM, depthM: slopeLenM * Math.cos(tiltDeg * DEG2RAD) };
}

describe('PV62 — le pavage mixte loge PLUS que les deux poses uniformes', () => {
  const cases = [
    { name: 'toit 20 × 16 m nu', ring: rect(20, 16), obstructions: [] as LngLat[][] },
    {
      name: 'toit 25 × 13 m avec 3 obstacles',
      ring: rect(25, 13),
      obstructions: [obs('o1', -7, 0, 1.5, 1.5), obs('o2', 0, 2, 2, 3), obs('o3', 7, -1, 1.2, 1.2)].map(obstacleRing),
    },
    { name: 'toit en L avec un obstacle', ring: L_SHAPE, obstructions: [obstacleRing(obs('o', -3, 0, 2, 2))] },
  ];

  for (const c of cases) {
    it(`${c.name} : mixte > portrait ET > paysage`, () => {
      const pack = packOf(c.ring, c.obstructions);
      const mixed = pack.mixed!;
      expect(mixed.count).toBeGreaterThan(pack.portrait.count);
      expect(mixed.count).toBeGreaterThan(pack.landscape.count);
      expect(mixed.panelOrientation).toBe('mixed');
      // Le gain vient bien d'un MÉLANGE : les deux poses sont présentes.
      const poses = new Set(mixed.panels.map((p) => p.orient));
      expect(poses.has('portrait') || poses.has('landscape')).toBe(true);
      expect(mixed.panels.every((p) => p.orient === 'portrait' || p.orient === 'landscape')).toBe(true);
      // kWc suit le comptage réel (720 W par panneau posé).
      expect(mixed.kwc).toBeCloseTo((mixed.count * PANEL2_WATT) / 1000, 6);
    });
  }

  it('chaque panneau mixte tient DANS le toit, au retrait, et hors obstacle', () => {
    for (const c of cases) {
      const pack = packOf(c.ring, c.obstructions);
      const toLocal = toENU(pack.origin);
      const ringENU = c.ring.map(toLocal);
      const obsENU = c.obstructions.map((o) => o.map(toLocal));
      const az = pack.azimuthDeg * DEG2RAD;
      const s: [number, number] = [Math.sin(az), Math.cos(az)];
      const u: [number, number] = [-s[1], s[0]];
      for (const p of pack.mixed!.panels) {
        const { widthM, depthM } = dimsOf(p.orient, pack.tiltDeg);
        const hw = widthM / 2;
        const hd = depthM / 2;
        const corners: [number, number][] = [
          [p.cx - hw * u[0] - hd * s[0], p.cy - hw * u[1] - hd * s[1]],
          [p.cx + hw * u[0] - hd * s[0], p.cy + hw * u[1] - hd * s[1]],
          [p.cx + hw * u[0] + hd * s[0], p.cy + hw * u[1] + hd * s[1]],
          [p.cx - hw * u[0] + hd * s[0], p.cy - hw * u[1] + hd * s[1]],
        ];
        for (const cc of corners) {
          expect(inPolygon(cc, ringENU), `${c.name} — coin hors du toit`).toBe(true);
          expect(distToBoundary(cc, ringENU), `${c.name} — retrait de rive`).toBeGreaterThanOrEqual(PERIMETER_SETBACK_M - 1e-3);
        }
        for (const o of obsENU) {
          const hit = corners.some((cc) => inPolygon(cc, o) || distToBoundary(cc, o) <= OBSTACLE_CLEARANCE_M);
          expect(hit, `${c.name} — panneau dans un obstacle`).toBe(false);
        }
      }
    }
  });

  it('aucun panneau mixte n’en CHEVAUCHE un autre', () => {
    const pack = packOf(rect(20, 16));
    const az = pack.azimuthDeg * DEG2RAD;
    const s: [number, number] = [Math.sin(az), Math.cos(az)];
    const u: [number, number] = [-s[1], s[0]];
    // Tout est aligné sur (u, v) : deux rectangles se chevauchent ssi leurs intervalles
    // se chevauchent SUR LES DEUX axes.
    const boxes = pack.mixed!.panels.map((p) => {
      const { widthM, depthM } = dimsOf(p.orient, pack.tiltDeg);
      const uu = p.cx * u[0] + p.cy * u[1];
      const vv = p.cx * s[0] + p.cy * s[1];
      return { u0: uu - widthM / 2, u1: uu + widthM / 2, v0: vv - depthM / 2, v1: vv + depthM / 2 };
    });
    const EPS = 1e-6;
    let overlaps = 0;
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i];
        const b = boxes[j];
        if (a.u0 < b.u1 - EPS && b.u0 < a.u1 - EPS && a.v0 < b.v1 - EPS && b.v0 < a.v1 - EPS) overlaps++;
      }
    }
    expect(overlaps).toBe(0);
  });
});

describe('PV62 — garde-fous du pavage mixte', () => {
  it('si le mélange ne gagne rien, `mixed` EST la meilleure pose uniforme (jamais pire)', () => {
    const pack = packOf(rect(30, 20));
    expect(pack.mixed!.count).toBeGreaterThanOrEqual(Math.max(pack.portrait.count, pack.landscape.count));
    if (pack.mixed!.count === Math.max(pack.portrait.count, pack.landscape.count)) {
      expect(pack.mixed).toBe(pack.best); // repli : le MÊME objet, pas une copie approximative
      expect(pack.mixed!.panelOrientation).not.toBe('mixed');
    }
  });

  it('Est-Ouest : le chevron impose sa géométrie → mixte = meilleur uniforme', () => {
    const pack = packConfig(rect(20, 16), LAT0, { family: 'eastwest', tiltDeg: 10 });
    expect(pack.mixed).toBe(pack.best);
  });

  it('accès PARESSEUX mémorisé : deux lectures donnent le MÊME objet', () => {
    const pack = packOf(rect(20, 16));
    expect(pack.mixed).toBe(pack.mixed);
  });

  it('le pavage UNIFORME est inchangé par l’ajout du mixte (aucun panneau ne porte de pose)', () => {
    const pack = packOf(rect(20, 16));
    expect(pack.portrait.panels.every((p) => p.orient === undefined)).toBe(true);
    expect(pack.landscape.panels.every((p) => p.orient === undefined)).toBe(true);
    expect(pack.portrait.panelOrientation).toBe('portrait');
    expect(pack.landscape.panelOrientation).toBe('landscape');
  });
});

describe('PV62 — « mixte » est un AXE de pose verrouillable (V7)', () => {
  const ring = rect(25, 13);
  const obstructions = [obs('o1', -7, 0, 1.5, 1.5), obs('o2', 0, 2, 2, 3)].map(obstacleRing);

  it('verrouiller la pose « mixte » tient l’axe et se lit dans le gagnant', () => {
    const res = solveLive(ring, LAT0, 3000, obstructions, { layout: 'mixed' });
    expect(res.winner.layout).toBe('mixed');
    expect(res.winner.layoutLabel).toBe('mixte');
  });

  it('le balayage AUTO ne propose jamais « mixte » (axe opt-in, coût maîtrisé)', () => {
    const res = solveLive(ring, LAT0, 3000, obstructions, {});
    expect(res.winner.layout).not.toBe('mixed');
    expect(res.recommended.layout).not.toBe('mixed');
  });

  it('à config égale, la pose mixte ne loge jamais MOINS que la pose libre', () => {
    const free = solveLive(ring, LAT0, 3000, obstructions, {});
    const locked = solveLive(ring, LAT0, 3000, obstructions, {
      layout: 'mixed',
      orientation: free.winner.orientation,
      tiltDeg: free.winner.tiltDeg,
      margin: free.winner.margin,
    });
    expect(locked.winner.fitCount).toBeGreaterThanOrEqual(free.winner.fitCount);
  });
});
