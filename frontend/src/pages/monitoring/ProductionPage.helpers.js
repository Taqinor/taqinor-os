// ENF22 — helpers extraits de ProductionPage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

// VX148 — dérive la tendance kWh (chronologique) des relevés bruts. Extrait
// en fonction pure (nommée, exportée) pour un test unitaire direct, sans
// dépendre du rendu Radix Select/ResizeObserver.
export function buildProductionChartData(readings) {
  return [...(readings || [])]
    .filter((r) => r.date)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((r) => ({ label: r.date, value: Number(r.energy_kwh) || 0 }))
}
