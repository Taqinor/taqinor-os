// ORDRE FONDATEUR (18/08) — « we introduce a system loss of 20% total ».
//
// UNE SEULE base de production pour tout le groupe : la page marketing, le
// tunnel d'estimation et le devis ERP annoncent le MÊME chiffre central pour la
// même ville et la même puissance.
//
// La table committée `yieldTable.ts` est une sortie PVGIS demandée à `loss=14`
// (apps/web/scripts/generate-yield-table.mjs, `const LOSS = 14`) : 14 % de
// pertes y sont DÉJÀ incluses. On applique donc le seul COMPLÉMENT
// (1 − 0,20)/(1 − 0,14) = 0,8/0,86 ≈ 0,9302 — jamais 20 % de plus, qui ferait
// 31 % cumulés.
//
// VERROU DE DÉRIVE à trois branches (les trois DOIVENT rester alignées) :
//   • ce fichier / apps/web/src/lib/estimatorBrainV2.ts  (site public)
//   • frontend/src/features/ventes/solar.js              (écran ERP)
//   • backend/django_core/apps/ventes/quote_engine/pricing.py (PDF)
// Le test « miroir » ci-dessous lit RÉELLEMENT les deux fichiers ERP sur disque
// et compare les constantes, pour qu'une modification d'un seul côté échoue ici.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  PRODUCTION_NET_FACTOR,
  PVGIS_BUILTIN_LOSS,
  SYSTEM_LOSS_TOTAL,
  specificYield,
  specificYieldPvgis14,
} from '../src/lib/estimatorBrainV2';
import { YIELD_TABLE } from '../src/lib/yieldTable';
import {
  FALLBACK_SPECIFIC_YIELD_KWH_PER_KWC,
  FALLBACK_SPECIFIC_YIELD_PVGIS14,
} from '../src/lib/productionEngine';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..', '..');

/** Casablanca, plein sud (aspect 0), inclinaison OPTIMALE 30° — le cas de
 *  référence, celui que l'ERP fige comme productible de la ville (1651). */
const CASA_LAT = 33.59;  // latitude EXACTE de la table (pas d'interpolation)
const CASA_TILT = 30;
const CASA_PVGIS14 = YIELD_TABLE.casablanca.grid['0']['30']; // 1651 kWh/kWc/an

describe('Pertes système 20 % AU TOTAL — la base du fondateur', () => {
  it('le facteur est le COMPLÉMENT, pas un second dérate', () => {
    expect(SYSTEM_LOSS_TOTAL).toBe(0.2);
    expect(PVGIS_BUILTIN_LOSS).toBe(0.14);
    expect(PRODUCTION_NET_FACTOR).toBe(0.8 / 0.86);
    expect(PRODUCTION_NET_FACTOR).toBeCloseTo(0.9302325581395349, 15);
    // Les pertes RÉELLEMENT subies par le productible brut valent bien 20 %.
    expect((1 - PVGIS_BUILTIN_LOSS) * PRODUCTION_NET_FACTOR).toBeCloseTo(0.8, 15);
  });

  it('specificYield rend le CENTRAL (base 20 %), specificYieldPvgis14 la donnée brute', () => {
    // Table Casablanca plein sud 30° (optimum) = 1651 kWh/kWc/an (base 14 %).
    expect(CASA_PVGIS14).toBe(1651);
    expect(specificYieldPvgis14(CASA_LAT, CASA_TILT, 0)).toBeCloseTo(1651, 6);
    // Central : 1651 × 0,9302325581 = 1535,81 kWh/kWc/an (dérivé à la main).
    expect(specificYield(CASA_LAT, CASA_TILT, 0)).toBeCloseTo(1535.8139534883721, 6);
    expect(specificYield(CASA_LAT, CASA_TILT, 0)).toBeCloseTo(
      specificYieldPvgis14(CASA_LAT, CASA_TILT, 0) * PRODUCTION_NET_FACTOR,
      9,
    );
  });

  it('CASABLANCA 10 kWc = 15 358 kWh/an — le MÊME chiffre que le devis ERP', () => {
    // Dérivation à la main : 10 kWc × 1651 = 16 510 kWh (base PVGIS 14 %) ;
    // × 0,9302325581 = 15 358,14 → 15 358 kWh/an.
    // Le backend calcule round(10 × 1651 × 0,9302325581) = 15 358 (voir
    // backend/django_core/apps/ventes/tests/test_battery_autoconso.py) et
    // l'écran ERP la même chose (frontend/.../solar.batterie.test.mjs).
    const central = 10 * specificYield(CASA_LAT, CASA_TILT, 0);
    expect(Math.round(central)).toBe(15358);
    expect(Math.round(10 * CASA_PVGIS14 * PRODUCTION_NET_FACTOR)).toBe(15358);
  });

  it('le repli hors-ligne de productionEngine suit la MÊME base', () => {
    expect(FALLBACK_SPECIFIC_YIELD_PVGIS14).toBe(1600);
    // 1600 × 0,9302325581 = 1488,37 kWh/kWc/an
    expect(FALLBACK_SPECIFIC_YIELD_KWH_PER_KWC).toBeCloseTo(1488.3720930232557, 6);
  });
});

describe('MIROIR à trois branches — site public ↔ écran ERP ↔ moteur PDF', () => {
  it('solar.js (écran ERP) porte les mêmes constantes de pertes', () => {
    const solar = readFileSync(
      join(REPO, 'frontend', 'src', 'features', 'ventes', 'solar.js'),
      'utf8',
    );
    expect(solar).toMatch(/export const SYSTEM_LOSS_TOTAL = 0\.20/);
    expect(solar).toMatch(/export const PVGIS_BUILTIN_LOSS = 0\.14/);
    expect(solar).toMatch(
      /export const PRODUCTIBLE_NET_FACTOR = \(1 - SYSTEM_LOSS_TOTAL\) \/ \(1 - PVGIS_BUILTIN_LOSS\)/,
    );
  });

  it('pricing.py (moteur PDF) porte les mêmes constantes de pertes', () => {
    const pricing = readFileSync(
      join(REPO, 'backend', 'django_core', 'apps', 'ventes', 'quote_engine', 'pricing.py'),
      'utf8',
    );
    expect(pricing).toMatch(/SYSTEM_LOSS_TOTAL = 0\.20/);
    expect(pricing).toMatch(/PVGIS_BUILTIN_LOSS = 0\.14/);
    expect(pricing).toMatch(
      /PRODUCTION_DERATE = \(1 - SYSTEM_LOSS_TOTAL\) \/ \(1 - PVGIS_BUILTIN_LOSS\)/,
    );
  });

  it('la table de productible PVGIS est la MÊME des deux côtés (villes communes)', () => {
    // Le productible par ville de solar.js est le plein-sud inclinaison optimale
    // de la table web : les deux doivent rester alignés (QX38).
    const solar = readFileSync(
      join(REPO, 'frontend', 'src', 'features', 'ventes', 'solar.js'),
      'utf8',
    );
    for (const [ville, attendu] of [
      ['agadir', 1687],
      ['marrakech', 1651],
      ['casablanca', 1651],
      ['rabat', 1630],
      ['tanger', 1634],
    ] as const) {
      expect(solar).toContain(`${ville}: ${attendu}`);
      const grid = YIELD_TABLE[ville];
      if (grid) {
        const best = Math.max(...Object.values(grid.grid['0']).map(Number));
        expect(best).toBe(attendu);
      }
    }
  });
});
