// Cerveau V7 — src/lib/estimatorBrainV7.ts (preview privé pro-10). L'OPTIMISEUR
// CONTRAINT VIVANT pour toit plat : re-résout à chaque changement d'option, les
// verrous s'accumulent, et chaque axe affiche sa valeur « Recommandé » (axe libéré,
// autres verrous tenus). Ces tests ancrent : le vrai maximum sur tout le balayage,
// le verrou tenu pendant que le reste se re-résout, l'accumulation des verrous +
// la réinitialisation, le recommandé-par-axe = optimum de l'axe libéré, le mapping
// de signe d'azimut PVGIS (S=0 / E=−90 / O=+90 / N=180), génération = posé × kWc ×
// rendement PVGIS avec posé = min(besoin, ce qui tient) et le plafond jamais dépassé,
// et le repli gracieux PVGIS.
import { describe, expect, it } from 'vitest';
import {
  betterLive,
  solveLive,
  type AxisLocks,
  type LiveConfigEval,
  type YieldFn,
} from '../src/lib/estimatorBrainV7';
import { PANEL2_WATT, aspectForAzimuth, optimalSouthTiltDeg } from '../src/lib/estimatorBrainV2';
import { matrixTiltGrid } from '../src/lib/estimatorBrainV6';
import { type LngLat } from '../src/lib/roof';

const LAT = 33.59;
const BILL = 1500;

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

/** Rectangle TOURNÉ de `rotDeg` (sens horaire), pour fabriquer un toit « aligné toit »
 *  distinct du plein sud (longueur le long de l'axe tourné). */
function rotatedRect(lenM: number, widM: number, rotDeg: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const r = (rotDeg * Math.PI) / 180;
  const cos = Math.cos(r);
  const sin = Math.sin(r);
  const mPerLat = 111320;
  const mPerLng = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const corners: [number, number][] = [
    [-lenM / 2, -widM / 2],
    [lenM / 2, -widM / 2],
    [lenM / 2, widM / 2],
    [-lenM / 2, widM / 2],
  ];
  return corners.map(([x, y]) => {
    const xr = x * cos - y * sin;
    const yr = x * sin + y * cos;
    return [lng0 + xr / mPerLng, lat0 + yr / mPerLat] as LngLat;
  });
}

// Pic PVGIS injecté : rendement maximal à (peakTilt, peakAspect), décroît linéairement.
function peakYield(peakTilt: number, peakAspect: number, base = 1700): YieldFn {
  return (tilt, aspect) => Math.max(150, base - Math.abs(tilt - peakTilt) * 14 - Math.abs(aspect - peakAspect) * 10);
}

describe('V7 — comparateur déterministe', () => {
  it('betterLive préfère plus d\'énergie posée, puis rendement, puis moins de matériel', () => {
    const base: LiveConfigEval = {
      orientation: 'south', family: 'south', azimuthDeg: 180, aspect: 0, tiltDeg: 29,
      layout: 'portrait', margin: 'keep', fitCount: 10, placedCount: 10, kwc: 7.2,
      annualKwh: 12000, pctOfTarget: 100, savingsLow: 1, savingsHigh: 2, perPanelYield: 1666,
      yieldSource: 'pvgis', orientationLabel: 'plein sud', layoutLabel: 'portrait', label: 'x',
    };
    const more = { ...base, annualKwh: 12500 };
    expect(betterLive(more, base)).toBe(true);
    expect(betterLive(base, more)).toBe(false);
    // énergie égale → moins de panneaux (moins de matériel) gagne
    const fewer = { ...base, placedCount: 8 };
    expect(betterLive(fewer, base)).toBe(true);
  });
});

describe('V7 — le gagnant est le VRAI maximum sur tout le balayage', () => {
  const ring = squareRing(20);

  it('aucune autre config (axes libres) ne bat le gagnant', () => {
    const res = solveLive(ring, LAT, BILL, [], {});
    const w = res.winner;
    // re-balayer toutes les combinaisons possibles et vérifier qu'aucune ne dépasse le gagnant
    const orientations: AxisLocks['orientation'][] = res.hasAlignedChoice
      ? ['south', 'aligned', 'eastwest']
      : ['south', 'eastwest'];
    for (const orientation of orientations) {
      for (const tiltDeg of matrixTiltGrid(LAT)) {
        for (const layout of ['portrait', 'landscape'] as const) {
          for (const margin of ['keep', 'remove'] as const) {
            const locked = solveLive(ring, LAT, BILL, [], { orientation, tiltDeg, layout, margin } as AxisLocks).winner;
            expect(locked.annualKwh).toBeLessThanOrEqual(w.annualKwh + 1e-6);
          }
        }
      }
    }
  });

  it('PVGIS = source de vérité : un pic injecté DÉPLACE le gagnant (inclinaison)', () => {
    const res = solveLive(ring, LAT, BILL, [], {}, { yieldFn: peakYield(10, 0) });
    expect(res.winner.yieldSource).toBe('pvgis');
    expect(res.winner.tiltDeg).toBe(10); // cale sur le pic, pas l'inclinaison de table
    expect(res.winner.orientation).toBe('south');
    expect(Math.round(res.winner.aspect)).toBe(0); // plein sud
  });

  it('sans pic, le gagnant plein-sud cale près de l\'inclinaison optimale de table', () => {
    const res = solveLive(ring, LAT, BILL, [], {});
    expect(res.winner.orientation === 'south' || res.winner.orientation === 'eastwest').toBe(true);
    // l'inclinaison du gagnant fait partie de la grille fine
    expect(matrixTiltGrid(LAT)).toContain(res.winner.tiltDeg);
  });
});

describe('V7 — un verrou est TENU pendant que le reste se re-résout', () => {
  const ring = squareRing(20);

  it('verrouiller l\'inclinaison la tient ; les autres axes restent optimaux sous contrainte', () => {
    const res = solveLive(ring, LAT, BILL, [], { tiltDeg: 12 });
    expect(res.winner.tiltDeg).toBe(12); // verrou tenu
    // le reste = le meilleur à 12° : re-balayer orientation/layout/margin à 12°
    for (const orientation of (res.hasAlignedChoice ? ['south', 'aligned', 'eastwest'] : ['south', 'eastwest']) as AxisLocks['orientation'][]) {
      for (const layout of ['portrait', 'landscape'] as const) {
        for (const margin of ['keep', 'remove'] as const) {
          const probe = solveLive(ring, LAT, BILL, [], { tiltDeg: 12, orientation, layout, margin } as AxisLocks).winner;
          expect(probe.annualKwh).toBeLessThanOrEqual(res.winner.annualKwh + 1e-6);
        }
      }
    }
  });

  it('verrouiller une orientation sous-optimale la tient (Est-Ouest forcé)', () => {
    const res = solveLive(ring, LAT, BILL, [], { orientation: 'eastwest' });
    expect(res.winner.orientation).toBe('eastwest');
    expect(res.winner.family).toBe('eastwest');
  });
});

describe('V7 — les verrous s\'ACCUMULENT, Réinitialiser efface tout', () => {
  const ring = squareRing(20);

  it('un 2ᵉ verrou ne laisse flotter que les axes encore AUTO en tenant les DEUX', () => {
    const res = solveLive(ring, LAT, BILL, [], { orientation: 'eastwest', tiltDeg: 15 });
    expect(res.winner.orientation).toBe('eastwest');
    expect(res.winner.tiltDeg).toBe(15);
    // layout & margin re-résolus : meilleurs à (E-O, 15°)
    for (const layout of ['portrait', 'landscape'] as const) {
      for (const margin of ['keep', 'remove'] as const) {
        const probe = solveLive(ring, LAT, BILL, [], { orientation: 'eastwest', tiltDeg: 15, layout, margin }).winner;
        expect(probe.annualKwh).toBeLessThanOrEqual(res.winner.annualKwh + 1e-6);
      }
    }
  });

  it('globalWinner = l\'optimum tous-axes-libres (la cible de « Réinitialiser »)', () => {
    const constrained = solveLive(ring, LAT, BILL, [], { orientation: 'eastwest', tiltDeg: 15, layout: 'landscape' });
    const reset = solveLive(ring, LAT, BILL, [], {});
    // le globalWinner d'un état verrouillé == le gagnant d'un état SANS verrou
    expect(constrained.globalWinner.label).toBe(reset.winner.label);
    expect(constrained.globalWinner.annualKwh).toBeCloseTo(reset.winner.annualKwh, 6);
  });
});

describe('V7 — « Recommandé » par axe = l\'optimum de l\'axe LIBÉRÉ (autres verrous tenus)', () => {
  const ring = squareRing(20);

  it('quand on verrouille une valeur sous-optimale, le recommandé montre la meilleure', () => {
    // forcer Est-Ouest sur un toit où plein sud est meilleur → recommandé orientation = sud
    const res = solveLive(ring, LAT, BILL, [], { orientation: 'eastwest' });
    const freedBest = solveLive(ring, LAT, BILL, [], {}).winner; // orientation libérée, rien d'autre verrouillé
    expect(res.recommended.orientation).toBe(freedBest.orientation);
    // l'utilisateur voit qu'il a choisi E-O mais que « sud » est recommandé
    expect(res.winner.orientation).toBe('eastwest');
  });

  it('le recommandé d\'un axe tient compte des AUTRES verrous courants', () => {
    // verrou inclinaison = 5° ; le layout recommandé = le meilleur layout À 5°
    const res = solveLive(ring, LAT, BILL, [], { tiltDeg: 5 });
    const freedLayout = solveLive(ring, LAT, BILL, [], { tiltDeg: 5 }); // layout libre, tilt tenu
    expect(res.recommended.layout).toBe(freedLayout.winner.layout);
  });

  it('le besoin recommandé est toujours la cible dérivée de la facture', () => {
    const res = solveLive(ring, LAT, BILL, [], { need: 4 });
    expect(res.recommended.need).toBe(res.neededPanels);
    expect(res.effectiveNeed).toBe(4); // verrou besoin respecté
  });
});

describe('V7 — mapping de signe d\'azimut PVGIS (S=0 / E=−90 / O=+90 / N=180)', () => {
  it('aspectForAzimuth respecte la convention PVGIS pour le sud', () => {
    expect(aspectForAzimuth('south', 180)).toBe(0); // plein sud → 0
    expect(aspectForAzimuth('south', 90)).toBe(-90); // est → −90
    expect(aspectForAzimuth('south', 270)).toBe(90); // ouest → +90
    expect(aspectForAzimuth('south', 360)).toBe(180); // nord → 180
  });

  it('le gagnant plein sud interroge bien l\'aspect 0 (yieldFn enregistreur)', () => {
    const ring = squareRing(20);
    const seen: { tilt: number; aspect: number }[] = [];
    const recFn: YieldFn = (tilt, aspect) => {
      seen.push({ tilt, aspect });
      return aspect === 0 ? 1700 : 1200; // récompense le plein sud
    };
    const res = solveLive(ring, LAT, BILL, [], {}, { yieldFn: recFn });
    expect(res.winner.orientation).toBe('south');
    expect(Math.round(res.winner.aspect)).toBe(0);
    expect(seen.some((s) => s.aspect === 0)).toBe(true);
    // l'Est-Ouest interroge bien −90 et +90
    expect(seen.some((s) => s.aspect === -90)).toBe(true);
    expect(seen.some((s) => s.aspect === 90)).toBe(true);
  });
});

describe('V7 — génération = posé × kWc × rendement, plafond besoin jamais dépassé', () => {
  it('formule de génération exacte (sud : kWh = kWc × rendement/panneau)', () => {
    const ring = squareRing(20);
    const flat: YieldFn = () => 1600; // rendement constant
    const res = solveLive(ring, LAT, BILL, [], { orientation: 'south', tiltDeg: 20, layout: 'portrait', margin: 'keep' }, { yieldFn: flat });
    const w = res.winner;
    expect(w.kwc).toBeCloseTo((w.placedCount * PANEL2_WATT) / 1000, 9);
    expect(w.annualKwh).toBeCloseTo(w.kwc * 1600, 6);
  });

  it('posé = min(besoin, ce qui tient) — plafond jamais dépassé', () => {
    const ring = squareRing(30); // grand toit, tient bien plus que le besoin
    const res = solveLive(ring, LAT, BILL, [], {});
    expect(res.winner.placedCount).toBeLessThanOrEqual(res.effectiveNeed);
    expect(res.winner.placedCount).toBeLessThanOrEqual(res.winner.fitCount);
  });

  it('toit limité : posé = ce qui tient (< besoin) → roofLimited', () => {
    const ring = squareRing(7); // petit toit
    const res = solveLive(ring, LAT, 3000, [], {}); // grosse facture → besoin élevé
    expect(res.winner.placedCount).toBe(res.winner.fitCount);
    expect(res.winner.placedCount).toBeLessThan(res.effectiveNeed);
    expect(res.roofLimited).toBe(true);
  });

  it('verrouiller un besoin PLUS BAS réduit le posé et l\'énergie', () => {
    const ring = squareRing(20);
    const full = solveLive(ring, LAT, BILL, [], {});
    const capped = solveLive(ring, LAT, BILL, [], { need: 3 });
    expect(capped.effectiveNeed).toBe(3);
    expect(capped.winner.placedCount).toBeLessThanOrEqual(3);
    expect(capped.winner.annualKwh).toBeLessThan(full.winner.annualKwh);
  });
});

describe('V7 — repli gracieux PVGIS', () => {
  const ring = squareRing(20);

  it('yieldFn=null → table committée, source « estimate », chiffres = table seule', () => {
    const withNull = solveLive(ring, LAT, BILL, [], {}, { yieldFn: () => null });
    const tableOnly = solveLive(ring, LAT, BILL, [], {});
    expect(withNull.winner.yieldSource).toBe('estimate');
    expect(Math.round(withNull.winner.annualKwh)).toBe(Math.round(tableOnly.winner.annualKwh));
  });

  it('sans pic PVGIS, l\'optimum sud cale sur l\'inclinaison optimale de table', () => {
    const res = solveLive(ring, LAT, BILL, [], {});
    if (res.winner.orientation === 'south' && Math.round(res.winner.aspect) === 0) {
      expect(Math.abs(res.winner.tiltDeg - optimalSouthTiltDeg(LAT))).toBeLessThanOrEqual(5);
    }
    expect(res.winner.yieldSource).toBe('estimate');
  });
});

// W72 — UNE seule source de rendement pour le cap besoin ET la production : le PVGIS du
// gagnant pilote neededPanels, donc la couverture affichée ~110 % se calcule au MÊME
// rendement que la production (plus de dérive table↔PVGIS).
describe('W72 — le PVGIS du gagnant pilote le cap « besoin »', () => {
  const ring = squareRing(40); // grand toit : non limité, le cap besoin domine

  it('un PVGIS plus BAS que la table augmente neededPanels (cap recalé)', () => {
    const tableOnly = solveLive(ring, LAT, BILL, [], {});
    const lowYield = solveLive(ring, LAT, BILL, [], {}, { yieldFn: () => 900 });
    // rendement < table (~1700) → il faut plus de panneaux pour la même cible.
    expect(lowYield.winner.yieldSource).toBe('pvgis');
    expect(lowYield.neededPanels).toBeGreaterThan(tableOnly.neededPanels);
  });

  it('la couverture du gagnant est ~110 % au MÊME rendement PVGIS que la production', () => {
    const res = solveLive(ring, LAT, BILL, [], {}, { yieldFn: () => 1300 });
    // toit spacieux → posé = besoin (cap atteint), pctOfTarget ≈ marge de couverture 110 %.
    expect(res.roofLimited).toBe(false);
    expect(res.winner.placedCount).toBe(res.neededPanels);
    expect(res.winner.pctOfTarget).toBeGreaterThan(100);
    expect(res.winner.pctOfTarget).toBeLessThan(125);
  });
});
