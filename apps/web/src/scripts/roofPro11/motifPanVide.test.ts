// ACAL1966 — la cause d'un pan vide quand l'anneau posable est vide, mesurée par la VRAIE chaîne
// `anneauPosableParArete` → `packConfig` → `mesurerPanVide` → `causeDuPanVide` (celle de
// `optimizer.ts::paveDuGagnant`). La phrase part telle quelle sur la planche PDF : la cause doit être VRAIE.
import { describe, expect, it } from 'vitest';
import { packConfig } from '../../lib/estimatorBrainV2';
import { anneauPosableParArete } from '../../lib/estimatorBrainV7';
import { cotesDePavage } from '../../lib/roofPro2';
import type { LngLat } from '../../lib/roof';
import { causeDuPanVide, contourPanENU, mesurerPanVide, retraitApplique } from './motifPanVide';

const MODULE = cotesDePavage(undefined);
const LAT = 33.57;
const C = Math.cos((LAT * Math.PI) / 180);
const pt = (dx: number, dy: number): LngLat => [-7.6 + dx / (111320 * C), LAT + dy / 111320];
const rect = (l: number, h: number): LngLat[] => [pt(0, 0), pt(l, 0), pt(l, h), pt(0, h)];

/** Le pan, ses retraits d'arête (rang → m) et le retrait de rive R, par la chaîne de `paveDuGagnant`. */
function motif(pan: LngLat[], retraitsParArete: Record<number, number>, R: number) {
  const anneau = anneauPosableParArete([...pan], retraitsParArete);
  const pack = packConfig(anneau, LAT, { family: 'south', tiltDeg: 13, setbackM: R });
  expect(pack.best.count).toBe(0);
  return causeDuPanVide(mesurerPanVide(pack, pack.best, retraitApplique(undefined, R), MODULE, null,
    contourPanENU(pan), retraitsParArete));
}

describe('ACAL1966 — pan vide, anneau posable et retraits d\'arête', () => {
  it('A — pan 6 × 3 m, retraits d\'arête 1,60 m sur les deux longs côtés : anneau vide, la cause nomme ces retraits', () => {
    const m = motif(rect(6, 3), { 0: 1.6, 2: 1.6 }, 0.5);
    expect(m.code).toBe('retrait_rive');
    expect(m.message).toBe('Aucun module : aucun anneau posable — les retraits saisis sur 2 arêtes (1,60 m et 1,60 m) ne laissent aucune surface sur ce pan de 3,00 m de large');
    expect(m.message).not.toContain('ne tient pas');
    expect(m.mesures).toMatchObject({ retraitM: 0.5, largeurPanM: 3, largeurUtileM: 0 });
  });

  it('B — anneau rogné à 1,60 m par les retraits d\'arête : la phrase d\'avant, mesurée sur l\'anneau', () => {
    const m = motif(rect(6, 3), { 0: 0.7, 2: 0.7 }, 0.5);
    expect(m.code).toBe('retrait_rive');
    expect(m.message).toBe('Aucun module : le retrait de rive (0,50 m de chaque côté) ne laisse que 0,60 m sur 1,60 m de large');
  });

  it('C — aucun retrait d\'arête : phrase inchangée', () => {
    const m = motif(rect(6, 1.8), {}, 0.5);
    expect(m.message).toBe('Aucun module : le retrait de rive (0,50 m de chaque côté) ne laisse que 0,80 m sur 1,80 m de large');
  });

  it('anneau posable vide sans contour ⇒ « aucun anneau posable », jamais « ne laisse que 0,00 m sur 0,00 m »', () => {
    const pack = { ringENU: [], areaM2: 0, usableAreaM2: 0 } as unknown as Parameters<typeof mesurerPanVide>[0];
    const grille = { panels: [] } as unknown as Parameters<typeof mesurerPanVide>[1];
    const m = causeDuPanVide(mesurerPanVide(pack, grille, retraitApplique(undefined, 0.8), MODULE, null));
    expect(m.code).toBe('retrait_rive');
    expect(m.message).toBe('Aucun module : aucun anneau posable — le retrait de rive (0,80 m de chaque côté) ne laisse aucune surface sur ce pan');
    expect(m.message).not.toContain('0,00 m sur 0,00 m');
    expect(m.mesures).toMatchObject({ retraitM: 0.8, largeurPanM: 0, largeurUtileM: 0 });
  });

  it('anneau vide + contour du pan, sans retrait d\'arête ⇒ le message cite la largeur du pan (R suffit à le vider)', () => {
    const pack = { ringENU: [], areaM2: 0, usableAreaM2: 0 } as unknown as Parameters<typeof mesurerPanVide>[0];
    const grille = { panels: [] } as unknown as Parameters<typeof mesurerPanVide>[1];
    const m = causeDuPanVide(mesurerPanVide(pack, grille, retraitApplique(undefined, 0.8), MODULE, null, [[0, 0], [3, 0], [3, 1.5], [0, 1.5]]));
    expect(m.message).toBe('Aucun module : aucun anneau posable — le retrait de rive (0,80 m de chaque côté) ne laisse aucune surface sur ce pan de 1,50 m de large');
    expect(m.mesures).toMatchObject({ retraitM: 0.8, largeurPanM: 1.5, largeurUtileM: 0 });
  });
});
