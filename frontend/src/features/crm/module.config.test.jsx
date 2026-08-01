import { describe, it, expect } from 'vitest'

/* WIR15/NTCRM7 — Forecast (`ForecastPage.jsx`) était construit/testé (appelle
   déjà `forecast-entries/`, `forecast/rollup/`, `forecast/historique/`) mais
   monté nulle part (ni route, ni menu), aucun travail backend requis. On
   vérifie ici — comme `adsengine.test.jsx`/`compta.test.jsx` le font pour leur
   propre module — que `/crm/forecast` existe en route ET en entrée de menu
   CRM.

   ODY15 — passe CRM (Groupe ODY, checklist commune « module.config COMPLET,
   zéro route orpheline ») ferme le dernier trou réel : `/crm/payloads-site-web`
   (QX16, rejeu des leads site web en échec) n'avait aucune entrée de nav, et
   l'app n'avait aucun cockpit (porte d'entrée). Deux routes RESTENT
   volontairement sans entrée de nav DÉDIÉE, ni bug ni oubli :
     - `/crm/leads/:id` — fiche détail (VX22), atteinte depuis la liste des
       leads, jamais un item de menu à part (même patron que toute fiche
       détail de l'ERP) ;
     - `/activites` — « Ma file » (VX83) est un écran CROSS-MODULE
       délibérément promu HORS de CRM vers le groupe de tête de la Sidebar
       (Sidebar.jsx:151-154) ; la ROUTE reste enregistrée ici (compat), le
       MENU n'appartient pas à CRM. */
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

describe('crm — module.config (ODY15 : cockpit + parité route↔nav)', () => {
  it('déclare /crm/cockpit en route ET en PREMIER item du menu CRM (convention nav.items[0] = cockpit)', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/crm/cockpit')
    expect(route).toBeTruthy()

    expect(config.nav.items[0].to).toBe('/crm/cockpit')
    expect(config.nav.items[0].label).toBe('Cockpit')
    expect(config.nav.items[0].roles).toEqual(['normal', 'responsable', 'admin'])
    expect(config.nav.items[0].icon).toBeTruthy()
  })

  it('/crm/payloads-site-web (QX16) a désormais une entrée de menu, réservée responsable/admin (miroir de la garde serveur)', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/crm/payloads-site-web')
    expect(route).toBeTruthy()

    const navItem = config.nav.items.find((i) => i.to === '/crm/payloads-site-web')
    expect(navItem).toBeTruthy()
    expect(navItem.roles).toEqual(['responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()
  })

  it('zéro route orpheline hors des deux exceptions documentées (fiche détail + /activites cross-module)', async () => {
    const { default: config } = await import('./module.config.jsx')

    const staticRoutes = config.routes
      .map((r) => r.path)
      .filter((p) => !p.includes(':'))
    const navTargets = config.nav.items.map((i) => i.to)
    const CROSS_MODULE_EXCEPTIONS = ['/activites']

    const orphans = staticRoutes.filter(
      (p) => !navTargets.includes(p) && !CROSS_MODULE_EXCEPTIONS.includes(p),
    )
    expect(orphans).toEqual([])

    // Chaque item de nav DOIT porter `roles` (BottomTabBar/Sidebar font
    // `it.roles.includes(role)` sans garde — un item sans `roles` crashe).
    for (const item of config.nav.items) {
      expect(Array.isArray(item.roles)).toBe(true)
      expect(item.roles.length).toBeGreaterThan(0)
    }
  })
})
