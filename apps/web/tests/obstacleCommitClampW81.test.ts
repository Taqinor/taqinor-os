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
  for (const id of ['rp9-obs-length', 'rp9-obs-width', 'rp9-obs-height']) {
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

  // ACAL493 — hauteur saisie : « 1,2 » + change ⇒ heightM 1,2 ; champ vidé ⇒ propriété ABSENTE (jamais 0).
  it('la hauteur saisie est rangée au `change` ; vidée, elle est retirée', () => {
    const ctx = makeCtx();
    const ui = createObstaclesUi(ctx, { map: makeMap(), recalc: () => {}, setStatus: () => {} });
    ui.addObstacle(defaultObstacle('obs-1', [-7.5, 33.5]));
    const h = document.getElementById('rp9-obs-height') as HTMLInputElement;

    h.value = '1,2';
    h.dispatchEvent(new Event('change', { bubbles: true }));
    expect(ctx.obstacles[0].heightM).toBe(1.2);

    h.value = '';
    h.dispatchEvent(new Event('change', { bubbles: true }));
    expect('heightM' in ctx.obstacles[0]).toBe(false);
  });
});

// ACAL1032 — « Dupliquer » et « Poser en série » : une trame 3 × 2 = UNE photo d'historique.
describe('ACAL1032 — duplication et trame', () => {
  beforeEach(() => {
    setupDom();
    for (const [id, tag] of [
      ['rp9-obs-duplicate', 'button'], ['rp9-obs-grid-place', 'button'],
      ['rp9-obs-grid-spacing', 'input'], ['rp9-obs-grid-cols', 'input'], ['rp9-obs-grid-rows', 'input'],
    ]) {
      const e = document.createElement(tag);
      e.id = id;
      document.body.appendChild(e);
    }
  });
  const el = (id: string) => document.getElementById(id) as HTMLInputElement;
  function monte() {
    const ctx = makeCtx();
    let photos = 0;
    (ctx as unknown as { pushWorkshopHistory: () => void }).pushWorkshopHistory = () => { photos++; };
    const ui = createObstaclesUi(ctx, { map: makeMap(), recalc: () => {}, setStatus: () => {} });
    ui.addObstacle(defaultObstacle('obs-1', [-7.5, 33.5]));
    photos = 0;
    return { ctx, photos: () => photos };
  }

  it('« Dupliquer » ajoute une copie sélectionnée, en une photo', () => {
    const { ctx, photos } = monte();
    el('rp9-obs-duplicate').click();
    expect(ctx.obstacles).toHaveLength(2);
    expect(ctx.selectedObsId).toBe(ctx.obstacles[1].id);
    expect(photos()).toBe(1);
  });

  it('trame 3 m, 3 colonnes, 2 lignes : 6 obstacles, UNE seule photo', () => {
    const { ctx, photos } = monte();
    el('rp9-obs-grid-spacing').value = '3';
    el('rp9-obs-grid-cols').value = '3';
    el('rp9-obs-grid-rows').value = '2';
    el('rp9-obs-grid-place').click();
    expect(ctx.obstacles).toHaveLength(6);
    expect(photos()).toBe(1);
  });

  it('pas vide ou lignes à 0 : rien posé, aucune photo, champ fautif marqué', () => {
    const { ctx, photos } = monte();
    el('rp9-obs-grid-cols').value = '3';
    el('rp9-obs-grid-rows').value = '2';
    el('rp9-obs-grid-place').click();
    expect(ctx.obstacles).toHaveLength(1);
    expect(photos()).toBe(0);
    expect(el('rp9-obs-grid-spacing').getAttribute('aria-invalid')).toBe('true');
    expect(el('rp9-obs-grid-cols').hasAttribute('aria-invalid')).toBe(false);

    el('rp9-obs-grid-spacing').value = '3';
    el('rp9-obs-grid-rows').value = '0';
    el('rp9-obs-grid-place').click();
    expect(ctx.obstacles).toHaveLength(1);
    expect(el('rp9-obs-grid-rows').getAttribute('aria-invalid')).toBe('true');
    expect(el('rp9-obs-grid-spacing').hasAttribute('aria-invalid')).toBe(false);
  });
});
