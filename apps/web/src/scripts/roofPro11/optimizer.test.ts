// CAL75 — écart rangée/colonne RÉGLABLE en pose optimisée (jusqu'ici réglable SEULEMENT en
// placement libre). `optimizer.ts` ne fait que transmettre `ctx.colGapM`/`ctx.rowGapExtraM` au
// pavage (packConfig, estimatorBrainV2.ts) et re-pave à chaud — la physique testée ici EST le
// changement : options absentes → calepinage identique au millimètre ; écart agrandi → moins de
// panneaux tiennent (le compte baisse), jamais l'inverse.
import { describe, expect, it } from 'vitest';
import { packConfig, type PackOptions } from '../../lib/estimatorBrainV2';
import { type LngLat } from '../../lib/roof';

/** Contour RECTANGULAIRE large (assez pour plusieurs rangées/colonnes de panneaux). */
function rectRing(widthM: number, depthM: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = depthM / 2 / 111320;
  const dLng = widthM / 2 / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng, lat0 - dLat],
    [lng0 + dLng, lat0 - dLat],
    [lng0 + dLng, lat0 + dLat],
    [lng0 - dLng, lat0 + dLat],
  ];
}

const ring = rectRing(20, 15);
const baseOpts: PackOptions = { family: 'south', tiltDeg: 13 };

describe('CAL75 — packConfig(colGapM, rowGapExtraM)', () => {
  it('options absentes → calepinage IDENTIQUE (même compte, mêmes positions) à avant CAL75', () => {
    const withoutOpts = packConfig(ring, 33.5, baseOpts);
    const withDefaultsExplicit = packConfig(ring, 33.5, { ...baseOpts, colGapM: undefined, rowGapExtraM: 0 });
    expect(withDefaultsExplicit.best.count).toBe(withoutOpts.best.count);
    expect(withDefaultsExplicit.best.rowPitchM).toBeCloseTo(withoutOpts.best.rowPitchM, 9);
    expect(withDefaultsExplicit.best.panels).toEqual(withoutOpts.best.panels);
  });

  it('colGapM agrandi → jamais PLUS de panneaux (les colonnes s’espacent, le compte baisse ou reste égal)', () => {
    const tight = packConfig(ring, 33.5, baseOpts);
    const wide = packConfig(ring, 33.5, { ...baseOpts, colGapM: 0.5 });
    expect(wide.best.count).toBeLessThanOrEqual(tight.best.count);
    expect(wide.best.count).toBeGreaterThan(0); // le toit reste assez grand pour en accueillir
  });

  it('rowGapExtraM agrandi → le pas de rangée grandit d’AUTANT, le compte baisse ou reste égal', () => {
    const tight = packConfig(ring, 33.5, baseOpts);
    const spaced = packConfig(ring, 33.5, { ...baseOpts, rowGapExtraM: 0.3 });
    expect(spaced.best.rowPitchM).toBeCloseTo(tight.best.rowPitchM + 0.3, 9);
    expect(spaced.best.count).toBeLessThanOrEqual(tight.best.count);
  });

  it('un colGapM négatif est ramené à 0 (jamais un recouvrement)', () => {
    const negative = packConfig(ring, 33.5, { ...baseOpts, colGapM: -5 });
    const zero = packConfig(ring, 33.5, { ...baseOpts, colGapM: 0 });
    expect(negative.best.count).toBe(zero.best.count);
  });

  it('même écart appliqué en Est-Ouest (chevron) : rowGapExtraM élargit aussi le pas entre chevrons', () => {
    const ew: PackOptions = { family: 'eastwest', tiltDeg: 13 };
    const tight = packConfig(ring, 33.5, ew);
    const spaced = packConfig(ring, 33.5, { ...ew, rowGapExtraM: 0.3 });
    // Compare la MÊME orientation des deux côtés (`best` peut basculer portrait/paysage selon
    // l'écart, ce qui changerait aussi la géométrie du panneau — pas ce qu'on veut isoler ici).
    expect(spaced.landscape.rowPitchM).toBeCloseTo(tight.landscape.rowPitchM + 0.3, 9);
    expect(spaced.portrait.rowPitchM).toBeCloseTo(tight.portrait.rowPitchM + 0.3, 9);
  });
});
