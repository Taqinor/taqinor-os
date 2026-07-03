// WJ90 — clavier sur la visionneuse 3D de la proposition : tabindex + flèches
// pour tourner + +/- pour zoomer, hint copy mise à jour dans les 3 langues.
// Les constantes (KEY_ROTATE_RAD/KEY_ZOOM_SCALE) sont pures — importées
// directement. Le câblage DOM (canvas focusable, gestionnaire keydown,
// nettoyage à dispose()) est vérifié en LECTURE SOURCE (même convention que
// mobilePerfWJ18.test.ts) : construire un vrai contexte WebGL/Three.js en
// test unitaire serait fragile et hors du périmètre de ce module pur.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { KEY_ROTATE_RAD, KEY_ZOOM_SCALE } from '../src/scripts/roofPro11/viewerOnly';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const VIEWER_ONLY = read('../src/scripts/roofPro11/viewerOnly.ts');
const PROPOSITION = read('../src/pages/proposition/[token].astro');

describe('WJ90 — constantes de pas clavier (pures)', () => {
  it('KEY_ROTATE_RAD est un angle raisonnable (quelques degrés)', () => {
    expect(KEY_ROTATE_RAD).toBeGreaterThan(0);
    expect(KEY_ROTATE_RAD).toBeLessThan(Math.PI / 4); // < 45°, jamais un saut brutal
  });

  it('KEY_ZOOM_SCALE est un facteur multiplicatif > 1 (dollyIn/dollyOut)', () => {
    expect(KEY_ZOOM_SCALE).toBeGreaterThan(1);
    expect(KEY_ZOOM_SCALE).toBeLessThan(2);
  });
});

describe('WJ90 — canvas focusable + gestionnaire clavier (viewerOnly.ts)', () => {
  it('pose tabIndex sur le canvas (focusable au clavier)', () => {
    expect(VIEWER_ONLY).toMatch(/canvas\.tabIndex\s*=\s*0/);
  });

  it('gère ArrowLeft/ArrowRight/ArrowUp/ArrowDown via rotateLeft/rotateUp', () => {
    expect(VIEWER_ONLY).toContain("case 'ArrowLeft'");
    expect(VIEWER_ONLY).toContain("case 'ArrowRight'");
    expect(VIEWER_ONLY).toContain("case 'ArrowUp'");
    expect(VIEWER_ONLY).toContain("case 'ArrowDown'");
    expect(VIEWER_ONLY).toContain('controls.rotateLeft(');
    expect(VIEWER_ONLY).toContain('controls.rotateUp(');
  });

  it('gère +/- (et =/_) via dollyIn/dollyOut', () => {
    expect(VIEWER_ONLY).toMatch(/case '\+':/);
    expect(VIEWER_ONLY).toMatch(/case '-':/);
    expect(VIEWER_ONLY).toContain('controls.dollyIn(');
    expect(VIEWER_ONLY).toContain('controls.dollyOut(');
  });

  it('empêche le défilement de page sur une touche gérée (preventDefault)', () => {
    expect(VIEWER_ONLY).toContain('e.preventDefault()');
  });

  it('retire l’écouteur keydown à dispose() (aucune fuite)', () => {
    expect(VIEWER_ONLY).toContain("canvas.addEventListener('keydown', onKeyDown)");
    expect(VIEWER_ONLY).toContain("canvas.removeEventListener('keydown', onKeyDown)");
  });
});

describe('WJ90 — hint copy mentionne le clavier dans les 3 langues', () => {
  it('FR/EN/AR mentionnent flèches/arrow keys et +/-', () => {
    const hintMatch = PROPOSITION.match(/id="roof3d-hint"[\s\S]{0,900}?<\/p>/);
    expect(hintMatch).not.toBeNull();
    const hint = hintMatch![0];
    expect(hint).toMatch(/flèches/);
    expect(hint).toMatch(/arrow keys/);
    expect(hint).toMatch(/أسهم/);
  });
});
