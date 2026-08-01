import { describe, it, expect } from 'vitest'

/* ODY20 — Passe Appels d'offres (AO) : décision WIR166 déjà actée — le module
   reste BACKEND-ONLY tant qu'un besoin d'écran SPA n'est pas confirmé par le
   fondateur (aucun écran AO n'existe sous `frontend/src/pages/`). Ce test
   verrouille l'invariant : la config sert UNIQUEMENT d'ancrage de corrélation
   clé↔manifest backend (`scripts/check_modules.py`) — zéro nav, zéro route,
   donc zéro route orpheline possible. */
describe('ao — module.config (ODY20, WIR166 backend-only confirmé)', () => {
  it('déclare la clé sans nav ni routes (ancrage de corrélation uniquement)', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('ao')
    expect(config.nav).toBeUndefined()
    expect(config.routes ?? []).toHaveLength(0)
  })
})
