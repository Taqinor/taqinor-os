// PV71 — la MATRICE D'OMBRAGE 12 mois × 24 heures voyage avec le layout. Elle vit
// globalement sur le ctx (elle décrit l'horizon du site, pas une zone), donc elle est
// portée à la RACINE du JSON. Taille FIXE et facteurs arrondis : charge utile bornée.
import { describe, expect, it } from 'vitest';
import {
  serializeLayout,
  serializeShading,
  deserializeShading,
  SHADING_MONTHS,
  SHADING_HOURS,
} from '../src/scripts/roofPro11/prefill';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

/** Matrice 12 × 24 déterministe : dérate marqué le matin d'hiver, dégagé l'été. */
function matrix(): number[][] {
  return Array.from({ length: SHADING_MONTHS }, (_, m) =>
    Array.from({ length: SHADING_HOURS }, (_, h) => {
      if (h < 7 || h > 18) return 1; // nuit : aucun ombrage à modéliser
      const winter = m <= 1 || m >= 10;
      return winter && h < 10 ? 0.421 : 1;
    }),
  );
}

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function makeCtx(shadeFactors: number[][] | null): Ctx {
  const area: AreaRecord = {
    id: 'area-1',
    label: 'Zone 1',
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
  };
  return {
    areas: [area],
    activeAreaId: 'area-1',
    vertices: area.vertices,
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    layoutPlan: null,
    layoutOptimalCount: 0,
    layoutState: null,
    shadeFactors,
  } as unknown as Ctx;
}

describe('PV71 — round-trip de la matrice d’ombrage', () => {
  it('la matrice est portée par le layout et se relit à l’identique', () => {
    const layout = serializeLayout(makeCtx(matrix()), 9000);
    expect(layout.shading12x24).not.toBeNull();
    expect(layout.shading12x24!.length).toBe(SHADING_MONTHS);
    expect(layout.shading12x24![0].length).toBe(SHADING_HOURS);
    const back = deserializeShading(JSON.parse(JSON.stringify(layout)));
    expect(back).toEqual(matrix()); // valeurs déjà à 3 décimales → identité exacte
  });

  it('sans ombre tracée, la clé vaut null (jamais une matrice de 1 inventée)', () => {
    expect(serializeLayout(makeCtx(null), 9000).shading12x24).toBeNull();
    expect(deserializeShading({ shading12x24: null })).toBeNull();
    expect(deserializeShading(null)).toBeNull();
    expect(deserializeShading({})).toBeNull();
  });

  it('accepte aussi la matrice NUE (pas seulement l’objet layout)', () => {
    expect(deserializeShading(matrix())).toEqual(matrix());
  });
});

describe('PV71 — taille bornée et valeurs propres', () => {
  it('12 × 24 exactement, facteurs dans [0, 1] arrondis à 3 décimales', () => {
    const dirty = Array.from({ length: SHADING_MONTHS }, () => Array.from({ length: SHADING_HOURS }, () => 0.123456789));
    const out = serializeShading(dirty)!;
    expect(out.length).toBe(SHADING_MONTHS);
    for (const row of out) {
      expect(row.length).toBe(SHADING_HOURS);
      for (const v of row) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(1);
        expect(v).toBe(0.123); // arrondi à 3 décimales
      }
    }
  });

  it('la charge utile reste petite (< 4 ko) — c’est une taille FIXE', () => {
    const json = JSON.stringify(serializeShading(matrix()));
    expect(json.length).toBeLessThan(4000);
    // Le layout complet ne double pas de taille pour autant.
    const withShade = JSON.stringify(serializeLayout(makeCtx(matrix()), 9000)).length;
    const without = JSON.stringify(serializeLayout(makeCtx(null), 9000)).length;
    expect(withShade - without).toBeLessThan(4000);
  });

  it('les valeurs hors bornes sont bornées, pas rejetées', () => {
    const odd = Array.from({ length: SHADING_MONTHS }, () => Array.from({ length: SHADING_HOURS }, () => 5));
    expect(serializeShading(odd)![0][0]).toBe(1);
    const neg = Array.from({ length: SHADING_MONTHS }, () => Array.from({ length: SHADING_HOURS }, () => -2));
    expect(serializeShading(neg)![0][0]).toBe(0);
  });

  it('une matrice de MAUVAISE FORME est refusée en bloc (jamais à moitié lue)', () => {
    expect(serializeShading([])).toBeNull();
    expect(serializeShading(Array.from({ length: 11 }, () => Array(24).fill(1)))).toBeNull();
    expect(serializeShading(Array.from({ length: 12 }, () => Array(23).fill(1)))).toBeNull();
    const nan = Array.from({ length: 12 }, () => Array(24).fill(1));
    nan[3][5] = Number.NaN;
    expect(serializeShading(nan)).toBeNull();
  });

  it('la matrice relue est NEUVE (aucun alias sur le JSON d’entrée)', () => {
    const src = matrix();
    const back = deserializeShading(src)!;
    back[0][0] = 0;
    expect(src[0][0]).toBe(1);
  });
});
