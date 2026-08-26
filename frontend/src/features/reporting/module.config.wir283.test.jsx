import { describe, it, expect } from 'vitest'

/* WIR283 — `/reporting/dashboards` (DashboardConfigPage) existait comme ROUTE
   sans aucune entrée de menu : c'était la dernière ligne `sans-nav` de la base
   `scripts/ecrans_atteignables_allow.txt` pour ce module. L'entrée est ajoutée
   JUSTE AVANT « Dashboards TV » (l'écran qui CRÉE les dashboards précède ceux
   qui les consomment) et avec les MÊMES rôles. */
describe('reporting — module.config (WIR283 config des dashboards)', () => {
  it('déclare /reporting/dashboards en route ET en entrée de nav, mêmes rôles', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/reporting/dashboards')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/reporting/dashboards')
    expect(navItem).toBeTruthy()
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.label).toBeTruthy()
  })

  it('se place AVANT « Dashboards TV » et avant le partage de dashboards', async () => {
    const { default: config } = await import('./module.config.jsx')
    const idx = (to) => config.nav.items.findIndex((i) => i.to === to)
    expect(idx('/reporting/dashboards')).toBeGreaterThanOrEqual(0)
    expect(idx('/reporting/dashboards')).toBeLessThan(idx('/dashboards-tv'))
    expect(idx('/reporting/dashboards')).toBeLessThan(idx('/reporting/dashboards/partage'))
  })
})
