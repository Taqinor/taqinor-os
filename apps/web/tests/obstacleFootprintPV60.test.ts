// PV60 — le dégagement d'obstacle était testé au CENTRE du panneau seulement : un
// panneau dont la moitié mordait la cheminée était compté (comptes trop hauts en
// production). La règle est désormais l'EMPREINTE : les 4 coins du rectangle posé +
// son centre. `obstacleRule: 'center'` (LEGACY) n'existe que pour mesurer ici le diff
// de comptage AVANT/APRÈS sur des toits synthétiques.
import { describe, expect, it } from 'vitest';
import { packConfig, PANEL2_WATT, OBSTACLE_CLEARANCE_M } from '../src/lib/estimatorBrainV2';
import { packFlushPlane } from '../src/lib/estimatorBrainV3';
import { obstacleRing, type Obstacle } from '../src/lib/obstacles';
import { type LngLat } from '../src/lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;

/** Rectangle `wEW` m (est-ouest) × `hNS` m (nord-sud) centré sur (lng0, lat0). */
function rect(wEW: number, hNS: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const cosLat = Math.cos(lat0 * DEG2RAD);
  const dLng = wEW / 2 / (DEG2M * cosLat);
  const dLat = hNS / 2 / DEG2M;
  return [
    [lng0 - dLng, lat0 - dLat],
    [lng0 + dLng, lat0 - dLat],
    [lng0 + dLng, lat0 + dLat],
    [lng0 - dLng, lat0 + dLat],
  ];
}

/** Obstacle posé à `dx`/`dy` mètres du centre du toit. */
function obs(id: string, dxM: number, dyM: number, lengthM: number, widthM: number, lng0 = -7.62, lat0 = 33.59): Obstacle {
  const cosLat = Math.cos(lat0 * DEG2RAD);
  return {
    id,
    centerLng: lng0 + dxM / (DEG2M * cosLat),
    centerLat: lat0 + dyM / DEG2M,
    lengthM,
    widthM,
  };
}

interface Fixture {
  name: string;
  ring: LngLat[];
  obstacles: Obstacle[];
  tiltDeg: number;
}

// — 4 toits synthétiques, tous avec obstacles (le diff AVANT/APRÈS porte là-dessus) —
const FIXTURES: Fixture[] = [
  {
    name: 'Toit carré 20 m · cheminée 2 × 2 au centre',
    ring: rect(20, 20),
    obstacles: [obs('o1', 0, 0, 2, 2)],
    tiltDeg: 13,
  },
  {
    name: 'Toit 25 × 12 m · 3 édicules alignés',
    ring: rect(25, 12),
    obstacles: [obs('o1', -7, 0, 1.5, 1.5), obs('o2', 0, 1, 2, 3), obs('o3', 7, -1, 1.2, 1.2)],
    tiltDeg: 15,
  },
  {
    name: 'Toit carré 14 m · gros édicule 5 × 3 décentré',
    ring: rect(14, 14),
    obstacles: [obs('o1', 2, -2, 3, 5)],
    tiltDeg: 10,
  },
  {
    name: 'Toit 18 × 9 m · 2 ventilations + une antenne',
    ring: rect(18, 9),
    obstacles: [obs('o1', -4, 0, 1, 1), obs('o2', 1, 1.5, 0.8, 0.8), obs('o3', 5, -1, 0.6, 0.6)],
    tiltDeg: 13,
  },
];

const ringsOf = (f: Fixture): LngLat[][] => f.obstacles.map(obstacleRing);

function countFor(f: Fixture, obstacleRule: 'footprint' | 'center'): number {
  return packConfig(f.ring, 33.59, {
    family: 'south',
    tiltDeg: f.tiltDeg,
    obstructions: ringsOf(f),
    obstacleRule,
  }).best.count;
}

// ── Géométrie de vérification (indépendante du moteur) ────────────────────────
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

/** Les 4 coins ENU d'un panneau posé (centre + dimensions + azimut d'empilement). */
function panelCorners(
  center: { cx: number; cy: number },
  azimuthDeg: number,
  widthM: number,
  depthM: number,
): [number, number][] {
  const az = azimuthDeg * DEG2RAD;
  const s: [number, number] = [Math.sin(az), Math.cos(az)]; // sens d'empilement
  const u: [number, number] = [-s[1], s[0]]; // axe long de la rangée
  const hw = widthM / 2;
  const hd = depthM / 2;
  return [
    [center.cx - hw * u[0] - hd * s[0], center.cy - hw * u[1] - hd * s[1]],
    [center.cx + hw * u[0] - hd * s[0], center.cy + hw * u[1] - hd * s[1]],
    [center.cx + hw * u[0] + hd * s[0], center.cy + hw * u[1] + hd * s[1]],
    [center.cx - hw * u[0] + hd * s[0], center.cy - hw * u[1] + hd * s[1]],
  ];
}

/** Anneaux d'obstacle projetés en ENU autour de l'origine du pavage. */
function obstaclesENU(f: Fixture, origin: LngLat): [number, number][][] {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return ringsOf(f).map((r) => r.map(([lng, lat]) => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M] as [number, number]));
}

/** Nombre de panneaux dont l'EMPREINTE mord un obstacle (ou son dégagement). */
function violating(f: Fixture, rule: 'footprint' | 'center'): number {
  const pack = packConfig(f.ring, 33.59, { family: 'south', tiltDeg: f.tiltDeg, obstructions: ringsOf(f), obstacleRule: rule });
  const grid = pack.best;
  const depthM = grid.slopeLenM * Math.cos(pack.tiltDeg * DEG2RAD);
  const obsENU = obstaclesENU(f, pack.origin);
  let bad = 0;
  for (const p of grid.panels) {
    const corners = panelCorners(p, pack.azimuthDeg, grid.rowWidthM, depthM);
    const hit = obsENU.some((o) => corners.some((c) => inPolygon(c, o) || distToBoundary(c, o) <= OBSTACLE_CLEARANCE_M));
    if (hit) bad++;
  }
  return bad;
}

describe('PV60 — dégagement d’obstacle testé sur les 4 coins (empreinte), pas au centre', () => {
  it('DIFF AVANT/APRÈS : la règle empreinte ne compte JAMAIS plus que la règle centre', () => {
    const deltas = FIXTURES.map((f) => {
      const before = countFor(f, 'center'); // AVANT (règle historique : centre seul)
      const after = countFor(f, 'footprint'); // APRÈS (règle physique : empreinte)
      return { name: f.name, before, after, delta: after - before };
    });
    // Chaque toit : l'empreinte est strictement plus conservatrice (jamais plus de panneaux).
    for (const d of deltas) {
      expect(d.after, `${d.name} — après (${d.after}) doit rester ≤ avant (${d.before})`).toBeLessThanOrEqual(d.before);
      expect(d.before).toBeGreaterThan(0); // les fixtures logent bien des panneaux
    }
    // Sur l'ensemble des toits, le correctif RETIRE réellement des panneaux fantômes.
    const before = deltas.reduce((s, d) => s + d.before, 0);
    const after = deltas.reduce((s, d) => s + d.after, 0);
    expect(after).toBeLessThan(before);
    // Table du diff, lisible dans le rapport de test (jamais un chiffre inventé).
    // Mesuré au moment du correctif : 84→78, 51→44, 31→29, 28→24 — TOTAL 194→175 (−19,
    // soit −9,8 % de panneaux fantômes qui mordaient un obstacle). Les assertions
    // ci-dessus restent des INÉGALITÉS : la table ne fige aucun chiffre.
    console.log(
      'PV60 diff comptage (avant → après) :\n' +
        deltas.map((d) => `  ${d.name} : ${d.before} → ${d.after} (${d.delta})`).join('\n') +
        `\n  TOTAL : ${before} → ${after} (${after - before} panneaux, ${(((after - before) / before) * 100).toFixed(1)} %)`,
    );
  });

  it('règle empreinte : AUCUN panneau posé ne mord un obstacle ni son dégagement', () => {
    for (const f of FIXTURES) {
      expect(violating(f, 'footprint'), `${f.name} — panneaux en infraction`).toBe(0);
    }
  });

  it('règle centre (LEGACY) : au moins un panneau mordait bien un obstacle — c’était le bug', () => {
    const total = FIXTURES.reduce((s, f) => s + violating(f, 'center'), 0);
    expect(total).toBeGreaterThan(0);
  });

  it('la règle par DÉFAUT est l’empreinte (aucun appelant n’a à la demander)', () => {
    for (const f of FIXTURES) {
      const dflt = packConfig(f.ring, 33.59, { family: 'south', tiltDeg: f.tiltDeg, obstructions: ringsOf(f) }).best;
      const explicit = packConfig(f.ring, 33.59, {
        family: 'south',
        tiltDeg: f.tiltDeg,
        obstructions: ringsOf(f),
        obstacleRule: 'footprint',
      }).best;
      expect(dflt.count).toBe(explicit.count);
      expect(dflt.panels).toEqual(explicit.panels);
    }
  });

  it('sans obstacle, le comptage est INCHANGÉ (le correctif ne touche que les obstacles)', () => {
    for (const f of FIXTURES) {
      const a = packConfig(f.ring, 33.59, { family: 'south', tiltDeg: f.tiltDeg, obstacleRule: 'center' }).best.count;
      const b = packConfig(f.ring, 33.59, { family: 'south', tiltDeg: f.tiltDeg, obstacleRule: 'footprint' }).best.count;
      expect(b).toBe(a);
      expect(b).toBeGreaterThan(0);
    }
  });

  it('kWc suit le comptage corrigé (720 W par panneau posé)', () => {
    const f = FIXTURES[0];
    const pack = packConfig(f.ring, 33.59, { family: 'south', tiltDeg: f.tiltDeg, obstructions: ringsOf(f) });
    expect(pack.best.kwc).toBeCloseTo((pack.best.count * PANEL2_WATT) / 1000, 6);
  });

  it('toit en PENTE (pose affleurante V3) : même correction, comptage ≤ règle centre', () => {
    const ring = rect(16, 10);
    const obstructions = [obstacleRing(obs('c1', 0, 0, 1.6, 1.6)), obstacleRing(obs('c2', 5, 2, 1, 1))];
    const plane = { ring, pitchDeg: 25, facingAzimuthDeg: 180, obstructions };
    const before = packFlushPlane(plane, { obstacleRule: 'center' }).best.count;
    const after = packFlushPlane(plane, { obstacleRule: 'footprint' }).best.count;
    const dflt = packFlushPlane(plane).best.count;
    expect(before).toBeGreaterThan(0);
    expect(after).toBeLessThanOrEqual(before);
    expect(dflt).toBe(after); // défaut = empreinte
  });
});
