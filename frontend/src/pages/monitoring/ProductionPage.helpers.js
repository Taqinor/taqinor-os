// ENF22 — helpers extraits de ProductionPage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { todayLocalIso } from '../../lib/dateLocale'

// VX148 — dérive la tendance kWh (chronologique) des relevés bruts. Extrait
// en fonction pure (nommée, exportée) pour un test unitaire direct, sans
// dépendre du rendu Radix Select/ResizeObserver.
export function buildProductionChartData(readings) {
  return [...(readings || [])]
    .filter((r) => r.date)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((r) => ({ label: r.date, value: Number(r.energy_kwh) || 0 }))
}

// AMON3 — la date d'un relevé est le PREMIER jour couvert : par défaut,
// aujourd'hui − période (jamais une période qui déborde sur le futur).
export function debutParDefaut(periode, aujourdhui = todayLocalIso()) {
  const jours = Math.max(Math.floor(Number(periode) || 1), 1)
  const d = new Date(`${aujourdhui}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() - jours)
  const deux = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${deux(d.getUTCMonth() + 1)}-${deux(d.getUTCDate())}`
}
