// WJ127 — Calepinage RÉEL du toit (roof_layout.zones[].geometry, PV27) : la
// visionneuse doit dessiner les panneaux EXACTS conçus dans l'ERP (le plan
// gagnant sérialisé par roofPro11/prefill.ts serializeLayout — cellules
// réellement occupées), jamais un re-pavage illustratif — SAUF repli total
// quand `geometry` est absente ou invalide (layout ancien en base, ou backend
// qui ne l'a pas encore republiée dans _safe_roof_layout). Aucun DOM, aucun
// Three.js : mêmes garanties que propositionViewerWJ25.test.ts.
import { describe, expect, it } from 'vitest';
import {
  parseRoofLayout,
  buildViewerModel,
  realZonePanels,
  zoneAnnotations,
  type RoofLayoutZone,
} from '../src/lib/proposition';

// ── Aides : un « toit » carré réaliste au Maroc (lng/lat autour de Casablanca),
// MÊME convention que propositionViewerWJ25.test.ts (x=Est, y=Nord, mètres).
const LAT0 = 33.5;
const LNG0 = -7.6;
const DEG2M = 111_320;
const COS = Math.cos((LAT0 * Math.PI) / 180);
function at(x: number, y: number): [number, number] {
  return [LNG0 + x / (DEG2M * COS), LAT0 + y / DEG2M];
}
function squareLngLat(half: number): Array<[number, number]> {
  return [at(-half, -half), at(half, -half), at(half, half), at(-half, half)];
}

/** `zone.geometry` valide (voir SerializedZoneGeometry — roofPro11/prefill.ts). */
function validGeometryRaw(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    azimuthDeg: 180,
    tiltDeg: 13,
    family: 'south',
    flush: false,
    count: 2,
    origin: [LNG0, LAT0],
    panels: [
      { cx: -1.5, cy: 0 },
      { cx: 1.5, cy: 0, face: 'E' },
    ],
    ...over,
  };
}

function validRawLayout(zoneOver: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    version: 2,
    zones: [
      {
        id: 'z1',
        label: 'Pan principal',
        vertices: squareLngLat(7),
        obstacles: [],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        // « Cible » d'étude délibérément DIFFÉRENTE du posé (geometry.count)
        // — reproduit le bug d'origine (légende ≠ bloc devis).
        neededPanels: 20,
        ...zoneOver,
      },
    ],
  };
}

// ── parseRoofLayout — parse DÉFENSIF de zone.geometry ────────────────────────

describe('WJ127 — parseRoofLayout : zone.geometry (calepinage RÉEL)', () => {
  it('geometry valide → conservée sur la zone, avec les bons champs', () => {
    const parsed = parseRoofLayout(validRawLayout({ geometry: validGeometryRaw() }))!;
    const g = parsed.zones[0].geometry;
    expect(g).toBeDefined();
    expect(g!.azimuthDeg).toBe(180);
    expect(g!.tiltDeg).toBe(13);
    expect(g!.family).toBe('south');
    expect(g!.flush).toBe(false);
    expect(g!.count).toBe(2);
    expect(g!.origin).toEqual([LNG0, LAT0]);
    expect(g!.panels).toHaveLength(2);
    expect(g!.panels[0]).toEqual({ cx: -1.5, cy: 0 });
    expect(g!.panels[1]).toMatchObject({ cx: 1.5, cy: 0, face: 'E' });
  });

  it('azimut normalisé 0–360, tilt borné [0,60] — même discipline que le reste de la zone', () => {
    const g = parseRoofLayout(
      validRawLayout({ geometry: validGeometryRaw({ azimuthDeg: -90, tiltDeg: 999 }) }),
    )!.zones[0].geometry!;
    expect(g.azimuthDeg).toBe(270);
    expect(g.tiltDeg).toBe(60);
  });

  it.each([
    ['absente', undefined],
    ['null', null],
    ['pas un objet', 'nope'],
    ['azimuthDeg manquant', validGeometryRaw({ azimuthDeg: undefined })],
    ['tiltDeg non fini', validGeometryRaw({ tiltDeg: NaN })],
    ['family inconnue', validGeometryRaw({ family: 'diagonale' })],
    ['origin absente', validGeometryRaw({ origin: undefined })],
    ['origin tronquée (1 seul élément)', validGeometryRaw({ origin: [LNG0] })],
    ['origin hors bornes', validGeometryRaw({ origin: [999, 999] })],
    ['panels absents', validGeometryRaw({ panels: undefined })],
    ['panels vide', validGeometryRaw({ panels: [] })],
    ['aucun panel exploitable (cx/cy non finis)', validGeometryRaw({ panels: [{ cx: 'a', cy: 0 }] })],
  ])('geometry malformée (%s) → jamais de throw, zone gardée SANS geometry', (_label, geometry) => {
    let parsed: ReturnType<typeof parseRoofLayout> = null;
    expect(() => {
      parsed = parseRoofLayout(validRawLayout({ geometry }));
    }).not.toThrow();
    expect(parsed).not.toBeNull();
    expect(parsed!.zones).toHaveLength(1);
    expect(parsed!.zones[0].geometry).toBeUndefined();
    // Le reste de la zone reste parfaitement exploitable (repli illustratif intact).
    expect(parsed!.zones[0].neededPanels).toBe(20);
    expect(parsed!.zones[0].vertices).toHaveLength(4);
  });

  it('un seul panneau invalide au milieu d’une liste → filtré, les autres conservés', () => {
    const g = parseRoofLayout(
      validRawLayout({
        geometry: validGeometryRaw({
          panels: [{ cx: -1, cy: 0 }, { cx: 'oops', cy: 0 }, { cx: 1, cy: 0 }],
        }),
      }),
    )!.zones[0].geometry!;
    expect(g.panels).toHaveLength(2);
  });

  it('count absent/incohérent → repli sur panels.length (jamais un chiffre inventé)', () => {
    const g = parseRoofLayout(
      validRawLayout({ geometry: validGeometryRaw({ count: undefined }) }),
    )!.zones[0].geometry!;
    expect(g.count).toBe(2); // == panels.length
  });

  it('un layout SANS geometry reste un layout valide (zéro régression sur un devis ancien)', () => {
    const parsed = parseRoofLayout(validRawLayout())!;
    expect(parsed.zones[0].geometry).toBeUndefined();
    expect(parsed.zones[0].neededPanels).toBe(20);
  });
});

// ── realZonePanels — g→rectangles à dessiner (fonction pure, cas simple) ─────

describe('WJ127 — realZonePanels (geometry → panneaux dessinés, repère cohérent)', () => {
  it('sans geometry → null (l’appelant retombe sur packZonePanels)', () => {
    const zone: RoofLayoutZone = {
      id: 'z1',
      label: 'Pan',
      vertices: squareLngLat(7),
      obstacles: [],
      roofType: 'flat',
      pitchDeg: 0,
      facingAzimuthDeg: 180,
      neededPanels: 4,
    };
    expect(realZonePanels(zone, (pt) => pt)).toBeNull();
  });

  it('géométrie identique au centroïde global : cx/cy se retrouvent EXACTEMENT en ENU', () => {
    // Repère GLOBAL centré exactement sur geometry.origin (cas réel le plus
    // courant : une seule zone, son origin == le centroïde global calculé par
    // buildViewerModel) — même conversion ENU (x=Est,y=Nord) que
    // roofPro2.ts/estimatorBrainV2.ts, aller-retour lat/lng EXACT.
    const olat = LAT0;
    const olng = LNG0;
    const cosLat = Math.cos((olat * Math.PI) / 180);
    const toGlobalENU = ([lng, lat]: [number, number]): [number, number] => [
      (lng - olng) * DEG2M * cosLat,
      (lat - olat) * DEG2M,
    ];
    const zone: RoofLayoutZone = {
      id: 'z1',
      label: 'Pan',
      vertices: squareLngLat(7),
      obstacles: [],
      roofType: 'flat',
      pitchDeg: 0,
      facingAzimuthDeg: 180,
      neededPanels: 20,
      geometry: {
        azimuthDeg: 180,
        tiltDeg: 13,
        family: 'south',
        flush: false,
        count: 2,
        origin: [olng, olat],
        panels: [
          { cx: -1.5, cy: 0.4 },
          { cx: 1.5, cy: -0.4, face: 'E' },
        ],
      },
    };
    const real = realZonePanels(zone, toGlobalENU)!;
    expect(real).not.toBeNull();
    expect(real.panels).toHaveLength(2);
    expect(real.panels[0].x).toBeCloseTo(-1.5, 6);
    expect(real.panels[0].y).toBeCloseTo(0.4, 6);
    expect(real.panels[1].x).toBeCloseTo(1.5, 6);
    expect(real.panels[1].y).toBeCloseTo(-0.4, 6);
    // Empreinte panneau : positive, dépend de l'inclinaison RÉELLE (13°), pas
    // d'une constante de repli.
    expect(real.alongM).toBeGreaterThan(0);
    expect(real.depthM).toBeGreaterThan(0);
  });

  it('géométrie sans panneau exploitable → null', () => {
    const zone: RoofLayoutZone = {
      id: 'z1',
      label: 'Pan',
      vertices: squareLngLat(7),
      obstacles: [],
      roofType: 'flat',
      pitchDeg: 0,
      facingAzimuthDeg: 180,
      neededPanels: 4,
      geometry: {
        azimuthDeg: 180,
        tiltDeg: 13,
        family: 'south',
        flush: false,
        count: 0,
        origin: [LNG0, LAT0],
        panels: [],
      },
    };
    expect(realZonePanels(zone, (pt) => pt)).toBeNull();
  });
});

// ── buildViewerModel — la géométrie RÉELLE pilote le rendu, pas un re-pavage ─

describe('WJ127 — buildViewerModel : priorité au calepinage RÉEL', () => {
  it('zone avec geometry → le modèle dessine EXACTEMENT ces panneaux (pas un re-pavage)', () => {
    const raw = validRawLayout({ geometry: validGeometryRaw() });
    const model = buildViewerModel(parseRoofLayout(raw)!)!;
    expect(model.zones).toHaveLength(1);
    // 2 panneaux RÉELS posés — PAS les 20 de neededPanels (qui aurait pavé le
    // toit avec packZonePanels si le repli illustratif s'était déclenché).
    expect(model.zones[0].panels).toHaveLength(2);
    expect(model.totalPanels).toBe(2);
    // L'inclinaison/l'azimut RENDUS viennent de geometry (13°/180°), pas du
    // repli illustratif (pitchDeg=0 → VIEWER_FLAT_TILT_DEG aurait donné 15°).
    expect(model.zones[0].tiltDeg).toBe(13);
    expect(model.zones[0].azimuthDeg).toBe(180);
  });

  it('zone SANS geometry → repli illustratif inchangé (zéro régression)', () => {
    const raw = validRawLayout(); // pas de champ geometry
    const model = buildViewerModel(parseRoofLayout(raw)!)!;
    // neededPanels: 20 dans un carré 14×14 m → repavage illustratif classique.
    expect(model.zones[0].panels.length).toBeGreaterThan(0);
    expect(model.zones[0].tiltDeg).toBe(15); // VIEWER_FLAT_TILT_DEG (toit plat)
  });

  it('le modèle avec geometry reste du JSON pur (sérialisable tel quel)', () => {
    const raw = validRawLayout({ geometry: validGeometryRaw() });
    const model = buildViewerModel(parseRoofLayout(raw)!)!;
    const round = JSON.parse(JSON.stringify(model));
    expect(round).toEqual(model);
  });
});

// ── zoneAnnotations — la légende affiche le POSÉ réel, pas la cible d'étude ──

describe('WJ127 — zoneAnnotations : geometry.count prioritaire sur neededPanels', () => {
  it('geometry présente → la légende affiche le posé RÉEL (count), pas la cible (neededPanels)', () => {
    // neededPanels: 20 (cible d'étude) vs geometry.count: 2 (réellement posé)
    // — le même écart que le bug confirmé (bloc devis affiche q.nb_panneaux
    // == posé, la légende affichait jusqu'ici la cible).
    const layout = parseRoofLayout(validRawLayout({ geometry: validGeometryRaw() }))!;
    const [a] = zoneAnnotations(layout, 720);
    expect(a.panels).toBe(2);
    expect(a.kwc).toBeCloseTo((2 * 720) / 1000, 6);
  });

  it('sans geometry → repli sur neededPanels (comportement historique)', () => {
    const layout = parseRoofLayout(validRawLayout())!;
    const [a] = zoneAnnotations(layout, 720);
    expect(a.panels).toBe(20);
  });
});
