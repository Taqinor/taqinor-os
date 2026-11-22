import { describe, it, expect, vi } from 'vitest';
import { geleDefilementPendantGeste, optionsGestesCarte } from './gestesCarte';

describe('ACAL952 — gestes de la carte au toucher', () => {
  it('pointeur tactile : gestes coopératifs et libellé français', () => {
    const o = optionsGestesCarte({ matchMedia: (q) => ({ matches: q === '(pointer: coarse)' }) });
    expect(o.cooperativeGestures).toBe(true);
    expect(o.locale?.['CooperativeGesturesHandler.MobileHelpText']).toMatch(/deux doigts/);
  });

  it('pointeur fin ou sans matchMedia : pas de gestes coopératifs', () => {
    expect(optionsGestesCarte({ matchMedia: () => ({ matches: false }) }).cooperativeGestures).toBe(false);
    expect(optionsGestesCarte({}).cooperativeGestures).toBe(false);
  });

  it("annule l'événement DOM seulement quand un geste est actif", () => {
    const preventDefault = vi.fn();
    geleDefilementPendantGeste({ originalEvent: { preventDefault } }, false);
    expect(preventDefault).not.toHaveBeenCalled();
    geleDefilementPendantGeste({ originalEvent: { preventDefault } }, true);
    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(() => geleDefilementPendantGeste({}, true)).not.toThrow();
  });
});
