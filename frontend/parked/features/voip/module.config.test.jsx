import { describe, it, expect } from 'vitest'

/* WIR160 — le module « Téléphonie / VoIP » (backend complet, aucune UI) est
   désormais enregistré : on vérifie que module.config.jsx expose la clé `voip`,
   la nav, et les routes journal / mes-identifiants / config société avec le bon
   gating (config société = responsable/admin ; le reste tout rôle). */
describe('voip — module.config (WIR160)', () => {
  it('déclare la clé voip + nav + routes avec le bon gating', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('voip')

    const paths = config.routes.map((r) => r.path)
    expect(paths).toContain('/voip')
    expect(paths).toContain('/voip/mes-identifiants')
    expect(paths).toContain('/voip/parametres')

    // Config société réservée responsable/admin.
    const params = config.routes.find((r) => r.path === '/voip/parametres')
    expect(params.roles).toEqual(['responsable', 'admin'])
    // Journal + identifiants ouverts à tout rôle authentifié.
    const journal = config.routes.find((r) => r.path === '/voip')
    expect(journal.roles).toContain('normal')

    // Nav : entrée click-to-call + une entrée config société gatée gestion.
    const navCall = config.nav.items.find((i) => i.to === '/voip')
    expect(navCall).toBeTruthy()
    const navParams = config.nav.items.find((i) => i.to === '/voip/parametres')
    expect(navParams.roles).toEqual(['responsable', 'admin'])
  })
})
