// PV61 — DÉGAGEMENT PAR TYPE D'OBSTACLE. Le type ne touche pas la géométrie du
// rectangle : il fixe le recul laissé autour (cheminée 0,50 m ↔ antenne 0,30 m). Les
// packers (plat V2 + pente V3) lisent un tableau de dégagements PARALLÈLE aux
// obstructions ; une entrée absente retombe sur OBSTACLE_CLEARANCE_M (historique).
import { describe, expect, it } from 'vitest';
import { packConfig, OBSTACLE_CLEARANCE_M } from '../src/lib/estimatorBrainV2';
import { packFlushPlane } from '../src/lib/estimatorBrainV3';
import { obstacleRing, type Obstacle } from '../src/lib/obstacles';
import {
  OBSTACLE_TYPES,
  CLEARANCE_BY_TYPE,
  clearanceForType,
  obstructionClearancesFor,
} from '../src/scripts/roofPro11/types';
import { serializeLayout, deserializeLayout } from '../src/scripts/roofPro11/prefill';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';
import { type LngLat } from '../src/lib/roof';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LNG0 = -7.62;
const LAT0 = 33.59;

function rect(wEW: number, hNS: number): LngLat[] {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  const dLng = wEW / 2 / (DEG2M * cosLat);
  const dLat = hNS / 2 / DEG2M;
  return [
    [LNG0 - dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 + dLat],
    [LNG0 - dLng, LAT0 + dLat],
  ];
}
function obs(id: string, dxM: number, dyM: number, dim = 1.5, type?: Obstacle['type']): Obstacle {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  return {
    id,
    centerLng: LNG0 + dxM / (DEG2M * cosLat),
    centerLat: LAT0 + dyM / DEG2M,
    lengthM: dim,
    widthM: dim,
    ...(type ? { type } : {}),
  };
}

describe('PV61 — table des dégagements par type', () => {
  it('chaque type du sélecteur a un dégagement, et « autre » vaut le dégagement de base', () => {
    for (const t of OBSTACLE_TYPES) {
      expect(CLEARANCE_BY_TYPE[t.id], `type ${t.id}`).toBeGreaterThan(0);
      expect(t.label.length).toBeGreaterThan(0); // libellé FR pour le sélecteur
    }
    expect(CLEARANCE_BY_TYPE.autre).toBe(OBSTACLE_CLEARANCE_M);
    // Les obstacles HAUTS reculent plus que les petits/bas.
    expect(CLEARANCE_BY_TYPE.cheminee).toBeGreaterThan(CLEARANCE_BY_TYPE.antenne);
    expect(CLEARANCE_BY_TYPE.edicule).toBeGreaterThan(CLEARANCE_BY_TYPE.ventilation);
    expect(CLEARANCE_BY_TYPE.chien_assis).toBeGreaterThan(CLEARANCE_BY_TYPE.ventilation);
  });

  it('un type absent/inconnu retombe sur le dégagement de base (jamais 0)', () => {
    expect(clearanceForType(undefined)).toBe(OBSTACLE_CLEARANCE_M);
    expect(clearanceForType(null)).toBe(OBSTACLE_CLEARANCE_M);
    expect(clearanceForType('inconnu' as never)).toBe(OBSTACLE_CLEARANCE_M);
    expect(clearanceForType('cheminee')).toBe(CLEARANCE_BY_TYPE.cheminee);
  });

  it('obstructionClearancesFor garde l’ORDRE de la liste d’obstacles', () => {
    const list = [obs('a', 0, 0, 1.5, 'cheminee'), obs('b', 3, 0, 1.5), obs('c', -3, 0, 1.5, 'antenne')];
    expect(obstructionClearancesFor(list)).toEqual([
      CLEARANCE_BY_TYPE.cheminee,
      OBSTACLE_CLEARANCE_M,
      CLEARANCE_BY_TYPE.antenne,
    ]);
  });
});

describe('PV61 — les packers appliquent DEUX dégagements distincts', () => {
  const ring = rect(24, 14);
  // Deux obstacles IDENTIQUES (même taille), l'un cheminée (0,50 m), l'autre antenne (0,30 m).
  const cheminee = obs('o1', -6, 0, 1.5, 'cheminee');
  const antenne = obs('o2', 6, 0, 1.5, 'antenne');
  const rings = [obstacleRing(cheminee), obstacleRing(antenne)];

  it('toit plat : dégagement par type ≤ dégagement uniforme minimal, et > uniforme large', () => {
    const perType = packConfig(ring, LAT0, {
      family: 'south',
      tiltDeg: 13,
      obstructions: rings,
      obstructionClearancesM: obstructionClearancesFor([cheminee, antenne]),
    }).best.count;
    // Bornes honnêtes : mélanger 0,5 et 0,3 loge au plus autant qu'un 0,3 partout,
    // et au moins autant qu'un 0,5 partout.
    const allSmall = packConfig(ring, LAT0, { family: 'south', tiltDeg: 13, obstructions: rings, clearanceM: 0.3 }).best.count;
    const allLarge = packConfig(ring, LAT0, { family: 'south', tiltDeg: 13, obstructions: rings, clearanceM: 0.5 }).best.count;
    expect(allLarge).toBeLessThanOrEqual(allSmall);
    expect(perType).toBeLessThanOrEqual(allSmall);
    expect(perType).toBeGreaterThanOrEqual(allLarge);
    // Le recul ÉLARGI de la cheminée mord vraiment : on loge moins qu'avec 0,3 m partout.
    expect(perType).toBeLessThan(allSmall);
  });

  it('deux types → deux reculs différents : inverser les types change le calepinage', () => {
    const asIs = packConfig(ring, LAT0, {
      family: 'south',
      tiltDeg: 13,
      obstructions: rings,
      obstructionClearancesM: [CLEARANCE_BY_TYPE.cheminee, CLEARANCE_BY_TYPE.antenne],
    }).best;
    const swapped = packConfig(ring, LAT0, {
      family: 'south',
      tiltDeg: 13,
      obstructions: rings,
      obstructionClearancesM: [CLEARANCE_BY_TYPE.antenne, CLEARANCE_BY_TYPE.cheminee],
    }).best;
    // Le nombre peut coïncider (toit symétrique) mais le PLACEMENT, lui, diffère :
    // le recul large a changé de côté.
    expect(asIs.panels).not.toEqual(swapped.panels);
  });

  it('tableau absent → calepinage IDENTIQUE à l’uniforme historique', () => {
    const base = packConfig(ring, LAT0, { family: 'south', tiltDeg: 13, obstructions: rings }).best;
    const explicit = packConfig(ring, LAT0, {
      family: 'south',
      tiltDeg: 13,
      obstructions: rings,
      obstructionClearancesM: [OBSTACLE_CLEARANCE_M, OBSTACLE_CLEARANCE_M],
    }).best;
    expect(explicit.count).toBe(base.count);
    expect(explicit.panels).toEqual(base.panels);
  });

  it('entrée aberrante (NaN / négative / manquante) retombe sur le dégagement uniforme', () => {
    const base = packConfig(ring, LAT0, { family: 'south', tiltDeg: 13, obstructions: rings }).best.count;
    const junk = packConfig(ring, LAT0, {
      family: 'south',
      tiltDeg: 13,
      obstructions: rings,
      obstructionClearancesM: [Number.NaN, -3],
    }).best.count;
    expect(junk).toBe(base);
  });

  it('toit en PENTE : le dégagement par type passe aussi par le pan (packFlushPlane)', () => {
    const plane = {
      ring,
      pitchDeg: 25,
      facingAzimuthDeg: 180,
      obstructions: rings,
      obstructionClearancesM: obstructionClearancesFor([cheminee, antenne]),
    };
    const perType = packFlushPlane(plane).best.count;
    const allSmall = packFlushPlane({ ...plane, obstructionClearancesM: undefined }, { clearanceM: 0.3 }).best.count;
    const allLarge = packFlushPlane({ ...plane, obstructionClearancesM: undefined }, { clearanceM: 0.5 }).best.count;
    expect(perType).toBeLessThanOrEqual(allSmall);
    expect(perType).toBeGreaterThanOrEqual(allLarge);
  });
});

describe('PV61 — le type survit à la sérialisation du layout', () => {
  function makeCtx(obstacles: Obstacle[]): Ctx {
    const area: AreaRecord = {
      id: 'area-1',
      label: 'Zone 1',
      vertices: rect(20, 20),
      obstacles,
      roofType: 'flat',
      pitchDeg: 22,
      facingAzimuthDeg: 180,
      facingManual: false,
      neededPanels: 10,
      neededAuto: true,
      result: null,
      renderPlan: null,
    };
    return {
      areas: [area],
      activeAreaId: 'area-1',
      vertices: area.vertices,
      obstacles,
      roofType: 'flat',
      pitchDeg: 22,
      facingAzimuthDeg: 180,
      facingManual: false,
      neededPanels: 10,
      neededAuto: true,
    } as unknown as Ctx;
  }

  it('round-trip : un obstacle typé garde son type, un obstacle sans type n’en gagne aucun', () => {
    const typed = obs('o1', 0, 0, 2, 'cheminee');
    const untyped = obs('o2', 4, 0, 2);
    const layout = serializeLayout(makeCtx([typed, untyped]));
    expect(layout.zones[0].obstacles[0].type).toBe('cheminee');
    expect('type' in layout.zones[0].obstacles[1]).toBe(false);
    const back = deserializeLayout(layout);
    expect(back[0].obstacles[0].type).toBe('cheminee');
    expect(back[0].obstacles[1].type).toBeUndefined();
  });
});
