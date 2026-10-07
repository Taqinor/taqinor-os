// ACAL349 — une seule constante de projection côté écran (lib/geo.ts).
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { WGS84_RADIUS as RAYON_CONSTANTS } from '../scripts/roofPro11/constants';
import { DEG2M_GEO, WGS84_RADIUS, metresParDegre } from './geo';
import { metresParDegre as viaRoof } from './roof';

const SRC = resolve(__dirname, '..');
const AUTORISES = ['lib/geo.ts', 'lib/roof.ts', 'scripts/roofPro11/constants.ts'];

function sources(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) sources(p, out);
    else if (/\.(ts|tsx|astro)$/.test(e) && !/\.test\./.test(e)) out.push(p);
  }
  return out;
}

describe('ACAL349 — projection unique', () => {
  it('une seule constante exportée, aucune copie littérale 6378137 ni 111320 hors constants.ts/roof.ts', () => {
    const fichiers = [...sources(SRC), resolve(SRC, '../../../frontend/src/pages/ventes/RoofViewer.jsx')];
    const fautifs = fichiers.filter((f) => {
      const rel = f.split(String.fromCharCode(92)).join('/');
      if (AUTORISES.some((a) => rel.endsWith(a))) return false;
      return /6[_]?378[_]?137|111[_ ]?320/.test(readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, ''));
    });
    // geo.ts est la définition unique (déplacée de constants.ts, réexportée par lui).
    expect(fautifs.map((f) => f.split(String.fromCharCode(92)).join('/')).filter((f) => !f.endsWith('lib/geo.ts'))).toEqual([]);
    expect(RAYON_CONSTANTS).toBe(WGS84_RADIUS);
    expect(viaRoof).toBe(metresParDegre);
  });

  it('viewerOnly, proposition, RoofViewer projettent le même rectangle à 0,1 %', () => {
    const lues = ['lib/proposition.ts', 'scripts/roofPro11/viewerOnly.ts'].map((f) =>
      readFileSync(resolve(SRC, f), 'utf8'),
    );
    for (const s of lues) expect(s).toMatch(/DEG2M_GEO as/);
    expect(readFileSync(resolve(SRC, '../../../frontend/src/pages/ventes/RoofViewer.jsx'), 'utf8')).toMatch(
      /DEG2M_GEO as M_PER_DEG_LAT/,
    );
    // Rectangle de Casablanca 30 m × 20 m : même dimension quelle que soit la voie.
    const lat = 33.5731;
    const { lat: mLat, lng: mLng } = metresParDegre(lat);
    const ancien = 111_320; // ancienne projection plate
    expect(Math.abs(mLat - ancien) / ancien).toBeLessThan(0.001);
    expect(mLat).toBe(DEG2M_GEO);
    const dLat = 20 / mLat;
    const dLng = 30 / mLng;
    expect(Math.abs(dLat * ancien - 20) / 20).toBeLessThan(0.001);
    expect(Math.abs(dLng * ancien * Math.cos((lat * Math.PI) / 180) - 30) / 30).toBeLessThan(0.001);
  });
});
