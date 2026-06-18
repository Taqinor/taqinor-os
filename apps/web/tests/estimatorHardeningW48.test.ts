// W48 — DURCISSEMENT des DEUX optimiseurs (toit plat V7 + toit en pente V8).
// Tests défensifs EXHAUSTIFS + property/fuzz : tracés dégénérés, obstacles couvrant
// tout, toit trop petit, plafond besoin 0/énorme, PVGIS NaN/Infinity/négatif/null,
// mapping de signe d'azimut PVGIS, bornes physiques toujours tenues (Σ empreintes ≤
// surface utile ; posé = min(besoin, ce qui tient) ≤ besoin ; E-O ≥ sud même
// inclinaison ; économies ≤ coût énergie évitable ; surplus non rémunéré), verrous
// cumulés en profondeur sous ordres fuzzés, invariants pente (pas d'axe inclinaison,
// orientation = alignée toit, coplanaire). Le but : aucun crash, jamais NaN/Infinity/
// négatif, repli gracieux « estimé », et les invariants ne cassent JAMAIS.
import { describe, expect, it } from 'vitest';
import { solveLive, type AxisLocks, type LiveConfigEval } from '../src/lib/estimatorBrainV7';
import { solveLivePitched, type PitchedLocks } from '../src/lib/estimatorBrainV8';
import {
  packConfig,
  billMAD,
  tariffForCity,
  billToAnnualKwh,
  aspectForAzimuth,
} from '../src/lib/estimatorBrainV2';
import { type LngLat } from '../src/lib/roof';

const LAT = 33.59;

// ── Générateur pseudo-aléatoire déterministe (mulberry32) — fuzz reproductible. ──
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

/** Polygone à n sommets autour d'un centre, rayons aléatoires (peut être non convexe). */
function randomPolygon(r: () => number, n: number, maxRadiusM: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const mPerLat = 111320;
  const mPerLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const pts: LngLat[] = [];
  for (let i = 0; i < n; i++) {
    const ang = (i / n) * 2 * Math.PI + (r() - 0.5) * 0.6;
    const rad = maxRadiusM * (0.15 + 0.85 * r());
    pts.push([lng0 + (Math.cos(ang) * rad) / mPerLng, lat0 + (Math.sin(ang) * rad) / mPerLat]);
  }
  return pts;
}

const FINITE = (v: number) => Number.isFinite(v);
/** Toute config évaluée respecte les bornes de base (fini, ≥ 0, posé ≤ besoin/fit). */
function assertEvalSane(e: LiveConfigEval, effectiveNeed: number) {
  for (const v of [e.fitCount, e.placedCount, e.kwc, e.annualKwh, e.perPanelYield, e.savingsLow, e.savingsHigh, e.pctOfTarget]) {
    expect(FINITE(v)).toBe(true);
  }
  expect(e.placedCount).toBeGreaterThanOrEqual(0);
  expect(e.fitCount).toBeGreaterThanOrEqual(0);
  expect(Number.isInteger(e.placedCount)).toBe(true);
  expect(e.placedCount).toBeLessThanOrEqual(e.fitCount);
  if (effectiveNeed > 0) expect(e.placedCount).toBeLessThanOrEqual(effectiveNeed); // plafond besoin
  expect(e.kwc).toBeGreaterThanOrEqual(0);
  expect(e.annualKwh).toBeGreaterThanOrEqual(0);
  expect(e.savingsLow).toBeGreaterThanOrEqual(0);
  expect(e.savingsHigh).toBeGreaterThanOrEqual(e.savingsLow - 1e-6);
}

// ════════════════════════════ TOIT PLAT (V7) ════════════════════════════

describe('W48 (V7) — tracés/entrées dégénérés ne crashent jamais et ne rendent jamais NaN', () => {
  const cases: { label: string; ring: LngLat[]; bill: number; lat: number }[] = [
    { label: 'ring vide', ring: [], bill: 1500, lat: LAT },
    { label: 'ring 1 point', ring: [[-7.6, 33.5]], bill: 1500, lat: LAT },
    { label: 'ring 2 points', ring: [[-7.6, 33.5], [-7.6, 33.6]], bill: 1500, lat: LAT },
    { label: 'aire nulle (points confondus)', ring: [[-7.6, 33.5], [-7.6, 33.5], [-7.6, 33.5]], bill: 1500, lat: LAT },
    { label: 'colinéaire (sliver)', ring: [[-7.6, 33.5], [-7.59996, 33.5], [-7.59992, 33.5], [-7.6, 33.5]], bill: 1500, lat: LAT },
    // bowtie réaliste (~20 m) : auto-intersection, aire signée ~nulle, sans extent km.
    { label: 'bowtie (auto-intersection)', ring: [[-7.6, 33.5], [-7.5998, 33.50018], [-7.6, 33.50018], [-7.5998, 33.5]], bill: 1500, lat: LAT },
    { label: 'toit minuscule (< 1 panneau)', ring: squareRing(0.4), bill: 1500, lat: LAT },
    { label: 'facture NaN', ring: squareRing(16), bill: NaN, lat: LAT },
    { label: 'facture négative', ring: squareRing(16), bill: -800, lat: LAT },
    { label: 'facture Infinity', ring: squareRing(16), bill: Infinity, lat: LAT },
    { label: 'latitude NaN', ring: squareRing(16), bill: 1500, lat: NaN },
    { label: 'latitude hors plage (90)', ring: squareRing(16), bill: 1500, lat: 90 },
  ];
  for (const c of cases) {
    it(`${c.label} → résultat fini, sans exception`, () => {
      let res!: ReturnType<typeof solveLive>;
      expect(() => { res = solveLive(c.ring, c.lat, c.bill, [], {}); }).not.toThrow();
      assertEvalSane(res.winner, res.effectiveNeed);
      assertEvalSane(res.globalWinner, res.neededPanels);
      expect(FINITE(res.target)).toBe(true);
      expect(FINITE(res.neededPanels)).toBe(true);
    }, 30000);
  }

  it('obstacle couvrant TOUT le toit → 0 posé, 0 kWh, pas de crash', () => {
    const res = solveLive(squareRing(16), LAT, 1500, [squareRing(60)], {});
    expect(res.winner.placedCount).toBe(0);
    expect(res.winner.annualKwh).toBe(0);
  });

  it('plafond besoin 0 vs énorme : 0 = pas de verrou (dérivé facture) ; énorme = capé au fit', () => {
    const zero = solveLive(squareRing(16), LAT, 1500, [], { need: 0 });
    expect(zero.effectiveNeed).toBe(zero.neededPanels); // 0 → ignoré, cible = facture
    const huge = solveLive(squareRing(16), LAT, 1500, [], { need: 1e9 });
    expect(huge.winner.placedCount).toBe(huge.winner.fitCount); // capé à ce qui tient
    expect(huge.winner.placedCount).toBeLessThanOrEqual(1e9);
  });
});

describe('W48 (V7) — PVGIS adverse (NaN/Infinity/négatif/null/vide) → repli gracieux « estimé »', () => {
  const ring = squareRing(16);
  const adversarial: { label: string; fn: () => number | null }[] = [
    { label: 'NaN', fn: () => NaN },
    { label: 'Infinity', fn: () => Infinity },
    { label: '-Infinity', fn: () => -Infinity },
    { label: 'négatif', fn: () => -123 },
    { label: 'zéro', fn: () => 0 },
    { label: 'null', fn: () => null },
  ];
  for (const a of adversarial) {
    it(`yieldFn ${a.label} → source « estimate », production finie ≥ 0`, () => {
      const res = solveLive(ring, LAT, 1500, [], {}, { yieldFn: a.fn });
      expect(res.winner.yieldSource).toBe('estimate');
      assertEvalSane(res.winner, res.effectiveNeed);
      expect(res.winner.annualKwh).toBeGreaterThan(0); // la table donne un vrai chiffre
    });
  }

  it('yieldFn qui ALTERNE valide/NaN → jamais de NaN, gagnant cohérent', () => {
    let n = 0;
    const res = solveLive(ring, LAT, 1500, [], {}, { yieldFn: () => (n++ % 2 === 0 ? 1600 : NaN) });
    assertEvalSane(res.winner, res.effectiveNeed);
  });
});

describe('W48 (V7) — mapping de signe d\'azimut PVGIS correct dans les QUATRE quadrants', () => {
  it('Sud=0, Est=−90, Ouest=+90, Nord=180', () => {
    expect(aspectForAzimuth('south', 180)).toBe(0);
    expect(aspectForAzimuth('south', 90)).toBe(-90);
    expect(aspectForAzimuth('south', 270)).toBe(90);
    expect(aspectForAzimuth('south', 0)).toBe(-180);
    expect(aspectForAzimuth('south', 360)).toBe(180);
  });
  it('l\'aspect interrogé par le solveur suit l\'azimut de face réel (yieldFn enregistreur)', () => {
    const seen: number[] = [];
    solveLive(squareRing(16), LAT, 1500, [], { orientation: 'south' }, { yieldFn: (_t, a) => { seen.push(a); return 1600; } });
    expect(seen).toContain(0); // plein sud → aspect 0
  });
});

describe('W48 (V7) — PROPERTY/FUZZ : bornes physiques toujours tenues (toits + verrous + configs aléatoires)', () => {
  it('toits aléatoires × verrous aléatoires : fini, posé ≤ besoin, Σ empreintes ≤ surface utile, économies ≤ coût évitable', () => {
    const r = rng(0xC0FFEE);
    const orientations: (AxisLocks['orientation'] | undefined)[] = [undefined, 'south', 'eastwest', 'aligned'];
    const layouts: (AxisLocks['layout'] | undefined)[] = [undefined, 'portrait', 'landscape'];
    const margins: (AxisLocks['margin'] | undefined)[] = [undefined, 'keep', 'remove'];
    const tilts: (number | undefined)[] = [undefined, 0, 5, 15, 29, 35];
    for (let i = 0; i < 80; i++) {
      const n = 3 + Math.floor(r() * 6); // 3..8 sommets
      // rayon borné (≤ ~16 m) : couvre slivers→moyens toits sans pavages géants (perf).
      const ring = randomPolygon(r, n, 3 + r() * 13);
      const bill = r() < 0.1 ? 0 : Math.floor(r() * 6000);
      const nObs = Math.floor(r() * 3);
      const obstructions: LngLat[][] = [];
      for (let k = 0; k < nObs; k++) obstructions.push(randomPolygon(r, 4, 1 + r() * 8, -7.62 + (r() - 0.5) * 1e-4, 33.59 + (r() - 0.5) * 1e-4));
      const locks: AxisLocks = {
        orientation: orientations[Math.floor(r() * orientations.length)],
        layout: layouts[Math.floor(r() * layouts.length)],
        margin: margins[Math.floor(r() * margins.length)],
        tiltDeg: tilts[Math.floor(r() * tilts.length)],
        need: r() < 0.3 ? Math.floor(r() * 50) : undefined,
      };
      const res = solveLive(ring, LAT, bill, obstructions, locks);
      assertEvalSane(res.winner, res.effectiveNeed);

      // Σ empreintes panneaux POSÉS ≤ surface utile (re-pavage au même réglage).
      const w = res.winner;
      const pack = packConfig(ring, LAT, {
        family: w.family,
        tiltDeg: w.tiltDeg,
        azimuthDeg: w.azimuthDeg,
        obstructions,
        setbackM: w.margin === 'keep' ? undefined : 0,
      });
      const grid = w.layout === 'portrait' ? pack.portrait : pack.landscape;
      const footprintSum = w.placedCount * grid.footprintPerPanelM2;
      expect(footprintSum).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-3);

      // Économies ≤ coût ÉNERGIE évitable (billMAD de la conso modélisée). Surplus = 0.
      const tariff = tariffForCity();
      const consMo = billToAnnualKwh(bill, tariff) / 12;
      const avoidableYr = billMAD(consMo, tariff) * 12;
      expect(res.winner.savingsHigh).toBeLessThanOrEqual(avoidableYr + 1e-3);
    }
  }, 90000);

  it('FUZZ verrous cumulés en PROFONDEUR sous ordres aléatoires : chaque verrou est TENU jusqu\'à saturation', () => {
    const r = rng(0x5EED);
    const ring = squareRing(18);
    for (let trial = 0; trial < 40; trial++) {
      // ordre aléatoire des axes ; valeur aléatoire par axe.
      const axes = ['orientation', 'tiltDeg', 'layout', 'margin', 'need'] as const;
      // mélange (Fisher-Yates)
      const order = [...axes];
      for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }
      const locks: AxisLocks = {};
      for (const ax of order) {
        if (ax === 'orientation') locks.orientation = (['south', 'eastwest', 'aligned'] as const)[Math.floor(r() * 3)];
        if (ax === 'tiltDeg') locks.tiltDeg = [0, 5, 15, 29, 35][Math.floor(r() * 5)];
        if (ax === 'layout') locks.layout = r() < 0.5 ? 'portrait' : 'landscape';
        if (ax === 'margin') locks.margin = r() < 0.5 ? 'keep' : 'remove';
        if (ax === 'need') locks.need = 1 + Math.floor(r() * 40);
        const res = solveLive(ring, LAT, 2000, [], locks);
        assertEvalSane(res.winner, res.effectiveNeed);
        // chaque verrou posé jusqu'ici est tenu par le gagnant
        if (locks.tiltDeg != null) expect(res.winner.tiltDeg).toBe(locks.tiltDeg);
        if (locks.layout) expect(res.winner.layout).toBe(locks.layout);
        if (locks.margin) expect(res.winner.margin).toBe(locks.margin);
        if (locks.orientation) {
          if (locks.orientation === 'eastwest') expect(res.winner.family).toBe('eastwest');
          else expect(res.winner.family).toBe('south');
          if (locks.orientation === 'aligned' && res.hasAlignedChoice) expect(res.winner.orientation).toBe('aligned');
        }
        if (locks.need != null && locks.need > 0) expect(res.winner.placedCount).toBeLessThanOrEqual(locks.need);
      }
    }
  }, 60000);
});

// ════════════════════════════ TOIT EN PENTE (V8) ════════════════════════════

describe('W48 (V8) — pente : dégénérés/adverses → fini, sans crash, repli « estimé »', () => {
  const ring = squareRing(16);
  const cases: { label: string; ring: LngLat[]; bill: number; pitch: number; facing: number }[] = [
    { label: 'ring vide', ring: [], bill: 1500, pitch: 30, facing: 180 },
    { label: 'aire nulle', ring: [[-7.6, 33.5], [-7.6, 33.5], [-7.6, 33.5]], bill: 1500, pitch: 30, facing: 180 },
    { label: 'toit minuscule', ring: squareRing(0.4), bill: 1500, pitch: 30, facing: 180 },
    { label: 'facture NaN', ring, bill: NaN, pitch: 30, facing: 180 },
    { label: 'pente NaN', ring, bill: 1500, pitch: NaN, facing: 180 },
    { label: 'face NaN', ring, bill: 1500, pitch: 30, facing: NaN },
    { label: 'pente 0', ring, bill: 1500, pitch: 0, facing: 180 },
    { label: 'pente 90', ring, bill: 1500, pitch: 90, facing: 180 },
    { label: 'face nord (0)', ring, bill: 1500, pitch: 30, facing: 0 },
  ];
  for (const c of cases) {
    it(`${c.label} → résultat fini, sans exception`, () => {
      let res!: ReturnType<typeof solveLivePitched>;
      expect(() => { res = solveLivePitched(c.ring, LAT, c.bill, c.pitch, c.facing, [], {}); }).not.toThrow();
      for (const v of [res.winner.fitCount, res.winner.placedCount, res.winner.kwc, res.winner.annualKwh, res.winner.perPanelYield, res.winner.savingsLow, res.winner.savingsHigh]) {
        expect(FINITE(v)).toBe(true);
      }
      expect(res.winner.placedCount).toBeGreaterThanOrEqual(0);
      expect(res.winner.annualKwh).toBeGreaterThanOrEqual(0);
      expect(res.winner.placedCount).toBeLessThanOrEqual(res.winner.fitCount);
    }, 30000);
  }

  it('obstacle couvrant tout → 0 posé ; besoin énorme → capé au fit', () => {
    const covered = solveLivePitched(ring, LAT, 1500, 30, 180, [squareRing(60)], {});
    expect(covered.winner.placedCount).toBe(0);
    const huge = solveLivePitched(ring, LAT, 1500, 30, 180, [], { need: 1e9 });
    expect(huge.winner.placedCount).toBe(huge.winner.fitCount);
  });

  const adversarial: { label: string; fn: () => number | null }[] = [
    { label: 'NaN', fn: () => NaN },
    { label: 'Infinity', fn: () => Infinity },
    { label: 'négatif', fn: () => -50 },
    { label: 'null', fn: () => null },
  ];
  for (const a of adversarial) {
    it(`yieldFn ${a.label} → repli table « estimate », jamais NaN`, () => {
      const res = solveLivePitched(ring, LAT, 1500, 30, 180, [], {}, { yieldFn: a.fn });
      expect(res.winner.yieldSource).toBe('estimate');
      expect(FINITE(res.winner.annualKwh)).toBe(true);
      expect(res.winner.annualKwh).toBeGreaterThanOrEqual(0);
    });
  }
});

describe('W48 (V8) — PROPERTY/FUZZ pente : invariants (pas d\'axe tilt/orientation, coplanaire, posé ≤ besoin)', () => {
  it('toits × pentes × faces × verrous aléatoires : fini, plafond tenu, invariants pente', () => {
    const r = rng(0xBADF00D);
    const layouts: (PitchedLocks['layout'] | undefined)[] = [undefined, 'portrait', 'landscape'];
    const margins: (PitchedLocks['margin'] | undefined)[] = [undefined, 'keep', 'remove'];
    for (let i = 0; i < 80; i++) {
      const n = 3 + Math.floor(r() * 6);
      // rayon borné (perf) ; couvre slivers → toits moyens.
      const ring = randomPolygon(r, n, 3 + r() * 13);
      const bill = r() < 0.1 ? 0 : Math.floor(r() * 6000);
      const pitch = r() * 60; // 0..60° (dont valeurs extrêmes)
      const facing = r() * 360; // toute la rose des vents
      const locks: PitchedLocks = {
        layout: layouts[Math.floor(r() * layouts.length)],
        margin: margins[Math.floor(r() * margins.length)],
        need: r() < 0.3 ? Math.floor(r() * 50) : undefined,
      };
      const res = solveLivePitched(ring, LAT, bill, pitch, facing, [], locks);
      const w = res.winner;
      for (const v of [w.fitCount, w.placedCount, w.kwc, w.annualKwh, w.perPanelYield, w.savingsLow, w.savingsHigh]) {
        expect(FINITE(v)).toBe(true);
      }
      expect(w.placedCount).toBeGreaterThanOrEqual(0);
      expect(Number.isInteger(w.placedCount)).toBe(true);
      expect(w.placedCount).toBeLessThanOrEqual(w.fitCount);
      if (res.effectiveNeed > 0) expect(w.placedCount).toBeLessThanOrEqual(res.effectiveNeed);
      expect(w.savingsLow).toBeGreaterThanOrEqual(0);

      // INVARIANT pente : un seul plan (pente, face) — pas d'axe inclinaison/orientation.
      expect(res.pitchDeg).toBe(pitch);
      expect(res.facingAzimuthDeg).toBe(facing);
      expect(w.pack.pitchDeg).toBe(pitch);
      expect(w.pack.facingAzimuthDeg).toBe(facing);
      // les seules valeurs d'axe sont pose × marge (≤ 4 lignes), orientation jamais variable
      expect(res.rows.length).toBeLessThanOrEqual(4);
      for (const row of res.rows) {
        expect(['portrait', 'landscape']).toContain(row.layout);
        expect(['keep', 'remove']).toContain(row.margin);
      }
      // un verrou posé est tenu
      if (locks.layout) expect(w.layout).toBe(locks.layout);
      if (locks.margin) expect(w.margin).toBe(locks.margin);
      // pan nord → 0 posé (honnêteté)
      if (res.northFacing) expect(w.placedCount).toBe(0);
    }
  }, 60000);
});

describe('W48 — E-O ≥ Sud même inclinaison (densité chevron), surplus non rémunéré', () => {
  it('à inclinaison E-O fixe, l\'Est-Ouest loge ≥ autant que le Sud (sur un grand toit)', () => {
    const ring = squareRing(30);
    // E-O n'existe qu'aux inclinaisons E-O (10/15) ; on compare à tilt égal, besoin non bornant.
    for (const tilt of [10, 15]) {
      const south = solveLive(ring, LAT, 99999, [], { orientation: 'south', tiltDeg: tilt });
      const ew = solveLive(ring, LAT, 99999, [], { orientation: 'eastwest', tiltDeg: tilt });
      expect(ew.winner.fitCount).toBeGreaterThanOrEqual(south.winner.fitCount);
    }
  });

  it('surplus non rémunéré : production ≫ conso → économies plafonnées au coût évitable', () => {
    const ring = squareRing(40);
    const res = solveLive(ring, LAT, 200 /* petite facture */, [], {});
    const tariff = tariffForCity();
    const consMo = billToAnnualKwh(200, tariff) / 12;
    const avoidableYr = billMAD(consMo, tariff) * 12;
    expect(res.winner.savingsHigh).toBeLessThanOrEqual(avoidableYr + 1e-3); // surplus vaut 0
  });
});
