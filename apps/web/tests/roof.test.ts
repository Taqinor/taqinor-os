// Géométrie pure de l'estimateur de toiture (preview privé) : aire géodésique,
// pavage à l'échelle (panneaux 1,7 × 1,0 m + retrait de rive), conversion kWc,
// production de repli et bande d'économies. Module pur (aucun DOM, aucune
// carte) → testé unitairement. La carte/le tracé restent de la colle non testée.
import { describe, expect, it } from 'vitest';
import {
  PANEL_LENGTH_M,
  PANEL_WIDTH_M,
  PANEL_WATT,
  SETBACK_M,
  geodesicAreaM2,
  roofAreaLabel,
  ringBBox,
  lngLatToUV,
  pointInPolygon,
  orientationToAspect,
  kwcFromPanelCount,
  fallbackAnnualKwh,
  annualSavingsBandMad,
  layoutPanels,
  type LngLat,
} from '../src/lib/roof';

const R = 6378137; // WGS84 — même rayon que la formule de référence
const DEG2M = (Math.PI / 180) * R;

/** Construit un rectangle (lng/lat) de `wEW` m est-ouest × `hNS` m nord-sud. */
function rectMeters(lng0: number, lat0: number, wEW: number, hNS: number): LngLat[] {
  const dLat = hNS / DEG2M;
  const dLng = wEW / (DEG2M * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0, lat0],
    [lng0 + dLng, lat0],
    [lng0 + dLng, lat0 + dLat],
    [lng0, lat0 + dLat],
  ];
}

describe('geodesicAreaM2 — aire d’un polygone WGS84 (m²)', () => {
  it('un carré ~10 m de côté à Casablanca ≈ 100 m² (±2 %)', () => {
    const ring = rectMeters(-7.6, 33.57, 10, 10);
    const a = geodesicAreaM2(ring);
    expect(a).toBeGreaterThan(98);
    expect(a).toBeLessThan(102);
  });

  it('doubler les côtés quadruple l’aire (±1 %)', () => {
    const small = geodesicAreaM2(rectMeters(-7.6, 33.57, 10, 10));
    const big = geodesicAreaM2(rectMeters(-7.6, 33.57, 20, 20));
    expect(big / small).toBeGreaterThan(3.96);
    expect(big / small).toBeLessThan(4.04);
  });

  it('indépendante du sens d’enroulement (toujours positive)', () => {
    const ring = rectMeters(-7.6, 33.57, 12, 8);
    const reversed = [...ring].reverse();
    expect(geodesicAreaM2(reversed)).toBeCloseTo(geodesicAreaM2(ring), 3);
    expect(geodesicAreaM2(ring)).toBeGreaterThan(0);
  });

  it('moins de 3 sommets → 0 (tracé dégénéré, jamais d’erreur)', () => {
    expect(geodesicAreaM2([])).toBe(0);
    expect(geodesicAreaM2([[-7.6, 33.57]])).toBe(0);
    expect(geodesicAreaM2([[-7.6, 33.57], [-7.5, 33.57]])).toBe(0);
  });
});

describe('roofAreaLabel — readout « surface du toit » à l’écran', () => {
  it('un carré ~10 m de côté → « ~100 m² » (arrondi au m²)', () => {
    const label = roofAreaLabel(rectMeters(-7.6, 33.57, 10, 10));
    expect(label).toBe('~100 m²');
  });

  it('arrondit au m² entier et préfixe ~ (estimation satellite)', () => {
    // ~84,3 m² doit s’afficher « ~84 m² » (jamais de décimale).
    const label = roofAreaLabel(rectMeters(-7.6, 33.57, 12, 7));
    expect(label).toMatch(/^~\d+ m²$/);
    expect(label).not.toContain(',');
    expect(label).not.toContain('.');
  });

  it('grands toits : séparateur de milliers FR (format du site)', () => {
    // 40 m × 40 m ≈ 1 600 m² ; on compare au format Intl fr-FR de référence.
    const label = roofAreaLabel(rectMeters(-7.6, 33.57, 40, 40));
    const expected = `~${new Intl.NumberFormat('fr-FR').format(1600)} m²`;
    expect(label).toBe(expected);
  });

  it('tracé vide / dégénéré (< 3 sommets) → null (readout effacé)', () => {
    expect(roofAreaLabel([])).toBeNull();
    expect(roofAreaLabel([[-7.6, 33.57]])).toBeNull();
    expect(roofAreaLabel([[-7.6, 33.57], [-7.5, 33.57]])).toBeNull();
  });
});

describe('ringBBox + lngLatToUV — alignement géographique de la texture satellite', () => {
  const ring: LngLat[] = [
    [-7.62, 33.58],
    [-7.60, 33.58],
    [-7.60, 33.59],
    [-7.62, 33.59],
  ];
  it('bbox = min/max lng/lat du tracé', () => {
    expect(ringBBox(ring)).toEqual([-7.62, 33.58, -7.60, 33.59]);
  });
  it('coin sud-ouest → (0,0), coin nord-est → (1,1)', () => {
    const bbox = ringBBox(ring);
    expect(lngLatToUV(-7.62, 33.58, bbox)).toEqual([0, 0]);
    expect(lngLatToUV(-7.60, 33.59, bbox)).toEqual([1, 1]);
  });
  it('le centre tombe au milieu de la texture', () => {
    const bbox = ringBBox(ring);
    const [u, v] = lngLatToUV(-7.61, 33.585, bbox);
    expect(u).toBeCloseTo(0.5, 6);
    expect(v).toBeCloseTo(0.5, 6);
  });
  it('le nord (lat haute) tombe en haut de l’image (v→1, flipY THREE)', () => {
    const bbox = ringBBox(ring);
    const [, vNorth] = lngLatToUV(-7.61, 33.59, bbox);
    const [, vSouth] = lngLatToUV(-7.61, 33.58, bbox);
    expect(vNorth).toBeGreaterThan(vSouth);
    expect(vNorth).toBe(1);
    expect(vSouth).toBe(0);
  });
});

describe('pointInPolygon — appartenance (rayon)', () => {
  const square: [number, number][] = [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
  ];
  it('un point intérieur est dedans', () => {
    expect(pointInPolygon([5, 5], square)).toBe(true);
  });
  it('un point extérieur est dehors', () => {
    expect(pointInPolygon([15, 5], square)).toBe(false);
    expect(pointInPolygon([-1, 5], square)).toBe(false);
  });
});

describe('orientationToAspect — convention PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord)', () => {
  it('mappe les orientations canoniques', () => {
    expect(orientationToAspect('sud')).toBe(0);
    expect(orientationToAspect('sud-est')).toBe(-45);
    expect(orientationToAspect('sud-ouest')).toBe(45);
    expect(orientationToAspect('est')).toBe(-90);
    expect(orientationToAspect('ouest')).toBe(90);
    expect(orientationToAspect('nord')).toBe(180);
  });
  it('inconnu / valeur absente → Sud (meilleure hypothèse, documentée)', () => {
    expect(orientationToAspect('inconnu')).toBe(0);
    expect(orientationToAspect('')).toBe(0);
    expect(orientationToAspect('bidon')).toBe(0);
  });
});

describe('kwcFromPanelCount — puissance crête', () => {
  it('count × 550 W → kWc', () => {
    expect(kwcFromPanelCount(0)).toBe(0);
    expect(kwcFromPanelCount(10)).toBeCloseTo(5.5, 6);
    expect(kwcFromPanelCount(1)).toBeCloseTo(0.55, 6);
  });
  it('watt configurable', () => {
    expect(kwcFromPanelCount(10, 500)).toBeCloseTo(5, 6);
  });
  it('constantes panneau au standard du marché', () => {
    expect(PANEL_LENGTH_M).toBe(1.7);
    expect(PANEL_WIDTH_M).toBe(1.0);
    expect(PANEL_WATT).toBe(550);
    expect(SETBACK_M).toBeGreaterThanOrEqual(0.4);
    expect(SETBACK_M).toBeLessThanOrEqual(0.5);
  });
});

describe('fallbackAnnualKwh — repli quand PVGIS est injoignable', () => {
  it('≈ 1 600 kWh/kWc/an (hypothèse Maroc)', () => {
    expect(fallbackAnnualKwh(0)).toBe(0);
    expect(fallbackAnnualKwh(5)).toBe(8000);
    expect(fallbackAnnualKwh(10)).toBe(16000);
  });
});

describe('annualSavingsBandMad — fourchette 60–90 % × tarif', () => {
  it('basse = 60 %, haute = 90 % de la valeur produite', () => {
    // 8000 kWh × 1,4 MAD = 11 200 MAD de valeur ; 60 % → 6 720, 90 % → 10 080
    const band = annualSavingsBandMad(8000);
    expect(band.low).toBeCloseTo(6720, 0);
    expect(band.high).toBeCloseTo(10080, 0);
    expect(band.low).toBeLessThan(band.high);
  });
  it('0 kWh → bande nulle', () => {
    expect(annualSavingsBandMad(0)).toEqual({ low: 0, high: 0 });
  });

  it('plafonne l’économie à la facture annuelle estimée (ERR113)', () => {
    // 8000 kWh → low 6720 / high 10080 sans plafond ; avec une facture de
    // 5000 MAD, les DEUX bornes sont ramenées au plafond (on ne peut pas
    // économiser plus que ce qu’on dépense).
    const band = annualSavingsBandMad(8000, { annualBillMad: 5000 });
    expect(band.high).toBe(5000);
    expect(band.low).toBe(5000); // 6720 > 5000 → plafonnée aussi
    expect(band.low).toBeLessThanOrEqual(band.high);
  });

  it('plafond entre low et high : seule la haute est rabotée', () => {
    // facture = 8000 MAD : high 10080 → 8000, low 6720 reste sous le plafond.
    const band = annualSavingsBandMad(8000, { annualBillMad: 8000 });
    expect(band.high).toBe(8000);
    expect(band.low).toBeCloseTo(6720, 0);
    expect(band.low).toBeLessThan(band.high);
  });

  it('facture haute → aucun plafonnement (comportement inchangé)', () => {
    const uncapped = annualSavingsBandMad(8000);
    const capped = annualSavingsBandMad(8000, { annualBillMad: 1_000_000 });
    expect(capped).toEqual(uncapped);
  });

  it('plafond absent/invalide → comportement d’origine (compat ascendante)', () => {
    const base = annualSavingsBandMad(8000);
    expect(annualSavingsBandMad(8000, {})).toEqual(base);
    expect(annualSavingsBandMad(8000, { annualBillMad: Number.NaN })).toEqual(base);
    expect(annualSavingsBandMad(8000, { annualBillMad: -1 })).toEqual(base);
  });
});

describe('layoutPanels — pavage à l’échelle, à l’intérieur du tracé, avec retrait', () => {
  // Toit rectangulaire 20 m (E-O) × 10 m (N-S) ≈ 200 m² à Casablanca.
  const roof = rectMeters(-7.6, 33.57, 20, 10);

  it('aire reportée = aire géodésique du tracé', () => {
    const out = layoutPanels(roof);
    expect(out.areaM2).toBeCloseTo(geodesicAreaM2(roof), 2);
  });

  it('pose des panneaux et la puissance suit le compte', () => {
    const out = layoutPanels(roof);
    expect(out.count).toBeGreaterThan(0);
    expect(out.kwc).toBeCloseTo(kwcFromPanelCount(out.count), 6);
  });

  it('chaque panneau a un anneau fermé à 5 sommets (GeoJSON)', () => {
    const out = layoutPanels(roof);
    for (const p of out.panels) {
      expect(p.length).toBe(5);
      expect(p[0]).toEqual(p[4]); // fermé
    }
  });

  it('tous les coins de panneau tombent à l’intérieur du tracé', () => {
    const out = layoutPanels(roof);
    // Projection equirectangulaire locale identique pour le test d’appartenance
    const lat0 = roof[0][1];
    const cosLat = Math.cos((lat0 * Math.PI) / 180);
    const toXY = ([lng, lat]: LngLat): [number, number] => [
      (lng - roof[0][0]) * DEG2M * cosLat,
      (lat - lat0) * DEG2M,
    ];
    const ringXY = roof.map(toXY);
    for (const panel of out.panels) {
      for (const v of panel.slice(0, 4)) {
        expect(pointInPolygon(toXY(v), ringXY)).toBe(true);
      }
    }
  });

  it('un toit plus grand porte au moins autant de panneaux (monotonie)', () => {
    const small = layoutPanels(rectMeters(-7.6, 33.57, 10, 6));
    const big = layoutPanels(rectMeters(-7.6, 33.57, 20, 12));
    expect(big.count).toBeGreaterThanOrEqual(small.count);
    expect(big.count).toBeGreaterThan(0);
  });

  it('un tracé plus petit qu’un panneau + retrait → 0 panneau (jamais d’erreur)', () => {
    const tiny = rectMeters(-7.6, 33.57, 1.5, 0.8);
    const out = layoutPanels(tiny);
    expect(out.count).toBe(0);
    expect(out.panels).toEqual([]);
    expect(out.kwc).toBe(0);
  });

  it('tracé dégénéré (< 3 sommets) → 0 panneau, 0 aire', () => {
    const out = layoutPanels([[-7.6, 33.57], [-7.5, 33.57]]);
    expect(out.count).toBe(0);
    expect(out.areaM2).toBe(0);
  });
});
