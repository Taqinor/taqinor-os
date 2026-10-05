// ACAL262 — la 3D publique dessine chaque pan avec SON module (cotes) et les
// tables des surfaces de pose publiées (ACAL261). Fonctions pures, sans WebGL.
import { describe, expect, it } from 'vitest';
import { PANEL2_LONG_M, PANEL2_SHORT_M } from '../../lib/roofPro2';
import { parseRoofLayout, type RoofLayoutZoneGeometry } from '../../lib/proposition';
import { buildViewerFullPlan, gridFromGeometry } from './viewerFullModel';

const M550 = { id: 'm550', longueurMm: 2279, largeurMm: 1134, pmaxWc: 550 };

function geo(extra: Partial<RoofLayoutZoneGeometry> = {}): RoofLayoutZoneGeometry {
  return {
    azimuthDeg: 180,
    tiltDeg: 17,
    family: 'south',
    flush: true, // une seule colonne => pose de repli portrait => grand cote dans la pente
    count: 1,
    origin: [-7.6, 33.5],
    panels: [{ cx: 0, cy: 0 }],
    ...extra,
  };
}

const GEO_BRUT = {
  azimuthDeg: 180,
  tiltDeg: 17,
  family: 'south',
  flush: true,
  count: 1,
  origin: [-7.6, 33.5],
  panels: [{ cx: 0, cy: 0 }],
};

function layoutBrut(zoneGeo: Record<string, unknown>, extra: Record<string, unknown> = {}) {
  return {
    version: 2,
    zones: [
      {
        id: 'z1',
        label: 'Pan 1',
        vertices: [[-7.6001, 33.4999], [-7.5999, 33.4999], [-7.5999, 33.5001], [-7.6001, 33.5001]],
        geometry: zoneGeo,
      },
    ],
    ...extra,
  };
}

describe('ACAL262 - grille au module du pan', () => {
  it('grille au module du pan (slopeLenM 2.279)', () => {
    const grid = gridFromGeometry(geo({ moduleId: 'm550' }), [M550]);
    expect(grid.slopeLenM).toBeCloseTo(2.279, 6);
    expect(grid.rowWidthM).toBeCloseTo(1.134, 6);
    expect(grid.kwc).toBeCloseTo(0.55, 6);
  });

  it('repli PANEL2_* seulement sans module (ancien devis, module inconnu)', () => {
    for (const grid of [
      gridFromGeometry(geo()),
      gridFromGeometry(geo({ moduleId: 'm550' }), []),
      gridFromGeometry(geo({ moduleId: 'inconnu' }), [M550]),
    ]) {
      expect(grid.slopeLenM).toBe(PANEL2_LONG_M);
      expect(grid.rowWidthM).toBe(PANEL2_SHORT_M);
    }
  });

  it('deux pans, deux modules : chacun garde SES cotes', () => {
    const autre = { id: 'm400', longueurMm: 1722, largeurMm: 1134, pmaxWc: 400 };
    expect(gridFromGeometry(geo({ moduleId: 'm400' }), [M550, autre]).slopeLenM).toBeCloseTo(1.722, 6);
    expect(gridFromGeometry(geo({ moduleId: 'm550' }), [M550, autre]).slopeLenM).toBeCloseTo(2.279, 6);
  });

  it('angleDeg du mode free est porte par le panneau', () => {
    const grid = gridFromGeometry(
      geo({ mode: 'free', moduleId: 'm550', panels: [{ cx: 0, cy: 0, angleDeg: 17 }] }),
      [M550],
    );
    expect((grid.panels[0] as { angleDeg?: number }).angleDeg).toBe(17);
  });
});

describe('ACAL262 - tables des surfaces de pose', () => {
  it('tables de surface de pose', () => {
    const layout = parseRoofLayout(
      layoutBrut(
        { ...GEO_BRUT, moduleId: 'm550' },
        {
          modules: [M550],
          poseSurfaces: [
            { id: 'omb1', kind: 'ombriere', tiltDeg: 10, engine: { modules: 60, rowPitchM: 5, tables: [{ x0: 0, x1: 6, y0: 0, y1: 2.3 }] } },
            { id: 'poubelle', kind: 'inconnu' },
          ],
        },
      ),
    );
    const plan = buildViewerFullPlan(layout);
    expect(plan).not.toBeNull();
    expect(plan!.surfacesPose).toHaveLength(1); // le genre inconnu est ignore
    expect(plan!.surfacesPose[0].engine?.tables).toEqual([{ x0: 0, x1: 6, y0: 0, y1: 2.3 }]);
    expect(plan!.zones[0].plan!.grid.slopeLenM).toBeCloseTo(2.279, 6);
  });

  it('un ancien devis (sans les nouvelles cles) reste rendu, sans surface', () => {
    const plan = buildViewerFullPlan(parseRoofLayout(layoutBrut(GEO_BRUT)));
    expect(plan!.surfacesPose).toEqual([]);
    expect(plan!.zones[0].plan!.grid.slopeLenM).toBe(PANEL2_LONG_M);
  });
});
