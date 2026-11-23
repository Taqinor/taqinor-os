import { describe, it, expect, vi } from 'vitest';
import { geleDefilementPendantGeste, optionsGestesCarte } from './gestesCarte';
import { reafficherEpingleApresEffacement } from './repriseEpingle'; // ACAL1423
import { masquerMarqueur } from './epingleClient';

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

describe('ACAL1423 — Effacer : le marqueur du lead est replanté', () => {
  it('l’épingle masquée à la fermeture redevient visible, sans être retirée', () => {
    const el = { hidden: false } as HTMLElement;
    const remove = vi.fn();
    const marqueur = { remove, getElement: () => el };
    masquerMarqueur(marqueur); // fermeture du toit (ACAL972)
    expect(el.hidden).toBe(true);
    reafficherEpingleApresEffacement(marqueur); // « Effacer »
    expect(el.hidden).toBe(false);
    expect(remove).not.toHaveBeenCalled();
    masquerMarqueur(marqueur); // un nouveau tracé la masque à nouveau à la fermeture
    expect(el.hidden).toBe(true);
  });

  it('sans épingle : aucune erreur', () => {
    expect(() => reafficherEpingleApresEffacement(null)).not.toThrow();
  });
});
