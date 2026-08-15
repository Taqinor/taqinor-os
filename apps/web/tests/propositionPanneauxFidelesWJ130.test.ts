// WJ130 — Le calepinage du LIEN CLIENT doit se superposer EXACTEMENT à celui de
// l'ERP (retour fondateur : « the PV shown in the ERP should be the same shown
// in the website, not creating a new rectangle »).
//
// WJ127 avait déjà branché les POSITIONS réelles (`zone.geometry.panels[].cx/cy`,
// centres posés par le builder). Ce qui restait faux, c'était l'EMPREINTE : le
// site choisissait la pose (portrait / paysage) avec une règle générique
// (« portrait sur pan incliné, paysage sur toit plat ») au lieu de celle du pack
// gagnant — donc des rectangles tournés de 90°, aux bonnes places. Et les
// chevrons Est-Ouest s'inclinaient tous du MÊME côté au lieu de dos à dos.
//
// La vérité de référence de ces tests n'est pas une constante recopiée : c'est le
// PACKER DU BUILDER lui-même (`packConfig` de lib/estimatorBrainV2, celui que
// roofPro11 fait tourner). On pave un vrai toit avec lui, on sérialise son
// résultat comme `serializeLayout` le fait (cx/cy/face seulement), et on exige
// que la visionneuse en redéduise EXACTEMENT `rowWidthM`/`slopeLenM`/la pose.
//
// Aucun DOM, aucun Three.js : fonctions pures de lib/proposition.ts.
import { describe, expect, it } from 'vitest';
import {
  buildViewerModel,
  inferPanelPose,
  parseRoofLayout,
  realZonePanels,
  VIEWER_PANEL_LONG_M,
  VIEWER_PANEL_SHORT_M,
  VIEWER_PANEL_SIDE_GAP_M,
  VIEWER_PANEL_THICK_M,
  type RoofLayoutZone,
  type RoofLayoutZoneGeometry,
} from '../src/lib/proposition';
import { packConfig, type PanelGrid } from '../src/lib/estimatorBrainV2';
import { PANEL2_LONG_M, PANEL2_SHORT_M, PANEL2_THICK_M } from '../src/lib/roofPro2';

// ── Aides géo : un toit rectangulaire réaliste au Maroc ─────────────────────
const LAT0 = 33.5;
const LNG0 = -7.6;
const DEG2M = 111_320;
const COS = Math.cos((LAT0 * Math.PI) / 180);
function at(x: number, y: number): [number, number] {
  return [LNG0 + x / (DEG2M * COS), LAT0 + y / DEG2M];
}
/** Rectangle centré (mètres) → anneau lng/lat. */
function rectLngLat(halfX: number, halfY: number): Array<[number, number]> {
  return [at(-halfX, -halfY), at(halfX, -halfY), at(halfX, halfY), at(-halfX, halfY)];
}

/** Repère ENU global centré sur l'origine du pack (cas d'une zone unique). */
function toGlobalENUAround(origin: [number, number]) {
  const [olng, olat] = origin;
  const cosLat = Math.cos((olat * Math.PI) / 180);
  return ([lng, lat]: [number, number]): [number, number] => [
    (lng - olng) * DEG2M * cosLat,
    (lat - olat) * DEG2M,
  ];
}

/**
 * Sérialise un `PanelGrid` du builder EXACTEMENT comme `serializeLayout`
 * (roofPro11/prefill.ts) : azimut, tilt, famille, flush, count, origine, et par
 * panneau `{cx, cy, face?}` — JAMAIS `rowWidthM`/`slopeLenM`/`orient`. C'est
 * précisément ce que le site reçoit et doit savoir réinterpréter.
 */
function serializeGrid(
  grid: PanelGrid,
  origin: [number, number],
  azimuthDeg: number,
  tiltDeg: number,
  family: 'south' | 'eastwest',
  flush = false,
): RoofLayoutZoneGeometry {
  return {
    azimuthDeg,
    tiltDeg,
    family,
    flush,
    count: grid.panels.length,
    origin,
    panels: grid.panels.map((p) => (p.face ? { cx: p.cx, cy: p.cy, face: p.face } : { cx: p.cx, cy: p.cy })),
  };
}

function zoneWith(
  geometry: RoofLayoutZoneGeometry | undefined,
  roofType: 'flat' | 'pitched' = 'flat',
  over: Partial<RoofLayoutZone> = {},
): RoofLayoutZone {
  return {
    id: 'z1',
    label: 'Pan',
    vertices: rectLngLat(9, 9),
    obstacles: [],
    roofType,
    pitchDeg: roofType === 'pitched' ? 20 : 0,
    facingAzimuthDeg: 180,
    neededPanels: 0,
    ...(geometry ? { geometry } : {}),
    ...over,
  };
}

// ── Les constantes du site SONT celles du builder ───────────────────────────

describe('WJ130 — constantes de panneau : le site ne réinvente rien', () => {
  it('grand/petit côté et épaisseur == lib/roofPro2 (source du builder)', () => {
    expect(VIEWER_PANEL_LONG_M).toBe(PANEL2_LONG_M);
    expect(VIEWER_PANEL_SHORT_M).toBe(PANEL2_SHORT_M);
    expect(VIEWER_PANEL_THICK_M).toBe(PANEL2_THICK_M);
  });

  it('le jeu latéral est celui du pavage (pas de colonne = largeur + jeu)', () => {
    // `PANEL_SIDE_GAP_M` n'est pas exporté par estimatorBrainV2 : on le vérifie
    // par sa CONSÉQUENCE mesurable sur un vrai pavage (voir ci-dessous), la
    // valeur ici n'étant que le miroir documenté.
    expect(VIEWER_PANEL_SIDE_GAP_M).toBe(0.02);
  });
});

// ── inferPanelPose : retrouver la pose du pack gagnant sur les seuls centres ─

describe('WJ130 — inferPanelPose : la pose se relit sur les centres posés', () => {
  const RING = rectLngLat(9, 9);

  it('pavage PORTRAIT du builder → pose « portrait » redéduite', () => {
    const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 15 });
    expect(pack.portrait.panels.length).toBeGreaterThan(3);
    const g = serializeGrid(pack.portrait, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
    expect(inferPanelPose(g)).toBe('portrait');
  });

  it('pavage PAYSAGE du builder → pose « paysage » redéduite', () => {
    const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 15 });
    expect(pack.landscape.panels.length).toBeGreaterThan(3);
    const g = serializeGrid(pack.landscape, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
    expect(inferPanelPose(g)).toBe('landscape');
  });

  it('toit TOURNÉ (azimut non canonique) → toujours la bonne pose (l’axe de rangée suit l’azimut)', () => {
    for (const azimuthDeg of [200, 145, 305]) {
      const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 12, azimuthDeg });
      for (const grid of [pack.portrait, pack.landscape]) {
        const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
        expect(inferPanelPose(g)).toBe(grid.panelOrientation);
      }
    }
  });

  it('chevrons EST-OUEST → pose du pack gagnant, malgré 2 panneaux par cellule', () => {
    const pack = packConfig(RING, LAT0, { family: 'eastwest', tiltDeg: 10 });
    for (const grid of [pack.portrait, pack.landscape]) {
      expect(grid.panels.length).toBeGreaterThan(3);
      const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'eastwest');
      // Les deux versants d'un chevron partagent la MÊME colonne (écart nul en
      // u) : ils ne doivent pas être pris pour un pas de colonne.
      expect(inferPanelPose(g)).toBe(grid.panelOrientation);
    }
  });

  it('une seule colonne occupée → null (aucune mesure possible, pas de devinette)', () => {
    const g: RoofLayoutZoneGeometry = {
      azimuthDeg: 180,
      tiltDeg: 15,
      family: 'south',
      flush: false,
      count: 3,
      origin: [LNG0, LAT0],
      // Azimut 180 → axe de rangée u = [-cos180, sin180] = [1, 0] : ces trois
      // panneaux sont empilés en y, donc tous à la MÊME abscisse de rangée.
      panels: [{ cx: 0, cy: -3 }, { cx: 0, cy: 0 }, { cx: 0, cy: 3 }],
    };
    expect(inferPanelPose(g)).toBeNull();
  });

  it('un pas DOUBLE (colonne sautée) n’est jamais lu comme l’autre pose', () => {
    // 2 × (1,303 + 0,02) = 2,646 m, à 0,24 m du pas paysage (2,404 m) : sans
    // borne, on conclurait « paysage » sur un calepinage portrait troué.
    const pitch2 = 2 * (VIEWER_PANEL_SHORT_M + VIEWER_PANEL_SIDE_GAP_M);
    const g: RoofLayoutZoneGeometry = {
      azimuthDeg: 180,
      tiltDeg: 15,
      family: 'south',
      flush: false,
      count: 2,
      origin: [LNG0, LAT0],
      panels: [{ cx: 0, cy: 0 }, { cx: pitch2, cy: 0 }],
    };
    expect(inferPanelPose(g)).toBeNull();
  });

  it('moins de 2 panneaux → null', () => {
    const g: RoofLayoutZoneGeometry = {
      azimuthDeg: 180,
      tiltDeg: 15,
      family: 'south',
      flush: false,
      count: 1,
      origin: [LNG0, LAT0],
      panels: [{ cx: 0, cy: 0 }],
    };
    expect(inferPanelPose(g)).toBeNull();
  });
});

// ── realZonePanels : rectangles == ceux du builder ──────────────────────────

describe('WJ130 — realZonePanels : le rectangle dessiné est celui du builder', () => {
  const RING = rectLngLat(9, 9);

  it.each(['portrait', 'landscape'] as const)(
    'pavage %s → alongM == rowWidthM et slopeM == slopeLenM du PanelGrid',
    (which) => {
      const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 15 });
      const grid = pack[which];
      const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
      const real = realZonePanels(zoneWith(g), toGlobalENUAround(pack.origin))!;
      expect(real).not.toBeNull();
      expect(real.pose).toBe(grid.panelOrientation);
      // Les DEUX dimensions du rectangle, telles que scene3d.ts les passe à
      // BoxGeometry(rowWidthM, slopeLenM, épaisseur).
      expect(real.alongM).toBeCloseTo(grid.rowWidthM, 9);
      expect(real.slopeM).toBeCloseTo(grid.slopeLenM, 9);
      // Empreinte au sol = longueur de pente projetée par l'inclinaison RÉELLE.
      expect(real.depthM).toBeCloseTo(grid.slopeLenM * Math.cos((pack.tiltDeg * Math.PI) / 180), 9);
      // Empreinte au sol d'un panneau : la MÊME que celle facturée par le builder.
      expect(real.alongM * real.depthM).toBeCloseTo(grid.footprintPerPanelM2, 6);
    },
  );

  it('toit PLAT pavé en PORTRAIT → le site ne force plus « paysage » (le bug du fondateur)', () => {
    const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 15 });
    const g = serializeGrid(pack.portrait, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
    // roofType 'flat' : l'ancienne règle générique donnait alongM = grand côté
    // (paysage) — un rectangle tourné de 90° par rapport à l'ERP.
    const real = realZonePanels(zoneWith(g, 'flat'), toGlobalENUAround(pack.origin))!;
    expect(real.pose).toBe('portrait');
    expect(real.alongM).toBeCloseTo(VIEWER_PANEL_SHORT_M, 9);
    expect(real.slopeM).toBeCloseTo(VIEWER_PANEL_LONG_M, 9);
  });

  it('pan INCLINÉ pavé en PAYSAGE → le site ne force plus « portrait »', () => {
    const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 20 });
    const g = serializeGrid(pack.landscape, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south', true);
    const real = realZonePanels(zoneWith(g, 'pitched'), toGlobalENUAround(pack.origin))!;
    expect(real.pose).toBe('landscape');
    expect(real.alongM).toBeCloseTo(VIEWER_PANEL_LONG_M, 9);
    expect(real.slopeM).toBeCloseTo(VIEWER_PANEL_SHORT_M, 9);
  });

  it('les CENTRES restent exacts (acquis WJ127 : jamais un re-pavage)', () => {
    const pack = packConfig(RING, LAT0, { family: 'south', tiltDeg: 15 });
    const grid = pack.best;
    const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'south');
    const real = realZonePanels(zoneWith(g), toGlobalENUAround(pack.origin))!;
    expect(real.panels).toHaveLength(grid.panels.length);
    for (let i = 0; i < grid.panels.length; i++) {
      expect(real.panels[i].x).toBeCloseTo(grid.panels[i].cx, 6);
      expect(real.panels[i].y).toBeCloseTo(grid.panels[i].cy, 6);
    }
  });

  it('EST-OUEST : chaque face de chevron est transmise telle quelle (dos à dos au rendu)', () => {
    const pack = packConfig(RING, LAT0, { family: 'eastwest', tiltDeg: 10 });
    const grid = pack.best;
    const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'eastwest');
    const real = realZonePanels(zoneWith(g), toGlobalENUAround(pack.origin))!;
    expect(real.panels).toHaveLength(grid.panels.length);
    for (let i = 0; i < grid.panels.length; i++) {
      expect(real.panels[i].face).toBe(grid.panels[i].face);
    }
    // Un chevron = 2 panneaux dos à dos : les deux faces sont présentes, en
    // nombre égal (c'est ce qui donne les toits « en A » du builder).
    const east = real.panels.filter((p) => p.face === 'E').length;
    const west = real.panels.filter((p) => p.face === 'W').length;
    expect(east).toBeGreaterThan(0);
    expect(east).toBe(west);
  });
});

// ── buildViewerModel : la zone porte tout ce qu’il faut au rendu ────────────

describe('WJ130 — buildViewerModel : la zone transporte pose, famille et flush', () => {
  const RING = rectLngLat(9, 9);

  function layoutFrom(g: RoofLayoutZoneGeometry, roofType: 'flat' | 'pitched' = 'flat') {
    return parseRoofLayout({
      version: 2,
      zones: [
        {
          id: 'z1',
          label: 'Pan',
          vertices: RING,
          obstacles: [],
          roofType,
          pitchDeg: roofType === 'pitched' ? 20 : 0,
          facingAzimuthDeg: 180,
          neededPanels: 0,
          geometry: g,
        },
      ],
    })!;
  }

  it('zone avec geometry → panelSlopeM/panelPose/family/flush viennent du builder', () => {
    const pack = packConfig(RING, LAT0, { family: 'eastwest', tiltDeg: 10 });
    const grid = pack.best;
    const g = serializeGrid(grid, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'eastwest');
    const [zone] = buildViewerModel(layoutFrom(g))!.zones;
    expect(zone.family).toBe('eastwest');
    expect(zone.flush).toBe(false);
    expect(zone.panelPose).toBe(grid.panelOrientation);
    expect(zone.panelSlopeM).toBeCloseTo(grid.slopeLenM, 9);
    expect(zone.panelAlongM).toBeCloseTo(grid.rowWidthM, 9);
    // Invariant lu par le rendu : l'empreinte au sol est la projection de la
    // longueur de pente (viewerOnly n'a plus à diviser par cos).
    expect(zone.panelDepthM).toBeCloseTo(zone.panelSlopeM * Math.cos((zone.tiltDeg * Math.PI) / 180), 9);
    expect(zone.panels.some((p) => p.face === 'E')).toBe(true);
  });

  it('le modèle reste du JSON pur (sérialisable tel quel vers la page)', () => {
    const pack = packConfig(RING, LAT0, { family: 'eastwest', tiltDeg: 10 });
    const g = serializeGrid(pack.best, pack.origin, pack.azimuthDeg, pack.tiltDeg, 'eastwest');
    const model = buildViewerModel(layoutFrom(g))!;
    expect(JSON.parse(JSON.stringify(model))).toEqual(model);
  });
});

// ── REPLI sans geometry : rigoureusement inchangé ───────────────────────────

describe('WJ130 — repli illustratif (aucune geometry) : comportement d’avant', () => {
  function fallbackModel(roofType: 'flat' | 'pitched') {
    const layout = parseRoofLayout({
      version: 2,
      zones: [
        {
          id: 'z1',
          label: 'Pan',
          vertices: rectLngLat(9, 9),
          obstacles: [],
          roofType,
          pitchDeg: roofType === 'pitched' ? 20 : 0,
          facingAzimuthDeg: 180,
          neededPanels: 8,
        },
      ],
    })!;
    expect(layout.zones[0].geometry).toBeUndefined();
    return buildViewerModel(layout)!;
  }

  it('toit PLAT : paysage + tilt visuel 15° — mêmes empreintes qu’avant WJ130', () => {
    const [zone] = fallbackModel('flat').zones;
    expect(zone.tiltDeg).toBe(15); // VIEWER_FLAT_TILT_DEG
    expect(zone.panelPose).toBe('landscape');
    expect(zone.panelAlongM).toBe(VIEWER_PANEL_LONG_M);
    expect(zone.panelSlopeM).toBe(VIEWER_PANEL_SHORT_M);
    expect(zone.panelDepthM).toBeCloseTo(VIEWER_PANEL_SHORT_M * Math.cos((15 * Math.PI) / 180), 12);
    expect(zone.panels.length).toBeGreaterThan(0);
    // Aucune face inventée : le repli n'a pas de chevrons.
    expect(zone.panels.every((p) => p.face === undefined)).toBe(true);
    expect(zone.family).toBe('south');
    expect(zone.flush).toBe(false);
  });

  it('pan INCLINÉ : portrait affleurant + pente du pan — mêmes empreintes qu’avant WJ130', () => {
    const [zone] = fallbackModel('pitched').zones;
    expect(zone.tiltDeg).toBe(20); // pitchDeg
    expect(zone.panelPose).toBe('portrait');
    expect(zone.panelAlongM).toBe(VIEWER_PANEL_SHORT_M);
    expect(zone.panelSlopeM).toBe(VIEWER_PANEL_LONG_M);
    expect(zone.panelDepthM).toBeCloseTo(VIEWER_PANEL_LONG_M * Math.cos((20 * Math.PI) / 180), 12);
    expect(zone.family).toBe('south');
    expect(zone.flush).toBe(true);
  });

  it('l’ancienne règle « empreinte ÷ cos(tilt) » et panelSlopeM donnent la MÊME valeur', () => {
    // Garde d'équivalence : le rendu lisait `panelDepthM / cos(tilt)` pour
    // retrouver la longueur de pente ; il lit désormais `panelSlopeM`. Sur le
    // repli (le seul chemin qui existait), les deux coïncident au flottant près.
    for (const roofType of ['flat', 'pitched'] as const) {
      const [zone] = fallbackModel(roofType).zones;
      const ancien = zone.panelDepthM / Math.cos((zone.tiltDeg * Math.PI) / 180);
      expect(zone.panelSlopeM).toBeCloseTo(ancien, 9);
    }
  });
});
