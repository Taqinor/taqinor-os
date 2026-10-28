// WJ26 — « Tout est expliqué » : légende + annotations + visite guidée.
// Chaque test prouve qu'un chiffre affiché vient du layout serveur ou du
// payload quote, et que toute donnée absente devient « estimation
// indisponible » / null — jamais une valeur fabriquée.
import { describe, expect, it } from 'vitest';
import {
  orientationLabelFr,
  zoneAnnotations,
  parseRoofLayout,
  type RoofLayout,
} from '../src/lib/proposition';


function makeLayout(): RoofLayout {
  return parseRoofLayout({
    version: 1,
    zones: [
      {
        id: 'z1',
        label: 'Pan sud',
        vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001], [-7.6, 33.5001]],
        roofType: 'pitched',
        pitchDeg: 22,
        facingAzimuthDeg: 170,
        neededPanels: 6,
      },
      {
        id: 'z2',
        label: 'Terrasse',
        vertices: [[-7.61, 33.5], [-7.6099, 33.5], [-7.6099, 33.5001], [-7.61, 33.5001]],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        neededPanels: 0,
      },
    ],
  })!;
}

describe('WJ26 — orientationLabelFr', () => {
  it('mappe les azimuts sur les 8 directions FR', () => {
    expect(orientationLabelFr(180)).toBe('Sud');
    expect(orientationLabelFr(135)).toBe('Sud-Est');
    expect(orientationLabelFr(225)).toBe('Sud-Ouest');
    expect(orientationLabelFr(90)).toBe('Est');
    expect(orientationLabelFr(270)).toBe('Ouest');
    expect(orientationLabelFr(0)).toBe('Nord');
    expect(orientationLabelFr(360)).toBe('Nord');
    expect(orientationLabelFr(-90)).toBe('Ouest');
    // au plus proche : 170° → Sud
    expect(orientationLabelFr(170)).toBe('Sud');
  });
});

describe('WJ26 — zoneAnnotations (chiffres serveur uniquement)', () => {
  it('annote chaque pan : orientation, pente, panneaux, kWc calculé', () => {
    const a = zoneAnnotations(makeLayout(), 720);
    expect(a).toHaveLength(2);
    expect(a[0].label).toBe('Pan sud');
    expect(a[0].orientation).toBe('Sud');
    expect(a[0].tiltDeg).toBe(22);
    expect(a[0].roofTypeLabel).toBe('Toit en pente');
    expect(a[0].panels).toBe(6);
    // kWc = panneaux (layout serveur) × Wc/panneau (payload) — traçable.
    expect(a[0].kwc).toBe(4.32);
  });

  it('toit plat : pas de pente affichée ; zone non dimensionnée : panels/kwc null', () => {
    const a = zoneAnnotations(makeLayout(), 720);
    expect(a[1].tiltDeg).toBeNull();
    expect(a[1].roofTypeLabel).toBe('Toit plat');
    expect(a[1].panels).toBeNull();
    expect(a[1].kwc).toBeNull();
  });

  it('sans watt_par_panneau (payload), kWc = null — jamais inventé', () => {
    const a = zoneAnnotations(makeLayout(), null);
    expect(a[0].kwc).toBeNull();
    const b = zoneAnnotations(makeLayout(), undefined);
    expect(b[0].kwc).toBeNull();
  });
});
