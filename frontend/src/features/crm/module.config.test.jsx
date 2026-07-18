import { describe, it, expect } from 'vitest'

/* WIR15/NTCRM7 — Forecast (`ForecastPage.jsx`) était construit/testé (appelle
   déjà `forecast-entries/`, `forecast/rollup/`, `forecast/historique/`) mais
   monté nulle part (ni route, ni menu), aucun travail backend requis. On
   vérifie ici — comme `adsengine.test.jsx`/`compta.test.jsx` le font pour leur
   propre module — que `/crm/forecast` existe en route ET en entrée de menu
   CRM. Le reste des routes `crm` (ex. `/crm/leads/:id`,
   `/crm/payloads-site-web`) reste sans entrée de nav dédiée : ce test ne
   vérifie donc pas de parité totale route↔nav, seulement l'ajout WIR15. */
describe('crm — module.config (WIR15 Forecast)', () => {
  it('déclare /crm/forecast en route ET en entrée du menu CRM', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('crm')

    const route = config.routes.find((r) => r.path === '/crm/forecast')
    expect(route).toBeTruthy()

    const navItem = config.nav.items.find((i) => i.to === '/crm/forecast')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Forecast')
    expect(navItem.roles).toEqual(['normal', 'responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})
