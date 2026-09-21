// @vitest-environment jsdom
// CÂBLAGES du lot 2 (Groupe CALX) — chaque crochet laissé par une lane de phase A/B est
// ici EXERCÉ : la fonction existait et était testée, il manquait la ligne qui l'appelle.
// Ce fichier ne prouve que ces lignes-là (aucune fonctionnalité neuve).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { createZones } from './zones';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { type LngLat } from '../../lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LAT0 = 33.59;
const LNG0 = -7.6;

/** Point donné en MÈTRES autour de (LNG0, LAT0) — x vers l'est, y vers le nord. */
function ptM(x: number, y: number): LngLat {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  return [LNG0 + x / (DEG2M * cosLat), LAT0 + y / DEG2M];
}

const CARRE: LngLat[] = [ptM(-5, -5), ptM(5, -5), ptM(5, 5), ptM(-5, 5)];

function zone(id: string, vertices: LngLat[]): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices,
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 10,
    neededAuto: true,
    result: null,
    renderPlan: null,
  };
}

function makeCtx(areas: AreaRecord[], activeId = areas[0].id): Ctx {
  const active = areas.find((a) => a.id === activeId)!;
  return {
    areas,
    activeAreaId: activeId,
    activeArea: () => areas.find((a) => a.id === activeId),
    vertices: active.vertices,
    obstacles: active.obstacles,
    closed: true,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: active.facingManual ?? false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
    dom: {},
  } as unknown as Ctx;
}

/** Le SOURCE de l'entrée du constructeur — seul endroit où vivent les lignes d'appel
 *  câblées ici (une page à effets de bord, non importable en test). Le chemin part du
 *  dossier de travail (`apps/web`, celui d'où vitest est lancé ici comme en CI) :
 *  `import.meta.url` n'est pas une URL de fichier sous jsdom. Les assertions ne portent
 *  JAMAIS sur plusieurs lignes à la fois (CRLF local). */
const SOURCE_ENTREE = readFileSync(
  resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'),
  'utf8',
);

describe('CALX97/98 câblage — la carte se redessine après une transformation de pan', () => {
  it('les quatre crochets de `createZones` sont appelés par une rotation de pan', () => {
    const areas = [zone('area-1', [...CARRE])];
    const ctx = makeCtx(areas);
    const redrawTrace = vi.fn();
    const redrawObstacles = vi.fn();
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace, redrawObstacles, recalc, setStatus });

    expect(zones.pivoterPanActif(90)).toBe(true);

    expect(redrawTrace).toHaveBeenCalledTimes(1);
    expect(redrawObstacles).toHaveBeenCalledTimes(1);
    expect(recalc).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalled();
  });

  it('un refus NOMMÉ passe par le bandeau de statut et ne redessine rien', () => {
    const areas = [zone('area-1', [...CARRE])];
    const ctx = makeCtx(areas);
    const redrawTrace = vi.fn();
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { redrawTrace, recalc, setStatus });

    expect(zones.pivoterPanActif(Number.NaN)).toBe(false);

    expect(redrawTrace).not.toHaveBeenCalled();
    expect(recalc).not.toHaveBeenCalled();
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining('Zone area-1'));
  });

  it('l’entrée du constructeur passe bien les quatre crochets à `createZones`', () => {
    expect(SOURCE_ENTREE).toContain('const zones = createZones(ctx, {');
    for (const crochet of [
      'redrawTrace: () => redrawTrace(), // CALX97 câblage',
      'redrawObstacles: () => redrawObstacles(), // CALX97 câblage',
      'recalc: () => recalc(), // CALX97 câblage',
      'setStatus: (msg: string) => setStatus(msg), // CALX97 câblage',
    ]) {
      expect(SOURCE_ENTREE).toContain(crochet);
    }
  });
});
