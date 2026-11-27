// WIR171 — Gating d'écran : un module dont la garde serveur suit
// `HasPermissionOrLegacy` (repli légacy palier responsable/admin, YRBAC3) ne
// doit jamais rester invisible à un rôle FIN qui porte la permission fine
// mais relève d'un palier de menu plus bas. SOLMVP40 (21/09/2026) a sorti du
// produit les cinq modules qui servaient jusque-là d'exemples à ce test
// (litiges/contrats/qhse/gestion_projet/kb, cf. frontend/parked/README.md) ;
// `visites` (VT2/VTA4) est aujourd'hui le SEUL module du MVP solaire dont le
// `module.config.jsx` déclare `permRepliPalier: true`
// (`features/visites/module.config.jsx` — vérifié : aucun autre module gardé
// ne porte `perm`/`permRepliPalier` à part `reporting`/`parametres`, qui sont
// justement l'exemple ET-STRICT sans repli couvert plus bas). C'est donc le
// seul cas réel restant pour prouver la sémantique serveur de bout en bout
// via la Sidebar et le lanceur d'apps.
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import Sidebar from './Sidebar'
import { moduleConfigs } from '../../router/moduleRoutes'
import { buildInstalledApps } from '../../lib/apps/useInstalledApps'

function makeStore({ role = 'normal', permissions = [], modulesDesactives = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions, modulesDesactives, user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

function renderSidebar({ path, ...opts }) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const navHrefs = (container) =>
  Array.from(container.querySelectorAll('.sidebar-nav a')).map((a) => a.getAttribute('href'))

// Extrait RÉEL de `COMMERCIAL_PERMISSIONS`
// (backend/django_core/apps/roles/models.py) : palier de menu 'normal'
// (authentication/role_tiers.py — le nom n'est pas un rôle système
// responsable) et pourtant porteur de `visites_voir` (VT2 : le commercial
// terrain remplit la visite, sans jamais se donner `visites_valider`).
const COMMERCIAL = ['crm_voir', 'crm_creer', 'ventes_voir', 'stock_voir', 'visites_voir']

describe('WIR171 — le seul module MVP solaire à repli légacy suit la sémantique serveur', () => {
  it('un Commercial (palier normal + visites_voir) voit la coquille « visites »', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: COMMERCIAL })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('un rôle fin de palier normal portant SEULEMENT visites_voir voit aussi « visites »', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: ['visites_voir'] })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('un rôle FIN de palier normal SANS la permission reste dehors sur « visites »', () => {
    const { container } = renderSidebar({
      path: '/visites', role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
    })
    expect(navHrefs(container)).not.toContain('/visites')
  })

  it('compte LÉGACY responsable (aucune permission servie) : « visites » inchangé', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'responsable', permissions: [] })
    expect(navHrefs(container)).toContain('/visites')
  })

  it('compte LÉGACY de palier normal : « visites » reste refusé (miroir is_responsable)', () => {
    const { container } = renderSidebar({ path: '/visites', role: 'normal', permissions: [] })
    expect(navHrefs(container)).not.toContain('/visites')
  })

  it('l’app « visites » apparaît au lanceur d’apps d’un Commercial', () => {
    const apps = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: COMMERCIAL })
    expect(apps.map((a) => a.key)).toContain('visites')
  })

  it('…et pas au lanceur d’un rôle fin dépourvu de visites_voir', () => {
    const apps = buildInstalledApps(moduleConfigs, {
      role: 'normal', permissions: ['crm_voir', 'ventes_voir'],
    })
    expect(apps.map((a) => a.key)).not.toContain('visites')
  })

  it('le Journal d’activité garde son ET STRICT (aucun repli légacy)', () => {
    // CanViewActivityLog exclut délibérément l'admin légacy sans rôle fin :
    // le relâchement WIR171 ne doit PAS déborder sur cette entrée.
    const legacyAdmin = buildInstalledApps(moduleConfigs, { role: 'admin', permissions: [] })
    const reporting = legacyAdmin.find((a) => a.key === 'reporting')
    // L'app reste visible par ses autres écrans, mais jamais via /journal.
    if (reporting) expect(reporting.to).not.toBe('/journal')
    const { container } = renderSidebar({ path: '/journal', role: 'admin', permissions: [] })
    expect(navHrefs(container)).not.toContain('/journal')
  })
})

/* T4-X8-016 (lot 8) — le menu CRM d'un rôle qui ne lit pas le CRM ne montre plus que les écrans qui
   s'ouvrent sans `crm_voir`. Permissions = extraits RÉELS du registre
   (`backend/django_core/apps/roles/permissions_registre.py`) : la liste complète pour le Technicien,
   les codes `crm_*` + quelques voisins pour les trois autres ; palier de menu = `authentication/role_tiers.py`. */
const TECHNICIEN = [
  'installation_voir', 'installation_gerer', 'intervention_gerer', 'equipement_voir', 'sav_voir', 'sav_gerer',
  'sav_repondre_client_externe', 'stock_voir', 'stock_mouvement', 'parametres_voir', 'reporting_voir',
  'client_pii_voir', 'qhse_voir', 'qhse_gerer', 'projet_voir', 'projet_gerer', 'contrat_voir', 'contrat_gerer',
  'litige_voir', 'litige_gerer', 'kb_voir', 'kb_gerer', 'ged_voir', 'ged_gerer', 'adsengine_view',
  'adsengine_manage', 'btp_voir', 'ux_vue_partager_equipe', 'ux_vue_definir_defaut_role', 'records_scope_equipe',
  'visites_voir', 'visites_modifier', 'calepinage_voir', 'calepinage_releve',
]
const COMMERCIAL_REEL = ['crm_voir', 'crm_creer', 'crm_modifier', 'crm_export', 'ventes_voir', 'prix_vente_voir']
const COMMERCIAL_RESP = [...COMMERCIAL_REEL, 'crm_reassign', 'crm_supprimer', 'users_voir']
const ADMINISTRATEUR = [...COMMERCIAL_RESP, 'roles_gerer', 'users_gerer']

// Le menu CRM tel qu'il était AVANT ce lot : chaque entrée jugée sur son seul palier.
const crmConfig = moduleConfigs.find((c) => c.key === 'crm')
const CRM_HREFS = new Set(crmConfig.nav.items.map((i) => i.to))
const menuCrm = (container) => navHrefs(container).filter((h) => CRM_HREFS.has(h))
const parPalier = (tier) => crmConfig.nav.items.filter((i) => i.roles.includes(tier)).map((i) => i.to)

describe('T4-X8-016 — le menu CRM suit la règle de ses routes', () => {
  it.each([
    ['Commercial', 'normal', COMMERCIAL_REEL],
    ['Commercial responsable', 'responsable', COMMERCIAL_RESP],
    ['Administrateur', 'admin', ADMINISTRATEUR],
  ])('%s : menu CRM inchangé (toutes les entrées de son palier)', (_nom, role, permissions) => {
    const { container } = renderSidebar({ path: '/calendrier', role, permissions })
    expect(menuCrm(container)).toEqual(parPalier(role))
    expect(menuCrm(container)).toContain('/crm/leads')
  })

  it('Technicien : plus aucune entrée dont l’écran exige crm_voir ou un code du module crm', () => {
    const { container } = renderSidebar({ path: '/calendrier', role: 'normal', permissions: TECHNICIEN })
    expect(menuCrm(container)).toEqual([
      '/calendrier', '/crm', '/crm/forecast', '/carte', '/crm/visiteurs', '/crm/attribution', '/crm/cockpit-equipe',
    ])
  })

  it('rôle PERSONNALISÉ « crm_creer » sans crm_voir : Défis, Parrainage et Profils site, jamais Leads', () => {
    const { container } = renderSidebar({ path: '/calendrier', role: 'normal', permissions: ['crm_creer'] })
    const menu = menuCrm(container)
    for (const lu of ['/crm/defis', '/crm/parrainage', '/crm/profils-site']) expect(menu).toContain(lu)
    for (const refuse of ['/crm/leads', '/crm/cockpit', '/crm/concurrents-perte', '/crm/relances']) {
      expect(menu).not.toContain(refuse)
    }
  })

  it('compte LÉGACY de palier normal (aucune permission servie) : menu CRM inchangé', () => {
    const { container } = renderSidebar({ path: '/calendrier', role: 'normal', permissions: [] })
    expect(menuCrm(container)).toEqual(parPalier('normal'))
  })

  it('lanceur : le CRM du Technicien s’ouvre sur une page qu’il peut lire, celui du Commercial sur les Leads', () => {
    const tech = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: TECHNICIEN })
    expect(tech.find((a) => a.key === 'crm')?.to).toBe('/calendrier')
    const commercial = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: COMMERCIAL_REEL })
    expect(commercial.find((a) => a.key === 'crm')?.to).toBe('/crm/leads')
    const personnalise = buildInstalledApps(moduleConfigs, { role: 'normal', permissions: ['crm_creer'] })
    expect(personnalise.find((a) => a.key === 'crm')?.to).toBe('/calendrier')
  })
})
