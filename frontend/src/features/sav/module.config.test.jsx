import { describe, it, expect } from 'vitest'

/* ODY19 — Passe SAV : vérifie, comme `crm/module.config.test.jsx` /
   `reporting/module.config.test.jsx` le font pour leur propre ajout, que le
   nouveau cockpit `/sav/cockpit` existe EN ROUTE ET en entrée de nav (premier
   item, la porte d'entrée de l'app), et que le module reste zéro-orphelin :
   chaque route déclarée a une entrée de nav correspondante (ou est un cas
   documenté d'exception — aucun ici, toutes les routes SAV sont dans le menu
   APRÈS-VENTE). */
describe('sav — module.config (ODY19)', () => {
  it('déclare /sav/cockpit en route ET en premier item du menu APRÈS-VENTE', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('sav')

    const route = config.routes.find((r) => r.path === '/sav/cockpit')
    expect(route).toBeTruthy()

    expect(config.nav.items[0].to).toBe('/sav/cockpit')
    expect(config.nav.items[0].label).toBe('Cockpit')
    expect(config.nav.items[0].roles).toEqual(['normal', 'responsable', 'admin'])
    expect(config.nav.items[0].icon).toBeTruthy()
  })

  it('zéro route orpheline : chaque route a une entrée de nav', async () => {
    const { default: config } = await import('./module.config.jsx')
    const navPaths = new Set(config.nav.items.map((i) => i.to))
    for (const r of config.routes) {
      expect(navPaths.has(r.path)).toBe(true)
    }
    // ... et réciproquement (parité totale route <-> nav pour ce module).
    const routePaths = new Set(config.routes.map((r) => r.path))
    for (const to of navPaths) {
      expect(routePaths.has(to)).toBe(true)
    }
  })
})
