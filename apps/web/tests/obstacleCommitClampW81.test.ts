// @vitest-environment jsdom
//
// W81 — les champs numériques longueur/largeur d'un obstacle bornent (clampDim,
// snap <0,5 → 0,5) et recalculent à la VALIDATION (`change` : blur/Entrée), JAMAIS
// à chaque frappe. Avant : sur `input`, écraser un « 0,7 » en cours de saisie le
// ramenait à 0,5 au milieu de la frappe et relançait le re-pavage. On vérifie :
//   - un `input` intermédiaire ne borne pas, ne recalcule pas, ne modifie pas l'obstacle ;
//   - le `change` (commit) borne (<0,5 → 0,5) et déclenche un seul recalcul.
import { describe, expect, it, beforeEach } from 'vitest';
import { createObstaclesUi } from '../src/scripts/roofPro11/obstaclesUi';
import { defaultObstacle } from '../src/lib/obstacles';
import type { Ctx } from '../src/scripts/roofPro11/context';

const OBS_IDS = ['rp9-obstacle', 'rp9-obstacle-clear', 'rp9-obs-edit', 'rp9-obs-dims', 'rp9-obs-delete', 'rp9-obs-plus', 'rp9-obs-minus'];

function setupDom() {
  document.body.innerHTML = '';
  for (const id of OBS_IDS) {
    const e = document.createElement(id === 'rp9-obs-edit' ? 'div' : 'button');
    e.id = id;
    document.body.appendChild(e);
  }
  for (const id of ['rp9-obs-length', 'rp9-obs-width']) {
    const i = document.createElement('input');
    i.id = id;
    document.body.appendChild(i);
  }
}

// ctx minimal : seuls les champs lus/écrits par l'UI obstacle sont nécessaires.
function makeCtx(): Ctx {
  return {
    obstacles: [],
    selectedObsId: null,
    obstacleMode: false,
  } as unknown as Ctx;
}

// Carte stub : l'UI n'appelle map.* que dans des fonctions de rendu (getSource → undefined
// = no-op gracieux). Le constructeur ne fait que des lookups DOM + addEventListener.
function makeMap() {
  return {
    getSource: () => undefined,
    getCanvas: () => ({ style: {} }),
    dragPan: { enable() {}, disable() {} },
    queryRenderedFeatures: () => [],
    triggerRepaint() {},
  } as never;
}

const lengthEl = () => document.getElementById('rp9-obs-length') as HTMLInputElement;

describe('W81 — l\'obstacle est borné au commit, pas à chaque frappe', () => {
  beforeEach(setupDom);

  it('un `input` intermédiaire (« 0,7 » en cours) ne borne ni ne recalcule', () => {
    const ctx = makeCtx();
    let recalcs = 0;
    const ui = createObstaclesUi(ctx, { map: makeMap(), recalc: () => recalcs++, setStatus: () => {} });
    ui.addObstacle(defaultObstacle('obs-1', [-7.5, 33.5])); // 2 × 2 m, sélectionné
    recalcs = 0; // on remet à zéro après l'ajout

    lengthEl().value = '0.7';
    lengthEl().dispatchEvent(new Event('input', { bubbles: true }));

    // L'obstacle n'a PAS bougé et AUCUN recalcul n'a eu lieu sur `input`.
    expect(ctx.obstacles[0].lengthM).toBe(2);
    expect(recalcs).toBe(0);
  });

  it('le `change` (commit) borne <0,5 → 0,5 et recalcule UNE fois', () => {
    const ctx = makeCtx();
    let recalcs = 0;
    const ui = createObstaclesUi(ctx, { map: makeMap(), recalc: () => recalcs++, setStatus: () => {} });
    ui.addObstacle(defaultObstacle('obs-1', [-7.5, 33.5]));
    recalcs = 0;

    lengthEl().value = '0.2'; // sous le minimum
    lengthEl().dispatchEvent(new Event('change', { bubbles: true }));

    expect(ctx.obstacles[0].lengthM).toBe(0.5); // borné au commit
    expect(recalcs).toBe(1); // un seul recalcul
  });

  it('le `change` accepte une valeur valide sans la rejeter', () => {
    const ctx = makeCtx();
    const ui = createObstaclesUi(ctx, { map: makeMap(), recalc: () => {}, setStatus: () => {} });
    ui.addObstacle(defaultObstacle('obs-1', [-7.5, 33.5]));

    lengthEl().value = '3,5'; // virgule française
    lengthEl().dispatchEvent(new Event('change', { bubbles: true }));

    expect(ctx.obstacles[0].lengthM).toBe(3.5);
  });
});
