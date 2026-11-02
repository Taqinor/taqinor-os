/**
 * ENF19 — calcul commun des pages /ensoleillement-maroc (FR / EN / AR).
 * Le tableau affiché EST `YIELD_TABLE` (lecture seule, aucun recalcul) ; seuls
 * les libellés de ville sont fournis par la page (traduits).
 */
import { YIELD_TABLE } from './yieldTable';

export const AZIMUTHS = ['-90', '-45', '0', '45', '90'] as const;

export function ensoleillementData(cityLabels: Record<string, string>) {
  // Ordre par latitude croissante (Sud → Nord), comme dans estimatorBrain.ts.
  const cities = Object.entries(YIELD_TABLE)
    .map(([slug, data]) => ({ slug, label: cityLabels[slug] ?? slug, ...data }))
    .sort((a, b) => a.lat - b.lat);

  const tilts = Object.keys(cities[0].grid['0']).map(Number).sort((a, b) => a - b);

  // Meilleur couple (inclinaison, orientation) par ville — pour le résumé en tête de page.
  const bestByCity = cities.map((c) => {
    let best = { tilt: 0, azimuth: '0', value: 0 };
    for (const az of AZIMUTHS) {
      for (const [tiltStr, value] of Object.entries(c.grid[az] ?? {})) {
        if (value > best.value) best = { tilt: Number(tiltStr), azimuth: az, value };
      }
    }
    return { ...c, best };
  });

  return { cities, tilts, bestByCity };
}
