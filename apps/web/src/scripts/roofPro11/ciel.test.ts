/**
 * ACAL431 — le ciel suit la position du soleil. Module neuf, pur : `couleursCiel`
 * ne dépend que de l'élévation ; `appliquerCiel` ne touche la carte que par
 * `setSky`, jamais en mode bas de gamme.
 */
import { describe, it, expect, vi } from 'vitest';
import { couleursCiel, appliquerCiel } from './ciel';
import { sunDirection } from '../../lib/roofPro2';

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const lum = (hex: string) => { const [r, g, b] = rgb(hex); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };

describe('ACAL431 — ciel selon le soleil', () => {
  it('12 h : ciel clair et bleu ; élévation faible : horizon chaud ; ≤ 0 : sombre', () => {
    const midi = sunDirection(33.5, 355, 12).elevationDeg;
    const matin = sunDirection(33.5, 355, 7).elevationDeg;
    const soir = sunDirection(33.5, 355, 20).elevationDeg;
    expect(matin).toBeLessThan(10);
    expect(soir).toBeLessThanOrEqual(0);

    const jour = couleursCiel(midi);
    const [r, , b] = rgb(jour.skyColor);
    expect(b).toBeGreaterThan(r);
    expect(lum(jour.skyColor)).toBeGreaterThan(120);

    const chaud = couleursCiel(3);
    const [hr, , hb] = rgb(chaud.horizonColor);
    expect(hr).toBeGreaterThan(hb); // teinte chaude près de l'horizon

    const nuit = couleursCiel(soir);
    expect(lum(nuit.skyColor)).toBeLessThan(60);
    expect(lum(nuit.skyColor)).toBeLessThan(lum(jour.skyColor));
  });

  it('continu d\'un degré au suivant (pas de saut de teinte)', () => {
    for (let e = -10; e < 90; e += 1) {
      const a = couleursCiel(e);
      const c = couleursCiel(e + 1);
      for (const k of ['skyColor', 'horizonColor', 'fogColor'] as const) {
        const [ar, ag, ab] = rgb(a[k]);
        const [cr, cg, cb] = rgb(c[k]);
        expect(Math.max(Math.abs(ar - cr), Math.abs(ag - cg), Math.abs(ab - cb))).toBeLessThanOrEqual(40);
      }
    }
  });

  it('applique le ciel par setSky ; bas de gamme : JAMAIS setSky ; carte sans setSky : sans exception', () => {
    const setSky = vi.fn();
    appliquerCiel({ setSky } as never, 40, false);
    expect(setSky).toHaveBeenCalledTimes(1);
    const arg = setSky.mock.calls[0][0];
    expect(arg['sky-color']).toBe(couleursCiel(40).skyColor);

    const bas = vi.fn();
    appliquerCiel({ setSky: bas } as never, 40, true);
    expect(bas).not.toHaveBeenCalled();

    expect(() => appliquerCiel({} as never, 40, false)).not.toThrow();
  });
});
