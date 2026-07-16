import { describe, it, expect } from 'vitest'
import { buildProductionChartData } from './ProductionPage.jsx'

/* VX148 — ProductionPage.jsx : l'écran le plus consulté du dossier monitoring
   n'avait AUCUN graphique (juste une table de relevés) — ses 4 voisins directs
   (PR mensuel/CO2/flotte…) en ont un. `buildProductionChartData` dérive la
   tendance kWh (chronologique) des mêmes relevés que la table, testée en
   isolation (pure, sans dépendre du rendu Radix Select/ResizeObserver). */

describe('buildProductionChartData (VX148)', () => {
  it('trie les relevés par date croissante et projette {label, value}', () => {
    const readings = [
      { date: '2026-07-01', energy_kwh: '135.2' },
      { date: '2026-06-01', energy_kwh: '120.5' },
    ]
    expect(buildProductionChartData(readings)).toEqual([
      { label: '2026-06-01', value: 120.5 },
      { label: '2026-07-01', value: 135.2 },
    ])
  })

  it('ignore les relevés sans date, jamais de NaN pour une énergie invalide', () => {
    const readings = [
      { date: '2026-06-01', energy_kwh: 'abc' },
      { energy_kwh: '50' }, // pas de date
    ]
    expect(buildProductionChartData(readings)).toEqual([
      { label: '2026-06-01', value: 0 },
    ])
  })

  it('liste vide → tableau vide (le graphe retombe sur ChartEmpty)', () => {
    expect(buildProductionChartData([])).toEqual([])
    expect(buildProductionChartData(undefined)).toEqual([])
  })
})
