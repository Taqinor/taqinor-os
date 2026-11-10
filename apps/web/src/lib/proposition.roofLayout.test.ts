// ACAL262 - parseRoofLayout lit les cles publiees par ACAL261 et tolere leur absence.
import { describe, expect, it } from 'vitest';
import { buildViewerModel, parseRoofLayout } from './proposition';

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

// ACON93 (D-ACON-4) - plafond de 2 000 PAR ZONE, fin du budget partage de 600.
describe('ACON93 - buildViewerModel, plafond par zone', () => {
  const grille = (n: number) => Array.from({ length: n }, (_, i) => ({ cx: (i % 50) * 1.2, cy: Math.floor(i / 50) * 2.3 }));
  const zone = (id: string, count: number, n: number) => ({ id, vertices: VERTS, geometry: { ...GEO, count, panels: grille(n) } });

  it('buildViewerModel : 4 x 500 dessines, zone de 2 400 simplifiee', () => {
    const quatre = buildViewerModel(parseRoofLayout({ version: 2, zones: ['a', 'b', 'c', 'd'].map((id) => zone(id, 500, 500)) }));
    expect(quatre?.totalPanels).toBe(2000);
    expect(quatre?.zones.map((z) => z.panels.length)).toEqual([500, 500, 500, 500]);
    expect(quatre?.simplifie).toBe(false);
    const grand = buildViewerModel(parseRoofLayout({ version: 2, zones: [zone('g', 2400, 2000)] }));
    expect(grand?.totalPanels).toBe(2000);
    expect(grand?.simplifie).toBe(true);
  });
});
