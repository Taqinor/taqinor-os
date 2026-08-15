import { describe, it, expect } from 'vitest'

/* WIR172 — La nav RH REFLÈTE le gating serveur.
   ---------------------------------------------------------------------------
   `_RhBaseViewSet` est passée du grossier `IsResponsableOrAdmin` aux
   permissions fines `rh_voir` (lecture) / `rh_gerer` (écriture). Sans
   alignement de la nav, un rôle sans `rh_voir` (Commercial, Technicien,
   Viewer) continuerait de VOIR les écrans RH pour n'y récolter que des 403.
   Ce test verrouille l'alignement : tout écran de back-office RH porte
   `perm: 'rh_voir'`, et le portail self-service (servi par d'autres vues,
   ouvert à tous les rôles) ne le porte PAS. */

const PERM_RH = 'rh_voir'
const PORTAIL = '/rh/portail'

describe('rh — module.config : la nav est alignée sur rh_voir (WIR172)', () => {
  it('chaque entrée de nav du back-office RH exige rh_voir', async () => {
    const { default: config } = await import('./module.config.jsx')
    const backOffice = config.nav.items.filter((i) => i.to !== PORTAIL)
    expect(backOffice.length).toBeGreaterThan(0)
    const sansPerm = backOffice.filter((i) => i.perm !== PERM_RH)
    expect(sansPerm.map((i) => i.to)).toEqual([])
  })

  it('chaque route du back-office RH exige rh_voir', async () => {
    const { default: config } = await import('./module.config.jsx')
    const backOffice = config.routes.filter((r) => r.path !== PORTAIL)
    expect(backOffice.length).toBeGreaterThan(0)
    const sansPerm = backOffice.filter((r) => r.perm !== PERM_RH)
    expect(sansPerm.map((r) => r.path)).toEqual([])
  })

  it('le portail self-service reste ouvert à tous les rôles, sans perm', async () => {
    const { default: config } = await import('./module.config.jsx')
    const navPortail = config.nav.items.find((i) => i.to === PORTAIL)
    expect(navPortail, 'entrée de nav « Mon portail » introuvable').toBeDefined()
    expect(navPortail.perm).toBeUndefined()
    expect(navPortail.roles).toEqual(['normal', 'responsable', 'admin'])
    const routePortail = config.routes.find((r) => r.path === PORTAIL)
    expect(routePortail.perm).toBeUndefined()
  })

  it("aucune entrée de nav orpheline : chaque `to` correspond à une route", async () => {
    const { default: config } = await import('./module.config.jsx')
    const paths = new Set(config.routes.map((r) => r.path))
    const orphelines = config.nav.items.filter((i) => !paths.has(i.to))
    expect(orphelines.map((i) => i.to)).toEqual([])
  })
})
