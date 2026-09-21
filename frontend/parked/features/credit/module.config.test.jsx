import { describe, it, expect } from 'vitest'

/* WIR55 — le module « Crédit client » (7 composants construits, zéro montage)
   est désormais enregistré : on vérifie que module.config.jsx expose la clé
   `credit`, la nav gatée responsable/admin, et les routes exposition /
   dérogations / conditions / fiche client — exactement comme les autres modules
   testent leur propre config (reporting/compta/adsengine). */
describe('credit — module.config (WIR55)', () => {
  it('déclare la clé credit + nav + routes gatées responsable/admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('credit')

    // Nav : exposition + dérogations.
    const navExpo = config.nav.items.find((i) => i.to === '/credit/exposition')
    const navDerog = config.nav.items.find((i) => i.to === '/credit/derogations')
    expect(navExpo).toBeTruthy()
    expect(navExpo.roles).toEqual(['responsable', 'admin'])
    expect(navExpo.icon).toBeTruthy()
    expect(navDerog).toBeTruthy()
    expect(navDerog.roles).toEqual(['responsable', 'admin'])

    // Routes attendues, toutes gatées responsable/admin.
    const paths = config.routes.map((r) => r.path)
    expect(paths).toContain('/credit/exposition')
    expect(paths).toContain('/credit/derogations')
    expect(paths).toContain('/credit/conditions')
    expect(paths).toContain('/credit/clients/:id')
    config.routes.forEach((r) => {
      expect(r.roles).toEqual(['responsable', 'admin'])
      expect(r.component).toBeTruthy()
    })
  })
})
