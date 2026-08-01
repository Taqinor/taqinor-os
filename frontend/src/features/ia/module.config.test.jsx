import { describe, it, expect } from 'vitest'

/* ODY23 — nouveau module.config « Intelligence » (`key: 'ia'`, absent
   jusqu'ici). Vérifie : la clé, le cockpit `/ia` déclaré en route ET en
   première entrée de menu (convention `nav.items[0]` = lien du cockpit,
   cf. `AppLauncher.jsx buildEntries`), et que les 3 outils historiques
   (OCR/Agent IA/Actions IA) gardent EXACTEMENT les gardes de rôle du menu
   INTELLIGENCE codé en dur (Sidebar.jsx, avant extraction ODY4) — même
   patron que `reporting`/`parametres` module.config.test.jsx (WIR17/WIR13). */
describe('ia — module.config (ODY23)', () => {
  it('déclare la clé "ia" et le cockpit /ia en route ET en 1re entrée de menu', async () => {
    const { default: config } = await import('./module.config.jsx')
    expect(config.key).toBe('ia')

    const route = config.routes.find((r) => r.path === '/ia')
    expect(route).toBeTruthy()

    expect(config.nav.items[0].to).toBe('/ia')
    expect(config.nav.items[0].icon).toBeTruthy()
  })

  it.each([
    ['/ia/ocr', 'OCR', ['responsable', 'admin']],
    ['/ia/agent', 'Agent IA', ['admin']],
    ['/ia/actions', 'Actions IA', ['normal', 'responsable', 'admin']],
  ])('déclare %s en entrée de menu "%s" gatée %j (route déjà enregistrée ailleurs)', async (path, label, roles) => {
    const { default: config } = await import('./module.config.jsx')
    const navItem = config.nav.items.find((i) => i.to === path)
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe(label)
    expect(navItem.roles).toEqual(roles)
    expect(navItem.icon).toBeTruthy()
  })

  it('ne redéclare PAS de route pour /ia/ocr, /ia/agent, /ia/actions (déjà dans router/index.jsx)', async () => {
    const { default: config } = await import('./module.config.jsx')
    const paths = config.routes.map((r) => r.path)
    expect(paths).not.toContain('/ia/ocr')
    expect(paths).not.toContain('/ia/agent')
    expect(paths).not.toContain('/ia/actions')
  })
})
