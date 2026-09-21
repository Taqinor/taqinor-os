import { describe, it, expect } from 'vitest'

/* AOF7 — Nav du module Appels d'offres : WIR166 EST ROUVERTE.
   ---------------------------------------------------------------------------
   Ce test verrouillait l'invariant INVERSE (« backend-only : zéro nav, zéro
   route »), qui était la bonne lecture d'ODY20 tant que WIR166 attendait une
   confirmation. **Le fondateur a confirmé le 2026-08-01** (en-tête du Groupe
   AOF dans `docs/PLAN.md`, tâche AOF7) : les écrans SPA sont autorisés et
   `module.config.jsx` porte désormais nav + titles + routes. L'ancienne
   assertion décrivait donc une intention PÉRIMÉE — elle est remplacée, pas
   supprimée.

   Ce qui SURVIT de l'intention d'origine, et qui est le vrai fond du test :
   la config reste l'ancrage de corrélation clé↔manifest backend
   (`scripts/check_modules.py`) et **aucune entrée de nav ne doit mener nulle
   part** — ce qui, à l'époque du zéro-route, était garanti trivialement et
   demande maintenant une vraie vérification. */

const PERM_RENTABILITE = 'ao_rentabilite_voir'

describe("ao — module.config (AOF7, WIR166 rouverte par le fondateur 2026-08-01)", () => {
  it("déclare la clé 'ao' — ancrage de corrélation avec le manifest backend", async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('ao')
  })

  it('expose une nav et des routes (les écrans SPA sont désormais autorisés)', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.nav).toBeDefined()
    expect(config.nav.items.length).toBeGreaterThan(0)
    expect(config.routes.length).toBeGreaterThan(0)
  })

  it("aucune entrée de nav orpheline : chaque `to` correspond à une route déclarée", async () => {
    const { default: config } = await import('./module.config.jsx')
    const paths = new Set(config.routes.map((r) => r.path))
    const orphelines = config.nav.items.filter((item) => !paths.has(item.to))
    expect(orphelines.map((i) => i.to)).toEqual([])
  })

  it("l'économie reste réservée au directeur : Rentabilité porte la permission élevée et le seul rôle admin", async () => {
    const { default: config } = await import('./module.config.jsx')
    const navRentabilite = config.nav.items.find((i) => i.to === '/ao/rentabilite')
    expect(navRentabilite, 'entrée de nav Rentabilité introuvable').toBeDefined()
    expect(navRentabilite.perm).toBe(PERM_RENTABILITE)
    expect(navRentabilite.roles).toEqual(['admin'])
    // Le gating de la NAV ne suffit pas : une route atteignable en tapant
    // l'URL doit porter la même garde.
    for (const route of config.routes.filter((r) => r.path.includes('rentabilite'))) {
      expect(route.perm, `route ${route.path} sans permission`).toBe(PERM_RENTABILITE)
      expect(route.roles, `route ${route.path} ouverte hors admin`).toEqual(['admin'])
    }
  })
})
