import { describe, it, expect } from 'vitest'

/* NTMIG16 — le module « Migration ERP » est auto-enregistré : on vérifie la
   clé (elle doit correspondre au module_manifest backend, corrélation vérifiée
   par scripts/check_modules.py), la nav gatée admin et la route liste. */
describe('migration — module.config (NTMIG16)', () => {
  it('déclare la clé migration + nav + routes réservées admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('migration')

    const navListe = config.nav.items.find((i) => i.to === '/migration')
    expect(navListe).toBeTruthy()
    expect(navListe.roles).toEqual(['admin'])
    expect(navListe.icon).toBeTruthy()

    const paths = config.routes.map((r) => r.path)
    expect(paths).toContain('/migration')
    expect(paths).toContain('/migration/projet/:id')
    config.routes.forEach((r) => {
      expect(r.roles).toEqual(['admin'])
      expect(r.component).toBeTruthy()
    })
  })

  it('ne laisse aucune route de migration accessible hors admin', async () => {
    const { default: config } = await import('./module.config.jsx')
    const roles = new Set(
      config.routes.flatMap((r) => r.roles).concat(
        config.nav.items.flatMap((i) => i.roles)))
    expect([...roles]).toEqual(['admin'])
  })
})
