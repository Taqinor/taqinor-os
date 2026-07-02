// WJ25 — Visionneuse 3D en lecture seule : logique PURE (parse défensif du
// roof_layout backend, conversion ENU, calepinage illustratif). Aucun DOM,
// aucun Three.js : ces fonctions sont la source de vérité géométrique que
// roofPro11/viewerOnly.ts ne fait que dessiner.
import { describe, expect, it } from 'vitest';
import {
  parseRoofLayout,
  packZonePanels,
  buildViewerModel,
  viewerPointInRing,
  VIEWER_MAX_PANELS,
  VIEWER_SETBACK_M,
} from '../src/lib/proposition';

// ── Aides : un « toit » carré réaliste au Maroc (lng/lat autour de Casablanca).
const LAT0 = 33.5;
const LNG0 = -7.6;
const DEG2M = 111_320;
const COS = Math.cos((LAT0 * Math.PI) / 180);
/** Sommet lng/lat à (x, y) mètres du centre. */
function at(x: number, y: number): [number, number] {
  return [LNG0 + x / (DEG2M * COS), LAT0 + y / DEG2M];
}
/** Carré de demi-côté `half` mètres (lng/lat). */
function squareLngLat(half: number): Array<[number, number]> {
  return [at(-half, -half), at(half, -half), at(half, half), at(-half, half)];
}

function validRawLayout(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: 1,
    pin: { lat: LAT0, lng: LNG0 },
    outline: [],
    billKwh: 9000,
    activeAreaId: 'z1',
    zones: [
      {
        id: 'z1',
        label: 'Pan principal',
        vertices: squareLngLat(7),
        obstacles: [],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        facingManual: false,
        neededPanels: 8,
        neededAuto: true,
      },
    ],
    ...over,
  };
}

// ── parseRoofLayout — parse DÉFENSIF (jamais de throw, null si inexploitable) ─

describe('WJ25 — parseRoofLayout (contrat backend optionnel QJ26)', () => {
  it('absent / malformé → null (la page garde le héros statique)', () => {
    expect(parseRoofLayout(undefined)).toBeNull();
    expect(parseRoofLayout(null)).toBeNull();
    expect(parseRoofLayout('x')).toBeNull();
    expect(parseRoofLayout(42)).toBeNull();
    expect(parseRoofLayout({})).toBeNull();
    expect(parseRoofLayout({ zones: 'nope' })).toBeNull();
    expect(parseRoofLayout({ zones: [] })).toBeNull();
  });

  it('zone avec moins de 3 sommets valides → écartée (aucune zone → null)', () => {
    const raw = validRawLayout({
      zones: [{ id: 'z1', vertices: [at(0, 0), at(1, 1)], roofType: 'flat' }],
    });
    expect(parseRoofLayout(raw)).toBeNull();
  });

  it('sommets non finis / hors bornes lng-lat → filtrés', () => {
    const raw = validRawLayout({
      zones: [
        {
          id: 'z1',
          label: 'Pan',
          vertices: [...squareLngLat(7), [NaN, 33], [999, 33], ['a', 'b']],
          roofType: 'flat',
          neededPanels: 4,
        },
      ],
    });
    const parsed = parseRoofLayout(raw);
    expect(parsed).not.toBeNull();
    expect(parsed!.zones[0].vertices).toHaveLength(4);
  });

  it('layout serializeLayout-conforme → zones typées avec valeurs sûres', () => {
    const parsed = parseRoofLayout(validRawLayout());
    expect(parsed).not.toBeNull();
    const z = parsed!.zones[0];
    expect(z.id).toBe('z1');
    expect(z.roofType).toBe('flat');
    expect(z.pitchDeg).toBe(0);
    expect(z.facingAzimuthDeg).toBe(180);
    expect(z.neededPanels).toBe(8);
  });

  it('azimut normalisé 0–360, pente bornée, neededPanels entier ≥ 0', () => {
    const raw = validRawLayout({
      zones: [
        {
          id: 'z1',
          label: 'Pan',
          vertices: squareLngLat(7),
          roofType: 'pitched',
          pitchDeg: 999,
          facingAzimuthDeg: -90,
          neededPanels: 5.9,
        },
      ],
    });
    const z = parseRoofLayout(raw)!.zones[0];
    expect(z.facingAzimuthDeg).toBe(270);
    expect(z.pitchDeg).toBe(60); // borné
    expect(z.neededPanels).toBe(5);
  });

  it('obstacles invalides filtrés, valides conservés', () => {
    const [oLng, oLat] = at(0, 0);
    const raw = validRawLayout({
      zones: [
        {
          id: 'z1',
          label: 'Pan',
          vertices: squareLngLat(7),
          roofType: 'flat',
          neededPanels: 0,
          obstacles: [
            { centerLng: oLng, centerLat: oLat, lengthM: 2, widthM: 1.5 },
            { centerLng: NaN, centerLat: oLat, lengthM: 2, widthM: 1.5 },
            { centerLng: oLng, centerLat: oLat, lengthM: 0, widthM: 1.5 },
          ],
        },
      ],
    });
    expect(parseRoofLayout(raw)!.zones[0].obstacles).toHaveLength(1);
  });
});

// ── packZonePanels — calepinage illustratif (dans le contour, hors obstacles) ─

describe('WJ25 — packZonePanels (géométrie pure)', () => {
  const ring: Array<[number, number]> = [[-6, -6], [6, -6], [6, 6], [-6, 6]];

  it('pose des panneaux dans un carré 12×12 m, tous entièrement dans le contour', () => {
    const { panels, alongM, depthM } = packZonePanels(ring, 180, 15, 'flat', 0);
    expect(panels.length).toBeGreaterThan(0);
    for (const p of panels) {
      expect(viewerPointInRing([p.x, p.y], ring)).toBe(true);
      // Retrait de rive respecté (au moins le setback jusqu'au bord du carré).
      expect(Math.abs(p.x)).toBeLessThanOrEqual(6 - VIEWER_SETBACK_M);
      expect(Math.abs(p.y)).toBeLessThanOrEqual(6 - VIEWER_SETBACK_M);
    }
    expect(alongM).toBeGreaterThan(0);
    expect(depthM).toBeGreaterThan(0);
  });

  it('plafonne à neededPanels quand > 0', () => {
    const { panels } = packZonePanels(ring, 180, 15, 'flat', 3);
    expect(panels).toHaveLength(3);
  });

  it('sans neededPanels (0) : borne dure VIEWER_MAX_PANELS', () => {
    const big: Array<[number, number]> = [[-80, -80], [80, -80], [80, 80], [-80, 80]];
    const { panels } = packZonePanels(big, 180, 15, 'flat', 0);
    expect(panels.length).toBeLessThanOrEqual(VIEWER_MAX_PANELS);
    expect(panels.length).toBeGreaterThan(50);
  });

  it('exclut les cellules sur un obstacle', () => {
    const withObs = packZonePanels(ring, 180, 15, 'flat', 0, [
      { x: 0, y: 0, widthM: 4, lengthM: 4 },
    ]);
    const without = packZonePanels(ring, 180, 15, 'flat', 0);
    expect(withObs.panels.length).toBeLessThan(without.panels.length);
    for (const p of withObs.panels) {
      // Aucun centre de panneau dans le rectangle d'obstacle.
      expect(Math.abs(p.x) <= 2 && Math.abs(p.y) <= 2).toBe(false);
    }
  });

  it('toit trop petit pour un panneau → aucun panneau (jamais de débordement)', () => {
    const tiny: Array<[number, number]> = [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]];
    expect(packZonePanels(tiny, 180, 15, 'flat', 4).panels).toHaveLength(0);
  });
});

// ── buildViewerModel — modèle complet (JSON pur, calculé côté serveur) ────────

describe('WJ25 — buildViewerModel', () => {
  it('null layout → null', () => {
    expect(buildViewerModel(null)).toBeNull();
  });

  it('construit zones ENU + rayon + total panneaux', () => {
    const layout = parseRoofLayout(validRawLayout())!;
    const model = buildViewerModel(layout)!;
    expect(model).not.toBeNull();
    expect(model.zones).toHaveLength(1);
    expect(model.totalPanels).toBe(model.zones[0].panels.length);
    // 8 panneaux demandés dans 14×14 m → exactement 8 posés.
    expect(model.totalPanels).toBe(8);
    expect(model.radiusM).toBeGreaterThanOrEqual(6);
    // L'anneau ENU est centré autour de l'origine (centroïde global).
    const [sx, sy] = model.zones[0].ringENU.reduce(
      ([ax, ay], [x, y]) => [ax + x, ay + y],
      [0, 0],
    );
    expect(Math.abs(sx / 4)).toBeLessThan(0.5);
    expect(Math.abs(sy / 4)).toBeLessThan(0.5);
  });

  it('zone en pente : inclinaison = pente du pan ; plate : châssis visuel', () => {
    const raw = validRawLayout({
      zones: [
        {
          id: 'z1', label: 'Pan sud', vertices: squareLngLat(7),
          roofType: 'pitched', pitchDeg: 25, facingAzimuthDeg: 180, neededPanels: 4,
        },
        {
          id: 'z2', label: 'Terrasse', vertices: squareLngLat(7).map(([lng, lat]) => [lng + 0.0004, lat] as [number, number]),
          roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, neededPanels: 4,
        },
      ],
    });
    const model = buildViewerModel(parseRoofLayout(raw)!)!;
    expect(model.zones[0].tiltDeg).toBe(25);
    expect(model.zones[1].tiltDeg).toBeGreaterThan(0); // châssis visuel (constante)
    expect(model.totalPanels).toBe(8);
  });

  it('le modèle est du JSON pur (sérialisable tel quel vers le client)', () => {
    const model = buildViewerModel(parseRoofLayout(validRawLayout())!)!;
    const round = JSON.parse(JSON.stringify(model));
    expect(round).toEqual(model);
  });
});
