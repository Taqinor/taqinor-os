// ACAL262 - parseRoofLayout lit les cles publiees par ACAL261 et tolere leur absence.
import { describe, expect, it } from 'vitest';
import { parseRoofLayout } from './proposition';

const VERTS = [[-7.6001, 33.4999], [-7.5999, 33.4999], [-7.5999, 33.5001], [-7.6001, 33.5001]];
const GEO = { azimuthDeg: 180, tiltDeg: 17, family: 'south', flush: false, count: 1, origin: [-7.6, 33.5] };

describe('ACAL262 - parseRoofLayout, nouvelles cles', () => {
  it('parse modules et poseSurfaces', () => {
    const layout = parseRoofLayout({
      version: 2,
      zones: [{ id: 'z', vertices: VERTS, geometry: { ...GEO, moduleId: 'm550', mode: 'free', panels: [{ cx: 1, cy: 2, angleDeg: 17 }] } }],
      modules: [{ id: 'm550', longueurMm: 2279, largeurMm: 1134, pmaxWc: 550 }, { id: 'casse' }],
      setbacksM: { lateralM: 2, extremityM: 2, parapetM: 2, bidon: 9 },
      exclusionZones: [
        { id: 'e1', nature: 'INTERDITE', vertices: VERTS, setbackM: 1 },
        { nature: 'AUTRE', vertices: VERTS },
      ],
      poseSurfaces: [{ id: 'omb', kind: 'ombriere', engine: { tables: [] } }],
    });
    expect(layout?.modules).toEqual([{ id: 'm550', longueurMm: 2279, largeurMm: 1134, pmaxWc: 550 }]);
    expect(layout?.setbacksM).toEqual({ lateralM: 2, extremityM: 2, parapetM: 2 });
    expect(layout?.exclusionZones).toHaveLength(1);
    expect(layout?.poseSurfaces).toHaveLength(1);
    const g = layout!.zones[0].geometry!;
    expect(g.moduleId).toBe('m550');
    expect(g.mode).toBe('free');
    expect(g.panels[0].angleDeg).toBe(17);
  });

  it("tolere l'absence des nouvelles cles (anciens devis)", () => {
    const layout = parseRoofLayout({
      version: 1,
      zones: [{ id: 'z', vertices: VERTS, geometry: { ...GEO, panels: [{ cx: 1, cy: 2 }] } }],
    });
    expect(layout).not.toBeNull();
    expect(layout).not.toHaveProperty('modules');
    expect(layout).not.toHaveProperty('poseSurfaces');
    expect(layout!.zones[0].geometry!.moduleId).toBeUndefined();
    expect(layout!.zones[0].geometry!.panels[0].angleDeg).toBeUndefined();
  });
});
