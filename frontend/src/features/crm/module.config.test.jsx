import { Suspense } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { estAutoriseEntree } from '../../router/moduleGating'

// VX22 — les deux écrans lead sont remplacés par des doublures identifiables :
// le test monte le composant que CHAQUE route désigne réellement et lit ce qui
// s'affiche (la route est lazy : le montage résout le vrai `import()`).
vi.mock('../../pages/crm/leads/LeadDetailPage', () => ({
  default: () => <div data-testid="ecran-fiche-lead" />,
}))
vi.mock('../../pages/crm/leads/LeadsPage', () => ({
  default: () => <div data-testid="ecran-liste-leads" />,
}))

afterEach(cleanup)

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
  /* APX1 (fondateur 2026-08-01) — cette assertion disait `items[0] === /crm/cockpit`.
     Elle est RETOURNÉE : la porte du CRM est `/crm/leads`, donc c'est LUI qui
     occupe `items[0]` (la convention « cockpit du module » lue par
     AppLauncher/PinnedApps/prefs). Le cockpit reste déclaré en route ET en
     entrée de nav — simplement plus en tête. Le verrou des 4 surfaces vit dans
     `crm-porte.test.jsx`. */
  it('déclare /crm/cockpit en route ET en entrée de menu (mais PAS en items[0] — APX1)', async () => {
    const { default: config } = await import('./module.config.jsx')

    const route = config.routes.find((r) => r.path === '/crm/cockpit')
    expect(route).toBeTruthy()

    const navItem = config.nav.items.find((i) => i.to === '/crm/cockpit')
    expect(navItem).toBeTruthy()
    expect(navItem.label).toBe('Cockpit')
    expect(navItem.roles).toEqual(['normal', 'responsable', 'admin'])
    expect(navItem.icon).toBeTruthy()

    expect(config.nav.items[0].to).not.toBe('/crm/cockpit')
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

/* VX22 — la fiche lead est adressable par une vraie route `/crm/leads/:id`,
   distincte de la liste `/crm/leads`, et charge sa PROPRE page (LeadDetailPage)
   au lieu de dépendre du cache de la liste. On monte le composant que chaque
   route déclare : c'est ce que le routeur rendrait. */
describe('crm — module.config (VX22 : fiche lead adressable)', () => {
  async function monter(chemin) {
    const { default: config } = await import('./module.config.jsx')
    const route = config.routes.find((r) => r.path === chemin)
    expect(route, `route ${chemin} absente`).toBeTruthy()
    const Ecran = route.component
    render(<Suspense fallback={null}><Ecran /></Suspense>)
    return route
  }

  it('/crm/leads/:id monte la page DÉDIÉE de la fiche, pas la liste', async () => {
    await monter('/crm/leads/:id')
    expect(await screen.findByTestId('ecran-fiche-lead')).toBeInTheDocument()
    expect(screen.queryByTestId('ecran-liste-leads')).not.toBeInTheDocument()
  })

  it('/crm/leads reste la LISTE (jamais écrasée par la route fiche)', async () => {
    await monter('/crm/leads')
    expect(await screen.findByTestId('ecran-liste-leads')).toBeInTheDocument()
    expect(screen.queryByTestId('ecran-fiche-lead')).not.toBeInTheDocument()
  })

  it('les deux routes sont distinctes : deux composants, deux chemins', async () => {
    const { default: config } = await import('./module.config.jsx')
    const liste = config.routes.find((r) => r.path === '/crm/leads')
    const fiche = config.routes.find((r) => r.path === '/crm/leads/:id')
    expect(liste.component).not.toBe(fiche.component)
    expect(config.routes.filter((r) => r.path === '/crm/leads')).toHaveLength(1)
    expect(config.routes.filter((r) => r.path === '/crm/leads/:id')).toHaveLength(1)
  })
})

/* T4-X8-016 (lot 8) — UNE règle par écran : la route et son entrée de menu portent la même garde
   (`{roles, perm, permRepliPalier}`), et la route la fait jouer à `roleLoader` (→ `/403` AVANT que la page ne
   lance une requête). Le Technicien (aucun `crm_*`) est refusé ; le Commercial et le compte légacy passent. */
describe('crm — module.config (T4-X8-016 : route et menu lisent la même règle)', () => {
  const garde = (e) => ({ roles: e.roles, perm: e.perm, permModule: e.permModule, permRepliPalier: e.permRepliPalier })
  const TECHNICIEN = ['installation_voir', 'sav_voir', 'stock_voir', 'visites_voir', 'calepinage_voir']

  it('chaque route gardée a une entrée de menu à la garde identique, et inversement', async () => {
    const { default: config } = await import('./module.config.jsx')
    const gardees = config.routes.filter((r) => r.perm || r.permModule)
    expect(gardees.filter((r) => r.perm).map((r) => r.path).sort()).toEqual([
      '/crm/cockpit', '/crm/concurrents-perte', '/crm/leads', '/crm/relances',
    ])
    expect(gardees.filter((r) => r.permModule).map((r) => r.path).sort()).toEqual([
      '/crm/defis', '/crm/parrainage', '/crm/profils-site',
    ])
    for (const route of gardees) {
      const item = config.nav.items.find((i) => i.to === route.path)
      expect(garde(item), route.path).toEqual(garde(route))
    }
    for (const item of config.nav.items.filter((i) => i.perm || i.permModule)) {
      expect(garde(config.routes.find((r) => r.path === item.to) ?? {}), item.to).toEqual(garde(item))
    }
  })

  it('/crm/leads : refusée au Technicien, ouverte au Commercial et au compte légacy de palier normal', async () => {
    const { default: config } = await import('./module.config.jsx')
    const route = config.routes.find((r) => r.path === '/crm/leads')
    expect(route.perm).toBe('crm_voir')
    expect(estAutoriseEntree(route, 'normal', TECHNICIEN)).toBe(false)
    expect(estAutoriseEntree(route, 'normal', ['crm_voir', 'crm_modifier'])).toBe(true)
    expect(estAutoriseEntree(route, 'normal', [])).toBe(true)
    // Écrans lisibles sans crm_voir : aucune garde ajoutée.
    for (const libre of ['/calendrier', '/crm', '/carte', '/crm/forecast']) {
      expect(config.routes.find((r) => r.path === libre).perm, libre).toBeUndefined()
    }
  })

  it('Défis, Parrainage, Profils site (LectureDuModule) : ouverts à un rôle crm_creer sans crm_voir, fermés au Technicien', async () => {
    const { default: config } = await import('./module.config.jsx')
    for (const chemin of ['/crm/defis', '/crm/parrainage', '/crm/profils-site']) {
      const route = config.routes.find((r) => r.path === chemin)
      const item = config.nav.items.find((i) => i.to === chemin)
      // Route gardée (`roles` + `permModule`) : `roleLoader` → `/403` avant le montage de la page.
      expect(route.permModule, chemin).toBe('crm')
      expect(route.perm, chemin).toBeUndefined()
      for (const entree of [route, item]) {
        expect(estAutoriseEntree(entree, 'normal', ['crm_creer']), chemin).toBe(true)
        expect(estAutoriseEntree(entree, 'normal', TECHNICIEN), chemin).toBe(false)
        expect(estAutoriseEntree(entree, 'normal', []), chemin).toBe(true)
      }
    }
    // … et /crm/leads, gardé par crm_voir côté serveur, lui reste refusé.
    expect(estAutoriseEntree(config.routes.find((r) => r.path === '/crm/leads'), 'normal', ['crm_creer'])).toBe(false)
  })
})
