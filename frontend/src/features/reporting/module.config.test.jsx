import { describe, it, expect } from 'vitest'

/* WIR17(a) — « Cohortes » (`CohortsPage.jsx`, FG98) avait déjà sa route
   (`/reporting/cohortes`, gatée responsable/admin) mais aucune entrée de menu
   ANALYSE : on vérifie ici — comme `adsengine.test.jsx`/`compta.test.jsx` le
   font pour leur propre module — que route et nav existent et pointent vers
   le même rôle. Le reste des routes `reporting` (ex. archive client/chantier,
   dashboards) reste sans entrée de nav dédiée (ouvertes par clic depuis leur
   écran d'origine) : ce test ne vérifie donc pas de parité totale route↔nav,
   seulement l'ajout WIR17(a). */
describe('reporting — module.config (WIR17 Cohortes)', () => {
  it('déclare /reporting/cohortes en route ET en entrée du menu ANALYSE, gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('reporting')

    const route = config.routes.find((r) => r.path === '/reporting/cohortes')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])

    const navItem = config.nav.items.find((i) => i.to === '/reporting/cohortes')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Cohortes')
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })
})
