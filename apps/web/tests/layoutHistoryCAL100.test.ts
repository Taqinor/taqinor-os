// CAL100 — étendre annuler/rétablir à TOUT l'atelier (obstacles, zones, tracé, pose), pas au
// seul panneau de disposition. Généralisation de la mécanique DÉJÀ pure de layoutHistory.ts
// (createValueHistory : photo + tampon circulaire + drop) à un instantané qui couvre tout
// l'atelier — testée hors DOM, même esprit que layoutHistoryPV26.test.ts.
import { describe, expect, it } from 'vitest';
import { createWorkshopHistory, copyWorkshopSnapshot, type WorkshopSnapshot } from '../src/scripts/roofPro11/layoutHistory';
import { type Obstacle } from '../src/lib/obstacles';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

function snap(over: Partial<WorkshopSnapshot> = {}): WorkshopSnapshot {
  return {
    vertices: [[-7.6, 33.5]],
    obstacles: [],
    areas: [],
    roofType: 'flat',
    pitchDeg: 13,
    facingAzimuthDeg: 180,
    ...over,
  };
}

const obstacle = (over: Partial<Obstacle> = {}): Obstacle => ({
  id: 'obs1',
  centerLng: -7.6,
  centerLat: 33.5,
  lengthM: 0.6,
  widthM: 0.6,
  type: 'cheminee',
  ...over,
});

const area = (over: Partial<AreaRecord> = {}): AreaRecord => ({
  id: 'z1',
  label: 'Zone 1',
  vertices: [],
  obstacles: [],
  roofType: 'pitched',
  pitchDeg: 25,
  facingAzimuthDeg: 90,
  neededPanels: 0,
  neededAuto: true,
  result: null,
  renderPlan: null,
  ...over,
});

describe('CAL100 — createWorkshopHistory', () => {
  it('supprimer un obstacle puis annuler le restaure À L’IDENTIQUE (dimensions, type, provenance)', () => {
    const h = createWorkshopHistory();
    const obs = obstacle();
    const before = snap({ obstacles: [obs] });
    h.push(before);
    const after = snap({ obstacles: [] }); // l'obstacle a été retiré
    const restored = h.undo(after);
    expect(restored).toEqual(before);
    expect(restored?.obstacles[0]).toEqual(obs); // dimensions/type/provenance intacts
  });

  it('couvre AUSSI zones et tracé (pas seulement les obstacles)', () => {
    const h = createWorkshopHistory();
    const before = snap({
      vertices: [[-7.6, 33.5], [-7.601, 33.5]],
      areas: [area()],
    });
    h.push(before);
    const emptied = snap();
    const restored = h.undo(emptied);
    expect(restored?.vertices).toHaveLength(2);
    expect(restored?.areas).toHaveLength(1);
    expect(restored?.areas[0].pitchDeg).toBe(25);
  });

  it('rétablit ce qui vient d’être annulé (redo)', () => {
    const h = createWorkshopHistory();
    const before = snap({ pitchDeg: 10 });
    h.push(before);
    const after = snap({ pitchDeg: 30 });
    h.undo(after);
    expect(h.canRedo()).toBe(true);
    const redone = h.redo(before);
    expect(redone).toEqual(after);
  });

  it('les photos sont des COPIES PROFONDES : muter l’instantané vivant ne réécrit pas l’historique', () => {
    const h = createWorkshopHistory();
    const obs = obstacle();
    const live = snap({ obstacles: [obs] });
    h.push(live);
    live.obstacles[0].widthM = 99; // mutation APRÈS la photo
    live.vertices.push([0, 0]);
    const restored = h.undo(snap());
    expect(restored?.obstacles[0].widthM).toBe(0.6); // la photo, intacte
    expect(restored?.vertices).toHaveLength(1);
  });

  it('un geste finalement REFUSÉ : drop() jette la photo sans toucher au rétablir', () => {
    const h = createWorkshopHistory();
    h.push(snap({ pitchDeg: 5 }));
    expect(h.size().undo).toBe(1);
    expect(h.drop()).toBe(true);
    expect(h.size()).toEqual({ undo: 0, redo: 0 });
  });
});

describe('CAL100 — copyWorkshopSnapshot', () => {
  it('copie profonde des obstacles à l’intérieur des zones (areas[].obstacles)', () => {
    const original = snap({ areas: [area({ obstacles: [obstacle({ widthM: 1 })] })] });
    const copy = copyWorkshopSnapshot(original);
    copy.areas[0].obstacles[0].widthM = 999;
    expect(original.areas[0].obstacles[0].widthM).toBe(1);
  });
});
