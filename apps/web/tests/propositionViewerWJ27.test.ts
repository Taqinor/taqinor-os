// WJ27 — Mobile, performance & fallback hardening de la visionneuse 3D.
// Logique PURE (aucun DOM, aucun Three.js) : cap DPR, détection bas de gamme,
// et la décision de démarrage/repli (WebGL absent → PNG ; reduced-motion /
// Save-Data → pas de préchargement automatique, amortissement coupé).
import { describe, expect, it } from 'vitest';
import {
  viewerDprCap,
  webglAvailable,
  detectLowEnd,
  viewerBootStrategy,
} from '../src/scripts/roofPro11/viewerOnly';

describe('WJ27 — viewerDprCap (plafond DPR bas de gamme)', () => {
  it('plafonne à 2 sur appareil normal', () => {
    expect(viewerDprCap(3, false)).toBe(2);
    expect(viewerDprCap(1.5, false)).toBe(1.5);
  });

  it('plafonne à 1,5 sur appareil bas de gamme', () => {
    expect(viewerDprCap(3, true)).toBe(1.5);
    expect(viewerDprCap(1, true)).toBe(1);
  });

  it('devicePixelRatio invalide (NaN/0/négatif) → repli 1', () => {
    expect(viewerDprCap(Number.NaN, false)).toBe(1);
    expect(viewerDprCap(0, false)).toBe(1);
    expect(viewerDprCap(-2, false)).toBe(1);
  });
});

describe('WJ27 — webglAvailable (sonde sans créer de renderer)', () => {
  it('ne jette jamais, renvoie un booléen', () => {
    expect(typeof webglAvailable()).toBe('boolean');
  });
});

describe('WJ27 — detectLowEnd (mémoire / cœurs)', () => {
  it('≤ 4 Go de RAM déclarés → bas de gamme', () => {
    expect(detectLowEnd({ deviceMemory: 4 })).toBe(true);
    expect(detectLowEnd({ deviceMemory: 2 })).toBe(true);
  });

  it('> 4 Go de RAM → pas bas de gamme (sauf peu de cœurs)', () => {
    expect(detectLowEnd({ deviceMemory: 8, hardwareConcurrency: 8 })).toBe(false);
  });

  it('≤ 4 cœurs logiques → bas de gamme', () => {
    expect(detectLowEnd({ hardwareConcurrency: 4 })).toBe(true);
    expect(detectLowEnd({ hardwareConcurrency: 2 })).toBe(true);
  });

  it('hardwareConcurrency absent → repli neutre (8, pas bas de gamme)', () => {
    expect(detectLowEnd({})).toBe(false);
  });

  it('mémoire ET cœurs confortables → pas bas de gamme', () => {
    expect(detectLowEnd({ deviceMemory: 16, hardwareConcurrency: 12 })).toBe(false);
  });
});

describe('WJ27 — viewerBootStrategy (décision de démarrage/repli)', () => {
  it('WebGL absent → jamais de boot, repli PNG immédiat', () => {
    const s = viewerBootStrategy({ webglAvailable: false });
    expect(s.canBoot).toBe(false);
    expect(s.fallbackMessage).toMatch(/indisponible/i);
    expect(s.autoPreload).toBe(false);
  });

  it('conditions normales → préchargement auto + amortissement actif', () => {
    const s = viewerBootStrategy({ webglAvailable: true, reducedMotion: false, saveData: false });
    expect(s.canBoot).toBe(true);
    expect(s.fallbackMessage).toBeNull();
    expect(s.autoPreload).toBe(true);
    expect(s.damping).toBe(true);
  });

  it('reduced-motion → pas de préchargement auto, pas d’amortissement (orbite manuelle seule)', () => {
    const s = viewerBootStrategy({ webglAvailable: true, reducedMotion: true });
    expect(s.canBoot).toBe(true);
    expect(s.autoPreload).toBe(false);
    expect(s.damping).toBe(false);
  });

  it('Save-Data actif → pas de préchargement auto (même en l’absence de reduced-motion)', () => {
    const s = viewerBootStrategy({ webglAvailable: true, reducedMotion: false, saveData: true });
    expect(s.canBoot).toBe(true);
    expect(s.autoPreload).toBe(false);
    expect(s.damping).toBe(true);
  });

  it('appareil bas de gamme → lowEnd=true propagé (DPR/anti-aliasing réduits en aval)', () => {
    const s = viewerBootStrategy({ webglAvailable: true, deviceMemory: 2 });
    expect(s.lowEnd).toBe(true);
  });

  it('webglAvailable omis (non sondé) → traité comme disponible (canBoot true)', () => {
    const s = viewerBootStrategy({});
    expect(s.canBoot).toBe(true);
  });
});
