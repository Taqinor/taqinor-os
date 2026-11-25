// @vitest-environment jsdom
//
// Boot RÉEL de l'atelier (harnais `estimatorRuntimePro11.harnais.ts`) sur un dossier rouvert en PENTE : les réglages
// montrés sont ceux du type de toit du dossier. Nouveau fichier car : le module de test du boot
// (`estimatorRuntimePro10Pro11.test.ts`, 2 200 lignes) ne peut plus grossir (garde C20 FICHIER_MUR).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createRoofTypeSelect } from '../src/lib/roofTypeSelect';
import { fakeMaps, fakeMarkers, loadTool, setupDom, squareCorners } from './estimatorRuntimePro11.harnais';

describe('runtime — dossier rouvert sur un toit en pente', () => {
  beforeEach(() => {
    fakeMaps.length = 0;
    fakeMarkers.length = 0;
    setupDom();
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('no network'))));
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  // T4-X2-008 — « Toit en pente / tuiles » enfoncé mais le bloc montrait les réglages du toit PLAT ; le bloc de pente
  // restait caché, même après un nouveau clic sur le bouton déjà enfoncé.
  it('le bloc de pente est montré, le bloc plat caché, et le restent après un clic sur le bouton enfoncé', async () => {
    const doc = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'area-1',
      zones: [{ id: 'area-1', label: 'area-1', vertices: squareCorners(16, -7.62), obstacles: [], roofType: 'pitched', pitchDeg: 22,
        facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true }],
    };
    const init = await loadTool();
    init({
      maptilerKey: 'test', reducedMotion: true, roofType: createRoofTypeSelect(document),
      hydrate: { devis: { id: 5, geometrie: { roof_layout: doc as never }, cibleVendue: false } },
    });
    fakeMaps[0].fire('load', {});
    const pente = () => (document.getElementById('rp9-pitched-controls') as HTMLElement).hidden;
    const plat = () => (document.getElementById('rp9-flat-only') as HTMLElement).hidden;
    expect(document.querySelector('[data-rooftype="pitched"]')?.getAttribute('aria-pressed')).toBe('true');
    expect(pente()).toBe(false);
    expect(plat()).toBe(true);
    (document.querySelector('[data-rooftype="pitched"]') as HTMLButtonElement).click();
    expect(pente()).toBe(false);
    expect(plat()).toBe(true);
  });
});
